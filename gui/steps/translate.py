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


@dataclass
class TranslatableLine:
    """A single translatable line with status."""

    idx: int
    original: str
    preprocessed: str
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

    # Model options for dropdown
    MODEL_OPTIONS = [
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

    # Retry strategy options - from prompt_adapter
    RETRY_STRATEGIES = [
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
        """Build the lines table view."""
        # Define columns
        columns = [
            ColumnDef(key="idx", title="#", width=50, anchor="center"),
            ColumnDef(key="status", title="Status", width=80, anchor="center"),
            ColumnDef(key="original", title="Original", width=200),
            ColumnDef(key="preprocessed", title="Preprocessed", width=200),
            ColumnDef(key="translated", title="Translated", width=200),
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

        # Enable mousewheel scrolling
        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

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

        # Max retries
        retries_frame = ttk.Frame(frame)
        retries_frame.pack(fill="x", pady=2)

        ttk.Label(retries_frame, text="Max Retries:").pack(side="left")
        self._retries_var = tk.IntVar(value=self._translation_options.max_retries)
        self._retries_spin = ttk.Spinbox(
            retries_frame,
            from_=1,
            to=10,
            textvariable=self._retries_var,
            width=6,
        )
        self._retries_spin.pack(side="right")

        # Cache enabled
        cache_frame = ttk.Frame(frame)
        cache_frame.pack(fill="x", pady=2)

        self._cache_var = tk.BooleanVar(value=self._translation_options.cache_enabled)
        ttk.Checkbutton(
            cache_frame,
            text="Enable Request Caching",
            variable=self._cache_var,
        ).pack(side="left")

        # Separator before advanced options
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # Line-by-line mode
        lbl_frame = ttk.Frame(frame)
        lbl_frame.pack(fill="x", pady=2)

        self._line_by_line_var = tk.BooleanVar(value=self._translation_options.line_by_line)
        ttk.Checkbutton(
            lbl_frame,
            text="Line-by-Line Mode",
            variable=self._line_by_line_var,
            command=self._on_line_by_line_toggle,
        ).pack(side="left")

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

        # Thinking mode (for Claude models)
        thinking_frame = ttk.Frame(frame)
        thinking_frame.pack(fill="x", pady=2)

        self._thinking_var = tk.BooleanVar(value=self._translation_options.thinking_enabled)
        ttk.Checkbutton(
            thinking_frame,
            text="Extended Thinking (Claude)",
            variable=self._thinking_var,
            command=self._on_thinking_toggle,
        ).pack(side="left")

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

        # Help text for advanced options
        ttk.Label(
            frame,
            text="(Line-by-line translates individually; Thinking uses Claude's extended reasoning)",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", pady=(5, 0))

    def _build_prompt_editor(self, parent: ttk.Frame) -> None:
        """Build prompt editor panel with preview capability.
        
        Note: Glossary and Conditional Prompts have been moved to their
        dedicated management locations (Information step for glossary,
        separate conditional prompts dialog).
        """
        frame = ttk.LabelFrame(parent, text="Prompt Editor", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # Style preset with preview button
        style_frame = ttk.Frame(frame)
        style_frame.pack(fill="x", pady=2)

        ttk.Label(style_frame, text="Style Preset:").pack(side="left")
        ttk.Button(
            style_frame,
            text="👁 Preview",
            command=self._show_prompt_preview,
            width=10,
        ).pack(side="right", padx=(5, 0))
        self._style_var = tk.StringVar(value="")
        self._style_entry = ttk.Entry(
            style_frame,
            textvariable=self._style_var,
            width=20,
        )
        self._style_entry.pack(side="right")

        # Summary/context
        ttk.Label(frame, text="Game Summary:").pack(anchor="w", pady=(5, 0))
        self._summary_text = scrolledtext.ScrolledText(
            frame,
            height=4,
            wrap="word",
            font=("TkDefaultFont", 9),
        )
        self._summary_text.pack(fill="x", pady=2)

        # Info about managed sections
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill="x", pady=(5, 2))
        
        ttk.Label(
            info_frame,
            text="📋 Glossary and Character Notes: Edit in Information step",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(anchor="w")

        # Ban tokens
        ban_frame = ttk.Frame(frame)
        ban_frame.pack(fill="x", pady=(5, 2))

        ttk.Label(ban_frame, text="Ban Tokens:").pack(side="left")
        self._ban_var = tk.StringVar(value="")
        self._ban_entry = ttk.Entry(
            ban_frame,
            textvariable=self._ban_var,
            width=25,
        )
        self._ban_entry.pack(side="right")

        # Help text
        ttk.Label(
            frame,
            text="(Comma-separated: em_dash, smart_quotes, etc.)",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(anchor="e")

        # Initialize removed fields as None for compatibility
        self._glossary_text = None
        self._conditional_text = None

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
        """Refresh lines from previous steps."""
        original, preprocessed = self._get_lines_from_previous_steps()

        if not original:
            self._status_label.configure(text="No lines loaded")
            return

        # Create TranslatableLine objects
        self._lines = []
        for idx, (orig, prep) in enumerate(zip(original, preprocessed)):
            line = TranslatableLine(
                idx=idx,
                original=orig,
                preprocessed=prep,
            )
            self._lines.append(line)

        # Update table
        self._update_lines_table()

        # Update status
        self._status_label.configure(text=f"{len(self._lines)} lines ready")

    def _update_lines_table(self) -> None:
        """Update the lines table with current data."""
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

            row = TableRow(
                id=line.idx,
                values={
                    "idx": str(line.idx + 1),
                    "status": status_display,
                    "original": line.original[:100] + "..." if len(line.original) > 100 else line.original,
                    "preprocessed": line.preprocessed[:100] + "..." if len(line.preprocessed) > 100 else line.preprocessed,
                    "translated": line.translated[:100] + "..." if len(line.translated) > 100 else line.translated,
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

        # Start translation thread
        self._translation_thread = threading.Thread(
            target=self._do_translation,
            daemon=True,
        )
        self._translation_thread.start()

    def _do_translation(self) -> None:
        """Perform translation in background thread."""
        try:
            self._log_progress("Starting translation...")

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

        Args:
            chunk: Lines to translate.

        Returns:
            List of translations.
        """
        if self._api_client is None:
            # Simulation mode
            time.sleep(0.5)  # Simulate API delay
            return [f"[Translated] {line.preprocessed}" for line in chunk]

        # Build prompt from prompt editor
        prompt_parts = self._get_prompt_parts()
        system_prompt = ""

        if prompt_parts["summary"]:
            system_prompt += f"Game Context:\n{prompt_parts['summary']}\n\n"

        if prompt_parts["glossary"]:
            system_prompt += f"Glossary:\n{prompt_parts['glossary']}\n\n"

        if prompt_parts["conditional"]:
            system_prompt += f"Special Instructions:\n{prompt_parts['conditional']}\n\n"

        # Get preprocessed text for translation
        lines_to_translate = [line.preprocessed for line in chunk]

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
            from CherryAI.gui.steps.estimate import estimate_cost
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
        # Refresh lines from previous steps
        if not self._lines:
            self._refresh_lines()

        # Load prompt data from config if available
        self._load_prompt_data()

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
