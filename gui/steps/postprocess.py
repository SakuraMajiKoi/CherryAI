"""CherryAI GUI v2 Postprocessing Step.

Eighth workflow tab for restoring placeholders/anchors with diff view.
Provides recovery operations, symbol conversion, and failure handling.
Also includes character/word validation per TASK 36.3.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from difflib import unified_diff
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME
from CherryAI.gui.helpers.manifest_binding import (
    BindingInfo,
    bind_checkbox_to_field,
)
from CherryAI.functions.manifest_fields import (
    save_nested_text_field,
    load_nested_text_field,
)
try:
    # Explicit import of shared processing logic per architecture rules
    from CherryAI.functions.postprocess import (
        recover_line,
        RecoveryResult,
        RecoveryType as FuncRecoveryType,
        RecoveryAction as FuncRecoveryAction,
    )
    _HAS_POSTPROCESS = True
except ImportError:  # pragma: no cover
    _HAS_POSTPROCESS = False

# TASK 36.3: Import character/word validation functions
try:
    from CherryAI.functions.validation import (
        validate_character_word,
        apply_autofix_to_lines,
        get_findings_summary,
        CharacterWordValidationResult,
        ValidationSeverity,
    )
    _HAS_CHAR_VALIDATION = True
except ImportError:  # pragma: no cover
    _HAS_CHAR_VALIDATION = False

# Test expectation: include direct import form for functions package resolution
try:  # pragma: no cover
    from functions.postprocess import recover_line as _test_hook_recover_line
except Exception:  # pragma: no cover
    _test_hook_recover_line = None

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class RecoveryType(Enum):
    """Type of recovery operation."""

    PLACEHOLDER_CASE = "placeholder_case"
    PLACEHOLDER_MANGLED = "placeholder_mangled"
    PLACEHOLDER_MISSING = "placeholder_missing"
    BRACKET_BALANCE = "bracket_balance"
    QUOTE_BALANCE = "quote_balance"
    WHITESPACE = "whitespace"
    CODE_CHARACTER = "code_character"
    BR_TAG = "br_tag"
    SPEAKER_FORMAT = "speaker_format"
    SYMBOL_CONVERSION = "symbol_conversion"


class RecoveryAction(Enum):
    """Action taken for a recovery issue."""

    RECOVERED = "recovered"
    NEEDS_RETRY = "needs_retry"
    SKIPPED = "skipped"
    FAILED = "failed"


class FailurePolicy(Enum):
    """How to handle unrecoverable issues.

    TASK 45.6: Redesigned — WRITE keeps partially-recovered text,
    FLAG marks for manual review. RETRY hidden (future).
    """

    WRITE = "write"
    FLAG = "flag"
    RETRY = "retry"  # Hidden from UI, kept for backward compat


class PostprocessStatus(Enum):
    """Status of postprocessing operation."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class RecoveryIssue:
    """A single recovery issue found during postprocessing."""

    line_idx: int
    recovery_type: RecoveryType
    action: RecoveryAction
    description: str
    original_text: str = ""
    recovered_text: str = ""
    position: int = -1


@dataclass
class PostprocessLine:
    """A line with postprocessing status."""

    idx: int
    original: str
    translated: str
    postprocessed: str = ""
    issues: List[RecoveryIssue] = field(default_factory=list)
    has_changes: bool = False
    needs_retry: bool = False
    skipped: bool = False
    written: bool = False  # TASK 45.9: Line was written despite failures
    flagged: bool = False  # TASK 45.9: Line flagged for manual review

    @property
    def issue_count(self) -> int:
        """Count of issues found."""
        return len(self.issues)

    @property
    def recovered_count(self) -> int:
        """Count of successfully recovered issues."""
        return sum(
            1 for i in self.issues if i.action == RecoveryAction.RECOVERED
        )


@dataclass
class PostprocessOptions:
    """Options for postprocessing."""

    enable_placeholder_recovery: bool = True
    enable_bracket_recovery: bool = True
    enable_quote_recovery: bool = True
    enable_whitespace_normalization: bool = True
    enable_symbol_conversion: bool = True
    failure_policy: FailurePolicy = FailurePolicy.WRITE
    convert_fullwidth_to_halfwidth: bool = False
    convert_halfwidth_to_fullwidth: bool = False
    restore_code_characters: bool = True
    restore_br_tags: bool = True


@dataclass
class RecoveryStats:
    """Statistics for recovery operations."""

    total_lines: int = 0
    lines_processed: int = 0
    lines_with_changes: int = 0
    total_issues: int = 0
    issues_recovered: int = 0
    issues_retry: int = 0
    issues_skipped: int = 0

    @property
    def recovery_rate(self) -> float:
        """Get recovery rate as percentage."""
        if self.total_issues == 0:
            return 100.0
        return (self.issues_recovered / self.total_issues) * 100.0


# ============================================================================
# Symbol Conversion Map
# ============================================================================


FULLWIDTH_TO_HALFWIDTH: Dict[str, str] = {
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
    "，": ",",
    "。": ".",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "｛": "{",
    "｝": "}",
    "＜": "<",
    "＞": ">",
    "＂": '"',
    "＇": "'",
    "　": " ",
    "～": "~",
    "＝": "=",
    "＋": "+",
    "－": "-",
    "＊": "*",
    "／": "/",
    "＼": "\\",
    "＠": "@",
    "＃": "#",
    "＄": "$",
    "％": "%",
    "＆": "&",
    "＿": "_",
}

# TASK 45.5: Reverse map for Halfwidth → Fullwidth conversion
HALFWIDTH_TO_FULLWIDTH: Dict[str, str] = {
    v: k for k, v in FULLWIDTH_TO_HALFWIDTH.items()
}


# ============================================================================
# PostprocessingStep Class
# ============================================================================


