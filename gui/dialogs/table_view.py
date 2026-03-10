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
    "idx", "orig", "prepro", "edited_prepro", "tl",
    "tlc1", "edit1", "tlc2", "edit2", "tlc3", "edit3",
    "postpro", "wordwr", "overwrite", "qa_overwrite",
    "log", "tags", "context_marker",
]

# Fields that are NOT editable
NON_EDITABLE_FIELDS: Set[str] = {"idx"}

# Fields that are metadata (not text content) — excluded from search by default
METADATA_FIELDS: Set[str] = {"idx", "log", "tags", "context_marker", "prepro_ops"}

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

        # Set visible columns: idx always + populated columns
        self._visible_columns = [
            f for f in LINE_FIELDS
            if f in self._populated_columns or f == "idx"
        ]
        self._hidden_columns = set(LINE_FIELDS) - set(self._visible_columns)

        self._refresh_file_filter_options()
        self._refresh_column_filter()
        self._refresh_table()

    # ================================================================== #
    #                         TOOLBAR                                     #
    # ================================================================== #

    def _build_toolbar(self) -> None:
        """Build the top toolbar with file filter, search, and action buttons."""
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=6, pady=(6, 2))

        # --- Left section: File filter ---
        file_frame = ttk.Frame(toolbar)
        file_frame.pack(side="left", padx=(0, 12))

        ttk.Label(file_frame, text="File:").pack(side="left", padx=(0, 4))
        self._file_filter_var = tk.StringVar(value="All")
        self._file_filter_btn = ttk.Button(
            file_frame, textvariable=self._file_filter_var,
            command=self._show_file_filter_dropdown, width=28,
        )
        self._file_filter_btn.pack(side="left")

        # --- Center section: Search ---
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side="left", fill="x", expand=True, padx=(0, 12))

        ttk.Label(search_frame, text="Search:").pack(side="left", padx=(0, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        self._search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        self._search_entry.pack(side="left", padx=(0, 4))

        self._regex_var = tk.BooleanVar(value=False)
        self._regex_btn = ttk.Checkbutton(
            search_frame, text="RegEx", variable=self._regex_var,
            command=self._on_search_changed,
        )
        self._regex_btn.pack(side="left", padx=(0, 4))

        self._miss_var = tk.BooleanVar(value=True)
        self._miss_btn = ttk.Checkbutton(
            search_frame, text="Show Misses", variable=self._miss_var,
            command=self._on_toggle_misses,
        )
        self._miss_btn.pack(side="left", padx=(0, 4))

        self._prev_btn = ttk.Button(
            search_frame, text="◀ Prev", command=self._on_prev_match, width=7,
        )
        self._next_btn = ttk.Button(
            search_frame, text="Next ▶", command=self._on_next_match, width=7,
        )
        # Prev/Next only visible when Show Misses is active
        self._prev_btn.pack(side="left", padx=(0, 2))
        self._next_btn.pack(side="left", padx=(0, 4))

        ttk.Label(search_frame, text="Replace:").pack(side="left", padx=(4, 4))
        self._replace_var = tk.StringVar()
        self._replace_entry = ttk.Entry(search_frame, textvariable=self._replace_var, width=20)
        self._replace_entry.pack(side="left", padx=(0, 4))

        ttk.Button(
            search_frame, text="Replace All", command=self._on_replace_all, width=10,
        ).pack(side="left", padx=(0, 4))

        # Search column selector
        ttk.Label(search_frame, text="in:").pack(side="left", padx=(4, 4))
        self._search_col_var = tk.StringVar(value="All Columns")
        self._search_col_combo = ttk.Combobox(
            search_frame, textvariable=self._search_col_var,
            state="readonly", width=14,
        )
        self._search_col_combo.pack(side="left")
        self._search_col_combo.bind("<<ComboboxSelected>>", self._on_search_changed)

        # --- Right section: Action buttons ---
        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side="right", padx=(12, 0))

        # Column filter dropdown
        ttk.Button(
            btn_frame, text="Columns", command=self._show_column_filter, width=8,
        ).pack(side="left", padx=(0, 16))

        # Spacer between column filter and action buttons
        ttk.Separator(btn_frame, orient="vertical").pack(
            side="left", fill="y", padx=(0, 16), pady=2,
        )

        ttk.Button(
            btn_frame, text="Diff", command=self._on_diff, width=6,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            btn_frame, text="Reset", command=self._on_reset, width=6,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            btn_frame, text="Save", command=self._on_save, width=6,
        ).pack(side="left", padx=(0, 0))

    # ================================================================== #
    #                         TABLE                                       #
    # ================================================================== #

    def _build_table(self) -> None:
        """Build the main table area using a Canvas + Frame for custom layout."""
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=6, pady=2)

        # Checkbox row above column headers
        self._checkbox_frame = ttk.Frame(table_frame)
        self._checkbox_frame.pack(fill="x")

        # Treeview for the table
        self._tree = ttk.Treeview(table_frame, show="headings", selectmode="extended")

        # Scrollbars
        self._vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=self._vsb.set, xscrollcommand=self._hsb.set)

        self._vsb.pack(side="right", fill="y")
        self._hsb.pack(side="bottom", fill="x")
        self._tree.pack(fill="both", expand=True)

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
            self._tree.heading(col, text=col, command=lambda c=col: self._on_sort(c))
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
        self._rebuild_checkboxes()

    def _rebuild_checkboxes(self) -> None:
        """Rebuild the Select checkboxes above each column."""
        for child in self._checkbox_frame.winfo_children():
            child.destroy()

        for col in self._visible_columns:
            if col == "idx":
                lbl = ttk.Label(self._checkbox_frame, text="Select", width=6)
                lbl.pack(side="left", padx=2)
            else:
                var = tk.BooleanVar(value=False)
                cb = ttk.Checkbutton(
                    self._checkbox_frame, text="",
                    variable=var,
                    command=lambda c=col, v=var: self._on_column_select_toggle(c, v),
                )
                cb.pack(side="left", padx=2)

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
        cols = ["All Columns"] + [c for c in self._visible_columns if c != "idx"]
        self._search_col_combo["values"] = cols

    def _show_column_filter(self) -> None:
        """Show a column visibility dropdown."""
        dropdown = _ColumnFilterDropdown(
            self,
            all_columns=LINE_FIELDS,
            visible=set(self._visible_columns),
            populated=self._populated_columns,
            on_apply=self._apply_column_visibility,
        )
        x = self.winfo_rootx() + self.winfo_width() - 300
        y = self.winfo_rooty() + 40
        dropdown.geometry(f"+{x}+{y}")

    def _apply_column_visibility(self, visible: Set[str]) -> None:
        """Apply column visibility changes."""
        # idx is always visible
        visible.add("idx")
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
        col_sel = self._search_col_var.get()
        if col_sel == "All Columns":
            search_cols = [c for c in self._visible_columns if c not in METADATA_FIELDS]
        else:
            search_cols = [col_sel]

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

    def _on_toggle_misses(self) -> None:
        """Toggle Show Misses / Hide Misses."""
        self._show_misses = self._miss_var.get()
        # Show prev/next buttons when misses are shown
        if self._show_misses:
            self._prev_btn.configure(state="normal")
            self._next_btn.configure(state="normal")
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
            target_cols = [c for c in self._visible_columns if c not in NON_EDITABLE_FIELDS and c not in METADATA_FIELDS]
        else:
            if col_sel in NON_EDITABLE_FIELDS:
                messagebox.showwarning("Replace", f"Column '{col_sel}' is not editable.")
                return
            target_cols = [col_sel]

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

        if col_name in NON_EDITABLE_FIELDS:
            return

        idx = int(item)
        # Find the line
        line = self._find_line(idx)
        if line is None:
            return

        current_val = line.get(col_name, "") or ""

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

    def _on_column_select_toggle(self, col: str, var: tk.BooleanVar) -> None:
        """Handle column select checkbox toggle."""
        # This selects all currently visible rows in this column for operations
        if var.get():
            for item in self._tree.get_children():
                idx = int(item)
                self._selected_rows.add(idx)
        else:
            self._selected_rows.clear()
        self._refresh_table()

    def _clear_column(self, col: str) -> None:
        """Clear all values in a column."""
        if col in NON_EDITABLE_FIELDS:
            return

        if not messagebox.askyesno(
            "Clear Column",
            f"Clear all values in column '{col}'?\nThis affects ALL lines, not just visible ones.",
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
        # Simple toggle sort
        reverse = getattr(self, "_sort_reverse", False)
        self._sort_reverse = not reverse

        def sort_key(line: Dict[str, Any]) -> Any:
            val = line.get(col, "")
            if col == "idx":
                return int(val) if val else 0
            return str(val or "").lower()

        self._all_lines.sort(key=sort_key, reverse=reverse)
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
            font=("TkDefaultFont", 9),
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


# ====================================================================== #
#                    COLUMN FILTER DROPDOWN                               #
# ====================================================================== #

class _ColumnFilterDropdown(tk.Toplevel):
    """Column visibility filter dropdown."""

    def __init__(
        self,
        parent: tk.Toplevel,
        all_columns: List[str],
        visible: Set[str],
        populated: Set[str],
        on_apply: Any,
    ) -> None:
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=COLOR_BORDER)

        self._all_columns = all_columns
        self._on_apply = on_apply
        self._vars: Dict[str, tk.BooleanVar] = {}

        frame = ttk.Frame(self, padding=4)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Column Visibility", font=("TkDefaultFont", 9, "bold")).pack(
            anchor="w", pady=(0, 4),
        )

        canvas = tk.Canvas(frame, bg=COLOR_INPUT, width=220, height=300)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for col in all_columns:
            var = tk.BooleanVar(value=col in visible)
            self._vars[col] = var
            suffix = ""
            if col not in populated and col != "idx":
                suffix = " (empty)"
            cb = ttk.Checkbutton(inner, text=f"{col}{suffix}", variable=var)
            cb.pack(anchor="w", padx=4, pady=1)
            if col == "idx":
                cb.configure(state="disabled")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(4, 0))

        ttk.Button(btn_frame, text="Show Populated", command=self._show_populated).pack(
            side="left", padx=(0, 4),
        )
        ttk.Button(btn_frame, text="Show All", command=self._show_all).pack(
            side="left", padx=(0, 4),
        )
        ttk.Button(btn_frame, text="Apply", command=self._apply).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<FocusOut>", lambda e: self.after(150, self._check_focus))
        self.focus_set()

    def _show_populated(self) -> None:
        """Set checkboxes to show only populated columns."""
        for col, var in self._vars.items():
            if col == "idx":
                var.set(True)
            else:
                parent = self.master
                if isinstance(parent, FullTableViewDialog):
                    var.set(col in parent._populated_columns)
                else:
                    var.set(True)

    def _show_all(self) -> None:
        """Set all checkboxes to checked."""
        for var in self._vars.values():
            var.set(True)

    def _apply(self) -> None:
        """Apply column visibility changes."""
        visible = {col for col, var in self._vars.items() if var.get()}
        self._on_apply(visible)
        self.destroy()

    def _check_focus(self) -> None:
        """Check if focus is still within this dropdown."""
        try:
            focused = self.focus_get()
            if focused is None or not str(focused).startswith(str(self)):
                self.destroy()
        except tk.TclError:
            pass
