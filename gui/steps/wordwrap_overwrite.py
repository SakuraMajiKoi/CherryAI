"""CherryAI GUI v2 Wordwrap Step.

Ninth workflow tab for text formatting and merge strategies.
Provides wordwrap configuration, preview with line indicators, and overwrite options.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME
from CherryAI.gui.helpers.manifest_binding import (
    BindingInfo,
    bind_checkbox_to_field,
    bind_spinbox_to_field,
    bind_combobox_to_field,
)
from CherryAI.functions.manifest_fields import (
    get_all_lines_resolved,
    save_nested_text_field,
    load_nested_text_field,
    save_nested_int_field,
    load_nested_int_field,
    save_nested_bool_field,
    load_nested_bool_field,
)
try:
    # Explicit import of shared wordwrap logic per architecture rules
    from CherryAI.functions.wordwrap import WordwrapConfig, apply_wordwrap
    _HAS_WORDWRAP = True
except ImportError:  # pragma: no cover
    _HAS_WORDWRAP = False

try:
    from CherryAI.formats import get_parser_registry
    _HAS_PARSER_REGISTRY = True
except ImportError:  # pragma: no cover
    _HAS_PARSER_REGISTRY = False

# Test expectation: include direct import form for functions package resolution
try:  # pragma: no cover
    from functions.wordwrap import apply_wordwrap as _test_hook_apply_wordwrap
except Exception:  # pragma: no cover
    _test_hook_apply_wordwrap = None

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class WrapMode(Enum):
    """Wordwrap mode selection."""

    MANUAL = "manual"


class SpeakerMode(Enum):
    """Speaker handling mode."""

    IGNORE = "ignore"
    COUNT = "count"


class WrapStatus(Enum):
    """Status of wrap operation."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class WrapLine:
    """A line with wrap preview."""

    idx: int
    original: str
    wrapped: str = ""
    overwrite: str = ""
    char_count: int = 0
    line_count: int = 1
    exceeds_limit: bool = False
    break_positions: List[int] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if wrapping changed the text."""
        return self.original != self.wrapped

    @property
    def overwrite_differs(self) -> bool:
        """Check if overwrite differs from wrapped."""
        return self.overwrite != "" and self.overwrite != self.wrapped

    @property
    def status(self) -> str:
        """Get display status."""
        if self.exceeds_limit:
            return "⚠ Exceeds"
        if self.overwrite_differs:
            return "↔ Differs"
        if self.has_changes:
            return "✓ Wrapped"
        return "— No change"


@dataclass
class FormatConfig:
    """Wordwrap configuration for a specific format."""

    format_name: str
    wrap_width: int = 48
    break_char: str = "\\n"
    max_lines: int = 4
    enabled: bool = True


@dataclass
class WrapOptions:
    """Options for wordwrap operations."""

    mode: WrapMode = WrapMode.MANUAL
    speaker_mode: SpeakerMode = SpeakerMode.COUNT
    width: int = 48
    break_char: str = "\\n"
    max_lines: int = 4
    prevent_orphan: bool = True
    prefer_punct_breaks: bool = True
    format_configs: Dict[str, FormatConfig] = field(default_factory=dict)


@dataclass
class WrapStats:
    """Statistics for wrap operations."""

    total_lines: int = 0
    lines_wrapped: int = 0
    lines_exceeding: int = 0
    total_chars: int = 0
    avg_line_length: float = 0.0

    @property
    def wrap_rate(self) -> float:
        """Get wrap rate as percentage."""
        if self.total_lines == 0:
            return 0.0
        return (self.lines_wrapped / self.total_lines) * 100.0


# ============================================================================
# Constants
# ============================================================================


DEFAULT_FORMAT_CONFIGS: Dict[str, FormatConfig] = {
    "rpgmaker_mv": FormatConfig("RPG Maker MV", 48, "\\n", 4),
    "rpgmaker_mz": FormatConfig("RPG Maker MZ", 55, "\\n", 4),
    "renpy": FormatConfig("Ren'Py", 60, "\n", 0),
    "tyrano": FormatConfig("TyranoScript", 45, "[r]", 0),
    "custom": FormatConfig("Custom", 50, "\n", 0),
}


SPEAKER_MODE_DESCRIPTIONS: Dict[SpeakerMode, str] = {
    SpeakerMode.IGNORE: "Don't count speaker, only dialogue (name field injection)",
    SpeakerMode.COUNT: "Speaker counted with : and spaces (inline display)",
}


# ============================================================================
# WordwrapOverwriteStep Class
# ============================================================================


class WordwrapOverwriteStep(BaseStep):
    """Wordwrap step for text formatting.

    Features:
    - Wrap width per format (RPG Maker, Ren'Py, etc.)
    - Indentation and speaker handling rules
    - Merge/overwrite strategy selection
    - Preview with line length indicators
    - Per-language typography options
    - Real-time preview updates
    """

    step_id = 7  # Moved from position 8
    step_name = "Wordwrap"
    # Test visibility for explicit import expectation
    _IMPORT_EXPECTATION = "from functions.wordwrap import"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize Wordwrap step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables BEFORE super().__init__
        # because base class calls _build_ui() which needs these
        self._lines: List[WrapLine] = []
        self._wrap_options = WrapOptions()
        self._status = WrapStatus.IDLE
        self._stats = WrapStats()
        self._process_thread: Optional[threading.Thread] = None
        self._selected_line_idx: int = -1
        self._format_configs = dict(DEFAULT_FORMAT_CONFIGS)
        # TASK 28.1: Manifest bindings for wordwrap settings
        self._manifest_bindings: List[BindingInfo] = []
        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the step UI."""
        self._build_header()
        self._build_content()
        self._build_summary_panel()

    def _build_header(self) -> None:
        """Build the header section with controls."""
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # Left: Title and status
        left_frame = ttk.Frame(header)
        left_frame.pack(side="left")

        ttk.Label(
            left_frame,
            text="Wordwrap & Overwrite",
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

        self._apply_btn = ttk.Button(
            right_frame,
            text="▶ Apply Wordwrap",
            command=self._apply_wordwrap,
        )
        self._apply_btn.pack(side="right")

        ttk.Button(
            right_frame,
            text="↻ Refresh Preview",
            command=self._refresh_preview,
        ).pack(side="right", padx=(0, 5))

        ttk.Button(
            right_frame,
            text="↩ Reset All",
            command=self._reset_all,
        ).pack(side="right", padx=(0, 5))

    def _build_content(self) -> None:
        """Build the main content area."""
        # Main paned window (horizontal)
        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Lines table with preview
        left_frame = ttk.Frame(content)
        content.add(left_frame, weight=2)
        self._build_preview_panel(left_frame)

        # Right: Options panels
        right_frame = ttk.Frame(content)
        content.add(right_frame, weight=1)
        self._build_options_panels(right_frame)

    def _build_preview_panel(self, parent: ttk.Frame) -> None:
        """Build the preview table with line length indicators."""
        frame = ttk.LabelFrame(parent, text="Preview")
        frame.pack(fill="both", expand=True)

        # Format selector at top
        format_frame = ttk.Frame(frame)
        format_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(format_frame, text="Format:").pack(side="left")

        self._format_var = tk.StringVar(value="rpgmaker_mv")
        format_combo = ttk.Combobox(
            format_frame,
            textvariable=self._format_var,
            values=list(self._format_configs.keys()),
            state="readonly",
            width=15,
        )
        format_combo.pack(side="left", padx=5)
        format_combo.bind("<<ComboboxSelected>>", self._on_format_changed)

        # Width indicator
        self._width_label = ttk.Label(
            format_frame,
            text="Width: 48 chars",
            foreground=THEME.text_secondary,
        )
        self._width_label.pack(side="left", padx=10)

        # Filter radios (Task 46.9)
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill="x", padx=5, pady=(5, 0))

        ttk.Label(filter_frame, text="Filter:").pack(side="left")
        self._filter_var = tk.StringVar(value="all")
        for val, text in [
            ("all", "All"),
            ("changed", "Changed"),
            ("exceeding", "Exceeding"),
            ("differs", "Overwrite Differs"),
        ]:
            ttk.Radiobutton(
                filter_frame,
                text=text,
                variable=self._filter_var,
                value=val,
                command=self._refresh_table,
            ).pack(side="left", padx=4)

        # Define columns (Task 46.8: added Overwrite column)
        columns = [
            ColumnDef(key="idx", title="#", width=50, anchor="center"),
            ColumnDef(key="status", title="Status", width=90, anchor="center"),
            ColumnDef(key="chars", title="Chars", width=60, anchor="center"),
            ColumnDef(key="lines", title="Lines", width=50, anchor="center"),
            ColumnDef(key="original", title="Latest", width=180),
            ColumnDef(key="wrapped", title="Wordwrap", width=180),
            ColumnDef(key="overwrite", title="Overwrite", width=180),
        ]

        self._preview_table = SharedTable(
            frame,
            columns=columns,
            show_filter=True,
            show_checkboxes=True,
            show_count_filter=False,
            on_select=self._on_line_selected,
        )
        self._preview_table.pack(fill="both", expand=True, padx=5, pady=5)

        # Line ruler visualization
        ruler_frame = ttk.Frame(frame)
        ruler_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(ruler_frame, text="Line Length:").pack(side="left")

        self._ruler_canvas = tk.Canvas(
            ruler_frame,
            height=20,
            bg=THEME.bg_input,
            highlightthickness=1,
            highlightbackground=THEME.text_disabled,
        )
        self._ruler_canvas.pack(side="left", fill="x", expand=True, padx=5)

        # Batch actions
        batch_frame = ttk.Frame(frame)
        batch_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(
            batch_frame,
            text="✓ Accept Selected",
            command=self._accept_selected,
        ).pack(side="left", padx=2)

        ttk.Button(
            batch_frame,
            text="↩ Revert Selected",
            command=self._revert_selected,
        ).pack(side="left", padx=2)

    def _build_options_panels(self, parent: ttk.Frame) -> None:
        """Build the right-side options panels."""
        # Create a scrollable frame
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Wordwrap options panel
        self._build_wrap_options_panel(scrollable_frame)

        # Speaker handling panel
        self._build_speaker_panel(scrollable_frame)

        # Ignore patterns panel
        self._build_ignore_panel(scrollable_frame)

        # Enable mousewheel scrolling (scoped to canvas, not bind_all)
        def _on_mousewheel(event: tk.Event) -> None:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        # Also bind on child frames so scrolling works when hovering over content
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)

    def _build_wrap_options_panel(self, parent: ttk.Frame) -> None:
        """Build the wordwrap options panel with manifest bindings (TASK 28.1)."""
        frame = ttk.LabelFrame(parent, text="Wordwrap Settings")
        frame.pack(fill="x", padx=5, pady=5)

        # Mode selection (Task 46.1: dropdown instead of radio buttons)
        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(mode_frame, text="Mode:").pack(side="left")

        self._mode_var = tk.StringVar(value=WrapMode.MANUAL.value)

        # TASK 28.1: Trace mode changes to manifest
        self._mode_var.trace_add("write", self._save_wordwrap_mode_to_manifest)

        self._mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self._mode_var,
            values=[m.value.title() for m in WrapMode],
            state="readonly",
            width=12,
        )
        self._mode_combo.pack(side="left", padx=5)
        self._mode_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._on_mode_changed()
        )

        # Width setting (Task 46.7: dropdown with Character/Pixel modes)
        width_frame = ttk.Frame(frame)
        width_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(width_frame, text="Width mode:").pack(side="left")
        self._width_mode_var = tk.StringVar(value="character")
        self._width_mode_combo = ttk.Combobox(
            width_frame,
            textvariable=self._width_mode_var,
            values=["Character", "Pixel"],
            state="readonly",
            width=10,
        )
        self._width_mode_combo.pack(side="left", padx=5)
        self._width_mode_combo.bind(
            "<<ComboboxSelected>>", self._on_width_mode_changed
        )

        # Character width entry
        self._char_width_frame = ttk.Frame(frame)
        self._char_width_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(self._char_width_frame, text="Width:").pack(side="left")
        self._width_var = tk.IntVar(value=48)
        width_spin = ttk.Spinbox(
            self._char_width_frame,
            from_=20,
            to=200,
            textvariable=self._width_var,
            width=8,
            command=self._on_width_changed,
        )
        width_spin.pack(side="left", padx=5)
        ttk.Label(
            self._char_width_frame, text="characters"
        ).pack(side="left")

        # Pixel width entry (initially hidden)
        self._pixel_width_frame = ttk.Frame(frame)

        ttk.Label(self._pixel_width_frame, text="Width:").pack(side="left")
        self._pixel_width_var = tk.IntVar(value=400)
        ttk.Spinbox(
            self._pixel_width_frame,
            from_=100,
            to=2000,
            textvariable=self._pixel_width_var,
            width=8,
        ).pack(side="left", padx=5)
        ttk.Label(self._pixel_width_frame, text="px").pack(side="left")

        ttk.Label(
            self._pixel_width_frame, text="  Font size:"
        ).pack(side="left", padx=(10, 0))
        self._font_size_var = tk.IntVar(value=14)
        ttk.Spinbox(
            self._pixel_width_frame,
            from_=8,
            to=72,
            textvariable=self._font_size_var,
            width=5,
        ).pack(side="left", padx=5)
        
        # TASK 28.1: Bind width spinbox to manifest
        self._manifest_bindings.append(
            bind_spinbox_to_field(
                spinbox=width_spin,
                var=self._width_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="Width",
                min_val=20,
                max_val=200,
                default=48,
                parent_key="WordwrapSettings",
            )
        )

        # Break character
        break_frame = ttk.Frame(frame)
        break_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(break_frame, text="Break char:").pack(side="left")
        self._break_var = tk.StringVar(value="\\n")
        break_combo = ttk.Combobox(
            break_frame,
            textvariable=self._break_var,
            values=["\\n", "\n", "<br>", "[r]", "\\r\\n"],
            width=10,
        )
        break_combo.pack(side="left", padx=5)
        
        # TASK 28.1: Bind break char combobox to manifest
        self._manifest_bindings.append(
            bind_combobox_to_field(
                combobox=break_combo,
                var=self._break_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="BreakChar",
                options=["\\n", "\n", "<br>", "[r]", "\\r\\n"],
                default="\\n",
                parent_key="WordwrapSettings",
            )
        )

        # Max lines
        max_lines_frame = ttk.Frame(frame)
        max_lines_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(max_lines_frame, text="Max lines:").pack(side="left")
        self._max_lines_var = tk.IntVar(value=4)
        max_lines_spin = ttk.Spinbox(
            max_lines_frame,
            from_=0,
            to=20,
            textvariable=self._max_lines_var,
            width=8,
        )
        max_lines_spin.pack(side="left", padx=5)
        ttk.Label(max_lines_frame, text="(0 = unlimited)").pack(side="left")
        
        # TASK 28.1: Bind max lines spinbox to manifest
        self._manifest_bindings.append(
            bind_spinbox_to_field(
                spinbox=max_lines_spin,
                var=self._max_lines_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="MaxLines",
                min_val=0,
                max_val=20,
                default=4,
                parent_key="WordwrapSettings",
            )
        )

        # Options — prevent orphan and prefer punctuation breaks are always
        # active in pretty_wrap(); no user toggle needed (Task 46.2)
        opts_frame = ttk.Frame(frame)
        opts_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(
            opts_frame,
            text="✓ Orphan prevention and punctuation breaks (always on)",
            foreground=THEME.text_secondary,
        ).pack(anchor="w")

    def _build_speaker_panel(self, parent: ttk.Frame) -> None:
        """Build the speaker handling options panel (Task 46.3: Ignore + Count)."""
        frame = ttk.LabelFrame(parent, text="Speaker Handling")
        frame.pack(fill="x", padx=5, pady=5)

        self._speaker_var = tk.StringVar(value=SpeakerMode.COUNT.value)

        # TASK 28.1: Trace speaker mode changes to manifest
        self._speaker_var.trace_add(
            "write", self._save_speaker_handling_to_manifest
        )

        speaker_frame = ttk.Frame(frame)
        speaker_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(speaker_frame, text="Mode:").pack(side="left")

        self._speaker_combo = ttk.Combobox(
            speaker_frame,
            textvariable=self._speaker_var,
            values=[m.value.title() for m in SpeakerMode],
            state="readonly",
            width=12,
        )
        self._speaker_combo.pack(side="left", padx=5)

        self._speaker_desc_label = ttk.Label(
            frame,
            text=SPEAKER_MODE_DESCRIPTIONS[SpeakerMode.COUNT],
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        )
        self._speaker_desc_label.pack(padx=5, pady=(0, 5), anchor="w")

        def _update_speaker_desc(*_args: Any) -> None:
            value = self._speaker_var.get().lower()
            for mode in SpeakerMode:
                if mode.value == value:
                    self._speaker_desc_label.configure(
                        text=SPEAKER_MODE_DESCRIPTIONS[mode]
                    )
                    break

        self._speaker_combo.bind(
            "<<ComboboxSelected>>", _update_speaker_desc
        )

    def _build_ignore_panel(self, parent: ttk.Frame) -> None:
        """Build the ignore patterns panel from Code Database (Task 46.4).

        Shows a read-only table of patterns sourced from the Code Database
        instead of hardcoded checkboxes.
        """
        frame = ttk.LabelFrame(parent, text="Ignore Patterns (Code Database)")
        frame.pack(fill="x", padx=5, pady=5)

        # Read-only Treeview showing Code Database patterns
        cols = ("pattern", "action", "example")
        self._ignore_tree = ttk.Treeview(
            frame,
            columns=cols,
            show="headings",
            height=4,
            selectmode="none",
        )
        self._ignore_tree.heading("pattern", text="Pattern")
        self._ignore_tree.heading("action", text="Action")
        self._ignore_tree.heading("example", text="Example")
        self._ignore_tree.column("pattern", width=100)
        self._ignore_tree.column("action", width=80)
        self._ignore_tree.column("example", width=120)
        self._ignore_tree.pack(fill="x", padx=5, pady=5)

        ttk.Label(
            frame,
            text="Patterns loaded from Code Database (Step 3)",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        ).pack(padx=5, pady=(0, 5), anchor="w")

    def _build_summary_panel(self) -> None:
        """Build the summary statistics panel."""
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=5)

        # Stats labels
        stats_frame = ttk.Frame(frame)
        stats_frame.pack(side="left")

        self._stats_labels: Dict[str, ttk.Label] = {}

        stats = [
            ("total", "Total:"),
            ("wrapped", "Wrapped:"),
            ("exceeding", "Exceeding:"),
            ("avg_len", "Avg length:"),
        ]

        for key, text in stats:
            lbl_frame = ttk.Frame(stats_frame)
            lbl_frame.pack(side="left", padx=10)

            ttk.Label(lbl_frame, text=text).pack(side="left")
            value_lbl = ttk.Label(
                lbl_frame,
                text="0",
                foreground=THEME.accent_info,
            )
            value_lbl.pack(side="left", padx=2)
            self._stats_labels[key] = value_lbl

        # Progress bar
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            frame,
            variable=self._progress_var,
            maximum=100,
            length=200,
        )
        self._progress_bar.pack(side="right", padx=5)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_format_changed(self, event: Optional[tk.Event] = None) -> None:
        """Handle format selection change."""
        format_key = self._format_var.get()
        if format_key in self._format_configs:
            config = self._format_configs[format_key]
            self._width_var.set(config.wrap_width)
            self._break_var.set(config.break_char)
            self._max_lines_var.set(config.max_lines)
            self._width_label.configure(text=f"Width: {config.wrap_width} chars")
            self._refresh_preview()

    def _on_mode_changed(self) -> None:
        """Handle wrap mode change."""
        mode = WrapMode(self._mode_var.get())
        self._wrap_options.mode = mode
        self._refresh_preview()

    def _on_width_changed(self) -> None:
        """Handle width change."""
        width = self._width_var.get()
        self._wrap_options.width = width
        self._width_label.configure(text=f"Width: {width} chars")
        self._refresh_preview()

    def _on_width_mode_changed(
        self, event: Optional[tk.Event] = None
    ) -> None:
        """Handle width mode toggle between Character and Pixel (Task 46.7)."""
        mode = self._width_mode_var.get().lower()
        if mode == "pixel":
            self._char_width_frame.pack_forget()
            self._pixel_width_frame.pack(fill="x", padx=5, pady=3)
        else:
            self._pixel_width_frame.pack_forget()
            self._char_width_frame.pack(fill="x", padx=5, pady=3)

    def _on_line_selected(self, row_ids: List[int]) -> None:
        """Handle line selection in preview table."""
        if not row_ids:
            self._selected_line_idx = -1
            return

        idx = row_ids[0]
        self._selected_line_idx = idx
        self._update_ruler(idx)

    # =========================================================================
    # Actions
    # =========================================================================

    def _apply_wordwrap(self) -> None:
        """Apply wordwrap to all lines."""
        if self._status == WrapStatus.RUNNING:
            messagebox.showinfo("Info", "Wordwrap is already running.")
            return

        self._status = WrapStatus.RUNNING
        self._status_label.configure(text="Running...")
        self._apply_btn.configure(state="disabled")

        def run_wrap() -> None:
            # Phase 48: Write wordwrap step log
            _ww_log = None
            import time as _time
            _ww_start = _time.perf_counter()
            try:
                from CherryAI.functions.mainhelper import (
                    _rotate_log, write_step_log_header,
                    write_step_log_footer,
                )
                mm = getattr(self, "_manifest_manager", None)
                if mm:
                    pdir = getattr(mm, "_project_dir", None)
                    pname = (
                        mm.get_project_info().project_name
                        if hasattr(mm, "get_project_info") else None
                    )
                    if pdir and pname:
                        from pathlib import Path as _P
                        _ww_log = _rotate_log(_P(str(pdir)), pname, "wordwrap")
                        write_step_log_header(_ww_log, {
                            "CherryAI Wordwrap Log": "",
                            "Started": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "Mode": self._mode_var.get(),
                            "Width": str(self._width_var.get()),
                        })
            except Exception:
                pass

            try:
                self._process_wrap()
                self._status = WrapStatus.COMPLETED
                # Phase 48: Footer
                try:
                    if _ww_log:
                        dur = _time.perf_counter() - _ww_start
                        changed = sum(1 for ln in self._lines if ln.wrapped != ln.original)
                        exceeding = sum(1 for ln in self._lines if ln.exceeds_limit)
                        write_step_log_footer(_ww_log, {
                            "Wordwrap Summary": "",
                            "Completed": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "Duration": f"{dur:.2f}s",
                            "Total Lines": str(len(self._lines)),
                            "Changed": str(changed),
                            "Exceeding": str(exceeding),
                        })
                except Exception:
                    pass
                self.after(0, self._on_wrap_complete)
            except Exception as e:
                logger.exception("Wordwrap failed")
                self._status = WrapStatus.FAILED
                self.after(0, lambda: self._on_wrap_error(str(e)))

        self._process_thread = threading.Thread(target=run_wrap, daemon=True)
        self._process_thread.start()

    def _process_wrap(self) -> None:
        """Process wordwrap on lines."""
        if not _HAS_WORDWRAP:
            logger.warning("wordwrap module not available, using simple wrap")
            self._simple_wrap()
            return

        # Build config
        config = WordwrapConfig(
            mode=self._mode_var.get(),
            in1=self._width_var.get(),
            in2=self._break_var.get(),
            in3=self._max_lines_var.get() or None,
            ignore_codes=self._get_ignore_codes(),
            speaker_mode=self._speaker_var.get().upper(),
        )

        # Get lines from session
        step_data = self.get_step_data()
        lines = step_data.get("lines", [])

        if not lines:
            return

        # Apply wordwrap
        wrapped_lines = apply_wordwrap(lines, config)

        # Update wrap lines
        self._lines = []
        for i, (orig, wrapped) in enumerate(zip(lines, wrapped_lines)):
            line = WrapLine(
                idx=i,
                original=orig,
                wrapped=wrapped,
                char_count=len(wrapped),
                line_count=wrapped.count(config.in2) + 1 if config.in2 else 1,
                exceeds_limit=bool(
                    config.in3 and ((wrapped.count(config.in2) + 1) if config.in2 else 1) > config.in3
                ),
            )
            self._lines.append(line)

        # Update stats
        self._update_stats()

    def _simple_wrap(self) -> None:
        """Simple wordwrap fallback when module not available."""
        step_data = self.get_step_data()
        lines = step_data.get("lines", [])
        width = self._width_var.get()
        break_char = self._break_var.get()
        max_lines = self._max_lines_var.get()

        self._lines = []
        for i, line in enumerate(lines):
            # Simple character-based wrap
            wrapped = self._wrap_line(line, width, break_char)
            lc = wrapped.count(break_char) + 1
            exceeds = bool(max_lines and lc > max_lines)
            wrap_line = WrapLine(
                idx=i,
                original=line,
                wrapped=wrapped,
                char_count=len(wrapped),
                line_count=lc,
                exceeds_limit=exceeds,
            )
            self._lines.append(wrap_line)

        self._update_stats()

    def _wrap_line(self, text: str, width: int, break_char: str) -> str:
        """Simple line wrapper."""
        if len(text) <= width:
            return text

        result = []
        current = ""

        for word in text.split():
            if len(current) + len(word) + 1 <= width:
                if current:
                    current += " "
                current += word
            else:
                if current:
                    result.append(current)
                current = word

        if current:
            result.append(current)

        return break_char.join(result)

    def _on_wrap_complete(self) -> None:
        """Handle wrap completion."""
        self._status_label.configure(text="Completed")
        self._apply_btn.configure(state="normal")
        self._refresh_table()
        self._update_summary()

    def _on_wrap_error(self, error: str) -> None:
        """Handle wrap error."""
        self._status_label.configure(text="Failed")
        self._apply_btn.configure(state="normal")
        messagebox.showerror("Error", f"Wordwrap failed: {error}")

    def _refresh_preview(self) -> None:
        """Refresh the preview with current settings."""
        self._apply_wordwrap()

    def _reset_all(self) -> None:
        """Reset all lines to original."""
        if messagebox.askyesno("Confirm", "Reset all lines to original?"):
            for line in self._lines:
                line.wrapped = line.original
            self._refresh_table()
            self._update_summary()

    def _accept_selected(self) -> None:
        """Accept selected lines as final."""
        selected = self._preview_table.get_selected_items()
        if not selected:
            messagebox.showinfo("Info", "No lines selected.")
            return

        # Mark as accepted in session
        step_data = self.get_step_data()
        accepted = step_data.get("accepted_lines", set())
        for row in selected:
            try:
                idx = int(row.values.get("idx", -1))
                accepted.add(idx)
            except (ValueError, TypeError):
                pass
        step_data["accepted_lines"] = accepted
        self.set_step_data(step_data)

        messagebox.showinfo("Info", f"Accepted {len(selected)} lines.")

    def _revert_selected(self) -> None:
        """Revert selected lines to original."""
        selected = self._preview_table.get_selected_items()
        if not selected:
            messagebox.showinfo("Info", "No lines selected.")
            return

        for row in selected:
            try:
                idx = int(row.values.get("idx", -1))
                if 0 <= idx < len(self._lines):
                    self._lines[idx].wrapped = self._lines[idx].original
            except (ValueError, TypeError):
                pass

        self._refresh_table()

    # =========================================================================
    # UI Updates
    # =========================================================================

    def _refresh_table(self) -> None:
        """Refresh the preview table with current lines and filter."""
        rows: List[TableRow] = []
        trunc = 45
        active_filter = self._filter_var.get()

        for line in self._lines:
            # Apply filter (Task 46.9)
            if active_filter == "changed" and not line.has_changes:
                continue
            if active_filter == "exceeding" and not line.exceeds_limit:
                continue
            if active_filter == "differs" and not line.overwrite_differs:
                continue

            orig = (line.original[:trunc] + "..."
                    if len(line.original) > trunc else line.original)
            wrap = (line.wrapped[:trunc] + "..."
                    if len(line.wrapped) > trunc else line.wrapped)
            ow = (line.overwrite[:trunc] + "..."
                  if len(line.overwrite) > trunc else line.overwrite)
            row = TableRow(
                id=line.idx,
                values={
                    "idx": str(line.idx),
                    "status": line.status,
                    "chars": str(line.char_count),
                    "lines": str(line.line_count),
                    "original": orig,
                    "wrapped": wrap,
                    "overwrite": ow,
                },
            )
            rows.append(row)

        self._preview_table.load_data(rows)

    def _update_ruler(self, line_idx: int) -> None:
        """Update the line length ruler for selected line."""
        self._ruler_canvas.delete("all")

        if line_idx < 0 or line_idx >= len(self._lines):
            return

        line = self._lines[line_idx]
        width = self._width_var.get()
        canvas_width = self._ruler_canvas.winfo_width() or 400

        # Calculate scale
        max_len = max(len(line.original), len(line.wrapped), width)
        scale = (canvas_width - 20) / max(max_len, 1)

        # Draw limit marker
        limit_x = 10 + (width * scale)
        self._ruler_canvas.create_line(
            limit_x, 0, limit_x, 20,
            fill=THEME.accent_warning,
            width=2,
            dash=(4, 2),
        )

        # Draw length bar
        bar_len = len(line.wrapped) * scale
        color = THEME.accent_success if len(line.wrapped) <= width else THEME.accent_error
        self._ruler_canvas.create_rectangle(
            10, 5, 10 + bar_len, 15,
            fill=color,
            outline="",
        )

        # Add text
        self._ruler_canvas.create_text(
            canvas_width - 10, 10,
            text=f"{len(line.wrapped)}/{width}",
            anchor="e",
            fill=THEME.text_primary,
        )

    def _update_stats(self) -> None:
        """Update wrap statistics."""
        if not self._lines:
            self._stats = WrapStats()
            return

        total = len(self._lines)
        wrapped = sum(1 for l in self._lines if l.has_changes)
        exceeding = sum(1 for l in self._lines if l.exceeds_limit)
        total_chars = sum(l.char_count for l in self._lines)

        self._stats = WrapStats(
            total_lines=total,
            lines_wrapped=wrapped,
            lines_exceeding=exceeding,
            total_chars=total_chars,
            avg_line_length=total_chars / total if total else 0,
        )

    def _update_summary(self) -> None:
        """Update summary display."""
        self._stats_labels["total"].configure(text=str(self._stats.total_lines))
        self._stats_labels["wrapped"].configure(text=str(self._stats.lines_wrapped))
        self._stats_labels["exceeding"].configure(text=str(self._stats.lines_exceeding))
        self._stats_labels["avg_len"].configure(text=f"{self._stats.avg_line_length:.1f}")

    def _get_ignore_codes(self) -> str:
        """Get comma-separated ignore code names from Code Database."""
        if self.manifest_manager is None:
            return ""
        try:
            codes = self.manifest_manager.get("CodeDatabase", {})
            patterns = []
            for entry in codes.get("entries", []):
                action = entry.get("action", "")
                if action.lower() in ("preserve", "remove"):
                    patterns.append(entry.get("pattern", ""))
            return ",".join(p for p in patterns if p)
        except Exception:
            return ""

    # =========================================================================
    # BaseStep Implementation
    # =========================================================================

    def _save_wordwrap_mode_to_manifest(self, *args: Any) -> None:
        """Save wordwrap mode to manifest when changed (TASK 28.1).
        
        Args:
            *args: Trace callback arguments (ignored).
        """
        if self.manifest_manager is None:
            return
        value = self._mode_var.get()
        save_nested_text_field(
            self.manifest_manager, "WordwrapSettings", "Mode", value
        )
        logger.debug("Wordwrap mode saved to manifest: %s", value)

    def _save_speaker_handling_to_manifest(self, *args: Any) -> None:
        """Save speaker handling mode to manifest when changed (TASK 28.1).
        
        Args:
            *args: Trace callback arguments (ignored).
        """
        if self.manifest_manager is None:
            return
        value = self._speaker_var.get()
        save_nested_text_field(
            self.manifest_manager, "WordwrapSettings", "SpeakerHandling", value
        )
        logger.debug("Speaker handling saved to manifest: %s", value)

    def _load_wordwrap_settings_from_manifest(self) -> None:
        """Load wordwrap settings from manifest (TASK 28.1).
        
        Loads all wordwrap options from manifest into UI widgets.
        """
        if self.manifest_manager is None:
            return
        
        # Load all checkbox/spinbox/combobox bindings
        for binding in self._manifest_bindings:
            if hasattr(binding, "load_from_manifest"):
                binding.load_from_manifest()
        
        # Load mode
        mode_value = load_nested_text_field(
            self.manifest_manager, "WordwrapSettings", "Mode", WrapMode.MANUAL.value
        )
        self._mode_var.set(mode_value)
        
        # Load speaker handling
        speaker_value = load_nested_text_field(
            self.manifest_manager, "WordwrapSettings", "SpeakerHandling", SpeakerMode.COUNT.value
        )
        self._speaker_var.set(speaker_value)
        
        logger.debug("Wordwrap settings loaded from manifest")

    def _apply_parser_wordwrap_defaults(self) -> None:
        """Auto-populate format configs from registered parser scripts (TASK 53.4).

        Iterates the parser registry and, for each parser that provides a
        :attr:`wordwrap_config`, registers a :class:`FormatConfig` entry.
        The format dropdown values are updated accordingly.

        User-set manifest values take precedence because
        ``_load_wordwrap_settings_from_manifest`` runs after this method.
        """
        if not _HAS_PARSER_REGISTRY:
            return

        try:
            registry = get_parser_registry()
        except Exception:
            return

        for info in registry.list_parsers():
            parser = registry.get(info["name"])
            if parser is None or not info.get("has_wordwrap"):
                continue

            ww = parser.wordwrap_config
            if ww is None:
                continue

            key = parser.name.lower()
            self._format_configs[key] = FormatConfig(
                format_name=parser.name,
                wrap_width=ww.max_line_length,
                break_char=ww.wordwrap_command,
                max_lines=ww.max_line_number,
                enabled=True,
            )
            logger.debug(
                "Parser '%s' registered wordwrap defaults: "
                "width=%d, break='%s', max_lines=%d",
                parser.name,
                ww.max_line_length,
                ww.wordwrap_command,
                ww.max_line_number,
            )

        # Refresh format dropdown values
        if hasattr(self, "_format_var"):
            try:
                self._format_var.configure(  # type: ignore[attr-defined]
                    values=list(self._format_configs.keys()),  # type: ignore[arg-type]
                )
            except Exception:
                pass

    def on_enter(self) -> None:
        """Called when entering this tab."""
        # TASK 53.4: Register parser-provided format defaults (before
        # manifest loading so manifest values override parser defaults)
        self._apply_parser_wordwrap_defaults()

        # TASK 28.1: Load wordwrap settings from manifest
        self._load_wordwrap_settings_from_manifest()
        
        self._load_lines_from_session()
        self._refresh_table()
        self._update_summary()

    def on_leave(self) -> None:
        """Called when leaving this tab."""
        self._save_to_session()

    def _load_lines_from_session(self) -> None:
        """Load lines from manifest using postpro → tl → prepro → orig chain.

        Also restores existing ``wordwr`` values when available.
        """
        latest: list[str] = []
        wordwr_map: dict[int, str] = {}

        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            latest = get_all_lines_resolved(mgr, "postpro")
            for ln in mgr.get_lines():
                idx = ln.get("idx")
                wr = ln.get("wordwr", "")
                if idx is not None and wr:
                    wordwr_map[idx] = wr

        # Fallback: session step data
        if not latest:
            step_data = self.get_step_data()
            latest = step_data.get("lines", [])

        self._lines = []
        for i, line in enumerate(latest):
            wr = wordwr_map.get(i, line)
            wrap_line = WrapLine(
                idx=i,
                original=line,
                wrapped=wr,
            )
            self._lines.append(wrap_line)

    def _save_to_session(self) -> None:
        """Save current state to session.

        Persists wrapped text to manifest lines[].wordwr via
        set_line_field.  Only writes lines where the wrapped text
        differs from the original to avoid unnecessary manifest bloat.
        """
        step_data = self.get_step_data()
        step_data["wrap_options"] = {
            "mode": self._mode_var.get(),
            "width": self._width_var.get(),
            "break_char": self._break_var.get(),
            "max_lines": self._max_lines_var.get(),
            "speaker_mode": self._speaker_var.get(),
        }
        step_data["wrapped_lines"] = [l.wrapped for l in self._lines]
        self.set_step_data(step_data)

        # Persist only changed wrapped lines to the manifest
        mgr = self.manifest_manager
        if mgr is not None:
            for line in self._lines:
                if line.wrapped != line.original:
                    mgr.set_line_field(line.idx, "wordwr", line.wrapped)

    # =========================================================================
    # Public API
    # =========================================================================

    def get_wrap_options(self) -> WrapOptions:
        """Get current wrap options.

        Returns:
            WrapOptions with current settings.
        """
        return WrapOptions(
            mode=WrapMode(self._mode_var.get()),
            speaker_mode=SpeakerMode(self._speaker_var.get()),
            width=self._width_var.get(),
            break_char=self._break_var.get(),
            max_lines=self._max_lines_var.get(),
            prevent_orphan=True,
            prefer_punct_breaks=True,
        )

    def get_lines(self) -> List[WrapLine]:
        """Get all wrap lines.

        Returns:
            List of WrapLine objects.
        """
        return list(self._lines)

    def get_wrapped_lines(self) -> List[str]:
        """Get wrapped text for all lines.

        Returns:
            List of wrapped text strings.
        """
        return [l.wrapped for l in self._lines]

    def get_stats(self) -> WrapStats:
        """Get wrap statistics.

        Returns:
            WrapStats with current statistics.
        """
        return self._stats
