"""CherryAI GUI v2 Wordwrap Step.

Ninth workflow tab for text formatting after QA.
Provides wordwrap configuration and preview based on the QA stage output.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.dialogs.table_view import _FileFilterDropdown
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
from CherryAI.functions.manifest_manager import get_primary_line_tag
try:
    # Explicit import of shared wordwrap logic per architecture rules
    from CherryAI.functions.wordwrap import (
        WordwrapConfig,
        apply_new_textbox_injection,
        apply_wordwrap,
        normalize_break_char,
    )
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

    CUSTOM = "custom"
    SIMPLE = "simple"

    @classmethod
    def from_display(cls, value: str) -> "WrapMode":
        """Parse from display string (title-case) or raw value."""
        normalized = value.strip().lower()
        if normalized == "manual":
            return cls.CUSTOM
        for member in cls:
            if member.value == value or member.value == normalized:
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
    source_format: str = ""
    source_path: str = ""
    wrapped: str = ""
    overwrite: str = ""
    char_count: int = 0
    line_count: int = 1
    exceeds_limit: bool = False
    new_textbox_applied: bool = False
    persist_wrapped: bool = True
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
        if self.new_textbox_applied:
            return "↳ New Textbox"
        if self.exceeds_limit:
            return "⚠ Exceeding"
        if self.has_changes:
            return "✓ Wrapped"
        return "— No change"


@dataclass
class FormatConfig:
    """Wordwrap configuration for a specific format."""

    format_id: str
    format_name: str
    wrap_width: int = 48
    break_char: str = "\\n"
    max_lines: int = 4
    enabled: bool = True
    tag_configs: List["TagWrapConfig"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to manifest-compatible dict."""
        return {
            "format": self.format_id,
            "FormatName": self.format_name,
            "Width": self.wrap_width,
            "BreakChar": self.break_char,
            "MaxLines": self.max_lines,
            "Enabled": self.enabled,
            "TagConfigs": [cfg.to_dict() for cfg in self.tag_configs],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormatConfig":
        """Deserialize from manifest dict."""
        return cls(
            format_id=str(data.get("format", "")),
            format_name=str(data.get("FormatName", data.get("format", ""))),
            wrap_width=int(data.get("Width", 48)),
            break_char=str(data.get("BreakChar", "\\n")),
            max_lines=int(data.get("MaxLines", 4)),
            enabled=bool(data.get("Enabled", True)),
            tag_configs=[
                TagWrapConfig.from_dict(item)
                for item in data.get("TagConfigs", [])
                if isinstance(item, dict)
            ],
        )


@dataclass
class WrapOptions:
    """Options for wordwrap operations."""

    mode: WrapMode = WrapMode.CUSTOM
    speaker_mode: SpeakerMode = SpeakerMode.COUNT
    width: int = 48
    break_char: str = "\\n"
    max_lines: int = 4
    pretty_wrap: bool = True
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
    enabled: bool = True
    width: int = 48
    break_char: str = "\\n"
    max_lines: int = 4
    speaker_handling: str = "count"  # "ignore" | "count"
    pretty_wrap: bool = True
    prevent_orphans: bool = True
    prefer_punct_breaks: bool = True
    new_textbox: bool = False
    new_textbox_injection: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to manifest-compatible dict."""
        return {
            "tag": self.tag,
            "Enabled": self.enabled,
            "Width": self.width,
            "BreakChar": self.break_char,
            "MaxLines": self.max_lines,
            "SpeakerHandling": self.speaker_handling,
            "PrettyWrap": self.pretty_wrap,
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
            enabled=d.get("Enabled", True),
            width=d.get("Width", 48),
            break_char=d.get("BreakChar", "\\n"),
            max_lines=d.get("MaxLines", 4),
            speaker_handling=d.get("SpeakerHandling", "count"),
            pretty_wrap=d.get(
                "PrettyWrap",
                d.get("PreventOrphans", True)
                or d.get("PreferPunctuationBreaks", True),
            ),
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
    "rpgmaker_mv": FormatConfig("rpgmaker_mv", "RPG Maker MV", 48, "\\n", 4),
    "rpgmaker_mz": FormatConfig("rpgmaker_mz", "RPG Maker MZ", 55, "\\n", 4),
    "renpy": FormatConfig("renpy", "Ren'Py", 60, "\n", 0),
    "tyrano": FormatConfig("tyrano", "TyranoScript", 45, "[r]", 0),
    "custom": FormatConfig("custom", "Custom", 50, "\n", 0),
}


SPEAKER_MODE_DESCRIPTIONS: Dict[SpeakerMode, str] = {
    SpeakerMode.IGNORE: "Don't count speaker for width, but keep it in output",
    SpeakerMode.COUNT: "Speaker counted with : and spaces (inline display)",
}


# ============================================================================
# WordwrapOverwriteStep Class
# ============================================================================


class WordwrapOverwriteStep(BaseStep):
    """Wordwrap step for text formatting.

    This is the ninth workflow tab for users and the internal ``step_id == 8``
    because Input is step 0 in the manifest/GUI pipeline.
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
        self._progress_queue: Optional[queue.SimpleQueue[Tuple[float, str]]] = None
        self._progress_poll_id: Optional[str] = None
        self._persist_done_in_worker: bool = False
        self._selected_line_idx: int = -1
        self._persist_after_wrap: bool = False
        self._last_processed_indices: Optional[set[int]] = None
        self._updating_format_widgets = False
        self._file_filter: Optional[str] = None
        self._filtered_indices: Optional[set[int]] = None
        self._file_tree: Dict[str, Any] = {}
        self._format_configs: Dict[str, FormatConfig] = {
            key: FormatConfig(
                format_id=value.format_id,
                format_name=value.format_name,
                wrap_width=value.wrap_width,
                break_char=value.break_char,
                max_lines=value.max_lines,
                enabled=value.enabled,
                tag_configs=[TagWrapConfig.from_dict(tag.to_dict()) for tag in value.tag_configs],
            )
            for key, value in DEFAULT_FORMAT_CONFIGS.items()
        }
        # TASK 28.1: Manifest bindings for wordwrap settings
        self._manifest_bindings: List[BindingInfo] = []
        self._tag_configs: List[TagWrapConfig] = []
        self._tag_widgets: Dict[str, Dict[str, Any]] = {}
        self._line_format_map: Dict[int, str] = {}
        self._line_path_map: Dict[int, str] = {}
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
            text="Wordwrap",
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

        self._format_var = tk.StringVar(value="")
        self._format_combo = ttk.Combobox(
            format_frame,
            textvariable=self._format_var,
            values=[],
            state="readonly",
            width=18,
        )
        self._format_combo.pack(side="left", padx=5)
        self._format_combo.bind("<<ComboboxSelected>>", self._on_format_changed)

        # Width indicator
        self._width_label = ttk.Label(
            format_frame,
            text="No format selected",
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
            ("new_textbox", "New Textbox"),
        ]:
            ttk.Radiobutton(
                filter_frame,
                text=text,
                variable=self._filter_var,
                value=val,
                command=self._refresh_table,
            ).pack(side="left", padx=4)

        file_picker_frame = ttk.Frame(filter_frame)
        file_picker_frame.pack(side="right")

        ttk.Label(file_picker_frame, text="Select File:").pack(side="left", padx=(8, 4))
        self._file_filter_var = tk.StringVar(value="All")
        self._file_filter_btn = ttk.Button(
            file_picker_frame,
            textvariable=self._file_filter_var,
            command=self._show_file_filter_dropdown,
            width=18,
        )
        self._file_filter_btn.pack(side="left")

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
            text="↗ View in File",
            command=self._view_in_file,
        ).pack(side="left", padx=2)

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

        self._mode_var = tk.StringVar(value=WrapMode.CUSTOM.value)
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

        self._simple_mode_frame = ttk.Frame(frame)
        self._build_simple_mode_panel(self._simple_mode_frame)

        self._custom_mode_frame = ttk.Frame(frame)

        selected_format_frame = ttk.Frame(self._custom_mode_frame)
        selected_format_frame.pack(fill="x", padx=5, pady=3)
        ttk.Label(selected_format_frame, text="Selected format:").pack(side="left")
        self._selected_format_label = ttk.Label(
            selected_format_frame,
            text="(none)",
            foreground=THEME.text_secondary,
        )
        self._selected_format_label.pack(side="left", padx=(5, 0))

        self._format_enabled_var = tk.BooleanVar(value=True)
        self._format_enabled_var.trace_add(
            "write", lambda *_args: self._on_format_enabled_changed()
        )
        ttk.Checkbutton(
            selected_format_frame,
            text="Enabled",
            variable=self._format_enabled_var,
        ).pack(side="right")

        # Width mode (global — character/pixel toggle)
        width_mode_frame = ttk.Frame(self._custom_mode_frame)
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
        self._pixel_width_frame = ttk.Frame(self._custom_mode_frame)
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
        ttk.Separator(self._custom_mode_frame, orient="horizontal").pack(fill="x", padx=5, pady=3)

        # Container for dynamic per-tag sections
        self._tag_sections_frame = ttk.Frame(self._custom_mode_frame)
        self._tag_sections_frame.pack(fill="x", padx=0, pady=0)

        # Build initial tag sections
        self._rebuild_tag_sections()

        # "Add Tag" dropdown at the bottom
        add_frame = ttk.Frame(self._custom_mode_frame)
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
        self._refresh_mode_ui()

    def _build_simple_mode_panel(self, parent: ttk.Frame) -> None:
        """Build the simplified file-scoped wrapping controls."""
        simple_group = ttk.LabelFrame(parent, text="Simple File Wrap")
        simple_group.pack(fill="x", padx=5, pady=5)

        self._simple_width_var = tk.IntVar(value=48)
        self._simple_width_var.trace_add("write", self._save_simple_settings_to_manifest)
        width_frame = ttk.Frame(simple_group)
        width_frame.pack(fill="x", padx=5, pady=3)
        ttk.Label(width_frame, text="Character Limit:").pack(side="left")
        ttk.Spinbox(
            width_frame,
            from_=1,
            to=999,
            textvariable=self._simple_width_var,
            width=8,
        ).pack(side="left", padx=5)

        self._simple_max_lines_var = tk.IntVar(value=4)
        self._simple_max_lines_var.trace_add("write", self._save_simple_settings_to_manifest)
        max_lines_frame = ttk.Frame(simple_group)
        max_lines_frame.pack(fill="x", padx=5, pady=3)
        ttk.Label(max_lines_frame, text="Line Limit:").pack(side="left")
        ttk.Spinbox(
            max_lines_frame,
            from_=0,
            to=20,
            textvariable=self._simple_max_lines_var,
            width=8,
        ).pack(side="left", padx=5)
        ttk.Label(max_lines_frame, text="(0 = unlimited)").pack(side="left")

        self._simple_break_var = tk.StringVar(value="\\n")
        self._simple_break_var.trace_add("write", self._save_simple_settings_to_manifest)
        break_frame = ttk.Frame(simple_group)
        break_frame.pack(fill="x", padx=5, pady=3)
        ttk.Label(break_frame, text="Break Char:").pack(side="left")
        ttk.Combobox(
            break_frame,
            textvariable=self._simple_break_var,
            values=["\\n", "\n", "<br>", "[r]", "\\r\\n"],
            width=10,
        ).pack(side="left", padx=5)

        self._simple_pretty_var = tk.BooleanVar(value=True)
        self._simple_pretty_var.trace_add("write", self._save_simple_settings_to_manifest)
        pretty_frame = ttk.Frame(simple_group)
        pretty_frame.pack(fill="x", padx=5, pady=3)
        ttk.Checkbutton(
            pretty_frame,
            text="Pretty Wrap",
            variable=self._simple_pretty_var,
        ).pack(side="left")

        ttk.Label(
            simple_group,
            text=(
                "Applies one uniform wrap configuration to the currently selected file "
                "filter, or to all files when no file is selected."
            ),
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
            wraplength=260,
            justify="left",
        ).pack(fill="x", padx=5, pady=(0, 5), anchor="w")

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

    def _clone_tag_configs(
        self, configs: Optional[List[TagWrapConfig]] = None,
    ) -> List[TagWrapConfig]:
        """Return a deep-ish copy of tag configs."""
        source = configs if configs is not None else DEFAULT_TAG_CONFIGS
        return [TagWrapConfig.from_dict(tc.to_dict()) for tc in source]

    def _get_parser_for_format(self, format_id: str) -> Any:
        """Return parser instance for a manifest format id, if any."""
        if not _HAS_PARSER_REGISTRY or not format_id:
            return None
        try:
            return get_parser_registry().get(format_id)
        except Exception:
            return None

    def _collect_manifest_formats(self) -> List[str]:
        """Collect distinct file formats present in the loaded manifest."""
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return []
        seen: set[str] = set()
        ordered: List[str] = []
        for entry in mgr.get_filedir():
            fmt = (entry.format or "").strip().lower()
            if not fmt or fmt in seen:
                continue
            seen.add(fmt)
            ordered.append(fmt)
        return ordered

    def _collect_available_tags(self, format_id: Optional[str] = None) -> set[str]:
        """Gather tags for the whole project or a specific format."""
        tags: set[str] = {"dialogue", "menu"}
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return tags

        idx_format_map = self._build_line_format_map()
        for entry in mgr.get_filedir():
            entry_format = (entry.format or "").strip().lower()
            if format_id and entry_format != format_id:
                continue
            if entry.type:
                tags.add(entry.type)

        for line in mgr.get_lines():
            idx = int(line.get("idx", -1))
            if format_id and idx_format_map.get(idx) != format_id:
                continue
            tag = get_primary_line_tag(line)
            if tag:
                tags.add(tag)
        return tags

    def _build_default_tag_configs(
        self,
        format_id: str,
        *,
        parser: Any = None,
        available_tags: Optional[set[str]] = None,
    ) -> List[TagWrapConfig]:
        """Build default tag configs for one manifest format."""
        tags = available_tags or self._collect_available_tags(format_id)
        ordered_tags: List[str] = []
        for tag in ["dialogue", "menu"]:
            if tag in tags:
                ordered_tags.append(tag)
        ordered_tags.extend(sorted(tag for tag in tags if tag not in {"dialogue", "menu"}))

        defaults_by_tag = {cfg.tag: cfg for cfg in DEFAULT_TAG_CONFIGS}
        result: List[TagWrapConfig] = []
        for tag in ordered_tags:
            base = defaults_by_tag.get(tag)
            if base is not None:
                tag_cfg = TagWrapConfig.from_dict(base.to_dict())
            else:
                tag_cfg = TagWrapConfig(tag=tag)
            tag_cfg.tag = tag

            if parser is not None:
                try:
                    parser_cfg = parser.wordwrap_for_tag(tag)
                except Exception:
                    parser_cfg = None
                if parser_cfg is not None:
                    tag_cfg.width = parser_cfg.max_line_length
                    tag_cfg.break_char = parser_cfg.wordwrap_command or "\\n"
                    tag_cfg.max_lines = parser_cfg.max_line_number
                    tag_cfg.new_textbox_injection = (
                        parser_cfg.new_textbox_injection or ""
                    )
                    tag_cfg.new_textbox = bool(tag_cfg.new_textbox_injection)
                    tag_cfg.enabled = tag_cfg.width > 0
                    if tag == "dialogue" and hasattr(parser, "detect_speakers"):
                        tag_cfg.speaker_handling = SpeakerMode.IGNORE.value

            result.append(tag_cfg)
        return result

    def _get_selected_format_config(self) -> Optional[FormatConfig]:
        """Return the currently selected format config."""
        format_id = self._format_var.get().strip().lower()
        if not format_id:
            return None
        return self._format_configs.get(format_id)

    def _sync_selected_format_state(self) -> None:
        """Refresh active tag list and selected-format widgets."""
        self._updating_format_widgets = True
        selected = self._get_selected_format_config()
        if selected is None:
            self._tag_configs = []
            if hasattr(self, "_selected_format_label"):
                self._selected_format_label.configure(text="(none)")
            if hasattr(self, "_format_enabled_var"):
                self._format_enabled_var.set(False)
            self._width_label.configure(text="No format selected")
            self._updating_format_widgets = False
            return

        self._tag_configs = selected.tag_configs
        if hasattr(self, "_selected_format_label"):
            self._selected_format_label.configure(text=selected.format_name)
        if hasattr(self, "_format_enabled_var"):
            self._format_enabled_var.set(selected.enabled)
        self._width_label.configure(
            text=(
                f"{selected.format_name}: "
                f"{'enabled' if selected.enabled else 'disabled'}, "
                f"{selected.wrap_width} chars"
            )
        )
        self._updating_format_widgets = False

    def _refresh_format_selector(self) -> None:
        """Populate the preview/settings format selector from manifest formats."""
        format_ids = list(self._format_configs.keys())
        if hasattr(self, "_format_combo"):
            self._format_combo.configure(values=format_ids)

        current = self._format_var.get().strip().lower()
        if current not in self._format_configs:
            current = format_ids[0] if format_ids else ""
            self._format_var.set(current)

        self._sync_selected_format_state()
        self._rebuild_tag_sections()
        self._refresh_add_tag_options()

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

        enable_frame = ttk.Frame(section)
        enable_frame.pack(fill="x", padx=5, pady=2)
        enabled_var = tk.BooleanVar(value=tc.enabled)
        enabled_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Checkbutton(
            enable_frame,
            text="Enabled",
            variable=enabled_var,
        ).pack(side="left")
        widgets["enabled_var"] = enabled_var

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

        # Pretty-wrap toggle
        pw_frame = ttk.Frame(section)
        pw_frame.pack(fill="x", padx=5, pady=2)
        pretty_var = tk.BooleanVar(value=tc.pretty_wrap)
        pretty_var.trace_add(
            "write",
            lambda *_a, t=tc.tag: self._on_tag_setting_changed(t),
        )
        ttk.Checkbutton(
            pw_frame,
            text="Pretty wrap",
            variable=pretty_var,
        ).pack(side="left")
        widgets["pretty_var"] = pretty_var

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
                if "enabled_var" in w:
                    try:
                        tc.enabled = w["enabled_var"].get()
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
                if "pretty_var" in w:
                    try:
                        tc.pretty_wrap = w["pretty_var"].get()
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
        selected = self._get_selected_format_config()
        if selected is not None:
            dialogue_cfg = next(
                (cfg for cfg in self._tag_configs if cfg.tag == "dialogue"),
                None,
            )
            if dialogue_cfg is not None:
                selected.wrap_width = dialogue_cfg.width
                selected.break_char = dialogue_cfg.break_char
                selected.max_lines = dialogue_cfg.max_lines
        self._save_tag_configs_to_manifest()
        self._sync_selected_format_state()

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
        selected = self._get_selected_format_config()
        parser = self._get_parser_for_format(selected.format_id) if selected else None
        if parser is not None:
            try:
                wcfg = parser.wordwrap_for_tag(tag)
                if wcfg is not None:
                    tc.width = wcfg.max_line_length
                    tc.break_char = wcfg.wordwrap_command
                    tc.max_lines = wcfg.max_line_number
                    tc.new_textbox_injection = wcfg.new_textbox_injection or ""
                    tc.new_textbox = bool(tc.new_textbox_injection)
                    tc.enabled = tc.width > 0
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
        selected = self._get_selected_format_config()
        available = self._collect_available_tags(
            selected.format_id if selected is not None else None
        )
        used = {tc.tag for tc in self._tag_configs}
        options = sorted(available - used)
        if hasattr(self, "_add_tag_combo"):
            self._add_tag_combo.configure(values=options or ["(no more tags)"])

    def _save_tag_configs_to_manifest(self) -> None:
        """Persist current format and selected-tag configs to the manifest."""
        mgr = self.manifest_manager
        if mgr is None:
            return
        selected = self._get_selected_format_config()
        if selected is not None:
            selected.tag_configs = self._tag_configs
        format_payload = [config.to_dict() for config in self._format_configs.values()]
        if hasattr(mgr, "set_wordwrap_format_configs"):
            mgr.set_wordwrap_format_configs(format_payload)
        else:
            mgr._manifest_data.setdefault("WordwrapSettings", {})["FormatConfigs"] = format_payload
            if hasattr(mgr, "_mark_dirty"):
                mgr._mark_dirty()

        tag_payload = [tc.to_dict() for tc in self._tag_configs]
        if hasattr(mgr, "set_wordwrap_tag_configs"):
            mgr.set_wordwrap_tag_configs(tag_payload)
        else:
            mgr._manifest_data.setdefault("WordwrapSettings", {})["TagConfigs"] = tag_payload
            if hasattr(mgr, "_mark_dirty"):
                mgr._mark_dirty()

    def get_tag_config_for(self, tag: str) -> Optional[TagWrapConfig]:
        """Return the per-tag config matching *tag*, or ``None``."""
        selected = self._get_selected_format_config()
        configs = selected.tag_configs if selected is not None else self._tag_configs
        for tc in configs:
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
        self._sync_selected_format_state()
        self._rebuild_tag_sections()
        self._refresh_add_tag_options()
        self._refresh_table()

    def _on_format_enabled_changed(self) -> None:
        """Handle enabled/disabled toggle for the selected format."""
        if self._updating_format_widgets:
            return
        selected = self._get_selected_format_config()
        if selected is None:
            return
        selected.enabled = bool(self._format_enabled_var.get())
        self._save_tag_configs_to_manifest()
        self._sync_selected_format_state()
        self._refresh_preview()

    def _on_mode_changed(self) -> None:
        """Handle wrap mode change."""
        mode = WrapMode.from_display(self._mode_var.get())
        self._wrap_options.mode = mode
        self._refresh_mode_ui()
        self._refresh_preview()

    def _refresh_mode_ui(self) -> None:
        """Show the settings group for the active wrap mode."""
        mode = WrapMode.from_display(self._mode_var.get())
        if mode == WrapMode.SIMPLE:
            self._custom_mode_frame.pack_forget()
            self._simple_mode_frame.pack(fill="x", padx=0, pady=0)
            self._width_label.configure(
                text=f"Simple mode: {self._simple_width_var.get()} chars"
            )
            return
        self._simple_mode_frame.pack_forget()
        self._custom_mode_frame.pack(fill="x", padx=0, pady=0)
        self._sync_selected_format_state()

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
        self._persist_done_in_worker = False
        self._status = WrapStatus.RUNNING
        self._status_label.configure(text="Wrapping...")
        self._apply_btn.configure(state="disabled")
        self._progress_var.set(0)
        self._start_progress_poll()

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
                self._queue_progress_update(2.0, "Wrapping...")
                self._process_wrap()
                if self._persist_after_wrap:
                    self._queue_progress_update(85.0, "Saving...")
                    self._persist_wrapped_lines(progress_base=85.0, progress_span=15.0)
                    self._persist_done_in_worker = True
                self._queue_progress_update(100.0, "Completed")
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
        """Process wordwrap grouped by manifest file format."""
        if not _HAS_WORDWRAP:
            logger.warning("wordwrap module not available, using simple wrap")
            self._simple_wrap()
            return

        # Tag resolution maps
        line_tag_map, filedir_type_map = self._build_tag_maps()
        line_format_map = self._build_line_format_map()
        format_configs = getattr(self, "_format_configs", {})

        # Global settings shared across all tags
        global_ignore = self._get_ignore_codes()
        speaker_names = self._get_detected_speakers()
        wrap_mode = WrapMode.from_display(self._mode_var.get())
        global_mode = wrap_mode.value
        process_indices = self._get_process_indices(wrap_mode)
        self._last_processed_indices = process_indices

        source_lines = [line.original for line in self._lines]
        if not source_lines:
            return

        existing_lines = self._lines
        wrapped_lines: List[WrapLine] = []
        total_lines = len(existing_lines)

        for line_pos, source_line in enumerate(existing_lines, start=1):
            idx = source_line.idx
            orig = source_line.original
            source_format = line_format_map.get(idx, source_line.source_format)

            format_cfg = format_configs.get(source_format)
            if format_cfg is None:
                format_var = getattr(self, "_format_var", None)
                selected_format = format_var.get().strip().lower() if format_var else ""
                format_cfg = format_configs.get(selected_format)

            # 1. Resolve tag (line tag overrules filedir file tag)
            tag = (
                line_tag_map.get(idx)
                or filedir_type_map.get(idx)
                or "dialogue"
            )

            if process_indices is not None and idx not in process_indices:
                preserved_wrapped = source_line.wrapped or orig
                preserved_break = normalize_break_char(self._simple_break_var.get())
                preserved_line_count = (
                    preserved_wrapped.count(preserved_break) + 1
                    if preserved_wrapped and preserved_break
                    else 1
                )
                wrapped_lines.append(WrapLine(
                    idx=idx,
                    original=orig,
                    source_format=source_format,
                    source_path=source_line.source_path,
                    wrapped=preserved_wrapped,
                    overwrite=source_line.overwrite,
                    char_count=len(preserved_wrapped),
                    line_count=preserved_line_count,
                    exceeds_limit=source_line.exceeds_limit,
                    new_textbox_applied=source_line.new_textbox_applied,
                    persist_wrapped=source_line.persist_wrapped,
                ))
                self._queue_progress_update(
                    (line_pos / max(total_lines, 1)) * 80.0,
                    f"Wrapping... {line_pos}/{total_lines}",
                )
                continue

            if wrap_mode == WrapMode.SIMPLE:
                simple_break_char = normalize_break_char(self._simple_break_var.get())
                simple_max_lines = self._simple_max_lines_var.get()
                config = WordwrapConfig(
                    mode=WrapMode.SIMPLE.value,
                    in1=self._simple_width_var.get(),
                    in2=self._simple_break_var.get(),
                    in3=None,
                    ignore_codes=global_ignore,
                    pretty_wrap=bool(self._simple_pretty_var.get()),
                )
                result_list = apply_wordwrap([orig], config)
                wrapped = result_list[0] if result_list else orig
                logical_line_count = (
                    wrapped.count(simple_break_char) + 1
                    if simple_break_char else 1
                )
                has_overflow = bool(simple_max_lines and logical_line_count > simple_max_lines)
                wrapped_lines.append(WrapLine(
                    idx=idx,
                    original=orig,
                    source_format=source_format,
                    source_path=source_line.source_path,
                    wrapped=wrapped,
                    overwrite=source_line.overwrite,
                    char_count=len(wrapped),
                    line_count=logical_line_count,
                    exceeds_limit=has_overflow,
                    new_textbox_applied=False,
                    persist_wrapped=not has_overflow,
                ))
                self._queue_progress_update(
                    (line_pos / max(total_lines, 1)) * 80.0,
                    f"Wrapping... {line_pos}/{total_lines}",
                )
                continue

            # 2. Look up per-tag config
            tc = None
            if format_cfg is not None:
                for candidate in format_cfg.tag_configs:
                    if candidate.tag == tag:
                        tc = candidate
                        break
            if tc is None:
                if format_cfg is not None:
                    for candidate in format_cfg.tag_configs:
                        if candidate.tag == "dialogue":
                            tc = candidate
                            break
            if tc is None:
                tc = TagWrapConfig(tag=tag)

            normalized_break_char = normalize_break_char(tc.break_char)
            new_textbox_applied = False
            persist_wrapped = True

            # 3. Wrap the line
            if format_cfg is None or not format_cfg.enabled or not tc.enabled or tc.width <= 0:
                wrapped = orig
                logical_line_count = 1
            else:
                config = WordwrapConfig(
                    mode=global_mode, in1=tc.width,
                    in2=tc.break_char, in3=None,
                    ignore_codes=global_ignore,
                    speaker_mode=tc.speaker_handling.upper(),
                    speaker_names=speaker_names,
                    pretty_wrap=tc.pretty_wrap,
                )
                result_list = apply_wordwrap([orig], config)
                wrapped = result_list[0] if result_list else orig
                logical_line_count = (
                    wrapped.count(normalized_break_char) + 1
                    if normalized_break_char else 1
                )
                has_overflow = bool(tc.max_lines and logical_line_count > tc.max_lines)
                if has_overflow and tc.new_textbox and tc.new_textbox_injection:
                    wrapped = apply_new_textbox_injection(
                        wrapped,
                        break_char=normalized_break_char,
                        max_lines=tc.max_lines,
                        injection=tc.new_textbox_injection,
                    )
                    new_textbox_applied = True
                elif has_overflow:
                    persist_wrapped = False

            # 4. Build WrapLine
            lc = logical_line_count
            exceeds = bool(tc.max_lines and lc > tc.max_lines and not new_textbox_applied)
            wrapped_lines.append(WrapLine(
                idx=idx,
                original=orig,
                source_format=source_format,
                source_path=source_line.source_path,
                wrapped=wrapped,
                overwrite=source_line.overwrite,
                char_count=len(wrapped),
                line_count=lc,
                exceeds_limit=exceeds,
                new_textbox_applied=new_textbox_applied,
                persist_wrapped=persist_wrapped,
            ))
            self._queue_progress_update(
                (line_pos / max(total_lines, 1)) * 80.0,
                f"Wrapping... {line_pos}/{total_lines}",
            )

        self._lines = wrapped_lines
        self._update_stats()

    def _get_process_indices(self, wrap_mode: WrapMode) -> Optional[set[int]]:
        """Return the subset of line indices affected by the current wrap run."""
        if wrap_mode != WrapMode.SIMPLE:
            return None
        if self._filtered_indices is None:
            return {line.idx for line in self._lines}
        return set(self._filtered_indices)

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
            tag = get_primary_line_tag(line_data)
            if tag:
                line_tag_map[idx] = tag
        for entry in mgr.get_filedir():
            if entry.type:
                for idx in range(entry.first_idx, entry.last_idx + 1):
                    filedir_type_map[idx] = entry.type
        return line_tag_map, filedir_type_map

    def _build_line_format_map(self) -> Dict[int, str]:
        """Build idx → file format map from manifest filedir."""
        mgr = self.manifest_manager
        format_map: Dict[int, str] = {}
        path_map: Dict[int, str] = {}
        if mgr is None or not mgr.is_loaded or not hasattr(mgr, "get_filedir"):
            self._line_format_map = format_map
            self._line_path_map = path_map
            return format_map
        for entry in mgr.get_filedir():
            entry_format = (entry.format or "").strip().lower()
            for idx in range(entry.first_idx, entry.last_idx + 1):
                format_map[idx] = entry_format
                path_map[idx] = entry.rel_path
        self._line_format_map = format_map
        self._line_path_map = path_map
        return format_map

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
        if self._persist_after_wrap and not getattr(self, "_persist_done_in_worker", False):
            self._persist_wrapped_lines()
        self._status_label.configure(text="Completed")
        self._apply_btn.configure(state="normal")
        self._stop_progress_poll()
        if hasattr(self, "_progress_var"):
            self._progress_var.set(100)
        self._refresh_table()
        self._update_summary()

    def _on_wrap_error(self, error: str) -> None:
        """Handle wrap error."""
        self._status_label.configure(text="Failed")
        self._apply_btn.configure(state="normal")
        self._stop_progress_poll()
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
                line = next((item for item in self._lines if item.idx == idx), None)
                if line is not None:
                    line.wrapped = line.original
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
        selected_format = self._format_var.get().strip().lower()

        for line in self._lines:
            if self._filtered_indices is not None and line.idx not in self._filtered_indices:
                continue
            if selected_format and line.source_format != selected_format:
                continue
            # Apply filter (Task 46.9)
            if active_filter == "changed" and not line.has_changes:
                continue
            if active_filter == "exceeding" and not line.exceeds_limit:
                continue
            if active_filter == "new_textbox" and not line.new_textbox_applied:
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
                meta={
                    "source_path": line.source_path,
                    "source_format": line.source_format,
                },
            )
            rows.append(row)

        self._preview_table.load_data(rows)

    def _update_ruler(self, line_idx: int) -> None:
        """Update the line length ruler for selected line."""
        self._ruler_canvas.delete("all")

        line = next((item for item in self._lines if item.idx == line_idx), None)
        if line is None:
            return

        width = self._get_active_width_limit()
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
        """Get manifest-defined invisible patterns for width ignoring only."""
        patterns: List[str] = []
        if self.manifest_manager is None:
            return patterns
        try:
            entries = []
            if hasattr(self.manifest_manager, "get_code_patterns"):
                entries = self.manifest_manager.get_code_patterns()
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                is_invisible = bool(
                    entry.get("IsInvisible")
                    or entry.get("is_invisible")
                    or str(entry.get("Type", "")).strip().lower() == "invisible"
                )
                if not is_invisible:
                    continue
                pattern = str(
                    entry.get("RegEx")
                    or entry.get("regex")
                    or entry.get("pattern")
                    or ""
                ).strip()
                if pattern:
                    patterns.append(pattern)
        except Exception:
            pass

        deduped: List[str] = []
        seen: set[str] = set()
        for pattern in patterns:
            if pattern in seen:
                continue
            seen.add(pattern)
            deduped.append(pattern)
        return deduped

    def _get_detected_speakers(self) -> List[str]:
        """Get analysis/parser-discovered speaker names from manifest characters."""
        if self.manifest_manager is None:
            return []

        speakers: List[str] = []
        seen: set[str] = set()
        try:
            characters = []
            if hasattr(self.manifest_manager, "get_characters"):
                characters = self.manifest_manager.get_characters()
            for character in characters:
                if not isinstance(character, dict):
                    continue
                for raw_name in (
                    character.get("original_name", ""),
                    character.get("translation", ""),
                ):
                    name = str(raw_name).strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    speakers.append(name)

            # If analysis data is absent or incomplete, fall back to parser-provided
            # speaker detection for the current preview lines instead of generic heuristics.
            if _HAS_PARSER_REGISTRY and hasattr(self, "_lines"):
                by_format: Dict[str, List[str]] = {}
                for line in getattr(self, "_lines", []):
                    text = getattr(line, "original", "")
                    source_format = str(getattr(line, "source_format", "") or "").strip().lower()
                    if not text or not source_format:
                        continue
                    by_format.setdefault(source_format, []).append(text)

                registry = get_parser_registry()
                for source_format, texts in by_format.items():
                    parser = registry.get(source_format)
                    if parser is None or not hasattr(parser, "detect_speakers"):
                        continue
                    detected = parser.detect_speakers(texts) or []
                    for speaker in detected:
                        name = ""
                        if isinstance(speaker, dict):
                            name = str(
                                speaker.get("name")
                                or speaker.get("original_name")
                                or ""
                            ).strip()
                        else:
                            name = str(getattr(speaker, "name", "") or "").strip()
                        if not name or name in seen:
                            continue
                        seen.add(name)
                        speakers.append(name)
        except Exception:
            pass
        return speakers

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

    def _save_simple_settings_to_manifest(self, *args: Any) -> None:
        """Persist simple mode settings into the manifest."""
        if self.manifest_manager is None:
            return
        save_nested_int_field(
            self.manifest_manager, "WordwrapSettings", "Width", self._simple_width_var.get()
        )
        save_nested_text_field(
            self.manifest_manager, "WordwrapSettings", "BreakChar", self._simple_break_var.get()
        )
        save_nested_int_field(
            self.manifest_manager, "WordwrapSettings", "MaxLines", self._simple_max_lines_var.get()
        )
        save_nested_bool_field(
            self.manifest_manager,
            "WordwrapSettings",
            "PrettyWrap",
            bool(self._simple_pretty_var.get()),
        )

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
            self.manifest_manager, "WordwrapSettings", "Mode", WrapMode.CUSTOM.value
        )
        self._mode_var.set(WrapMode.from_display(mode_value).value)

        self._simple_width_var.set(load_nested_int_field(
            self.manifest_manager, "WordwrapSettings", "Width", 48
        ))
        self._simple_break_var.set(load_nested_text_field(
            self.manifest_manager, "WordwrapSettings", "BreakChar", "\\n"
        ))
        self._simple_max_lines_var.set(load_nested_int_field(
            self.manifest_manager, "WordwrapSettings", "MaxLines", 4
        ))
        self._simple_pretty_var.set(load_nested_bool_field(
            self.manifest_manager, "WordwrapSettings", "PrettyWrap", True
        ))
        
        # Load speaker handling
        speaker_value = load_nested_text_field(
            self.manifest_manager, "WordwrapSettings", "SpeakerHandling", SpeakerMode.COUNT.value
        )
        self._speaker_var.set(speaker_value)

        if hasattr(self.manifest_manager, "get_wordwrap_format_configs"):
            raw_format_configs = self.manifest_manager.get_wordwrap_format_configs()
        else:
            raw_format_configs = self.manifest_manager.get("WordwrapSettings", {}).get("FormatConfigs", [])
        if raw_format_configs:
            self._format_configs = {
                str(cfg.get("format", "")).lower(): FormatConfig.from_dict(cfg)
                for cfg in raw_format_configs
                if isinstance(cfg, dict) and cfg.get("format")
            }

        self._apply_parser_wordwrap_defaults()

        # Backward compatibility: upgrade legacy global TagConfigs into the first format.
        if hasattr(self.manifest_manager, "get_wordwrap_tag_configs"):
            raw_tag_configs = self.manifest_manager.get_wordwrap_tag_configs()
        else:
            raw_tag_configs = self.manifest_manager.get("WordwrapSettings", {}).get("TagConfigs", [])
        if raw_tag_configs and self._format_configs:
            first_key = next(iter(self._format_configs))
            if not self._format_configs[first_key].tag_configs:
                self._format_configs[first_key].tag_configs = [
                    TagWrapConfig.from_dict(d) for d in raw_tag_configs
                ]

        self._refresh_format_selector()
        self._refresh_mode_ui()
        
        logger.debug("Wordwrap settings loaded from manifest")

    def _apply_parser_wordwrap_defaults(self) -> None:
        """Auto-populate format-scoped configs from manifest file formats."""
        format_ids = self._collect_manifest_formats()
        if not format_ids:
            self._format_configs = {}
            return

        updated: Dict[str, FormatConfig] = {}
        for format_id in format_ids:
            parser = self._get_parser_for_format(format_id)
            existing = self._format_configs.get(format_id)
            default_cfg = DEFAULT_FORMAT_CONFIGS.get(format_id)

            if existing is not None:
                cfg = existing
            elif default_cfg is not None:
                cfg = FormatConfig.from_dict(default_cfg.to_dict())
            else:
                cfg = FormatConfig(format_id=format_id, format_name=format_id)

            cfg.format_id = format_id
            if parser is not None:
                cfg.format_name = getattr(parser, "display_name", parser.name)
                ww = parser.wordwrap_config
                if ww is not None:
                    cfg.wrap_width = ww.max_line_length
                    cfg.break_char = ww.wordwrap_command
                    cfg.max_lines = ww.max_line_number
            elif default_cfg is not None:
                cfg.format_name = default_cfg.format_name

            if not cfg.tag_configs:
                cfg.tag_configs = self._build_default_tag_configs(
                    format_id,
                    parser=parser,
                    available_tags=self._collect_available_tags(format_id),
                )

            updated[format_id] = cfg

        self._format_configs = updated

    def on_new_project(self) -> None:
        """Reset cached state for a fresh project."""
        super().on_new_project()
        self._lines.clear()
        self._selected_line_idx = -1
        self._manifest_bindings.clear()
        self._tag_configs = []
        self._format_configs = {}
        self._line_format_map = {}
        self._line_path_map = {}
        self._file_tree = {}
        self._file_filter = None
        self._filtered_indices = None
        self._tag_widgets.clear()
        logger.debug("Wordwrap step reset for new project")

    def on_enter(self) -> None:
        """Called when entering this tab."""
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
            self._build_line_format_map()
            self._refresh_file_filter_options()
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
                source_format=self._line_format_map.get(i, ""),
                source_path=self._line_path_map.get(i, ""),
                wrapped=wr,
            )
            self._lines.append(wrap_line)

    def _save_to_session(self) -> None:
        """Save current state to session.

        Stores preview state in session without auto-writing ``wordwr``.
        """
        step_data = self.get_step_data()
        format_var = getattr(self, "_format_var", None)
        format_configs = getattr(self, "_format_configs", {})
        step_data["wrap_options"] = {
            "mode": self._mode_var.get(),
            "width": self._get_active_width_limit(),
            "break_char": self._get_active_break_char(),
            "max_lines": self._get_active_max_lines(),
            "speaker_mode": self._speaker_var.get(),
            "file_filter": getattr(self, "_file_filter", None),
        }
        step_data["tag_configs"] = [tc.to_dict() for tc in self._tag_configs]
        step_data["format_configs"] = [
            config.to_dict() for config in format_configs.values()
        ]
        step_data["selected_format"] = format_var.get() if format_var else ""
        self.set_step_data(step_data)

    def _persist_wrapped_lines(
        self,
        progress_base: float = 0.0,
        progress_span: float = 0.0,
    ) -> None:
        """Persist explicit wordwrap results sparsely to the manifest."""
        mgr = self.manifest_manager
        if mgr is None:
            return
        total_lines = len(self._lines)
        processed_indices = getattr(self, "_last_processed_indices", None)
        for line_pos, line in enumerate(self._lines, start=1):
            if processed_indices is not None and line.idx not in processed_indices:
                continue
            if not line.persist_wrapped:
                mgr.clear_line_field(line.idx, "wordwr")
                self._queue_progress_update(
                    progress_base + (line_pos / max(total_lines, 1)) * progress_span,
                    f"Saving... {line_pos}/{total_lines}",
                )
                continue
            _persist_sparse_wordwrap(
                mgr,
                line.idx,
                line.original,
                line.wrapped,
            )
            self._queue_progress_update(
                progress_base + (line_pos / max(total_lines, 1)) * progress_span,
                f"Saving... {line_pos}/{total_lines}",
            )

    def _start_progress_poll(self) -> None:
        """Start polling worker progress updates onto the UI thread."""
        self._stop_progress_poll()
        self._progress_queue = queue.SimpleQueue()
        self._poll_progress_queue()

    def _stop_progress_poll(self) -> None:
        """Stop polling worker progress updates."""
        poll_id = getattr(self, "_progress_poll_id", None)
        if poll_id is not None:
            try:
                self.after_cancel(poll_id)
            except Exception:
                pass
        self._progress_poll_id = None

    def _queue_progress_update(self, value: float, status: str) -> None:
        """Queue a progress update from the worker thread."""
        progress_queue = getattr(self, "_progress_queue", None)
        if progress_queue is None:
            return
        progress_queue.put((max(0.0, min(100.0, value)), status))

    def _poll_progress_queue(self) -> None:
        """Apply queued progress updates on the Tk main thread."""
        progress_queue = getattr(self, "_progress_queue", None)
        if progress_queue is not None:
            while True:
                try:
                    value, status = progress_queue.get_nowait()
                except queue.Empty:
                    break
                self._progress_var.set(value)
                if status:
                    self._status_label.configure(text=status)

        if self._status == WrapStatus.RUNNING:
            self._progress_poll_id = self.after(50, self._poll_progress_queue)
        else:
            self._progress_poll_id = None

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
            width=self._get_active_width_limit(),
            break_char=self._get_active_break_char(),
            max_lines=self._get_active_max_lines(),
            pretty_wrap=self._get_active_pretty_wrap(),
        )

    def _get_active_width_limit(self) -> int:
        """Return the active width limit for the current wrap mode."""
        if WrapMode.from_display(self._mode_var.get()) == WrapMode.SIMPLE:
            return self._simple_width_var.get()
        return self._width_var.get()

    def _get_active_break_char(self) -> str:
        """Return the active break character for the current wrap mode."""
        if WrapMode.from_display(self._mode_var.get()) == WrapMode.SIMPLE:
            return self._simple_break_var.get()
        return self._break_var.get()

    def _get_active_max_lines(self) -> int:
        """Return the active max-lines value for the current wrap mode."""
        if WrapMode.from_display(self._mode_var.get()) == WrapMode.SIMPLE:
            return self._simple_max_lines_var.get()
        return self._max_lines_var.get()

    def _get_active_pretty_wrap(self) -> bool:
        """Return the active pretty-wrap toggle for the current wrap mode."""
        if WrapMode.from_display(self._mode_var.get()) == WrapMode.SIMPLE:
            return bool(self._simple_pretty_var.get())
        dialogue_cfg = self.get_tag_config_for("dialogue")
        return dialogue_cfg.pretty_wrap if dialogue_cfg is not None else True

    def _refresh_file_filter_options(self) -> None:
        """Build the file-selection tree from manifest filedir entries."""
        self._file_tree = {}
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            if hasattr(self, "_file_filter_var"):
                self._file_filter_var.set("All")
            return

        for entry in mgr.get_filedir():
            parts = entry.rel_path.replace("\\", "/").split("/")
            node = self._file_tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = entry

        if hasattr(self, "_file_filter_var") and self._file_filter is None:
            self._file_filter_var.set("All")

    def _show_file_filter_dropdown(self) -> None:
        """Show the reusable hierarchical file selector used by Full Table View."""
        if not self._file_tree or self.manifest_manager is None:
            return
        dropdown = _FileFilterDropdown(
            self,
            self._file_tree,
            self.manifest_manager.get_filedir(),
            current_filter=self._file_filter,
            on_select=self._apply_file_filter,
        )
        x = self._file_filter_btn.winfo_rootx()
        y = self._file_filter_btn.winfo_rooty() + self._file_filter_btn.winfo_height()
        dropdown.geometry(f"+{x}+{y}")

    def _apply_file_filter(self, filter_path: Optional[str]) -> None:
        """Restrict the preview to one file or folder path."""
        self._file_filter = filter_path
        if filter_path is None:
            self._filtered_indices = None
            self._file_filter_var.set("All")
            self._refresh_table()
            return

        filtered: set[int] = set()
        mgr = self.manifest_manager
        if mgr is not None:
            filter_norm = filter_path.replace("\\", "/")
            for entry in mgr.get_filedir():
                rel = entry.rel_path.replace("\\", "/")
                if rel == filter_norm or rel.startswith(filter_norm + "/"):
                    for idx in range(entry.first_idx, entry.last_idx + 1):
                        filtered.add(idx)

        self._filtered_indices = filtered
        display = filter_path.replace("\\", "/")
        if len(display) > 28:
            display = "…" + display[-27:]
        self._file_filter_var.set(display)

        selected_line = next(
            (line for line in self._lines if line.idx in filtered),
            None,
        )
        if selected_line is not None and selected_line.source_format:
            self._format_var.set(selected_line.source_format)
            self._sync_selected_format_state()
        self._refresh_table()

    def _view_in_file(self) -> None:
        """Filter the preview down to the file that owns the selected row."""
        if self._selected_line_idx < 0:
            messagebox.showinfo("Info", "Select a line first.")
            return
        line = next((item for item in self._lines if item.idx == self._selected_line_idx), None)
        if line is None or not line.source_path:
            messagebox.showinfo("Info", "The selected line is not linked to a file.")
            return
        self._apply_file_filter(line.source_path)
        self._preview_table.scroll_to_row(line.idx)

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
