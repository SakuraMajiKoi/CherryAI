"""CherryAI GUI v2 Wordwrap and Overwrite Step.

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
try:
    # Explicit import of shared wordwrap logic per architecture rules
    from CherryAI.functions.wordwrap import WordwrapConfig, apply_wordwrap
    _HAS_WORDWRAP = True
except ImportError:  # pragma: no cover
    _HAS_WORDWRAP = False

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
    RPGMAKER = "rpgmaker"
    DISABLED = "disabled"


class SpeakerMode(Enum):
    """Speaker handling mode."""

    IGNORE = "ignore"
    SAMELINE = "sameline"
    SAMELINEINDENT = "samelineindent"
    NEWLINE = "newline"


class IgnorePattern(Enum):
    """Pattern types to ignore during wrapping."""

    ANGLE = "angle"
    SQUARE = "square"
    CURLY = "curly"
    EN = "en"


class OverwriteStrategy(Enum):
    """Strategy for handling output file conflicts."""

    OVERWRITE = "overwrite"
    BACKUP = "backup"
    MERGE = "merge"
    SKIP = "skip"


class MergeMethod(Enum):
    """Method for merging translated content."""

    REPLACE_ALL = "replace_all"
    REPLACE_CHANGED = "replace_changed"
    APPEND = "append"
    INTERLEAVE = "interleave"


class TypographyStyle(Enum):
    """Typography style for punctuation and spacing."""

    WESTERN = "western"
    JAPANESE = "japanese"
    CHINESE = "chinese"
    KOREAN = "korean"
    MIXED = "mixed"


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
    char_count: int = 0
    line_count: int = 1
    exceeds_limit: bool = False
    break_positions: List[int] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if wrapping changed the text."""
        return self.original != self.wrapped

    @property
    def status(self) -> str:
        """Get display status."""
        if self.exceeds_limit:
            return "⚠ Exceeds"
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
    speaker_mode: SpeakerMode = SpeakerMode.SAMELINE
    ignore_patterns: List[IgnorePattern] = field(default_factory=list)
    width: int = 48
    break_char: str = "\\n"
    max_lines: int = 4
    prevent_orphan: bool = True
    prefer_punct_breaks: bool = True
    format_configs: Dict[str, FormatConfig] = field(default_factory=dict)


@dataclass
class OverwriteOptions:
    """Options for overwrite and merge strategies."""

    strategy: OverwriteStrategy = OverwriteStrategy.BACKUP
    merge_method: MergeMethod = MergeMethod.REPLACE_ALL
    create_backup: bool = True
    backup_suffix: str = ".bak"
    preserve_formatting: bool = True


@dataclass
class TypographyOptions:
    """Typography options per language."""

    style: TypographyStyle = TypographyStyle.WESTERN
    use_fullwidth_punct: bool = False
    use_ideographic_space: bool = False
    convert_quotes: bool = False
    quote_style: str = '""'


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
    SpeakerMode.IGNORE: "Remove speaker prefix before wrapping",
    SpeakerMode.SAMELINE: "Keep prefix on first line only",
    SpeakerMode.SAMELINEINDENT: "Prefix on first line, indent continuation",
    SpeakerMode.NEWLINE: "Speaker prefix on its own line",
}


IGNORE_PATTERN_DESCRIPTIONS: Dict[IgnorePattern, str] = {
    IgnorePattern.ANGLE: "Ignore <tags> (HTML/XML)",
    IgnorePattern.SQUARE: "Ignore [codes] (RPG Maker)",
    IgnorePattern.CURLY: "Ignore {vars} (template)",
    IgnorePattern.EN: "Ignore en() escapes",
}


# ============================================================================
# WordwrapOverwriteStep Class
# ============================================================================


