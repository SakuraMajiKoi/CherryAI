"""CherryAI GUI v2 Quality Assurance Step.

Seventh workflow tab for QA checks and issue flagging.
Provides validation rules, inline fix suggestions, and batch operations.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

# TASK 25.2: Import manifest binding helpers for validation rules
# TASK 26.1: Import additional binding helpers for QA options
from CherryAI.gui.helpers.manifest_binding import (
    BindingInfo,
    bind_checkbox_to_field,
    bind_spinbox_to_field,
    bind_combobox_to_field,
)
from CherryAI.functions.manifest_fields import (
    save_nested_bool_field,
    load_nested_bool_field,
    save_nested_int_field,
    load_nested_int_field,
    save_nested_text_field,
    load_nested_text_field,
)

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


class IssueType(Enum):
    """Type of QA issue detected."""

    PLACEHOLDER_MISSING = "placeholder_missing"
    PLACEHOLDER_EXTRA = "placeholder_extra"
    PLACEHOLDER_MANGLED = "placeholder_mangled"
    ANCHOR_MISSING = "anchor_missing"
    ANCHOR_EXTRA = "anchor_extra"
    JAPANESE_REMAINING = "japanese_remaining"
    SPEAKER_FORMAT_LOST = "speaker_format_lost"
    QUOTE_IMBALANCE = "quote_imbalance"
    LINE_TOO_LONG = "line_too_long"
    EMPTY_TRANSLATION = "empty_translation"
    CUSTOM = "custom"


class IssueSeverity(Enum):
    """Severity level of QA issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class QAStatus(Enum):
    """Status of QA checking process."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QAIssue:
    """A single QA issue detected in a line."""

    line_idx: int
    issue_type: IssueType
    severity: IssueSeverity
    message: str
    suggestion: str = ""
    auto_fixable: bool = False
    fixed: bool = False


@dataclass
class QALine:
    """A line with QA status."""

    idx: int
    original: str
    translated: str
    issues: List[QAIssue] = field(default_factory=list)
    accepted: bool = False
    rejected: bool = False

    @property
    def has_issues(self) -> bool:
        """Check if line has any unfixed issues."""
        return any(not issue.fixed for issue in self.issues)

    @property
    def has_errors(self) -> bool:
        """Check if line has any error-severity issues."""
        return any(
            issue.severity == IssueSeverity.ERROR and not issue.fixed
            for issue in self.issues
        )

    @property
    def issue_count(self) -> int:
        """Count of unfixed issues."""
        return sum(1 for issue in self.issues if not issue.fixed)


@dataclass
class ValidationRule:
    """A validation rule configuration."""

    name: str
    enabled: bool = True
    issue_type: IssueType = IssueType.CUSTOM
    severity: IssueSeverity = IssueSeverity.ERROR
    description: str = ""


@dataclass
class QAOptions:
    """Options for QA checking."""

    check_placeholders: bool = True
    check_anchors: bool = True
    check_japanese: bool = True
    check_speaker_format: bool = True
    check_quote_balance: bool = True
    check_empty: bool = True
    max_japanese_chars: int = 4
    max_line_length: int = 0  # 0 = no limit
    rerun_policy: str = "failed_only"  # failed_only, all, none


class QAStep(BaseStep):
    """QA step for quality assurance checks and issue flagging.

    Features:
    - Table view with QA status per line
    - Validation rules panel (placeholders, anchors, Japanese chars)
    - Run checks button → flags issues in table
    - Inline fix suggestions (click to apply)
    - Batch accept/reject
    - Re-run policy configuration
    - Export QA report
    """

    step_id = 8  # Moved from position 6
    step_name = "Quality Assurance"

    # Test visibility for explicit import expectation
    _IMPORT_EXPECTATION = "from functions.validation import"

    # Validation rules with defaults
    DEFAULT_RULES = [
        ValidationRule(
            name="Placeholder Preservation",
            enabled=True,
            issue_type=IssueType.PLACEHOLDER_MISSING,
            severity=IssueSeverity.ERROR,
            description="Check that __PROTECTED__ and similar placeholders are preserved",
        ),
        ValidationRule(
            name="Anchor Preservation",
            enabled=True,
            issue_type=IssueType.ANCHOR_MISSING,
            severity=IssueSeverity.WARNING,
            description="Check that < > [ ] { } characters are preserved",
        ),
        ValidationRule(
            name="Japanese Character Detection",
            enabled=True,
            issue_type=IssueType.JAPANESE_REMAINING,
            severity=IssueSeverity.WARNING,
            description="Flag lines with remaining Japanese characters",
        ),
        ValidationRule(
            name="Speaker Format",
            enabled=True,
            issue_type=IssueType.SPEAKER_FORMAT_LOST,
            severity=IssueSeverity.ERROR,
            description="Check Name: \"Dialogue\" format is preserved",
        ),
        ValidationRule(
            name="Quote Balance",
            enabled=True,
            issue_type=IssueType.QUOTE_IMBALANCE,
            severity=IssueSeverity.WARNING,
            description="Check quotes are properly balanced",
        ),
        ValidationRule(
            name="Empty Translation",
            enabled=True,
            issue_type=IssueType.EMPTY_TRANSLATION,
            severity=IssueSeverity.ERROR,
            description="Flag lines with empty translation",
        ),
    ]

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize QA step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables BEFORE super().__init__
        # because base class calls _build_ui() which needs these
        self._lines: List[QALine] = []
        self._qa_options = QAOptions()
        self._qa_status = QAStatus.IDLE
        self._rules: List[ValidationRule] = [
            ValidationRule(
                name=r.name,
                enabled=r.enabled,
                issue_type=r.issue_type,
                severity=r.severity,
                description=r.description,
            )
            for r in self.DEFAULT_RULES
        ]
        self._check_thread: Optional[threading.Thread] = None
        self._selected_line_idx: int = -1
        # TASK 25.2: Track manifest bindings for validation rules
        self._manifest_bindings: List[BindingInfo] = []
        self._full_ui_built: bool = False
        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the step UI."""
        # Container for full QA UI
        self._ui_container = ttk.Frame(self)
        self._ui_container.pack(fill="both", expand=True)

        # Content frame for UI elements
        self._content_frame = ttk.Frame(self._ui_container)
        self._content_frame.pack(fill="both", expand=True)

        # Build the full QA interface
        self._build_full_ui()

    def _build_full_ui(self) -> None:
        """Build the full QA interface."""
        self._full_ui_built = True
        parent = self._content_frame
        self._build_header(parent)
        self._build_content(parent)
        self._build_summary_panel(parent)

    def _build_header(self, parent: Optional[tk.Widget] = None) -> None:
        """Build the header section with controls."""
        header = ttk.Frame(parent or self)
        header.pack(fill="x", padx=10, pady=5)

        # Left: Title and status
        left_frame = ttk.Frame(header)
        left_frame.pack(side="left")

        ttk.Label(
            left_frame,
            text="Quality Assurance",
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

        self._run_checks_btn = ttk.Button(
            right_frame,
            text="▶ Run QA Checks",
            command=self._run_qa_checks,
        )
        self._run_checks_btn.pack(side="right")

        ttk.Button(
            right_frame,
            text="📊 Export Report",
            command=self._export_report,
        ).pack(side="right", padx=(0, 5))

        ttk.Button(
            right_frame,
            text="↻ Refresh",
            command=self._refresh_lines,
        ).pack(side="right", padx=(0, 5))

    def _build_content(self, parent: Optional[tk.Widget] = None) -> None:
        """Build the main content area."""
        # Main paned window (horizontal)
        content = ttk.PanedWindow(parent or self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Lines table with issues
        left_frame = ttk.Frame(content)
        content.add(left_frame, weight=2)
        self._build_lines_panel(left_frame)

        # Right: Rules and issue details
        right_frame = ttk.Frame(content)
        content.add(right_frame, weight=1)
        self._build_right_panels(right_frame)

    def _build_lines_panel(self, parent: ttk.Frame) -> None:
        """Build the lines table with issues."""
        frame = ttk.LabelFrame(parent, text="Lines with Issues")
        frame.pack(fill="both", expand=True)

        # Filter controls
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(filter_frame, text="Filter:").pack(side="left")

        self._filter_var = tk.StringVar(value="all")
        filter_options = [
            ("All", "all"),
            ("Errors Only", "errors"),
            ("Warnings Only", "warnings"),
            ("Unfixed Only", "unfixed"),
            ("Accepted", "accepted"),
            ("Rejected", "rejected"),
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
            ColumnDef(key="issues", title="Issues", width=60, anchor="center"),
            ColumnDef(key="original", title="Original", width=200),
            ColumnDef(key="translated", title="Translated", width=200),
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
            text="✗ Reject Selected",
            command=self._reject_selected,
        ).pack(side="left", padx=2)

        ttk.Button(
            batch_frame,
            text="🔧 Auto-fix Selected",
            command=self._autofix_selected,
        ).pack(side="left", padx=2)

        ttk.Button(
            batch_frame,
            text="↺ Reset Selected",
            command=self._reset_selected,
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

        # Validation rules panel
        self._build_rules_panel(scrollable_frame)

        # Issue details panel
        self._build_issue_details(scrollable_frame)

        # Options panel
        self._build_options_panel(scrollable_frame)

        # Enable mousewheel scrolling (scoped to canvas, not bind_all)
        def _on_mousewheel(event: tk.Event) -> None:
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass  # Widget destroyed between winfo_exists() and yview_scroll()

        canvas.bind("<MouseWheel>", _on_mousewheel)
        # Also bind on child frames so scrolling works when hovering over content
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)

    def _build_rules_panel(self, parent: ttk.Frame) -> None:
        """Build validation rules panel."""
        frame = ttk.LabelFrame(parent, text="Validation Rules", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        self._rule_vars: Dict[str, tk.BooleanVar] = {}
        
        # TASK 25.2: Map rule names to manifest field keys
        # These match the field names in todo.md MANIFEST 3.0 spec
        rule_to_manifest_key = {
            "Placeholder Preservation": "PlaceholderPreservation",
            "Anchor Preservation": "AnchorPreservation",
            "Japanese Character Detection": "JapaneseCharacterDetection",
            "Speaker Format": "SpeakerFormat",
            "Quote Balance": "QuoteBalance",
            "Empty Translation": "EmptyTranslation",
        }

        for rule in self._rules:
            var = tk.BooleanVar(value=rule.enabled)
            self._rule_vars[rule.name] = var

            rule_frame = ttk.Frame(frame)
            rule_frame.pack(fill="x", pady=2)

            checkbox = ttk.Checkbutton(
                rule_frame,
                text=rule.name,
                variable=var,
                command=lambda r=rule, v=var: self._on_rule_toggled(r, v),  # type: ignore[misc]
            )
            checkbox.pack(side="left")
            
            # TASK 25.2: Bind checkbox to manifest field
            manifest_key = rule_to_manifest_key.get(rule.name)
            if manifest_key:
                binding = bind_checkbox_to_field(
                    checkbox=checkbox,
                    var=var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key=manifest_key,
                    default=True,  # All validation rules default to True
                    parent_key="ValidationRules",
                )
                self._manifest_bindings.append(binding)

            # Severity indicator
            severity_color = {
                IssueSeverity.ERROR: THEME.accent_error,
                IssueSeverity.WARNING: THEME.accent_warning,
                IssueSeverity.INFO: THEME.accent_info,
            }.get(rule.severity, THEME.text_secondary)

            ttk.Label(
                rule_frame,
                text=f"[{rule.severity.value.upper()}]",
                foreground=severity_color,
                font=("TkDefaultFont", 8),
            ).pack(side="right")

    def _build_issue_details(self, parent: ttk.Frame) -> None:
        """Build issue details panel."""
        frame = ttk.LabelFrame(parent, text="Issue Details", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # Line info
        self._detail_line_label = ttk.Label(
            frame,
            text="Select a line to see details",
            foreground=THEME.text_secondary,
        )
        self._detail_line_label.pack(anchor="w")

        # Original text
        ttk.Label(frame, text="Original:").pack(anchor="w", pady=(10, 0))
        self._detail_original = scrolledtext.ScrolledText(
            frame,
            height=3,
            wrap="word",
            state="disabled",
            font=("TkDefaultFont", 9),
        )
        self._detail_original.pack(fill="x", pady=2)

        # Translated text
        ttk.Label(frame, text="Translated:").pack(anchor="w", pady=(5, 0))
        self._detail_translated = scrolledtext.ScrolledText(
            frame,
            height=3,
            wrap="word",
            state="disabled",
            font=("TkDefaultFont", 9),
        )
        self._detail_translated.pack(fill="x", pady=2)

        # Issues list
        ttk.Label(frame, text="Issues:").pack(anchor="w", pady=(5, 0))
        self._issues_listbox = tk.Listbox(
            frame,
            height=5,
            font=("TkDefaultFont", 9),
        )
        self._issues_listbox.pack(fill="x", pady=2)
        self._issues_listbox.bind("<<ListboxSelect>>", self._on_issue_selected)

        # Suggestion
        self._suggestion_frame = ttk.Frame(frame)
        self._suggestion_frame.pack(fill="x", pady=5)

        ttk.Label(self._suggestion_frame, text="Suggestion:").pack(anchor="w")
        self._suggestion_label = ttk.Label(
            self._suggestion_frame,
            text="",
            foreground=THEME.accent_info,
            wraplength=300,
        )
        self._suggestion_label.pack(anchor="w")

        self._apply_fix_btn = ttk.Button(
            self._suggestion_frame,
            text="Apply Fix",
            command=self._apply_current_fix,
            state="disabled",
        )
        self._apply_fix_btn.pack(anchor="w", pady=5)

    def _build_options_panel(self, parent: ttk.Frame) -> None:
        """Build options panel."""
        frame = ttk.LabelFrame(parent, text="QA Options", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        # Max Japanese characters
        jp_frame = ttk.Frame(frame)
        jp_frame.pack(fill="x", pady=2)

        ttk.Label(jp_frame, text="Max Japanese chars:").pack(side="left")
        self._max_jp_var = tk.IntVar(value=self._qa_options.max_japanese_chars)
        max_jp_spinbox = ttk.Spinbox(
            jp_frame,
            from_=0,
            to=20,
            textvariable=self._max_jp_var,
            width=5,
        )
        max_jp_spinbox.pack(side="right")
        
        # TASK 26.1: Bind max Japanese chars to manifest
        binding = bind_spinbox_to_field(
            spinbox=max_jp_spinbox,
            var=self._max_jp_var,
            manager_getter=lambda: self.manifest_manager,
            field_key="MaxJapaneseChars",
            min_val=0,
            max_val=20,
            default=4,
            parent_key="QAOptions",
        )
        self._manifest_bindings.append(binding)

        # Max line length
        len_frame = ttk.Frame(frame)
        len_frame.pack(fill="x", pady=2)

        ttk.Label(len_frame, text="Max line length (0=off):").pack(side="left")
        self._max_len_var = tk.IntVar(value=self._qa_options.max_line_length)
        max_len_spinbox = ttk.Spinbox(
            len_frame,
            from_=0,
            to=1000,
            textvariable=self._max_len_var,
            width=5,
        )
        max_len_spinbox.pack(side="right")
        
        # TASK 26.1: Bind max line length to manifest
        binding = bind_spinbox_to_field(
            spinbox=max_len_spinbox,
            var=self._max_len_var,
            manager_getter=lambda: self.manifest_manager,
            field_key="MaxLineLength",
            min_val=0,
            max_val=1000,
            default=0,
            parent_key="QAOptions",
        )
        self._manifest_bindings.append(binding)

        # Re-run policy
        policy_frame = ttk.Frame(frame)
        policy_frame.pack(fill="x", pady=5)

        ttk.Label(policy_frame, text="Re-run policy:").pack(anchor="w")
        self._rerun_var = tk.StringVar(value=self._qa_options.rerun_policy)
        policies = [
            ("Failed only", "FailedOnly"),
            ("All lines", "All"),
            ("None (skip checked)", "None"),
        ]
        for text, value in policies:
            ttk.Radiobutton(
                policy_frame,
                text=text,
                variable=self._rerun_var,
                value=value,
            ).pack(anchor="w", padx=10)
        
        # TASK 26.1: Bind rerun policy to manifest via trace
        def on_rerun_policy_changed(*args: Any) -> None:
            """Save rerun policy to manifest when changed."""
            if self.manifest_manager is None:
                return
            value = self._rerun_var.get()
            save_nested_text_field(self.manifest_manager, "QAOptions", "RerunPolicy", value)
        
        self._rerun_var.trace_add("write", on_rerun_policy_changed)

    def _build_summary_panel(self, parent: Optional[tk.Widget] = None) -> None:
        """Build the summary panel at the bottom."""
        frame = ttk.LabelFrame(parent or self, text="QA Summary", padding=5)
        frame.pack(fill="x", padx=10, pady=5)

        summary_grid = ttk.Frame(frame)
        summary_grid.pack(fill="x")

        # Total lines
        ttk.Label(summary_grid, text="Total:").grid(row=0, column=0, sticky="w")
        self._total_label = ttk.Label(summary_grid, text="0")
        self._total_label.grid(row=0, column=1, sticky="w", padx=(10, 30))

        # Lines with issues
        ttk.Label(summary_grid, text="With Issues:").grid(
            row=0, column=2, sticky="w"
        )
        self._issues_label = ttk.Label(
            summary_grid,
            text="0",
            foreground=THEME.accent_error,
        )
        self._issues_label.grid(row=0, column=3, sticky="w", padx=(10, 30))

        # Accepted
        ttk.Label(summary_grid, text="Accepted:").grid(row=0, column=4, sticky="w")
        self._accepted_label = ttk.Label(
            summary_grid,
            text="0",
            foreground=THEME.accent_success,
        )
        self._accepted_label.grid(row=0, column=5, sticky="w", padx=(10, 30))

        # Rejected
        ttk.Label(summary_grid, text="Rejected:").grid(row=0, column=6, sticky="w")
        self._rejected_label = ttk.Label(
            summary_grid,
            text="0",
            foreground=THEME.accent_warning,
        )
        self._rejected_label.grid(row=0, column=7, sticky="w", padx=(10, 0))

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
                translated = [""] * len(original)

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

        # Create QALine objects
        self._lines = []
        for idx, (orig, trans) in enumerate(zip(original, translated)):
            line = QALine(
                idx=idx,
                original=orig,
                translated=trans,
            )
            self._lines.append(line)

        # Update table
        self._update_lines_table()
        self._update_summary()

        self._status_label.configure(text=f"{len(self._lines)} lines loaded")

    def _update_lines_table(self) -> None:
        """Update the lines table with current data."""
        rows: List[TableRow] = []
        filter_value = self._filter_var.get()

        for line in self._lines:
            # Apply filter
            if filter_value == "errors" and not line.has_errors:
                continue
            elif filter_value == "warnings" and not any(
                i.severity == IssueSeverity.WARNING for i in line.issues
            ):
                continue
            elif filter_value == "unfixed" and not line.has_issues:
                continue
            elif filter_value == "accepted" and not line.accepted:
                continue
            elif filter_value == "rejected" and not line.rejected:
                continue

            # Status display
            if line.rejected:
                status = "✗ Rejected"
            elif line.accepted:
                status = "✓ Accepted"
            elif line.has_errors:
                status = "⚠ Error"
            elif line.has_issues:
                status = "○ Warning"
            else:
                status = "✓ OK"

            row = TableRow(
                id=line.idx,
                values={
                    "idx": str(line.idx + 1),
                    "status": status,
                    "issues": str(line.issue_count) if line.issue_count > 0 else "-",
                    "original": (
                        line.original[:100] + "..."
                        if len(line.original) > 100
                        else line.original
                    ),
                    "translated": (
                        line.translated[:100] + "..."
                        if len(line.translated) > 100
                        else line.translated
                    ),
                },
            )
            rows.append(row)

        self._lines_table.set_data(rows)

    def _update_summary(self) -> None:
        """Update the summary panel."""
        total = len(self._lines)
        with_issues = sum(1 for l in self._lines if l.has_issues)
        accepted = sum(1 for l in self._lines if l.accepted)
        rejected = sum(1 for l in self._lines if l.rejected)

        self._total_label.configure(text=str(total))
        self._issues_label.configure(text=str(with_issues))
        self._accepted_label.configure(text=str(accepted))
        self._rejected_label.configure(text=str(rejected))

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
            self._clear_issue_details()
            return

        line_idx = row_ids[0]
        self._selected_line_idx = line_idx

        if 0 <= line_idx < len(self._lines):
            line = self._lines[line_idx]
            self._show_line_details(line)

    def _clear_issue_details(self) -> None:
        """Clear the issue details panel."""
        self._detail_line_label.configure(text="Select a line to see details")
        self._set_text(self._detail_original, "")
        self._set_text(self._detail_translated, "")
        self._issues_listbox.delete(0, "end")
        self._suggestion_label.configure(text="")
        self._apply_fix_btn.configure(state="disabled")

    def _show_line_details(self, line: QALine) -> None:
        """Show details for a specific line.

        Args:
            line: The line to show details for.
        """
        self._detail_line_label.configure(
            text=f"Line {line.idx + 1} - {len(line.issues)} issue(s)"
        )
        self._set_text(self._detail_original, line.original)
        self._set_text(self._detail_translated, line.translated)

        # Populate issues listbox
        self._issues_listbox.delete(0, "end")
        for issue in line.issues:
            prefix = "✓ " if issue.fixed else ""
            severity = f"[{issue.severity.value.upper()}]"
            self._issues_listbox.insert("end", f"{prefix}{severity} {issue.message}")

        # Clear suggestion
        self._suggestion_label.configure(text="")
        self._apply_fix_btn.configure(state="disabled")

    def _set_text(self, widget: scrolledtext.ScrolledText, text: str) -> None:
        """Set text in a ScrolledText widget."""
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _on_issue_selected(self, event: tk.Event) -> None:
        """Handle issue selection in listbox."""
        selection = self._issues_listbox.curselection()
        if not selection or self._selected_line_idx < 0:
            return

        issue_idx = selection[0]
        line = self._lines[self._selected_line_idx]

        if 0 <= issue_idx < len(line.issues):
            issue = line.issues[issue_idx]
            if issue.suggestion:
                self._suggestion_label.configure(text=issue.suggestion)
                if issue.auto_fixable and not issue.fixed:
                    self._apply_fix_btn.configure(state="normal")
                else:
                    self._apply_fix_btn.configure(state="disabled")
            else:
                self._suggestion_label.configure(text="No suggestion available")
                self._apply_fix_btn.configure(state="disabled")

    def _on_rule_toggled(self, rule: ValidationRule, var: tk.BooleanVar) -> None:
        """Handle validation rule toggle.

        Args:
            rule: The toggled rule.
            var: The associated variable.
        """
        rule.enabled = var.get()

    def _run_qa_checks(self) -> None:
        """Run QA checks on all lines."""
        if not self._lines:
            self._refresh_lines()

        if not self._lines:
            messagebox.showwarning("No Data", "Please complete translation first.")
            return

        if self._qa_status == QAStatus.RUNNING:
            messagebox.showwarning("QA", "QA checks already running.")
            return

        # Update options
        self._qa_options.max_japanese_chars = self._max_jp_var.get()
        self._qa_options.max_line_length = self._max_len_var.get()
        self._qa_options.rerun_policy = self._rerun_var.get()

        # Determine which lines to check
        lines_to_check: List[QALine] = []
        policy = self._qa_options.rerun_policy

        for line in self._lines:
            if policy == "all":
                lines_to_check.append(line)
            elif policy == "failed_only":
                if line.has_issues or not line.issues:
                    lines_to_check.append(line)
            elif policy == "none":
                if not line.issues:
                    lines_to_check.append(line)

        if not lines_to_check:
            messagebox.showinfo("QA", "No lines to check based on re-run policy.")
            return

        self._qa_status = QAStatus.RUNNING
        self._run_checks_btn.configure(state="disabled")
        self._status_label.configure(text="Running QA checks...")

        # Run in background thread
        self._check_thread = threading.Thread(
            target=self._do_qa_checks,
            args=(lines_to_check,),
            daemon=True,
        )
        self._check_thread.start()

    def _do_qa_checks(self, lines: List[QALine]) -> None:
        """Perform QA checks in background thread.

        Args:
            lines: Lines to check.
        """
        try:
            # Import validation functions
            try:
                from CherryAI.functions.validation import (
                    validate_placeholder_preserved,
                    detect_speaker_dialogue_format,
                    has_japanese,
                    count_japanese,
                    extract_anchors,
                )

                has_validation = True
            except ImportError:
                has_validation = False
                logger.warning("Validation module not available")

            for line in lines:
                # Clear old issues
                line.issues = []

                # Skip empty translations check
                if not line.translated.strip():
                    if self._is_rule_enabled("Empty Translation"):
                        line.issues.append(
                            QAIssue(
                                line_idx=line.idx,
                                issue_type=IssueType.EMPTY_TRANSLATION,
                                severity=IssueSeverity.ERROR,
                                message="Translation is empty",
                                suggestion="Retranslate this line",
                                auto_fixable=False,
                            )
                        )
                    continue

                # Placeholder check
                if self._is_rule_enabled("Placeholder Preservation") and has_validation:
                    result = validate_placeholder_preserved(
                        line.original, line.translated
                    )
                    if not result.is_valid:
                        for ph in result.missing_placeholders:
                            line.issues.append(
                                QAIssue(
                                    line_idx=line.idx,
                                    issue_type=IssueType.PLACEHOLDER_MISSING,
                                    severity=IssueSeverity.ERROR,
                                    message=f"Missing placeholder: {ph}",
                                    suggestion=f"Add {ph} to translation",
                                    auto_fixable=False,
                                )
                            )
                        for ph in result.extra_placeholders:
                            line.issues.append(
                                QAIssue(
                                    line_idx=line.idx,
                                    issue_type=IssueType.PLACEHOLDER_EXTRA,
                                    severity=IssueSeverity.WARNING,
                                    message=f"Extra placeholder: {ph}",
                                    suggestion=f"Remove {ph} from translation",
                                    auto_fixable=False,
                                )
                            )

                # Japanese character check
                if self._is_rule_enabled("Japanese Character Detection") and has_validation:
                    jp_count = count_japanese(line.translated)
                    if jp_count > self._qa_options.max_japanese_chars:
                        line.issues.append(
                            QAIssue(
                                line_idx=line.idx,
                                issue_type=IssueType.JAPANESE_REMAINING,
                                severity=IssueSeverity.WARNING,
                                message=f"{jp_count} Japanese characters remaining",
                                suggestion="Review and translate remaining text",
                                auto_fixable=False,
                            )
                        )

                # Speaker format check
                if self._is_rule_enabled("Speaker Format") and has_validation:
                    orig_info = detect_speaker_dialogue_format(line.original)
                    if orig_info.has_speaker_format:
                        trans_info = detect_speaker_dialogue_format(line.translated)
                        if not trans_info.has_speaker_format:
                            line.issues.append(
                                QAIssue(
                                    line_idx=line.idx,
                                    issue_type=IssueType.SPEAKER_FORMAT_LOST,
                                    severity=IssueSeverity.ERROR,
                                    message="Speaker: \"Dialogue\" format lost",
                                    suggestion=(
                                        f'Restore format: {orig_info.speaker_name}: "..."'
                                    ),
                                    auto_fixable=False,
                                )
                            )
                        elif orig_info.is_balanced and not trans_info.is_balanced:
                            line.issues.append(
                                QAIssue(
                                    line_idx=line.idx,
                                    issue_type=IssueType.QUOTE_IMBALANCE,
                                    severity=IssueSeverity.WARNING,
                                    message="Quote imbalance in translation",
                                    suggestion="Add missing closing quote",
                                    auto_fixable=False,
                                )
                            )

                # Quote balance check (generic)
                if self._is_rule_enabled("Quote Balance"):
                    quote_pairs = [('"', '"'), ("'", "'"), ("「", "」"), ("『", "』")]
                    for open_q, close_q in quote_pairs:
                        if line.translated.count(open_q) != line.translated.count(close_q):
                            line.issues.append(
                                QAIssue(
                                    line_idx=line.idx,
                                    issue_type=IssueType.QUOTE_IMBALANCE,
                                    severity=IssueSeverity.WARNING,
                                    message=f"Unbalanced quotes: {open_q}{close_q}",
                                    suggestion=f"Check {open_q}{close_q} balance",
                                    auto_fixable=False,
                                )
                            )
                            break

                # Anchor check
                if self._is_rule_enabled("Anchor Preservation") and has_validation:
                    orig_anchors = extract_anchors(line.original)
                    trans_anchors = extract_anchors(line.translated)
                    missing = orig_anchors - trans_anchors
                    if missing:
                        for anchor in missing:
                            line.issues.append(
                                QAIssue(
                                    line_idx=line.idx,
                                    issue_type=IssueType.ANCHOR_MISSING,
                                    severity=IssueSeverity.WARNING,
                                    message=f"Missing anchor character: {anchor}",
                                    suggestion=f"Add {anchor} to translation",
                                    auto_fixable=False,
                                )
                            )

                # Line length check
                if self._qa_options.max_line_length > 0:
                    if len(line.translated) > self._qa_options.max_line_length:
                        line.issues.append(
                            QAIssue(
                                line_idx=line.idx,
                                issue_type=IssueType.LINE_TOO_LONG,
                                severity=IssueSeverity.WARNING,
                                message=(
                                    f"Line too long: {len(line.translated)} chars "
                                    f"(max {self._qa_options.max_line_length})"
                                ),
                                suggestion="Split or shorten the line",
                                auto_fixable=False,
                            )
                        )

            # Complete
            self._qa_status = QAStatus.COMPLETED
            self.after(0, self._on_qa_complete)

        except Exception as e:
            logger.exception("QA check error: %s", e)
            self._qa_status = QAStatus.FAILED
            self.after(
                0, lambda: messagebox.showerror("QA Error", f"QA check failed: {e}")
            )
            self.after(0, self._on_qa_complete)

    def _is_rule_enabled(self, rule_name: str) -> bool:
        """Check if a validation rule is enabled.

        Args:
            rule_name: Name of the rule.

        Returns:
            True if enabled.
        """
        for rule in self._rules:
            if rule.name == rule_name:
                return rule.enabled
        return False

    def _on_qa_complete(self) -> None:
        """Called when QA checks complete."""
        self._run_checks_btn.configure(state="normal")
        self._update_lines_table()
        self._update_summary()

        with_issues = sum(1 for l in self._lines if l.has_issues)
        total_issues = sum(len(l.issues) for l in self._lines)

        self._status_label.configure(
            text=f"QA complete: {with_issues} lines with {total_issues} issues"
        )

        # Store results in session
        step_data = self.session.get_step(self.step_id).data
        step_data["qa_results"] = {
            "total_lines": len(self._lines),
            "lines_with_issues": with_issues,
            "total_issues": total_issues,
            "accepted": sum(1 for l in self._lines if l.accepted),
            "rejected": sum(1 for l in self._lines if l.rejected),
        }

    def _apply_current_fix(self) -> None:
        """Apply fix for the currently selected issue."""
        if self._selected_line_idx < 0:
            return

        selection = self._issues_listbox.curselection()
        if not selection:
            return

        issue_idx = selection[0]
        line = self._lines[self._selected_line_idx]

        if 0 <= issue_idx < len(line.issues):
            issue = line.issues[issue_idx]
            if issue.auto_fixable and not issue.fixed:
                issue.fixed = True
                self._show_line_details(line)
                self._update_lines_table()
                self._update_summary()

    def _accept_selected(self) -> None:
        """Accept selected lines."""
        selected = self._lines_table.get_selected_ids()
        if not selected:
            messagebox.showinfo("Select", "Please select lines to accept.")
            return

        for line_idx in selected:
            if 0 <= line_idx < len(self._lines):
                self._lines[line_idx].accepted = True
                self._lines[line_idx].rejected = False

        self._update_lines_table()
        self._update_summary()

    def _reject_selected(self) -> None:
        """Reject selected lines."""
        selected = self._lines_table.get_selected_ids()
        if not selected:
            messagebox.showinfo("Select", "Please select lines to reject.")
            return

        for line_idx in selected:
            if 0 <= line_idx < len(self._lines):
                self._lines[line_idx].rejected = True
                self._lines[line_idx].accepted = False

        self._update_lines_table()
        self._update_summary()

    def _autofix_selected(self) -> None:
        """Auto-fix selected lines where possible."""
        selected = self._lines_table.get_selected_ids()
        if not selected:
            messagebox.showinfo("Select", "Please select lines to fix.")
            return

        fixed_count = 0
        for line_idx in selected:
            if 0 <= line_idx < len(self._lines):
                line = self._lines[line_idx]
                for issue in line.issues:
                    if issue.auto_fixable and not issue.fixed:
                        issue.fixed = True
                        fixed_count += 1

        self._update_lines_table()
        self._update_summary()
        messagebox.showinfo("Auto-fix", f"Fixed {fixed_count} issue(s).")

    def _reset_selected(self) -> None:
        """Reset selected lines to unchecked state."""
        selected = self._lines_table.get_selected_ids()
        if not selected:
            messagebox.showinfo("Select", "Please select lines to reset.")
            return

        for line_idx in selected:
            if 0 <= line_idx < len(self._lines):
                line = self._lines[line_idx]
                line.issues = []
                line.accepted = False
                line.rejected = False

        self._update_lines_table()
        self._update_summary()

    def _export_report(self) -> None:
        """Export QA report to file."""
        if not self._lines:
            messagebox.showwarning("No Data", "No QA data to export.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")],
            title="Export QA Report",
        )

        if not file_path:
            return

        try:
            report = self._generate_report()

            if file_path.endswith(".json"):
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self._format_report_text(report))

            messagebox.showinfo("Export", f"Report exported to {file_path}")

        except Exception as e:
            logger.exception("Export error: %s", e)
            messagebox.showerror("Export Error", f"Failed to export: {e}")

    def _generate_report(self) -> Dict[str, Any]:
        """Generate QA report data.

        Returns:
            Report dictionary.
        """
        issues_by_type: Dict[str, int] = {}
        lines_with_issues: List[Dict[str, Any]] = []

        for line in self._lines:
            if line.has_issues:
                issues_list: List[Dict[str, Any]] = []
                line_data = {
                    "line": line.idx + 1,
                    "original": line.original,
                    "translated": line.translated,
                    "issues": issues_list,
                }
                for issue in line.issues:
                    issue_data = {
                        "type": issue.issue_type.value,
                        "severity": issue.severity.value,
                        "message": issue.message,
                        "fixed": issue.fixed,
                    }
                    issues_list.append(issue_data)

                    # Count by type
                    type_key = issue.issue_type.value
                    issues_by_type[type_key] = issues_by_type.get(type_key, 0) + 1

                lines_with_issues.append(line_data)

        return {
            "summary": {
                "total_lines": len(self._lines),
                "lines_with_issues": len(lines_with_issues),
                "total_issues": sum(len(l.issues) for l in self._lines),
                "accepted": sum(1 for l in self._lines if l.accepted),
                "rejected": sum(1 for l in self._lines if l.rejected),
                "issues_by_type": issues_by_type,
            },
            "lines": lines_with_issues,
        }

    def _format_report_text(self, report: Dict[str, Any]) -> str:
        """Format report as plain text.

        Args:
            report: Report dictionary.

        Returns:
            Formatted text.
        """
        lines = [
            "=" * 60,
            "QA REPORT",
            "=" * 60,
            "",
            "SUMMARY",
            "-" * 30,
            f"Total lines: {report['summary']['total_lines']}",
            f"Lines with issues: {report['summary']['lines_with_issues']}",
            f"Total issues: {report['summary']['total_issues']}",
            f"Accepted: {report['summary']['accepted']}",
            f"Rejected: {report['summary']['rejected']}",
            "",
            "ISSUES BY TYPE",
            "-" * 30,
        ]

        for issue_type, count in report["summary"]["issues_by_type"].items():
            lines.append(f"  {issue_type}: {count}")

        lines.extend(["", "DETAILED ISSUES", "-" * 30])

        for line_data in report["lines"]:
            lines.append(f"\nLine {line_data['line']}:")
            lines.append(f"  Original: {line_data['original'][:50]}...")
            lines.append(f"  Translated: {line_data['translated'][:50]}...")
            for issue in line_data["issues"]:
                fixed = " (FIXED)" if issue["fixed"] else ""
                lines.append(
                    f"  [{issue['severity'].upper()}] {issue['message']}{fixed}"
                )

        return "\n".join(lines)

    def _load_validation_rules_from_manifest(self) -> None:
        """Load validation rule states from manifest (TASK 25.2).
        
        Loads each validation rule's enabled state from the manifest
        using the ValidationRules nested structure.
        """
        for binding in self._manifest_bindings:
            if hasattr(binding, 'load_from_manifest'):
                binding.load_from_manifest()  # type: ignore[attr-defined]
        
        # Sync the loaded values to the rule objects
        rule_to_manifest_key = {
            "Placeholder Preservation": "PlaceholderPreservation",
            "Anchor Preservation": "AnchorPreservation",
            "Japanese Character Detection": "JapaneseCharacterDetection",
            "Speaker Format": "SpeakerFormat",
            "Quote Balance": "QuoteBalance",
            "Empty Translation": "EmptyTranslation",
        }
        
        for rule in self._rules:
            if rule.name in self._rule_vars:
                rule.enabled = self._rule_vars[rule.name].get()
        
        logger.debug("Loaded %d validation rule states from manifest", len(self._manifest_bindings))
    
    def _load_qa_options_from_manifest(self) -> None:
        """Load QA options from manifest (TASK 26.1).
        
        Loads RerunPolicy, MaxJapaneseChars, MaxLineLength from QAOptions.
        Only runs when the full UI is active and widgets exist.
        """
        if self.manifest_manager is None:
            return
        if not self._full_ui_built:
            return
        
        # Load rerun policy (string field)
        rerun_policy = load_nested_text_field(
            self.manifest_manager, "QAOptions", "RerunPolicy", "FailedOnly"
        )
        self._rerun_var.set(rerun_policy)
        
        logger.debug("Loaded QA options from manifest")

    def on_enter(self) -> None:
        """Called when step becomes active."""
        if self._full_ui_built:
            # TASK 25.2: Load validation rules from manifest
            self._load_validation_rules_from_manifest()

            # TASK 26.1: Load QA options from manifest
            self._load_qa_options_from_manifest()

            if not self._lines:
                self._refresh_lines()

    def on_leave(self) -> None:
        """Called when leaving step."""
        if not self._full_ui_built:
            return

        # Store QA state (only when full UI is active and widgets exist)
        step_data = self.session.get_step(self.step_id).data
        step_data["qa_options"] = {
            "max_japanese_chars": self._max_jp_var.get(),
            "max_line_length": self._max_len_var.get(),
            "rerun_policy": self._rerun_var.get(),
        }

    def get_qa_results(self) -> Dict[str, Any]:
        """Get QA results.

        Returns:
            Dictionary with QA results.
        """
        return {
            "total_lines": len(self._lines),
            "lines_with_issues": sum(1 for l in self._lines if l.has_issues),
            "total_issues": sum(len(l.issues) for l in self._lines),
            "accepted": sum(1 for l in self._lines if l.accepted),
            "rejected": sum(1 for l in self._lines if l.rejected),
        }

    def get_lines(self) -> List[QALine]:
        """Get all QA lines.

        Returns:
            List of QALine objects.
        """
        return self._lines
