"""CherryAI GUI v2 Translation Step.

Sixth workflow tab for translation execution with live progress.
Provides prompt editing, per-request options, and progress tracking.

TASK 16.9: Integrates prompt_builder, conditional_prompts, and retry_handler
via gui/helpers/prompt_adapter.py for unified prompt management.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.helpers.chunker_adapter import count_tokens
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

# TASK 26.2: Import manifest binding helpers for request options
from CherryAI.gui.helpers.manifest_binding import (
    BindingInfo,
    bind_entry_to_field,
    bind_checkbox_to_field,
    bind_spinbox_to_field,
    bind_combobox_to_field,
)
from CherryAI.functions.manifest_fields import (
    get_all_lines_resolved,
    save_nested_text_field,
    load_nested_text_field,
    save_nested_float_field,
    load_nested_float_field,
    save_nested_int_field,
    load_nested_int_field,
    save_nested_bool_field,
    load_nested_bool_field,
)

# Import prompt adapter for prompt building and retry handling
from CherryAI.gui.helpers.prompt_adapter import (
    RetryStrategyView,
    RetryConfigView,
    ConditionalPromptView,
    PromptPreviewView,
    get_translation_style,
    get_game_summary,
    get_builtin_conditions,
    build_conditional_instructions,
    build_prompt_preview,
    get_retry_strategies,
    get_strategy_info,
    create_retry_config,
    handle_failed_lines,
)
from CherryAI.functions.common_errors import TranslationAbortError
from CherryAI.functions.config import get_model_pricing

# Lazy import targets for concurrent execution; resolved on first use.
_sort_requests_by_type = None
_RequestString = None

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


class LineStatus(Enum):
    """Status of a translatable line."""

    PENDING = "pending"
    TRANSLATING = "translating"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NEEDS_REVIEW = "needs_review"


class TranslationState(Enum):
    """State of the translation process."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TranslationProgress:
    """Progress data for translation."""

    total_lines: int = 0
    translated_lines: int = 0
    failed_lines: int = 0
    skipped_lines: int = 0
    current_chunk: int = 0
    total_chunks: int = 0
    tokens_used: int = 0
    start_time: float = 0.0
    elapsed_seconds: float = 0.0
    eta_seconds: float = 0.0
    tokens_per_second: float = 0.0

    @property
    def remaining_lines(self) -> int:
        """Lines remaining to translate."""
        return self.total_lines - self.translated_lines - self.failed_lines - self.skipped_lines

    @property
    def progress_percent(self) -> float:
        """Percentage complete."""
        if self.total_lines == 0:
            return 0.0
        return (self.translated_lines + self.failed_lines + self.skipped_lines) / self.total_lines * 100


@dataclass
class TranslationOptions:
    """Options for translation request.
    
    Includes all CLI-compatible options for translation:
    - API key and provider selection
    - Model and API settings
    - Retry and rate limiting
    - Style and token bans
    - Line-by-line mode for individual line translation
    - Thinking mode for extended reasoning (Claude models)
    - Edit before translation (Task 33.1)
    """

    # API key selection (provider, name from API.ini)
    api_key_provider: str = ""  # e.g. "gemini", "openai"
    api_key_name: str = ""  # e.g. "default"
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    chunk_size: int = 30
    retry_strategy: str = "batch"  # batch, contextual, isolated, skip
    max_retries: int = 3
    rate_limit_rpm: int = 60
    style_preset: str = ""
    banned_tokens: str = ""
    cache_enabled: bool = False
    # CLI-compatible options (TASK 16.11)
    line_by_line: bool = False  # Translate lines individually
    context_lines: int = 1  # Context lines for line-by-line mode
    thinking_enabled: bool = False  # Enable extended thinking (Claude)
    thinking_budget: int = 10000  # Token budget for thinking
    reasoning_effort: str = "medium"  # low/medium/high for reasoning models
    # Edit before translation (Task 33.1)
    edit_before_translation: bool = False  # Show edit dialog before API call
    # Skip already translated lines (Task 47.9)
    skip_already_translated: bool = False  # Skip lines with existing tl field
    # Request slicing mode: conservative (default) or efficient
    request_slicing: str = "conservative"
    # Request mode: normal, batch, flex, or priority
    request_mode: str = "normal"


@dataclass
class TranslatableLine:
    """A single translatable line with status."""

    idx: int
    original: str
    preprocessed: str
    edited_prepro: str = ""  # User-edited text (Task 33.1)
    translated: str = ""
    status: LineStatus = LineStatus.PENDING
    error_message: str = ""
    chunk_id: int = -1


class TranslationProgressWindow(tk.Toplevel):
    """Modal window for translation progress.

    Features:
    - Progress bar with percentage
    - ETA and token speed display
    - Lines translated/remaining/failed counts
    - Pause/Resume/Cancel controls
    - Inline log pane
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        """Initialize progress window.

        Args:
            parent: Parent widget.
            on_pause: Callback for pause button.
            on_resume: Callback for resume button.
            on_cancel: Callback for cancel button.
        """
        super().__init__(parent)
        self.title("Translation Progress")
        self.geometry("600x500")
        self.resizable(True, True)
        self.transient(parent)  # type: ignore[call-overload]

        self._on_pause = on_pause
        self._on_resume = on_resume
        self._on_cancel = on_cancel
        self._state = TranslationState.RUNNING
        self._progress = TranslationProgress()

        self._build_ui()

        # Focus this window (non-modal to allow API Log interaction)
        self.focus_set()

        # Prevent closing while running
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

    def _build_ui(self) -> None:
        """Build the progress window UI."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)

        # Progress section
        self._build_progress_section(main_frame)

        # Stats section
        self._build_stats_section(main_frame)

        # Controls section
        self._build_controls_section(main_frame)

        # Log section
        self._build_log_section(main_frame)

    def _build_progress_section(self, parent: ttk.Frame) -> None:
        """Build progress bar and percentage."""
        frame = ttk.LabelFrame(parent, text="Progress", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        # Progress bar
        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(
            frame,
            variable=self._progress_var,
            maximum=100,
            mode="determinate",
            length=400,
        )
        self._progress_bar.pack(fill="x", pady=(0, 5))

        # Progress label
        progress_info = ttk.Frame(frame)
        progress_info.pack(fill="x")

        self._percent_label = ttk.Label(
            progress_info,
            text="0%",
            font=("TkDefaultFont", 12, "bold"),
        )
        self._percent_label.pack(side="left")

        self._eta_label = ttk.Label(
            progress_info,
            text="ETA: --",
            foreground=THEME.text_secondary,
        )
        self._eta_label.pack(side="right")

        self._speed_label = ttk.Label(
            progress_info,
            text="",
            foreground=THEME.text_secondary,
        )
        self._speed_label.pack(side="right", padx=(0, 20))

    def _build_stats_section(self, parent: ttk.Frame) -> None:
        """Build statistics display."""
        frame = ttk.LabelFrame(parent, text="Statistics", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        stats_grid = ttk.Frame(frame)
        stats_grid.pack(fill="x")

        # Row 1: Lines
        ttk.Label(stats_grid, text="Lines:").grid(row=0, column=0, sticky="w")
        self._lines_label = ttk.Label(stats_grid, text="0 / 0")
        self._lines_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

        ttk.Label(stats_grid, text="Chunks:").grid(row=0, column=2, sticky="w", padx=(30, 0))
        self._chunks_label = ttk.Label(stats_grid, text="0 / 0")
        self._chunks_label.grid(row=0, column=3, sticky="w", padx=(10, 0))

        # Row 2: Status breakdown
        ttk.Label(stats_grid, text="Completed:").grid(row=1, column=0, sticky="w")
        self._completed_label = ttk.Label(
            stats_grid,
            text="0",
            foreground=THEME.accent_success,
        )
        self._completed_label.grid(row=1, column=1, sticky="w", padx=(10, 0))

        ttk.Label(stats_grid, text="Failed:").grid(row=1, column=2, sticky="w", padx=(30, 0))
        self._failed_label = ttk.Label(
            stats_grid,
            text="0",
            foreground=THEME.accent_error,
        )
        self._failed_label.grid(row=1, column=3, sticky="w", padx=(10, 0))

        # Row 3: Tokens and time
        ttk.Label(stats_grid, text="Tokens:").grid(row=2, column=0, sticky="w")
        self._tokens_label = ttk.Label(stats_grid, text="0")
        self._tokens_label.grid(row=2, column=1, sticky="w", padx=(10, 0))

        ttk.Label(stats_grid, text="Elapsed:").grid(row=2, column=2, sticky="w", padx=(30, 0))
        self._elapsed_label = ttk.Label(stats_grid, text="0s")
        self._elapsed_label.grid(row=2, column=3, sticky="w", padx=(10, 0))

    def _build_controls_section(self, parent: ttk.Frame) -> None:
        """Build control buttons."""
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 10))

        # State label
        self._state_label = ttk.Label(
            frame,
            text="● Running",
            foreground=THEME.accent_info,
            font=("TkDefaultFont", 10, "bold"),
        )
        self._state_label.pack(side="left")

        # Buttons
        self._cancel_btn = ttk.Button(
            frame,
            text="Cancel",
            command=self._on_cancel_click,
        )
        self._cancel_btn.pack(side="right")

        self._pause_btn = ttk.Button(
            frame,
            text="Pause",
            command=self._on_pause_click,
        )
        self._pause_btn.pack(side="right", padx=(0, 5))

    def _build_log_section(self, parent: ttk.Frame) -> None:
        """Build log output section."""
        frame = ttk.LabelFrame(parent, text="Log", padding=5)
        frame.pack(fill="both", expand=True)

        self._log_text = scrolledtext.ScrolledText(
            frame,
            height=10,
            state="disabled",
            wrap="word",
            font=("Consolas", 9),
        )
        self._log_text.pack(fill="both", expand=True)

    def update_progress(self, progress: TranslationProgress) -> None:
        """Update progress display.

        Args:
            progress: Current progress data.
        """
        self._progress = progress
        self._progress_var.set(progress.progress_percent)
        self._percent_label.configure(text=f"{progress.progress_percent:.1f}%")

        # ETA
        if progress.eta_seconds > 0:
            eta_str = self._format_time(progress.eta_seconds)
            self._eta_label.configure(text=f"ETA: {eta_str}")
        else:
            self._eta_label.configure(text="ETA: --")

        # Speed
        if progress.tokens_per_second > 0:
            self._speed_label.configure(text=f"{progress.tokens_per_second:.1f} tok/s")

        # Lines and chunks
        self._lines_label.configure(
            text=f"{progress.translated_lines} / {progress.total_lines}"
        )
        self._chunks_label.configure(
            text=f"{progress.current_chunk} / {progress.total_chunks}"
        )

        # Status counts
        self._completed_label.configure(text=str(progress.translated_lines))
        self._failed_label.configure(text=str(progress.failed_lines))
        self._tokens_label.configure(text=f"{progress.tokens_used:,}")
        self._elapsed_label.configure(text=self._format_time(progress.elapsed_seconds))

    def set_state(self, state: TranslationState) -> None:
        """Set current translation state.

        Args:
            state: New state.
        """
        self._state = state

        if state == TranslationState.RUNNING:
            self._state_label.configure(text="● Running", foreground=THEME.accent_info)
            self._pause_btn.configure(text="Pause", state="normal")
            self._cancel_btn.configure(state="normal")
        elif state == TranslationState.PAUSED:
            self._state_label.configure(text="● Paused", foreground=THEME.accent_warning)
            self._pause_btn.configure(text="Resume", state="normal")
            self._cancel_btn.configure(state="normal")
        elif state == TranslationState.COMPLETED:
            self._state_label.configure(text="✓ Completed", foreground=THEME.accent_success)
            self._pause_btn.configure(state="disabled")
            self._cancel_btn.configure(text="Close", state="normal")
        elif state == TranslationState.FAILED:
            self._state_label.configure(text="✗ Failed", foreground=THEME.accent_error)
            self._pause_btn.configure(state="disabled")
            self._cancel_btn.configure(text="Close", state="normal")
        elif state == TranslationState.CANCELLED:
            self._state_label.configure(text="⊘ Cancelled", foreground=THEME.text_secondary)
            self._pause_btn.configure(state="disabled")
            self._cancel_btn.configure(text="Close", state="normal")

    def log(self, message: str) -> None:
        """Add message to log.

        Args:
            message: Message to log.
        """
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"

    def _on_pause_click(self) -> None:
        """Handle pause/resume button click."""
        if self._state == TranslationState.RUNNING:
            self._on_pause()
        elif self._state == TranslationState.PAUSED:
            self._on_resume()

    def _on_cancel_click(self) -> None:
        """Handle cancel button click."""
        if self._state in (TranslationState.COMPLETED, TranslationState.FAILED, TranslationState.CANCELLED):
            self.destroy()
        else:
            if messagebox.askyesno("Cancel Translation", "Are you sure you want to cancel?"):
                self._on_cancel()

    def _on_close_attempt(self) -> None:
        """Handle window close attempt."""
        if self._state in (TranslationState.COMPLETED, TranslationState.FAILED, TranslationState.CANCELLED):
            self.destroy()
        else:
            if messagebox.askyesno("Cancel Translation", "Translation in progress. Cancel?"):
                self._on_cancel()