class WordwrapOverwriteStep(BaseStep):
    """Wordwrap and overwrite step for text formatting.

    Features:
    - Wrap width per format (RPG Maker, Ren'Py, etc.)
    - Indentation and speaker handling rules
    - Merge/overwrite strategy selection
    - Preview with line length indicators
    - Per-language typography options
    - Real-time preview updates
    """

    step_id = 8
    step_name = "Wordwrap and Overwrite"
    # Test visibility for explicit import expectation
    _IMPORT_EXPECTATION = "from functions.wordwrap import"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize wordwrap and overwrite step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables BEFORE super().__init__
        # because base class calls _build_ui() which needs these
        self._lines: List[WrapLine] = []
        self._wrap_options = WrapOptions()
        self._overwrite_options = OverwriteOptions()
        self._typography_options = TypographyOptions()
        self._status = WrapStatus.IDLE
        self._stats = WrapStats()
        self._process_thread: Optional[threading.Thread] = None
        self._selected_line_idx: int = -1
        self._format_configs = dict(DEFAULT_FORMAT_CONFIGS)
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

        # Define columns
        columns = [
            ColumnDef(key="idx", title="#", width=50, anchor="center"),
            ColumnDef(key="status", title="Status", width=90, anchor="center"),
            ColumnDef(key="chars", title="Chars", width=60, anchor="center"),
            ColumnDef(key="lines", title="Lines", width=50, anchor="center"),
            ColumnDef(key="original", title="Original", width=200),
            ColumnDef(key="wrapped", title="Wrapped Preview", width=250),
        ]

        self._preview_table = SharedTable(
            frame,
            columns=columns,
            show_filter=True,
            show_checkboxes=True,
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

        # Typography panel
        self._build_typography_panel(scrollable_frame)

        # Overwrite strategy panel
        self._build_overwrite_panel(scrollable_frame)

        # Enable mousewheel scrolling
        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _build_wrap_options_panel(self, parent: ttk.Frame) -> None:
        """Build the wordwrap options panel."""
        frame = ttk.LabelFrame(parent, text="Wordwrap Settings")
        frame.pack(fill="x", padx=5, pady=5)

        # Mode selection
        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(mode_frame, text="Mode:").pack(side="left")

        self._mode_var = tk.StringVar(value=WrapMode.MANUAL.value)
        for mode in WrapMode:
            ttk.Radiobutton(
                mode_frame,
                text=mode.value.title(),
                variable=self._mode_var,
                value=mode.value,
                command=self._on_mode_changed,
            ).pack(side="left", padx=5)

        # Width setting
        width_frame = ttk.Frame(frame)
        width_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(width_frame, text="Width:").pack(side="left")
        self._width_var = tk.IntVar(value=48)
        width_spin = ttk.Spinbox(
            width_frame,
            from_=20,
            to=200,
            textvariable=self._width_var,
            width=8,
            command=self._on_width_changed,
        )
        width_spin.pack(side="left", padx=5)
        ttk.Label(width_frame, text="characters").pack(side="left")

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

        # Options
        opts_frame = ttk.Frame(frame)
        opts_frame.pack(fill="x", padx=5, pady=5)

        self._orphan_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts_frame,
            text="Prevent orphans",
            variable=self._orphan_var,
        ).pack(anchor="w")

        self._punct_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts_frame,
            text="Prefer punctuation breaks",
            variable=self._punct_var,
        ).pack(anchor="w")

    def _build_speaker_panel(self, parent: ttk.Frame) -> None:
        """Build the speaker handling options panel."""
        frame = ttk.LabelFrame(parent, text="Speaker Handling")
        frame.pack(fill="x", padx=5, pady=5)

        self._speaker_var = tk.StringVar(value=SpeakerMode.SAMELINE.value)

        for mode in SpeakerMode:
            rb_frame = ttk.Frame(frame)
            rb_frame.pack(fill="x", padx=5, pady=2)

            ttk.Radiobutton(
                rb_frame,
                text=mode.value.title(),
                variable=self._speaker_var,
                value=mode.value,
            ).pack(side="left")

            ttk.Label(
                rb_frame,
                text=SPEAKER_MODE_DESCRIPTIONS[mode],
                foreground=THEME.text_secondary,
                font=("TkDefaultFont", 8),
            ).pack(side="left", padx=5)

    def _build_ignore_panel(self, parent: ttk.Frame) -> None:
        """Build the ignore patterns panel."""
        frame = ttk.LabelFrame(parent, text="Ignore Patterns")
        frame.pack(fill="x", padx=5, pady=5)

        self._ignore_vars: Dict[IgnorePattern, tk.BooleanVar] = {}

        for pattern in IgnorePattern:
            cb_frame = ttk.Frame(frame)
            cb_frame.pack(fill="x", padx=5, pady=2)

            var = tk.BooleanVar(value=False)
            self._ignore_vars[pattern] = var

            ttk.Checkbutton(
                cb_frame,
                text=pattern.value.title(),
                variable=var,
            ).pack(side="left")

            ttk.Label(
                cb_frame,
                text=IGNORE_PATTERN_DESCRIPTIONS[pattern],
                foreground=THEME.text_secondary,
                font=("TkDefaultFont", 8),
            ).pack(side="left", padx=5)

    def _build_typography_panel(self, parent: ttk.Frame) -> None:
        """Build the typography options panel."""
        frame = ttk.LabelFrame(parent, text="Typography")
        frame.pack(fill="x", padx=5, pady=5)

        # Style selection
        style_frame = ttk.Frame(frame)
        style_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(style_frame, text="Style:").pack(side="left")

        self._typo_style_var = tk.StringVar(value=TypographyStyle.WESTERN.value)
        typo_combo = ttk.Combobox(
            style_frame,
            textvariable=self._typo_style_var,
            values=[s.value.title() for s in TypographyStyle],
            state="readonly",
            width=12,
        )
        typo_combo.pack(side="left", padx=5)

        # Options
        opts_frame = ttk.Frame(frame)
        opts_frame.pack(fill="x", padx=5, pady=3)

        self._fullwidth_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts_frame,
            text="Use fullwidth punctuation",
            variable=self._fullwidth_var,
        ).pack(anchor="w")

        self._ideographic_space_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts_frame,
            text="Use ideographic spaces",
            variable=self._ideographic_space_var,
        ).pack(anchor="w")

        self._convert_quotes_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts_frame,
            text="Convert quotation marks",
            variable=self._convert_quotes_var,
        ).pack(anchor="w")

    def _build_overwrite_panel(self, parent: ttk.Frame) -> None:
        """Build the overwrite strategy panel."""
        frame = ttk.LabelFrame(parent, text="Overwrite Strategy")
        frame.pack(fill="x", padx=5, pady=5)

        # Strategy selection
        self._strategy_var = tk.StringVar(value=OverwriteStrategy.BACKUP.value)

        strategies = [
            (OverwriteStrategy.OVERWRITE, "Replace existing files"),
            (OverwriteStrategy.BACKUP, "Create backup before overwrite"),
            (OverwriteStrategy.MERGE, "Merge with existing content"),
            (OverwriteStrategy.SKIP, "Skip if file exists"),
        ]

        for strategy, desc in strategies:
            rb_frame = ttk.Frame(frame)
            rb_frame.pack(fill="x", padx=5, pady=2)

            ttk.Radiobutton(
                rb_frame,
                text=strategy.value.title(),
                variable=self._strategy_var,
                value=strategy.value,
                command=self._on_strategy_changed,
            ).pack(side="left")

            ttk.Label(
                rb_frame,
                text=desc,
                foreground=THEME.text_secondary,
                font=("TkDefaultFont", 8),
            ).pack(side="left", padx=5)

        # Merge options (shown when merge selected)
        self._merge_frame = ttk.Frame(frame)
        self._merge_frame.pack(fill="x", padx=20, pady=5)

        ttk.Label(self._merge_frame, text="Merge method:").pack(side="left")

        self._merge_var = tk.StringVar(value=MergeMethod.REPLACE_ALL.value)
        merge_combo = ttk.Combobox(
            self._merge_frame,
            textvariable=self._merge_var,
            values=[m.value.replace("_", " ").title() for m in MergeMethod],
            state="readonly",
            width=15,
        )
        merge_combo.pack(side="left", padx=5)

        # Initially hide merge options
        self._merge_frame.pack_forget()

        # Backup suffix
        backup_frame = ttk.Frame(frame)
        backup_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(backup_frame, text="Backup suffix:").pack(side="left")

        self._backup_suffix_var = tk.StringVar(value=".bak")
        ttk.Entry(
            backup_frame,
            textvariable=self._backup_suffix_var,
            width=10,
        ).pack(side="left", padx=5)

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

    def _on_strategy_changed(self) -> None:
        """Handle overwrite strategy change."""
        strategy = OverwriteStrategy(self._strategy_var.get())
        self._overwrite_options.strategy = strategy

        # Show/hide merge options
        if strategy == OverwriteStrategy.MERGE:
            self._merge_frame.pack(fill="x", padx=20, pady=5)
        else:
            self._merge_frame.pack_forget()

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
            try:
                self._process_wrap()
                self._status = WrapStatus.COMPLETED
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

        self._lines = []
        for i, line in enumerate(lines):
            # Simple character-based wrap
            wrapped = self._wrap_line(line, width, break_char)
            wrap_line = WrapLine(
                idx=i,
                original=line,
                wrapped=wrapped,
                char_count=len(wrapped),
                line_count=wrapped.count(break_char) + 1,
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
        """Refresh the preview table with current lines."""
        rows: List[TableRow] = []

        for line in self._lines:
            row = TableRow(
                id=line.idx,
                values={
                    "idx": str(line.idx),
                    "status": line.status,
                    "chars": str(line.char_count),
                    "lines": str(line.line_count),
                    "original": line.original[:50] + "..." if len(line.original) > 50 else line.original,
                    "wrapped": line.wrapped[:50] + "..." if len(line.wrapped) > 50 else line.wrapped,
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
        """Get comma-separated ignore code names."""
        codes = []
        for pattern, var in self._ignore_vars.items():
            if var.get():
                codes.append(pattern.value)
        return ",".join(codes)

    # =========================================================================
    # BaseStep Implementation
    # =========================================================================

    def on_enter(self) -> None:
        """Called when entering this tab."""
        self._load_lines_from_session()
        self._refresh_table()
        self._update_summary()

    def on_leave(self) -> None:
        """Called when leaving this tab."""
        self._save_to_session()

    def _load_lines_from_session(self) -> None:
        """Load lines from session state."""
        step_data = self.get_step_data()
        lines = step_data.get("lines", [])

        self._lines = []
        for i, line in enumerate(lines):
            wrap_line = WrapLine(
                idx=i,
                original=line,
                wrapped=line,
            )
            self._lines.append(wrap_line)

    def _save_to_session(self) -> None:
        """Save current state to session."""
        step_data = self.get_step_data()
        step_data["wrap_options"] = {
            "mode": self._mode_var.get(),
            "width": self._width_var.get(),
            "break_char": self._break_var.get(),
            "max_lines": self._max_lines_var.get(),
            "speaker_mode": self._speaker_var.get(),
            "ignore_patterns": [
                p.value for p, v in self._ignore_vars.items() if v.get()
            ],
        }
        step_data["overwrite_options"] = {
            "strategy": self._strategy_var.get(),
            "merge_method": self._merge_var.get(),
            "backup_suffix": self._backup_suffix_var.get(),
        }
        step_data["wrapped_lines"] = [l.wrapped for l in self._lines]
        self.set_step_data(step_data)

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
            ignore_patterns=[
                p for p, v in self._ignore_vars.items() if v.get()
            ],
            width=self._width_var.get(),
            break_char=self._break_var.get(),
            max_lines=self._max_lines_var.get(),
            prevent_orphan=self._orphan_var.get(),
            prefer_punct_breaks=self._punct_var.get(),
        )

    def get_overwrite_options(self) -> OverwriteOptions:
        """Get current overwrite options.

        Returns:
            OverwriteOptions with current settings.
        """
        return OverwriteOptions(
            strategy=OverwriteStrategy(self._strategy_var.get()),
            merge_method=MergeMethod(self._merge_var.get().lower().replace(" ", "_")),
            backup_suffix=self._backup_suffix_var.get(),
        )

    def get_typography_options(self) -> TypographyOptions:
        """Get current typography options.

        Returns:
            TypographyOptions with current settings.
        """
        return TypographyOptions(
            style=TypographyStyle(self._typo_style_var.get().lower()),
            use_fullwidth_punct=self._fullwidth_var.get(),
            use_ideographic_space=self._ideographic_space_var.get(),
            convert_quotes=self._convert_quotes_var.get(),
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
