"""CherryAI GUI - Full Table View Dialog.

Provides a comprehensive table view of all manifest line entries with:
- All LineEntry fields as columns (idx, orig, prepro, tl, postpro, wordwr, etc.)
- Column visibility controls with auto-hide for empty columns
- Cell editing (double-click), deletion (Del), multi-select, column clearing
- File filter dropdown with hierarchical folder navigation
- Full RegEx search and replace across selectable columns
- Row selection checkboxes with highlighting
- Pagination (Show All / Show X) with configurable display count
- Save/Discard/Reset/Diff operations against manifest
- Text overflow into adjacent empty cells, multiline support

Architecture note: This dialog handles ONLY display and user interaction.
All manifest data access goes through ManifestManager.
"""

from __future__ import annotations

import copy
import logging
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional, Set, Tuple

from CherryAI.functions.manifest_manager import ManifestManager, FileDirEntry

logger = logging.getLogger(__name__)

# --- Constants --------------------------------------------------------------- #

# All possible line entry fields in display order
LINE_FIELDS: List[str] = [
    "idx", "context_marker", "orig", "prepro", "tl",
    "postpro", "wordwr", "overwrite", "qa_overwrite",
    "log", "tags",
]

# Fields that are NOT editable (but orig can be selected to copy)
NON_EDITABLE_FIELDS: Set[str] = {"idx", "orig"}

# Display names for columns
COLUMN_DISPLAY_NAMES: Dict[str, str] = {
    "idx": "Line #",
    "context_marker": "Tags",
    "orig": "Original",
    "prepro": "Preprocessed",
    "tl": "Translated",
    "postpro": "Postprocessed",
    "wordwr": "Wrapped",
    "overwrite": "Overwrite",
    "qa_overwrite": "Quality Assurance",
    "log": "Log",
    "tags": "Tags (Internal)",
}

# Columns hidden by default even when populated
DEFAULT_HIDDEN: Set[str] = {"context_marker"}

# Reverse lookup: display name → field name
DISPLAY_NAME_TO_FIELD: Dict[str, str] = {v: k for k, v in COLUMN_DISPLAY_NAMES.items()}

# Fields that are metadata (not text content) — excluded from search by default
METADATA_FIELDS: Set[str] = {"log", "tags", "prepro_ops"}

# Default page size
DEFAULT_PAGE_SIZE = 100

# Minimum column width in pixels
MIN_COL_WIDTH = 60
IDX_COL_WIDTH = 50
DEFAULT_COL_WIDTH = 180

# Row height for multiline
DEFAULT_ROW_HEIGHT = 24
MULTILINE_ROW_HEIGHT = 48

# Colors matching CherryAI theme
COLOR_BG = "#E8F4FC"
COLOR_PANEL = "#D6E8F5"
COLOR_INPUT = "#FFFFFF"
COLOR_SELECTED = "#A8CCE8"
COLOR_HOVER = "#C5DCF0"
COLOR_TEXT = "#1A3A5C"
COLOR_TEXT_SEC = "#4A6A8C"
COLOR_BORDER = "#C5DCF0"
COLOR_ACCENT = "#5BA4D9"
COLOR_SUCCESS = "#6BBF8E"
COLOR_CHANGED = "#FFF3CD"
COLOR_HIGHLIGHT = "#D4EDFF"
COLOR_DIFF_ADD = "#D4F5D4"
COLOR_DIFF_DEL = "#F5D4D4"


