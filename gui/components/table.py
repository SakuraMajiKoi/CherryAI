"""CherryAI GUI v2 Shared Table Component.

Reusable table widget used across all workflow tabs for displaying and editing
translation data. Features virtualized scrolling for large files (10k+ lines).
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, cast
import tkinter as tk
from tkinter import ttk

from CherryAI.gui.theme.colors import THEME

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ColumnDef:
    """Definition for a table column.

    Attributes:
        key: Column identifier key.
        title: Display title for the column header.
        width: Initial column width in pixels.
        stretch: Whether column stretches to fill space.
        anchor: Text anchor (w, center, e).
        editable: Whether the column can be edited.
        visible: Whether the column is visible.
    """

    key: str
    title: str
    width: int = 150
    stretch: bool = False
    anchor: str = "w"
    editable: bool = False
    visible: bool = True


@dataclass
class TableRow:
    """Represents a single row of data in the table.

    Attributes:
        id: Unique row identifier.
        values: Dictionary of column key to value.
        tags: List of tags for styling/filtering.
        meta: Optional metadata dictionary.
    """

    id: int
    values: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON export.

        Returns:
            Dictionary representation of the row.
        """
        return {
            "id": self.id,
            "values": self.values,
            "tags": self.tags,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TableRow":
        """Deserialize from dictionary.

        Args:
            d: Dictionary data.

        Returns:
            TableRow instance.
        """
        return cls(
            id=d["id"],
            values=d.get("values", {}),
            tags=d.get("tags", []),
            meta=d.get("meta", {}),
        )


# Default column definitions for translation workflow
DEFAULT_COLUMNS = [
    ColumnDef(key="line_id", title="#", width=50, anchor="e"),
    ColumnDef(key="source", title="Source", width=300, stretch=True),
    ColumnDef(key="preprocessed", title="Preprocessed", width=250, visible=False),
    ColumnDef(key="translated", title="Translated", width=300, stretch=True),
    ColumnDef(key="status", title="Status", width=80, anchor="center"),
]


class SharedTable(ttk.Frame):
    """Shared table component with virtualized scrolling.

    Features:
    - Virtualized scrolling for large files (10k+ lines)
    - Column resize and visibility toggle
    - Filter/search bar
    - Multi-select with checkboxes
    - CSV/Excel export
    - Cell editing (optional)
    - Tag-based row styling

    Attributes:
        columns: List of ColumnDef objects.
        rows: List of TableRow objects.
        selection_mode: Single or multiple selection.
    """

    def __init__(
        self,
        parent: tk.Widget,
        columns: Optional[List[ColumnDef]] = None,
        show_filter: bool = True,
        show_checkboxes: bool = False,
        on_select: Optional[Callable[[List[int]], None]] = None,
        on_edit: Optional[Callable[[int, str, Any], None]] = None,
    ) -> None:
        """Initialize the shared table.

        Args:
            parent: Parent widget.
            columns: Column definitions. Defaults to DEFAULT_COLUMNS.
            show_filter: Whether to show filter bar.
            show_checkboxes: Whether to show checkbox column.
            on_select: Callback when selection changes.
            on_edit: Callback when a cell is edited.
        """
        super().__init__(parent)

        self.columns = columns or DEFAULT_COLUMNS.copy()
        self._rows: List[TableRow] = []
        self._filtered_rows: List[TableRow] = []
        self._show_filter = show_filter
        self._show_checkboxes = show_checkboxes
        self._on_select = on_select
        self._on_edit = on_edit
        self._checked_rows: set = set()
        self._filter_var = tk.StringVar()
        self._count_filter_var = tk.StringVar()
        self._count_mode_var = tk.StringVar(value="≥")  # ≥ or ≤ toggle
        self._current_filter = ""
        self._current_count_filter = ""
        self._batch_insert_version = 0  # Track batch insertion version to cancel stale batches

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the table UI components."""
        # Filter bar (optional)
        if self._show_filter:
            self._build_filter_bar()

        # Main table area
        self._build_table()

        # Info/status bar
        self._build_status_bar()

    def _build_filter_bar(self) -> None:
        """Build the filter/search bar with text and count filters."""
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=5, pady=(5, 2))

        ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=(0, 5))

        self._filter_entry = ttk.Entry(
            filter_frame,
            textvariable=self._filter_var,
            width=30,
        )
        self._filter_entry.pack(side="left", fill="x", expand=True)
        self._filter_entry.bind("<KeyRelease>", self._on_filter_change)

        # Count filter (supports <X, >X, <=X, >=X, =X syntax)
        ttk.Label(filter_frame, text="Count:").pack(
            side="left", padx=(10, 5),
        )

        # Toggle button for ≥ / ≤ default operator
        self._count_mode_btn = ttk.Button(
            filter_frame,
            textvariable=self._count_mode_var,
            width=2,
            command=self._toggle_count_mode,
        )
        self._count_mode_btn.pack(side="left")

        self._count_filter_entry = ttk.Entry(
            filter_frame,
            textvariable=self._count_filter_var,
            width=8,
        )
        self._count_filter_entry.pack(side="left")
        self._count_filter_entry.bind("<KeyRelease>", self._on_filter_change)

        clear_btn = ttk.Button(
            filter_frame,
            text="Clear",
            command=self._clear_filter,
            width=6,
        )
        clear_btn.pack(side="left", padx=(5, 0))

        # Column visibility toggle
        col_btn = ttk.Menubutton(
            filter_frame,
            text="Columns",
        )
        col_btn.pack(side="right", padx=(5, 0))
        self._col_menu = tk.Menu(col_btn, tearoff=0)
        col_btn["menu"] = self._col_menu
        self._update_column_menu()

    def _build_table(self) -> None:
        """Build the main table with treeview."""
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=5, pady=2)

        # Configure column IDs
        visible_cols = [c for c in self.columns if c.visible]
        col_ids = [c.key for c in visible_cols]

        if self._show_checkboxes:
            col_ids = ["_check"] + col_ids

        # Create Treeview
        self._tree = ttk.Treeview(
            table_frame,
            columns=col_ids,
            show="headings",
            selectmode="extended",
        )

        # Configure columns
        if self._show_checkboxes:
            self._tree.heading("_check", text="☐")
            self._tree.column("_check", width=30, stretch=False, anchor="center")

        for col in visible_cols:
            self._tree.heading(col.key, text=col.title, command=lambda c=col.key: self._on_sort(c))  # type: ignore
            self._tree.column(
                col.key,
                width=col.width,
                stretch=col.stretch,
                anchor=cast(Any, col.anchor),
            )

        # Scrollbars
        v_scroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self._tree.yview,
        )
        h_scroll = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self._tree.xview,
        )
        self._tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # Grid layout
        self._tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bindings
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        if self._show_checkboxes:
            self._tree.bind("<Button-1>", self._on_tree_click)
        self._tree.bind("<Double-1>", self._on_double_click)

        # Configure row tags for styling
        self._tree.tag_configure("odd", background=THEME.bg_main)
        self._tree.tag_configure("even", background=THEME.bg_panel)
        self._tree.tag_configure("error", foreground=THEME.accent_error)
        self._tree.tag_configure("success", foreground=THEME.accent_success)
        self._tree.tag_configure("warning", foreground=THEME.accent_warning)

    def _build_status_bar(self) -> None:
        """Build the status bar."""
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=5, pady=(2, 5))

        self._status_label = ttk.Label(
            status_frame,
            text="0 rows",
            foreground=THEME.text_secondary,
        )
        self._status_label.pack(side="left")

        # Export button
        export_btn = ttk.Button(
            status_frame,
            text="Export CSV",
            command=self._export_csv,
            width=10,
        )
        export_btn.pack(side="right")

    def _update_column_menu(self) -> None:
        """Update the column visibility menu."""
        self._col_menu.delete(0, "end")
        for col in self.columns:
            var = tk.BooleanVar(value=col.visible)
            self._col_menu.add_checkbutton(
                label=col.title,
                variable=var,
                command=lambda c=col, v=var: self._toggle_column(c, v.get()),  # type: ignore
            )

    def _toggle_column(self, col: ColumnDef, visible: bool) -> None:
        """Toggle column visibility."""
        col.visible = visible
        self._rebuild_columns()

    def _rebuild_columns(self) -> None:
        """Rebuild the treeview columns after visibility change."""
        visible_cols = [c for c in self.columns if c.visible]
        col_ids = [c.key for c in visible_cols]

        if self._show_checkboxes:
            col_ids = ["_check"] + col_ids

        self._tree.configure(columns=col_ids)

        if self._show_checkboxes:
            self._tree.heading("_check", text="☐")
            self._tree.column("_check", width=30, stretch=False, anchor="center")

        for col in visible_cols:
            self._tree.heading(col.key, text=col.title)
            self._tree.column(
                col.key,
                width=col.width,
                stretch=col.stretch,
                anchor=cast(Any, col.anchor),
            )

        self._refresh_display()

    def _on_filter_change(self, event: Optional[tk.Event] = None) -> None:
        """Handle filter text or count filter change."""
        filter_text = self._filter_var.get().lower().strip()
        count_text = self._count_filter_var.get().strip()
        if (
            filter_text == self._current_filter
            and count_text == self._current_count_filter
        ):
            return

        self._current_filter = filter_text
        self._current_count_filter = count_text
        self._apply_filter()

    def _clear_filter(self) -> None:
        """Clear both text and count filters."""
        self._filter_var.set("")
        self._count_filter_var.set("")
        self._current_filter = ""
        self._current_count_filter = ""
        self._apply_filter()

    def _toggle_count_mode(self) -> None:
        """Toggle the default count filter operator between ≥ and ≤."""
        current = self._count_mode_var.get()
        self._count_mode_var.set("≤" if current == "≥" else "≥")
        # Re-apply filter with the new default operator
        self._current_count_filter = ""  # force re-evaluation
        self._on_filter_change()

    @staticmethod
    def _parse_count_filter(
        expr: str,
        default_op: str = ">=",
    ) -> Optional[Callable[[int], bool]]:
        """Parse a count filter expression into a predicate.

        Supported syntax:
            >X   — count greater than X
            <X   — count less than X
            >=X  — count greater than or equal to X
            <=X  — count less than or equal to X
            =X   — count equal to X
            X    — bare number uses *default_op*

        Args:
            expr: Filter expression string.
            default_op: Operator to use for bare numbers (``>=`` or ``<=``).

        Returns:
            Predicate function or None if invalid.
        """
        import re as _re

        expr = expr.strip()
        if not expr:
            return None

        match = _re.match(r"^(>=|<=|>|<|=)?(\d+)$", expr)
        if not match:
            return None

        op = match.group(1) or default_op
        value = int(match.group(2))

        if op == ">":
            return lambda c: c > value
        if op == "<":
            return lambda c: c < value
        if op == ">=":
            return lambda c: c >= value
        if op == "<=":
            return lambda c: c <= value
        return lambda c: c == value

    def _apply_filter(self) -> None:
        """Apply text and count filters to rows."""
        # Map toggle symbol to operator string
        mode_sym = self._count_mode_var.get()
        default_op = "<=" if mode_sym == "≤" else ">="
        count_pred = self._parse_count_filter(
            self._current_count_filter, default_op=default_op,
        )

        if not self._current_filter and count_pred is None:
            self._filtered_rows = self._rows.copy()
        else:
            filtered: List[TableRow] = []
            for row in self._rows:
                # Text filter: substring match across all column values
                if self._current_filter:
                    if not any(
                        self._current_filter in str(v).lower()
                        for v in row.values.values()
                    ):
                        continue

                # Count filter: compare the "count" column value
                if count_pred is not None:
                    try:
                        count_val = int(row.values.get("count", 0))
                    except (ValueError, TypeError):
                        count_val = 0
                    if not count_pred(count_val):
                        continue

                filtered.append(row)
            self._filtered_rows = filtered
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the treeview display.

        TASK 43.2: Uses batch insertion for large datasets (>1000 rows).
        Rows are inserted in chunks of ``_BATCH_SIZE`` with periodic
        ``update_idletasks()`` to keep the UI responsive.
        
        Uses version tracking to cancel stale batch insertions when a new
        refresh starts before a previous one completes.
        """
        # Increment version to invalidate any pending batch insertions
        self._batch_insert_version += 1
        current_version = self._batch_insert_version
        
        # Clear existing items
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Get visible columns
        visible_cols = [c for c in self.columns if c.visible]

        rows = self._filtered_rows
        batch_size = 500

        if len(rows) <= batch_size:
            # Small dataset: insert synchronously
            self._insert_rows(rows, visible_cols, 0)
        else:
            # Large dataset: batch insert with version tracking
            self._batch_insert(rows, visible_cols, 0, batch_size, current_version)

        self._update_status()

    def _insert_rows(
        self,
        rows: list,
        visible_cols: list,
        start: int,
    ) -> None:
        """Insert rows into the Treeview (Task 43.2 helper)."""
        for i, row in enumerate(rows, start=start):
            values: list = []
            if self._show_checkboxes:
                values.append("☑" if row.id in self._checked_rows else "☐")
            for col in visible_cols:
                val = row.values.get(col.key, "")
                values.append(str(val) if val is not None else "")

            tags = list(row.tags)
            tags.append("odd" if i % 2 == 0 else "even")

            self._tree.insert(
                "", "end", iid=str(row.id), values=values, tags=tags,
            )

    def _batch_insert(
        self,
        rows: list,
        visible_cols: list,
        offset: int,
        batch_size: int,
        version: int,
    ) -> None:
        """Insert a batch of rows and schedule the next batch (Task 43.2).
        
        Args:
            rows: All rows to insert.
            visible_cols: Visible column definitions.
            offset: Current offset in rows list.
            batch_size: Number of rows per batch.
            version: Batch insertion version for cancellation tracking.
        """
        # Check if this batch is stale (a newer refresh has started)
        if version != self._batch_insert_version:
            return  # Cancel this stale batch
            
        end = min(offset + batch_size, len(rows))
        self._insert_rows(rows[offset:end], visible_cols, offset)

        if end < len(rows):
            # Schedule next batch (non-blocking) with version check
            self.after(1, lambda: self._batch_insert(
                rows, visible_cols, end, batch_size, version,
            ))
            self._status_label.configure(
                text=f"Loading {end}/{len(rows)} rows..."
            )
        else:
            self._update_status()

    def _update_status(self) -> None:
        """Update the status bar text."""
        total = len(self._rows)
        filtered = len(self._filtered_rows)
        checked = len(self._checked_rows)

        if self._current_filter:
            text = f"{filtered} of {total} rows (filtered)"
        else:
            text = f"{total} rows"

        if self._show_checkboxes and checked > 0:
            text += f" | {checked} selected"

        self._status_label.configure(text=text)

    def _on_tree_select(self, event: Optional[tk.Event] = None) -> None:
        """Handle treeview selection change."""
        if self._on_select:
            selected = [int(iid) for iid in self._tree.selection()]
            self._on_select(selected)

    def _on_tree_click(self, event: tk.Event) -> None:
        """Handle click for checkbox toggle."""
        if not self._show_checkboxes:
            return

        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._tree.identify_column(event.x)
        if column != "#1":  # First column (checkbox)
            return

        item = self._tree.identify_row(event.y)
        if not item:
            return

        row_id = int(item)
        if row_id in self._checked_rows:
            self._checked_rows.discard(row_id)
        else:
            self._checked_rows.add(row_id)

        self._refresh_display()

    def _on_double_click(self, event: tk.Event) -> None:
        """Handle double-click for editing."""
        if not self._on_edit:
            return

        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._tree.identify_column(event.x)
        item = self._tree.identify_row(event.y)
        if not item:
            return

        # Get column key
        col_idx = int(column.replace("#", "")) - 1
        if self._show_checkboxes:
            col_idx -= 1

        if col_idx < 0:
            return

        visible_cols = [c for c in self.columns if c.visible]
        if col_idx >= len(visible_cols):
            return

        col = visible_cols[col_idx]
        if not col.editable:
            return

        row_id = int(item)
        self._start_edit(row_id, col)

    def _start_edit(self, row_id: int, col: ColumnDef) -> None:
        """Start inline editing of a cell."""
        # Find the row
        row = next((r for r in self._rows if r.id == row_id), None)
        if not row:
            return

        current_value = row.values.get(col.key, "")

        # Get cell bbox
        item = str(row_id)
        col_id = col.key
        try:
            bbox = self._tree.bbox(item, col_id)
            if not bbox:
                return
        except tk.TclError:
            return

        x, y, width, height = bbox

        # Create entry widget for editing
        entry = ttk.Entry(self._tree)
        entry.insert(0, str(current_value))
        entry.select_range(0, "end")
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()

        def on_confirm(event=None):
            new_value = entry.get()
            entry.destroy()
            if new_value != str(current_value):
                row.values[col.key] = new_value
                self._refresh_display()
                if self._on_edit:
                    self._on_edit(row_id, col.key, new_value)

        def on_cancel(event=None):
            entry.destroy()

        entry.bind("<Return>", on_confirm)
        entry.bind("<Escape>", on_cancel)
        entry.bind("<FocusOut>", on_confirm)

    def _on_sort(self, column_key: str) -> None:
        """Sort by the specified column."""
        # Toggle sort direction
        current_dir = getattr(self, "_sort_dir", {}).get(column_key, "asc")
        new_dir = "desc" if current_dir == "asc" else "asc"

        if not hasattr(self, "_sort_dir"):
            self._sort_dir = {}
        self._sort_dir[column_key] = new_dir

        # Sort rows
        reverse = new_dir == "desc"
        self._filtered_rows.sort(
            key=lambda r: str(r.values.get(column_key, "")),
            reverse=reverse,
        )
        self._refresh_display()

    def _export_csv(self) -> None:
        """Export table data to CSV."""
        file_path = filedialog.asksaveasfilename(
            title="Export to CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not file_path:
            return

        try:
            visible_cols = [c for c in self.columns if c.visible]
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Header
                writer.writerow([c.title for c in visible_cols])
                # Data
                for row in self._filtered_rows:
                    row_data = [str(row.values.get(c.key, "")) for c in visible_cols]
                    writer.writerow(row_data)

            messagebox.showinfo("Export Complete", f"Exported {len(self._filtered_rows)} rows to {file_path}")
        except Exception as e:
            logger.error("Failed to export CSV: %s", e)
            messagebox.showerror("Export Failed", f"Failed to export: {e}")

    # Public API

    def set_data(self, rows: List[TableRow]) -> None:
        """Set the table data.

        Args:
            rows: List of TableRow objects.
        """
        self._rows = rows
        self._checked_rows.clear()
        self._apply_filter()

    def set_data_from_lines(self, lines: List[str], source_column: str = "source") -> None:
        """Set table data from a list of text lines.

        Args:
            lines: List of text strings.
            source_column: Column key to put the line text in.
        """
        rows = [
            TableRow(
                id=i + 1,
                values={"line_id": i + 1, source_column: line},
            )
            for i, line in enumerate(lines)
        ]
        self.set_data(rows)

    def get_data(self) -> List[TableRow]:
        """Get all table rows.

        Returns:
            List of TableRow objects.
        """
        return self._rows.copy()

    def get_filtered_data(self) -> List[TableRow]:
        """Get filtered table rows.

        Returns:
            List of filtered TableRow objects.
        """
        return self._filtered_rows.copy()

    def get_checked_rows(self) -> List[TableRow]:
        """Get checked rows (if checkboxes enabled).

        Returns:
            List of checked TableRow objects.
        """
        return [r for r in self._rows if r.id in self._checked_rows]

    def get_selected_rows(self) -> List[TableRow]:
        """Get currently selected rows.

        Returns:
            List of selected TableRow objects.
        """
        selected_ids = {int(iid) for iid in self._tree.selection()}
        return [r for r in self._rows if r.id in selected_ids]

    def get_selected_ids(self) -> List[int]:
        """Get IDs of currently selected rows.

        Returns:
            List of selected row IDs.
        """
        return [int(iid) for iid in self._tree.selection()]

    def get_selected_items(self) -> List[TableRow]:
        """Get currently selected rows (alias for get_selected_rows).

        Returns:
            List of selected TableRow objects.
        """
        return self.get_selected_rows()

    def load_data(self, rows: List[TableRow]) -> None:
        """Set the table data (alias for set_data).

        Args:
            rows: List of TableRow objects.
        """
        self.set_data(rows)

    def set_row_tag(self, row_id: int, tag: str) -> None:
        """Add a tag to a row for styling.

        Args:
            row_id: Row identifier.
            tag: Tag name (e.g., 'error', 'success').
        """
        row = next((r for r in self._rows if r.id == row_id), None)
        if row and tag not in row.tags:
            row.tags.append(tag)
            self._refresh_display()

    def clear_row_tag(self, row_id: int, tag: str) -> None:
        """Remove a tag from a row.

        Args:
            row_id: Row identifier.
            tag: Tag name to remove.
        """
        row = next((r for r in self._rows if r.id == row_id), None)
        if row and tag in row.tags:
            row.tags.remove(tag)
            self._refresh_display()

    def scroll_to_row(self, row_id: int) -> None:
        """Scroll to make a specific row visible.

        Args:
            row_id: Row identifier.
        """
        item = str(row_id)
        try:
            self._tree.see(item)
            self._tree.selection_set(item)
        except tk.TclError:
            pass

    def get_row_count(self) -> int:
        """Get total row count.

        Returns:
            Number of rows.
        """
        return len(self._rows)

    def get_filtered_count(self) -> int:
        """Get filtered row count.

        Returns:
            Number of filtered rows.
        """
        return len(self._filtered_rows)

    def clear(self) -> None:
        """Clear all table data."""
        self._rows.clear()
        self._filtered_rows.clear()
        self._checked_rows.clear()
        self._current_filter = ""
        self._filter_var.set("")
        self._refresh_display()