class EditPreviewDialog(tk.Toplevel):
    """Modal dialog for editing preprocessed text before translation.
    
    Task 33.1: Shows preprocessed lines in an editable view, allowing
    user to make adjustments before sending to the translation API.
    
    Features:
    - Shows all pending lines with their preprocessed text
    - Allows inline editing of preprocessed text
    - Supports undo/redo within the editor
    - Preview changes with clear visual diff
    - Apply changes to save edited_prepro field
    """
    
    RESULT_APPLY: str = "apply"
    RESULT_CANCEL: str = "cancel"
    
    def __init__(
        self,
        parent: tk.Widget,
        lines: List["TranslatableLine"],
    ) -> None:
        """Initialize edit preview dialog.
        
        Args:
            parent: Parent widget.
            lines: Lines to edit (pending lines).
        """
        super().__init__(parent)
        self._lines = lines
        self._result: str = self.RESULT_CANCEL
        self._edited_data: Dict[int, str] = {}  # idx -> edited text
        
        self.title("Edit Before Translation")
        self.transient(parent)
        self.grab_set()
        
        # Size and position
        self.geometry("900x600")
        self.minsize(600, 400)
        self.update_idletasks()
        
        # Center on parent
        parent_widget = self.winfo_toplevel()
        x = parent_widget.winfo_x() + (parent_widget.winfo_width() // 2) - 450
        y = parent_widget.winfo_y() + (parent_widget.winfo_height() // 2) - 300
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        
        self._build_ui()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Bind keys
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.bind("<Control-Return>", lambda e: self._on_apply())
        
        # Focus on first text entry
        self._text_widgets[0].focus_set() if self._text_widgets else None
    
    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(
            header_frame,
            text="Edit Preprocessed Text",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side="left")
        
        ttk.Label(
            header_frame,
            text=f"{len(self._lines)} lines",
            foreground=THEME.text_secondary,
        ).pack(side="right")
        
        # Info text
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(
            info_frame,
            text="Make any adjustments to the preprocessed text before translation. "
                 "Changes are saved to the manifest.",
            wraplength=800,
            foreground=THEME.text_secondary,
        ).pack(anchor="w")
        
        # Scrollable content area
        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self._scroll_frame = ttk.Frame(canvas)
        
        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mousewheel scrolling (scoped to canvas, not bind_all)
        def _on_mousewheel(event: tk.Event) -> None:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        # Also bind on child frames so scrolling works when hovering over content
        self._scroll_frame.bind("<MouseWheel>", _on_mousewheel)
        
        # Build line editors
        self._text_widgets: List[tk.Text] = []
        self._build_line_editors()
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
        ).pack(side="right", padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Apply and Continue",
            command=self._on_apply,
        ).pack(side="right")
        
        # Hint
        ttk.Label(
            button_frame,
            text="Ctrl+Enter to apply",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(side="left")
    
    def _build_line_editors(self) -> None:
        """Build editable text widgets for each line."""
        for i, line in enumerate(self._lines):
            frame = ttk.LabelFrame(
                self._scroll_frame,
                text=f"Line {line.idx + 1}",
                padding=5,
            )
            frame.pack(fill="x", padx=5, pady=2)
            
            # Original text (read-only reference)
            orig_frame = ttk.Frame(frame)
            orig_frame.pack(fill="x", pady=(0, 2))
            
            ttk.Label(
                orig_frame,
                text="Original:",
                foreground=THEME.text_secondary,
                width=10,
            ).pack(side="left")
            
            orig_text = line.original[:100] + "..." if len(line.original) > 100 else line.original
            ttk.Label(
                orig_frame,
                text=orig_text,
                foreground=THEME.text_secondary,
            ).pack(side="left", fill="x")
            
            # Editable preprocessed text
            edit_frame = ttk.Frame(frame)
            edit_frame.pack(fill="x")
            
            ttk.Label(
                edit_frame,
                text="Edit:",
                width=10,
            ).pack(side="left", anchor="n")
            
            text_widget = tk.Text(
                edit_frame,
                height=2,
                wrap="word",
                font=("TkDefaultFont", 9),
            )
            text_widget.pack(side="left", fill="x", expand=True)
            
            # Insert current text (use edited_prepro if available, else preprocessed)
            current_text = line.edited_prepro if line.edited_prepro else line.preprocessed
            text_widget.insert("1.0", current_text)
            
            # Store reference
            text_widget._line_idx = line.idx  # type: ignore
            self._text_widgets.append(text_widget)
    
    def _on_apply(self) -> None:
        """Apply edits and close dialog."""
        # Collect edited text from all widgets
        for widget in self._text_widgets:
            idx = widget._line_idx  # type: ignore
            text = widget.get("1.0", "end-1c").strip()
            
            # Only store if different from preprocessed
            original_line = next((l for l in self._lines if l.idx == idx), None)
            if original_line:
                if text != original_line.preprocessed:
                    self._edited_data[idx] = text
                elif original_line.edited_prepro:
                    # Clear edited_prepro if user reverted to original preprocessed
                    self._edited_data[idx] = ""
        
        self._result = self.RESULT_APPLY
        self.destroy()
    
    def _on_cancel(self) -> None:
        """Cancel and close dialog."""
        self._result = self.RESULT_CANCEL
        self.destroy()
    
    @property
    def result(self) -> str:
        """Get dialog result."""
        return self._result
    
    @property
    def edited_data(self) -> Dict[int, str]:
        """Get edited data mapping idx -> edited text."""
        return self._edited_data


# ======================================================================
# Preview Request data model and dialog
# ======================================================================

# Filter part keys — order matches the toolbar dropdown and spec §5.2
FILTER_PARTS: List[Tuple[str, str]] = [
    ("meta", "Meta"),
    ("language", "Language"),
    ("system_instructions", "System Instructions"),
    ("io_examples", "I/O Examples"),
    ("style", "Style"),
    ("tone", "Tone"),
    ("summary", "Summary"),
    ("genre", "Genre"),
    ("pov", "Point of View"),
    ("conditional_prompts", "Conditional Prompts"),
    ("glossary", "Glossary"),
    ("rolling_context", "Rolling Context"),
    ("input_lines", "Input Lines"),
]

# Extended header descriptions for Formatted view — shown in === headers
SECTION_DESCRIPTIONS: Dict[str, str] = {
    "meta": "Section headers (===) are for display only and not sent to the API",
    "language": "Source → Target language pair from Information step",
    "system_instructions": "General instructions from Information step",
    "io_examples": "Auto-generated translation examples from I/O example bank",
    "style": "Translation style guidelines from Information step",
    "tone": "Translation tone and register from Information step",
    "summary": "Game/project context summary from Information step",
    "genre": "Content genre classification from Information step",
    "pov": "Narrative perspective detected by Analysis step",
    "conditional_prompts": "Auto-detected pattern-based instructions",
    "glossary": "Term translations and character names",
    "rolling_context": "Previous translations for continuity (per-chunk)",
    "input_lines": "Lines to translate — sent as user message",
}


@dataclass
class PreviewRequest:
    """One API request with labelled parts for filtering."""

    index: int
    meta: str
    language: str
    system_instructions: str
    io_examples: str
    summary: str
    style: str
    tone: str
    genre: str
    pov: str
    conditional_prompts: str
    glossary: str
    rolling_context: str
    input_lines: str
    full_system_prompt: str
    line_count: int = 0

    def get_part(self, key: str) -> str:
        """Return the text of a named part."""
        return str(getattr(self, key, ""))

    def build_full_request_text(
        self,
        active_parts: Optional[set[str]] = None,
    ) -> str:
        """Assemble the visible request text honouring active filters.

        Section headers include informative descriptions so users
        understand which parts are sent to the API and where data
        originates.  Input lines are displayed one-per-line for
        readability while curly braces ``{`` / ``}`` are preserved.

        Args:
            active_parts: Set of part keys to include.  ``None`` = all.

        Returns:
            Concatenated request text.
        """
        if active_parts is None:
            active_parts = {k for k, _ in FILTER_PARTS}

        sections: list[str] = []
        for key, label in FILTER_PARTS:
            if key not in active_parts:
                continue
            text = self.get_part(key)
            if not text:
                continue

            # Expand input_lines JSON so each line is on its own row
            if key == "input_lines":
                text = self._format_input_lines(text)

            desc = SECTION_DESCRIPTIONS.get(key, "")
            if desc:
                header = f"=== {label} ({desc}) ==="
            else:
                header = f"=== {label} ==="
            sections.append(f"{header}\n{text}")
        return "\n\n".join(sections)

    @staticmethod
    def _format_input_lines(raw_json: str) -> str:
        """Pretty-format the input-lines JSON so every line gets a line break.

        Preserves curly braces and other symbols that appear inside
        the actual line content.

        Args:
            raw_json: JSON string, e.g. ``{"lines": [...]}``.

        Returns:
            Human-readable multiline representation.
        """
        try:
            data = json.loads(raw_json)
            lines = data.get("lines", [])
            if not lines:
                return raw_json
            numbered: list[str] = []
            for idx, line in enumerate(lines, 1):
                numbered.append(f"  {idx:>3}. {line}")
            return "{\n" + "\n".join(numbered) + "\n}"
        except (json.JSONDecodeError, TypeError, AttributeError):
            return raw_json

    def build_pure_json(self) -> str:
        """Build a single-line JSON of the complete API request payload."""
        messages = [
            {"role": "system", "content": self.full_system_prompt},
            {"role": "user", "content": self.input_lines},
        ]
        payload: dict[str, Any] = {
            "model": self.meta.split("\n")[0].replace("model: ", ""),
            "messages": messages,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        # Extract temperature from meta
        for line in self.meta.split("\n"):
            if line.startswith("temperature:"):
                try:
                    payload["temperature"] = float(
                        line.split(":")[1].strip(),
                    )
                except ValueError:
                    pass
        return json.dumps(payload, ensure_ascii=False)


class RequestPreviewDialog(tk.Toplevel):
    """Read-only dialog showing all API requests as they would be sent.

    Features:
        * **Jump To** — request number spinner + total label.
        * **View** dropdown — Pure / Formatted / Plain.
        * **Search** — text entry with Previous / Next and match count.
        * **Filter** — checkboxes for each request part.
        * Selectable (but not editable) text area.
    """

    _VIEW_PURE = "Pure"
    _VIEW_FORMATTED = "Formatted"
    _VIEW_PLAIN = "Plain"
    _VIEW_OPTIONS = [_VIEW_PURE, _VIEW_FORMATTED, _VIEW_PLAIN]

    def __init__(
        self,
        parent: tk.Widget,
        requests: List[PreviewRequest],
    ) -> None:
        super().__init__(parent)
        self.title("Request Preview")
        self.geometry("950x700")
        self.minsize(700, 400)
        self.transient(parent)  # type: ignore[call-overload]

        self._requests = requests
        self._current_idx = 0  # 0-based index of displayed request
        self._view_mode: str = self._VIEW_FORMATTED
        self._search_matches: list[str] = []  # tk text indices (current req)
        self._search_match_idx = -1

        # Cross-request search state
        self._cross_counts: list[int] = []   # match count per request
        self._cross_total: int = 0           # sum of all counts
        self._cross_global_idx: int = -1     # current global match index

        # Active filter parts (all enabled by default)
        self._active_filters: dict[str, tk.BooleanVar] = {}

        self._build_ui()
        self._render_current_request()

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _: self.destroy())
        self.grab_set()
        self.focus_set()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the full dialog layout."""
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        self._build_toolbar(main)
        self._build_text_area(main)
        self._build_footer(main)

    def _build_toolbar(self, parent: ttk.Frame) -> None:
        """Build the top toolbar row."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 6))

        # --- Jump To ---
        ttk.Label(toolbar, text="Request:").pack(side="left")
        self._jump_var = tk.IntVar(value=1)
        self._jump_spin = ttk.Spinbox(
            toolbar,
            from_=1,
            to=max(len(self._requests), 1),
            textvariable=self._jump_var,
            width=5,
            command=self._on_jump,
        )
        self._jump_spin.pack(side="left", padx=(4, 0))
        self._jump_spin.bind("<Return>", lambda _: self._on_jump())

        self._total_label = ttk.Label(
            toolbar, text=f"/ {len(self._requests)}",
        )
        self._total_label.pack(side="left", padx=(2, 10))

        # --- View Mode ---
        ttk.Label(toolbar, text="View:").pack(side="left")
        self._view_var = tk.StringVar(value=self._VIEW_FORMATTED)
        view_combo = ttk.Combobox(
            toolbar,
            textvariable=self._view_var,
            values=self._VIEW_OPTIONS,
            state="readonly",
            width=11,
        )
        view_combo.pack(side="left", padx=(4, 10))
        view_combo.bind("<<ComboboxSelected>>", self._on_view_change)

        # --- Search ---
        ttk.Label(toolbar, text="Search:").pack(side="left")
        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(
            toolbar, textvariable=self._search_var, width=18,
        )
        self._search_entry.pack(side="left", padx=(4, 2))
        self._search_entry.bind("<Return>", lambda _: self._do_search())

        ttk.Button(
            toolbar, text="◀", width=2, command=self._search_prev,
        ).pack(side="left")
        ttk.Button(
            toolbar, text="▶", width=2, command=self._search_next,
        ).pack(side="left")
        self._match_label = ttk.Label(toolbar, text="0 / 0")
        self._match_label.pack(side="left", padx=(4, 10))

        # --- Filter dropdown (Menubutton with checkboxes) ---
        self._filter_btn = ttk.Menubutton(toolbar, text="Filter ▾")
        self._filter_btn.pack(side="left")
        filter_menu = tk.Menu(self._filter_btn, tearoff=False)
        self._filter_btn["menu"] = filter_menu

        for key, label in FILTER_PARTS:
            var = tk.BooleanVar(value=True)
            self._active_filters[key] = var
            filter_menu.add_checkbutton(
                label=label,
                variable=var,
                command=self._on_filter_change,
            )

        filter_menu.add_separator()
        filter_menu.add_command(
            label="Select All",
            command=lambda: self._set_all_filters(True),
        )
        filter_menu.add_command(
            label="Deselect All",
            command=lambda: self._set_all_filters(False),
        )

    def _build_text_area(self, parent: ttk.Frame) -> None:
        """Build the main scrollable text display."""
        text_frame = ttk.Frame(parent)
        text_frame.pack(fill="both", expand=True)

        self._text = tk.Text(
            text_frame,
            wrap="none",
            font=("Consolas", 9),
            state="disabled",
            exportselection=True,
        )
        yscroll = ttk.Scrollbar(
            text_frame, orient="vertical", command=self._text.yview,
        )
        xscroll = ttk.Scrollbar(
            text_frame, orient="horizontal", command=self._text.xview,
        )
        self._text.configure(
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set,
        )
        self._text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        # Tag for search highlights
        self._text.tag_configure(
            "search_hl",
            background="#FFFF00",
            foreground="#000000",
        )
        self._text.tag_configure(
            "search_current",
            background="#FF8800",
            foreground="#FFFFFF",
        )

    def _build_footer(self, parent: ttk.Frame) -> None:
        """Build the footer with info and close button."""
        footer = ttk.Frame(parent)
        footer.pack(fill="x", pady=(6, 0))

        self._info_label = ttk.Label(
            footer, text="", foreground=THEME.text_secondary,
        )
        self._info_label.pack(side="left")

        ttk.Button(footer, text="Close", command=self.destroy).pack(
            side="right",
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_current_request(self) -> None:
        """Render the request at ``self._current_idx`` into the text area."""
        if not self._requests:
            return

        req = self._requests[self._current_idx]
        active = {
            k for k, v in self._active_filters.items() if v.get()
        }
        mode = self._view_var.get()

        if mode == self._VIEW_PURE:
            content = req.build_pure_json()
        elif mode == self._VIEW_PLAIN:
            raw = req.build_full_request_text(active)
            # Strip JSON/code artefacts and word-wrap
            content = self._plain_text(raw)
        else:
            # Formatted (default)
            content = req.build_full_request_text(active)

        # Set wrap mode based on view
        if mode == self._VIEW_PLAIN:
            self._text.configure(wrap="word")
        else:
            self._text.configure(wrap="none")

        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", content)
        self._text.configure(state="disabled")

        # Info label — count the actual API payload, not the display
        prompt_text = req.full_system_prompt or ""
        input_text = req.input_lines or ""
        try:
            prompt_tok, _ = count_tokens(prompt_text)
        except Exception:
            prompt_tok = len(prompt_text) // 4
        try:
            input_tok, _ = count_tokens(input_text)
        except Exception:
            input_tok = len(input_text) // 4
        self._info_label.configure(
            text=(
                f"Request {self._current_idx + 1} of "
                f"{len(self._requests)}  |  "
                f"{req.line_count} lines  |  "
                f"~{prompt_tok + input_tok:,} tokens "
                f"(~{prompt_tok:,} prompt, ~{input_tok:,} input)"
            ),
        )

        # Re-apply local search highlights if a search is active
        term = self._search_var.get()
        if term:
            self._highlight_local_matches(term)

    # ------------------------------------------------------------------
    # View helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _plain_text(raw: str) -> str:
        """Convert raw request text to plain readable text.

        Strips only JSON structural tokens (brackets, quotes around
        keys) while preserving curly braces ``{`` / ``}`` that appear
        inside the actual content (e.g. RPG Maker control codes).
        Each input line gets its own visual line break.
        """
        import textwrap
        import re as _re

        cleaned = raw
        cleaned = cleaned.replace("\\n", "\n")

        # Remove only square brackets and double-quotes (preserve { } )
        cleaned = _re.sub(r'[\[\]"]', "", cleaned)
        cleaned = _re.sub(r",\s*$", "", cleaned, flags=_re.MULTILINE)
        cleaned = _re.sub(r"^\s*translations:\s*", "", cleaned, flags=_re.MULTILINE)
        cleaned = _re.sub(r"^\s*lines:\s*", "", cleaned, flags=_re.MULTILINE)
        cleaned = _re.sub(r"^\s*role:\s*\w+\s*$", "", cleaned, flags=_re.MULTILINE)
        cleaned = _re.sub(r"^\s*content:\s*", "", cleaned, flags=_re.MULTILINE)

        # Collapse multiple blank lines
        cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned)

        # Word wrap to ~100 chars
        wrapped_lines: list[str] = []
        for line in cleaned.split("\n"):
            if len(line) > 100:
                wrapped_lines.extend(textwrap.wrap(line, width=100))
            else:
                wrapped_lines.append(line)

        return "\n".join(wrapped_lines).strip()

    # ------------------------------------------------------------------
    # Jump To
    # ------------------------------------------------------------------

    def _on_jump(self) -> None:
        """Handle Jump To spinbox change."""
        try:
            val = self._jump_var.get()
        except tk.TclError:
            return
        idx = max(0, min(val - 1, len(self._requests) - 1))
        self._current_idx = idx
        self._jump_var.set(idx + 1)
        self._render_current_request()

    # ------------------------------------------------------------------
    # View mode
    # ------------------------------------------------------------------

    def _on_view_change(self, _event: object = None) -> None:
        """Handle View dropdown change."""
        self._render_current_request()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _do_search(self) -> None:
        """Run search across ALL requests and highlight current request matches.

        Builds per-request match counts so that Previous/Next can
        navigate across request boundaries seamlessly.
        """
        term = self._search_var.get()

        # Clear highlights on current text widget
        self._text.tag_remove("search_hl", "1.0", "end")
        self._text.tag_remove("search_current", "1.0", "end")
        self._search_matches.clear()
        self._search_match_idx = -1
        self._cross_counts.clear()
        self._cross_total = 0
        self._cross_global_idx = -1

        if not term:
            self._match_label.configure(text="0 / 0")
            return

        # Count matches in every request (using rendered text)
        active = {k for k, v in self._active_filters.items() if v.get()}
        mode = self._view_var.get()
        lower_term = term.lower()
        for req in self._requests:
            content = self._render_text_for_request(req, active, mode)
            count = content.lower().count(lower_term)
            self._cross_counts.append(count)
        self._cross_total = sum(self._cross_counts)

        # Highlight matches in the currently displayed request
        self._highlight_local_matches(term)

        total = self._cross_total
        if total:
            # Set global index to first match in current request, or 0
            offset = sum(self._cross_counts[:self._current_idx])
            if self._search_matches:
                self._cross_global_idx = offset
                self._search_match_idx = 0
                self._highlight_current_match()
            else:
                self._cross_global_idx = 0
                self._search_match_idx = -1
        self._update_match_label()

    def _render_text_for_request(
        self,
        req: "PreviewRequest",
        active: set[str],
        mode: str,
    ) -> str:
        """Render request text without touching the widget.

        Args:
            req: The request to render.
            active: Active filter keys.
            mode: View mode string.

        Returns:
            Rendered text string.
        """
        if mode == self._VIEW_PURE:
            return req.build_pure_json()
        elif mode == self._VIEW_PLAIN:
            return self._plain_text(req.build_full_request_text(active))
        return req.build_full_request_text(active)

    def _highlight_local_matches(self, term: str) -> None:
        """Find and highlight all matches of *term* in the text widget.

        Populates ``_search_matches`` with tk text indices.

        Args:
            term: Search term (case-insensitive).
        """
        self._text.tag_remove("search_hl", "1.0", "end")
        self._text.tag_remove("search_current", "1.0", "end")
        self._search_matches.clear()

        start = "1.0"
        while True:
            pos = self._text.search(
                term, start, stopindex="end", nocase=True,
            )
            if not pos:
                break
            end_pos = f"{pos}+{len(term)}c"
            self._text.tag_add("search_hl", pos, end_pos)
            self._search_matches.append(pos)
            start = end_pos

    def _highlight_current_match(self) -> None:
        """Highlight the current match distinctively and scroll to it."""
        self._text.tag_remove("search_current", "1.0", "end")
        if 0 <= self._search_match_idx < len(self._search_matches):
            pos = self._search_matches[self._search_match_idx]
            term = self._search_var.get()
            end_pos = f"{pos}+{len(term)}c"
            self._text.tag_add("search_current", pos, end_pos)
            self._text.see(pos)

    def _update_match_label(self) -> None:
        """Update the match count label with global index/total."""
        if self._cross_total:
            self._match_label.configure(
                text=(
                    f"{self._cross_global_idx + 1} / "
                    f"{self._cross_total}"
                ),
            )
        else:
            self._match_label.configure(text="0 / 0")

    def _resolve_global_index(self, global_idx: int) -> tuple[int, int]:
        """Map a global match index to (request_idx, local_match_idx).

        Args:
            global_idx: 0-based index across all requests.

        Returns:
            Tuple of (request index, local match index within that request).
        """
        cumulative = 0
        for req_idx, count in enumerate(self._cross_counts):
            if cumulative + count > global_idx:
                return req_idx, global_idx - cumulative
            cumulative += count
        # Fallback — should not happen
        return len(self._requests) - 1, 0

    def _navigate_to_global_match(self, global_idx: int) -> None:
        """Switch to the request containing ``global_idx`` and highlight.

        Args:
            global_idx: 0-based global match index.
        """
        req_idx, local_idx = self._resolve_global_index(global_idx)
        self._cross_global_idx = global_idx

        if req_idx != self._current_idx:
            self._current_idx = req_idx
            self._jump_var.set(req_idx + 1)
            self._render_current_request()
            # _render_current_request calls _do_search if search active,
            # which would reset global state.  Re-highlight instead.
            term = self._search_var.get()
            self._highlight_local_matches(term)

        self._search_match_idx = local_idx
        self._highlight_current_match()
        self._update_match_label()

    def _search_next(self) -> None:
        """Move to the next search match (cross-request)."""
        if self._cross_total == 0:
            self._do_search()
            return
        new_idx = (self._cross_global_idx + 1) % self._cross_total
        self._navigate_to_global_match(new_idx)

    def _search_prev(self) -> None:
        """Move to the previous search match (cross-request)."""
        if self._cross_total == 0:
            self._do_search()
            return
        new_idx = (self._cross_global_idx - 1) % self._cross_total
        self._navigate_to_global_match(new_idx)

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------

    def _on_filter_change(self) -> None:
        """Re-render after a filter checkbox changes."""
        self._render_current_request()

    def _set_all_filters(self, state: bool) -> None:
        """Set all filter checkboxes to *state* and re-render."""
        for var in self._active_filters.values():
            var.set(state)
        self._render_current_request()


class TranslationStep(BaseStep):
    """Translation step for executing translations with live progress.

    Features:
    - Table view with translatable lines and per-line status
    - Prompt editor (style, summary, glossary, conditional prompts, ban tokens)
    - Per-request options (model, temperature, chunk-size, retry strategy)
    - Translation progress window modal
    - API usage panel
    - Integration with api_client.py
    """

    step_id = 5
    step_name = "Translation"
    # Test visibility for explicit import expectation
    _IMPORT_EXPECTATION = "from functions.api_client import"

    # Model options for dropdown (TASK 43.5: Mock Translation always available)
    # This list is used only as a last-resort fallback; the primary model list
    # is populated from model_registry (dynamic) or Global Options (user-configured).
    MODEL_OPTIONS = [
        "Mock Translation",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-4o-mini",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "mistral-large-latest",
        "mistral-small-latest",
    ]

    # Mapping from API.ini provider names to model_registry provider IDs.
    _KEY_PROVIDER_TO_REGISTRY: Dict[str, str] = {
        "gemini": "google",
        "openai": "openai",
        "mistral": "mistral",
        "anthropic": "anthropic",
        "lmstudio": "lmstudio",
        "local": "local",
        "ollama": "ollama",
    }

    # Retry strategy options - TASK 43.10: Only Batch and Contextual visible in UI
    # Isolated and Skip still supported internally for CLI compatibility
    RETRY_STRATEGIES = [
        (RetryStrategyView.BATCH.value, RetryStrategyView.BATCH.display_name),
        (RetryStrategyView.CONTEXTUAL.value, RetryStrategyView.CONTEXTUAL.display_name),
    ]
    # Full set kept for CLI/internal use
    ALL_RETRY_STRATEGIES = [
        (RetryStrategyView.BATCH.value, RetryStrategyView.BATCH.display_name),
        (RetryStrategyView.CONTEXTUAL.value, RetryStrategyView.CONTEXTUAL.display_name),
        (RetryStrategyView.ISOLATED.value, RetryStrategyView.ISOLATED.display_name),
        (RetryStrategyView.SKIP.value, RetryStrategyView.SKIP.display_name),
    ]

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize Translation step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables BEFORE super().__init__
        # because base class calls _build_ui() which needs these
        self._lines: List[TranslatableLine] = []
        self._translation_options = TranslationOptions()
        self._translation_state = TranslationState.IDLE
        self._progress = TranslationProgress()
        self._progress_window: Optional[TranslationProgressWindow] = None
        self._translation_thread: Optional[threading.Thread] = None
        self._cancel_requested = False
        self._pause_requested = False
        self._api_client: Any = None
        # TASK 26.2: Track manifest bindings for request options
        self._manifest_bindings: List[BindingInfo] = []
        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the step UI."""
        self._build_header()
        self._build_content()
        self._build_api_usage_panel()

    def _build_header(self) -> None:
        """Build the header section with controls."""
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # Left: Title and status
        left_frame = ttk.Frame(header)
        left_frame.pack(side="left")

        ttk.Label(
            left_frame,
            text="Translation",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side="left")

        self._status_label = ttk.Label(
            left_frame,
            text="Ready",
            foreground=THEME.text_secondary,
        )
        self._status_label.pack(side="left", padx=(10, 0))

        # Right: Buttons
        right_frame = ttk.Frame(header)
        right_frame.pack(side="right")

        self._translate_btn = ttk.Button(
            right_frame,
            text="▶ Start Translation",
            command=self._start_translation,
        )
        self._translate_btn.pack(side="right")

        ttk.Button(
            right_frame,
            text="↻ Refresh Lines",
            command=self._refresh_lines,
        ).pack(side="right", padx=(0, 5))

        ttk.Button(
            right_frame,
            text="👁 Preview Requests",
            command=self._show_request_preview,
            width=16,
        ).pack(side="right", padx=(0, 5))

    def _build_content(self) -> None:
        """Build the main content area."""
        # Main paned window (horizontal)
        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Lines table
        left_frame = ttk.LabelFrame(content, text="Translatable Lines")
        content.add(left_frame, weight=2)
        self._build_lines_table(left_frame)

        # Right: Options panels
        right_frame = ttk.Frame(content)
        content.add(right_frame, weight=1)
        self._build_options_panels(right_frame)

    def _build_lines_table(self, parent: ttk.LabelFrame) -> None:
        """Build the lines table view.

        TASK 43.3: Merged Original/Preprocessed into "To be Translated".
        """
        columns = [
            ColumnDef(key="idx", title="#", width=50, anchor="center"),
            ColumnDef(key="status", title="Status", width=80, anchor="center"),
            ColumnDef(key="to_translate", title="To be Translated", width=300),
            ColumnDef(key="translated", title="Translated", width=300),
        ]

        self._lines_table = SharedTable(
            parent,
            columns=columns,
            show_filter=True,
            show_checkboxes=False,
            show_count_filter=False,
        )
        self._lines_table.pack(fill="both", expand=True)

    def _build_options_panels(self, parent: ttk.Frame) -> None:
        """Build the options panels on the right side."""
        # Create a scrollable frame for all options
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Request options panel
        self._build_request_options(scrollable_frame)

        # Prompt editor panel
        self._build_prompt_editor(scrollable_frame)

        # Enable mousewheel scrolling (scoped to canvas, not bind_all)
        def _on_mousewheel(event: tk.Event) -> None:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        # Also bind on child frames so scrolling works when hovering over content
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)

    def _build_request_options(self, parent: ttk.Frame) -> None:
        """Build per-request options panel.

        Visible widgets: Key, Model, Model Settings / Translation Options
        Change… buttons, Character Whitelist, Character Blacklist, and
        Ban Tokens.  Settings that moved to Global Options (chunk size,
        retries, caching, retry strategy, line-by-line, etc.) are kept
        as hidden variables for backward compatibility.
        """
        frame = ttk.LabelFrame(parent, text="Request Options", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # API Key selection (row 1) — populated from saved keys in API.ini
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill="x", pady=2)

        ttk.Label(key_frame, text="Key:").pack(side="left")
        self._key_var = tk.StringVar(value="")
        self._key_combo = ttk.Combobox(
            key_frame,
            textvariable=self._key_var,
            values=[],
            state="readonly",
            width=20,
        )
        self._key_combo.pack(side="right")
        self._key_combo.bind("<<ComboboxSelected>>", self._on_key_changed)

        # Model selection (row 2) — filtered by selected key's provider
        model_frame = ttk.Frame(frame)
        model_frame.pack(fill="x", pady=2)

        ttk.Label(model_frame, text="Model:").pack(side="left")
        self._model_var = tk.StringVar(value=self._translation_options.model)
        self._model_combo = ttk.Combobox(
            model_frame,
            textvariable=self._model_var,
            values=self.MODEL_OPTIONS,
            state="readonly",
            width=20,
        )
        self._model_combo.pack(side="right")

        # Bind model to manifest
        self._manifest_bindings.append(
            bind_combobox_to_field(
                combobox=self._model_combo,
                var=self._model_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="Model",
                options=self.MODEL_OPTIONS,
                default="gpt-4o-mini",
                parent_key="RequestOptions",
            )
        )

        # Request Mode selection (row 3) — Normal / Batch / Flex / Priority
        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill="x", pady=2)

        ttk.Label(mode_frame, text="Request Mode:").pack(side="left")
        self._request_mode_var = tk.StringVar(value="Normal")
        self._request_mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self._request_mode_var,
            values=["Normal", "Batch", "Flex", "Priority"],
            state="readonly",
            width=20,
        )
        self._request_mode_combo.pack(side="right")
        self._request_mode_combo.bind(
            "<<ComboboxSelected>>", self._on_request_mode_changed,
        )

        # Bind request mode to manifest
        self._manifest_bindings.append(
            bind_combobox_to_field(
                combobox=self._request_mode_combo,
                var=self._request_mode_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="RequestMode",
                options=["Normal", "Batch", "Flex", "Priority"],
                default="Normal",
                parent_key="RequestOptions",
            )
        )

        # Populate keys only after all dependent request widgets exist.
        self._populate_key_dropdown()
        self._refresh_request_mode_options()

        # Model Settings — open Global Options dialog at Model Settings
        ms_frame = ttk.Frame(frame)
        ms_frame.pack(fill="x", pady=2)

        ttk.Label(ms_frame, text="Model Settings:").pack(side="left")
        ttk.Button(
            ms_frame, text="Change…", width=8,
            command=self._open_model_settings,
        ).pack(side="right")
        self._ms_label = ttk.Label(
            ms_frame, text="(Global Options)",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        )
        self._ms_label.pack(side="right", padx=5)

        # Translation Options — open Global Options dialog at Translation Options
        to_frame = ttk.Frame(frame)
        to_frame.pack(fill="x", pady=2)

        ttk.Label(to_frame, text="Translation Options:").pack(side="left")
        ttk.Button(
            to_frame, text="Change…", width=8,
            command=self._open_translation_options,
        ).pack(side="right")
        self._to_label = ttk.Label(
            to_frame, text="(Global Options)",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        )
        self._to_label.pack(side="right", padx=5)

        # Separator
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=5)

        # --- Hidden variables (managed by Global Options, kept for compat) ---
        self._temp_var = tk.DoubleVar(value=self._translation_options.temperature)
        self._chunk_var = tk.IntVar(value=self._translation_options.chunk_size)
        self._retry_var = tk.StringVar(
            value=self._translation_options.retry_strategy,
        )
        self._retries_var = tk.IntVar(value=self._translation_options.max_retries)
        self._cache_var = tk.BooleanVar(
            value=self._translation_options.cache_enabled,
        )
        self._edit_before_var = tk.BooleanVar(
            value=self._translation_options.edit_before_translation,
        )
        self._skip_translated_var = tk.BooleanVar(
            value=self._translation_options.skip_already_translated,
        )
        self._skip_non_source_var = tk.BooleanVar(value=False)
        self._line_by_line_var = tk.BooleanVar(
            value=self._translation_options.line_by_line,
        )
        self._context_lines_var = tk.IntVar(
            value=self._translation_options.context_lines,
        )
        self._thinking_var = tk.BooleanVar(
            value=self._translation_options.thinking_enabled,
        )
        self._thinking_budget_var = tk.IntVar(
            value=self._translation_options.thinking_budget,
        )
        self._reasoning_effort_var = tk.StringVar(
            value=self._translation_options.reasoning_effort,
        )

        # --- Character Whitelist ---
        wl_lf = ttk.LabelFrame(frame, text="Character Whitelist", padding=5)
        wl_lf.pack(fill="x", pady=(0, 5))

        wl_row = ttk.Frame(wl_lf)
        wl_row.pack(fill="x", pady=2)
        ttk.Label(wl_row, text="Chars:").pack(side="left")
        self._whitelist_var = tk.StringVar(value="")
        self._whitelist_entry = ttk.Entry(
            wl_row, textvariable=self._whitelist_var, width=30,
        )
        self._whitelist_entry.pack(side="left", padx=5, fill="x", expand=True)

        ttk.Label(
            wl_lf,
            text="Only these characters are allowed in output. Leave empty = allow all.",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(anchor="w")

        # Bind whitelist to manifest
        self._manifest_bindings.append(
            bind_entry_to_field(
                entry=self._whitelist_entry,
                var=self._whitelist_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="CharacterWhitelist",
                default="",
                parent_key="RequestOptions",
            )
        )

        # --- Character Blacklist ---
        bl_lf = ttk.LabelFrame(frame, text="Character Blacklist", padding=5)
        bl_lf.pack(fill="x", pady=(0, 5))

        bl_row = ttk.Frame(bl_lf)
        bl_row.pack(fill="x", pady=2)
        ttk.Label(bl_row, text="Chars:").pack(side="left")
        self._blacklist_var = tk.StringVar(value="")
        self._blacklist_entry = ttk.Entry(
            bl_row, textvariable=self._blacklist_var, width=30,
        )
        self._blacklist_entry.pack(side="left", padx=5, fill="x", expand=True)

        ttk.Label(
            bl_lf,
            text="These characters are stripped from output. Comma-separated.",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(anchor="w")

        # Bind blacklist to manifest
        self._manifest_bindings.append(
            bind_entry_to_field(
                entry=self._blacklist_entry,
                var=self._blacklist_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="CharacterBlacklist",
                default="",
                parent_key="RequestOptions",
            )
        )

        # --- Ban Tokens ---
        ban_lf = ttk.LabelFrame(frame, text="Ban Tokens", padding=5)
        ban_lf.pack(fill="x", pady=(0, 5))

        preset_row = ttk.Frame(ban_lf)
        preset_row.pack(fill="x", pady=2)
        ttk.Label(preset_row, text="Preset:").pack(side="left")
        self._ban_preset_var = tk.StringVar(value="None")
        ban_preset_combo = ttk.Combobox(
            preset_row,
            textvariable=self._ban_preset_var,
            values=["None", "Clean English", "Strict"],
            state="readonly",
            width=15,
        )
        ban_preset_combo.pack(side="left", padx=5)
        ban_preset_combo.bind("<<ComboboxSelected>>", self._on_ban_preset_change)

        ban_entry_row = ttk.Frame(ban_lf)
        ban_entry_row.pack(fill="x", pady=2)
        ttk.Label(ban_entry_row, text="Tokens:").pack(side="left")
        self._ban_var = tk.StringVar(value="")
        self._ban_entry = ttk.Entry(
            ban_entry_row,
            textvariable=self._ban_var,
            width=30,
        )
        self._ban_entry.pack(side="left", padx=5, fill="x", expand=True)

        ttk.Label(
            ban_lf,
            text="Comma-separated: em_dash, smart_quotes, ellipsis, etc.",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(anchor="w")

        # Bind ban tokens to manifest
        self._manifest_bindings.append(
            bind_entry_to_field(
                entry=self._ban_entry,
                var=self._ban_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="BanTokens",
                default="",
                parent_key="RequestOptions",
            )
        )

    def _build_prompt_editor(self, parent: ttk.Frame) -> None:
        """Initialize hidden compatibility variables (prompt editor removed).

        The Prompt Editor panel has been removed.  Ban Tokens are now in
        Request Options, and the Preview button is in the header bar.
        This method only sets up hidden variables required by other code.
        """
        # Hidden summary text for backward compat (loaded by _load_prompt_data)
        self._summary_text = scrolledtext.ScrolledText(
            parent, height=0, wrap="word",
        )
        # Don't pack — kept only as data holder

        # Removed fields — set None for compatibility
        self._style_var = tk.StringVar(value="")
        self._style_entry = None
        self._glossary_text = None
        self._conditional_text = None

    # Ban-token presets (Task 43.11)
    _BAN_PRESETS: dict[str, str] = {
        "None": "",
        "Clean English": "em_dash, smart_quotes",
        "Strict": "em_dash, smart_quotes, ellipsis, en_dash, curly_apostrophe",
    }

    def _on_ban_preset_change(self, _event: object = None) -> None:
        """Apply selected ban-token preset."""
        preset = self._ban_preset_var.get()
        tokens = self._BAN_PRESETS.get(preset, "")
        self._ban_var.set(tokens)

    def _build_api_usage_panel(self) -> None:
        """Build the API usage panel at the bottom."""
        frame = ttk.LabelFrame(self, text="API Usage", padding=5)
        frame.pack(fill="x", padx=10, pady=5)

        usage_grid = ttk.Frame(frame)
        usage_grid.pack(fill="x")

        # Tokens used
        ttk.Label(usage_grid, text="Tokens Used:").grid(row=0, column=0, sticky="w")
        self._usage_tokens_label = ttk.Label(usage_grid, text="0")
        self._usage_tokens_label.grid(row=0, column=1, sticky="w", padx=(10, 30))

        # Cost estimate
        ttk.Label(usage_grid, text="Est. Cost:").grid(row=0, column=2, sticky="w")
        self._usage_cost_label = ttk.Label(usage_grid, text="$0.00")
        self._usage_cost_label.grid(row=0, column=3, sticky="w", padx=(10, 30))

        # Rate limit
        ttk.Label(usage_grid, text="Rate Limit:").grid(row=0, column=4, sticky="w")
        self._usage_rate_label = ttk.Label(usage_grid, text="0 / 60 RPM")
        self._usage_rate_label.grid(row=0, column=5, sticky="w", padx=(10, 0))

    def _get_lines_from_previous_steps(self) -> Tuple[List[str], List[str]]:
        """Get original and preprocessed lines from manifest.

        Uses manifest ``orig`` for originals and ``prepro`` chain
        (prepro → orig fallback) for the preprocessed column.

        Returns:
            Tuple of (original_lines, preprocessed_lines).
        """
        original: List[str] = []
        preprocessed: List[str] = []

        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            manifest_lines = mgr.get_lines()
            if manifest_lines:
                original = [ln.get("orig", "") for ln in manifest_lines]
                preprocessed = get_all_lines_resolved(mgr, "prepro")

        # Fallback: GUI input step
        if not original:
            try:
                app = self.winfo_toplevel()
                if hasattr(app, "_step_tabs") and len(app._step_tabs) > 0:
                    input_step = app._step_tabs[0]
                    if hasattr(input_step, "get_loaded_files"):
                        loaded_files = input_step.get_loaded_files()
                        for lf in loaded_files:
                            if hasattr(lf, "lines"):
                                original.extend(lf.lines)
            except Exception as e:
                logger.debug("Error getting lines: %s", e)

        # Final fallback: legacy session step data
        if not original:
            input_data = self.session.get_step(0).data
            if "all_lines" in input_data:
                original = input_data["all_lines"]

        # Fallback preprocessed to original
        if not preprocessed and original:
            preprocessed = original[:]

        return original, preprocessed

    def _refresh_lines(self) -> None:
        """Refresh lines from previous steps.

        Reads ``edited_prepro`` and existing ``tl`` translations from
        the manifest so that re-entering the tab shows prior work.
        """
        original, preprocessed = self._get_lines_from_previous_steps()

        if not original:
            self._status_label.configure(text="No lines loaded")
            return

        # Batch-read edited_prepro and existing tl from manifest
        edit_map: dict[int, str] = {}
        tl_map: dict[int, str] = {}
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            # edited_prepro from Lines section
            lines_section = mgr._manifest_data.get("Lines", {})
            for idx_str, line_data in lines_section.items():
                if isinstance(line_data, dict):
                    ep = line_data.get("edited_prepro", "")
                    if ep:
                        try:
                            edit_map[int(idx_str)] = ep
                        except (ValueError, TypeError):
                            pass

            # tl from lines[] array
            for ln in mgr.get_lines():
                idx = ln.get("idx")
                tl_val = ln.get("tl", "")
                if idx is not None and tl_val:
                    tl_map[idx] = tl_val

        # Create TranslatableLine objects
        self._lines = []
        for idx, (orig, prep) in enumerate(zip(original, preprocessed)):
            tl_text = tl_map.get(idx, "")
            line = TranslatableLine(
                idx=idx,
                original=orig,
                preprocessed=prep,
                edited_prepro=edit_map.get(idx, ""),
                translated=tl_text,
                status=LineStatus.COMPLETED if tl_text else LineStatus.PENDING,
            )
            self._lines.append(line)

        # Update table
        self._update_lines_table()

        # Update status
        completed = sum(1 for l in self._lines if l.status == LineStatus.COMPLETED)
        total = len(self._lines)
        if completed > 0:
            self._status_label.configure(
                text=f"{total} lines ready ({completed} translated)",
            )
        else:
            self._status_label.configure(text=f"{total} lines ready")

    def _update_lines_table(self) -> None:
        """Update the lines table with current data.

        TASK 43.3: Uses merged "To be Translated" column showing
        edited_prepro → preprocessed → original (first available).
        TASK 43.4: Renders newlines as ↵ symbol for visible line breaks.
        """
        rows: List[TableRow] = []

        for line in self._lines:
            # Status display with icon
            status_display = {
                LineStatus.PENDING: "○ Pending",
                LineStatus.TRANSLATING: "◐ Translating",
                LineStatus.COMPLETED: "✓ Done",
                LineStatus.FAILED: "✗ Failed",
                LineStatus.SKIPPED: "⊘ Skipped",
                LineStatus.NEEDS_REVIEW: "⚠ Review",
            }.get(line.status, "?")

            # TASK 43.3: Merge column resolution order
            to_translate = line.edited_prepro or line.preprocessed or line.original
            # TASK 43.4: Render newlines as ↵ symbol
            to_translate_display = to_translate.replace("\n", "↵")
            translated_display = line.translated.replace("\n", "↵")
            # Truncate for display
            max_len = 200
            if len(to_translate_display) > max_len:
                to_translate_display = to_translate_display[:max_len] + "..."
            if len(translated_display) > max_len:
                translated_display = translated_display[:max_len] + "..."

            row = TableRow(
                id=line.idx,
                values={
                    "idx": str(line.idx + 1),
                    "status": status_display,
                    "to_translate": to_translate_display,
                    "translated": translated_display,
                },
            )
            rows.append(row)

        self._lines_table.set_data(rows)

    def _get_options_from_ui(self) -> TranslationOptions:
        """Get current options from UI controls.

        Returns:
            TranslationOptions with current values.
        """
        key_provider, key_name = self._parse_key_selection()
        return TranslationOptions(
            api_key_provider=key_provider,
            api_key_name=key_name,
            model=self._model_var.get(),
            temperature=self._temp_var.get(),
            chunk_size=self._chunk_var.get(),
            retry_strategy=self._retry_var.get(),
            max_retries=self._retries_var.get(),
            cache_enabled=self._cache_var.get(),
            style_preset=self._style_var.get(),
            banned_tokens=self._ban_var.get(),
            line_by_line=self._line_by_line_var.get(),
            context_lines=self._context_lines_var.get(),
            thinking_enabled=self._thinking_var.get(),
            thinking_budget=self._thinking_budget_var.get(),
            reasoning_effort=self._reasoning_effort_var.get(),
            edit_before_translation=self._edit_before_var.get(),
            skip_already_translated=self._skip_translated_var.get(),
            request_slicing=self._get_request_slicing_mode(),
        )

    def _get_request_slicing_mode(self) -> str:
        """Return current request slicing mode from Global Options.

        Returns:
            ``"conservative"`` or ``"efficient"``.
        """
        go = getattr(self.session, "global_options", None)
        if go is not None and hasattr(go, "translation"):
            return getattr(go.translation, "request_slicing", "conservative")
        return "conservative"

    def _get_prompt_parts(self) -> Dict[str, str]:
        """Get prompt parts from UI.

        Returns:
            Dict with summary, glossary, conditional prompts.
            
        Note: Glossary and conditional prompts are now managed externally.
        This method returns empty strings for backward compatibility.
        """
        glossary = ""
        if self._glossary_text is not None:
            glossary = self._glossary_text.get("1.0", "end-1c").strip()
        
        conditional = ""
        if self._conditional_text is not None:
            conditional = self._conditional_text.get("1.0", "end-1c").strip()
        
        return {
            "summary": self._summary_text.get("1.0", "end-1c").strip(),
            "glossary": glossary,
            "conditional": conditional,
        }

    def _build_system_prompt_from_manifest(
        self,
        rolling_context_text: str = "",
        chunk_lines: Optional[List[str]] = None,
        merge_instruction: str = "",
        context_type: str = "",
    ) -> str:
        """Build the system prompt from manifest Information step metadata.

        Uses ``gather_prompt_data()`` and ``build_request_prompt()``
        from prompt_adapter.py — the single source of truth for both
        data gathering and §5.2 injection order.  All features
        (Estimation, Request Preview, Start Translation) share the
        same code path so the resulting prompts are identical.

        Args:
            rolling_context_text: Pre-formatted rolling context lines to
                include in the prompt. Empty string disables.
            chunk_lines: When provided, enables per-chunk selective
                filtering of glossary, characters, and conditional
                prompts (only terms present in these lines are included).
            merge_instruction: Optional instruction describing block
                relatedness for merged requests (Step 5).
            context_type: Resolved content type for this chunk/request.

        Returns:
            Assembled system prompt string.
        """
        from CherryAI.gui.helpers.prompt_adapter import (
            gather_prompt_data,
            build_request_prompt,
        )

        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            # Gather all prompt data from manifest (shared with costs
            # and request preview to guarantee identical prompts).
            sample_lines = [
                (line.edited_prepro or line.preprocessed or line.original)
                for line in self._lines[:200]
            ]
            prompt_data = gather_prompt_data(mgr, sample_lines=sample_lines)

            prompt_text, _ = build_request_prompt(
                prompt_data,
                chunk_lines=chunk_lines,
                rolling_context_text=rolling_context_text,
                code_patterns=prompt_data.get("code_patterns"),
                merge_instruction=merge_instruction,
                context_type=context_type,
            )

            if prompt_text:
                return prompt_text

        # Fallback to legacy prompt parts if manifest is not available
        parts: list[str] = []
        prompt_parts = self._get_prompt_parts()
        if prompt_parts["summary"]:
            parts.append(
                f"Game Context:\n{prompt_parts['summary']}"
            )
        if prompt_parts["glossary"]:
            parts.append(
                f"Glossary:\n{prompt_parts['glossary']}"
            )
        if prompt_parts["conditional"]:
            parts.append(
                f"Special Instructions:\n{prompt_parts['conditional']}"
            )
        return "\n\n".join(parts)

    def _start_translation(self) -> None:
        """Start the translation process."""
        if self._translation_state == TranslationState.RUNNING:
            messagebox.showwarning("Translation", "Translation already in progress.")
            return

        if not self._lines:
            self._refresh_lines()

        if not self._lines:
            messagebox.showwarning("No Data", "Please load files in the Input step first.")
            return

        # Get options
        self._translation_options = self._get_options_from_ui()

        # Check for pending lines
        pending_lines = [l for l in self._lines if l.status == LineStatus.PENDING]
        if not pending_lines:
            if messagebox.askyesno(
                "No Pending Lines",
                "All lines have been processed. Restart translation for failed lines?",
            ):
                # Reset failed lines to pending
                for line in self._lines:
                    if line.status == LineStatus.FAILED:
                        line.status = LineStatus.PENDING
                        line.error_message = ""
                pending_lines = [l for l in self._lines if l.status == LineStatus.PENDING]
            else:
                return

        if not pending_lines:
            messagebox.showinfo("Translation", "No lines to translate.")
            return

        # Task 33.1: Show edit dialog if enabled
        if self._translation_options.edit_before_translation:
            if not self._show_edit_dialog(pending_lines):
                return  # User cancelled edit dialog

        # Mark dedup/placeholder-only lines as SKIPPED before translation
        # so they don't inflate total_lines and prevent 100% progress.
        from CherryAI.functions.prompt_builder import is_placeholder_only
        skipped_before_start = 0
        translatable_lines: list[TranslatableLine] = []
        for line in pending_lines:
            text = (
                line.edited_prepro or line.preprocessed or line.original
            )
            if not text.strip() or is_placeholder_only(text):
                line.status = LineStatus.SKIPPED
                skipped_before_start += 1
            else:
                translatable_lines.append(line)

        # Initialize progress
        self._progress = TranslationProgress(
            total_lines=len(pending_lines),
            translated_lines=0,
            failed_lines=0,
            skipped_lines=skipped_before_start,
            total_chunks=math.ceil(
                len(translatable_lines) / self._translation_options.chunk_size
            ) if translatable_lines else 0,
            start_time=time.time(),
        )

        # Reset state
        self._cancel_requested = False
        self._pause_requested = False
        self._translation_state = TranslationState.RUNNING
        self._abort_error: TranslationAbortError | None = None

        # Show progress window
        self._progress_window = TranslationProgressWindow(
            self,
            on_pause=self._on_pause,
            on_resume=self._on_resume,
            on_cancel=self._on_cancel,
        )

        # Disable start button
        self._translate_btn.configure(state="disabled")

        # TASK 29.2: Save manifest before starting translation
        self._save_manifest_before_translation()

        # Start translation thread
        self._translation_thread = threading.Thread(
            target=self._do_translation,
            daemon=True,
        )
        self._translation_thread.start()

    def _show_edit_dialog(self, pending_lines: List[TranslatableLine]) -> bool:
        """Show edit dialog for preprocessed text (Task 33.1).
        
        Args:
            pending_lines: Lines to edit before translation.
            
        Returns:
            True if user applied changes or dialog was closed normally,
            False if user cancelled.
        """
        dialog = EditPreviewDialog(self, pending_lines)
        self.wait_window(dialog)
        
        if dialog.result == EditPreviewDialog.RESULT_CANCEL:
            return False
        
        # Apply edited data to lines and manifest
        for idx, edited_text in dialog.edited_data.items():
            # Update TranslatableLine
            for line in self._lines:
                if line.idx == idx:
                    line.edited_prepro = edited_text if edited_text else ""
                    break
            
            # Update manifest
            self._save_edited_prepro_to_manifest(idx, edited_text)
        
        # Update table to show edited indicator
        self._update_lines_table()
        
        return True

    def _save_edited_prepro_to_manifest(self, idx: int, edited_text: str) -> None:
        """Save edited_prepro to manifest (Task 33.1).
        
        Args:
            idx: Line index.
            edited_text: Edited preprocessed text (empty string to clear).
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            if edited_text:
                mgr.set_line_field(idx, "edited_prepro", edited_text)
            else:
                # Clear the field by setting to None
                line = mgr.get_line(idx)
                if line and "edited_prepro" in line:
                    del line["edited_prepro"]
                    mgr._mark_dirty()

    def _save_manifest_before_translation(self) -> None:
        """Save manifest before starting translation (TASK 29.2).
        
        Ensures current state is persisted before potentially long-running
        translation operation to prevent data loss.
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            try:
                if mgr.save():
                    logger.debug("Manifest saved before translation start")
            except Exception as e:
                logger.warning("Failed to save manifest before translation: %s", e)

    def _do_translation(self) -> None:
        """Perform translation in background thread."""
        try:
            self._log_progress("Starting translation...")

            # TASK 43.5: Check for Mock Translation before API setup
            is_mock = self._translation_options.model in (
                "Mock Translation", "mock",
            )

            if is_mock:
                from CherryAI.functions.mock_translator import MockTranslator
                self._mock_translator = MockTranslator(delay_per_chunk=0.1)
                self._api_client = None
                self._log_progress("Using Mock Translation (no API required)")
            else:
                self._mock_translator = None
                # Try to import and initialize API client
                try:
                    from CherryAI.functions.api_client import (
                        APIClient, APIConfig, TranslationError,
                    )
                    from CherryAI.functions.api_config import (
                        get_api_key_plain, PROVIDER_BASE_URLS,
                    )

                    # Resolve the API key from the user's selection
                    key_provider = self._translation_options.api_key_provider
                    key_name = self._translation_options.api_key_name
                    resolved_key = ""
                    if key_provider and key_name:
                        resolved_key = get_api_key_plain(
                            key_provider, key_name,
                        ) or ""

                    # Local providers (lmstudio, local, ollama) don't need
                    # a real API key — use a placeholder if none is set.
                    _LOCAL_PROVIDERS = ("local", "lmstudio", "ollama")
                    is_local = key_provider.lower() in _LOCAL_PROVIDERS

                    if not resolved_key and not is_local:
                        self._log_progress(
                            "No API key selected — please choose a key "
                            "in the Request Options panel."
                        )
                        self._api_client = None
                    else:
                        self._api_client = APIClient(enable_api_log=True)

                        # Inject the resolved key, provider, and base URL
                        self._api_client.config.api_key = (
                            resolved_key or "lm-studio"
                        )
                        self._api_client.config.provider = key_provider
                        if is_local:
                            self._api_client.config.no_api_key = True
                        base_url = PROVIDER_BASE_URLS.get(
                            key_provider, "",
                        )
                        if base_url:
                            self._api_client.config.base_url = base_url

                        # Reinitialize the OpenAI client with the real key
                        self._api_client._init_client()

                        # Apply per-request options
                        self._api_client.config.model = (
                            self._translation_options.model
                        )
                        self._api_client.config.temperature = (
                            self._translation_options.temperature
                        )
                        self._api_client.config.chunk_size = (
                            self._translation_options.chunk_size
                        )
                        self._api_client.config.retries = (
                            self._translation_options.max_retries
                        )
                        self._api_client.config.cache_enabled = (
                            self._translation_options.cache_enabled
                        )

                        # Apply request mode (normal/batch/flex/priority)
                        mode_display = self._request_mode_var.get()
                        mode_key = mode_display.lower().split()[0]
                        self._api_client.config.request_mode = mode_key
                        if mode_key == "batch":
                            self._api_client.config.batch_mode = True

                        # Set source/target language from Information metadata
                        info_mgr = self.manifest_manager
                        if info_mgr is not None and info_mgr.is_loaded:
                            info_meta = info_mgr.get_step_data_value(
                                2, "metadata", {},
                            )
                            if isinstance(info_meta, dict):
                                sl = info_meta.get("source_language", "")
                                tl = info_meta.get("target_language", "")
                                if sl:
                                    self._api_client.config.source_lang = sl
                                if tl:
                                    self._api_client.config.target_lang = tl

                        if self._translation_options.banned_tokens:
                            self._api_client.configure_logit_bias(
                                enabled=True,
                                banned_tokens=self._translation_options.banned_tokens,
                            )

                        # Parser Handshake O7: Merge parser forbidden chars
                        try:
                            info_mgr_o7 = self.manifest_manager
                            if info_mgr_o7 is not None and info_mgr_o7.is_loaded:
                                opts = info_mgr_o7._manifest_data.get(
                                    "Options", {},
                                )
                                if isinstance(opts, dict):
                                    pname = opts.get("ParserName", "")
                                    if pname:
                                        self._api_client.apply_parser_forbidden_chars(
                                            pname,
                                        )
                        except Exception:
                            pass

                        self._log_progress(
                            f"API client initialized: {key_provider} "
                            f"({self._translation_options.model})"
                        )

                except ImportError as e:
                    self._log_progress(f"API client not available: {e}")
                    self._log_progress("Running in simulation mode (no actual translation)")
                    self._api_client = None

            # Get pending lines
            pending_lines = [l for l in self._lines if l.status == LineStatus.PENDING]

            # Task 47.9: Skip lines that already have a base translation
            if self._skip_translated_var.get() and self._manifest_manager:
                skipped_count = 0
                still_pending = []
                for line in pending_lines:
                    manifest_line = self._manifest_manager.get_line(line.idx)
                    tl_val = manifest_line.get("tl", "") if manifest_line else ""
                    if tl_val and str(tl_val).strip():
                        line.status = LineStatus.SKIPPED
                        self._progress.skipped_lines += 1
                        skipped_count += 1
                    else:
                        still_pending.append(line)
                pending_lines = still_pending
                if skipped_count:
                    self._log_progress(
                        f"Skipped {skipped_count} already translated lines"
                    )

            # TASK 43.13: Skip lines not in source language
            if self._skip_non_source_var.get():
                pending_lines = self._apply_language_skip(pending_lines)

            # Build chunks
            chunks = self._build_chunks(pending_lines)
            self._progress.total_chunks = len(chunks)

            self._log_progress(f"Processing {len(pending_lines)} lines in {len(chunks)} chunks")

            # Rolling context state
            go = getattr(self.session, "global_options", None)
            try:
                rolling_ctx_max = int(
                    go.request.rolling_context_lines,
                ) if go else 3
            except (TypeError, ValueError, AttributeError):
                rolling_ctx_max = 3

            try:
                rolling_ctx_between = int(
                    go.request.rolling_context_between,
                ) if go else 0
            except (TypeError, ValueError, AttributeError):
                rolling_ctx_between = 0

            try:
                rolling_ctx_after = int(
                    go.request.rolling_context_after,
                ) if go else 0
            except (TypeError, ValueError, AttributeError):
                rolling_ctx_after = 0

            use_translated_ctx = True
            try:
                use_translated_ctx = bool(
                    go.request.use_translated_context,
                ) if go else True
            except (TypeError, ValueError, AttributeError):
                use_translated_ctx = True

            rolling_ctx_buffer: list[str] = []

            # ================================================================
            # First-Request Validation Gate
            # ================================================================
            # Send the very first chunk alone before committing to the full
            # translation run. If the API returns a fatal error (auth,
            # model not found, non-structured output, etc.) translation
            # stops immediately with a user-facing message.  This avoids
            # wasting time / tokens on a clearly broken configuration.
            # ================================================================
            first_request_validated = False

            # ================================================================
            # Concurrent Execution Engine
            # ================================================================
            # Group chunks into request strings (rolling-context chains).
            # Strings execute in parallel; chunks within a string execute
            # sequentially to maintain rolling context ordering.
            # ================================================================
            request_strings = self._group_chunks_into_strings(chunks)

            # Flatten all chunks for index-based lookup and assign chunk_ids
            all_chunks_flat = []
            for string_group in request_strings:
                all_chunks_flat.extend(string_group)
            chunk_id_map: dict[int, int] = {}
            for flat_idx, chunk in enumerate(all_chunks_flat):
                for line in chunk:
                    chunk_id_map[line.idx] = flat_idx

            max_concurrent = 1  # Default: sequential
            if self._api_client and hasattr(self._api_client, "config"):
                max_concurrent = max(1, self._api_client.config.max_concurrent)

            self._log_progress(
                f"Execution plan: {len(request_strings)} strings, "
                f"max {max_concurrent} concurrent"
            )

            # Thread-safe progress lock
            progress_lock = threading.Lock()

            # ----------------------------------------------------------------
            # Validation gate: execute the first chunk of the first string
            # alone before starting concurrent execution.
            # ----------------------------------------------------------------
            if request_strings and request_strings[0]:
                gate_chunk = request_strings[0][0]
                gate_result = self._process_single_chunk(
                    chunk=gate_chunk,
                    chunk_idx=0,
                    total_chunks=len(chunks),
                    rolling_ctx_buffer=rolling_ctx_buffer,
                    rolling_ctx_max=rolling_ctx_max,
                    rolling_ctx_between=rolling_ctx_between,
                    rolling_ctx_after=rolling_ctx_after,
                    use_translated_ctx=use_translated_ctx,
                    all_chunks=chunks,
                    progress_lock=progress_lock,
                )
                if gate_result == "abort":
                    # _abort_error was set by _process_single_chunk
                    if not hasattr(self, "_abort_error") or self._abort_error is None:
                        # Shouldn't happen, but guard
                        pass
                    else:
                        self._log_progress(
                            "First-request validation FAILED — aborting."
                        )
                elif gate_result == "cancel":
                    pass  # Will be handled below
                else:
                    first_request_validated = True
                    self._log_progress(
                        "First request validated — API configuration OK"
                    )

            # ----------------------------------------------------------------
            # If validation failed or was cancelled, skip remaining work.
            # ----------------------------------------------------------------
            if (
                not first_request_validated
                and not self._cancel_requested
                and request_strings
            ):
                # Abort — don't process remaining strings
                pass
            elif not self._cancel_requested and first_request_validated:
                # ============================================================
                # Execute remaining work concurrently
                # ============================================================
                # Build work items: each is (string_index, chunk_list)
                # For the first string, skip the first chunk (already done).
                work_items: list[tuple[int, list[list[TranslatableLine]]]] = []
                for s_idx, string_group in enumerate(request_strings):
                    if s_idx == 0:
                        remaining = string_group[1:]  # Skip validated chunk
                        if remaining:
                            work_items.append((s_idx, remaining))
                    else:
                        work_items.append((s_idx, string_group))

                if max_concurrent <= 1 or len(work_items) <= 1:
                    # Sequential execution
                    for s_idx, string_chunks in work_items:
                        if self._cancel_requested:
                            break
                        if hasattr(self, "_abort_error") and self._abort_error is not None:
                            break
                        local_buffer = (
                            list(rolling_ctx_buffer) if s_idx == 0 else []
                        )
                        self._execute_string_sequential(
                            string_chunks=string_chunks,
                            rolling_ctx_buffer=local_buffer,
                            rolling_ctx_max=rolling_ctx_max,
                            rolling_ctx_between=rolling_ctx_between,
                            rolling_ctx_after=rolling_ctx_after,
                            use_translated_ctx=use_translated_ctx,
                            all_chunks=chunks,
                            progress_lock=progress_lock,
                        )
                else:
                    # Concurrent execution via ThreadPoolExecutor
                    with ThreadPoolExecutor(
                        max_workers=min(max_concurrent, len(work_items)),
                    ) as executor:
                        futures: dict[Future, int] = {}
                        for s_idx, string_chunks in work_items:
                            local_buffer = (
                                list(rolling_ctx_buffer) if s_idx == 0 else []
                            )
                            future = executor.submit(
                                self._execute_string_sequential,
                                string_chunks=string_chunks,
                                rolling_ctx_buffer=local_buffer,
                                rolling_ctx_max=rolling_ctx_max,
                                rolling_ctx_between=rolling_ctx_between,
                                rolling_ctx_after=rolling_ctx_after,
                                use_translated_ctx=use_translated_ctx,
                                all_chunks=chunks,
                                progress_lock=progress_lock,
                            )
                            futures[future] = s_idx

                        # Wait for all strings to complete
                        for future in as_completed(futures):
                            try:
                                future.result()
                            except TranslationAbortError as abort_err:
                                self._abort_error = abort_err
                                self._log_progress(
                                    f"ABORT: {abort_err.user_message}"
                                )
                                # Cancel remaining futures
                                self._cancel_requested = True
                                break
                            except Exception as exc:
                                logger.exception(
                                    "String %d failed: %s",
                                    futures[future], exc,
                                )

            # Translation complete
            if self._cancel_requested:
                self._translation_state = TranslationState.CANCELLED
            elif hasattr(self, "_abort_error") and self._abort_error is not None:
                self._translation_state = TranslationState.FAILED
                self._log_progress("Translation aborted due to API error.")
            elif self._progress.failed_lines > 0:
                self._translation_state = TranslationState.COMPLETED
                self._log_progress(f"Translation completed with {self._progress.failed_lines} failures")
            else:
                self._translation_state = TranslationState.COMPLETED
                self._log_progress("Translation completed successfully!")

            self.after(0, self._on_translation_complete)

        except TranslationAbortError as abort_err:
            # Fatal API error caught at top level (e.g. during first-request)
            self._abort_error = abort_err
            self._log_progress(f"ABORT: {abort_err.user_message}")
            self._translation_state = TranslationState.FAILED
            self.after(0, self._on_translation_complete)

        except Exception as e:
            logger.exception("Translation error: %s", e)
            self._log_progress(f"Translation failed: {e}")
            self._translation_state = TranslationState.FAILED
            self.after(0, self._on_translation_complete)

    # Language → expected script mapping for Task 43.13
    _LANG_SCRIPT_MAP: dict[str, str] = {
        "Japanese": "japanese",
        "Chinese (Simplified)": "chinese",
        "Chinese (Traditional)": "chinese",
        "Korean": "korean",
        "English": "latin",
        "French": "latin",
        "German": "latin",
        "Spanish": "latin",
        "Portuguese": "latin",
        "Italian": "latin",
        "Russian": "latin",  # Cyrillic would need extension
        "Polish": "latin",
        "Dutch": "latin",
        "Turkish": "latin",
        "Vietnamese": "latin",
    }

    def _apply_language_skip(
        self, lines: list[TranslatableLine],
    ) -> list[TranslatableLine]:
        """Skip lines not matching the source language script (Task 43.13).

        Lines shorter than 3 non-whitespace characters are never skipped.

        Placeholder tokens (``__PROTECTED__``, ``__COLOR__``, etc.) are
        stripped before detection because the token *names* are Latin
        letters that would skew ratio-based script classification.  After
        stripping, the remaining text represents the actual language
        content: if CJK characters remain the line is kept for
        translation; if only non-source text remains it is skipped.

        Args:
            lines: Pending lines to filter.

        Returns:
            Lines that should still be translated.
        """
        from CherryAI.functions.analysis import detect_line_script
        from CherryAI.functions.prompt_builder import _PLACEHOLDER_TOKEN_RE

        # Determine expected source script from manifest
        source_lang = "Japanese"
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            source_lang = mgr.get_info_metadata_field(
                "source_language", "Japanese",
            )

        expected_script = self._LANG_SCRIPT_MAP.get(source_lang)
        if expected_script is None:
            # Unknown language — can't filter, return all
            return lines

        kept: list[TranslatableLine] = []
        skipped = 0
        for line in lines:
            # Use the prioritized text (what actually gets sent to the LLM)
            # for language detection. After preprocessing, CJK may be replaced
            # by __PROTECTED__ — if only non-source text remains, skip it.
            text = line.edited_prepro or line.preprocessed or line.original
            # Strip placeholder tokens before detection: their character
            # names (PROTECTED, COLOR, …) are Latin letters that skew the
            # ratio-based script classifier.
            clean = _PLACEHOLDER_TOKEN_RE.sub("", text).strip()
            if not clean:
                # Line is all placeholders — keep here; caught by
                # is_placeholder_only() in _build_chunks() later.
                kept.append(line)
                continue
            script = detect_line_script(clean)
            if script == "unknown" or script == "mixed" or script == expected_script:
                kept.append(line)
            else:
                line.status = LineStatus.SKIPPED
                line.translated = ""
                skipped += 1

        if skipped:
            self._log_progress(
                f"Skipped {skipped} lines (not {source_lang})"
            )

        return kept

    def _collect_between_context(
        self,
        chunk: List[TranslatableLine],
        max_between: int,
        use_translated: bool,
    ) -> List[str]:
        """Collect skipped/already-translated lines interspersed within a chunk.

        "Between" context gathers lines that appear *between* the chunk's
        first and last manifest index but were skipped (already translated
        or non-source language).  These give the LLM visibility into gaps.

        Args:
            chunk: The current chunk being translated.
            max_between: Maximum number of between-context lines to include.
            use_translated: Prefer ``tl`` over ``orig`` when available.

        Returns:
            List of context line strings (may be empty).
        """
        if max_between <= 0 or not chunk:
            return []

        mgr = self._manifest_manager
        if mgr is None or not mgr.is_loaded:
            return []

        first_idx = chunk[0].idx
        last_idx = chunk[-1].idx
        chunk_indices = {line.idx for line in chunk}

        between: list[str] = []
        for idx in range(first_idx, last_idx + 1):
            if idx in chunk_indices:
                continue
            entry = mgr.get_line(idx)
            if entry is None:
                continue
            text = ""
            if use_translated:
                text = (entry.get("tl", "") or "").strip()
            if not text:
                text = (
                    entry.get("prepro", "") or entry.get("orig", "") or ""
                ).strip()
            if text:
                between.append(text)
            if len(between) >= max_between:
                break

        return between

    def _collect_after_context(
        self,
        chunk: List[TranslatableLine],
        all_chunks: List[List[TranslatableLine]],
        chunk_idx: int,
        max_after: int,
        use_translated: bool,
    ) -> List[str]:
        """Collect already-translated lines that follow this chunk.

        "After" context provides forward-looking context from lines that
        have already been translated (useful for re-translation / update
        scenarios).  Only lines with existing translations are included.

        Args:
            chunk: The current chunk.
            all_chunks: All chunks in the translation run.
            chunk_idx: Index of the current chunk.
            max_after: Maximum number of after-context lines.
            use_translated: Prefer ``tl`` over ``orig`` when available.

        Returns:
            List of context line strings (may be empty).
        """
        if max_after <= 0 or not chunk:
            return []

        mgr = self._manifest_manager
        if mgr is None or not mgr.is_loaded:
            return []

        last_idx = chunk[-1].idx
        after: list[str] = []

        # Scan manifest lines after the chunk's last index
        idx = last_idx + 1
        while len(after) < max_after:
            entry = mgr.get_line(idx)
            if entry is None:
                break
            text = ""
            if use_translated:
                text = (entry.get("tl", "") or "").strip()
            if not text:
                text = (
                    entry.get("prepro", "") or entry.get("orig", "") or ""
                ).strip()
            if text:
                after.append(text)
            idx += 1

        return after

    def _build_chunks(self, lines: List[TranslatableLine]) -> List[List[TranslatableLine]]:
        """Build translation chunks using the 4-step formation pipeline.

        Uses :func:`build_requests` from ``prompt_builder.py`` which
        implements:
            Rule 1 — Split at file boundaries (``first_idx``/``last_idx``).
            Rule 2 — Balance sub-groups to avoid single-line requests.
            Rule 3 — Tag rolling context eligibility per request.
            Rule 4 — Merge short requests within file boundaries.

        Falls back to simple fixed-size chunking when the pipeline is
        not available or the manifest has no filedir data.

        Args:
            lines: Lines to chunk.

        Returns:
            List of chunks (each chunk is a list of TranslatableLine).
        """
        chunk_size = self._translation_options.chunk_size
        slicing = getattr(self._translation_options, "request_slicing", "conservative")

        try:
            from CherryAI.functions.prompt_builder import (
                LineInfo, RequestFormationConfig, build_requests,
                is_placeholder_only,
            )

            # Build LineInfo objects from TranslatableLine objects
            idx_to_line: dict[int, TranslatableLine] = {
                line.idx: line for line in lines
            }
            line_infos: list[LineInfo] = []
            for line in lines:
                text = (
                    line.edited_prepro or line.preprocessed or line.original
                )
                is_invalid = (
                    not text.strip()
                    or is_placeholder_only(text)
                )
                line_infos.append(LineInfo(
                    index=line.idx,
                    text=text,
                    is_invalid=is_invalid,
                ))

            # Inject file-end markers from manifest filedir
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                try:
                    filedir = mgr.get_filedir()
                    for entry in filedir:
                        # Insert file_end marker after each file's last_idx
                        last = entry.last_idx
                        line_infos.append(LineInfo(
                            index=last + 1,
                            text="",
                            is_invalid=True,
                            tag="file_end",
                        ))
                except Exception:
                    pass

            # Sort by index (file_end markers slot between files)
            line_infos.sort(key=lambda li: li.index)

            # Conservative: small min_lines → more granular requests
            # Efficient: higher min_lines → fewer, larger requests
            if slicing == "efficient":
                min_lines = max(5, chunk_size // 2)
            else:
                min_lines = max(2, chunk_size // 5)

            # Fetch rolling-context settings for Step 5 merge blocking
            rc_between = 0
            rc_after = 0
            go = getattr(self.session, "global_options", None)
            if go is not None:
                try:
                    rc_between = int(go.request.rolling_context_between)
                except (TypeError, ValueError, AttributeError):
                    pass
                try:
                    rc_after = int(go.request.rolling_context_after)
                except (TypeError, ValueError, AttributeError):
                    pass

            # Fetch max_input_tokens setting for token-based splitting
            max_input_tokens = 0
            if go is not None:
                try:
                    max_input_tokens = int(go.request.max_input_tokens)
                except (TypeError, ValueError, AttributeError):
                    pass

            config = RequestFormationConfig(
                max_lines=chunk_size,
                min_lines=min_lines,
                max_tokens=max_input_tokens,
                efficient_merge=(slicing == "efficient"),
                rolling_context_between=rc_between,
                rolling_context_after=rc_after,
            )
            formation_requests = build_requests(line_infos, config)

            # Convert back to List[List[TranslatableLine]]
            chunks: list[list[TranslatableLine]] = []
            for req in formation_requests:
                chunk_lines = [
                    idx_to_line[idx]
                    for idx in req.line_indices
                    if idx in idx_to_line
                ]
                if chunk_lines:
                    # Store formation metadata on the first line
                    chunk_lines[0]._formation_ctx = {
                        "receives_context": req.receives_context,
                        "provides_context": req.provides_context,
                        "context_type": req.context_type,
                        "merge_boundaries": req._merge_boundaries,
                    }
                    chunks.append(chunk_lines)

            if chunks:
                return chunks

        except ImportError:
            logger.debug("prompt_builder not available, using simple chunking")
        except Exception:
            logger.debug("Formation pipeline failed, using simple chunking",
                         exc_info=True)

        # Fallback: simple fixed-size chunking
        chunks = []
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i:i + chunk_size]
            chunks.append(chunk)
        return chunks

    # ------------------------------------------------------------------
    # Concurrent Execution Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _group_chunks_into_strings(
        chunks: List[List["TranslatableLine"]],
    ) -> List[List[List["TranslatableLine"]]]:
        """Group chunks into request strings using formation metadata.

        A "string" is a consecutive run of chunks linked by rolling
        context (``receives_context=True``).  When a chunk does not
        receive context, it starts a new string.

        Each string contains an ordered list of chunks that **must**
        execute sequentially, but independent strings can run in
        parallel.

        After grouping, strings are sorted by type priority using
        :func:`sort_requests_by_type` from ``prompt_builder``.

        Args:
            chunks: Chunks from :meth:`_build_chunks`.

        Returns:
            Sorted list of string groups (each a list of chunks).
        """
        if not chunks:
            return []

        # Try using the full formation-based sorting
        try:
            from CherryAI.functions.prompt_builder import (
                TranslationRequest, sort_requests_by_type,
            )

            # Reconstruct TranslationRequest objects from chunk metadata
            chunk_to_req: Dict[int, TranslationRequest] = {}
            requests: List[TranslationRequest] = []
            for i, chunk in enumerate(chunks):
                ctx = getattr(chunk[0], "_formation_ctx", None) if chunk else None
                req = TranslationRequest(
                    lines=[
                        (line.edited_prepro or line.preprocessed)
                        for line in chunk
                    ],
                    line_indices=[line.idx for line in chunk],
                    context_type=(ctx.get("context_type", "unknown") if ctx else "unknown"),
                    receives_context=(ctx.get("receives_context", False) if ctx else False),
                    provides_context=(ctx.get("provides_context", True) if ctx else True),
                    _merge_boundaries=(ctx.get("merge_boundaries", []) if ctx else []),
                )
                # Infer file section from receives_context transitions
                req._file_section = getattr(chunk[0], "_file_section", 0) if chunk else 0
                chunk_to_req[i] = req
                requests.append(req)

            # Sort into RequestString objects
            sorted_strings = sort_requests_by_type(requests)

            # Map back to chunk indices
            req_to_chunk: Dict[int, int] = {}
            for chunk_idx, req in chunk_to_req.items():
                req_id = id(req)
                req_to_chunk[req_id] = chunk_idx

            result: List[List[List["TranslatableLine"]]] = []
            for rs in sorted_strings:
                string_chunks: List[List["TranslatableLine"]] = []
                for req in rs.requests:
                    chunk_idx = req_to_chunk.get(id(req))
                    if chunk_idx is not None:
                        string_chunks.append(chunks[chunk_idx])
                if string_chunks:
                    result.append(string_chunks)

            return result if result else [chunks]

        except ImportError:
            pass

        # Fallback: each chunk is its own string
        return [[chunk] for chunk in chunks]

    # ------------------------------------------------------------------
    # Single-Chunk Processing (used by both gate and sequential worker)
    # ------------------------------------------------------------------

    def _process_single_chunk(
        self,
        chunk: List[TranslatableLine],
        chunk_idx: int,
        total_chunks: int,
        rolling_ctx_buffer: list[str],
        rolling_ctx_max: int,
        rolling_ctx_between: int,
        rolling_ctx_after: int,
        use_translated_ctx: bool,
        all_chunks: List[List[TranslatableLine]],
        progress_lock: threading.Lock,
    ) -> str:
        """Process a single chunk: build context, translate, apply filters.

        Returns:
            ``"ok"`` on success, ``"abort"`` if a fatal error occurred,
            ``"cancel"`` if the user cancelled.
        """
        if self._cancel_requested:
            return "cancel"

        # Wait while paused
        while self._pause_requested:
            time.sleep(0.1)
            if self._cancel_requested:
                return "cancel"

        self._log_progress(
            f"Processing chunk {chunk_idx + 1}/{total_chunks}"
        )

        # Mark lines as translating
        for line in chunk:
            line.status = LineStatus.TRANSLATING
            line.chunk_id = chunk_idx
        self.after(0, self._update_lines_table)

        # Build rolling context text for this chunk
        formation_ctx = (
            getattr(chunk[0], "_formation_ctx", None) if chunk else None
        )
        receives_context = (
            formation_ctx.get("receives_context", False)
            if formation_ctx else (chunk_idx > 0)
        )

        # Reset buffer at file boundaries
        if not receives_context:
            rolling_ctx_buffer.clear()

        rolling_context_text = ""
        if receives_context and rolling_ctx_buffer and rolling_ctx_max > 0:
            tail = rolling_ctx_buffer[-rolling_ctx_max:]
            rolling_context_text = "\n".join(tail)

        # Build "between" context
        between_context_text = ""
        if rolling_ctx_between > 0 and self._manifest_manager is not None:
            between_lines = self._collect_between_context(
                chunk, rolling_ctx_between, use_translated_ctx,
            )
            if between_lines:
                between_context_text = "\n".join(between_lines)

        # Build "after" context
        after_context_text = ""
        if rolling_ctx_after > 0 and self._manifest_manager is not None:
            after_lines = self._collect_after_context(
                chunk, all_chunks, chunk_idx, rolling_ctx_after,
                use_translated_ctx,
            )
            if after_lines:
                after_context_text = "\n".join(after_lines)

        # Combine all rolling context parts
        full_context_text = rolling_context_text
        if between_context_text:
            from CherryAI.functions.prompt_builder import format_rolling_context
            full_context_text += format_rolling_context(
                between_context_text.split("\n"),
                is_translated=use_translated_ctx,
                context_type="between",
            )
        if after_context_text:
            from CherryAI.functions.prompt_builder import format_rolling_context
            full_context_text += format_rolling_context(
                after_context_text.split("\n"),
                is_translated=use_translated_ctx,
                context_type="after",
            )

        # Translate chunk
        try:
            translations = self._translate_chunk(
                chunk, rolling_context_text=full_context_text,
            )

            # Apply character whitelist/blacklist filters
            translations = self._apply_char_filters(
                translations, line_objects=chunk,
            )

            # Apply translations
            for line, translation in zip(chunk, translations):
                line.translated = translation
                if line.status not in (
                    LineStatus.NEEDS_REVIEW, LineStatus.PENDING,
                ):
                    line.status = LineStatus.COMPLETED
                with progress_lock:
                    self._progress.translated_lines += 1
                # Persist to manifest
                if self._manifest_manager is not None:
                    self._manifest_manager.update_translation(
                        line.idx, translation,
                    )

            # Validate preserve-action code patterns after translation.
            # Attempt recovery for each line where the LLM translated
            # a code pattern instead of preserving it.  If recovery
            # fails, flag the line for QA review.
            if self._manifest_manager is not None:
                _cp = self._manifest_manager.get_code_patterns()
                if _cp:
                    from CherryAI.functions.postprocess import (
                        recover_code_patterns as _rcp,
                        RecoveryAction as _RA,
                    )
                    for line in chunk:
                        if not line.translated:
                            continue
                        _orig = (
                            line.edited_prepro
                            or line.preprocessed
                            or line.original
                        )
                        _fixed, _iss = _rcp(
                            line.translated, _orig, _cp,
                        )
                        if _fixed != line.translated:
                            line.translated = _fixed
                            self._manifest_manager.update_translation(
                                line.idx, _fixed,
                            )
                        if any(
                            i.action == _RA.NEEDS_RETRY for i in _iss
                        ):
                            line.status = LineStatus.NEEDS_REVIEW

            # Flush to disk immediately so no chunk is lost
            if self._manifest_manager is not None:
                self._manifest_manager.save()

            # Update rolling context buffer
            provides_context = (
                formation_ctx.get("provides_context", True)
                if formation_ctx else True
            )
            if provides_context:
                if use_translated_ctx:
                    rolling_ctx_buffer.extend(translations)
                else:
                    rolling_ctx_buffer.extend(
                        line.edited_prepro or line.preprocessed
                        for line in chunk
                    )

        except TranslationAbortError as abort_err:
            # Fatal API error — mark lines failed, store abort.
            for line in chunk:
                line.status = LineStatus.FAILED
                line.error_message = abort_err.user_message
                with progress_lock:
                    self._progress.failed_lines += 1
            self.after(0, self._update_lines_table)
            self._abort_error = abort_err
            return "abort"

        except Exception as e:
            self._log_progress(
                f"Chunk {chunk_idx + 1} failed: {e}"
            )
            self._handle_chunk_retry(chunk, e, progress_lock)

        # Update progress
        self._update_progress_display()
        self.after(0, self._update_lines_table)
        return "ok"

    # ------------------------------------------------------------------
    # Chunk Retry Handler
    # ------------------------------------------------------------------

    def _handle_chunk_retry(
        self,
        chunk: List[TranslatableLine],
        error: Exception,
        progress_lock: threading.Lock,
    ) -> None:
        """Retry a failed chunk using the standard retry handler."""
        original_lines = [line.preprocessed for line in chunk]
        translations = [""] * len(chunk)

        retry_config, _ = create_retry_config(
            strategy=self._translation_options.retry_strategy,
            max_retries=self._translation_options.max_retries,
            context_lines=2,
        )

        def translate_fn(
            lines: List[str], prompt: str | None,
        ) -> List[str]:
            if self._api_client is None:
                return [f"[Retry] {line}" for line in lines]
            return self._api_client.translate_batch(
                lines, system_prompt=prompt or "",
            )

        retry_result, method = handle_failed_lines(
            failed_indices=list(range(len(chunk))),
            original_lines=original_lines,
            translations=translations,
            translate_fn=translate_fn,
            config=retry_config,
            system_prompt=self._get_prompt_parts().get("summary", ""),
        )

        for i, line in enumerate(chunk):
            if i < len(retry_result.line_results):
                result = retry_result.line_results[i]
                if result.success:
                    line.translated = result.translation
                    line.status = LineStatus.COMPLETED
                    with progress_lock:
                        self._progress.translated_lines += 1
                    if self._manifest_manager is not None:
                        self._manifest_manager.update_translation(
                            line.idx, result.translation,
                        )
                else:
                    line.status = LineStatus.FAILED
                    line.error_message = (
                        result.error_message or str(error)
                    )
                    with progress_lock:
                        self._progress.failed_lines += 1
            else:
                line.status = LineStatus.FAILED
                line.error_message = str(error)
                with progress_lock:
                    self._progress.failed_lines += 1

        self._log_progress(
            f"Retry complete: {retry_result.successful_count} recovered, "
            f"{retry_result.failed_count} failed ({method})"
        )

        # Flush to disk after retry so recovered translations are not lost
        if self._manifest_manager is not None:
            self._manifest_manager.save()

    # ------------------------------------------------------------------
    # Sequential String Worker (runs inside a thread)
    # ------------------------------------------------------------------

    def _execute_string_sequential(
        self,
        string_chunks: List[List[TranslatableLine]],
        rolling_ctx_buffer: list[str],
        rolling_ctx_max: int,
        rolling_ctx_between: int,
        rolling_ctx_after: int,
        use_translated_ctx: bool,
        all_chunks: List[List[TranslatableLine]],
        progress_lock: threading.Lock,
    ) -> None:
        """Execute all chunks of a single string sequentially.

        Designed to run inside a ``ThreadPoolExecutor`` thread. Each
        string has its own ``rolling_ctx_buffer`` so there are no
        cross-thread buffer conflicts.

        Args:
            string_chunks: Ordered chunks for one request string.
            rolling_ctx_buffer: Per-string rolling context (caller
                provides the initial buffer; this method extends it).
            rolling_ctx_max: Max rolling context window size.
            rolling_ctx_between: Between context line count.
            rolling_ctx_after: After context line count.
            use_translated_ctx: Whether to use translated text for ctx.
            all_chunks: All chunks (for after-context lookup).
            progress_lock: Lock for thread-safe progress updates.

        Raises:
            TranslationAbortError: Re-raised from ``_process_single_chunk``
                when a fatal API error is encountered.
        """
        total = len(all_chunks)
        for chunk in string_chunks:
            if self._cancel_requested:
                break
            if hasattr(self, "_abort_error") and self._abort_error is not None:
                break

            # Determine global chunk index for logging
            chunk_idx = 0
            if chunk and chunk[0]:
                for ci, c in enumerate(all_chunks):
                    if c is chunk or (c and c[0].idx == chunk[0].idx):
                        chunk_idx = ci
                        break

            result = self._process_single_chunk(
                chunk=chunk,
                chunk_idx=chunk_idx,
                total_chunks=total,
                rolling_ctx_buffer=rolling_ctx_buffer,
                rolling_ctx_max=rolling_ctx_max,
                rolling_ctx_between=rolling_ctx_between,
                rolling_ctx_after=rolling_ctx_after,
                use_translated_ctx=use_translated_ctx,
                all_chunks=all_chunks,
                progress_lock=progress_lock,
            )

            if result == "abort":
                if self._abort_error is not None:
                    raise self._abort_error
                break
            if result == "cancel":
                break

    def _translate_chunk(
        self,
        chunk: List[TranslatableLine],
        rolling_context_text: str = "",
    ) -> List[str]:
        """Translate a chunk of lines.

        TASK 43.5: Routes to MockTranslator when mock model selected.

        Args:
            chunk: Lines to translate.
            rolling_context_text: Pre-formatted rolling context from
                previously translated chunks.

        Returns:
            List of translations.
        """
        # TASK 43.5: Use mock translator if available
        if hasattr(self, "_mock_translator") and self._mock_translator is not None:
            lines_to_translate = [
                line.edited_prepro if line.edited_prepro else line.preprocessed
                for line in chunk
            ]
            return self._mock_translator.translate_batch(lines_to_translate)

        if self._api_client is None:
            # Simulation mode (fallback when no API and not mock)
            time.sleep(0.5)
            return [
                f"[Translated] {line.edited_prepro or line.preprocessed}"
                for line in chunk
            ]

        # Build system prompt from manifest (Information step data)
        # NOTE: System prompt is built AFTER collecting chunk lines
        # so that selective filtering can be applied.

        # Get text for translation - use edited_prepro if available (Task 33.1)
        lines_to_translate = [
            line.edited_prepro if line.edited_prepro else line.preprocessed
            for line in chunk
        ]

        # Filter __DEDUP__ lines from request input
        filtered_for_api = [
            ln for ln in lines_to_translate if "__DEDUP__" not in ln
        ]

        # Extract context_type from formation metadata for conditional prompt
        context_type = ""
        merge_instruction = ""
        formation_ctx = getattr(chunk[0], "_formation_ctx", None) if chunk else None
        if formation_ctx:
            context_type = formation_ctx.get("context_type", "")
            boundaries = formation_ctx.get("merge_boundaries", [])
            if boundaries and len(boundaries) > 1:
                try:
                    from CherryAI.functions.conditional_prompts import (
                        build_merged_request_instruction,
                    )
                    merge_instruction = build_merged_request_instruction(
                        boundaries,
                    )
                except ImportError:
                    pass

        system_prompt = self._build_system_prompt_from_manifest(
            rolling_context_text=rolling_context_text,
            chunk_lines=filtered_for_api,
            merge_instruction=merge_instruction,
            context_type=context_type,
        )

        # Log outgoing request when enabled in Global Options
        self._log_request_json(system_prompt, filtered_for_api)

        # Call API
        translations = self._api_client.translate_batch(
            filtered_for_api,
            system_prompt=system_prompt if system_prompt else None,
        )

        # Update token count
        if hasattr(self._api_client, "_total_prompt_tokens"):
            self._progress.tokens_used = (
                self._api_client._total_prompt_tokens +
                self._api_client._total_completion_tokens
            )

        return translations

    def _apply_char_filters(
        self,
        texts: List[str],
        line_objects: Optional[List[Any]] = None,
    ) -> List[str]:
        """Validate translations against character whitelist/blacklist.

        Instead of stripping characters, this method:
        1. Parses entries supporting ``re=`` regex and ``\\,`` literal commas.
        2. Checks each text for violations.
        3. If *exchange* is enabled, applies the autofix map to fix what it can.
        4. Re-checks after exchange; remaining violations are handled by
           *retry* (revert to original) or *flag* (mark ``NEEDS_REVIEW``).

        Args:
            texts: Raw translation strings.
            line_objects: Optional list of ``TranslatableLine`` objects
                corresponding to *texts* (used for setting status).

        Returns:
            The (possibly exchanged) translation strings.
        """
        from CherryAI.functions.validation import (
            parse_filter_entries,
            check_filter_violations,
            apply_autofix,
        )

        whitelist_raw = self._whitelist_var.get().strip()
        blacklist_raw = self._blacklist_var.get().strip()
        if not whitelist_raw and not blacklist_raw:
            return texts

        wl_entries = parse_filter_entries(whitelist_raw)
        bl_entries = parse_filter_entries(blacklist_raw)
        if not wl_entries and not bl_entries:
            return texts

        # Read strategy settings from global options
        go = getattr(self.session, "global_options", None)
        exchange = True
        flag_qa = True
        retry = False
        if go is not None:
            ts = getattr(go, "translation", None)
            if ts is not None:
                exchange = getattr(ts, "exchange_forbidden_chars", True)
                flag_qa = getattr(ts, "flag_for_qa_review", True)
                retry = getattr(ts, "retry_forbidden_chars", False)

        # Load autofix map from manifest when exchange is enabled
        autofix_map: Dict[str, str] = {}
        if exchange:
            mgr = getattr(self, "manifest_manager", None) or getattr(
                self, "_manifest_manager", None,
            )
            if mgr is not None:
                try:
                    autofix_map = mgr.get_autofix_map()
                except Exception:
                    autofix_map = {}

        result: List[str] = list(texts)
        for i, text in enumerate(texts):
            violations = check_filter_violations(text, wl_entries, bl_entries)
            if not violations:
                continue

            # Strategy 1: Exchange forbidden characters via autofix map
            if exchange and autofix_map:
                fixed, _count = apply_autofix(text, autofix_map)
                if _count > 0:
                    result[i] = fixed
                    # Re-check after exchange
                    violations = check_filter_violations(
                        fixed, wl_entries, bl_entries,
                    )
                    if not violations:
                        continue

            # Strategy 2: Retry — revert to empty so caller retries
            if retry:
                result[i] = ""
                if line_objects and i < len(line_objects):
                    line_objects[i].status = LineStatus.PENDING
                continue

            # Strategy 3: Flag for QA review
            if flag_qa and line_objects and i < len(line_objects):
                line_objects[i].status = LineStatus.NEEDS_REVIEW

        return result

    def _log_request_json(
        self,
        system_prompt: str,
        lines_to_translate: List[str],
    ) -> None:
        """Write outgoing request as JSON when log_requests is enabled.

        Logs are written to the ``logs/`` directory as timestamped JSON files
        so that actual requests can be compared against the Request Preview.

        Args:
            system_prompt: The full system prompt built for this chunk.
            lines_to_translate: The input lines sent to the API.
        """
        try:
            go = getattr(self.session, "global_options", None)
            if go is None or not getattr(go.logging, "log_requests", False):
                return

            from pathlib import Path

            log_dir = Path(__file__).resolve().parents[2] / "logs" / "requests"
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            chunk_idx = self._progress.current_chunk
            filename = f"request_{timestamp}_chunk{chunk_idx}.json"

            payload = {
                "timestamp": timestamp,
                "chunk_index": chunk_idx,
                "model": self._translation_options.model,
                "temperature": self._translation_options.temperature,
                "system_prompt": system_prompt,
                "input_lines": lines_to_translate,
                "line_count": len(lines_to_translate),
            }

            (log_dir / filename).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("Logged request to %s", filename)
        except Exception:
            logger.debug("Failed to log request JSON", exc_info=True)

    def _update_progress_display(self) -> None:
        """Update the progress window display."""
        if self._progress_window is None:
            return

        # Calculate elapsed and ETA
        elapsed = time.time() - self._progress.start_time
        self._progress.elapsed_seconds = elapsed

        processed = self._progress.translated_lines + self._progress.failed_lines
        if processed > 0 and processed < self._progress.total_lines:
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = self._progress.total_lines - processed
            self._progress.eta_seconds = remaining / rate if rate > 0 else 0
        else:
            self._progress.eta_seconds = 0

        # Token speed
        if elapsed > 0 and self._progress.tokens_used > 0:
            self._progress.tokens_per_second = self._progress.tokens_used / elapsed

        self.after(0, lambda: self._progress_window.update_progress(self._progress) if self._progress_window else None)

    def _log_progress(self, message: str) -> None:
        """Log a message to the progress window.

        Args:
            message: Message to log.
        """
        logger.info(message)
        if self._progress_window:
            self.after(0, lambda: self._progress_window.log(message) if self._progress_window else None)

    def _on_pause(self) -> None:
        """Handle pause request."""
        self._pause_requested = True
        self._translation_state = TranslationState.PAUSED
        if self._progress_window:
            self._progress_window.set_state(TranslationState.PAUSED)
        self._log_progress("Translation paused")

    def _on_resume(self) -> None:
        """Handle resume request."""
        self._pause_requested = False
        self._translation_state = TranslationState.RUNNING
        if self._progress_window:
            self._progress_window.set_state(TranslationState.RUNNING)
        self._log_progress("Translation resumed")

    def _on_cancel(self) -> None:
        """Handle cancel request."""
        self._cancel_requested = True
        self._translation_state = TranslationState.CANCELLED
        if self._progress_window:
            self._progress_window.set_state(TranslationState.CANCELLED)

    def _on_translation_complete(self) -> None:
        """Called when translation completes."""
        self._translate_btn.configure(state="normal")
        self._update_lines_table()

        # Update API usage panel
        if self._api_client:
            tokens = self._progress.tokens_used
            self._usage_tokens_label.configure(text=f"{tokens:,}")

            # Estimate cost
            from CherryAI.gui.steps.costs import estimate_cost
            cost = estimate_cost(tokens // 2, tokens // 2, self._translation_options.model)
            self._usage_cost_label.configure(text=f"${cost['total_usd']:.2f}")

        # Update progress window state
        if self._progress_window:
            self._progress_window.set_state(self._translation_state)

        # Show abort error dialog if translation was aborted
        abort_err = getattr(self, "_abort_error", None)
        if abort_err is not None:
            self._show_abort_error_dialog(abort_err)
            self._abort_error = None

        # Store results in session
        step_data = self.session.get_step(self.step_id).data
        step_data["translated_lines"] = [l.translated for l in self._lines]
        step_data["translation_status"] = {
            "completed": sum(1 for l in self._lines if l.status == LineStatus.COMPLETED),
            "failed": sum(1 for l in self._lines if l.status == LineStatus.FAILED),
            "skipped": sum(1 for l in self._lines if l.status == LineStatus.SKIPPED),
        }

        # Update status label
        completed = sum(1 for l in self._lines if l.status == LineStatus.COMPLETED)
        failed = sum(1 for l in self._lines if l.status == LineStatus.FAILED)
        self._status_label.configure(
            text=f"Completed: {completed}, Failed: {failed}"
        )

    def _show_abort_error_dialog(self, abort_err: TranslationAbortError) -> None:
        """Show a user-facing error dialog for a translation abort.

        Displays the classified error message, remediation steps, and
        for unknown errors includes the raw API message so the user can
        copy it for bug reports.

        Args:
            abort_err: The classified abort error.
        """
        display_text = abort_err.format_for_display()
        messagebox.showerror("Translation Aborted", display_text)

    def on_new_project(self) -> None:
        """Reset cached state for a fresh project."""
        super().on_new_project()
        self._lines.clear()
        self._cancel_requested = False
        self._pause_requested = False
        self._api_client = None
        self._manifest_bindings.clear()
        logger.debug("Translation step reset for new project")

    def on_enter(self) -> None:
        """Called when step becomes active."""
        # TASK 43.6: Update model list from Global Options
        self._update_model_list_from_global_options()

        # TASK 43.14: Skip refresh when cache is valid
        if self._is_cache_valid():
            return

        # Refresh lines from previous steps
        if not self._lines:
            self._refresh_lines()

        # Load prompt data from config if available
        self._load_prompt_data()

        # Load request options from manifest
        self._load_request_options_from_manifest()

        # TASK 43.14: Update cache hash after full refresh
        self._update_cache()

    def _update_model_list_from_global_options(self) -> None:
        """Refresh model dropdown from the selected key's provider.

        When an API key is selected in the Key dropdown, models are
        filtered to that provider.  Falls back to the full registry or
        hardcoded list when no key is selected.

        Priority:
        1. Provider-filtered models when a key is selected.
        2. model_registry.get_all_models_flat() (dynamic / cached registry).
        3. Hardcoded MODEL_OPTIONS as a last resort.
        """
        # If a key is selected, filter by its provider
        provider, _ = self._parse_key_selection()
        if provider:
            self._filter_models_by_provider(provider)
            return

        # No key selected — show all models from registry
        try:
            from CherryAI.functions.model_registry import get_all_models_flat
            reg_models = (
                ["Mock Translation"]
                + [m.model_id for m in get_all_models_flat()]
            )
            if len(reg_models) > 1:
                self._model_combo["values"] = reg_models
                return
        except Exception:
            pass

        # Final fallback: use hardcoded list
        self._model_combo["values"] = self.MODEL_OPTIONS

    def _save_temperature_to_manifest(self) -> None:
        """Save temperature value to manifest."""
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            try:
                value = self._temp_var.get()
                save_nested_float_field(
                    mgr, "RequestOptions", "Temperature", value
                )
            except (tk.TclError, ValueError):
                pass  # Ignore invalid values during typing

    def _load_request_options_from_manifest(self) -> None:
        """Load request options from manifest into UI widgets."""
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        # Load API Key selection
        key_provider = load_nested_text_field(
            mgr, "RequestOptions", "ApiKeyProvider", "",
        )
        key_name = load_nested_text_field(
            mgr, "RequestOptions", "ApiKeyName", "",
        )
        if key_provider and key_name:
            combo_val = f"{key_provider}: {key_name}"
            # Only set if this key still exists in saved keys
            current_values = list(self._key_combo["values"])
            if combo_val in current_values:
                self._key_var.set(combo_val)
                self._filter_models_by_provider(key_provider)

        # Load Model
        model = load_nested_text_field(mgr, "RequestOptions", "Model", "")
        if model:
            self._model_var.set(model)

        # Load Temperature
        temp = load_nested_float_field(
            mgr, "RequestOptions", "Temperature", 0.2
        )
        self._temp_var.set(temp)

        # Load LinesPerChunk
        chunk_size = load_nested_int_field(
            mgr, "RequestOptions", "LinesPerChunk", 30
        )
        self._chunk_var.set(chunk_size)

        # Load RetryStrategy
        retry = load_nested_text_field(mgr, "RequestOptions", "RetryStrategy", "")
        if retry:
            self._retry_var.set(retry)

        # Load MaxRetries
        max_retries = load_nested_int_field(
            mgr, "RequestOptions", "MaxRetries", 3
        )
        self._retries_var.set(max_retries)

        # Load EnableRequestCaching
        caching = load_nested_bool_field(
            mgr, "RequestOptions", "EnableRequestCaching", True
        )
        self._cache_var.set(caching)

        # Load LineByLineMode
        line_by_line = load_nested_bool_field(
            mgr, "RequestOptions", "LineByLineMode", False
        )
        self._line_by_line_var.set(line_by_line)

        # Load ContextLines
        context_lines = load_nested_int_field(
            mgr, "RequestOptions", "ContextLines", 2
        )
        self._context_lines_var.set(context_lines)

        # Load Thinking
        thinking = load_nested_bool_field(
            mgr, "RequestOptions", "Thinking", False
        )
        self._thinking_var.set(thinking)

        # Load ThinkingBudget
        thinking_budget = load_nested_int_field(
            mgr, "RequestOptions", "ThinkingBudget", 10000
        )
        self._thinking_budget_var.set(thinking_budget)

        # Load ReasoningEffort
        reasoning_effort = load_nested_text_field(
            mgr, "RequestOptions", "ReasoningEffort", "medium"
        )
        if reasoning_effort not in ("low", "medium", "high"):
            reasoning_effort = "medium"
        self._reasoning_effort_var.set(reasoning_effort)

        # TASK 43.7/43.8/43.9: Override from Global Options when available
        self._sync_from_global_options()

    def _sync_from_global_options(self) -> None:
        """Apply Global Options overrides for caching, thinking, context.

        Global Options values take precedence over per-project manifest
        values for these settings (Tasks 43.7, 43.8, 43.9).
        """
        try:
            go = getattr(self.session, "global_options", None)
        except Exception:
            return
        if go is None:
            return

        # Task 43.7: Cache mode from Global Options
        if hasattr(go, "caching"):
            self._cache_var.set(go.caching.enabled)

        # Task 43.8: Thinking mode from Global Options
        if hasattr(go, "request"):
            self._thinking_var.set(go.request.thinking_enabled)
            self._thinking_budget_var.set(go.request.thinking_budget)
            self._reasoning_effort_var.set(go.request.reasoning_effort)

        # Task 43.9: Rolling context from Global Options
        if hasattr(go, "request"):
            self._context_lines_var.set(go.request.rolling_context_lines)
            self._chunk_var.set(go.request.chunk_size)

        # Translation settings from Global Options
        if hasattr(go, "translation"):
            tr = go.translation
            self._retry_var.set(getattr(tr, "retry_strategy", "batch"))
            self._skip_non_source_var.set(
                getattr(tr, "skip_non_source_language", True),
            )
            # overwrite_translation inverts skip_translated
            overwrite = getattr(tr, "overwrite_translation", False)
            self._skip_translated_var.set(not overwrite)
            self._edit_before_var.set(False)

    def on_leave(self) -> None:
        """Called when leaving step."""
        # Store current state
        step_data = self.session.get_step(self.step_id).data
        step_data["options"] = {
            "model": self._model_var.get(),
            "temperature": self._temp_var.get(),
            "chunk_size": self._chunk_var.get(),
            "retry_strategy": self._retry_var.get(),
            "line_by_line": self._line_by_line_var.get(),
            "context_lines": self._context_lines_var.get(),
            "thinking_enabled": self._thinking_var.get(),
            "thinking_budget": self._thinking_budget_var.get(),
            "reasoning_effort": self._reasoning_effort_var.get(),
        }

    def _load_prompt_data(self) -> None:
        """Load prompt data from manifest Information step metadata.

        Reads Summary and Style from ``step_state.Information.data.metadata``
        set by the Information step.  Falls back to config files for
        backward compatibility.
        """
        try:
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                # Read from Information metadata (step index 2)
                metadata = mgr.get_step_data_value(2, "metadata", {})
                if isinstance(metadata, dict):
                    summary = (metadata.get("summary", "") or "").strip()
                    if summary:
                        self._summary_text.delete("1.0", "end")
                        self._summary_text.insert("1.0", summary)

                    style = (metadata.get("style", "") or "").strip()
                    if style:
                        self._style_var.set(style[:100])
                    return

            # Fallback: load from config files (legacy)
            from pathlib import Path
            config_dir = Path(__file__).parent.parent.parent / "config"

            summary, _ = get_game_summary(str(config_dir / "game_summary.txt"))
            if summary:
                self._summary_text.delete("1.0", "end")
                self._summary_text.insert("1.0", summary)

            style, _ = get_translation_style(
                str(config_dir / "translation_style.txt"),
                config_dir,
            )
            if style:
                self._style_var.set(style[:100])

        except Exception as e:
            logger.debug("Error loading prompt data: %s", e)

    def _show_request_preview(self) -> None:
        """Show request preview dialog with all API requests.

        Builds the exact same requests that would be sent during
        translation, using the same system prompt construction and
        chunking logic.  Opens a read-only dialog with Jump To,
        Search, View modes (Pure/Formatted/Plain), and part filters.
        """
        if not self._lines:
            self._refresh_lines()

        if not self._lines:
            messagebox.showwarning(
                "No Data",
                "Please load files in the Input step first.",
            )
            return

        # Build structured requests using the same code path as translation
        requests = self._build_preview_requests()

        if not requests:
            messagebox.showinfo(
                "Preview Requests",
                "No translatable lines found.",
            )
            return

        # Open the preview dialog
        RequestPreviewDialog(self, requests)

    def _build_preview_requests(self) -> "list[PreviewRequest]":
        """Build preview request objects mirroring the real translation flow.

        Uses ``gather_prompt_data`` + ``build_request_prompt`` from
        prompt_adapter.py (single source of truth) for both data
        gathering and §5.2 prompt assembly.  Individual metadata
        fields are extracted from the gathered data for the labelled
        preview parts so the dialog can highlight each section.

        Returns:
            List of :class:`PreviewRequest` with labelled parts.
        """
        from CherryAI.gui.helpers.prompt_adapter import (
            gather_prompt_data,
            build_request_prompt,
        )

        # Gather options from UI
        opts = self._get_options_from_ui()

        # Gather pending lines (same filtering as _do_translation)
        pending = [
            line for line in self._lines
            if line.status in (LineStatus.PENDING, LineStatus.COMPLETED,
                               LineStatus.FAILED, LineStatus.SKIPPED)
        ]
        if not pending:
            pending = list(self._lines)

        # Apply the same language skip as the real translation flow so
        # that non-source-language lines (e.g. English in a JP project)
        # do not appear in the preview.
        if self._skip_non_source_var.get():
            pending = self._apply_language_skip(pending)

        # Chunk the lines the same way translation does
        chunks = self._build_chunks(pending)

        # Rolling context setting (for preview hint)
        go = getattr(self.session, "global_options", None)
        try:
            rolling_ctx_max = int(go.request.rolling_context_lines) if go else 3
        except (TypeError, ValueError, AttributeError):
            rolling_ctx_max = 3

        # Gather all prompt data from manifest — single entry point
        # shared with costs and translation to guarantee identical
        # prompts.
        mgr = self.manifest_manager
        sample_lines = [
            (line.edited_prepro or line.preprocessed or line.original)
            for line in self._lines[:200]
        ]
        prompt_data = gather_prompt_data(mgr, sample_lines=sample_lines)

        metadata = prompt_data["metadata"]
        glossary_entries = prompt_data["glossary_entries"]
        characters = prompt_data["characters"]
        pov_data = prompt_data["pov_data"]

        # Initialise labelled section blocks for the preview UI
        language_block = ""
        sys_instructions = ""
        io_examples_block = ""
        summary_block = ""
        style_block = ""
        tone_block = ""
        genre_block = ""
        pov_block = ""

        # Extract individual labelled sections (non-per-chunk sections)
        src = (metadata.get("source_language", "") or "").strip()
        tgt = (metadata.get("target_language", "") or "").strip()
        if src and tgt:
            language_block = f"# Language\nTranslate from {src} to {tgt}."

        # --- Section toggle flags from Information metadata (§5.2) ---
        si_enabled = metadata.get("system_instructions_enabled", True)
        style_enabled = metadata.get("style_enabled", False)
        tone_enabled = metadata.get("tone_enabled", False)
        summary_enabled = metadata.get("summary_enabled", False)
        genre_enabled = metadata.get("genre_enabled", False)
        glossary_enabled = metadata.get("glossary_enabled", True)

        if si_enabled:
            sys_instructions = (metadata.get("system_instructions", "") or "").strip()

        # --- I/O Examples (slot 2b) ---
        io_mode = (metadata.get("io_examples", "disabled") or "disabled").strip()
        if io_mode != "disabled":
            try:
                from CherryAI.functions.io_examples import (
                    generate_io_examples as _gen_io,
                    calculate_fill_target as _calc_fill,
                    estimate_tokens as _est_tok,
                )
            except ImportError:
                _gen_io = None  # type: ignore[assignment]
            if _gen_io is not None:
                io_src = (metadata.get("source_language", "") or "").strip()
                io_tgt = (metadata.get("target_language", "") or "").strip()
                if io_mode == "fill":
                    # Estimate all static part tokens for fill calculation
                    _static_parts = [language_block, sys_instructions]
                    if style_enabled:
                        _sv = (metadata.get("style", "") or "").strip()
                        if _sv:
                            _static_parts.append(
                                f"# Translation Style Guidelines\n{_sv}")
                    if tone_enabled:
                        _tv = (metadata.get("tone", "") or "").strip()
                        if _tv:
                            _static_parts.append(f"# Translation Tone\n{_tv}")
                    if summary_enabled:
                        _smv = (metadata.get("summary", "") or "").strip()
                        if _smv:
                            _static_parts.append(f"# Game Context\n{_smv}")
                    if genre_enabled:
                        _gv = (metadata.get("genre", "") or "").strip()
                        if _gv:
                            _static_parts.append(f"# Genre\n{_gv}")
                    _static_toks = sum(_est_tok(p) for p in _static_parts if p)
                    _io_budget = _calc_fill(_static_toks)
                else:
                    _io_budget = int(io_mode)
                if _io_budget > 0:
                    _io_text, _ = _gen_io(
                        code_patterns=metadata.get("code_patterns", []),
                        source_language=io_src or "Japanese",
                        target_language=io_tgt or "English",
                        target_tokens=_io_budget,
                    )
                    if _io_text:
                        io_examples_block = _io_text

        if style_enabled:
            style_val = (metadata.get("style", "") or "").strip()
            if style_val:
                style_block = f"# Translation Style Guidelines\n{style_val}"

        if tone_enabled:
            tone_val = (metadata.get("tone", "") or "").strip()
            if tone_val:
                tone_block = f"# Translation Tone\n{tone_val}"

        if summary_enabled:
            summary_val = (metadata.get("summary", "") or "").strip()
            if summary_val:
                summary_block = f"# Game Context\n{summary_val}"

        if genre_enabled:
            genre_val = (metadata.get("genre", "") or "").strip()
            if genre_val:
                genre_block = f"# Genre\n{genre_val}"

        if isinstance(pov_data, dict) and pov_data.get("confidence") == "high":
            pov_label = {
                "1st": "first", "2nd": "second", "3rd": "third",
            }.get(pov_data.get("pov", ""), pov_data.get("pov", ""))
            pov_block = (
                f"# Narrative Perspective\n"
                f"The narrative uses {pov_label} person perspective. "
                f"Maintain consistent {pov_label} person perspective "
                f"throughout."
            )

        # Conditional import
        from CherryAI.gui.helpers.prompt_adapter import (
            build_conditional_instructions,
        )

        # Meta info
        meta_block = (
            f"model: {opts.model}\n"
            f"temperature: {opts.temperature}\n"
            f"response_format: {{\"type\": \"json_object\"}}"
        )

        # Build preview requests per chunk — glossary, characters, and
        # conditional prompts are selective (only included when their
        # source term / trigger appears in the chunk's lines).
        requests: list[PreviewRequest] = []
        for chunk_idx, chunk in enumerate(chunks):
            lines_for_chunk = [
                line.edited_prepro or line.preprocessed or line.original
                for line in chunk
            ]

            # Filter out __DEDUP__ lines from input
            filtered_lines = [
                ln for ln in lines_for_chunk
                if "__DEDUP__" not in ln
            ]

            chunk_text_joined = "\n".join(filtered_lines)

            # Per-chunk selective glossary (gated by glossary_enabled)
            chunk_glossary_block = ""
            if glossary_enabled:
                active = [
                    e for e in glossary_entries
                    if e.get("active", True) and e.get("source", "")
                    and e["source"] in chunk_text_joined
                ]
                if active:
                    g_lines = ["# Glossary", "Use these terms strictly:"]
                    for entry in active:
                        s = entry.get("source", "")
                        t = entry.get("target", "")
                        n = entry.get("notes", "")
                        if s:
                            lt = f"- {s} → {t}" if t else f"- {s}"
                            if n:
                                lt += f" ({n})"
                            g_lines.append(lt)
                    chunk_glossary_block = "\n".join(g_lines)

            # Per-chunk selective characters (gated by glossary_enabled)
            if glossary_enabled:
                relevant_chars = [
                    ch for ch in characters
                    if ch.get("original_name", "")
                    and ch["original_name"] in chunk_text_joined
                ]
            else:
                relevant_chars = []
            if relevant_chars:
                char_lines = ["# Characters"]
                for ch in relevant_chars:
                    orig = ch.get("original_name", "")
                    eng = ch.get("translation", "") or ch.get("name", "")
                    notes = ch.get("notes", "")
                    if orig:
                        et = f"- {orig}"
                        if eng:
                            et += f" → {eng}"
                        if notes:
                            et += f" ({notes})"
                        char_lines.append(et)
                if len(char_lines) > 1:
                    if chunk_glossary_block:
                        chunk_glossary_block += "\n\n" + "\n".join(char_lines)
                    else:
                        chunk_glossary_block = "\n".join(char_lines)

            # Per-chunk selective conditional prompts
            chunk_conditional_block = ""
            cond_text, _ = build_conditional_instructions(filtered_lines)
            if cond_text and cond_text.strip():
                chunk_conditional_block = cond_text.strip()

            # Build per-chunk full system prompt with selective filtering
            # Resolve context type from tags → filedir → fallback
            from CherryAI.functions.analysis import resolve_chunk_type
            chunk_line_indices = [line.idx for line in chunk]
            m_lines = mgr.get_lines() if mgr is not None and mgr.is_loaded else []
            m_filedir = mgr.get_filedir() if mgr is not None and mgr.is_loaded else []
            resolved_type = resolve_chunk_type(
                chunk_line_indices, m_lines, m_filedir,
            )
            chunk_full_prompt, _ = build_request_prompt(
                prompt_data,
                chunk_lines=filtered_lines,
                context_type=resolved_type,
            )

            # Rolling context preview — show actual orig lines for
            # chunks that will receive rolling context.  At runtime the
            # option to use tl instead of orig is applied; the preview
            # always shows orig lines.
            formation_ctx = getattr(chunk[0], "_formation_ctx", None)
            receives_ctx = (
                formation_ctx.get("receives_context", False)
                if formation_ctx else (chunk_idx > 0)
            )
            rolling_ctx_hint = ""
            if receives_ctx and rolling_ctx_max > 0:
                # Find previous orig lines up to the file's first_idx
                first_line_idx = chunk[0].idx
                file_first_idx = 0
                if mgr is not None and mgr.is_loaded:
                    try:
                        for fd in mgr.get_filedir():
                            if fd.first_idx <= first_line_idx <= fd.last_idx:
                                file_first_idx = fd.first_idx
                                break
                    except Exception:
                        pass
                start = max(file_first_idx, first_line_idx - rolling_ctx_max)
                ctx_lines: list[str] = []
                if mgr is not None and mgr.is_loaded and start < first_line_idx:
                    m_lines = mgr.get_lines()
                    for ci in range(start, first_line_idx):
                        if 0 <= ci < len(m_lines):
                            ctx_lines.append(
                                m_lines[ci].get("orig", ""),
                            )
                if ctx_lines:
                    rolling_ctx_hint = "\n".join(ctx_lines)
                else:
                    rolling_ctx_hint = (
                        f"[Rolling context: last {rolling_ctx_max} "
                        f"translated lines will be inserted at "
                        f"translation time]"
                    )

            user_content = json.dumps(
                {"lines": filtered_lines}, ensure_ascii=False,
            )
            requests.append(PreviewRequest(
                index=chunk_idx,
                meta=meta_block,
                language=language_block,
                system_instructions=sys_instructions,
                io_examples=io_examples_block,
                summary=summary_block,
                style=style_block,
                tone=tone_block,
                genre=genre_block,
                pov=pov_block,
                conditional_prompts=chunk_conditional_block,
                glossary=chunk_glossary_block,
                rolling_context=rolling_ctx_hint,
                input_lines=user_content,
                full_system_prompt=chunk_full_prompt,
                line_count=len(filtered_lines),
            ))

        return requests

    def _detect_conditional_prompts(self) -> None:
        """Detect conditional prompts based on loaded lines.
        
        Note: This method is kept for backward compatibility but the
        conditional prompts text field has been removed from the UI.
        """
        if self._conditional_text is None:
            # Conditional prompts field removed - show info message
            messagebox.showinfo(
                "Conditional Prompts",
                "Conditional prompts are now managed separately.\n\n"
                "Use the Analysis step to detect patterns.",
            )
            return
            
        if not self._lines:
            messagebox.showinfo("Detection", "No lines loaded. Load files first.")
            return

        # Get sample lines for detection
        sample_lines = [l.preprocessed for l in self._lines[:50]]

        # Build conditional instructions
        instructions, method = build_conditional_instructions(sample_lines)

        if instructions:
            self._conditional_text.delete("1.0", "end")
            self._conditional_text.insert("1.0", instructions.strip())
            logger.info(f"Detected conditional prompts using {method}")
        else:
            messagebox.showinfo(
                "Detection",
                "No special patterns detected in the loaded lines.",
            )

    # ------------------------------------------------------------------
    # API Key selection helpers
    # ------------------------------------------------------------------

    def _populate_key_dropdown(self) -> None:
        """Populate the Key combobox from saved keys in API.ini."""
        try:
            from CherryAI.functions.api_config import list_api_keys
            keys = list_api_keys()
        except Exception:
            keys = []

        display_values: list[str] = []
        for provider, name in keys:
            display_values.append(f"{provider}: {name}")

        self._key_combo["values"] = display_values

        # Auto-select the first key if available and nothing is set
        if display_values and not self._key_var.get():
            self._key_var.set(display_values[0])
            self._on_key_changed()

    def _parse_key_selection(self) -> tuple[str, str]:
        """Parse the Key combobox value into (provider, name).

        Returns:
            Tuple of (provider, name) or ("", "") if invalid.
        """
        val = self._key_var.get()
        if not val or ": " not in val:
            return ("", "")
        provider, name = val.split(": ", 1)
        return (provider.strip(), name.strip())

    def _on_request_mode_changed(self, event: Any = None) -> None:
        """Handle request mode selection change.

        Filters the displayed modes based on the current model's
        pricing availability and applies the selection to the
        translation options.
        """
        display = self._request_mode_var.get()
        mode_key = display.lower()  # "normal", "batch", "flex", "priority"
        self._translation_options.request_slicing = mode_key

    def _refresh_request_mode_options(self) -> None:
        """Update request mode combobox options based on model availability.

        Marks unavailable modes with a suffix so the user knows which
        modes the current model supports.
        """
        if not hasattr(self, "_request_mode_combo") or not hasattr(
            self, "_request_mode_var",
        ):
            return

        model_id = self._model_var.get()
        if not model_id:
            return

        try:
            pricing = get_model_pricing(model_id)
        except Exception:
            return

        _MODES = (
            ("Normal", "input"),
            ("Batch", "batch_input"),
            ("Flex", "flex_input"),
            ("Priority", "priority_input"),
        )
        options: list[str] = []
        for label, price_key in _MODES:
            if label == "Normal" or pricing.get(price_key) is not None:
                options.append(label)
            else:
                options.append(f"{label} (Unavailable)")
        self._request_mode_combo["values"] = options

        # If current selection is now unavailable, reset to Normal
        current = self._request_mode_var.get()
        available_labels = [
            o for o in options if "(Unavailable)" not in o
        ]
        if current not in available_labels:
            self._request_mode_var.set("Normal")

    def _on_key_changed(self, event: Any = None) -> None:
        """Handle key selection change — filter Models by provider.

        After filtering the model list, the default model for the selected
        key is applied automatically (if one was set via "Set as Default"
        in the Available Models window).
        """
        provider, name = self._parse_key_selection()
        if not provider:
            return

        # Save key selection to manifest
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            save_nested_text_field(mgr, "RequestOptions", "ApiKeyProvider", provider)
            save_nested_text_field(mgr, "RequestOptions", "ApiKeyName", name)

        # Filter models to the selected provider
        self._filter_models_by_provider(provider)

        # Auto-set the default model for this key (if configured)
        try:
            from CherryAI.functions.api_config import get_default_model
            default_model = get_default_model(provider, name)
            if default_model:
                values = list(self._model_combo["values"])
                if default_model in values:
                    self._model_var.set(default_model)
        except Exception:
            pass

    def _filter_models_by_provider(self, provider: str) -> None:
        """Update Model combobox to show only models for *provider*.

        Uses model_registry to look up models for the registry-ID that
        corresponds to the API.ini provider key (e.g. gemini → google).
        For local providers (lmstudio, local, ollama), queries the server
        directly for available models.
        Applies the saved capability filters from the Available Models
        window (Structured Output, Batch, Thinking).
        """
        _LOCAL_PROVIDERS = ("local", "lmstudio", "ollama")
        is_local = provider.lower() in _LOCAL_PROVIDERS

        # For local providers, try to discover models from the server
        if is_local:
            try:
                from CherryAI.functions.local_llm import discover_models
                from CherryAI.functions.api_config import PROVIDER_BASE_URLS
                base_url = PROVIDER_BASE_URLS.get(provider.lower(), "")
                if base_url:
                    server_models = discover_models(base_url, timeout=5.0)
                    model_ids = [m.id for m in server_models if m.id]
                    if model_ids:
                        values = ["Mock Translation"] + model_ids
                        self._model_combo["values"] = values
                        current = self._model_var.get()
                        if current not in values:
                            self._model_var.set(
                                values[1] if len(values) > 1 else values[0]
                            )
                        return
            except Exception:
                pass
            # Fallback for local: generic model options
            values = ["Mock Translation", "local-model"]
            self._model_combo["values"] = values
            current = self._model_var.get()
            if current not in values:
                self._model_var.set(values[1])
            return

        registry_id = self._KEY_PROVIDER_TO_REGISTRY.get(provider, provider)

        try:
            from CherryAI.functions.model_registry import (
                get_provider_models,
            )
            from CherryAI.functions.api_config import get_api_setting
            all_models = get_provider_models(registry_id)
        except Exception:
            all_models = []

        # Apply capability filters (saved in API.ini by Available Models)
        try:
            filter_struct = get_api_setting("filter_structured", "1") == "1"
            filter_batch = get_api_setting("filter_batch", "0") == "1"
            filter_thinking = get_api_setting("filter_thinking", "0") == "1"
        except Exception:
            filter_struct = True
            filter_batch = False
            filter_thinking = False

        filtered_ids: list[str] = []
        for m in all_models:
            if filter_struct and not m.structured_output:
                continue
            if filter_batch and not m.batch_mode:
                continue
            if filter_thinking and not m.thinking:
                continue
            filtered_ids.append(m.model_id)

        if filtered_ids:
            values = ["Mock Translation"] + filtered_ids
        elif all_models:
            # Filters excluded everything — fall back to all provider models
            values = ["Mock Translation"] + [m.model_id for m in all_models]
        else:
            # Fallback: show all models
            values = self.MODEL_OPTIONS

        self._model_combo["values"] = values

        # If current model is not in the new list, reset to first real model
        current = self._model_var.get()
        if current not in values:
            default_model = values[1] if len(values) > 1 else values[0]
            self._model_var.set(default_model)

        # Refresh request mode availability for the new model set
        self._refresh_request_mode_options()

    def _on_line_by_line_toggle(self) -> None:
        """Handle line-by-line mode toggle.
        
        Enables/disables the context lines spinbox based on mode state.
        """
        enabled = self._line_by_line_var.get()
        state = "normal" if enabled else "disabled"
        self._context_spin.configure(state=state)
        
        if enabled:
            # Warn that this is slower
            logger.info("Line-by-line mode enabled - translates each line individually")

    def get_translated_lines(self) -> List[str]:
        """Get list of translated lines.

        Returns:
            List of translated text.
        """
        return [line.translated for line in self._lines]

    def get_translation_status(self) -> Dict[str, int]:
        """Get translation status counts.

        Returns:
            Dict with completed, failed, pending counts.
        """
        return {
            "completed": sum(1 for l in self._lines if l.status == LineStatus.COMPLETED),
            "failed": sum(1 for l in self._lines if l.status == LineStatus.FAILED),
            "pending": sum(1 for l in self._lines if l.status == LineStatus.PENDING),
            "skipped": sum(1 for l in self._lines if l.status == LineStatus.SKIPPED),
        }

    # ------------------------------------------------------------------
    # Quick-access buttons for Global Options dialogs
    # ------------------------------------------------------------------

    def _open_model_settings(self) -> None:
        """Open the Global Options dialog at the Model Settings section."""
        try:
            from CherryAI.gui.dialogs.global_options import (
                GlobalOptionsDialog, OptionSection,
            )
            go = getattr(self.session, "global_options", None)
            if go is None:
                from CherryAI.gui.dialogs.global_options import GlobalOptions
                go = GlobalOptions.load_from_ini()

            def _on_save(options):
                self.session.global_options = options
                self._sync_from_global_options()

            dlg = GlobalOptionsDialog(
                self.winfo_toplevel(),
                initial_options=go,
                on_save=_on_save,
            )
            dlg._show_panel(OptionSection.REQUEST)
        except Exception:
            logger.debug("Could not open Model Settings dialog", exc_info=True)

    def _open_translation_options(self) -> None:
        """Open the Global Options dialog at the Translation Options section."""
        try:
            from CherryAI.gui.dialogs.global_options import (
                GlobalOptionsDialog, OptionSection,
            )
            go = getattr(self.session, "global_options", None)
            if go is None:
                from CherryAI.gui.dialogs.global_options import GlobalOptions
                go = GlobalOptions.load_from_ini()

            def _on_save(options):
                self.session.global_options = options
                self._sync_from_global_options()

            dlg = GlobalOptionsDialog(
                self.winfo_toplevel(),
                initial_options=go,
                on_save=_on_save,
            )
            dlg._show_panel(OptionSection.TRANSLATION)
        except Exception:
            logger.debug(
                "Could not open Translation Options dialog", exc_info=True,
            )
