"""CherryAI GUI v2 Preprocessing Step.

Fourth workflow tab for configuring and applying preprocessing rules.
Provides toggles for deduplication, symbol conversion, ellipsis handling,
placeholders, and speaker formatting with live preview and diff view.

Updated: TASK 16.5 - Now uses modi/ modules via mode_adapter for preprocessing.
TASK 24.1: Standard Mode Toggles bound to manifest.
TASK 24.2: Protect Code Patterns bound to manifest.
TASK 24.3: Custom Placeholders and Anchor Removal bound to manifest.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

# TASK 16.5: Import mode adapter for preprocessing via modi/ modules
from CherryAI.gui.helpers.mode_adapter import (
    apply_ellipsis_compression,
    apply_symbol_conversion,
    apply_prot_compression,
    apply_protect_code,
    apply_custom_placeholder,
    apply_preprocessing,
    get_common_patterns,
)

# TASK 24.1: Import manifest binding helpers
from CherryAI.gui.helpers.manifest_binding import (
    BindingInfo,
    bind_checkbox_to_field,
    bind_spinbox_to_field,
)

# TASK 24.2/24.3: Import special format helpers for pattern lists
from CherryAI.functions.manifest_fields import (
    save_protect_code_patterns,
    load_protect_code_patterns,
    save_custom_placeholders,
    load_custom_placeholders,
    save_anchor_removal,
    load_anchor_removal,
    load_character_notes,
)

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)

# Tag name → display label mapping for the preview filter and Changes column.
TAG_DISPLAY_NAMES: Dict[str, str] = {
    "symbol_conversion": "Symbol Conversion",
    "ellipsis": "Ellipsis Compression",
    "protect_code": "Protected",
    "placeholder": "Custom Placeholder",
    "prot_compression": "Protected Compression",
    "dedup": "Deduplicated",
    "aggressive_dedup": "Aggressive Deduplicated",
    "anchor": "Anchored",
    "speaker": "Speaker Name Replacement",
}

# Reverse mapping: filter dropdown label → internal tag name.
FILTER_TAG_MAP: Dict[str, str] = {v: k for k, v in TAG_DISPLAY_NAMES.items()}

# TASK 16.5: Import centralized preprocessing config from store
# Use conditional import to avoid circular imports
try:
    from CherryAI.gui.state.store import DEFAULT_PREPROCESS_CONFIG
except ImportError:
    # Fallback if circular import occurs
    DEFAULT_PREPROCESS_CONFIG: Dict[str, Any] = {  # type: ignore[no-redef]
        "dedup_enabled": True,
        "dedup_threshold": 1,
        "aggressive_dedup_enabled": False,  # TASK 42.4
        "ellipsis_enabled": True,
        "symbol_conversion_enabled": True,
        "symbol_src_lang": "ja",
        "symbol_tgt_lang": "en",
        "prot_compression_enabled": True,
        "speaker_replacement_enabled": False,
        "code_spacing_enabled": False,
        "placeholder_rules": [],
        "protect_code_patterns": [],
    }

# Tooltip descriptions for each rule
RULE_TOOLTIPS = {
    "dedup": (
        "Deduplication replaces consecutive identical lines with placeholders.\n"
        "Threshold controls when replacement happens:\n"
        "  - 0: Disabled\n"
        "  - 1: Replace all repeated occurrences (keep first)\n"
        "  - N>1: Replace when N+ consecutive identical lines occur"
    ),
    "ellipsis": (
        "Compresses long ellipsis sequences (... or ……) to a single ellipsis.\n"
        "Helps prevent AI confusion with variable ellipsis lengths."
    ),
    "symbol_conversion": (
        "Converts symbols between languages:\n"
        "  - Japanese → English: 。→ .  、→ ,  ！→ !  ？→ ?\n"
        "  - Fullwidth → Halfwidth punctuation"
    ),
    "prot_compression": (
        "Compresses adjacent __PROTECTED__ tokens into indexed form:\n"
        "  __PROTECTED____PROTECTED__ → __PROTECTED_2__\n"
        "Reduces token count and improves AI handling."
    ),
    "speaker_replacement": (
        "Replaces speaker names based on speakers.analysis.tsv.\n"
        "Uses second column as replacement (empty = skip)."
    ),
    "code_spacing": (
        "Enforces spacing rules around code based on code.analysis.tsv.\n"
        "Respects IsInvisible/IsWord/IsNumber/IsBoundary flags."
    ),
    "placeholder": (
        "Custom Placeholder: Replace patterns with tokens.\n"
        "Pattern: Regex or literal to match\n"
        "Token: Replacement placeholder (e.g., __NAME__)"
    ),
    "protect_code": (
        "Protect Code: Replace code patterns with __PROTECTED__.\n"
        "Pattern: Regex matching code to protect\n"
        "Preserved exactly and restored after translation."
    ),
}


class PreprocessingStep(BaseStep):
    """Preprocessing step for configuring and applying rules.

    Features:
    - Rules panel with toggles for each preprocessing mode
    - Deduplication threshold control
    - Custom placeholder rule editor
    - Protect code pattern editor
    - Preview table showing original vs preprocessed
    - Diff column highlighting changes
    - Apply button to run preprocessing
    - Auto-suggestion for rules based on analysis
    """

    step_id = 3
    step_name = "Preprocessing"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize Preprocessing step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        self._config: Dict[str, Any] = dict(DEFAULT_PREPROCESS_CONFIG)
        self._preview_lines: List[Tuple[str, str, str, List[str]]] = []  # (original, processed, diff, tags)
        self._is_processing = False
        
        # TASK 24.1: Manifest bindings for standard rules
        self._manifest_bindings: List[BindingInfo] = []

        # UI variables (created in _build_ui)
        self._dedup_var: Optional[tk.BooleanVar] = None
        self._dedup_threshold_var: Optional[tk.IntVar] = None
        self._aggressive_dedup_var: Optional[tk.BooleanVar] = None  # TASK 42.4
        self._ellipsis_var: Optional[tk.BooleanVar] = None
        self._symbol_var: Optional[tk.BooleanVar] = None
        self._prot_var: Optional[tk.BooleanVar] = None
        self._speaker_var: Optional[tk.BooleanVar] = None
        self._code_spacing_var: Optional[tk.BooleanVar] = None

        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the Preprocessing UI."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Header with Apply button (row 0)
        self._build_header()

        # Progress bar (row 1, hidden by default)
        self._progress_frame = ttk.Frame(self)
        self._progress_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 2))
        self._progress_frame.grid_remove()

        self._progress_label = ttk.Label(
            self._progress_frame,
            text="",
            foreground=THEME.text_secondary,
        )
        self._progress_label.pack(side="left", padx=(0, 10))

        self._progress_bar = ttk.Progressbar(
            self._progress_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
        )
        self._progress_bar.pack(side="left", fill="x", expand=True)

        # Main content: rules panel (left) + preview table (right) (row 2)
        self._build_content()

    def _build_header(self) -> None:
        """Build the header with action buttons."""
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Title
        ttk.Label(
            header,
            text="Preprocessing Rules",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        # Apply button
        self._apply_btn = ttk.Button(
            header,
            text="▶ Apply Rules",
            command=self._apply_rules,
        )
        self._apply_btn.pack(side="right", padx=5)

        # Reset button
        ttk.Button(
            header,
            text="↺ Reset",
            command=self._reset_rules,
        ).pack(side="right", padx=5)

        # Auto-suggest button
        ttk.Button(
            header,
            text="💡 Auto-Suggest",
            command=self._auto_suggest,
        ).pack(side="right", padx=5)

    def _build_content(self) -> None:
        """Build the main content area with rules and preview."""
        # Horizontal paned window
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # Left: Rules panel
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        self._build_rules_panel(left_frame)

        # Right: Preview table
        right_frame = ttk.LabelFrame(paned, text="Preview")
        paned.add(right_frame, weight=2)
        self._build_preview_panel(right_frame)

    def _build_rules_panel(self, parent: ttk.Frame) -> None:
        """Build the rules configuration panel.

        Args:
            parent: Parent frame.
        """
        # Scrollable frame for rules
        canvas = tk.Canvas(parent, bg=THEME.bg_panel, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Standard Rules section
        self._build_standard_rules(scrollable)

        # Custom Placeholder section
        self._build_placeholder_section(scrollable)

        # Protect Code section
        self._build_protect_code_section(scrollable)

        # Anchoring section (TASK 42.1: renamed from Anchor Removal)
        self._build_anchoring_section(scrollable)

    def _build_standard_rules(self, parent: ttk.Frame) -> None:
        """Build standard preprocessing rules section.
        
        TASK 24.1: All toggles bound to manifest for auto-save/load.

        Args:
            parent: Parent frame.
        """
        section = ttk.LabelFrame(parent, text="Standard Rules")
        section.pack(fill="x", padx=5, pady=5)

        # Deduplication
        dedup_frame = ttk.Frame(section)
        dedup_frame.pack(fill="x", padx=10, pady=5)

        self._dedup_var = tk.BooleanVar(value=self._config["dedup_enabled"])
        dedup_cb = ttk.Checkbutton(
            dedup_frame,
            text="Deduplication",
            variable=self._dedup_var,
            command=self._on_config_changed,
        )
        dedup_cb.pack(side="left")
        self._add_tooltip(dedup_cb, RULE_TOOLTIPS["dedup"])
        
        # TASK 24.1: Bind to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=dedup_cb,
                var=self._dedup_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="Deduplication",
                default=True,
                parent_key="Preprocessing",
            )
        )

        ttk.Label(dedup_frame, text="Threshold:").pack(side="left", padx=(20, 5))
        self._dedup_threshold_var = tk.IntVar(value=self._config["dedup_threshold"])
        threshold_spin = ttk.Spinbox(
            dedup_frame,
            from_=0,
            to=10,
            width=5,
            textvariable=self._dedup_threshold_var,
            command=self._on_config_changed,
        )
        threshold_spin.pack(side="left")
        
        # TASK 42.4: Aggressive number deduplication toggle
        aggr_frame = ttk.Frame(section)
        aggr_frame.pack(fill="x", padx=10, pady=(0, 5))
        self._aggressive_dedup_var = tk.BooleanVar(
            value=self._config.get("aggressive_dedup_enabled", False),
        )
        aggr_cb = ttk.Checkbutton(
            aggr_frame,
            text="Aggressive Number Dedup",
            variable=self._aggressive_dedup_var,
            command=self._on_config_changed,
        )
        aggr_cb.pack(side="left", padx=(20, 0))
        self._add_tooltip(
            aggr_cb,
            "Treat lines differing only by numbers as duplicates.\n"
            "Numbers are normalized to a token for comparison "
            "and restored during postprocessing.",
        )
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=aggr_cb,
                var=self._aggressive_dedup_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="AggressiveNumberDedup",
                default=False,
                parent_key="Preprocessing",
            )
        )

        # TASK 24.1: Bind threshold to manifest
        self._manifest_bindings.append(
            bind_spinbox_to_field(
                spinbox=threshold_spin,
                var=self._dedup_threshold_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="DeduplicationThreshold",
                default=1,
                min_val=0,
                max_val=10,
                parent_key="Preprocessing",
            )
        )

        # Ellipsis
        ellipsis_frame = ttk.Frame(section)
        ellipsis_frame.pack(fill="x", padx=10, pady=5)

        self._ellipsis_var = tk.BooleanVar(value=self._config["ellipsis_enabled"])
        ellipsis_cb = ttk.Checkbutton(
            ellipsis_frame,
            text="Ellipsis Compression",
            variable=self._ellipsis_var,
            command=self._on_config_changed,
        )
        ellipsis_cb.pack(side="left")
        self._add_tooltip(ellipsis_cb, RULE_TOOLTIPS["ellipsis"])
        
        # TASK 24.1: Bind to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=ellipsis_cb,
                var=self._ellipsis_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="EllipsisCompression",
                default=True,
                parent_key="Preprocessing",
            )
        )

        # Symbol Conversion
        symbol_frame = ttk.Frame(section)
        symbol_frame.pack(fill="x", padx=10, pady=5)

        self._symbol_var = tk.BooleanVar(value=self._config["symbol_conversion_enabled"])
        symbol_cb = ttk.Checkbutton(
            symbol_frame,
            text="Symbol Conversion (JP → EN)",
            variable=self._symbol_var,
            command=self._on_config_changed,
        )
        symbol_cb.pack(side="left")
        self._add_tooltip(symbol_cb, RULE_TOOLTIPS["symbol_conversion"])
        
        # TASK 24.1: Bind to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=symbol_cb,
                var=self._symbol_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="SymbolConversion",
                default=True,
                parent_key="Preprocessing",
            )
        )

        # PROTECTED Compression
        prot_frame = ttk.Frame(section)
        prot_frame.pack(fill="x", padx=10, pady=5)

        self._prot_var = tk.BooleanVar(value=self._config["prot_compression_enabled"])
        prot_cb = ttk.Checkbutton(
            prot_frame,
            text="PROTECTED Token Compression",
            variable=self._prot_var,
            command=self._on_config_changed,
        )
        prot_cb.pack(side="left")
        self._add_tooltip(prot_cb, RULE_TOOLTIPS["prot_compression"])
        
        # TASK 24.1: Bind to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=prot_cb,
                var=self._prot_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="ProtCompression",
                default=True,
                parent_key="Preprocessing",
            )
        )

        # Speaker Replacement
        speaker_frame = ttk.Frame(section)
        speaker_frame.pack(fill="x", padx=10, pady=5)

        self._speaker_var = tk.BooleanVar(value=self._config["speaker_replacement_enabled"])
        speaker_cb = ttk.Checkbutton(
            speaker_frame,
            text="Speaker Name Replacement",
            variable=self._speaker_var,
            command=self._on_config_changed,
        )
        speaker_cb.pack(side="left")
        self._add_tooltip(speaker_cb, RULE_TOOLTIPS["speaker_replacement"])
        
        # TASK 24.1: Bind to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=speaker_cb,
                var=self._speaker_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="SpeakerNameReplacement",
                default=False,
                parent_key="Preprocessing",
            )
        )

        # Code Spacing
        spacing_frame = ttk.Frame(section)
        spacing_frame.pack(fill="x", padx=10, pady=5)

        self._code_spacing_var = tk.BooleanVar(value=self._config["code_spacing_enabled"])
        spacing_cb = ttk.Checkbutton(
            spacing_frame,
            text="Code Spacing Rules",
            variable=self._code_spacing_var,
            command=self._on_config_changed,
        )
        spacing_cb.pack(side="left")
        self._add_tooltip(spacing_cb, RULE_TOOLTIPS["code_spacing"])
        
        # TASK 24.1: Bind to manifest
        self._manifest_bindings.append(
            bind_checkbox_to_field(
                checkbox=spacing_cb,
                var=self._code_spacing_var,
                manager_getter=lambda: self.manifest_manager,
                field_key="CodeSpacingRules",
                default=False,
                parent_key="Preprocessing",
            )
        )

    def _build_placeholder_section(self, parent: ttk.Frame) -> None:
        """Build custom placeholder rules section.

        TASK 42.2: Added RegEx toggle and Treeview-based table.

        Args:
            parent: Parent frame.
        """
        section = ttk.LabelFrame(parent, text="Custom Placeholders")
        section.pack(fill="x", padx=5, pady=5)

        # Info label
        info_label = ttk.Label(
            section,
            text="Replace patterns with placeholder tokens.",
            foreground=THEME.text_secondary,
        )
        info_label.pack(anchor="w", padx=10, pady=(5, 0))

        # Treeview table (TASK 42.2)
        tree_frame = ttk.Frame(section)
        tree_frame.pack(fill="x", padx=10, pady=5)

        cols = ("pattern", "token", "is_regex")
        self._placeholder_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=4,
        )
        self._placeholder_tree.heading("pattern", text="Pattern")
        self._placeholder_tree.heading("token", text="Token")
        self._placeholder_tree.heading("is_regex", text="RegEx")

        self._placeholder_tree.column("pattern", width=180, stretch=True)
        self._placeholder_tree.column("token", width=120)
        self._placeholder_tree.column("is_regex", width=50, anchor="center")

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self._placeholder_tree.yview,
        )
        self._placeholder_tree.configure(yscrollcommand=scrollbar.set)
        self._placeholder_tree.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind double-click for editing and Delete for removal
        self._placeholder_tree.bind(
            "<Double-1>", lambda e: self._edit_placeholder_rule(),
        )
        self._placeholder_tree.bind(
            "<Delete>", lambda e: self._remove_placeholder_rule(),
        )

        # Add/Remove buttons
        btn_frame = ttk.Frame(section)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="+ Add", command=self._add_placeholder_rule).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="- Remove", command=self._remove_placeholder_rule).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="Edit", command=self._edit_placeholder_rule).pack(
            side="left", padx=2
        )

    def _build_protect_code_section(self, parent: ttk.Frame) -> None:
        """Build protect code patterns section.

        TASK 42.3: Treeview with RegEx column (default enabled).

        Args:
            parent: Parent frame.
        """
        section = ttk.LabelFrame(parent, text="Protect Code Patterns")
        section.pack(fill="x", padx=5, pady=5)

        # Info label
        info_label = ttk.Label(
            section,
            text="Patterns to protect from translation (replaced with __PROTECTED__).",
            foreground=THEME.text_secondary,
        )
        info_label.pack(anchor="w", padx=10, pady=(5, 0))

        # Treeview table (TASK 42.3)
        tree_frame = ttk.Frame(section)
        tree_frame.pack(fill="x", padx=10, pady=5)

        cols = ("pattern", "is_regex", "description")
        self._protect_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=4,
        )
        self._protect_tree.heading("pattern", text="Pattern")
        self._protect_tree.heading("is_regex", text="RegEx")
        self._protect_tree.heading("description", text="Description")

        self._protect_tree.column("pattern", width=200, stretch=True)
        self._protect_tree.column("is_regex", width=50, anchor="center")
        self._protect_tree.column("description", width=150, stretch=True)

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self._protect_tree.yview,
        )
        self._protect_tree.configure(yscrollcommand=scrollbar.set)
        self._protect_tree.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind double-click for editing and Delete for removal
        self._protect_tree.bind(
            "<Double-1>", lambda e: self._edit_protect_pattern(),
        )
        self._protect_tree.bind(
            "<Delete>", lambda e: self._remove_protect_pattern(),
        )

        # Add/Remove buttons
        btn_frame = ttk.Frame(section)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="+ Add", command=self._add_protect_pattern).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="- Remove", command=self._remove_protect_pattern).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="Edit", command=self._edit_protect_pattern).pack(
            side="left", padx=2
        )

        # Common patterns button
        ttk.Button(
            btn_frame, text="📋 Common Patterns", command=self._show_common_patterns
        ).pack(side="right", padx=2)

    def _build_anchoring_section(self, parent: ttk.Frame) -> None:
        """Build anchoring section with table-based management.

        TASK 42.1: Redesigned from single-field "Anchor Removal" to
        table-based "Anchoring" with Pattern, Action, Anchor Spec,
        RegEx, and Description columns.

        Args:
            parent: Parent frame.
        """
        section = ttk.LabelFrame(parent, text="Anchoring")
        section.pack(fill="x", padx=5, pady=5)

        # Info label
        info_label = ttk.Label(
            section,
            text="Remove patterns and restore at anchor positions after translation.",
            foreground=THEME.text_secondary,
        )
        info_label.pack(anchor="w", padx=10, pady=(5, 0))

        # Anchoring table (Treeview)
        tree_frame = ttk.Frame(section)
        tree_frame.pack(fill="x", padx=10, pady=5)

        cols = ("pattern", "action", "anchor_spec", "is_regex", "description")
        self._anchor_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=4,
        )
        self._anchor_tree.heading("pattern", text="Pattern")
        self._anchor_tree.heading("action", text="Action")
        self._anchor_tree.heading("anchor_spec", text="Anchor Spec")
        self._anchor_tree.heading("is_regex", text="RegEx")
        self._anchor_tree.heading("description", text="Description")

        self._anchor_tree.column("pattern", width=140, stretch=True)
        self._anchor_tree.column("action", width=70, anchor="center")
        self._anchor_tree.column("anchor_spec", width=120)
        self._anchor_tree.column("is_regex", width=50, anchor="center")
        self._anchor_tree.column("description", width=140, stretch=True)

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self._anchor_tree.yview,
        )
        self._anchor_tree.configure(yscrollcommand=scrollbar.set)
        self._anchor_tree.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind double-click for editing and Delete for removal
        self._anchor_tree.bind("<Double-1>", lambda e: self._edit_anchor_entry())
        self._anchor_tree.bind("<Delete>", lambda e: self._remove_anchor_entry())

        # Add/Edit/Remove buttons
        btn_frame = ttk.Frame(section)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="+ Add", command=self._add_anchor_entry).pack(
            side="left", padx=2,
        )
        ttk.Button(btn_frame, text="- Remove", command=self._remove_anchor_entry).pack(
            side="left", padx=2,
        )
        ttk.Button(btn_frame, text="Edit", command=self._edit_anchor_entry).pack(
            side="left", padx=2,
        )

    # ── Anchoring management methods (TASK 42.1) ──

    def _add_anchor_entry(self) -> None:
        """Add a new anchoring entry via dialog.

        TASK 42.1: Opens _AnchorDialog with fields for Pattern,
        Action, Anchor Spec, RegEx, and Description.
        """
        dialog = _AnchorDialog(self, "Add Anchoring Rule")
        if dialog.result:
            vals = (
                dialog.result["pattern"],
                dialog.result["action"],
                dialog.result["anchor_spec"],
                "✓" if dialog.result["is_regex"] else "✗",
                dialog.result["description"],
            )
            self._anchor_tree.insert("", tk.END, values=vals)
            self._sync_anchor_tree_to_manifest()
            self.session.set_dirty(True)

    def _remove_anchor_entry(self) -> None:
        """Remove selected anchoring entry.

        TASK 42.1: Deletes from tree and syncs to manifest.
        """
        sel = self._anchor_tree.selection()
        if sel:
            for item in sel:
                self._anchor_tree.delete(item)
            self._sync_anchor_tree_to_manifest()
            self.session.set_dirty(True)

    def _edit_anchor_entry(self) -> None:
        """Edit selected anchoring entry via dialog.

        TASK 42.1: Opens _AnchorDialog pre-populated with selected row.
        """
        sel = self._anchor_tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = self._anchor_tree.item(item, "values")
        if not vals or len(vals) < 5:
            return
        defaults = {
            "pattern": vals[0],
            "action": vals[1],
            "anchor_spec": vals[2],
            "is_regex": vals[3] == "✓",
            "description": vals[4],
        }
        dialog = _AnchorDialog(self, "Edit Anchoring Rule", defaults=defaults)
        if dialog.result:
            new_vals = (
                dialog.result["pattern"],
                dialog.result["action"],
                dialog.result["anchor_spec"],
                "✓" if dialog.result["is_regex"] else "✗",
                dialog.result["description"],
            )
            self._anchor_tree.item(item, values=new_vals)
            self._sync_anchor_tree_to_manifest()
            self.session.set_dirty(True)

    def _sync_anchor_tree_to_manifest(self) -> None:
        """Sync anchoring tree data to manifest.

        TASK 42.1: Reads all tree items and saves via save_anchor_removal.
        """
        anchors: List[Dict[str, Any]] = []
        for child in self._anchor_tree.get_children():
            vals = self._anchor_tree.item(child, "values")
            if vals and len(vals) >= 5:
                anchors.append({
                    "pattern": vals[0],
                    "action": vals[1],
                    "anchor_spec": vals[2],
                    "is_regex": vals[3] == "✓",
                    "description": vals[4],
                })
        # Update config list
        self._config["anchor_entries"] = anchors
        if self.manifest_manager:
            save_anchor_removal(self.manifest_manager, anchors)

    def _refresh_anchor_entries(self) -> None:
        """Refresh anchoring tree from manifest data.

        TASK 42.1: Loads entries and populates tree.
        """
        if not hasattr(self, "_anchor_tree"):
            return
        self._anchor_tree.delete(*self._anchor_tree.get_children())
        if not self.manifest_manager or not self.manifest_manager.is_loaded:
            return
        anchors = load_anchor_removal(self.manifest_manager)
        for a in anchors:
            vals = (
                a.get("pattern", ""),
                a.get("action", "remove"),
                a.get("anchor_spec", ""),
                "✓" if a.get("is_regex", True) else "✗",
                a.get("description", ""),
            )
            self._anchor_tree.insert("", tk.END, values=vals)
        self._config["anchor_entries"] = anchors

    def _build_preview_panel(self, parent: ttk.LabelFrame) -> None:
        """Build the preview table panel.

        TASK 42.8: Includes filter dropdown for preview filtering.

        Args:
            parent: Parent frame.
        """
        # TASK 42.8: Filter dropdown
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill="x", padx=5, pady=(5, 0))
        ttk.Label(filter_frame, text="Search:").pack(side="left")
        self._preview_filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self._preview_filter_var,
            values=[
                "All",
                "Changed",
                "Unchanged",
                "Deduplicated",
                "Aggressive Deduplicated",
                "Ellipsis Compression",
                "Symbol Conversion",
                "Protected Compression",
                "Custom Placeholder",
                "Protected",
                "Anchored",
                "Speaker Name Replacement",
            ],
            state="readonly",
            width=24,
        )
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda _: self._update_preview())
        self._filter_count_label = ttk.Label(filter_frame, text="")
        self._filter_count_label.pack(side="left", padx=5)

        # Define columns for preview
        columns = [
            ColumnDef(key="line_num", title="#", width=50, anchor="e"),
            ColumnDef(key="original", title="Original", width=300, stretch=True),
            ColumnDef(key="processed", title="Processed", width=300, stretch=True),
            ColumnDef(key="diff", title="Changes", width=150),
        ]

        self._preview_table = SharedTable(
            parent,
            columns=columns,
            show_filter=True,
            show_checkboxes=False,
            show_count_filter=False,
        )
        self._preview_table.pack(fill="both", expand=True)

        # Summary bar
        self._summary_label = ttk.Label(
            parent,
            text="No preview available. Click 'Apply Rules' to see changes.",
            foreground=THEME.text_secondary,
        )
        self._summary_label.pack(anchor="w", padx=5, pady=5)

    def _add_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Add a tooltip to a widget.

        Args:
            widget: Widget to add tooltip to.
            text: Tooltip text.
        """
        # Simple tooltip implementation using bind
        def show_tooltip(event: tk.Event) -> None:
            x, y = event.x_root + 10, event.y_root + 10
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            label = ttk.Label(
                tip,
                text=text,
                background=THEME.bg_panel,
                foreground=THEME.text_primary,
                padding=(5, 3),
                wraplength=300,
            )
            label.pack()
            setattr(widget, "_tooltip", tip)

        def hide_tooltip(event: tk.Event) -> None:
            tip = getattr(widget, "_tooltip", None)
            if tip:
                tip.destroy()
                setattr(widget, "_tooltip", None)

        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)

    def _on_config_changed(self) -> None:
        """Handle configuration change from UI controls.
        
        TASK 24.3: Also saves anchor removal to manifest.
        """
        self._config["dedup_enabled"] = self._dedup_var.get() if self._dedup_var else True
        self._config["dedup_threshold"] = (
            self._dedup_threshold_var.get() if self._dedup_threshold_var else 1
        )
        # TASK 42.4: Aggressive dedup setting
        self._config["aggressive_dedup_enabled"] = (
            self._aggressive_dedup_var.get() if self._aggressive_dedup_var else False
        )
        self._config["ellipsis_enabled"] = self._ellipsis_var.get() if self._ellipsis_var else True
        self._config["symbol_conversion_enabled"] = (
            self._symbol_var.get() if self._symbol_var else True
        )
        self._config["prot_compression_enabled"] = self._prot_var.get() if self._prot_var else True
        self._config["speaker_replacement_enabled"] = (
            self._speaker_var.get() if self._speaker_var else False
        )
        self._config["code_spacing_enabled"] = (
            self._code_spacing_var.get() if self._code_spacing_var else False
        )

        # TASK 42.1: Anchor entries managed via tree, no single-field config
        # Sync is done in _sync_anchor_tree_to_manifest() on add/edit/remove

        # Mark session as dirty
        self.session.set_dirty(True)

    def _get_loaded_lines(self) -> List[str]:
        """Get lines from manifest ``orig`` fields, with GUI/session fallback.

        Returns:
            List of original lines.
        """
        # Primary: manifest orig fields
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            manifest_lines = mgr.get_lines()
            if manifest_lines:
                orig_lines = [
                    ln.get("orig", "") for ln in manifest_lines
                ]
                if any(orig_lines):
                    return orig_lines

        # Fallback: GUI input step
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 0:
                input_step = app._step_tabs[0]
                if hasattr(input_step, "get_loaded_files"):
                    loaded_files = input_step.get_loaded_files()
                    lines: list[str] = []
                    for lf in loaded_files:
                        lines.extend(lf.lines)
                    if lines:
                        return lines
        except Exception as e:
            logger.debug("Could not get loaded lines: %s", e)

        # Final fallback: legacy session step data
        input_data = self.session.get_step(0).data
        return input_data.get("all_lines", [])

    def _apply_rules(self) -> None:
        """Apply preprocessing rules to loaded lines."""
        if self._is_processing:
            return

        lines = self._get_loaded_lines()
        if not lines:
            messagebox.showwarning(
                "No Data",
                "Please load files in the Input & Extraction step first.",
            )
            return

        self._is_processing = True
        self._apply_btn.configure(state="disabled", text="Processing...")

        # Run in background thread
        thread = threading.Thread(target=self._process_lines, args=(lines,))
        thread.daemon = True
        thread.start()

    def _process_lines(self, lines: List[str]) -> None:
        """Process lines with configured rules in background.

        Uses mode_adapter.apply_preprocessing() for comprehensive processing
        via modi/ modules (TASK 16.5).  Reports progress to the UI
        progress bar.

        Args:
            lines: Lines to process.
        """
        try:
            # Show progress bar on the main thread
            self.after(0, self._show_progress)

            def _on_progress(step_name: str, fraction: float) -> None:
                self.after(
                    0,
                    lambda n=step_name, f=fraction: self._set_progress(n, f),
                )

            # TASK 16.5: Use apply_preprocessing for comprehensive processing
            # Inject character data for speaker name replacement
            if self._config.get("speaker_replacement_enabled", False):
                mgr = self.manifest_manager
                if mgr is not None and mgr.is_loaded:
                    self._config["characters"] = load_character_notes(mgr)
                else:
                    self._config["characters"] = []
            processed, stats = apply_preprocessing(
                lines, self._config, progress_cb=_on_progress,
            )

            # Build preview data using per-line tags from stats
            _on_progress("Building preview…", 0.9)
            processed_lines: List[Tuple[str, str, str, List[str]]] = []
            tags_by_line = stats.get("tags_by_line", {})

            for idx, (original, new_line) in enumerate(zip(lines, processed)):
                line_tags = tags_by_line.get(idx, [])
                display = ", ".join(
                    TAG_DISPLAY_NAMES.get(t, t) for t in line_tags
                ) if line_tags else ""
                processed_lines.append((original, new_line, display, line_tags))

            self._preview_lines = processed_lines
            self._last_stats = stats  # Preserve dedup maps for step data

            # Hide progress and update UI on main thread
            self.after(0, self._hide_progress)
            self.after(0, self._update_preview)

        except Exception as e:
            logger.exception("Error processing lines: %s", e)
            err_msg = str(e)
            self.after(0, self._hide_progress)
            self.after(0, lambda: messagebox.showerror("Error", f"Processing failed: {err_msg}"))
        finally:
            self._is_processing = False
            self.after(0, lambda: self._apply_btn.configure(state="normal", text="▶ Apply Rules"))

    def _show_progress(self) -> None:
        """Show the progress bar."""
        self._progress_bar["value"] = 0
        self._progress_label.configure(text="Starting…")
        self._progress_frame.grid()

    def _hide_progress(self) -> None:
        """Hide the progress bar."""
        self._progress_frame.grid_remove()

    def _set_progress(self, step_name: str, fraction: float) -> None:
        """Update the progress bar value and label.

        Args:
            step_name: Current processing step name.
            fraction: Progress fraction between 0.0 and 1.0.
        """
        self._progress_bar["value"] = int(fraction * 100)
        self._progress_label.configure(text=step_name)

    def _apply_ellipsis(self, line: str) -> str:
        """Apply ellipsis compression to a line.

        Uses modi/standard_mode.py via mode_adapter for consistent behavior.

        Args:
            line: Line to process.

        Returns:
            Processed line.
        """
        # TASK 16.5: Use mode_adapter instead of hardcoded implementation
        result, _ = apply_ellipsis_compression(line)
        return result

    def _apply_symbol_conversion(self, line: str) -> str:
        """Apply symbol conversion (JP to EN).

        Uses modi/standard_mode.py via mode_adapter for consistent behavior.

        Args:
            line: Line to process.

        Returns:
            Processed line with converted symbols.
        """
        # TASK 16.5: Use mode_adapter instead of hardcoded implementation
        src_lang = self._config.get("symbol_src_lang", "ja")
        tgt_lang = self._config.get("symbol_tgt_lang", "en")
        result, _ = apply_symbol_conversion(line, src_lang, tgt_lang)
        return result

    def _update_preview(self) -> None:
        """Update the preview table with processed lines.

        Filters entirely by reading the per-line tags list (read-only).
        """
        rows = []
        changed_count = 0
        active_filter = "All"
        if hasattr(self, "_preview_filter_var"):
            active_filter = self._preview_filter_var.get() or "All"

        # Resolve which tag name the active filter maps to (if any).
        required_tag = FILTER_TAG_MAP.get(active_filter, "")

        for idx, entry in enumerate(self._preview_lines):
            # Support both 4-tuple (with tags) and legacy 3-tuple format
            if len(entry) == 4:
                original, processed, changes, line_tags = entry
            else:
                original, processed, changes = entry[:3]
                line_tags: List[str] = []

            has_changes = bool(line_tags) or bool(changes)
            if has_changes:
                changed_count += 1

            # Apply filter
            if active_filter == "Changed" and not has_changes:
                continue
            if active_filter == "Unchanged" and has_changes:
                continue
            if required_tag and required_tag not in line_tags:
                continue

            rows.append(
                TableRow(
                    id=idx,
                    values={
                        "line_num": str(idx + 1),
                        "original": original[:100] + "..." if len(original) > 100 else original,
                        "processed": (
                            processed[:100] + "..." if len(processed) > 100 else processed
                        ),
                        "diff": changes,
                    },
                )
            )

        self._preview_table.set_data(rows)

        # Update filter count
        if hasattr(self, "_filter_count_label") and active_filter != "All":
            self._filter_count_label.configure(
                text=f"({len(rows)} of {len(self._preview_lines)} lines)",
            )
        elif hasattr(self, "_filter_count_label"):
            self._filter_count_label.configure(text="")

        # Update summary
        total = len(self._preview_lines)
        self._summary_label.configure(
            text=f"Processed {total} lines. {changed_count} lines changed."
        )

        # Store in step data
        self._update_step_data()

    def _update_step_data(self) -> None:
        """Update step data with current configuration and results.

        Persists preprocessed text to manifest lines[].prepro via
        set_line_field so that downstream steps and session restore
        can read the preprocessed text directly from the manifest.

        Skips writing prepro when it equals orig (unchanged lines)
        since the PIPELINE_FIELDS resolution chain already falls back
        to orig.  Also writes a comma-separated ``tags`` field per line.

        Deduplication maps (dedup_map, aggr_dedup_map, aggr_numbers)
        are stored in step data so postprocessing can restore duplicates.

        Preserves existing step data keys (e.g. dedup maps from a
        previous preprocessing run) when they are not regenerated
        during the current visit.
        """
        # Start from existing step data to preserve keys not regenerated
        data = self.get_step_data()
        data["config"] = dict(self._config)
        data["processed_count"] = len(self._preview_lines)
        data["changed_count"] = sum(
            1 for entry in self._preview_lines
            if (entry[3] if len(entry) == 4 else entry[2])
        )

        # Persist dedup mappings for postprocessing restoration
        last_stats = getattr(self, "_last_stats", {})
        dedup_map = last_stats.get("dedup_map", {})
        aggr_dedup_map = last_stats.get("aggr_dedup_map", {})
        aggr_numbers = last_stats.get("aggr_numbers", {})

        if dedup_map:
            # Serialize with string keys for JSON compatibility
            data["dedup_map"] = {str(k): v for k, v in dedup_map.items()}
        if aggr_dedup_map:
            data["aggr_dedup_map"] = {
                str(k): v for k, v in aggr_dedup_map.items()
            }
        if aggr_numbers:
            data["aggr_numbers"] = {
                str(k): v for k, v in aggr_numbers.items()
            }

        # Persist protect code captured values for postprocessing restoration
        prot_captured = last_stats.get("protect_code_captured", {})
        if prot_captured:
            data["protect_code_captured"] = {
                str(k): v for k, v in prot_captured.items()
            }

        # Persist custom placeholder captured values
        ph_captured = last_stats.get("placeholder_captured", {})
        if ph_captured:
            data["placeholder_captured"] = {
                str(k): v for k, v in ph_captured.items()
            }

        # Persist token-aware placeholder records for batch restoration
        ph_records = last_stats.get("placeholder_records", {})
        if ph_records:
            data["placeholder_records"] = {
                str(k): v for k, v in ph_records.items()
            }

        # Persist ellipsis counts for decompression
        ell_counts = last_stats.get("ellipsis_counts", {})
        if ell_counts:
            data["ellipsis_counts"] = {
                str(k): v for k, v in ell_counts.items()
            }

        # Persist anchor captured data for restoration
        anchor_captured = last_stats.get("anchor_captured", {})
        if anchor_captured:
            data["anchor_captured"] = {
                str(k): v for k, v in anchor_captured.items()
            }

        self.set_step_data(data)

        # Persist each preprocessed line to the manifest
        mgr = self.manifest_manager
        if mgr is not None:
            lines = mgr.get_lines()
            idx_map: Dict[int, Dict[str, Any]] = {
                ln.get("idx"): ln for ln in lines if ln.get("idx") is not None
            }
            dirty = False
            for idx, entry in enumerate(self._preview_lines):
                if len(entry) == 4:
                    _orig, processed, _changes, line_tags = entry
                else:
                    _orig, processed, _changes = entry[:3]
                    line_tags = []

                manifest_line = idx_map.get(idx)
                if manifest_line is None:
                    continue

                orig = manifest_line.get("orig", "")

                tags_str = ",".join(line_tags)
                old_tags = manifest_line.get("tags", "")
                if tags_str != old_tags:
                    if tags_str:
                        manifest_line["tags"] = tags_str
                    elif "tags" in manifest_line:
                        del manifest_line["tags"]
                    dirty = True

                if processed == orig:
                    if "prepro" in manifest_line:
                        del manifest_line["prepro"]
                        dirty = True
                else:
                    if manifest_line.get("prepro") != processed:
                        manifest_line["prepro"] = processed
                        dirty = True

            if dirty:
                mgr._mark_dirty()

    def _reset_rules(self) -> None:
        """Reset rules to defaults."""
        self._config = dict(DEFAULT_PREPROCESS_CONFIG)
        self._update_ui_from_config()
        # TASK 42.2/42.3: Clear placeholder and protect trees
        if hasattr(self, "_placeholder_tree"):
            self._placeholder_tree.delete(*self._placeholder_tree.get_children())
        if hasattr(self, "_protect_tree"):
            self._protect_tree.delete(*self._protect_tree.get_children())
        # TASK 42.1: Clear anchoring tree
        if hasattr(self, "_anchor_tree"):
            self._anchor_tree.delete(*self._anchor_tree.get_children())
        self.session.set_dirty(True)

    def _update_ui_from_config(self) -> None:
        """Update UI controls from config."""
        if self._dedup_var:
            self._dedup_var.set(self._config.get("dedup_enabled", True))
        if self._dedup_threshold_var:
            self._dedup_threshold_var.set(self._config.get("dedup_threshold", 1))
        # TASK 42.4
        if self._aggressive_dedup_var:
            self._aggressive_dedup_var.set(
                self._config.get("aggressive_dedup_enabled", False),
            )
        if self._ellipsis_var:
            self._ellipsis_var.set(self._config.get("ellipsis_enabled", True))
        if self._symbol_var:
            self._symbol_var.set(self._config.get("symbol_conversion_enabled", True))
        if self._prot_var:
            self._prot_var.set(self._config.get("prot_compression_enabled", True))
        if self._speaker_var:
            self._speaker_var.set(self._config.get("speaker_replacement_enabled", False))
        if self._code_spacing_var:
            self._code_spacing_var.set(self._config.get("code_spacing_enabled", False))

        # TASK 42.1: Anchor entries loaded via _refresh_anchor_entries()

    def _auto_suggest(self) -> None:
        """Auto-suggest rules based on loaded content and analysis results.
        
        Analyzes the loaded lines and analysis results to suggest appropriate
        preprocessing rules. Offers to apply suggestions automatically.
        """
        # Get analysis results and loaded lines
        analysis_data = self.session.get_step(1).data
        lines = self._get_loaded_lines()

        if not lines:
            messagebox.showinfo(
                "Auto-Suggest",
                "No files loaded. Please load files first.",
            )
            return

        suggestions = []
        auto_apply = {}

        # Analyze content for ellipsis patterns
        ellipsis_count = 0
        for line in lines:
            if "……" in line or "..." in line or "…" in line:
                ellipsis_count += 1

        if ellipsis_count > len(lines) * 0.05:  # More than 5% of lines have ellipsis
            suggestions.append(f"• Ellipsis Compression ({ellipsis_count} lines with ellipsis)")
            auto_apply["ellipsis_enabled"] = True

        # Analyze for Japanese characters
        jp_char_count = 0
        for line in lines:
            for ch in line:
                if "\u3040" <= ch <= "\u309f" or "\u30a0" <= ch <= "\u30ff":  # Hiragana/Katakana
                    jp_char_count += 1
                    break

        if jp_char_count > len(lines) * 0.1:  # More than 10% have Japanese
            suggestions.append(f"• Symbol Conversion ({jp_char_count} lines with Japanese)")
            auto_apply["symbol_conversion_enabled"] = True

        # Check for code patterns from analysis
        code_patterns = analysis_data.get("analysis_results", {}).get("code_patterns", {})
        if code_patterns:
            pattern_count = len(code_patterns)
            suggestions.append(f"• Protect Code ({pattern_count} code patterns detected)")
            # Auto-add common patterns to protect list
            protect_patterns = []
            for pattern_type, patterns in code_patterns.items():
                if pattern_type in ("html_tags", "xml_tags"):
                    protect_patterns.append(r"<[^>]+>")
                elif pattern_type in ("variables", "placeholders"):
                    protect_patterns.append(r"\{[^}]+\}")
                    protect_patterns.append(r"\[[^\]]+\]")
            auto_apply["protect_code_patterns"] = list(set(protect_patterns))

        # Check for duplicates from analysis
        duplicate_count = analysis_data.get("analysis_results", {}).get("duplicate_count", 0)
        if duplicate_count > 0:
            suggestions.append(f"• Deduplication ({duplicate_count} duplicate lines)")
            auto_apply["dedup_enabled"] = True

        # Check for common placeholder-worthy patterns in content
        placeholder_patterns = []
        for line in lines[:500]:  # Sample first 500 lines
            # Check for name-like patterns
            if re.search(r"\[\[.+?\]\]", line):
                placeholder_patterns.append(r"\[\[.+?\]\]")
            if re.search(r"{{.+?}}", line):
                placeholder_patterns.append(r"{{.+?}}")

        if placeholder_patterns:
            unique_patterns = list(set(placeholder_patterns))[:5]  # Limit to 5
            suggestions.append(f"• Custom Placeholders ({len(unique_patterns)} patterns found)")
            auto_apply["placeholder_suggestions"] = unique_patterns

        if not suggestions:
            messagebox.showinfo(
                "Auto-Suggest",
                "No specific suggestions based on current content.\n\n"
                "Try running Analysis first for more detailed detection.",
            )
            return

        # Build suggestion message
        msg = "Suggested preprocessing rules:\n\n" + "\n".join(suggestions)
        msg += "\n\nApply these suggestions?"

        if messagebox.askyesno("Auto-Suggest", msg):
            # Apply suggestions
            applied = []
            
            if auto_apply.get("ellipsis_enabled"):
                self._config["ellipsis_enabled"] = True
                self._ellipsis_var.set(True)
                applied.append("Ellipsis Compression")

            if auto_apply.get("symbol_conversion_enabled"):
                self._config["symbol_conversion_enabled"] = True
                self._symbol_var.set(True)
                applied.append("Symbol Conversion")

            if auto_apply.get("dedup_enabled"):
                self._config["dedup_enabled"] = True
                self._dedup_var.set(True)
                applied.append("Deduplication")

            # Add protect patterns
            new_patterns = auto_apply.get("protect_code_patterns", [])
            existing_patterns = set(self._config.get("protect_code_patterns", []))
            for p in new_patterns:
                if p not in existing_patterns:
                    self._config["protect_code_patterns"].append(p)
                    self._protect_tree.insert(
                        "", "end",
                        values=(p, "Yes", ""),
                    )
                    applied.append(f"Protect: {p}")

            # Add placeholder suggestions
            placeholder_suggestions = auto_apply.get("placeholder_suggestions", [])
            for p in placeholder_suggestions:
                # Don't auto-add, just show info
                pass

            self.session.set_dirty(True)
            messagebox.showinfo(
                "Applied",
                f"Applied {len(applied)} suggestion(s):\n• " + "\n• ".join(applied[:10]),
            )

    def _add_placeholder_rule(self) -> None:
        """Add a new custom placeholder rule.
        
        TASK 42.2: Now uses Treeview with RegEx toggle.
        """
        dialog = _RuleDialog(
            self, "Add Placeholder Rule",
            ["Pattern:", "Token:"],
            regex_default=False,
            show_regex=True,
        )
        if dialog.result:
            pattern = dialog.result[0]
            token = dialog.result[1] or "__CUST__"
            is_regex = dialog.regex_result
            if pattern:
                self._placeholder_tree.insert(
                    "", tk.END,
                    values=(pattern, token, "✓" if is_regex else "✗"),
                )
                self._config["placeholder_rules"].append({
                    "pattern": pattern, "token": token, "is_regex": is_regex,
                })
                self._save_custom_placeholders_to_manifest()
                self.session.set_dirty(True)

    def _remove_placeholder_rule(self) -> None:
        """Remove selected placeholder rule.
        
        TASK 42.2: Now uses Treeview.
        """
        sel = self._placeholder_tree.selection()
        if sel:
            # Find index of selected item
            children = self._placeholder_tree.get_children()
            idx = list(children).index(sel[0])
            self._placeholder_tree.delete(sel[0])
            if idx < len(self._config["placeholder_rules"]):
                del self._config["placeholder_rules"][idx]
            self._save_custom_placeholders_to_manifest()
            self.session.set_dirty(True)

    def _edit_placeholder_rule(self) -> None:
        """Edit selected placeholder rule.
        
        TASK 42.2: Now uses Treeview with RegEx.
        """
        sel = self._placeholder_tree.selection()
        if not sel:
            return

        children = self._placeholder_tree.get_children()
        idx = list(children).index(sel[0])
        if idx >= len(self._config["placeholder_rules"]):
            return

        rule = self._config["placeholder_rules"][idx]
        dialog = _RuleDialog(
            self,
            "Edit Placeholder Rule",
            ["Pattern:", "Token:"],
            [rule.get("pattern", ""), rule.get("token", "")],
            regex_default=rule.get("is_regex", False),
            show_regex=True,
        )
        if dialog.result:
            pattern = dialog.result[0]
            token = dialog.result[1] or "__CUST__"
            is_regex = dialog.regex_result
            if pattern:
                self._placeholder_tree.item(
                    sel[0], values=(pattern, token, "✓" if is_regex else "✗"),
                )
                self._config["placeholder_rules"][idx] = {
                    "pattern": pattern, "token": token, "is_regex": is_regex,
                }
                self._save_custom_placeholders_to_manifest()
                self.session.set_dirty(True)

    def _add_protect_pattern(self) -> None:
        """Add a new protect code pattern.
        
        TASK 42.3: Now uses Treeview with RegEx (default enabled).
        """
        dialog = _RuleDialog(
            self, "Add Protect Pattern",
            ["Pattern:", "Description:"],
            regex_default=True,
            show_regex=True,
        )
        if dialog.result:
            pattern = dialog.result[0]
            description = dialog.result[1] if len(dialog.result) > 1 else ""
            is_regex = dialog.regex_result
            if pattern:
                self._protect_tree.insert(
                    "", tk.END,
                    values=(pattern, "✓" if is_regex else "✗", description),
                )
                self._config["protect_code_patterns"].append({
                    "pattern": pattern, "is_regex": is_regex,
                    "description": description,
                })
                self._save_protect_patterns_to_manifest()
                self.session.set_dirty(True)

    def _remove_protect_pattern(self) -> None:
        """Remove selected protect pattern.
        
        TASK 42.3: Now uses Treeview.
        """
        sel = self._protect_tree.selection()
        if sel:
            children = self._protect_tree.get_children()
            idx = list(children).index(sel[0])
            self._protect_tree.delete(sel[0])
            if idx < len(self._config["protect_code_patterns"]):
                del self._config["protect_code_patterns"][idx]
            self._save_protect_patterns_to_manifest()
            self.session.set_dirty(True)

    def _edit_protect_pattern(self) -> None:
        """Edit selected protect pattern.
        
        TASK 42.3: Now uses Treeview with RegEx.
        """
        sel = self._protect_tree.selection()
        if not sel:
            return

        children = self._protect_tree.get_children()
        idx = list(children).index(sel[0])
        if idx >= len(self._config["protect_code_patterns"]):
            return

        entry = self._config["protect_code_patterns"][idx]
        # Handle both old (plain string) and new (dict) formats
        if isinstance(entry, str):
            pattern, is_regex, description = entry, True, ""
        else:
            pattern = entry.get("pattern", "")
            is_regex = entry.get("is_regex", True)
            description = entry.get("description", "")

        dialog = _RuleDialog(
            self, "Edit Protect Pattern",
            ["Pattern:", "Description:"],
            [pattern, description],
            regex_default=is_regex,
            show_regex=True,
        )
        if dialog.result:
            new_pattern = dialog.result[0]
            new_desc = dialog.result[1] if len(dialog.result) > 1 else ""
            new_regex = dialog.regex_result
            if new_pattern:
                self._protect_tree.item(
                    sel[0],
                    values=(new_pattern, "✓" if new_regex else "✗", new_desc),
                )
                self._config["protect_code_patterns"][idx] = {
                    "pattern": new_pattern, "is_regex": new_regex,
                    "description": new_desc,
                }
                self._save_protect_patterns_to_manifest()
                self.session.set_dirty(True)

    def _show_common_patterns(self) -> None:
        """Show common protect code patterns.

        Uses patterns from mode_adapter (consistent with modi/protect_code.py).
        """
        # TASK 16.5: Use get_common_patterns from mode_adapter
        common = get_common_patterns()

        msg = "Common Protect Code Patterns:\n\n"
        for item in common:
            pattern = item.get("pattern", "")
            desc = item.get("description", "")
            msg += f"• {pattern}\n  ({desc})\n\n"

        messagebox.showinfo("Common Patterns", msg)

    def on_new_project(self) -> None:
        """Reset cached state for a fresh project."""
        super().on_new_project()
        self._preview_lines.clear()
        self._is_processing = False
        self._manifest_bindings.clear()
        logger.debug("Preprocessing step reset for new project")

    def on_enter(self) -> None:
        """Called when entering this step.
        
        TASK 18.4: Ensures Input step files are restored before accessing them.
        TASK 24.1: Loads manifest bindings for standard rules.
        TASK 24.2: Loads protect code patterns from manifest.
        """
        # Ensure Input step has restored its files from session
        self._ensure_input_files_restored()
        
        # TASK 24.1: Load from manifest bindings
        self._load_from_manifest_bindings()
        
        # Sync code pattern actions to preprocessing sections
        if self.manifest_manager:
            from CherryAI.functions.manifest_fields import (
                sync_code_pattern_actions,
            )
            sync_code_pattern_actions(self.manifest_manager)
        
        # TASK 24.2: Load protect patterns from manifest
        self._load_protect_patterns_from_manifest()
        
        # TASK 24.3: Load custom placeholders and anchor removal from manifest
        self._load_custom_placeholders_from_manifest()
        self._load_anchor_removal_from_manifest()
        
        # Reload config from step data if available
        step_data = self.get_step_data()
        if step_data.get("config"):
            self._config = step_data["config"]
            self._update_ui_from_config()

            # Restore placeholder rules (TASK 42.2: Treeview)
            if hasattr(self, "_placeholder_tree"):
                self._placeholder_tree.delete(
                    *self._placeholder_tree.get_children(),
                )
                for rule in self._config.get("placeholder_rules", []):
                    pattern = rule.get("pattern", "")
                    token = rule.get("token", "__CUST__")
                    is_regex = "Yes" if rule.get("is_regex", False) else "No"
                    self._placeholder_tree.insert(
                        "", "end", values=(pattern, token, is_regex),
                    )

            # Restore protect patterns (TASK 42.3: Treeview)
            if hasattr(self, "_protect_tree"):
                self._protect_tree.delete(
                    *self._protect_tree.get_children(),
                )
                for entry in self._config.get("protect_code_patterns", []):
                    if isinstance(entry, dict):
                        pat = entry.get("pattern", "")
                        is_re = "Yes" if entry.get("is_regex", True) else "No"
                        desc = entry.get("description", "")
                    else:
                        pat = str(entry)
                        is_re = "Yes"
                        desc = ""
                    self._protect_tree.insert(
                        "", "end", values=(pat, is_re, desc),
                    )

        # Restore preview from manifest orig/prepro if available
        if not self._preview_lines:
            self._load_preview_from_manifest()

    def _load_preview_from_manifest(self) -> None:
        """Populate the preview table from manifest ``orig``/``prepro``/``tags`` fields.

        Called during ``on_enter`` so that returning to the tab shows
        existing preprocessing results without re-running Apply Rules.
        Tags are read directly for efficient filtering.
        """
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        manifest_lines = mgr.get_lines()
        if not manifest_lines:
            return

        preview: list[tuple[str, str, str, list[str]]] = []
        for ln in manifest_lines:
            orig = ln.get("orig", "")
            prepro = ln.get("prepro", "")
            tags_str = ln.get("tags", "")
            line_tags = [t for t in tags_str.split(",") if t] if tags_str else []
            if prepro and prepro != orig:
                display = ", ".join(
                    TAG_DISPLAY_NAMES.get(t, t) for t in line_tags
                ) if line_tags else "preprocessed"
            else:
                prepro = orig
                display = ""
            preview.append((orig, prepro, display, line_tags))

        if preview:
            self._preview_lines = preview
            self._update_preview()

    def _load_from_manifest_bindings(self) -> None:
        """Load values from manifest into bound widgets.
        
        TASK 24.1: Loads standard rule toggles from manifest.
        """
        if not self.manifest_manager:
            return
        
        if not self.manifest_manager.is_loaded:
            return
        
        for binding in self._manifest_bindings:
            if hasattr(binding, "load_from_manifest"):
                binding.load_from_manifest()

    def _save_protect_patterns_to_manifest(self) -> None:
        """Save protect code patterns to manifest.
        
        TASK 24.2: Converts the simple string list to manifest format.
        """
        if not self.manifest_manager:
            return
        
        # TASK 42.3: Convert config entries (dict or string) to manifest format
        patterns = self._config.get("protect_code_patterns", [])
        manifest_patterns = []
        for entry in patterns:
            if isinstance(entry, dict):
                manifest_patterns.append({
                    "pattern": entry.get("pattern", ""),
                    "replacement": "__PROTECTED__",
                    "is_regex": entry.get("is_regex", True),
                    "description": entry.get("description", ""),
                })
            else:
                manifest_patterns.append({
                    "pattern": str(entry),
                    "replacement": "__PROTECTED__",
                    "is_regex": True,
                    "description": "",
                })
        
        save_protect_code_patterns(self.manifest_manager, manifest_patterns)

    def _load_protect_patterns_from_manifest(self) -> None:
        """Load protect code patterns from manifest.
        
        TASK 24.2: Loads patterns from manifest format to config list.
        """
        if not self.manifest_manager:
            return
        
        if not self.manifest_manager.is_loaded:
            return
        
        # Load from manifest
        manifest_patterns = load_protect_code_patterns(self.manifest_manager)
        
        # TASK 42.3: Convert to dict entries preserving is_regex/description
        entries = [
            {
                "pattern": p.get("pattern", ""),
                "is_regex": p.get("is_regex", True),
                "description": p.get("description", ""),
            }
            for p in manifest_patterns
            if p.get("pattern")
        ]
        
        # Update config
        self._config["protect_code_patterns"] = entries
        
        # Update tree (TASK 42.3)
        if hasattr(self, "_protect_tree"):
            self._protect_tree.delete(*self._protect_tree.get_children())
            for entry in entries:
                is_re = "Yes" if entry.get("is_regex", True) else "No"
                self._protect_tree.insert(
                    "", "end",
                    values=(entry["pattern"], is_re, entry.get("description", "")),
                )

    def _save_custom_placeholders_to_manifest(self) -> None:
        """Save custom placeholder rules to manifest.
        
        TASK 24.3: Converts config format to manifest format.
        """
        if not self.manifest_manager:
            return
        
        # Convert from config format {pattern, token} to manifest format
        rules = self._config.get("placeholder_rules", [])
        manifest_placeholders = [
            {
                "pattern": r.get("pattern", ""),
                "placeholder": r.get("token", "__CUST__"),
                "is_regex": r.get("is_regex", False),  # TASK 42.2: From config
                "restore_after": True,
            }
            for r in rules
        ]
        
        save_custom_placeholders(self.manifest_manager, manifest_placeholders)

    def _load_custom_placeholders_from_manifest(self) -> None:
        """Load custom placeholder rules from manifest.
        
        TASK 24.3: Loads placeholders from manifest format to config list.
        """
        if not self.manifest_manager:
            return
        
        if not self.manifest_manager.is_loaded:
            return
        
        # Load from manifest
        manifest_placeholders = load_custom_placeholders(self.manifest_manager)
        
        # TASK 42.2: Convert to config format with is_regex
        rules = [
            {
                "pattern": p.get("pattern", ""),
                "token": p.get("placeholder", "__CUST__"),
                "is_regex": p.get("is_regex", False),
            }
            for p in manifest_placeholders
            if p.get("pattern")
        ]
        
        # Update config
        self._config["placeholder_rules"] = rules
        
        # Update tree (TASK 42.2)
        if hasattr(self, "_placeholder_tree"):
            self._placeholder_tree.delete(
                *self._placeholder_tree.get_children(),
            )
            for rule in rules:
                pattern = rule.get("pattern", "")
                token = rule.get("token", "__CUST__")
                is_regex = "Yes" if rule.get("is_regex", False) else "No"
                self._placeholder_tree.insert(
                    "", "end", values=(pattern, token, is_regex),
                )

    def _save_anchor_removal_to_manifest(self) -> None:
        """Save anchoring entries to manifest.
        
        TASK 42.1: Delegates to _sync_anchor_tree_to_manifest.
        Kept for backward compatibility with callers.
        """
        if hasattr(self, "_anchor_tree"):
            self._sync_anchor_tree_to_manifest()

    def _load_anchor_removal_from_manifest(self) -> None:
        """Load anchoring entries from manifest into tree.
        
        TASK 42.1: Delegates to _refresh_anchor_entries.
        """
        self._refresh_anchor_entries()

    def _ensure_input_files_restored(self) -> None:
        """Ensure Input step has its files restored from session.
        
        TASK 18.4/18.8: When navigating directly to Preprocessing after session restore,
        the Input step may not have called on_enter() yet. This ensures files
        are available for preprocessing.
        """
        try:
            # Check if manifest has lines
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                manifest_lines = mgr.get_lines()
                if manifest_lines:
                    logger.debug("Manifest has %d lines available for Preprocessing", len(manifest_lines))
                    return  # Lines available in manifest
            
            # Try to trigger Input step restore
            app = self.winfo_toplevel()
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 0:
                input_step = app._step_tabs[0]
                if hasattr(input_step, "get_loaded_files"):
                    loaded_files = input_step.get_loaded_files()
                    if not loaded_files:
                        # Files not loaded in Input step, trigger restore
                        if hasattr(input_step, "on_enter"):
                            input_step.on_enter()
                            logger.debug("Triggered Input step file restore for Preprocessing")
                            # Re-check after restore
                            loaded_files = input_step.get_loaded_files()
                            if loaded_files:
                                logger.debug("Input step restored %d files", len(loaded_files))
                            else:
                                logger.debug("Input step restore did not load files (no files in project yet)")
        except Exception as e:
            logger.debug("Could not ensure input files: %s", e)

    def on_leave(self) -> None:
        """Called when leaving this step."""
        self._update_step_data()


