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
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
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
    - Model and API settings
    - Retry and rate limiting
    - Style and token bans
    - Line-by-line mode for individual line translation
    - Thinking mode for extended reasoning (Claude models)
    - Edit before translation (Task 33.1)
    """

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
    # Edit before translation (Task 33.1)
    edit_before_translation: bool = False  # Show edit dialog before API call
    # Skip already translated lines (Task 47.9)
    skip_already_translated: bool = False  # Skip lines with existing tl field


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

        # Make modal
        self.grab_set()
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
    MODEL_OPTIONS = [
        "Mock Translation",
        "gpt-4.1",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "claude-3-5-sonnet",
        "claude-3-opus",
        "claude-3-haiku",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]

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
        """Build per-request options panel."""
        frame = ttk.LabelFrame(parent, text="Request Options", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # Model selection
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

        # Temperature
        temp_frame = ttk.Frame(frame)
        temp_frame.pack(fill="x", pady=2)

        ttk.Label(temp_frame, text="Temperature:").pack(side="left")
        self._temp_var = tk.DoubleVar(value=self._translation_options.temperature)
        self._temp_spin = ttk.Spinbox(
            temp_frame,
            from_=0.0,
            to=2.0,
            increment=0.1,
            textvariable=self._temp_var,
            width=6,
        )
        self._temp_spin.pack(side="right")

        # Bind temperature via trace (DoubleVar not directly supported)
        self._temp_var.trace_add("write", lambda *_: self._save_temperature_to_manifest())

        # Chunk size
        chunk_frame = ttk.Frame(frame)
        chunk_frame.pack(fill="x", pady=2)

        ttk.Label(chunk_frame, text="Lines/Chunk:").pack(side="left")
        self._chunk_var = tk.IntVar(value=self._translation_options.chunk_size)
        self._chunk_spin = ttk.Spinbox(
            chunk_frame,
            from_=5,
            to=100,
            textvariable=self._chunk_var,
            width=6,
        )
        self._chunk_spin.pack(side="right")

        # Bind chunk size to manifest
        self._manifest_bindings.append(
            bind_spinbox_to_field(
                spinbox=self._chunk_spin,
                var=self._chunk_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="LinesPerChunk",
                min_val=5,
                max_val=100,
                default=30,
                parent_key="RequestOptions",
            )
        )

        # Retry strategy
        retry_frame = ttk.Frame(frame)
        retry_frame.pack(fill="x", pady=2)

        ttk.Label(retry_frame, text="Retry Strategy:").pack(side="left")
        self._retry_var = tk.StringVar(value=self._translation_options.retry_strategy)
        self._retry_combo = ttk.Combobox(
            retry_frame,
            textvariable=self._retry_var,
            values=[name for name, _ in self.RETRY_STRATEGIES],
            state="readonly",
            width=15,
        )
        self._retry_combo.pack(side="right")

        # Bind retry strategy to manifest
        self._manifest_bindings.append(
            bind_combobox_to_field(
                combobox=self._retry_combo,
                var=self._retry_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="RetryStrategy",
                options=[name for name, _ in self.RETRY_STRATEGIES],
                default="batch",
                parent_key="RequestOptions",
            )
        )

        # Max retries
        retries_frame = ttk.Frame(frame)
        retries_frame.pack(fill="x", pady=2)

        ttk.Label(retries_frame, text="Max Retries:").pack(side="left")
        self._retries_var = tk.IntVar(value=self._translation_options.max_retries)
        self._retries_spin = ttk.Spinbox(
            retries_frame,
            from_=0,
            to=10,
            textvariable=self._retries_var,
            width=6,
        )
        self._retries_spin.pack(side="right")

        # Bind max retries to manifest
        self._manifest_bindings.append(
            bind_spinbox_to_field(
                spinbox=self._retries_spin,
                var=self._retries_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="MaxRetries",
                min_val=0,
                max_val=10,
                default=3,
                parent_key="RequestOptions",
            )
        )

        # Cache enabled
        cache_frame = ttk.Frame(frame)
        cache_frame.pack(fill="x", pady=2)

        self._cache_var = tk.BooleanVar(value=self._translation_options.cache_enabled)
        cache_cb = ttk.Checkbutton(
            cache_frame,
            text="Enable Request Caching",
            variable=self._cache_var,
        )
        cache_cb.pack(side="left")

        # Bind cache enabled to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=cache_cb,
                var=self._cache_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="EnableRequestCaching",
                default=False,
                parent_key="RequestOptions",
            )
        )

        # Edit before translation (Task 33.1)
        edit_frame = ttk.Frame(frame)
        edit_frame.pack(fill="x", pady=2)

        self._edit_before_var = tk.BooleanVar(
            value=self._translation_options.edit_before_translation
        )
        edit_cb = ttk.Checkbutton(
            edit_frame,
            text="Edit Before Translation",
            variable=self._edit_before_var,
        )
        edit_cb.pack(side="left")

        # Bind edit before translation to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=edit_cb,
                var=self._edit_before_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="EditBeforeTranslation",
                default=False,
                parent_key="RequestOptions",
            )
        )

        # Skip Already Translated (Task 47.9)
        skip_translated_frame = ttk.Frame(frame)
        skip_translated_frame.pack(fill="x", pady=2)

        self._skip_translated_var = tk.BooleanVar(
            value=self._translation_options.skip_already_translated
        )
        skip_translated_cb = ttk.Checkbutton(
            skip_translated_frame,
            text="Skip Already Translated",
            variable=self._skip_translated_var,
        )
        skip_translated_cb.pack(side="left")

        # Bind skip already translated to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=skip_translated_cb,
                var=self._skip_translated_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="SkipAlreadyTranslated",
                default=False,
                parent_key="RequestOptions",
            )
        )

        # Skip Non-Source Language (Task 43.13)
        skip_lang_frame = ttk.Frame(frame)
        skip_lang_frame.pack(fill="x", pady=2)

        self._skip_non_source_var = tk.BooleanVar(value=False)
        skip_lang_cb = ttk.Checkbutton(
            skip_lang_frame,
            text="Skip Non-Source Language Lines",
            variable=self._skip_non_source_var,
        )
        skip_lang_cb.pack(side="left")

        # Bind skip non-source to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=skip_lang_cb,
                var=self._skip_non_source_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="SkipNonSourceLanguage",
                default=False,
                parent_key="RequestOptions",
            )
        )

        # Separator before advanced options
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # Line-by-line mode
        lbl_frame = ttk.Frame(frame)
        lbl_frame.pack(fill="x", pady=2)

        self._line_by_line_var = tk.BooleanVar(value=self._translation_options.line_by_line)
        lbl_cb = ttk.Checkbutton(
            lbl_frame,
            text="Line-by-Line Mode",
            variable=self._line_by_line_var,
            command=self._on_line_by_line_toggle,
        )
        lbl_cb.pack(side="left")

        # Bind line-by-line to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=lbl_cb,
                var=self._line_by_line_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="LineByLineMode",
                default=False,
                parent_key="RequestOptions",
            )
        )

        # Context lines (enabled only when line-by-line is on)
        context_frame = ttk.Frame(frame)
        context_frame.pack(fill="x", pady=2)

        ttk.Label(context_frame, text="Context Lines:").pack(side="left", padx=(20, 0))
        self._context_lines_var = tk.IntVar(value=self._translation_options.context_lines)
        self._context_spin = ttk.Spinbox(
            context_frame,
            from_=0,
            to=5,
            textvariable=self._context_lines_var,
            width=6,
            state="disabled" if not self._translation_options.line_by_line else "normal",
        )
        self._context_spin.pack(side="right")

        # Bind context lines to manifest
        self._manifest_bindings.append(
            bind_spinbox_to_field(
                spinbox=self._context_spin,
                var=self._context_lines_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="ContextLines",
                min_val=0,
                max_val=5,
                default=1,
                parent_key="RequestOptions",
            )
        )

        # Thinking mode (for Claude models)
        thinking_frame = ttk.Frame(frame)
        thinking_frame.pack(fill="x", pady=2)

        self._thinking_var = tk.BooleanVar(value=self._translation_options.thinking_enabled)
        thinking_cb = ttk.Checkbutton(
            thinking_frame,
            text="Extended Thinking (Claude)",
            variable=self._thinking_var,
            command=self._on_thinking_toggle,
        )
        thinking_cb.pack(side="left")

        # Bind thinking to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=thinking_cb,
                var=self._thinking_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="Thinking",
                default=False,
                parent_key="RequestOptions",
            )
        )

        # Thinking budget
        budget_frame = ttk.Frame(frame)
        budget_frame.pack(fill="x", pady=2)

        ttk.Label(budget_frame, text="Thinking Budget:").pack(side="left", padx=(20, 0))
        self._thinking_budget_var = tk.IntVar(value=self._translation_options.thinking_budget)
        self._budget_spin = ttk.Spinbox(
            budget_frame,
            from_=1000,
            to=100000,
            increment=1000,
            textvariable=self._thinking_budget_var,
            width=8,
            state="disabled" if not self._translation_options.thinking_enabled else "normal",
        )
        self._budget_spin.pack(side="right")

        # Bind thinking budget to manifest
        self._manifest_bindings.append(
            bind_spinbox_to_field(
                spinbox=self._budget_spin,
                var=self._thinking_budget_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="ThinkingBudget",
                min_val=1000,
                max_val=100000,
                default=10000,
                parent_key="RequestOptions",
            )
        )

        # Help text for advanced options
        ttk.Label(
            frame,
            text="(Line-by-line translates individually; Thinking uses Claude's extended reasoning)",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", pady=(5, 0))

    def _build_prompt_editor(self, parent: ttk.Frame) -> None:
        """Build prompt editor panel (Task 43.11 redesign).

        Simplified to a prompt preview button (read-only) and a separate
        Ban Tokens section.  Style Preset and Game Summary are now managed
        in the Information step.
        """
        frame = ttk.LabelFrame(parent, text="Prompt Editor", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # Preview button — shows the fully-constructed prompt read-only
        preview_row = ttk.Frame(frame)
        preview_row.pack(fill="x", pady=2)

        ttk.Label(
            preview_row,
            text="Prompt is built from Information step data (glossary, summary, style).",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(side="left")
        ttk.Button(
            preview_row,
            text="👁 Preview Prompt",
            command=self._show_prompt_preview,
            width=15,
        ).pack(side="right")

        # Ban Tokens section (Task 43.11)
        ban_lf = ttk.LabelFrame(frame, text="Ban Tokens", padding=5)
        ban_lf.pack(fill="x", pady=(10, 0))

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

        # Hidden summary text for backward compat (loaded by _load_prompt_data)
        self._summary_text = scrolledtext.ScrolledText(
            frame, height=0, wrap="word",
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
        """Get original and preprocessed lines from previous steps.

        Returns:
            Tuple of (original_lines, preprocessed_lines).
        """
        original: List[str] = []
        preprocessed: List[str] = []

        try:
            # Get from input step (step 0)
            app = self.winfo_toplevel()
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 0:
                input_step = app._step_tabs[0]
                if hasattr(input_step, "get_loaded_files"):
                    loaded_files = input_step.get_loaded_files()
                    for lf in loaded_files:
                        if hasattr(lf, "lines"):
                            original.extend(lf.lines)

            # Get preprocessed from step 3
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 3:
                prep_data = self.session.get_step(3).data
                if "preprocessed_lines" in prep_data:
                    preprocessed = prep_data["preprocessed_lines"]

            # Fallback: use original if no preprocessed data
            if not preprocessed and original:
                preprocessed = original[:]

        except Exception as e:
            logger.debug("Error getting lines: %s", e)

        # Final fallback from step data
        if not original:
            input_data = self.session.get_step(0).data
            if "all_lines" in input_data:
                original = input_data["all_lines"]
            if not preprocessed:
                preprocessed = original[:]

        return original, preprocessed

    def _refresh_lines(self) -> None:
        """Refresh lines from previous steps.

        TASK 43.2: Optimized to avoid per-line manifest lookups for
        edited_prepro when the manifest has no edit data.
        """
        original, preprocessed = self._get_lines_from_previous_steps()

        if not original:
            self._status_label.configure(text="No lines loaded")
            return

        # TASK 43.2: Batch-read edited_prepro from manifest
        edit_map: dict[int, str] = {}
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            lines_section = mgr._manifest_data.get("Lines", {})
            for idx_str, line_data in lines_section.items():
                if isinstance(line_data, dict):
                    ep = line_data.get("edited_prepro", "")
                    if ep:
                        try:
                            edit_map[int(idx_str)] = ep
                        except (ValueError, TypeError):
                            pass

        # Create TranslatableLine objects
        self._lines = [
            TranslatableLine(
                idx=idx,
                original=orig,
                preprocessed=prep,
                edited_prepro=edit_map.get(idx, ""),
            )
            for idx, (orig, prep) in enumerate(zip(original, preprocessed))
        ]

        # Update table
        self._update_lines_table()

        # Update status
        self._status_label.configure(text=f"{len(self._lines)} lines ready")

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
        return TranslationOptions(
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
            edit_before_translation=self._edit_before_var.get(),
        )

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

        # Initialize progress
        self._progress = TranslationProgress(
            total_lines=len(pending_lines),
            total_chunks=math.ceil(len(pending_lines) / self._translation_options.chunk_size),
            start_time=time.time(),
        )

        # Reset state
        self._cancel_requested = False
        self._pause_requested = False
        self._translation_state = TranslationState.RUNNING

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
                    from CherryAI.functions.api_client import APIClient, APIConfig, TranslationError
                    self._api_client = APIClient(enable_api_log=True)

                    # Apply options
                    self._api_client.config.model = self._translation_options.model
                    self._api_client.config.temperature = self._translation_options.temperature
                    self._api_client.config.chunk_size = self._translation_options.chunk_size
                    self._api_client.config.retries = self._translation_options.max_retries
                    self._api_client.config.cache_enabled = self._translation_options.cache_enabled

                    if self._translation_options.banned_tokens:
                        self._api_client.configure_logit_bias(
                            enabled=True,
                            banned_tokens=self._translation_options.banned_tokens,
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

            # Process each chunk
            for chunk_idx, chunk in enumerate(chunks):
                if self._cancel_requested:
                    self._log_progress("Translation cancelled by user")
                    break

                # Wait while paused
                while self._pause_requested:
                    time.sleep(0.1)
                    if self._cancel_requested:
                        break

                if self._cancel_requested:
                    break

                self._progress.current_chunk = chunk_idx + 1
                self._log_progress(f"Processing chunk {chunk_idx + 1}/{len(chunks)}")

                # Mark lines as translating
                for line in chunk:
                    line.status = LineStatus.TRANSLATING
                    line.chunk_id = chunk_idx

                self.after(0, self._update_lines_table)

                # Translate chunk
                try:
                    translations = self._translate_chunk(chunk)

                    # Apply translations
                    for line, translation in zip(chunk, translations):
                        line.translated = translation
                        line.status = LineStatus.COMPLETED
                        self._progress.translated_lines += 1

                except Exception as e:
                    self._log_progress(f"Chunk {chunk_idx + 1} failed: {e}")

                    # Handle failed lines using prompt_adapter retry handler
                    failed_indices = [line.idx for line in chunk]
                    original_lines = [line.preprocessed for line in chunk]
                    translations = [""] * len(chunk)

                    # Create retry config from options
                    retry_config, _ = create_retry_config(
                        strategy=self._translation_options.retry_strategy,
                        max_retries=self._translation_options.max_retries,
                        context_lines=2,
                    )

                    # Build translate function for retry handler
                    def translate_fn(lines: List[str], prompt: str | None) -> List[str]:
                        if self._api_client is None:
                            return [f"[Retry] {line}" for line in lines]
                        return self._api_client.translate_batch(lines, system_prompt=prompt or "")

                    # Attempt retry via adapter
                    retry_result, method = handle_failed_lines(
                        failed_indices=list(range(len(chunk))),
                        original_lines=original_lines,
                        translations=translations,
                        translate_fn=translate_fn,
                        config=retry_config,
                        system_prompt=self._get_prompt_parts().get("summary", ""),
                    )

                    # Apply retry results
                    for i, line in enumerate(chunk):
                        if i < len(retry_result.line_results):
                            result = retry_result.line_results[i]
                            if result.success:
                                line.translated = result.translation
                                line.status = LineStatus.COMPLETED
                                self._progress.translated_lines += 1
                            else:
                                line.status = LineStatus.FAILED
                                line.error_message = result.error_message or str(e)
                                self._progress.failed_lines += 1
                        else:
                            line.status = LineStatus.FAILED
                            line.error_message = str(e)
                            self._progress.failed_lines += 1

                    self._log_progress(
                        f"Retry complete: {retry_result.successful_count} recovered, "
                        f"{retry_result.failed_count} failed ({method})"
                    )

                # Update progress
                self._update_progress_display()
                self.after(0, self._update_lines_table)

            # Translation complete
            if self._cancel_requested:
                self._translation_state = TranslationState.CANCELLED
            elif self._progress.failed_lines > 0:
                self._translation_state = TranslationState.COMPLETED
                self._log_progress(f"Translation completed with {self._progress.failed_lines} failures")
            else:
                self._translation_state = TranslationState.COMPLETED
                self._log_progress("Translation completed successfully!")

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

        Args:
            lines: Pending lines to filter.

        Returns:
            Lines that should still be translated.
        """
        from CherryAI.functions.analysis import detect_line_script

        # Determine expected source script from manifest
        source_lang = "Japanese"
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            source_lang = mgr._manifest_data.get("SourceLanguage", "Japanese")

        expected_script = self._LANG_SCRIPT_MAP.get(source_lang)
        if expected_script is None:
            # Unknown language — can't filter, return all
            return lines

        kept: list[TranslatableLine] = []
        skipped = 0
        for line in lines:
            text = line.preprocessed or line.original
            script = detect_line_script(text)
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

    def _build_chunks(self, lines: List[TranslatableLine]) -> List[List[TranslatableLine]]:
        """Build chunks from lines.

        Args:
            lines: Lines to chunk.

        Returns:
            List of chunks.
        """
        chunks: List[List[TranslatableLine]] = []
        chunk_size = self._translation_options.chunk_size

        for i in range(0, len(lines), chunk_size):
            chunk = lines[i:i + chunk_size]
            chunks.append(chunk)

        return chunks

    def _translate_chunk(self, chunk: List[TranslatableLine]) -> List[str]:
        """Translate a chunk of lines.

        TASK 43.5: Routes to MockTranslator when mock model selected.

        Args:
            chunk: Lines to translate.

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

        # Build prompt from prompt editor
        prompt_parts = self._get_prompt_parts()
        system_prompt = ""

        if prompt_parts["summary"]:
            system_prompt += f"Game Context:\n{prompt_parts['summary']}\n\n"

        if prompt_parts["glossary"]:
            system_prompt += f"Glossary:\n{prompt_parts['glossary']}\n\n"

        if prompt_parts["conditional"]:
            system_prompt += f"Special Instructions:\n{prompt_parts['conditional']}\n\n"

        # Get text for translation - use edited_prepro if available (Task 33.1)
        lines_to_translate = [
            line.edited_prepro if line.edited_prepro else line.preprocessed
            for line in chunk
        ]

        # Call API
        translations = self._api_client.translate_batch(
            lines_to_translate,
            system_prompt=system_prompt if system_prompt else None,
        )

        # Update token count
        if hasattr(self._api_client, "_total_prompt_tokens"):
            self._progress.tokens_used = (
                self._api_client._total_prompt_tokens +
                self._api_client._total_completion_tokens
            )

        return translations

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
        """Refresh model dropdown from Global Options providers (Task 43.6).

        Falls back to hardcoded MODEL_OPTIONS when no providers are
        configured or session/global_options is unavailable.
        """
        try:
            go = getattr(self.session, "global_options", None)
            if go is not None and hasattr(go, "get_model_list"):
                models = go.get_model_list()
                if len(models) > 1:  # More than just Mock Translation
                    self._model_combo["values"] = models
                    return
        except Exception:
            pass
        # Fallback: use hardcoded list
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

        # Task 43.9: Rolling context from Global Options
        if hasattr(go, "request"):
            self._context_lines_var.set(go.request.rolling_context_lines)

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
        }

    def _load_prompt_data(self) -> None:
        """Load prompt data from config files using prompt_adapter."""
        try:
            from pathlib import Path
            config_dir = Path(__file__).parent.parent.parent / "config"

            # Load game summary via adapter
            summary, _ = get_game_summary(str(config_dir / "game_summary.txt"))
            if summary:
                self._summary_text.delete("1.0", "end")
                self._summary_text.insert("1.0", summary)

            # Load translation style via adapter
            style, _ = get_translation_style(
                str(config_dir / "translation_style.txt"),
                config_dir,
            )
            if style:
                self._style_var.set(style[:100])  # Truncate for entry field

        except Exception as e:
            logger.debug("Error loading prompt data: %s", e)

    def _show_prompt_preview(self) -> None:
        """Show prompt preview dialog with complete system prompt."""
        # Get sample lines for conditional prompt detection
        sample_lines = []
        if self._lines:
            sample_lines = [l.preprocessed for l in self._lines[:10]]

        # Get glossary text (may be None if moved to Information step)
        glossary = ""
        if self._glossary_text is not None:
            glossary = self._glossary_text.get("1.0", "end-1c").strip()

        # Build preview
        preview, _ = build_prompt_preview(
            lines=sample_lines,
            game_summary=self._summary_text.get("1.0", "end-1c").strip(),
            glossary_text=glossary,
            style_text=self._style_var.get(),
        )

        # Show in a dialog
        self._show_preview_dialog(preview)

    def _show_preview_dialog(self, preview: PromptPreviewView) -> None:
        """Show prompt preview in a dialog window.

        Args:
            preview: The preview data to display.
        """
        dialog = tk.Toplevel(self)
        dialog.title("Prompt Preview")
        dialog.geometry("700x500")
        dialog.transient(self)  # type: ignore[call-overload]

        # Main frame
        main = ttk.Frame(dialog, padding=10)
        main.pack(fill="both", expand=True)

        # Token count header
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 10))

        ttk.Label(
            header,
            text=f"Estimated Tokens: {preview.total_tokens}",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left")

        # Breakdown
        breakdown_text = " | ".join(
            f"{k}: {v}" for k, v in preview.breakdown.items()
        )
        ttk.Label(
            header,
            text=breakdown_text,
            foreground=THEME.text_secondary,
        ).pack(side="right")

        # System prompt display
        ttk.Label(main, text="System Prompt:").pack(anchor="w")
        text_widget = scrolledtext.ScrolledText(
            main,
            wrap="word",
            font=("Consolas", 9),
        )
        text_widget.pack(fill="both", expand=True, pady=5)
        text_widget.insert("1.0", preview.system_prompt)
        text_widget.configure(state="disabled")

        # Close button
        ttk.Button(
            main,
            text="Close",
            command=dialog.destroy,
        ).pack(pady=10)

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

    def _on_thinking_toggle(self) -> None:
        """Handle thinking mode toggle.
        
        Enables/disables the thinking budget spinbox based on mode state.
        """
        enabled = self._thinking_var.get()
        state = "normal" if enabled else "disabled"
        self._budget_spin.configure(state=state)
        
        if enabled:
            # Check if model is Claude
            model = self._model_var.get().lower()
            if "claude" not in model:
                messagebox.showwarning(
                    "Thinking Mode",
                    "Extended thinking is optimized for Claude models.\n"
                    "Other models may not benefit from this setting.",
                )

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
