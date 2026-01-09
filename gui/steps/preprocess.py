"""CherryAI GUI v2 Preprocessing Step.

Fourth workflow tab for configuring and applying preprocessing rules.
Provides toggles for deduplication, symbol conversion, ellipsis handling,
placeholders, and speaker formatting with live preview and diff view.

Updated: TASK 16.5 - Now uses modi/ modules via mode_adapter for preprocessing.
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

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)

# TASK 16.5: Import centralized preprocessing config from store
# Use conditional import to avoid circular imports
try:
    from CherryAI.gui.state.store import DEFAULT_PREPROCESS_CONFIG
except ImportError:
    # Fallback if circular import occurs
    DEFAULT_PREPROCESS_CONFIG: Dict[str, Any] = {  # type: ignore[no-redef]
        "dedup_enabled": True,
        "dedup_threshold": 1,
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
        "Compresses adjacent __PROT__ tokens into indexed form:\n"
        "  __PROT____PROT__ → __PROT_2__\n"
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
        "Protect Code: Replace code patterns with __PROT__.\n"
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

    step_id = 4  # Moved from position 3
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
        self._preview_lines: List[Tuple[str, str, str]] = []  # (original, processed, diff)
        self._is_processing = False

        # UI variables (created in _build_ui)
        self._dedup_var: Optional[tk.BooleanVar] = None
        self._dedup_threshold_var: Optional[tk.IntVar] = None
        self._ellipsis_var: Optional[tk.BooleanVar] = None
        self._symbol_var: Optional[tk.BooleanVar] = None
        self._prot_var: Optional[tk.BooleanVar] = None
        self._speaker_var: Optional[tk.BooleanVar] = None
        self._code_spacing_var: Optional[tk.BooleanVar] = None

        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the Preprocessing UI."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header with Apply button
        self._build_header()

        # Main content: rules panel (left) + preview table (right)
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
        paned.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

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

        # Anchor Removal section
        self._build_anchor_removal_section(scrollable)

    def _build_standard_rules(self, parent: ttk.Frame) -> None:
        """Build standard preprocessing rules section.

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

        # PROT Compression
        prot_frame = ttk.Frame(section)
        prot_frame.pack(fill="x", padx=10, pady=5)

        self._prot_var = tk.BooleanVar(value=self._config["prot_compression_enabled"])
        prot_cb = ttk.Checkbutton(
            prot_frame,
            text="PROT Token Compression",
            variable=self._prot_var,
            command=self._on_config_changed,
        )
        prot_cb.pack(side="left")
        self._add_tooltip(prot_cb, RULE_TOOLTIPS["prot_compression"])

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

    def _build_placeholder_section(self, parent: ttk.Frame) -> None:
        """Build custom placeholder rules section.

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

        # Rules list
        list_frame = ttk.Frame(section)
        list_frame.pack(fill="x", padx=10, pady=5)

        self._placeholder_listbox = tk.Listbox(
            list_frame,
            height=4,
            bg=THEME.bg_input,
            fg=THEME.text_primary,
            selectbackground=THEME.bg_selected,
        )
        self._placeholder_listbox.pack(side="left", fill="x", expand=True)

        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self._placeholder_listbox.yview
        )
        scrollbar.pack(side="right", fill="y")
        self._placeholder_listbox.configure(yscrollcommand=scrollbar.set)

        # Bind double-click for editing and Delete for removal
        self._placeholder_listbox.bind("<Double-1>", lambda e: self._edit_placeholder_rule())
        self._placeholder_listbox.bind("<Delete>", lambda e: self._remove_placeholder_rule())

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

        Args:
            parent: Parent frame.
        """
        section = ttk.LabelFrame(parent, text="Protect Code Patterns")
        section.pack(fill="x", padx=5, pady=5)

        # Info label
        info_label = ttk.Label(
            section,
            text="Regex patterns to protect from translation.",
            foreground=THEME.text_secondary,
        )
        info_label.pack(anchor="w", padx=10, pady=(5, 0))

        # Patterns list
        list_frame = ttk.Frame(section)
        list_frame.pack(fill="x", padx=10, pady=5)

        self._protect_listbox = tk.Listbox(
            list_frame,
            height=4,
            bg=THEME.bg_input,
            fg=THEME.text_primary,
            selectbackground=THEME.bg_selected,
        )
        self._protect_listbox.pack(side="left", fill="x", expand=True)

        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self._protect_listbox.yview
        )
        scrollbar.pack(side="right", fill="y")
        self._protect_listbox.configure(yscrollcommand=scrollbar.set)

        # Bind double-click for editing and Delete for removal
        self._protect_listbox.bind("<Double-1>", lambda e: self._edit_protect_pattern())
        self._protect_listbox.bind("<Delete>", lambda e: self._remove_protect_pattern())

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

    def _build_anchor_removal_section(self, parent: ttk.Frame) -> None:
        """Build anchor removal section.

        Args:
            parent: Parent frame.
        """
        section = ttk.LabelFrame(parent, text="Anchor Removal")
        section.pack(fill="x", padx=5, pady=5)

        # Enable toggle
        enable_frame = ttk.Frame(section)
        enable_frame.pack(fill="x", padx=10, pady=5)

        self._anchor_enabled_var = tk.BooleanVar(
            value=self._config.get("anchor_removal_enabled", False)
        )
        anchor_cb = ttk.Checkbutton(
            enable_frame,
            text="Enable anchor-based removal",
            variable=self._anchor_enabled_var,
            command=self._on_config_changed,
        )
        anchor_cb.pack(side="left")

        # Info label
        info_label = ttk.Label(
            section,
            text="Remove content at specific anchors (restored after translation).",
            foreground=THEME.text_secondary,
        )
        info_label.pack(anchor="w", padx=10, pady=(0, 5))

        # Content pattern
        pattern_frame = ttk.Frame(section)
        pattern_frame.pack(fill="x", padx=10, pady=2)

        ttk.Label(pattern_frame, text="Content Pattern:", width=14).pack(side="left")
        self._anchor_pattern_var = tk.StringVar(
            value=self._config.get("anchor_content_pattern", "")
        )
        self._anchor_pattern_entry = ttk.Entry(
            pattern_frame,
            textvariable=self._anchor_pattern_var,
            width=30,
        )
        self._anchor_pattern_entry.pack(side="left", fill="x", expand=True)
        self._anchor_pattern_entry.bind("<KeyRelease>", lambda e: self._on_config_changed())

        # Anchor spec
        spec_frame = ttk.Frame(section)
        spec_frame.pack(fill="x", padx=10, pady=2)

        ttk.Label(spec_frame, text="Anchor Spec:", width=14).pack(side="left")
        self._anchor_spec_var = tk.StringVar(
            value=self._config.get("anchor_spec", "line_start;line_end")
        )
        self._anchor_spec_entry = ttk.Entry(
            spec_frame,
            textvariable=self._anchor_spec_var,
            width=30,
        )
        self._anchor_spec_entry.pack(side="left", fill="x", expand=True)
        self._anchor_spec_entry.bind("<KeyRelease>", lambda e: self._on_config_changed())

        # Quick presets
        preset_frame = ttk.Frame(section)
        preset_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(preset_frame, text="Presets:").pack(side="left")

        def set_anchor_preset(preset: str) -> None:
            """Set anchor spec from preset."""
            presets = {
                "Line Boundaries": "line_start;line_end",
                "After Punctuation": "after:。;after:.;after:!;after:?",
                "Before Punctuation": "before:。;before:.;before:!;before:?",
                "Around Quotes": "around:「;around:」;around:\";around:'",
            }
            self._anchor_spec_var.set(presets.get(preset, ""))
            self._on_config_changed()

        for preset in ["Line Boundaries", "After Punctuation", "Before Punctuation", "Around Quotes"]:
            ttk.Button(
                preset_frame,
                text=preset,
                command=lambda p=preset: set_anchor_preset(p),  # type: ignore
                width=len(preset) + 2,
            ).pack(side="left", padx=2)

        # Help text
        help_text = ttk.Label(
            section,
            text=(
                "Spec format: line_start; line_end; after:CHAR; before:CHAR; around:CHAR\n"
                "Separate multiple specs with semicolon (;)"
            ),
            font=("Segoe UI", 8),
            foreground="gray",
        )
        help_text.pack(anchor="w", padx=10, pady=(0, 5))

    def _build_preview_panel(self, parent: ttk.LabelFrame) -> None:
        """Build the preview table panel.

        Args:
            parent: Parent frame.
        """
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
        """Handle configuration change from UI controls."""
        self._config["dedup_enabled"] = self._dedup_var.get() if self._dedup_var else True
        self._config["dedup_threshold"] = (
            self._dedup_threshold_var.get() if self._dedup_threshold_var else 1
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

        # Anchor removal settings
        if hasattr(self, "_anchor_enabled_var"):
            self._config["anchor_removal_enabled"] = self._anchor_enabled_var.get()
        if hasattr(self, "_anchor_pattern_var"):
            self._config["anchor_content_pattern"] = self._anchor_pattern_var.get()
        if hasattr(self, "_anchor_spec_var"):
            self._config["anchor_spec"] = self._anchor_spec_var.get()

        # Mark session as dirty
        self.session.set_dirty(True)

    def _get_loaded_lines(self) -> List[str]:
        """Get lines from loaded files.

        Returns:
            List of lines from input step.
        """
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 0:
                input_step = app._step_tabs[0]
                if hasattr(input_step, "get_loaded_files"):
                    loaded_files = input_step.get_loaded_files()
                    lines = []
                    for lf in loaded_files:
                        lines.extend(lf.lines)
                    return lines
        except Exception as e:
            logger.debug("Could not get loaded lines: %s", e)

        # Fallback to step data
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
        via modi/ modules (TASK 16.5).

        Args:
            lines: Lines to process.
        """
        try:
            # TASK 16.5: Use apply_preprocessing for comprehensive processing
            processed, stats = apply_preprocessing(lines, self._config)

            # Build preview data with change tracking
            processed_lines: List[Tuple[str, str, str]] = []
            changes_by_line = stats.get("changes_by_rule", {})
            changed_indices = set(stats.get("changed_lines", []))

            for idx, (original, new_line) in enumerate(zip(lines, processed)):
                if idx in changed_indices:
                    # Determine which rules changed this line
                    changes_for_line: List[str] = []
                    # Check each rule type
                    if changes_by_line.get("symbol_conversion"):
                        old_sym, _ = apply_symbol_conversion(
                            original,
                            self._config.get("symbol_src_lang", "ja"),
                            self._config.get("symbol_tgt_lang", "en"),
                        )
                        if old_sym != original:
                            changes_for_line.append("symbols")
                    if changes_by_line.get("ellipsis"):
                        old_ell, changed = apply_ellipsis_compression(original)
                        if changed:
                            changes_for_line.append("ellipsis")
                    if changes_by_line.get("protect_code"):
                        changes_for_line.append("protect")
                    if changes_by_line.get("placeholder"):
                        changes_for_line.append("placeholder")
                    if changes_by_line.get("prot_compression"):
                        changes_for_line.append("prot_compress")

                    change_str = ", ".join(changes_for_line) if changes_for_line else "changed"
                else:
                    change_str = ""

                processed_lines.append((original, new_line, change_str))

            self._preview_lines = processed_lines

            # Update UI on main thread
            self.after(0, self._update_preview)

        except Exception as e:
            logger.exception("Error processing lines: %s", e)
            self.after(0, lambda: messagebox.showerror("Error", f"Processing failed: {e}"))
        finally:
            self._is_processing = False
            self.after(0, lambda: self._apply_btn.configure(state="normal", text="▶ Apply Rules"))

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
        """Update the preview table with processed lines."""
        rows = []
        changed_count = 0

        for idx, (original, processed, changes) in enumerate(self._preview_lines):
            if changes:
                changed_count += 1

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

        # Update summary
        total = len(self._preview_lines)
        self._summary_label.configure(
            text=f"Processed {total} lines. {changed_count} lines changed."
        )

        # Store in step data
        self._update_step_data()

    def _update_step_data(self) -> None:
        """Update step data with current configuration and results."""
        data = {
            "config": dict(self._config),
            "processed_count": len(self._preview_lines),
            "changed_count": sum(1 for _, _, c in self._preview_lines if c),
            "processed_lines": [p for _, p, _ in self._preview_lines],
        }
        self.set_step_data(data)

    def _reset_rules(self) -> None:
        """Reset rules to defaults."""
        self._config = dict(DEFAULT_PREPROCESS_CONFIG)
        self._update_ui_from_config()
        self._placeholder_listbox.delete(0, tk.END)
        self._protect_listbox.delete(0, tk.END)
        self.session.set_dirty(True)

    def _update_ui_from_config(self) -> None:
        """Update UI controls from config."""
        if self._dedup_var:
            self._dedup_var.set(self._config.get("dedup_enabled", True))
        if self._dedup_threshold_var:
            self._dedup_threshold_var.set(self._config.get("dedup_threshold", 1))
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

        # Anchor removal settings
        if hasattr(self, "_anchor_enabled_var"):
            self._anchor_enabled_var.set(self._config.get("anchor_removal_enabled", False))
        if hasattr(self, "_anchor_pattern_var"):
            self._anchor_pattern_var.set(self._config.get("anchor_content_pattern", ""))
        if hasattr(self, "_anchor_spec_var"):
            self._anchor_spec_var.set(self._config.get("anchor_spec", "line_start;line_end"))

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
                    self._protect_listbox.insert(tk.END, p)
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
        """Add a new custom placeholder rule."""
        dialog = _RuleDialog(self, "Add Placeholder Rule", ["Pattern:", "Token:"])
        if dialog.result:
            pattern, token = dialog.result
            if pattern:
                rule_str = f"{pattern} → {token or '__CUST__'}"
                self._placeholder_listbox.insert(tk.END, rule_str)
                self._config["placeholder_rules"].append({"pattern": pattern, "token": token})
                self.session.set_dirty(True)

    def _remove_placeholder_rule(self) -> None:
        """Remove selected placeholder rule."""
        selection = self._placeholder_listbox.curselection()
        if selection:
            idx = selection[0]
            self._placeholder_listbox.delete(idx)
            if idx < len(self._config["placeholder_rules"]):
                del self._config["placeholder_rules"][idx]
            self.session.set_dirty(True)

    def _edit_placeholder_rule(self) -> None:
        """Edit selected placeholder rule."""
        selection = self._placeholder_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self._config["placeholder_rules"]):
            return

        rule = self._config["placeholder_rules"][idx]
        dialog = _RuleDialog(
            self,
            "Edit Placeholder Rule",
            ["Pattern:", "Token:"],
            [rule.get("pattern", ""), rule.get("token", "")],
        )
        if dialog.result:
            pattern, token = dialog.result
            if pattern:
                rule_str = f"{pattern} → {token or '__CUST__'}"
                self._placeholder_listbox.delete(idx)
                self._placeholder_listbox.insert(idx, rule_str)
                self._config["placeholder_rules"][idx] = {"pattern": pattern, "token": token}
                self.session.set_dirty(True)

    def _add_protect_pattern(self) -> None:
        """Add a new protect code pattern."""
        dialog = _RuleDialog(self, "Add Protect Pattern", ["Regex Pattern:"])
        if dialog.result:
            pattern = dialog.result[0]
            if pattern:
                self._protect_listbox.insert(tk.END, pattern)
                self._config["protect_code_patterns"].append(pattern)
                self.session.set_dirty(True)

    def _remove_protect_pattern(self) -> None:
        """Remove selected protect pattern."""
        selection = self._protect_listbox.curselection()
        if selection:
            idx = selection[0]
            self._protect_listbox.delete(idx)
            if idx < len(self._config["protect_code_patterns"]):
                del self._config["protect_code_patterns"][idx]
            self.session.set_dirty(True)

    def _edit_protect_pattern(self) -> None:
        """Edit selected protect pattern."""
        selection = self._protect_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self._config["protect_code_patterns"]):
            return

        pattern = self._config["protect_code_patterns"][idx]
        dialog = _RuleDialog(self, "Edit Protect Pattern", ["Regex Pattern:"], [pattern])
        if dialog.result:
            new_pattern = dialog.result[0]
            if new_pattern:
                self._protect_listbox.delete(idx)
                self._protect_listbox.insert(idx, new_pattern)
                self._config["protect_code_patterns"][idx] = new_pattern
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

    def on_enter(self) -> None:
        """Called when entering this step.
        
        TASK 18.4: Ensures Input step files are restored before accessing them.
        """
        # Ensure Input step has restored its files from session
        self._ensure_input_files_restored()
        
        # Reload config from step data if available
        step_data = self.get_step_data()
        if step_data.get("config"):
            self._config = step_data["config"]
            self._update_ui_from_config()

            # Restore placeholder rules
            self._placeholder_listbox.delete(0, tk.END)
            for rule in self._config.get("placeholder_rules", []):
                pattern = rule.get("pattern", "")
                token = rule.get("token", "__CUST__")
                self._placeholder_listbox.insert(tk.END, f"{pattern} → {token}")

            # Restore protect patterns
            self._protect_listbox.delete(0, tk.END)
            for pattern in self._config.get("protect_code_patterns", []):
                self._protect_listbox.insert(tk.END, pattern)

    def _ensure_input_files_restored(self) -> None:
        """Ensure Input step has its files restored from session.
        
        TASK 18.4/18.8: When navigating directly to Preprocessing after session restore,
        the Input step may not have called on_enter() yet. This ensures files
        are available for preprocessing.
        """
        try:
            # First check if we can get lines from session directly
            input_data = self.session.get_step(0).data
            session_lines = input_data.get("all_lines", [])
            
            if session_lines:
                logger.debug("Session has %d lines available for Preprocessing", len(session_lines))
                return  # Lines available in session, we can use fallback
            
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
                                logger.warning("Input step restore did not load files")
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
    ) -> None:
        """Initialize rule dialog.

        Args:
            parent: Parent widget.
            title: Dialog title.
            labels: Input field labels.
            defaults: Default values for inputs.
        """
        super().__init__(parent)
        self.title(title)
        self.transient(parent)  # type: ignore[call-overload]
        self.grab_set()

        self.result: Optional[List[str]] = None
        self._entries: List[ttk.Entry] = []

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
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = None
        self.destroy()