class _RuleDialog(tk.Toplevel):
    """Simple dialog for adding/editing rules."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        labels: List[str],
        defaults: Optional[List[str]] = None,
        regex_default: bool = False,
        show_regex: bool = False,
    ) -> None:
        """Initialize rule dialog.

        Args:
            parent: Parent widget.
            title: Dialog title.
            labels: Input field labels.
            defaults: Default values for inputs.
            regex_default: Default state for RegEx checkbox (TASK 42.2).
            show_regex: Whether to show the RegEx checkbox (TASK 42.2).
        """
        super().__init__(parent)
        self.title(title)
        self.transient(parent)  # type: ignore[call-overload]
        self.grab_set()

        self.result: Optional[List[str]] = None
        self.regex_result: bool = regex_default
        self._entries: List[ttk.Entry] = []
        self._regex_var: Optional[tk.BooleanVar] = None

        defaults = defaults or [""] * len(labels)

        # Build UI
        for i, label in enumerate(labels):
            frame = ttk.Frame(self)
            frame.pack(fill="x", padx=10, pady=5)

            ttk.Label(frame, text=label, width=12).pack(side="left")
            entry = ttk.Entry(frame, width=40)
            entry.pack(side="left", fill="x", expand=True)
            entry.insert(0, defaults[i] if i < len(defaults) else "")
            self._entries.append(entry)

        # RegEx checkbox (TASK 42.2)
        if show_regex:
            regex_frame = ttk.Frame(self)
            regex_frame.pack(fill="x", padx=10, pady=5)
            ttk.Label(regex_frame, text="RegEx:", width=12).pack(side="left")
            self._regex_var = tk.BooleanVar(value=regex_default)
            ttk.Checkbutton(
                regex_frame, variable=self._regex_var, text="Enabled",
            ).pack(side="left")

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="right")

        # Focus first entry
        if self._entries:
            self._entries[0].focus_set()

        # Bind Enter key
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + 50
        y = parent.winfo_rooty() + 50
        self.geometry(f"+{x}+{y}")

        self.wait_window()

    def _on_ok(self) -> None:
        """Handle OK button."""
        self.result = [entry.get() for entry in self._entries]
        if self._regex_var is not None:
            self.regex_result = self._regex_var.get()
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = None
        self.destroy()


class _AnchorDialog(tk.Toplevel):
    """Dialog for adding/editing anchoring rules.

    TASK 42.1: Provides fields for Pattern, Action (combobox),
    Anchor Spec, RegEx (checkbox), and Description.
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize anchor dialog.

        Args:
            parent: Parent widget.
            title: Dialog title.
            defaults: Pre-populated field values.
        """
        super().__init__(parent)
        self.title(title)
        self.transient(parent)  # type: ignore[call-overload]
        self.grab_set()

        self.result: Optional[Dict[str, Any]] = None
        defaults = defaults or {}

        # Pattern
        f1 = ttk.Frame(self)
        f1.pack(fill="x", padx=10, pady=5)
        ttk.Label(f1, text="Pattern:", width=14).pack(side="left")
        self._pattern_entry = ttk.Entry(f1, width=40)
        self._pattern_entry.pack(side="left", fill="x", expand=True)
        self._pattern_entry.insert(0, defaults.get("pattern", ""))

        # Action
        f2 = ttk.Frame(self)
        f2.pack(fill="x", padx=10, pady=5)
        ttk.Label(f2, text="Action:", width=14).pack(side="left")
        self._action_var = tk.StringVar(value=defaults.get("action", "remove"))
        action_combo = ttk.Combobox(
            f2, textvariable=self._action_var, values=["remove", "preserve", "replace"],
            state="readonly", width=12,
        )
        action_combo.pack(side="left")

        # Anchor Spec
        f3 = ttk.Frame(self)
        f3.pack(fill="x", padx=10, pady=5)
        ttk.Label(f3, text="Anchor Spec:", width=14).pack(side="left")
        self._spec_entry = ttk.Entry(f3, width=40)
        self._spec_entry.pack(side="left", fill="x", expand=True)
        self._spec_entry.insert(0, defaults.get("anchor_spec", "line_start;line_end"))

        # RegEx
        f4 = ttk.Frame(self)
        f4.pack(fill="x", padx=10, pady=5)
        ttk.Label(f4, text="RegEx:", width=14).pack(side="left")
        self._regex_var = tk.BooleanVar(value=defaults.get("is_regex", True))
        ttk.Checkbutton(f4, variable=self._regex_var, text="Enabled").pack(side="left")

        # Description
        f5 = ttk.Frame(self)
        f5.pack(fill="x", padx=10, pady=5)
        ttk.Label(f5, text="Description:", width=14).pack(side="left")
        self._desc_entry = ttk.Entry(f5, width=40)
        self._desc_entry.pack(side="left", fill="x", expand=True)
        self._desc_entry.insert(0, defaults.get("description", ""))

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="right")

        self._pattern_entry.focus_set()
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        self.update_idletasks()
        x = parent.winfo_rootx() + 50
        y = parent.winfo_rooty() + 50
        self.geometry(f"+{x}+{y}")
        self.wait_window()

    def _on_ok(self) -> None:
        """Handle OK — collect all fields."""
        pattern = self._pattern_entry.get().strip()
        if not pattern:
            self.result = None
            self.destroy()
            return
        self.result = {
            "pattern": pattern,
            "action": self._action_var.get(),
            "anchor_spec": self._spec_entry.get().strip(),
            "is_regex": self._regex_var.get(),
            "description": self._desc_entry.get().strip(),
        }
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel."""
        self.result = None
        self.destroy()
