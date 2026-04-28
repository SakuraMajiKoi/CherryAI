"""CherryAI GUI - Ledger View Dialog.

Non-modal analytics window backed entirely by shared helpers in
``functions/usage_tracker.py``. The dialog is display-only: all filtering,
grouping, and summary calculations remain in shared functions code.
"""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from CherryAI.functions.usage_tracker import (
    query_usage,
    summarize_usage_totals,
    usage_summary,
)
from CherryAI.gui.theme.colors import apply_theme, apply_window_preferences, get_theme


GROUPING_OPTIONS = {
    "By Day": "day",
    "By Project": "project_name",
    "By Task": "task_type",
    "By Provider": "provider",
    "By Model": "model",
    "By Project then Day": "project_day",
    "Ungrouped Requests": "request",
}

DATE_PRESET_OPTIONS = ("All Time", "Today", "7 Days", "30 Days", "This Month")

TREE_COLUMNS = (
    "group_label",
    "project_name",
    "task_type",
    "provider",
    "model",
    "status",
    "request_count",
    "input_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "output_tokens",
    "total_tokens",
    "total_cost",
)

TREE_HEADERS = {
    "group_label": "Group",
    "project_name": "Project",
    "task_type": "Task",
    "provider": "Provider",
    "model": "Model",
    "status": "Status",
    "request_count": "Requests",
    "input_tokens": "Input",
    "cached_input_tokens": "Cached",
    "reasoning_tokens": "Reasoning",
    "output_tokens": "Output",
    "total_tokens": "Total Tokens",
    "total_cost": "Total Cost",
}

TREE_WIDTHS = {
    "group_label": 220,
    "project_name": 140,
    "task_type": 110,
    "provider": 110,
    "model": 150,
    "status": 90,
    "request_count": 80,
    "input_tokens": 90,
    "cached_input_tokens": 90,
    "reasoning_tokens": 90,
    "output_tokens": 90,
    "total_tokens": 105,
    "total_cost": 95,
}


def _fmt_int(value: Any) -> str:
    number = int(value or 0)
    return f"{number:,}" if number else "0"


def _fmt_cost(value: Any, unknown_count: Any = 0) -> str:
    numeric = float(value or 0.0)
    unknown_total = int(unknown_count or 0)
    if unknown_total > 0:
        if numeric > 0.0:
            return f"${numeric:.2f} + Unknown"
        return "Unknown"
    return f"${numeric:.2f}"


def _fmt_percent(value: Any) -> str:
    return f"{float(value or 0.0):.1f}%"


