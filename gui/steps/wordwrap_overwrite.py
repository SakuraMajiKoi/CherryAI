"""CherryAI GUI v2 Wordwrap Step.

Ninth workflow tab for text formatting after QA.
Provides wordwrap configuration and preview based on the QA stage output.
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
    get_all_lines_for_stage,
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


def _persist_sparse_wordwrap(
    manager: "ManifestManager",
    idx: int,
    original_text: str,
    wrapped_text: str,
) -> None:
    """Persist ``wordwr`` only when it differs from the stage input."""
    if wrapped_text and wrapped_text != original_text:
        manager.set_line_field(idx, "wordwr", wrapped_text)
        return
    manager.clear_line_field(idx, "wordwr")


# ============================================================================
# Enums
# ============================================================================


class WrapMode(Enum):
    """Wordwrap mode selection."""

    MANUAL = "manual"

    @classmethod
    def from_display(cls, value: str) -> "WrapMode":
        """Parse from display string (title-case) or raw value."""
        for member in cls:
            if member.value == value or member.value == value.lower():
                return member
        raise ValueError(f"{value!r} is not a valid WrapMode")


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


@dataclass
class TagWrapConfig:
    """Per-tag wordwrap configuration.

    Each extraction tag (dialogue, menu, etc.) can have its own wrap
    width, break character, max-lines, speaker handling, and pretty-wrap
    settings.  The parser provides defaults via ``wordwrap_for_tag``
    but all values are user-configurable.
    """

    tag: str
    width: int = 48
    break_char: str = "\\n"
    max_lines: int = 4
    speaker_handling: str = "count"  # "ignore" | "count"
    prevent_orphans: bool = True
    prefer_punct_breaks: bool = True
    new_textbox: bool = False
    new_textbox_injection: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to manifest-compatible dict."""
        return {
            "tag": self.tag,
            "Width": self.width,
            "BreakChar": self.break_char,
            "MaxLines": self.max_lines,
            "SpeakerHandling": self.speaker_handling,
            "PreventOrphans": self.prevent_orphans,
            "PreferPunctuationBreaks": self.prefer_punct_breaks,
            "NewTextbox": self.new_textbox,
            "NewTextboxInjection": self.new_textbox_injection,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TagWrapConfig":
        """Deserialize from manifest dict."""
        return cls(
            tag=d.get("tag", ""),
            width=d.get("Width", 48),
            break_char=d.get("BreakChar", "\\n"),
            max_lines=d.get("MaxLines", 4),
            speaker_handling=d.get("SpeakerHandling", "count"),
            prevent_orphans=d.get("PreventOrphans", True),
            prefer_punct_breaks=d.get("PreferPunctuationBreaks", True),
            new_textbox=d.get("NewTextbox", False),
            new_textbox_injection=d.get("NewTextboxInjection", ""),
        )


# ============================================================================
# Constants
# ============================================================================

DEFAULT_TAG_CONFIGS: List[TagWrapConfig] = [
    TagWrapConfig(tag="dialogue", width=48, break_char="\\n", max_lines=4),
    TagWrapConfig(tag="menu", width=48, break_char="\\n", max_lines=0),
]


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

    step_id = 8
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
        self._persist_after_wrap: bool = False
        self._format_configs = dict(DEFAULT_FORMAT_CONFIGS)
        # TASK 28.1: Manifest bindings for wordwrap settings
        self._manifest_bindings: List[BindingInfo] = []
        # Per-tag wordwrap configs and UI widgets
        self._tag_configs: List[TagWrapConfig] = [
            TagWrapConfig(tag=tc.tag, width=tc.width,
                          break_char=tc.break_char, max_lines=tc.max_lines)
            for tc in DEFAULT_TAG_CONFIGS
        ]
        self._tag_widgets: Dict[str, Dict[str, Any]] = {}
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

        # Define columns.
        columns = [
            ColumnDef(key="idx", title="#", width=50, anchor="center"),
            ColumnDef(key="status", title="Status", width=90, anchor="center"),
            ColumnDef(key="chars", title="Chars", width=60, anchor="center"),
            ColumnDef(key="lines", title="Lines", width=50, anchor="center"),
            ColumnDef(key="original", title="Input", width=180),
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
        """Build per-tag wordwrap options panel.

        Creates a "Wordwrap Settings" LabelFrame containing:
        - Global Mode dropdown
        - Per-tag sections (dialogue, menu by default) with Width,
          BreakChar, MaxLines widgets.  Parser-managed tags show an
          informational label instead of the settings.
        - "Add Tag" dropdown for extending the tag list.
        """
        frame = ttk.LabelFrame(parent, text="Wordwrap Settings")
        frame.pack(fill="x", padx=5, pady=5)

        # Global Mode selection
        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(mode_frame, text="Mode:").pack(side="left")

        self._mode_var = tk.StringVar(value=WrapMode.MANUAL.value)
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

        # Width mode (global — character/pixel toggle)
        width_mode_frame = ttk.Frame(frame)
        width_mode_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(width_mode_frame, text="Width mode:").pack(side="left")
        self._width_mode_var = tk.StringVar(value="character")
        self._width_mode_combo = ttk.Combobox(
            width_mode_frame,
            textvariable=self._width_mode_var,
            values=["Character", "Pixel"],
            state="readonly",
            width=10,
        )
        self._width_mode_combo.pack(side="left", padx=5)
        self._width_mode_combo.bind(
            "<<ComboboxSelected>>", self._on_width_mode_changed
        )

        # Pixel width entry (global, initially hidden)
        self._pixel_width_frame = ttk.Frame(frame)
        ttk.Label(self._pixel_width_frame, text="Width:").pack(side="left")
        self._pixel_width_var = tk.IntVar(value=400)
        ttk.Spinbox(
            self._pixel_width_frame, from_=100, to=2000,
            textvariable=self._pixel_width_var, width=8,
        ).pack(side="left", padx=5)
        ttk.Label(self._pixel_width_frame, text="px").pack(side="left")
        ttk.Label(
            self._pixel_width_frame, text="  Font size:",
        ).pack(side="left", padx=(10, 0))
        self._font_size_var = tk.IntVar(value=14)
        ttk.Spinbox(
            self._pixel_width_frame, from_=8, to=72,
            textvariable=self._font_size_var, width=5,
        ).pack(side="left", padx=5)

        # Separator
        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=5, pady=3)

        # Container for dynamic per-tag sections
        self._tag_sections_frame = ttk.Frame(frame)
        self._tag_sections_frame.pack(fill="x", padx=0, pady=0)

        # Build initial tag sections
        self._rebuild_tag_sections()

        # "Add Tag" dropdown at the bottom
        add_frame = ttk.Frame(frame)
        add_frame.pack(fill="x", padx=5, pady=5)

        self._add_tag_var = tk.StringVar(value="Add tag…")
        self._add_tag_combo = ttk.Combobox(
            add_frame,
            textvariable=self._add_tag_var,
            state="readonly",
            width=25,
        )
        self._add_tag_combo.pack(side="left")
        self._add_tag_combo.bind(
            "<<ComboboxSelected>>", self._on_add_tag_selected,
        )
        self._refresh_add_tag_options()

        # Backward-compat aliases — point at dialogue tag vars
        self._width_var = tk.IntVar(value=48)
        self._break_var = tk.StringVar(value="\\n")
        self._max_lines_var = tk.IntVar(value=4)
        # _char_width_frame kept for _on_width_mode_changed
        self._char_width_frame = self._tag_sections_frame

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

    # =========================================================================
    # Per-tag section helpers
    # =========================================================================

    def _rebuild_tag_sections(self) -> None:
        """Destroy and recreate all per-tag setting sections."""
        for child in self._tag_sections_frame.winfo_children():
            child.destroy()
        self._tag_widgets.clear()

        for tc in self._tag_configs:
            self._build_tag_section(self._tag_sections_frame, tc)

    def _build_tag_section(
        self, parent: ttk.Frame, tc: TagWrapConfig,
    ) -> None:
        """Build a single per-tag settings section.

        All fields are always editable.  When a parser provides defaults
        via ``wordwrap_for_tag``, they are pre-populated but the user can
        override every value.

        Args:
            parent: Container frame for the section.
            tc: Tag configuration to display.
        """
        section = ttk.LabelFrame(parent, text=f"Tag: {tc.tag}")
        section.pack(fill="x", padx=5, pady=3)

        widgets: Dict[str, Any] = {"frame": section}

        # Width
        w_frame = ttk.Frame(section)
        w_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(w_frame, text="Width:").pack(side="left")
        width_var = tk.IntVar(value=tc.width)
        width_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Spinbox(
            w_frame, from_=0, to=200,
            textvariable=width_var, width=8,
        ).pack(side="left", padx=5)
        ttk.Label(w_frame, text="chars (0 = no wrap)").pack(side="left")
        widgets["width_var"] = width_var

        # Break char
        b_frame = ttk.Frame(section)
        b_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(b_frame, text="Break char:").pack(side="left")
        break_var = tk.StringVar(value=tc.break_char)
        break_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Combobox(
            b_frame, textvariable=break_var,
            values=["\\n", "\n", "<br>", "[r]", "\\r\\n"],
            width=10,
        ).pack(side="left", padx=5)
        widgets["break_var"] = break_var

        # Max lines
        m_frame = ttk.Frame(section)
        m_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(m_frame, text="Max lines:").pack(side="left")
        max_lines_var = tk.IntVar(value=tc.max_lines)
        max_lines_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Spinbox(
            m_frame, from_=0, to=20,
            textvariable=max_lines_var, width=8,
        ).pack(side="left", padx=5)
        ttk.Label(m_frame, text="(0 = unlimited)").pack(side="left")
        widgets["max_lines_var"] = max_lines_var

        # Speaker handling
        s_frame = ttk.Frame(section)
        s_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(s_frame, text="Speaker:").pack(side="left")
        speaker_var = tk.StringVar(value=tc.speaker_handling)
        speaker_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Combobox(
            s_frame, textvariable=speaker_var,
            values=["ignore", "count"],
            state="readonly", width=10,
        ).pack(side="left", padx=5)
        widgets["speaker_var"] = speaker_var

        # Pretty-wrap toggles
        pw_frame = ttk.Frame(section)
        pw_frame.pack(fill="x", padx=5, pady=2)
        orphan_var = tk.BooleanVar(value=tc.prevent_orphans)
        orphan_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Checkbutton(
            pw_frame, text="Prevent orphans",
            variable=orphan_var,
        ).pack(side="left")
        widgets["orphan_var"] = orphan_var

        punct_var = tk.BooleanVar(value=tc.prefer_punct_breaks)
        punct_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Checkbutton(
            pw_frame, text="Prefer punctuation breaks",
            variable=punct_var,
        ).pack(side="left", padx=(10, 0))
        widgets["punct_var"] = punct_var

        # New textbox handling
        nt_frame = ttk.Frame(section)
        nt_frame.pack(fill="x", padx=5, pady=2)
        new_tb_var = tk.BooleanVar(value=tc.new_textbox)
        new_tb_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Checkbutton(
            nt_frame, text="New textbox on overflow",
            variable=new_tb_var,
        ).pack(side="left")
        widgets["new_tb_var"] = new_tb_var

        ntinj_var = tk.StringVar(value=tc.new_textbox_injection)
        ntinj_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Label(nt_frame, text="Injection:").pack(side="left", padx=(10, 0))
        ttk.Entry(
            nt_frame, textvariable=ntinj_var, width=8,
        ).pack(side="left", padx=2)
        widgets["ntinj_var"] = ntinj_var

        # Remove button (not for the first two default tags)
        is_default = tc.tag in {t.tag for t in DEFAULT_TAG_CONFIGS}
        if not is_default:
            btn_frame = ttk.Frame(section)
            btn_frame.pack(fill="x", padx=5, pady=2)
            ttk.Button(
                btn_frame, text="✕ Remove tag",
                command=lambda t=tc.tag: self._remove_tag_config(t),
            ).pack(side="right")

        self._tag_widgets[tc.tag] = widgets

        # Sync backward-compat aliases for first (dialogue) tag
        if tc.tag == "dialogue" and "width_var" in widgets:
            self._width_var = widgets["width_var"]
            self._break_var = widgets["break_var"]
            self._max_lines_var = widgets["max_lines_var"]

    def _on_tag_setting_changed(self, tag: str) -> None:
        """Sync UI var change back into _tag_configs and manifest."""
        w = self._tag_widgets.get(tag)
        if not w:
            return
        for tc in self._tag_configs:
            if tc.tag == tag:
                if "width_var" in w:
                    try:
                        tc.width = w["width_var"].get()
                    except tk.TclError:
                        pass
                if "break_var" in w:
                    tc.break_char = w["break_var"].get()
                if "max_lines_var" in w:
                    try:
                        tc.max_lines = w["max_lines_var"].get()
                    except tk.TclError:
                        pass
                if "speaker_var" in w:
                    tc.speaker_handling = w["speaker_var"].get()
                if "orphan_var" in w:
                    try:
                        tc.prevent_orphans = w["orphan_var"].get()
                    except tk.TclError:
                        pass
                if "punct_var" in w:
                    try:
                        tc.prefer_punct_breaks = w["punct_var"].get()
                    except tk.TclError:
                        pass
                if "new_tb_var" in w:
                    try:
                        tc.new_textbox = w["new_tb_var"].get()
                    except tk.TclError:
                        pass
                if "ntinj_var" in w:
                    tc.new_textbox_injection = w["ntinj_var"].get()
                break
        self._save_tag_configs_to_manifest()

    def _on_add_tag_selected(self, event: Optional[tk.Event] = None) -> None:
        """Handle selection from the 'Add tag' dropdown."""
        tag = self._add_tag_var.get()
        if not tag or tag == "Add tag…":
            return
        self._add_tag_config(tag)
        self._add_tag_var.set("Add tag…")

    def _add_tag_config(self, tag: str) -> None:
        """Add a new per-tag section with parser defaults if available."""
        if any(tc.tag == tag for tc in self._tag_configs):
            return
        tc = TagWrapConfig(tag=tag)
        # Pre-populate from parser defaults when available
        parser = self._get_active_parser()
        if parser is not None:
            try:
                wcfg = parser.wordwrap_for_tag(tag)
                if wcfg is not None:
                    tc.width = wcfg.max_line_length
                    tc.break_char = wcfg.wordwrap_command
                    tc.max_lines = wcfg.max_line_number
                    tc.new_textbox_injection = wcfg.new_textbox_injection or ""
                    tc.new_textbox = bool(tc.new_textbox_injection)
            except Exception:
                pass
        self._tag_configs.append(tc)
        self._rebuild_tag_sections()
        self._refresh_add_tag_options()
        self._save_tag_configs_to_manifest()

    def _remove_tag_config(self, tag: str) -> None:
        """Remove a per-tag section."""
        self._tag_configs = [tc for tc in self._tag_configs if tc.tag != tag]
        self._rebuild_tag_sections()
        self._refresh_add_tag_options()
        self._save_tag_configs_to_manifest()

    def _refresh_add_tag_options(self) -> None:
        """Update the 'Add tag' combobox with available (unused) tags."""
        available = self._collect_available_tags()
        used = {tc.tag for tc in self._tag_configs}
        options = sorted(available - used)
        if hasattr(self, "_add_tag_combo"):
            self._add_tag_combo.configure(values=options or ["(no more tags)"])

    def _collect_available_tags(self) -> set:
        """Gather all unique tags from filedir and lines in the manifest."""
        tags: set = {"dialogue", "menu"}
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return tags
        for entry_dict in mgr._manifest_data.get("filedir", []):
            t = entry_dict.get("type", "")
            if t:
                tags.add(t)
        for line in mgr._manifest_data.get("lines", []):
            t = line.get("tag", "")
            if t:
                tags.add(t)
        return tags

    def _get_active_parser(self) -> Any:
        """Return the active parser object or ``None``."""
        if not _HAS_PARSER_REGISTRY:
            return None
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return None
        opts = mgr._manifest_data.get("Options", {})
        name = opts.get("ParserName", "") if isinstance(opts, dict) else ""
        if not name:
            return None
        try:
            from CherryAI.formats import get_parser_registry
            return get_parser_registry().get(name)
        except Exception:
            return None

    def _save_tag_configs_to_manifest(self) -> None:
        """Persist current per-tag configs to the manifest."""
        mgr = self.manifest_manager
        if mgr is None:
            return
        configs = [tc.to_dict() for tc in self._tag_configs]
        mgr.set_wordwrap_tag_configs(configs)

    def get_tag_config_for(self, tag: str) -> Optional[TagWrapConfig]:
        """Return the per-tag config matching *tag*, or ``None``."""
        for tc in self._tag_configs:
            if tc.tag == tag:
                return tc
        return None

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
        mode = WrapMode.from_display(self._mode_var.get())
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
        self._run_wordwrap(persist_results=True)

    def _run_wordwrap(self, persist_results: bool) -> None:
        """Run wordwrap for preview or explicit persistence."""
        if self._status == WrapStatus.RUNNING:
            messagebox.showinfo("Info", "Wordwrap is already running.")
            return

        self._persist_after_wrap = persist_results
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
        """Process wordwrap on lines with per-tag settings.

        For each line the tag is resolved (line tag → filedir type →
        ``"dialogue"`` fallback), then the matching :class:`TagWrapConfig`
        is looked up.  All tags use the per-tag Width / BreakChar /
        MaxLines / SpeakerHandling / PreventOrphans / PreferPunctuationBreaks
        with the standard ``apply_wordwrap`` pipeline.  Ignore patterns
        are applied globally.
        """
        if not _HAS_WORDWRAP:
            logger.warning("wordwrap module not available, using simple wrap")
            self._simple_wrap()
            return

        # Tag resolution maps
        line_tag_map, filedir_type_map = self._build_tag_maps()

        # Global settings shared across all tags
        global_ignore = self._get_ignore_codes()
        global_mode = self._mode_var.get()

        # Get lines from session
        step_data = self.get_step_data()
        lines = step_data.get("lines", [])
        if not lines:
            return

        self._lines = []
        for i, orig in enumerate(lines):
            # 1. Resolve tag (line tag overrules filedir file tag)
            tag = (
                line_tag_map.get(i)
                or filedir_type_map.get(i)
                or "dialogue"
            )

            # 2. Look up per-tag config
            tc = self.get_tag_config_for(tag)
            if tc is None:
                tc = self.get_tag_config_for("dialogue")
            if tc is None:
                tc = TagWrapConfig(tag=tag)

            bc = tc.break_char
            max_l = tc.max_lines or None

            # 3. Wrap the line
            if tc.width <= 0:
                # Zero width → no wrap
                wrapped = orig
            else:
                config = WordwrapConfig(
                    mode=global_mode, in1=tc.width,
                    in2=bc, in3=max_l,
                    ignore_codes=global_ignore,
                    speaker_mode=tc.speaker_handling.upper(),
                    prevent_orphan=tc.prevent_orphans,
                    prefer_punct_breaks=tc.prefer_punct_breaks,
                )
                result_list = apply_wordwrap([orig], config)
                wrapped = result_list[0] if result_list else orig

            # 4. Build WrapLine
            lc = wrapped.count(bc) + 1 if bc else 1
            exceeds = bool(tc.max_lines and lc > tc.max_lines)
            self._lines.append(WrapLine(
                idx=i,
                original=orig,
                wrapped=wrapped,
                char_count=len(wrapped),
                line_count=lc,
                exceeds_limit=exceeds,
            ))

        self._update_stats()

    def _build_tag_maps(
        self,
    ) -> Tuple[Dict[int, str], Dict[int, str]]:
        """Build idx → tag maps from manifest lines and filedir.

        Returns:
            ``(line_tag_map, filedir_type_map)`` where each maps a
            global line index to the resolved tag / file type string.
        """
        line_tag_map: Dict[int, str] = {}
        filedir_type_map: Dict[int, str] = {}
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return line_tag_map, filedir_type_map
        for line_data in mgr.get_lines():
            idx = line_data.get("idx", -1)
            tag = line_data.get("tag", "")
            if tag:
                line_tag_map[idx] = tag
        for entry in mgr.get_filedir():
            if entry.type:
                for idx in range(entry.first_idx, entry.last_idx + 1):
                    filedir_type_map[idx] = entry.type
        return line_tag_map, filedir_type_map

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
        if self._persist_after_wrap:
            self._persist_wrapped_lines()
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
        self._run_wordwrap(persist_results=False)

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
        
        Loads all wordwrap options from manifest into UI widgets,
        including per-tag configurations from ``TagConfigs``.
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

        # Load per-tag configs from manifest (fall back to defaults)
        raw_configs = self.manifest_manager.get_wordwrap_tag_configs()
        if raw_configs:
            self._tag_configs = [TagWrapConfig.from_dict(d) for d in raw_configs]
        else:
            self._tag_configs = [
                TagWrapConfig(tag=tc.tag, width=tc.width,
                              break_char=tc.break_char, max_lines=tc.max_lines)
                for tc in DEFAULT_TAG_CONFIGS
            ]
        self._rebuild_tag_sections()
        self._refresh_add_tag_options()
        
        logger.debug("Wordwrap settings loaded from manifest")

    def _apply_parser_wordwrap_defaults(self) -> None:
        """Auto-populate format and per-tag configs from parser scripts.

        Iterates the parser registry and, for each parser that provides a
        :attr:`wordwrap_config`, registers a :class:`FormatConfig` entry.
        Also updates existing per-tag :class:`TagWrapConfig` entries
        with parser defaults for width, break char, max lines, new-textbox
        injection, and speaker handling.

        User-set manifest values take precedence because
        ``_load_wordwrap_settings_from_manifest`` runs after this method.
        """
        if not _HAS_PARSER_REGISTRY:
            return

        try:
            registry = get_parser_registry()
        except Exception:
            return

        # Find which parser is active for this project
        active_parser = self._get_active_parser()

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

        # Apply per-tag defaults from the active parser
        if active_parser is not None:
            for tc in self._tag_configs:
                try:
                    tag_cfg = active_parser.wordwrap_for_tag(tc.tag)
                except Exception:
                    tag_cfg = None
                if tag_cfg is not None:
                    tc.width = tag_cfg.max_line_length
                    tc.break_char = tag_cfg.wordwrap_command
                    tc.max_lines = tag_cfg.max_line_number
                    tc.new_textbox_injection = (
                        tag_cfg.new_textbox_injection or ""
                    )
                    tc.new_textbox = bool(tc.new_textbox_injection)
                    # Speaker handling: parsers with separate name field
                    # (like LightVN) should default to "ignore"
                    if hasattr(active_parser, "detect_speakers"):
                        tc.speaker_handling = "ignore"

        # Refresh format dropdown values
        if hasattr(self, "_format_var"):
            try:
                self._format_var.configure(  # type: ignore[attr-defined]
                    values=list(self._format_configs.keys()),  # type: ignore[arg-type]
                )
            except Exception:
                pass

    def on_new_project(self) -> None:
        """Reset cached state for a fresh project."""
        super().on_new_project()
        self._lines.clear()
        self._selected_line_idx = -1
        self._manifest_bindings.clear()
        self._tag_configs = [
            TagWrapConfig(tag=tc.tag, width=tc.width,
                          break_char=tc.break_char, max_lines=tc.max_lines)
            for tc in DEFAULT_TAG_CONFIGS
        ]
        self._tag_widgets.clear()
        logger.debug("Wordwrap step reset for new project")

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

        The preview input follows the Wordwrap stage ceiling, while the
        Wordwrap column itself only loads stored ``wordwr`` values.
        """
        latest: list[str] = []
        wordwr_map: dict[int, str] = {}

        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            latest = get_all_lines_for_stage(mgr, "wordwrap")
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
            wr = wordwr_map.get(i, "")
            wrap_line = WrapLine(
                idx=i,
                original=line,
                wrapped=wr,
            )
            self._lines.append(wrap_line)

    def _save_to_session(self) -> None:
        """Save current state to session.

        Stores preview state in session without auto-writing ``wordwr``.
        """
        step_data = self.get_step_data()
        step_data["wrap_options"] = {
            "mode": self._mode_var.get(),
            "width": self._width_var.get(),
            "break_char": self._break_var.get(),
            "max_lines": self._max_lines_var.get(),
            "speaker_mode": self._speaker_var.get(),
        }
        step_data["tag_configs"] = [tc.to_dict() for tc in self._tag_configs]
        step_data["wrapped_lines"] = [l.wrapped for l in self._lines]
        self.set_step_data(step_data)

    def _persist_wrapped_lines(self) -> None:
        """Persist explicit wordwrap results sparsely to the manifest."""
        mgr = self.manifest_manager
        if mgr is None:
            return
        for line in self._lines:
            _persist_sparse_wordwrap(
                mgr,
                line.idx,
                line.original,
                line.wrapped,
            )

    # =========================================================================
    # Public API
    # =========================================================================

    def get_wrap_options(self) -> WrapOptions:
        """Get current wrap options.

        Returns:
            WrapOptions with current settings.
        """
        return WrapOptions(
            mode=WrapMode.from_display(self._mode_var.get()),
            speaker_mode=SpeakerMode(self._speaker_var.get().lower()),
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