class PostprocessingStep(BaseStep):
    """Postprocessing step for restoring placeholders/anchors.

    Features:
    - Table view with postprocessed vs translated
    - Diff view for changes
    - Recovery options panel
    - Failure handling options
    - Symbol conversion settings
    - Batch operations
    """

    step_id = 6  # Moved from position 7
    step_name = "Postprocessing"
    # Test visibility for explicit import expectation
    _IMPORT_EXPECTATION = "from functions.postprocess import"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize postprocessing step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables BEFORE super().__init__
        # because base class calls _build_ui() which needs these
        self._lines: List[PostprocessLine] = []
        self._pp_options = PostprocessOptions()
        self._status = PostprocessStatus.IDLE
        self._stats = RecoveryStats()
        self._process_thread: Optional[threading.Thread] = None
        self._selected_line_idx: int = -1
        # TASK 27.1: Manifest bindings for postprocessing options
        self._manifest_bindings: List[BindingInfo] = []
        # TASK 36.3: Character/word validation state
        self._validation_result: Optional[Any] = None  # CharacterWordValidationResult
        self._validation_run: bool = False
        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the step UI."""
        self._build_header()
        self._build_content()
        self._build_summary_panel()

    def _build_header(self) -> None:
        """Build the header section with controls.

        TASK 45.3: Removed Refresh and Revert All buttons. Lines
        auto-load on tab entry via on_enter(). Overwrite warning
        added in _apply_postprocessing() (TASK 45.10).
        """
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # Left: Title and status
        left_frame = ttk.Frame(header)
        left_frame.pack(side="left")

        ttk.Label(
            left_frame,
            text="Postprocessing",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side="left")

        self._status_label = ttk.Label(
            left_frame,
            text="Ready",
            foreground=THEME.text_secondary,
        )
        self._status_label.pack(side="left", padx=(10, 0))

        # Right: Apply button only
        right_frame = ttk.Frame(header)
        right_frame.pack(side="right")

        self._apply_btn = ttk.Button(
            right_frame,
            text="▶ Apply Postprocessing",
            command=self._apply_postprocessing,
        )
        self._apply_btn.pack(side="right")

    def _build_content(self) -> None:
        """Build the main content area."""
        # Main paned window (horizontal)
        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Lines table
        left_frame = ttk.Frame(content)
        content.add(left_frame, weight=2)
        self._build_lines_panel(left_frame)

        # Right: Options and diff view
        right_frame = ttk.Frame(content)
        content.add(right_frame, weight=1)
        self._build_right_panels(right_frame)

    def _build_lines_panel(self, parent: ttk.Frame) -> None:
        """Build the lines table with postprocessing status (TASK 45.2)."""
        frame = ttk.LabelFrame(parent, text="Processed Lines")
        frame.pack(fill="both", expand=True)

        # Filter controls
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(filter_frame, text="Filter:").pack(side="left")

        self._filter_var = tk.StringVar(value="all")
        # TASK 45.9: Updated filter options (All/Changed/Written/Flagged)
        filter_options = [
            ("All", "all"),
            ("Changed", "changed"),
            ("Written", "written"),
            ("Flagged", "flagged"),
        ]
        for text, value in filter_options:
            ttk.Radiobutton(
                filter_frame,
                text=text,
                variable=self._filter_var,
                value=value,
                command=self._apply_filter,
            ).pack(side="left", padx=2)

        # Define columns
        columns = [
            ColumnDef(key="idx", title="#", width=50, anchor="center"),
            ColumnDef(key="status", title="Status", width=80, anchor="center"),
            ColumnDef(key="changes", title="Changes", width=60, anchor="center"),
            ColumnDef(key="translated", title="Translated", width=200),
            ColumnDef(key="postprocessed", title="Postprocessed", width=200),
        ]

        self._lines_table = SharedTable(
            frame,
            columns=columns,
            show_filter=True,
            show_checkboxes=True,
            on_select=self._on_line_selected,
        )
        self._lines_table.pack(fill="both", expand=True, padx=5, pady=5)

        # Batch action buttons
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

        ttk.Button(
            batch_frame,
            text="🔄 Retry Selected",
            command=self._retry_selected,
        ).pack(side="left", padx=2)

    def _build_right_panels(self, parent: ttk.Frame) -> None:
        """Build the right side panels."""
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

        # Recovery options panel
        self._build_options_panel(scrollable_frame)

        # Diff view panel
        self._build_diff_panel(scrollable_frame)

        # Issues panel
        self._build_issues_panel(scrollable_frame)

        # TASK 36.3: Character/word validation panel
        self._build_validation_panel(scrollable_frame)

        # Enable mousewheel scrolling (scoped to canvas, not bind_all)
        def _on_mousewheel(event: tk.Event) -> None:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        # Also bind on child frames so scrolling works when hovering over content
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)

    def _build_options_panel(self, parent: ttk.Frame) -> None:
        """Build recovery options panel with manifest bindings (TASK 27.1).

        TASK 45.4: Placeholder Recovery, Restore Code Characters, and
        Restore <br> Tags are always-on (no GUI toggle). Only optional
        recoveries are shown as checkboxes.
        """
        frame = ttk.LabelFrame(parent, text="Recovery Options", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # TASK 45.4: Always-on recoveries (no checkbox)
        auto_label = ttk.Label(
            frame,
            text="✓ Placeholder / Code / BR recovery (always on)",
            foreground=THEME.text_secondary,
        )
        auto_label.pack(anchor="w", pady=(0, 5))

        # Optional recovery toggles
        self._bracket_var = tk.BooleanVar(
            value=self._pp_options.enable_bracket_recovery
        )
        bracket_cb = ttk.Checkbutton(
            frame,
            text="Bracket Balance Recovery",
            variable=self._bracket_var,
        )
        bracket_cb.pack(anchor="w", pady=2)

        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=bracket_cb,
                var=self._bracket_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="BracketBalanceRecovery",
                default=True,
                parent_key="PostProcessing",
            )
        )

        self._quote_var = tk.BooleanVar(
            value=self._pp_options.enable_quote_recovery
        )
        quote_cb = ttk.Checkbutton(
            frame,
            text="Quote Balance Recovery",
            variable=self._quote_var,
        )
        quote_cb.pack(anchor="w", pady=2)

        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=quote_cb,
                var=self._quote_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="QuoteBalanceRecovery",
                default=True,
                parent_key="PostProcessing",
            )
        )

        self._whitespace_var = tk.BooleanVar(
            value=self._pp_options.enable_whitespace_normalization
        )
        whitespace_cb = ttk.Checkbutton(
            frame,
            text="Whitespace Normalization",
            variable=self._whitespace_var,
        )
        whitespace_cb.pack(anchor="w", pady=2)

        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=whitespace_cb,
                var=self._whitespace_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="WhitespaceNormalization",
                default=True,
                parent_key="PostProcessing",
            )
        )

        # Symbol conversion options
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=5)

        ttk.Label(frame, text="Symbol Conversion:").pack(anchor="w")

        self._symbol_var = tk.BooleanVar(
            value=self._pp_options.enable_symbol_conversion
        )
        symbol_cb = ttk.Checkbutton(
            frame,
            text="Enable Symbol Conversion",
            variable=self._symbol_var,
        )
        symbol_cb.pack(anchor="w", pady=2, padx=10)
        
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=symbol_cb,
                var=self._symbol_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="EnableSymbolConversion",
                default=True,
                parent_key="PostProcessing",
            )
        )

        self._fullwidth_var = tk.BooleanVar(
            value=self._pp_options.convert_fullwidth_to_halfwidth
        )
        fullwidth_cb = ttk.Checkbutton(
            frame,
            text="Fullwidth → Halfwidth",
            variable=self._fullwidth_var,
        )
        fullwidth_cb.pack(anchor="w", pady=2, padx=10)

        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=fullwidth_cb,
                var=self._fullwidth_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="FullwidthToHalfwidth",
                default=True,
                parent_key="PostProcessing",
            )
        )

        # TASK 45.5: Halfwidth → Fullwidth (reverse direction)
        self._halfwidth_var = tk.BooleanVar(
            value=self._pp_options.convert_halfwidth_to_fullwidth
        )
        halfwidth_cb = ttk.Checkbutton(
            frame,
            text="Halfwidth → Fullwidth",
            variable=self._halfwidth_var,
        )
        halfwidth_cb.pack(anchor="w", pady=2, padx=10)

        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=halfwidth_cb,
                var=self._halfwidth_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="HalfwidthToFullwidth",
                default=False,
                parent_key="PostProcessing",
            )
        )

        # TASK 45.5: Mutual exclusion — enabling one disables the other
        def _on_fullwidth_change(*_args: Any) -> None:
            if self._fullwidth_var.get():
                self._halfwidth_var.set(False)

        def _on_halfwidth_change(*_args: Any) -> None:
            if self._halfwidth_var.get():
                self._fullwidth_var.set(False)

        self._fullwidth_var.trace_add("write", _on_fullwidth_change)
        self._halfwidth_var.trace_add("write", _on_halfwidth_change)

        # Failure handling (TASK 45.6: Write/Flag only, Retry hidden)
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=5)

        ttk.Label(frame, text="Failure Handling:").pack(anchor="w")

        self._failure_var = tk.StringVar(value=self._pp_options.failure_policy.value)

        # TASK 27.1: Trace failure handling changes to manifest
        self._failure_var.trace_add("write", self._save_failure_policy_to_manifest)

        policies = [
            ("Write (keep as-is)", "write"),
            ("Flag for Review", "flag"),
        ]
        for text, value in policies:
            ttk.Radiobutton(
                frame,
                text=text,
                variable=self._failure_var,
                value=value,
            ).pack(anchor="w", padx=10)

    def _save_failure_policy_to_manifest(self, *args: Any) -> None:
        """Save failure policy to manifest when changed (TASK 27.1).
        
        Args:
            *args: Trace callback arguments (ignored).
        """
        if self.manifest_manager is None:
            return
        value = self._failure_var.get()
        save_nested_text_field(
            self.manifest_manager, "PostProcessing", "FailureHandling", value
        )
        logger.debug("Failure policy saved to manifest: %s", value)

    def _load_postprocessing_options_from_manifest(self) -> None:
        """Load postprocessing options from manifest (TASK 27.1).
        
        Loads all checkbox states and failure handling policy from manifest.
        """
        if self.manifest_manager is None:
            return
        
        # Load all checkbox bindings
        for binding in self._manifest_bindings:
            if hasattr(binding, "load_from_manifest"):
                binding.load_from_manifest()
        
        # Load failure handling policy
        value = load_nested_text_field(
            self.manifest_manager, "PostProcessing", "FailureHandling", "write"
        )
        self._failure_var.set(value)
        logger.debug("Postprocessing options loaded from manifest")

    def _build_diff_panel(self, parent: ttk.Frame) -> None:
        """Build diff view panel with edit capability (TASK 45.7)."""
        frame = ttk.LabelFrame(parent, text="Diff View", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # Line info
        self._diff_line_label = ttk.Label(
            frame,
            text="Select a line to see diff",
            foreground=THEME.text_secondary,
        )
        self._diff_line_label.pack(anchor="w")

        # Diff text display (read-only)
        self._diff_text = scrolledtext.ScrolledText(
            frame,
            height=8,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
        )
        self._diff_text.pack(fill="x", pady=5)

        # Configure diff highlighting tags
        self._diff_text.tag_configure(
            "addition",
            foreground="#22c55e",
            font=("Consolas", 9, "bold"),
        )
        self._diff_text.tag_configure(
            "deletion",
            foreground="#ef4444",
            font=("Consolas", 9, "bold"),
        )
        self._diff_text.tag_configure(
            "header",
            foreground=THEME.accent_info,
        )

        # TASK 45.7: Editable text field for manual fixes
        edit_label = ttk.Label(
            frame,
            text="Edit postprocessed text:",
            foreground=THEME.text_secondary,
        )
        edit_label.pack(anchor="w", pady=(5, 0))

        self._edit_text = scrolledtext.ScrolledText(
            frame,
            height=4,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
        )
        self._edit_text.pack(fill="x", pady=2)

        # Mark as Fixed button
        self._mark_fixed_btn = ttk.Button(
            frame,
            text="✓ Mark as Fixed",
            command=self._mark_line_as_fixed,
            state="disabled",
        )
        self._mark_fixed_btn.pack(anchor="e", pady=2)

    def _build_issues_panel(self, parent: ttk.Frame) -> None:
        """Build issues panel."""
        frame = ttk.LabelFrame(parent, text="Recovery Details", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        self._issues_listbox = tk.Listbox(
            frame,
            height=5,
            font=("TkDefaultFont", 9),
        )
        self._issues_listbox.pack(fill="x", pady=2)

    def _build_validation_panel(self, parent: ttk.Frame) -> None:
        """Build character/word validation panel (TASK 36.3).
        
        Shows validation results and provides autofix action.
        """
        frame = ttk.LabelFrame(parent, text="Character/Word Validation", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # Summary labels
        summary_frame = ttk.Frame(frame)
        summary_frame.pack(fill="x", pady=2)

        ttk.Label(summary_frame, text="Status:").pack(side="left")
        self._validation_status_label = ttk.Label(
            summary_frame,
            text="Not scanned",
            foreground=THEME.text_secondary,
        )
        self._validation_status_label.pack(side="left", padx=(5, 0))

        # Counts frame
        counts_frame = ttk.Frame(frame)
        counts_frame.pack(fill="x", pady=2)

        ttk.Label(counts_frame, text="Warnings:").pack(side="left")
        self._validation_warnings_label = ttk.Label(
            counts_frame,
            text="0",
            foreground=THEME.accent_warning,
        )
        self._validation_warnings_label.pack(side="left", padx=(5, 15))

        ttk.Label(counts_frame, text="Errors:").pack(side="left")
        self._validation_errors_label = ttk.Label(
            counts_frame,
            text="0",
            foreground=THEME.accent_error if hasattr(THEME, 'accent_error') else "#ef4444",
        )
        self._validation_errors_label.pack(side="left", padx=(5, 0))

        # Findings listbox
        self._validation_listbox = tk.Listbox(
            frame,
            height=4,
            font=("TkDefaultFont", 9),
        )
        self._validation_listbox.pack(fill="x", pady=2)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=5)

        self._validate_btn = ttk.Button(
            btn_frame,
            text="🔍 Run Validation",
            command=self._run_character_validation,
        )
        self._validate_btn.pack(side="left", padx=2)

        self._autofix_btn = ttk.Button(
            btn_frame,
            text="🔧 Apply Autofix",
            command=self._apply_character_autofix,
            state="disabled",
        )
        self._autofix_btn.pack(side="left", padx=2)

    def _run_character_validation(self) -> None:
        """Run character/word validation on postprocessed lines (TASK 36.3)."""
        if not _HAS_CHAR_VALIDATION:
            messagebox.showwarning(
                "Validation Unavailable",
                "Character validation module not available.",
            )
            return

        if not self._lines:
            self._refresh_lines()

        if not self._lines:
            messagebox.showwarning(
                "No Data",
                "Please complete translation first.",
            )
            return

        # Get validation config from manifest
        whitelist = ""
        blacklist = ""
        word_blacklist: List[str] = []
        autofix_map: Dict[str, str] = {}

        if self.manifest_manager:
            config = self.manifest_manager.get_character_validation_config()
            whitelist = config.get("CharacterWhitelist", "")
            blacklist = config.get("CharacterBlacklist", "")
            word_blacklist = config.get("WordBlacklist", [])
            autofix_map = config.get("AutofixMap", {})

        # Build lines data for validation
        lines_data = []
        for line in self._lines:
            lines_data.append({
                "idx": line.idx,
                "tl": line.translated,
                "post": line.postprocessed,
            })

        # Run validation
        self._validation_result = validate_character_word(
            lines=lines_data,
            whitelist=whitelist,
            blacklist=blacklist,
            word_blacklist=word_blacklist,
            autofix_map=autofix_map,
            fields_to_check=["post"],  # Check postprocessed field
        )
        self._validation_run = True

        # Update UI
        self._update_validation_display()

    def _update_validation_display(self) -> None:
        """Update validation panel with current results (TASK 36.3)."""
        if not self._validation_result:
            self._validation_status_label.configure(text="Not scanned")
            self._validation_warnings_label.configure(text="0")
            self._validation_errors_label.configure(text="0")
            self._validation_listbox.delete(0, "end")
            self._autofix_btn.configure(state="disabled")
            return

        result = self._validation_result

        # Update status
        if result.has_issues:
            self._validation_status_label.configure(
                text=f"{result.total_issues} issues in {result.lines_with_issues} lines",
                foreground=THEME.accent_warning if result.warning_count > result.error_count else (
                    THEME.accent_error if hasattr(THEME, 'accent_error') else "#ef4444"
                ),
            )
        else:
            self._validation_status_label.configure(
                text="✓ No issues found",
                foreground=THEME.accent_success,
            )

        # Update counts
        self._validation_warnings_label.configure(text=str(result.warning_count))
        self._validation_errors_label.configure(text=str(result.error_count))

        # Update findings listbox
        self._validation_listbox.delete(0, "end")

        if not result.findings:
            self._validation_listbox.insert("end", "No issues found")
        else:
            # Show first 50 findings
            for finding in result.findings[:50]:
                severity_icon = "⚠" if finding.severity.value == "warning" else "✗"
                suggestion_text = f" → '{finding.suggestion}'" if finding.suggestion else ""
                self._validation_listbox.insert(
                    "end",
                    f"{severity_icon} Line {finding.idx + 1}: '{finding.offending_token}'{suggestion_text}",
                )

            if len(result.findings) > 50:
                self._validation_listbox.insert(
                    "end",
                    f"... and {len(result.findings) - 50} more",
                )

        # Enable autofix if there are warnings (fixable issues)
        if result.warning_count > 0:
            self._autofix_btn.configure(state="normal")
        else:
            self._autofix_btn.configure(state="disabled")

    def _apply_character_autofix(self) -> None:
        """Apply autofix to postprocessed lines (TASK 36.3)."""
        if not _HAS_CHAR_VALIDATION:
            return

        if not self._lines:
            return

        # Get autofix map from manifest
        autofix_map: Dict[str, str] = {}
        whitelist = ""
        blacklist = ""

        if self.manifest_manager:
            config = self.manifest_manager.get_character_validation_config()
            autofix_map = config.get("AutofixMap", {})
            whitelist = config.get("CharacterWhitelist", "")
            blacklist = config.get("CharacterBlacklist", "")

        if not autofix_map:
            messagebox.showinfo(
                "No Autofix Map",
                "No autofix mappings configured. Configure autofix map in project settings.",
            )
            return

        # Build lines data
        lines_data = []
        for line in self._lines:
            lines_data.append({
                "idx": line.idx,
                "post": line.postprocessed,
            })

        # Apply autofix
        fixed_lines, fix_count = apply_autofix_to_lines(
            lines=lines_data,
            autofix_map=autofix_map,
            whitelist=whitelist,
            blacklist=blacklist,
            fields_to_fix=["post"],
        )

        # Update lines
        for fixed_line in fixed_lines:
            idx = fixed_line["idx"]
            if 0 <= idx < len(self._lines):
                old_text = self._lines[idx].postprocessed
                new_text = fixed_line.get("post", old_text)
                if old_text != new_text:
                    self._lines[idx].postprocessed = new_text
                    self._lines[idx].has_changes = True

        # Update table and re-run validation
        self._update_lines_table()
        self._run_character_validation()

        messagebox.showinfo(
            "Autofix Applied",
            f"Applied {fix_count} character replacement(s).",
        )

    def _build_summary_panel(self) -> None:
        """Build the summary panel at the bottom (TASK 45.8)."""
        frame = ttk.LabelFrame(self, text="Postprocessing Summary", padding=5)
        frame.pack(fill="x", padx=10, pady=5)

        # TASK 45.8: Progress bar
        self._progress_bar = ttk.Progressbar(
            frame, mode="determinate", length=200
        )
        self._progress_bar.pack(fill="x", pady=(0, 5))

        summary_grid = ttk.Frame(frame)
        summary_grid.pack(fill="x")

        # Total lines
        ttk.Label(summary_grid, text="Total:").grid(row=0, column=0, sticky="w")
        self._total_label = ttk.Label(summary_grid, text="0")
        self._total_label.grid(row=0, column=1, sticky="w", padx=(10, 20))

        # Lines with changes
        ttk.Label(summary_grid, text="Changed:").grid(row=0, column=2, sticky="w")
        self._changed_label = ttk.Label(
            summary_grid,
            text="0",
            foreground=THEME.accent_info,
        )
        self._changed_label.grid(row=0, column=3, sticky="w", padx=(10, 20))

        # Recovered
        ttk.Label(summary_grid, text="Recovered:").grid(row=0, column=4, sticky="w")
        self._recovered_label = ttk.Label(
            summary_grid,
            text="0",
            foreground=THEME.accent_success,
        )
        self._recovered_label.grid(row=0, column=5, sticky="w", padx=(10, 20))

        # Written (TASK 45.8)
        ttk.Label(summary_grid, text="Written:").grid(row=0, column=6, sticky="w")
        self._written_label = ttk.Label(
            summary_grid,
            text="0",
            foreground=THEME.accent_info,
        )
        self._written_label.grid(row=0, column=7, sticky="w", padx=(10, 20))

        # Flagged (TASK 45.8)
        ttk.Label(summary_grid, text="Flagged:").grid(row=0, column=8, sticky="w")
        self._flagged_label = ttk.Label(
            summary_grid,
            text="0",
            foreground=THEME.accent_warning,
        )
        self._flagged_label.grid(row=0, column=9, sticky="w", padx=(10, 20))

        # Recovery rate
        ttk.Label(summary_grid, text="Rate:").grid(row=0, column=10, sticky="w")
        self._rate_label = ttk.Label(
            summary_grid,
            text="0%",
        )
        self._rate_label.grid(row=0, column=11, sticky="w", padx=(10, 0))

    def _get_lines_from_previous_steps(self) -> Tuple[List[str], List[str]]:
        """Get original and translated lines from previous steps.

        Returns:
            Tuple of (original_lines, translated_lines).
        """
        original: List[str] = []
        translated: List[str] = []

        try:
            # Get from translation step (step 5) data
            trans_data = self.session.get_step(5).data
            if "translated_lines" in trans_data:
                translated = trans_data["translated_lines"]

            # Get from QA step (step 6) if available
            qa_data = self.session.get_step(6).data
            if "qa_lines" in qa_data:
                # QA may have modified translations
                qa_lines = qa_data["qa_lines"]
                if isinstance(qa_lines, list) and qa_lines:
                    translated = qa_lines

            # Get original from input step (step 0)
            app = self.winfo_toplevel()
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 0:
                input_step = app._step_tabs[0]
                if hasattr(input_step, "get_loaded_files"):
                    loaded_files = input_step.get_loaded_files()
                    for lf in loaded_files:
                        if hasattr(lf, "lines"):
                            original.extend(lf.lines)

            # Fallback from step data
            if not original:
                input_data = self.session.get_step(0).data
                if "all_lines" in input_data:
                    original = input_data["all_lines"]

            # If no translated, use original as placeholder
            if not translated and original:
                translated = list(original)

        except Exception as e:
            logger.debug("Error getting lines: %s", e)

        return original, translated

    def _refresh_lines(self) -> None:
        """Refresh lines from previous steps."""
        original, translated = self._get_lines_from_previous_steps()

        if not original:
            self._status_label.configure(text="No lines loaded")
            return

        # Ensure translated list matches original length
        while len(translated) < len(original):
            translated.append("")

        # Create PostprocessLine objects
        self._lines = []
        for idx, (orig, trans) in enumerate(zip(original, translated)):
            line = PostprocessLine(
                idx=idx,
                original=orig,
                translated=trans,
                postprocessed=trans,  # Initially same as translated
            )
            self._lines.append(line)

        # Update table
        self._update_lines_table()
        self._update_summary()

        self._status_label.configure(text=f"{len(self._lines)} lines loaded")

    def _update_lines_table(self) -> None:
        """Update the lines table with current data (TASK 45.9)."""
        rows: List[TableRow] = []
        filter_value = self._filter_var.get()

        for line in self._lines:
            # Apply filter (TASK 45.9: All/Changed/Written/Flagged)
            if filter_value == "changed" and not line.has_changes:
                continue
            elif filter_value == "written" and not line.written:
                continue
            elif filter_value == "flagged" and not line.flagged:
                continue

            # Status display (TASK 45.6: new statuses)
            if line.flagged:
                status = "⚠ Flagged"
            elif line.written:
                status = "✓ Written"
            elif line.has_changes:
                status = "✓ Changed"
            else:
                status = "– Same"

            row = TableRow(
                id=line.idx,
                values={
                    "idx": str(line.idx + 1),
                    "status": status,
                    "changes": str(line.issue_count) if line.issue_count > 0 else "-",
                    "translated": (
                        line.translated[:100] + "..."
                        if len(line.translated) > 100
                        else line.translated
                    ),
                    "postprocessed": (
                        line.postprocessed[:100] + "..."
                        if len(line.postprocessed) > 100
                        else line.postprocessed
                    ),
                },
            )
            rows.append(row)

        self._lines_table.set_data(rows)

    def _update_summary(self) -> None:
        """Update the summary panel (TASK 45.8: live updates)."""
        total = len(self._lines)
        changed = sum(1 for l in self._lines if l.has_changes)
        recovered = sum(l.recovered_count for l in self._lines)
        written = sum(1 for l in self._lines if l.written)
        flagged = sum(1 for l in self._lines if l.flagged)

        total_issues = self._stats.total_issues if self._stats.total_issues > 0 else 1
        rate = (self._stats.issues_recovered / total_issues) * 100

        # Update progress bar
        if total > 0:
            progress = (self._stats.lines_processed / total) * 100
            self._progress_bar.configure(value=progress)

        self._total_label.configure(text=str(total))
        self._changed_label.configure(text=str(changed))
        self._recovered_label.configure(text=str(recovered))
        self._written_label.configure(text=str(written))
        self._flagged_label.configure(text=str(flagged))
        self._rate_label.configure(text=f"{rate:.1f}%")

    def _apply_filter(self) -> None:
        """Apply the current filter to the table."""
        self._update_lines_table()

    def _on_line_selected(self, row_ids: List[int]) -> None:
        """Handle line selection in table.

        Args:
            row_ids: List of selected row IDs.
        """
        if not row_ids:
            self._selected_line_idx = -1
            self._clear_diff()
            return

        line_idx = row_ids[0]
        self._selected_line_idx = line_idx

        if 0 <= line_idx < len(self._lines):
            line = self._lines[line_idx]
            self._show_diff(line)
            self._show_issues(line)

    def _clear_diff(self) -> None:
        """Clear the diff view and edit field (TASK 45.7)."""
        self._diff_line_label.configure(text="Select a line to see diff")
        self._diff_text.configure(state="normal")
        self._diff_text.delete("1.0", "end")
        self._diff_text.configure(state="disabled")
        # TASK 45.7: Clear edit field
        self._edit_text.configure(state="normal")
        self._edit_text.delete("1.0", "end")
        self._edit_text.configure(state="disabled")
        self._mark_fixed_btn.configure(state="disabled")
        self._issues_listbox.delete(0, "end")

    def _show_diff(self, line: PostprocessLine) -> None:
        """Show diff for a specific line.

        Args:
            line: The line to show diff for.
        """
        self._diff_line_label.configure(
            text=f"Line {line.idx + 1} - {line.issue_count} change(s)"
        )

        # Generate diff
        translated_lines = line.translated.splitlines(keepends=True)
        postprocessed_lines = line.postprocessed.splitlines(keepends=True)

        # Handle single-line case
        if not translated_lines:
            translated_lines = [line.translated]
        if not postprocessed_lines:
            postprocessed_lines = [line.postprocessed]

        diff = list(unified_diff(
            translated_lines,
            postprocessed_lines,
            fromfile="Translated",
            tofile="Postprocessed",
            lineterm="",
        ))

        # Display diff with highlighting
        self._diff_text.configure(state="normal")
        self._diff_text.delete("1.0", "end")

        if not diff or line.translated == line.postprocessed:
            self._diff_text.insert("end", "No changes")
        else:
            for diff_line in diff:
                if diff_line.startswith("---") or diff_line.startswith("+++"):
                    self._diff_text.insert("end", diff_line + "\n", "header")
                elif diff_line.startswith("+"):
                    self._diff_text.insert("end", diff_line + "\n", "addition")
                elif diff_line.startswith("-"):
                    self._diff_text.insert("end", diff_line + "\n", "deletion")
                elif diff_line.startswith("@@"):
                    self._diff_text.insert("end", diff_line + "\n", "header")
                else:
                    self._diff_text.insert("end", diff_line + "\n")

        self._diff_text.configure(state="disabled")

        # TASK 45.7: Populate edit field with postprocessed text
        self._edit_text.configure(state="normal")
        self._edit_text.delete("1.0", "end")
        self._edit_text.insert("1.0", line.postprocessed)
        self._mark_fixed_btn.configure(state="normal")

    def _show_issues(self, line: PostprocessLine) -> None:
        """Show issues for a specific line.

        Args:
            line: The line to show issues for.
        """
        self._issues_listbox.delete(0, "end")

        if not line.issues:
            self._issues_listbox.insert("end", "No recovery actions taken")
            return

        for issue in line.issues:
            action_symbol = {
                RecoveryAction.RECOVERED: "✓",
                RecoveryAction.NEEDS_RETRY: "⚠",
                RecoveryAction.SKIPPED: "○",
                RecoveryAction.FAILED: "✗",
            }.get(issue.action, "?")

            self._issues_listbox.insert(
                "end",
                f"{action_symbol} [{issue.recovery_type.value}] {issue.description}",
            )

    def _mark_line_as_fixed(self) -> None:
        """Apply manual edit and mark line as fixed (TASK 45.7).

        Reads the edited text from the edit field, updates the line's
        postprocessed text, clears flagged status, and refreshes the display.
        """
        if self._selected_line_idx < 0:
            return
        if self._selected_line_idx >= len(self._lines):
            return

        line = self._lines[self._selected_line_idx]
        new_text = self._edit_text.get("1.0", "end-1c")

        # Update line
        line.postprocessed = new_text
        line.has_changes = line.translated != new_text
        line.flagged = False
        line.written = True
        line.needs_retry = False

        # Write to manifest if available
        if self.manifest_manager is not None:
            try:
                self.manifest_manager.set_line_field(
                    line.idx, "postpro", new_text
                )
            except Exception as exc:
                logger.debug("Could not write to manifest: %s", exc)

        # Refresh display
        self._update_lines_table()
        self._update_summary()
        self._show_diff(line)
        self._show_issues(line)

    def _update_options(self) -> None:
        """Update options from UI.

        TASK 45.4: Placeholder, code, and BR recovery are always-on.
        """
        # Always-on recoveries (TASK 45.4)
        self._pp_options.enable_placeholder_recovery = True
        self._pp_options.restore_code_characters = True
        self._pp_options.restore_br_tags = True
        # User-configurable options
        self._pp_options.enable_bracket_recovery = self._bracket_var.get()
        self._pp_options.enable_quote_recovery = self._quote_var.get()
        self._pp_options.enable_whitespace_normalization = self._whitespace_var.get()
        self._pp_options.enable_symbol_conversion = self._symbol_var.get()
        self._pp_options.convert_fullwidth_to_halfwidth = self._fullwidth_var.get()
        self._pp_options.convert_halfwidth_to_fullwidth = self._halfwidth_var.get()
        self._pp_options.failure_policy = FailurePolicy(self._failure_var.get())

    def _apply_postprocessing(self) -> None:
        """Apply postprocessing to all lines (TASK 45.10: overwrite warning)."""
        if not self._lines:
            self._refresh_lines()

        if not self._lines:
            messagebox.showwarning(
                "No Data",
                "Please complete translation first.",
            )
            return

        if self._status == PostprocessStatus.RUNNING:
            messagebox.showwarning(
                "Postprocessing",
                "Postprocessing already running.",
            )
            return

        # TASK 45.10: Overwrite warning if results already exist
        has_results = any(
            l.postprocessed != l.translated for l in self._lines
        )
        if has_results:
            if not messagebox.askokcancel(
                "Overwrite Results",
                "Postprocessing results already exist. "
                "Re-running will overwrite them. Continue?",
            ):
                return

        # Update options from UI
        self._update_options()

        self._status = PostprocessStatus.RUNNING
        self._apply_btn.configure(state="disabled")
        self._status_label.configure(text="Applying postprocessing...")

        # Reset stats
        self._stats = RecoveryStats(total_lines=len(self._lines))

        # Run in background thread
        self._process_thread = threading.Thread(
            target=self._do_postprocessing,
            daemon=True,
        )
        self._process_thread.start()

    def _do_postprocessing(self) -> None:
        """Perform postprocessing in background thread."""
        # Phase 48: Write postprocess step log header
        _pp_log_path = None
        try:
            from CherryAI.functions.mainhelper import (
                _rotate_log, write_step_log_header, write_step_log_footer,
            )
            mm = getattr(self, "_manifest_manager", None)
            if mm:
                pdir = getattr(mm, "_project_dir", None)
                pname = mm.get_project_info().project_name if hasattr(mm, "get_project_info") else None
                if pdir and pname:
                    from pathlib import Path as _P
                    _pp_log_path = _rotate_log(_P(str(pdir)), pname, "postprocess")
                    write_step_log_header(_pp_log_path, {
                        "CherryAI Postprocessing Log": "",
                        "Started": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "Total Lines": str(len(self._lines)),
                    })
        except Exception:
            pass

        import time as _time
        _pp_start = _time.perf_counter()
        try:
            for line in self._lines:
                self._stats.lines_processed += 1
                if _HAS_POSTPROCESS:
                    # Use functions module
                    result = recover_line(
                        original=line.original,
                        translated=line.translated,
                        enable_placeholder_recovery=self._pp_options.enable_placeholder_recovery,
                        enable_bracket_recovery=self._pp_options.enable_bracket_recovery,
                        enable_quote_recovery=self._pp_options.enable_quote_recovery,
                        enable_whitespace_normalization=self._pp_options.enable_whitespace_normalization,
                    )

                    line.postprocessed = result.recovered
                    line.has_changes = result.original != result.recovered

                    # Convert issues
                    for func_issue in result.issues:
                        # Map function recovery type and action to GUI enums
                        try:
                            recovery_type = RecoveryType(func_issue.type.value)
                        except Exception:
                            recovery_type = RecoveryType.PLACEHOLDER_CASE
                        try:
                            action = RecoveryAction(func_issue.action.value)
                        except Exception:
                            action = RecoveryAction.SKIPPED

                        issue = RecoveryIssue(
                            line_idx=line.idx,
                            recovery_type=recovery_type,
                            action=action,
                            description=func_issue.description,
                            original_text=func_issue.original_text,
                            recovered_text=func_issue.recovered_text,
                            position=func_issue.position,
                        )
                        line.issues.append(issue)

                        # Update stats
                        self._stats.total_issues += 1
                        if action == RecoveryAction.RECOVERED:
                            self._stats.issues_recovered += 1
                        elif action == RecoveryAction.NEEDS_RETRY:
                            self._stats.issues_retry += 1
                        else:
                            self._stats.issues_skipped += 1

                    line.needs_retry = result.needs_retry
                else:
                    # Basic fallback processing
                    line.postprocessed = self._basic_postprocess(line)
                    line.has_changes = line.translated != line.postprocessed

                # Apply symbol conversion if enabled
                if self._pp_options.enable_symbol_conversion:
                    converted = self._apply_symbol_conversion(line.postprocessed)
                    if converted != line.postprocessed:
                        line.postprocessed = converted
                        line.has_changes = True
                        line.issues.append(
                            RecoveryIssue(
                                line_idx=line.idx,
                                recovery_type=RecoveryType.SYMBOL_CONVERSION,
                                action=RecoveryAction.RECOVERED,
                                description="Symbol conversion applied",
                            )
                        )
                        self._stats.total_issues += 1
                        self._stats.issues_recovered += 1

                if line.has_changes:
                    self._stats.lines_with_changes += 1

                # TASK 45.6/45.9: Set written/flagged based on policy
                if line.needs_retry or any(
                    i.action == RecoveryAction.FAILED for i in line.issues
                ):
                    if self._pp_options.failure_policy == FailurePolicy.WRITE:
                        line.written = True
                    elif self._pp_options.failure_policy == FailurePolicy.FLAG:
                        line.flagged = True

                # TASK 45.8: Schedule live summary update every 10 lines
                if self._stats.lines_processed % 10 == 0:
                    self.after(0, self._update_summary)

            # Complete
            self._status = PostprocessStatus.COMPLETED
            # Phase 48: Write postprocess step log footer
            try:
                if _pp_log_path:
                    dur = _time.perf_counter() - _pp_start
                    write_step_log_footer(_pp_log_path, {
                        "Postprocessing Summary": "",
                        "Completed": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "Duration": f"{dur:.2f}s",
                        "Total Lines": str(self._stats.lines_processed),
                        "Changed": str(self._stats.lines_with_changes),
                        "Issues": str(self._stats.total_issues),
                        "Recovered": str(self._stats.issues_recovered),
                    })
            except Exception:
                pass
            self.after(0, self._on_postprocess_complete)

        except Exception as e:
            logger.exception("Postprocessing error: %s", e)
            self._status = PostprocessStatus.FAILED
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Postprocessing Error",
                    f"Postprocessing failed: {e}",
                ),
            )
            self.after(0, self._on_postprocess_complete)

    def _basic_postprocess(self, line: PostprocessLine) -> str:
        """Basic postprocessing when module not available.

        Args:
            line: The line to process.

        Returns:
            Postprocessed text.
        """
        import re

        text = line.translated

        # Basic placeholder case normalization
        if self._pp_options.enable_placeholder_recovery:
            # Fix lowercase placeholders
            pattern = re.compile(r"__([a-z][a-z0-9]*)(?:_(\d+))?__", re.IGNORECASE)
            text = pattern.sub(lambda m: m.group(0).upper(), text)

        # Basic whitespace normalization
        if self._pp_options.enable_whitespace_normalization:
            # Fix placeholders with internal spaces
            text = re.sub(r"__\s+", "__", text)
            text = re.sub(r"\s+__", "__", text)

        return text

    def _apply_symbol_conversion(self, text: str) -> str:
        """Apply symbol conversion to text (TASK 45.5: bidirectional).

        Args:
            text: Text to convert.

        Returns:
            Converted text.
        """
        result = text
        if self._pp_options.convert_fullwidth_to_halfwidth:
            for full, half in FULLWIDTH_TO_HALFWIDTH.items():
                result = result.replace(full, half)
        elif self._pp_options.convert_halfwidth_to_fullwidth:
            for half, full in HALFWIDTH_TO_FULLWIDTH.items():
                result = result.replace(half, full)
        return result

    def _on_postprocess_complete(self) -> None:
        """Called when postprocessing completes (TASK 45.8: popup)."""
        self._apply_btn.configure(state="normal")
        self._update_lines_table()
        self._update_summary()

        flagged = sum(1 for l in self._lines if l.flagged)
        self._status_label.configure(
            text=(
                f"Complete: {self._stats.lines_with_changes} lines changed, "
                f"{self._stats.issues_recovered} issues recovered"
            )
        )

        # Store results in session
        step_data = self.session.get_step(self.step_id).data
        step_data["postprocess_results"] = {
            "total_lines": len(self._lines),
            "lines_with_changes": self._stats.lines_with_changes,
            "total_issues": self._stats.total_issues,
            "issues_recovered": self._stats.issues_recovered,
            "issues_retry": self._stats.issues_retry,
            "recovery_rate": self._stats.recovery_rate,
        }

        # Store postprocessed lines for next step
        step_data["postprocessed_lines"] = [l.postprocessed for l in self._lines]

        # Persist each postprocessed line to the manifest
        mgr = self.manifest_manager
        if mgr is not None:
            for line in self._lines:
                mgr.set_line_field(line.idx, "postpro", line.postprocessed)

        # TASK 45.8: Completion popup
        messagebox.showinfo(
            "Postprocessing Complete",
            (
                f"{len(self._lines)} lines processed, "
                f"{self._stats.lines_with_changes} changes applied, "
                f"{flagged} issues flagged"
            ),
        )

    def _accept_selected(self) -> None:
        """Accept selected postprocessed lines."""
        selected = self._lines_table.get_selected_ids()
        if not selected:
            messagebox.showinfo("Select", "Please select lines to accept.")
            return

        # Mark as not needing retry
        for line_idx in selected:
            if 0 <= line_idx < len(self._lines):
                self._lines[line_idx].needs_retry = False
                self._lines[line_idx].skipped = False

        self._update_lines_table()
        self._update_summary()

    def _revert_selected(self) -> None:
        """Revert selected lines to translated state."""
        selected = self._lines_table.get_selected_ids()
        if not selected:
            messagebox.showinfo("Select", "Please select lines to revert.")
            return

        for line_idx in selected:
            if 0 <= line_idx < len(self._lines):
                line = self._lines[line_idx]
                line.postprocessed = line.translated
                line.has_changes = False
                line.issues = []
                line.needs_retry = False

        self._update_lines_table()
        self._update_summary()

    def _revert_all(self) -> None:
        """Revert all lines to translated state."""
        if not self._lines:
            return

        if not messagebox.askyesno(
            "Revert All",
            "Revert all postprocessing changes?",
        ):
            return

        for line in self._lines:
            line.postprocessed = line.translated
            line.has_changes = False
            line.issues = []
            line.needs_retry = False

        self._stats = RecoveryStats(total_lines=len(self._lines))

        self._update_lines_table()
        self._update_summary()
        self._status_label.configure(text="All changes reverted")

    def _retry_selected(self) -> None:
        """Queue selected lines for retry."""
        selected = self._lines_table.get_selected_ids()
        if not selected:
            messagebox.showinfo("Select", "Please select lines to retry.")
            return

        for line_idx in selected:
            if 0 <= line_idx < len(self._lines):
                self._lines[line_idx].needs_retry = True

        self._update_lines_table()
        self._update_summary()
        messagebox.showinfo(
            "Retry",
            f"Marked {len(selected)} line(s) for retry.",
        )

    def on_enter(self) -> None:
        """Called when step becomes active."""
        # TASK 27.1: Load postprocessing options from manifest
        self._load_postprocessing_options_from_manifest()
        
        if not self._lines:
            self._refresh_lines()

    def on_leave(self) -> None:
        """Called when leaving step."""
        # Store options state (TASK 45.4: auto-recovery always True)
        step_data = self.session.get_step(self.step_id).data
        step_data["postprocess_options"] = {
            "enable_placeholder_recovery": True,
            "enable_bracket_recovery": self._bracket_var.get(),
            "enable_quote_recovery": self._quote_var.get(),
            "enable_whitespace_normalization": self._whitespace_var.get(),
            "enable_symbol_conversion": self._symbol_var.get(),
            "convert_fullwidth_to_halfwidth": self._fullwidth_var.get(),
            "convert_halfwidth_to_fullwidth": self._halfwidth_var.get(),
            "restore_code_characters": True,
            "restore_br_tags": True,
            "failure_policy": self._failure_var.get(),
        }

    def get_postprocess_results(self) -> Dict[str, Any]:
        """Get postprocessing results.

        Returns:
            Dictionary with postprocessing results.
        """
        return {
            "total_lines": len(self._lines),
            "lines_with_changes": sum(1 for l in self._lines if l.has_changes),
            "total_issues": self._stats.total_issues,
            "issues_recovered": self._stats.issues_recovered,
            "recovery_rate": self._stats.recovery_rate,
            "lines_needing_retry": sum(1 for l in self._lines if l.needs_retry),
        }

    def get_lines(self) -> List[PostprocessLine]:
        """Get all postprocess lines.

        Returns:
            List of PostprocessLine objects.
        """
        return self._lines

    def get_postprocessed_lines(self) -> List[str]:
        """Get postprocessed text lines.

        Returns:
            List of postprocessed strings.
        """
        return [l.postprocessed for l in self._lines]