class FullTableViewDialog(tk.Toplevel):
    """Full table view of all manifest line entries.

    Provides a spreadsheet-like interface for viewing and editing all
    line data from the project manifest.
    """

    def __init__(
        self,
        parent: tk.Tk,
        manifest_manager: ManifestManager,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._mgr = manifest_manager

        # --- State ---
        self._all_lines: List[Dict[str, Any]] = []  # Deep copy of manifest lines
        self._original_lines: List[Dict[str, Any]] = []  # Snapshot for diff/reset
        self._filedir: List[FileDirEntry] = []
        self._visible_columns: List[str] = []
        self._hidden_columns: Set[str] = set()
        self._populated_columns: Set[str] = set()
        self._selected_rows: Set[int] = set()  # Set of idx values
        self._selected_columns: Set[str] = set()  # Columns marked as "Selected"
        self._changes: Dict[int, Dict[str, Any]] = {}  # idx -> {field: new_value}
        self._deleted_fields: Dict[int, Set[str]] = {}  # idx -> set of cleared fields

        # Pagination
        self._page_size = DEFAULT_PAGE_SIZE
        self._show_all = False
        self._page_offset = 0

        # Search state
        self._search_pattern: Optional[re.Pattern[str]] = None
        self._search_column: str = ""  # "" means all columns
        self._search_regex_enabled = False
        self._show_misses = True
        self._search_matches: Set[int] = set()  # idx values that match
        self._current_match_index = -1
        self._pinned_rows: Set[int] = set()  # rows pinned by cell selection during search

        # File filter state
        self._file_filter: Optional[str] = None  # None = All files
        self._filtered_indices: Optional[Set[int]] = None  # None = no filter

        # Diff mode
        self._diff_mode = False

        # Sort state
        self._sort_column: Optional[str] = None
        self._sort_reverse: bool = False

        # Window setup
        self.title("Full Table View")
        self.geometry("1400x800")
        self.minsize(900, 500)
        self.configure(bg=COLOR_BG)

        # Build UI
        self._build_toolbar()
        self._build_table()
        self._build_status_bar()

        # Load data
        self._load_data()

        # Bind close protocol
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Keyboard bindings
        self.bind("<Delete>", self._on_delete_key)
        self.bind("<Escape>", lambda e: self._on_close())

        self.focus_set()
        self.grab_set()

    # ================================================================== #
    #                         DATA LOADING                                #
    # ================================================================== #

    def _load_data(self) -> None:
        """Load all line data from manifest into internal state."""
        raw_lines = self._mgr.get_lines()
        self._all_lines = copy.deepcopy(raw_lines)
        self._original_lines = copy.deepcopy(raw_lines)
        self._filedir = self._mgr.get_filedir()
        self._changes.clear()
        self._deleted_fields.clear()
        self._selected_rows.clear()
        self._diff_mode = False

        # Determine which columns have data
        self._populated_columns = set()
        for line in self._all_lines:
            for key, val in line.items():
                if key == "prepro_ops":
                    continue  # Skip metadata arrays
                if val is not None and val != "" and val is not False:
                    self._populated_columns.add(key)

        # Also scan for dynamic tlc/edit fields not in LINE_FIELDS
        all_keys: Set[str] = set()
        for line in self._all_lines:
            all_keys.update(line.keys())
        # Add dynamic tlc/edit fields
        for key in sorted(all_keys):
            if (key.startswith("tlc") or key.startswith("edit")) and key not in LINE_FIELDS:
                # Insert in correct position
                if key not in LINE_FIELDS:
                    LINE_FIELDS.append(key)

        # Set visible columns: idx always + populated columns (minus default hidden)
        self._visible_columns = [
            f for f in LINE_FIELDS
            if (f in self._populated_columns or f == "idx") and f not in DEFAULT_HIDDEN
        ]
        self._hidden_columns = set(LINE_FIELDS) - set(self._visible_columns)

        self._refresh_file_filter_options()
        self._refresh_column_filter()
        self._refresh_table()

    # ================================================================== #
    #                         TOOLBAR                                     #
    # ================================================================== #

    def _build_toolbar(self) -> None:
        """Build the top toolbar with file filter, search/replace, and action buttons.

        Layout:
        - Top row: File filter | Search entry + RegEx + Results Only + ◀ ▶ | Columns Diff Reset Save
        - Bottom row (below search): Replace entry + Replace All | Column selector
        """
        # --- Top row ---
        top_row = ttk.Frame(self)
        top_row.pack(fill="x", padx=6, pady=(6, 1))

        # Left: File filter (no "File:" label)
        self._file_filter_var = tk.StringVar(value="All")
        self._file_filter_btn = ttk.Button(
            top_row, textvariable=self._file_filter_var,
            command=self._show_file_filter_dropdown, width=24,
        )
        self._file_filter_btn.pack(side="left", padx=(0, 8))

        # Center: Search
        ttk.Label(top_row, text="Search:").pack(side="left", padx=(0, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        self._search_entry = ttk.Entry(top_row, textvariable=self._search_var, width=28)
        self._search_entry.pack(side="left", padx=(0, 4))

        self._regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top_row, text="RegEx", variable=self._regex_var,
            command=self._on_search_changed,
        ).pack(side="left", padx=(0, 4))

        # "Results Only" (inverted from old "Show Misses")
        # When checked: hide non-matching rows. Default: unchecked (show all).
        self._results_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top_row, text="Results Only", variable=self._results_only_var,
            command=self._on_toggle_results_only,
        ).pack(side="left", padx=(0, 4))

        # Prev/Next — arrow only, small
        self._prev_btn = ttk.Button(
            top_row, text="◀", command=self._on_prev_match, width=2,
        )
        self._prev_btn.pack(side="left", padx=(0, 1))
        self._next_btn = ttk.Button(
            top_row, text="▶", command=self._on_next_match, width=2,
        )
        self._next_btn.pack(side="left", padx=(0, 8))

        # Right: Action buttons (text-sized)
        btn_frame = ttk.Frame(top_row)
        btn_frame.pack(side="right", padx=(8, 0))

        ttk.Button(
            btn_frame, text="Columns", command=self._show_column_filter,
        ).pack(side="left", padx=(0, 12))

        ttk.Separator(btn_frame, orient="vertical").pack(
            side="left", fill="y", padx=(0, 12), pady=2,
        )

        ttk.Button(
            btn_frame, text="Diff", command=self._on_diff,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            btn_frame, text="Reset", command=self._on_reset,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            btn_frame, text="Save", command=self._on_save,
        ).pack(side="left")

        # --- Bottom row: Replace + Column selector ---
        bottom_row = ttk.Frame(self)
        bottom_row.pack(fill="x", padx=6, pady=(1, 2))

        # Spacer to align with search entry (file filter button width)
        ttk.Frame(bottom_row, width=190).pack(side="left")

        ttk.Label(bottom_row, text="Replace:").pack(side="left", padx=(0, 4))
        self._replace_var = tk.StringVar()
        self._replace_entry = ttk.Entry(
            bottom_row, textvariable=self._replace_var, width=28,
        )
        self._replace_entry.pack(side="left", padx=(0, 4))

        ttk.Button(
            bottom_row, text="Replace All", command=self._on_replace_all,
        ).pack(side="left", padx=(0, 8))

        # Column selector (no "in:" label)
        self._search_col_var = tk.StringVar(value="All Columns")
        self._search_col_combo = ttk.Combobox(
            bottom_row, textvariable=self._search_col_var,
            state="readonly", width=16,
        )
        self._search_col_combo.pack(side="left")
        self._search_col_combo.bind("<<ComboboxSelected>>", self._on_search_changed)

    # ================================================================== #
    #                         TABLE                                       #
    # ================================================================== #

    def _build_table(self) -> None:
        """Build the main table area using a Canvas + Frame for custom layout."""
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=6, pady=2)

        # Selection bar above column headers (scrolls with tree horizontally)
        self._sel_canvas = tk.Canvas(
            table_frame, height=26, highlightthickness=0, bg=COLOR_BG,
        )
        self._sel_canvas.pack(fill="x")
        self._sel_inner = ttk.Frame(self._sel_canvas)
        self._sel_canvas.create_window((0, 0), window=self._sel_inner, anchor="nw")
        self._sel_labels: Dict[str, tk.Label] = {}

        # Treeview for the table
        self._tree = ttk.Treeview(table_frame, show="headings", selectmode="extended")

        # Scrollbars with synchronized horizontal scroll
        self._vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._hsb = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self._xscroll_synced,
        )
        self._tree.configure(
            yscrollcommand=self._vsb.set,
            xscrollcommand=self._on_tree_xscroll,
        )

        self._vsb.pack(side="right", fill="y")
        self._hsb.pack(side="bottom", fill="x")
        self._tree.pack(fill="both", expand=True)

        # Re-sync selection bar on tree resize / column drag
        self._tree.bind("<Configure>", self._sync_selection_bar, add="+")
        self._tree.bind("<ButtonRelease-1>", self._sync_selection_bar, add="+")

        # Treeview bindings
        self._tree.bind("<Double-1>", self._on_cell_double_click)
        self._tree.bind("<Button-1>", self._on_tree_click)
        self._tree.bind("<MouseWheel>", self._on_mousewheel)

        # Tag configurations for highlighting
        self._tree.tag_configure("selected_row", background=COLOR_SELECTED)
        self._tree.tag_configure("changed", background=COLOR_CHANGED)
        self._tree.tag_configure("match", background=COLOR_HIGHLIGHT)
        self._tree.tag_configure("diff_add", background=COLOR_DIFF_ADD)
        self._tree.tag_configure("diff_del", background=COLOR_DIFF_DEL)
        self._tree.tag_configure("even", background=COLOR_INPUT)
        self._tree.tag_configure("odd", background=COLOR_PANEL)

    def _build_status_bar(self) -> None:
        """Build the bottom status bar with pagination controls."""
        status = ttk.Frame(self)
        status.pack(fill="x", padx=6, pady=(2, 6))

        # Left: showing info
        self._status_label = ttk.Label(status, text="Showing 0 / 0 Lines")
        self._status_label.pack(side="left")

        # Right: pagination
        page_frame = ttk.Frame(status)
        page_frame.pack(side="right")

        self._show_all_var = tk.BooleanVar(value=False)

        self._page_size_var = tk.StringVar(value=str(DEFAULT_PAGE_SIZE))
        ttk.Label(page_frame, text="Show").pack(side="left", padx=(0, 4))
        self._page_spin = ttk.Spinbox(
            page_frame, from_=10, to=999999, width=7,
            textvariable=self._page_size_var,
            command=self._on_page_size_changed,
        )
        self._page_spin.pack(side="left", padx=(0, 4))

        self._show_all_btn = ttk.Button(
            page_frame, text="Show All",
            command=self._on_toggle_show_all, width=10,
        )
        self._show_all_btn.pack(side="left", padx=(0, 8))

        ttk.Button(
            page_frame, text="◀", command=self._on_page_prev, width=3,
        ).pack(side="left", padx=(0, 2))
        ttk.Button(
            page_frame, text="▶", command=self._on_page_next, width=3,
        ).pack(side="left")

    # ================================================================== #
    #                       TABLE REFRESH                                 #
    # ================================================================== #

    def _get_display_lines(self) -> List[Dict[str, Any]]:
        """Get the lines to display based on current filters and pagination."""
        lines = self._all_lines

        # Apply file filter
        if self._filtered_indices is not None:
            lines = [ln for ln in lines if ln.get("idx") in self._filtered_indices]

        # Apply search filter (hide misses mode)
        if self._search_pattern and not self._show_misses:
            lines = [
                ln for ln in lines
                if ln.get("idx") in self._search_matches
                or ln.get("idx") in self._pinned_rows
            ]

        # Apply diff mode
        if self._diff_mode:
            changed_idx = set(self._changes.keys()) | set(self._deleted_fields.keys())
            lines = [ln for ln in lines if ln.get("idx") in changed_idx]

        return lines

    def _get_paginated_lines(self) -> Tuple[List[Dict[str, Any]], int]:
        """Apply pagination to display lines.

        Returns:
            Tuple of (paginated lines, total count).
        """
        all_display = self._get_display_lines()
        total = len(all_display)

        if self._show_all:
            return all_display, total

        start = self._page_offset
        end = start + self._page_size
        return all_display[start:end], total

    def _refresh_table(self) -> None:
        """Rebuild the treeview contents."""
        # Configure columns
        self._tree["columns"] = self._visible_columns
        for col in self._visible_columns:
            width = IDX_COL_WIDTH if col == "idx" else DEFAULT_COL_WIDTH
            display_name = COLUMN_DISPLAY_NAMES.get(col, col)
            if col == self._sort_column:
                indicator = " ▼" if self._sort_reverse else " ▲"
                display_name += indicator
            self._tree.heading(col, text=display_name, command=lambda c=col: self._on_sort(c))
            self._tree.column(col, width=width, minwidth=MIN_COL_WIDTH, stretch=True)

        # Clear existing
        self._tree.delete(*self._tree.get_children())

        # Get paginated lines
        lines, total = self._get_paginated_lines()

        # Insert rows
        for i, line in enumerate(lines):
            idx = line.get("idx", 0)
            values = []
            for col in self._visible_columns:
                val = line.get(col, "")
                if val is None:
                    val = ""
                elif not isinstance(val, str):
                    val = str(val)
                values.append(val)

            # Determine row tags
            tags: List[str] = []
            if idx in self._selected_rows:
                tags.append("selected_row")
            if idx in self._changes or idx in self._deleted_fields:
                tags.append("changed")
            if idx in self._search_matches and self._search_pattern:
                tags.append("match")
            if not tags:
                tags.append("even" if i % 2 == 0 else "odd")

            self._tree.insert("", "end", iid=str(idx), values=values, tags=tuple(tags))

        # Update status
        shown = len(lines)
        self._status_label.configure(text=f"Showing {shown} / {total} Lines")

        # Update show all button text
        if self._show_all:
            self._show_all_btn.configure(text=f"Show {DEFAULT_PAGE_SIZE}")
        else:
            self._show_all_btn.configure(text="Show All")

        # Rebuild checkbox row
        self._rebuild_selection_bar()

    def _rebuild_selection_bar(self) -> None:
        """Rebuild the Select / Selected bar above each column."""
        for child in self._sel_inner.winfo_children():
            child.destroy()
        self._sel_labels.clear()

        self._tree.update_idletasks()
        x_offset = 0
        for col in self._visible_columns:
            selected = col in self._selected_columns
            text = "Selected" if selected else "Select"
            bg = COLOR_SELECTED if selected else COLOR_PANEL
            w = self._tree.column(col, "width")
            lbl = tk.Label(
                self._sel_inner, text=text, relief="raised", borderwidth=1,
                font=("TkDefaultFont", 9), bg=bg, fg=COLOR_TEXT,
                cursor="hand2",
            )
            lbl.place(x=x_offset, y=0, width=w, height=24)
            lbl.bind("<Button-1>", lambda e, c=col: self._toggle_column_selection(c))
            self._sel_labels[col] = lbl
            x_offset += w

        total_w = max(x_offset, 1)
        self._sel_inner.configure(width=total_w, height=24)
        self._sel_canvas.configure(scrollregion=(0, 0, total_w, 26))

    def _sync_selection_bar(self, _event: Any = None) -> None:
        """Re-sync selection bar label widths with treeview columns."""
        self._tree.update_idletasks()
        x_offset = 0
        for col in self._visible_columns:
            lbl = self._sel_labels.get(col)
            if lbl is None:
                continue
            w = self._tree.column(col, "width")
            lbl.place_configure(x=x_offset, width=w)
            x_offset += w
        total_w = max(x_offset, 1)
        self._sel_inner.configure(width=total_w)
        self._sel_canvas.configure(scrollregion=(0, 0, total_w, 26))

    def _xscroll_synced(self, *args: Any) -> None:
        """Scroll both the tree and selection bar horizontally."""
        self._tree.xview(*args)
        self._sel_canvas.xview(*args)

    def _on_tree_xscroll(self, first: str, last: str) -> None:
        """Handle tree horizontal scroll — sync scrollbar and selection bar."""
        self._hsb.set(first, last)
        self._sel_canvas.xview_moveto(float(first))

    # ================================================================== #
    #                       FILE FILTER                                   #
    # ================================================================== #

    def _refresh_file_filter_options(self) -> None:
        """Build the file filter options from filedir."""
        self._file_tree: Dict[str, Any] = {}  # Nested dict for folder structure
        self._file_paths: List[str] = []  # Flat list of all rel_paths

        for entry in self._filedir:
            self._file_paths.append(entry.rel_path)
            parts = entry.rel_path.replace("\\", "/").split("/")
            node = self._file_tree
            for part in parts[:-1]:
                if part not in node:
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = entry  # Leaf is the FileDirEntry

    def _show_file_filter_dropdown(self) -> None:
        """Show the hierarchical file filter dropdown."""
        dropdown = _FileFilterDropdown(
            self, self._file_tree, self._filedir,
            current_filter=self._file_filter,
            on_select=self._apply_file_filter,
        )
        # Position below the button
        x = self._file_filter_btn.winfo_rootx()
        y = self._file_filter_btn.winfo_rooty() + self._file_filter_btn.winfo_height()
        dropdown.geometry(f"+{x}+{y}")

    def _apply_file_filter(self, filter_path: Optional[str]) -> None:
        """Apply a file filter.

        Args:
            filter_path: Relative path prefix to filter by, or None for All.
        """
        self._file_filter = filter_path
        if filter_path is None:
            self._filtered_indices = None
            self._file_filter_var.set("All")
        else:
            self._filtered_indices = set()
            for entry in self._filedir:
                rel = entry.rel_path.replace("\\", "/")
                filter_norm = filter_path.replace("\\", "/")
                if rel == filter_norm or rel.startswith(filter_norm + "/"):
                    for idx in range(entry.first_idx, entry.last_idx + 1):
                        self._filtered_indices.add(idx)
            display = filter_path.replace("\\", "/")
            if len(display) > 28:
                display = "…" + display[-27:]
            self._file_filter_var.set(display)

        self._page_offset = 0
        self._refresh_table()

    # ================================================================== #
    #                       COLUMN FILTER                                 #
    # ================================================================== #

    def _refresh_column_filter(self) -> None:
        """Update the search column combo box."""
        cols = ["All Columns"] + [
            COLUMN_DISPLAY_NAMES.get(c, c) for c in self._visible_columns if c != "idx"
        ]
        self._search_col_combo["values"] = cols

    def _show_column_filter(self) -> None:
        """Show column visibility as a dropdown menu.

        Options: Show All, Show Visible (populated), Show Latest, separator,
        then individual named columns with checkmarks.
        """
        menu = tk.Menu(self, tearoff=0)

        menu.add_command(
            label="Show All",
            command=lambda: self._apply_column_preset("all"),
        )
        menu.add_command(
            label="Show Visible",
            command=lambda: self._apply_column_preset("visible"),
        )
        menu.add_command(
            label="Show Latest",
            command=lambda: self._apply_column_preset("latest"),
        )
        menu.add_separator()

        # Individual columns with checkmarks
        self._col_menu_vars: Dict[str, tk.BooleanVar] = {}
        for col in LINE_FIELDS:
            display = COLUMN_DISPLAY_NAMES.get(col, col)
            var = tk.BooleanVar(value=col in self._visible_columns)
            self._col_menu_vars[col] = var
            menu.add_checkbutton(
                label=display,
                variable=var,
                command=lambda: self._apply_column_menu_selection(),
            )

        # Show the menu at the button position
        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _apply_column_preset(self, preset: str) -> None:
        """Apply a column visibility preset.

        Args:
            preset: One of 'all', 'visible', 'latest'.
        """
        if preset == "all":
            visible = set(LINE_FIELDS)
        elif preset == "visible":
            visible = {f for f in LINE_FIELDS if f in self._populated_columns or f == "idx"}
        elif preset == "latest":
            visible = self._compute_latest_columns()
        else:
            return
        self._apply_column_visibility(visible)

    def _compute_latest_columns(self) -> Set[str]:
        """Compute 'Show Latest' — idx + Tags + furthest non-empty right column per line.

        For each line, finds the rightmost populated field in the pipeline
        (orig → prepro → tl → postpro → wordwr → overwrite → qa_overwrite)
        and includes that column. Always includes idx.
        """
        pipeline_cols = [
            f for f in LINE_FIELDS
            if f not in {"idx", "context_marker", "log", "tags"}
        ]
        visible: Set[str] = {"idx"}
        for line in self._all_lines:
            for col in reversed(pipeline_cols):
                val = line.get(col)
                if val is not None and val != "":
                    visible.add(col)
                    break
        return visible

    def _apply_column_menu_selection(self) -> None:
        """Apply column visibility from individual checkbutton menu selections."""
        visible = {
            col for col, var in self._col_menu_vars.items() if var.get()
        }
        self._apply_column_visibility(visible)

    def _apply_column_visibility(self, visible: Set[str]) -> None:
        """Apply column visibility changes.

        All columns including Line # and Tags are hideable.
        """
        self._visible_columns = [f for f in LINE_FIELDS if f in visible]
        self._hidden_columns = set(LINE_FIELDS) - visible
        self._refresh_column_filter()
        self._refresh_table()

    # ================================================================== #
    #                       SEARCH & REPLACE                              #
    # ================================================================== #

    def _on_search_changed(self, *_args: Any) -> None:
        """Handle search text or options change."""
        query = self._search_var.get()
        if not query:
            self._search_pattern = None
            self._search_matches.clear()
            self._current_match_index = -1
            self._refresh_table()
            return

        # Build pattern
        try:
            if self._regex_var.get():
                self._search_pattern = re.compile(query, re.IGNORECASE)
            else:
                self._search_pattern = re.compile(re.escape(query), re.IGNORECASE)
        except re.error:
            self._search_pattern = None
            self._search_matches.clear()
            self._refresh_table()
            return

        # Determine search columns
        # If columns are selected, search only those; otherwise visible columns
        col_sel = self._search_col_var.get()
        if col_sel == "All Columns":
            if self._selected_columns:
                search_cols = [c for c in self._selected_columns if c not in METADATA_FIELDS]
            else:
                search_cols = [c for c in self._visible_columns if c not in METADATA_FIELDS]
        else:
            # Resolve display name to field name
            field = DISPLAY_NAME_TO_FIELD.get(col_sel, col_sel)
            search_cols = [field]

        # Find matches
        self._search_matches.clear()
        for line in self._all_lines:
            idx = line.get("idx", 0)
            # Respect file filter
            if self._filtered_indices is not None and idx not in self._filtered_indices:
                continue
            for col in search_cols:
                val = line.get(col, "")
                if val and isinstance(val, str) and self._search_pattern.search(val):
                    self._search_matches.add(idx)
                    break

        self._current_match_index = 0 if self._search_matches else -1
        self._refresh_table()

    def _on_toggle_results_only(self) -> None:
        """Toggle Results Only mode.

        When Results Only is checked, non-matching rows are hidden.
        Internally: _show_misses is the inverse of results_only.
        """
        self._show_misses = not self._results_only_var.get()
        self._page_offset = 0
        self._refresh_table()

    def _on_prev_match(self) -> None:
        """Navigate to previous search match."""
        if not self._search_matches:
            return
        sorted_matches = sorted(self._search_matches)
        if self._current_match_index > 0:
            self._current_match_index -= 1
        else:
            self._current_match_index = len(sorted_matches) - 1
        target_idx = sorted_matches[self._current_match_index]
        self._scroll_to_idx(target_idx)

    def _on_next_match(self) -> None:
        """Navigate to next search match."""
        if not self._search_matches:
            return
        sorted_matches = sorted(self._search_matches)
        if self._current_match_index < len(sorted_matches) - 1:
            self._current_match_index += 1
        else:
            self._current_match_index = 0
        target_idx = sorted_matches[self._current_match_index]
        self._scroll_to_idx(target_idx)

    def _scroll_to_idx(self, idx: int) -> None:
        """Scroll the treeview to show the row with given idx."""
        iid = str(idx)
        if self._tree.exists(iid):
            self._tree.see(iid)
            self._tree.selection_set(iid)

    def _on_replace_all(self) -> None:
        """Replace all search matches in the specified columns."""
        if not self._search_pattern:
            return

        replace_text = self._replace_var.get()
        col_sel = self._search_col_var.get()
        if col_sel == "All Columns":
            if self._selected_columns:
                target_cols = [
                    c for c in self._selected_columns
                    if c not in NON_EDITABLE_FIELDS and c not in METADATA_FIELDS
                ]
            else:
                target_cols = [
                    c for c in self._visible_columns
                    if c not in NON_EDITABLE_FIELDS and c not in METADATA_FIELDS
                ]
        else:
            # Resolve display name to field name
            field = DISPLAY_NAME_TO_FIELD.get(col_sel, col_sel)
            if field in NON_EDITABLE_FIELDS:
                display = COLUMN_DISPLAY_NAMES.get(field, field)
                messagebox.showwarning("Replace", f"Column '{display}' is not editable.")
                return
            target_cols = [field]

        count = 0
        for line in self._all_lines:
            idx = line.get("idx", 0)
            if idx not in self._search_matches:
                continue
            for col in target_cols:
                val = line.get(col, "")
                if val and isinstance(val, str) and self._search_pattern.search(val):
                    new_val = self._search_pattern.sub(replace_text, val)
                    if new_val != val:
                        line[col] = new_val
                        self._record_change(idx, col, new_val)
                        count += 1

        if count > 0:
            self._on_search_changed()  # Refresh search matches
            self._refresh_table()
            messagebox.showinfo("Replace", f"Replaced {count} occurrence(s).")
        else:
            messagebox.showinfo("Replace", "No replacements made.")

    # ================================================================== #
    #                       CELL EDITING                                  #
    # ================================================================== #

    def _on_cell_double_click(self, event: tk.Event) -> None:
        """Handle double-click to edit a cell."""
        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        item = self._tree.identify_row(event.y)
        column = self._tree.identify_column(event.x)
        if not item or not column:
            return

        # Get column name from #N format
        col_idx_num = int(column.replace("#", "")) - 1
        if col_idx_num < 0 or col_idx_num >= len(self._visible_columns):
            return
        col_name = self._visible_columns[col_idx_num]

        idx = int(item)
        # Find the line
        line = self._find_line(idx)
        if line is None:
            return

        current_val = line.get(col_name, "") or ""

        if col_name in NON_EDITABLE_FIELDS:
            # For orig: allow read-only selection to copy content
            if col_name == "orig":
                self._show_readonly_cell(item, column, str(current_val))
            return

        # Create inline edit widget
        self._start_inline_edit(item, column, col_name, idx, str(current_val))

    def _start_inline_edit(
        self, item: str, column: str, col_name: str, idx: int, current_val: str,
    ) -> None:
        """Create an inline Text widget for editing a cell value."""
        # Get cell bbox
        bbox = self._tree.bbox(item, column)
        if not bbox:
            return

        x, y, w, h = bbox

        # Use Text widget for multiline support
        edit_widget = tk.Text(
            self._tree, wrap="word",
            font=("TkDefaultFont", 9),
            bd=1, relief="solid",
        )
        edit_widget.insert("1.0", current_val)
        edit_widget.place(x=x, y=y, width=max(w, 200), height=max(h, 60))
        edit_widget.focus_set()
        edit_widget.tag_add("sel", "1.0", "end")

        def finish_edit(save: bool = True) -> None:
            if save:
                new_val = edit_widget.get("1.0", "end-1c")
                if new_val != current_val:
                    line = self._find_line(idx)
                    if line is not None:
                        line[col_name] = new_val
                        self._record_change(idx, col_name, new_val)
                        self._refresh_table()
            edit_widget.destroy()

        edit_widget.bind("<Return>", lambda e: (finish_edit(True), "break")[1])
        edit_widget.bind("<Shift-Return>", lambda e: None)  # Allow shift+enter for newline
        edit_widget.bind("<Escape>", lambda e: finish_edit(False))
        edit_widget.bind("<FocusOut>", lambda e: finish_edit(True))

    def _show_readonly_cell(self, item: str, column: str, value: str) -> None:
        """Show a read-only text widget for copying cell content (e.g., Original)."""
        bbox = self._tree.bbox(item, column)
        if not bbox:
            return
        x, y, w, h = bbox
        widget = tk.Text(
            self._tree, wrap="word",
            font=("TkDefaultFont", 9),
            bd=1, relief="solid",
            bg="#F0F0F0",
        )
        widget.insert("1.0", value)
        widget.configure(state="disabled")
        widget.place(x=x, y=y, width=max(w, 200), height=max(h, 60))
        widget.focus_set()

        def close(_event: Any = None) -> None:
            widget.destroy()

        widget.bind("<Escape>", close)
        widget.bind("<FocusOut>", close)
        # Allow Ctrl+C even in disabled state
        widget.bind("<Control-c>", lambda e: (
            widget.configure(state="normal"),
            widget.event_generate("<<Copy>>"),
            widget.configure(state="disabled"),
        ))

    def _on_delete_key(self, event: tk.Event) -> None:
        """Handle Delete key to clear selected cells."""
        selected = self._tree.selection()
        if not selected:
            return

        # Get selected items - clear all editable fields for selected rows
        for item in selected:
            idx = int(item)
            line = self._find_line(idx)
            if line is None:
                continue

            # If specific rows are checkbox-selected, only clear those rows
            if self._selected_rows and idx not in self._selected_rows:
                continue

            for col in self._visible_columns:
                if col in NON_EDITABLE_FIELDS:
                    continue
                if line.get(col):
                    line[col] = ""
                    self._record_delete(idx, col)

        self._refresh_table()

    def _toggle_column_selection(self, col: str) -> None:
        """Toggle a column's selection state for search/replace scoping."""
        if col in self._selected_columns:
            self._selected_columns.discard(col)
        else:
            self._selected_columns.add(col)
        # Update the label appearance
        lbl = self._sel_labels.get(col)
        if lbl is not None:
            selected = col in self._selected_columns
            lbl.configure(
                text="Selected" if selected else "Select",
                bg=COLOR_SELECTED if selected else COLOR_PANEL,
            )

    def _clear_column(self, col: str) -> None:
        """Clear all values in a column."""
        if col in NON_EDITABLE_FIELDS:
            return

        display = COLUMN_DISPLAY_NAMES.get(col, col)
        if not messagebox.askyesno(
            "Clear Column",
            f"Clear all values in column '{display}'?\nThis affects ALL lines, not just visible ones.",
        ):
            return

        for line in self._all_lines:
            idx = line.get("idx", 0)
            if self._filtered_indices is not None and idx not in self._filtered_indices:
                continue
            if line.get(col):
                line[col] = ""
                self._record_delete(idx, col)

        self._refresh_table()

    # ================================================================== #
    #                       TREE INTERACTION                              #
    # ================================================================== #

    def _on_tree_click(self, event: tk.Event) -> None:
        """Handle single click — toggle row selection."""
        item = self._tree.identify_row(event.y)
        if not item:
            return

        idx = int(item)

        # Pin row for search filtering
        if self._search_pattern and not self._show_misses:
            self._pinned_rows.add(idx)

        # Ctrl+click for multi-select
        if event.state & 0x4:  # Ctrl key
            if idx in self._selected_rows:
                self._selected_rows.discard(idx)
            else:
                self._selected_rows.add(idx)
        elif event.state & 0x1:  # Shift key
            # Range select
            if self._selected_rows:
                last = max(self._selected_rows)
                start, end = min(idx, last), max(idx, last)
                for ln in self._all_lines:
                    ln_idx = ln.get("idx", 0)
                    if start <= ln_idx <= end:
                        self._selected_rows.add(ln_idx)
        else:
            # Regular click — don't toggle, let treeview handle selection
            pass

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mousewheel scrolling from anywhere in the dialog."""
        self._tree.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_sort(self, col: str) -> None:
        """Sort the table by a column."""
        if self._sort_column == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = col
            self._sort_reverse = False

        def sort_key(line: Dict[str, Any]) -> Any:
            val = line.get(col, "")
            if col == "idx":
                return int(val) if val else 0
            return str(val or "").lower()

        self._all_lines.sort(key=sort_key, reverse=self._sort_reverse)
        self._refresh_table()

    # ================================================================== #
    #                       PAGINATION                                    #
    # ================================================================== #

    def _on_page_size_changed(self) -> None:
        """Handle page size spinbox change."""
        try:
            self._page_size = int(self._page_size_var.get())
        except ValueError:
            self._page_size = DEFAULT_PAGE_SIZE
        self._page_offset = 0
        self._show_all = False
        self._refresh_table()

    def _on_toggle_show_all(self) -> None:
        """Toggle between Show All and paginated view."""
        self._show_all = not self._show_all
        self._page_offset = 0
        self._refresh_table()

    def _on_page_prev(self) -> None:
        """Navigate to previous page."""
        if self._page_offset > 0:
            self._page_offset = max(0, self._page_offset - self._page_size)
            self._refresh_table()

    def _on_page_next(self) -> None:
        """Navigate to next page."""
        total = len(self._get_display_lines())
        if self._page_offset + self._page_size < total:
            self._page_offset += self._page_size
            self._refresh_table()

    # ================================================================== #
    #                       CHANGE TRACKING                               #
    # ================================================================== #

    def _record_change(self, idx: int, field: str, value: Any) -> None:
        """Record a change to a line field."""
        if idx not in self._changes:
            self._changes[idx] = {}
        self._changes[idx][field] = value

    def _record_delete(self, idx: int, field: str) -> None:
        """Record a field deletion."""
        if idx not in self._deleted_fields:
            self._deleted_fields[idx] = set()
        self._deleted_fields[idx].add(field)
        self._record_change(idx, field, "")

    def _has_changes(self) -> bool:
        """Check if there are any unsaved changes."""
        return bool(self._changes) or bool(self._deleted_fields)

    def _find_line(self, idx: int) -> Optional[Dict[str, Any]]:
        """Find a line by its idx in the working copy."""
        for line in self._all_lines:
            if line.get("idx") == idx:
                return line
        return None

    # ================================================================== #
    #                       SAVE / RESET / DIFF                           #
    # ================================================================== #

    def _on_save(self) -> None:
        """Save changes to manifest."""
        if not self._has_changes():
            messagebox.showinfo("Save", "No changes to save.")
            return

        # If rows are selected, only save selected rows
        save_indices = self._selected_rows if self._selected_rows else None

        count = 0
        for idx, fields in self._changes.items():
            if save_indices is not None and idx not in save_indices:
                continue
            for field, value in fields.items():
                self._mgr.set_line_field(idx, field, value)
                count += 1

        # Clear saved changes from tracking
        if save_indices:
            for idx in list(self._changes.keys()):
                if idx in save_indices:
                    del self._changes[idx]
            for idx in list(self._deleted_fields.keys()):
                if idx in save_indices:
                    del self._deleted_fields[idx]
        else:
            self._changes.clear()
            self._deleted_fields.clear()

        # Update original snapshot for saved lines
        self._original_lines = copy.deepcopy(self._mgr.get_lines())

        self._refresh_table()
        messagebox.showinfo("Save", f"Saved {count} field change(s) to manifest.")

    def _on_reset(self) -> None:
        """Reset changes using manifest data."""
        if not self._has_changes() and not self._selected_rows:
            messagebox.showinfo("Reset", "No changes to reset.")
            return

        scope = "selected rows" if self._selected_rows else "ALL changes"
        if not messagebox.askyesno("Reset", f"Reset {scope} to manifest values?"):
            return

        if self._selected_rows:
            # Reset only selected rows
            for idx in self._selected_rows:
                orig_line = None
                for ln in self._original_lines:
                    if ln.get("idx") == idx:
                        orig_line = ln
                        break
                if orig_line:
                    for i, line in enumerate(self._all_lines):
                        if line.get("idx") == idx:
                            self._all_lines[i] = copy.deepcopy(orig_line)
                            break
                self._changes.pop(idx, None)
                self._deleted_fields.pop(idx, None)
        else:
            # Reset all
            self._all_lines = copy.deepcopy(self._original_lines)
            self._changes.clear()
            self._deleted_fields.clear()

        self._refresh_table()

    def _on_diff(self) -> None:
        """Toggle diff mode — show only changed rows/columns."""
        if not self._has_changes():
            messagebox.showinfo("Diff", "No changes to show.")
            return

        self._diff_mode = not self._diff_mode
        self._page_offset = 0
        self._refresh_table()

    # ================================================================== #
    #                       CLOSE HANDLER                                 #
    # ================================================================== #

    def _on_close(self) -> None:
        """Handle window close — ask to save if there are changes."""
        if self._has_changes():
            result = messagebox.askyesnocancel(
                "Unsaved Changes",
                "There are unsaved changes. Save before closing?",
            )
            if result is None:
                return  # Cancel
            if result:
                self._on_save()

        self.grab_release()
        self.destroy()


# ====================================================================== #
#                    FILE FILTER DROPDOWN                                 #
# ====================================================================== #

class _FileFilterDropdown(tk.Toplevel):
    """Hierarchical file filter dropdown with folder navigation."""

    def __init__(
        self,
        parent: tk.Toplevel,
        file_tree: Dict[str, Any],
        filedir: List[FileDirEntry],
        current_filter: Optional[str],
        on_select: Any,
    ) -> None:
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=COLOR_BORDER)

        self._file_tree = file_tree
        self._filedir = filedir
        self._on_select = on_select
        self._current_path: List[str] = []  # Navigation breadcrumb

        # Build list frame
        self._frame = ttk.Frame(self, padding=2)
        self._frame.pack(fill="both", expand=True)

        self._listbox = tk.Listbox(
            self._frame, bg=COLOR_INPUT, fg=COLOR_TEXT,
            selectbackground=COLOR_SELECTED,
            font=("TkDefaultFont", 11),
            width=40, height=15,
            activestyle="none",
        )
        scrollbar = ttk.Scrollbar(self._frame, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)

        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._listbox.bind("<Double-1>", self._on_item_double_click)
        self._listbox.bind("<Return>", self._on_item_double_click)
        self._listbox.bind("<BackSpace>", self._on_back)
        self._listbox.bind("<Escape>", lambda e: self.destroy())
        self._listbox.bind("<Key-Up>", self._on_key_navigate)
        self._listbox.bind("<Key-Down>", self._on_key_navigate)
        self._listbox.bind("<Prior>", self._on_key_navigate)  # Page Up
        self._listbox.bind("<Next>", self._on_key_navigate)   # Page Down
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<MouseWheel>", self._on_mousewheel)

        self._populate_list()
        self._listbox.focus_set()

    def _get_current_node(self) -> Dict[str, Any]:
        """Get the current navigation node."""
        node = self._file_tree
        for part in self._current_path:
            node = node.get(part, {})
        return node

    def _populate_list(self) -> None:
        """Populate the listbox with current directory contents."""
        self._listbox.delete(0, tk.END)
        self._items: List[Tuple[str, bool]] = []  # (name, is_folder)

        # Add "All"  or "Back" at top
        if self._current_path:
            self._listbox.insert(tk.END, "◀ Back")
            self._items.append(("__back__", False))
        else:
            self._listbox.insert(tk.END, "All")
            self._items.append(("__all__", False))

        node = self._get_current_node()

        # Sort: folders first, then files
        folders = []
        files = []
        for key, val in sorted(node.items()):
            if isinstance(val, dict) and not isinstance(val, FileDirEntry):
                # Check if it's a folder (has nested items) vs a leaf
                if any(not isinstance(v, FileDirEntry) for v in val.values()):
                    folders.append(key)
                elif val:
                    # All children are FileDirEntry — it's a folder
                    folders.append(key)
                else:
                    folders.append(key)
            elif isinstance(val, FileDirEntry):
                files.append(key)
            elif isinstance(val, dict):
                folders.append(key)

        for folder in folders:
            self._listbox.insert(tk.END, f"📁 {folder}")
            self._items.append((folder, True))

        for f in files:
            self._listbox.insert(tk.END, f"  {f}")
            self._items.append((f, False))

        if self._listbox.size() > 0:
            self._listbox.selection_set(0)

    def _on_item_double_click(self, event: tk.Event) -> None:
        """Handle double-click or Enter on an item."""
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        name, is_folder = self._items[idx]

        if name == "__all__":
            self._on_select(None)
            self.destroy()
        elif name == "__back__":
            self._on_back(None)
        elif is_folder:
            self._current_path.append(name)
            self._populate_list()
        else:
            # File selected
            path = "/".join(self._current_path + [name])
            self._on_select(path)
            self.destroy()

    def _on_back(self, event: Any) -> None:
        """Navigate back one level."""
        if self._current_path:
            self._current_path.pop()
            self._populate_list()

    def _on_key_navigate(self, event: tk.Event) -> str:
        """Handle keyboard navigation."""
        return ""  # Let default listbox handling work

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mousewheel."""
        self._listbox.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_focus_out(self, event: tk.Event) -> None:
        """Close dropdown when focus leaves."""
        # Small delay to handle focus transitions
        self.after(150, self._check_focus)

    def _check_focus(self) -> None:
        """Check if focus is still within this dropdown."""
        try:
            focused = self.focus_get()
            if focused is None or not str(focused).startswith(str(self)):
                self.destroy()
        except tk.TclError:
            pass