class LedgerViewDialog(tk.Toplevel):
    """Reusable non-modal Ledger analytics window."""

    _ROOT_ATTR = "_ledger_dialog"

    @classmethod
    def open_or_focus(cls, parent: tk.Misc) -> "LedgerViewDialog":
        root = parent.winfo_toplevel()
        existing = getattr(root, cls._ROOT_ATTR, None)
        if isinstance(existing, cls):
            try:
                if existing.winfo_exists():
                    existing._present()
                    existing.refresh()
                    return existing
            except tk.TclError:
                pass

        dialog = cls(root)
        dialog._instance_owner = root
        setattr(root, cls._ROOT_ATTR, dialog)
        dialog._present()
        return dialog

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._instance_owner: Optional[tk.Misc] = None
        self._parent = parent
        self._row_lookup: Dict[str, Dict[str, Any]] = {}
        self._sort_column = "total_cost"
        self._sort_descending = True

        self.title("Ledger")
        self.minsize(1080, 620)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        apply_window_preferences(
            self,
            parent=parent,
            window_key="LedgerViewDialog",
            default_geometry="1280x760",
        )

        self._build_toolbar()
        self._build_summary_band()
        self._build_table()
        self._build_status_bar()
        self.refresh_theme()
        self.refresh()

    def _present(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _clear_root_reference(self) -> None:
        owner = self._instance_owner
        if owner is None:
            return
        if getattr(owner, self._ROOT_ATTR, None) is self:
            setattr(owner, self._ROOT_ATTR, None)
        self._instance_owner = None

    def refresh_theme(self) -> None:
        apply_theme(self, theme=get_theme())

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.pack(fill="x")

        self._project_var = tk.StringVar(value="All")
        self._task_var = tk.StringVar(value="All")
        self._provider_var = tk.StringVar(value="All")
        self._model_var = tk.StringVar(value="All")
        self._status_var = tk.StringVar(value="All")
        self._grouping_var = tk.StringVar(value="By Project")
        self._date_preset_var = tk.StringVar(value="All Time")
        self._start_date_var = tk.StringVar(value="")
        self._end_date_var = tk.StringVar(value="")

        ttk.Label(toolbar, text="Project:").pack(side="left")
        self._project_combo = ttk.Combobox(
            toolbar,
            textvariable=self._project_var,
            state="readonly",
            width=18,
        )
        self._project_combo.pack(side="left", padx=(4, 8))

        ttk.Label(toolbar, text="Task:").pack(side="left")
        self._task_combo = ttk.Combobox(
            toolbar,
            textvariable=self._task_var,
            state="readonly",
            width=14,
        )
        self._task_combo.pack(side="left", padx=(4, 8))

        ttk.Label(toolbar, text="Provider:").pack(side="left")
        self._provider_combo = ttk.Combobox(
            toolbar,
            textvariable=self._provider_var,
            state="readonly",
            width=12,
        )
        self._provider_combo.pack(side="left", padx=(4, 8))

        ttk.Label(toolbar, text="Model:").pack(side="left")
        self._model_combo = ttk.Combobox(
            toolbar,
            textvariable=self._model_var,
            state="readonly",
            width=16,
        )
        self._model_combo.pack(side="left", padx=(4, 8))

        ttk.Label(toolbar, text="Status:").pack(side="left")
        self._status_combo = ttk.Combobox(
            toolbar,
            textvariable=self._status_var,
            state="readonly",
            width=12,
            values=("All", "success", "recovered", "failed"),
        )
        self._status_combo.pack(side="left", padx=(4, 8))

        row2 = ttk.Frame(self, padding=(10, 0, 10, 8))
        row2.pack(fill="x")

        ttk.Label(row2, text="Group:").pack(side="left")
        self._grouping_combo = ttk.Combobox(
            row2,
            textvariable=self._grouping_var,
            state="readonly",
            width=18,
            values=tuple(GROUPING_OPTIONS.keys()),
        )
        self._grouping_combo.pack(side="left", padx=(4, 8))

        ttk.Label(row2, text="Date Preset:").pack(side="left")
        self._date_preset_combo = ttk.Combobox(
            row2,
            textvariable=self._date_preset_var,
            state="readonly",
            width=12,
            values=DATE_PRESET_OPTIONS,
        )
        self._date_preset_combo.pack(side="left", padx=(4, 8))

        ttk.Label(row2, text="Start:").pack(side="left")
        self._start_entry = ttk.Entry(row2, textvariable=self._start_date_var, width=12)
        self._start_entry.pack(side="left", padx=(4, 8))

        ttk.Label(row2, text="End:").pack(side="left")
        self._end_entry = ttk.Entry(row2, textvariable=self._end_date_var, width=12)
        self._end_entry.pack(side="left", padx=(4, 12))

        ttk.Button(row2, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(row2, text="Show Matching Requests", command=self._show_matching_requests).pack(
            side="right"
        )

        for widget in (
            self._project_combo,
            self._task_combo,
            self._provider_combo,
            self._model_combo,
            self._status_combo,
            self._grouping_combo,
            self._date_preset_combo,
        ):
            widget.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        self._start_entry.bind("<Return>", lambda _event: self.refresh())
        self._end_entry.bind("<Return>", lambda _event: self.refresh())

    def _build_summary_band(self) -> None:
        summary = ttk.Frame(self, padding=(10, 0, 10, 8))
        summary.pack(fill="x")

        self._summary_labels: Dict[str, ttk.Label] = {}
        fields = (
            ("Total Cost", "total_cost"),
            ("Total Requests", "total_requests"),
            ("Total Tokens", "total_tokens"),
            ("Cached Tokens", "cached_tokens"),
            ("Reasoning Tokens", "reasoning_tokens"),
            ("Success Rate", "success_rate"),
            ("Date Range", "date_range"),
        )
        for column, (title, key) in enumerate(fields):
            card = ttk.LabelFrame(summary, text=title)
            card.grid(row=0, column=column, padx=(0, 8), sticky="nsew")
            summary.columnconfigure(column, weight=1)
            label = ttk.Label(card, text="-", padding=(8, 6))
            label.pack(fill="both", expand=True)
            self._summary_labels[key] = label

    def _build_table(self) -> None:
        container = ttk.Frame(self, padding=(10, 0, 10, 8))
        container.pack(fill="both", expand=True)

        self._tree = ttk.Treeview(
            container,
            columns=TREE_COLUMNS,
            show="headings",
            selectmode="browse",
        )
        self._tree.pack(side="left", fill="both", expand=True)
        self._tree.bind("<Double-1>", lambda _event: self._show_matching_requests())

        yscroll = ttk.Scrollbar(container, orient="vertical", command=self._tree.yview)
        yscroll.pack(side="right", fill="y")
        xscroll = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        xscroll.pack(fill="x", padx=10, pady=(0, 8))
        self._tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        for column in TREE_COLUMNS:
            self._tree.heading(
                column,
                text=TREE_HEADERS[column],
                command=lambda key=column: self._sort_by_column(key),
            )
            anchor = "w" if column in {"group_label", "project_name", "task_type", "provider", "model", "status"} else "e"
            self._tree.column(column, width=TREE_WIDTHS[column], minwidth=60, anchor=anchor)

    def _build_status_bar(self) -> None:
        frame = ttk.Frame(self, padding=(10, 0, 10, 8))
        frame.pack(fill="x")
        self._status_label = ttk.Label(frame, text="0 rows")
        self._status_label.pack(side="left")

    def _selected_filter(self, value: str) -> Optional[str]:
        text = (value or "").strip()
        return None if not text or text == "All" else text

    def _collect_filters(self) -> Dict[str, Any]:
        return {
            "project_name": self._selected_filter(self._project_var.get()),
            "task_type": self._selected_filter(self._task_var.get()),
            "provider": self._selected_filter(self._provider_var.get()),
            "model": self._selected_filter(self._model_var.get()),
            "status": self._selected_filter(self._status_var.get()),
            "date_preset": self._date_preset_var.get(),
            "since": self._start_date_var.get().strip() or None,
            "until": self._end_date_var.get().strip() or None,
        }

    def _update_filter_values(self, rows: List[Dict[str, Any]]) -> None:
        def unique_values(field: str) -> List[str]:
            values = sorted({_value for _value in (_row.get(field, "") for _row in rows) if _value})
            return ["All", *values]

        combos = (
            (self._project_combo, self._project_var, unique_values("project_name")),
            (self._task_combo, self._task_var, unique_values("task_type")),
            (self._provider_combo, self._provider_var, unique_values("provider")),
            (self._model_combo, self._model_var, unique_values("model")),
        )
        for combo, variable, values in combos:
            current = variable.get() or "All"
            combo.configure(values=values)
            if current not in values:
                variable.set("All")

    def _update_summary(self, totals: Dict[str, Any]) -> None:
        self._summary_labels["total_cost"].configure(
            text=_fmt_cost(
                totals["total_cost"],
                totals.get("unknown_pricing_count", 0),
            )
        )
        self._summary_labels["total_requests"].configure(text=_fmt_int(totals["total_requests"]))
        self._summary_labels["total_tokens"].configure(text=_fmt_int(totals["total_tokens"]))
        self._summary_labels["cached_tokens"].configure(text=_fmt_int(totals["cached_tokens"]))
        self._summary_labels["reasoning_tokens"].configure(text=_fmt_int(totals["reasoning_tokens"]))
        self._summary_labels["success_rate"].configure(text=_fmt_percent(totals["success_rate"]))

        start_ts = totals.get("start_timestamp")
        end_ts = totals.get("end_timestamp")
        if start_ts and end_ts:
            start_text = dt.datetime.fromtimestamp(float(start_ts)).strftime("%Y-%m-%d")
            end_text = dt.datetime.fromtimestamp(float(end_ts)).strftime("%Y-%m-%d")
            date_range = f"{start_text} to {end_text}" if start_text != end_text else start_text
        else:
            date_range = "-"
        self._summary_labels["date_range"].configure(text=date_range)

    def _sort_key(self, row: Dict[str, Any], column: str) -> Any:
        if column in {
            "request_count",
            "input_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
            "output_tokens",
            "total_tokens",
        }:
            return int(row.get(column, 0))
        if column == "total_cost":
            return float(row.get(column, 0.0))
        return str(row.get(column, "")).lower()

    def _render_rows(self, rows: List[Dict[str, Any]]) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._row_lookup.clear()

        ordered_rows = sorted(
            rows,
            key=lambda row: self._sort_key(row, self._sort_column),
            reverse=self._sort_descending,
        )
        for index, row in enumerate(ordered_rows):
            iid = f"row-{index}"
            values = (
                row.get("group_label", ""),
                row.get("project_name", ""),
                row.get("task_type", ""),
                row.get("provider", ""),
                row.get("model", ""),
                row.get("status", ""),
                _fmt_int(row.get("request_count", 0)),
                _fmt_int(row.get("input_tokens", 0)),
                _fmt_int(row.get("cached_input_tokens", 0)),
                _fmt_int(row.get("reasoning_tokens", 0)),
                _fmt_int(row.get("output_tokens", 0)),
                _fmt_int(row.get("total_tokens", 0)),
                _fmt_cost(
                    row.get("total_cost", 0.0),
                    row.get("unknown_pricing_count", 0),
                ),
            )
            self._tree.insert("", "end", iid=iid, values=values)
            self._row_lookup[iid] = row

        self._status_label.configure(text=f"{len(ordered_rows)} rows")

    def _sort_by_column(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = column in {
                "request_count",
                "input_tokens",
                "cached_input_tokens",
                "reasoning_tokens",
                "output_tokens",
                "total_tokens",
                "total_cost",
            }
        self.refresh()

    def _selected_row(self) -> Optional[Dict[str, Any]]:
        selection = self._tree.selection()
        if not selection:
            return None
        return self._row_lookup.get(selection[0])

    def _show_matching_requests(self) -> None:
        row = self._selected_row()
        if row is None:
            messagebox.showinfo("Ledger", "Select a row first.", parent=self)
            return

        request_refs = list(row.get("request_refs") or [])
        if not request_refs:
            messagebox.showinfo(
                "Ledger",
                "The selected row has no request references to open in API Log.",
                parent=self,
            )
            return

        opener = getattr(self._parent, "open_api_log_dialog", None)
        if callable(opener):
            opener(request_refs=request_refs)
            return

        messagebox.showinfo(
            "Ledger",
            "API Log drill-down is only available when the main app exposes the shared API Log window.",
            parent=self,
        )

    def refresh(self) -> None:
        all_rows = query_usage(limit=100_000)
        self._update_filter_values(all_rows)
        filters = self._collect_filters()
        grouping = GROUPING_OPTIONS.get(self._grouping_var.get(), "project_name")
        grouped_rows = usage_summary(group_by=grouping, **filters)
        totals = summarize_usage_totals(**filters)
        self._update_summary(totals)
        self._render_rows(grouped_rows)

    def _on_close(self) -> None:
        self.destroy()

    def destroy(self) -> None:
        self._clear_root_reference()
        try:
            super().destroy()
        except tk.TclError:
            pass