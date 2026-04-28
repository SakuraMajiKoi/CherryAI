"""CherryAI GUI - RegEx Maker help window.

This dialog is a thin tkinter layer over the shared backend in
``CherryAI.functions.regex_maker``.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Dict, List, Optional

from CherryAI.functions import ini_manager
from CherryAI.functions.regex_maker import (
    MODE_SEARCH_ONLY,
    MODE_SEARCH_REPLACE,
    ROW_KIND_REPLACE,
    ROW_KIND_SEARCH,
    RegexCandidate,
    RegexExampleRow,
    RegexExampleSet,
    RegexGenerationResult,
    RegexMakerOptions,
    SpanAnnotation,
    generate_regex_suggestions,
)
from CherryAI.gui.helpers.tooltip import attach_tooltip
from CherryAI.gui.theme.colors import apply_theme, apply_window_preferences, get_theme

logger = logging.getLogger(__name__)

_OPTION_DEFAULTS_KEY = "regex_maker_option_defaults"
_MODE_LABELS = {
    MODE_SEARCH_ONLY: "Search only",
    MODE_SEARCH_REPLACE: "Search + Replace",
}
_MODE_VALUES = {value: key for key, value in _MODE_LABELS.items()}
_ANNOTATION_STYLES = {
    "constant": {"background": "#DDF1D7", "label": "Constant across examples"},
    "literal": {"background": "#D7F0EF", "label": "Must match literally"},
    "must_literal": {"background": "#D7F0EF", "label": "Must match literally"},
    "variable": {"background": "#DCEBFF", "label": "Variable span"},
    "variable_any": {"background": "#DCEBFF", "label": "Variable span"},
    "variable_number": {"background": "#D8E8FF", "label": "Variable number"},
    "variable_word": {"background": "#D7E8FF", "label": "Variable word"},
    "variable_japanese": {"background": "#E4DEFF", "label": "Variable Japanese span"},
    "capture": {"background": "#FFE7BF", "label": "Capture group candidate"},
    "capture_group": {"background": "#FFE7BF", "label": "Capture group"},
    "ignore": {"background": "#E5E7EB", "label": "Ignored span"},
    "optional": {"background": "#F2E1FF", "label": "Optional span"},
    "prefer_digits": {"background": "#E6F0FF", "label": "Prefer digits here"},
    "prefer_word": {"background": "#E3EEFF", "label": "Prefer word characters here"},
    "preserve_punctuation": {"background": "#D9F4F1", "label": "Preserve punctuation here"},
}


@dataclass
class _ExampleRowWidgets:
    row_kind: str
    index: int
    frame: ttk.Frame
    label: ttk.Label
    text_widget: tk.Text
    paste_button: ttk.Button
    remove_button: ttk.Button
    enabled_var: Optional[tk.BooleanVar] = None
    enabled_check: Optional[ttk.Checkbutton] = None


def _options_to_dict(options: RegexMakerOptions) -> Dict[str, object]:
    return {
        "match_whole_line": bool(options.match_whole_line),
        "ignore_spaces": bool(options.ignore_spaces),
        "ignore_leading_spaces": bool(options.ignore_leading_spaces),
        "ignore_trailing_spaces": bool(options.ignore_trailing_spaces),
        "case_sensitive": bool(options.case_sensitive),
        "prefer_simple": bool(options.prefer_simple),
        "prefer_strict": bool(options.prefer_strict),
        "allow_wildcard_fallback": bool(options.allow_wildcard_fallback),
        "disallow_lookaround": bool(options.disallow_lookaround),
        "disallow_backreferences": bool(options.disallow_backreferences),
        "require_replace_suggestion": bool(options.require_replace_suggestion),
        "max_candidates": max(1, min(20, int(options.max_candidates))),
    }


def _options_from_dict(data: Dict[str, object]) -> RegexMakerOptions:
    return RegexMakerOptions(
        match_whole_line=bool(data.get("match_whole_line", True)),
        ignore_spaces=bool(data.get("ignore_spaces", False)),
        ignore_leading_spaces=bool(data.get("ignore_leading_spaces", False)),
        ignore_trailing_spaces=bool(data.get("ignore_trailing_spaces", False)),
        case_sensitive=bool(data.get("case_sensitive", False)),
        prefer_simple=bool(data.get("prefer_simple", True)),
        prefer_strict=bool(data.get("prefer_strict", False)),
        allow_wildcard_fallback=bool(data.get("allow_wildcard_fallback", True)),
        disallow_lookaround=bool(data.get("disallow_lookaround", True)),
        disallow_backreferences=bool(data.get("disallow_backreferences", True)),
        require_replace_suggestion=bool(data.get("require_replace_suggestion", False)),
        max_candidates=max(1, min(20, int(data.get("max_candidates", 5) or 5))),
    )


def load_regex_maker_option_defaults() -> RegexMakerOptions:
    """Load persisted RegEx Maker defaults from ``CherryAI.ini``."""

    raw = str(ini_manager.get_ui_setting(_OPTION_DEFAULTS_KEY, "") or "").strip()
    if not raw:
        return RegexMakerOptions()
    try:
        payload = json.loads(raw)
    except Exception:
        logger.debug("Failed to decode RegEx Maker defaults", exc_info=True)
        return RegexMakerOptions()
    if not isinstance(payload, dict):
        return RegexMakerOptions()
    return _options_from_dict(payload)


def save_regex_maker_option_defaults(options: RegexMakerOptions) -> bool:
    """Persist RegEx Maker defaults into ``CherryAI.ini``."""

    payload = json.dumps(_options_to_dict(options), ensure_ascii=False)
    return ini_manager.set_ui_setting(_OPTION_DEFAULTS_KEY, payload)


class RegexHelpDialog(tk.Toplevel):
    """Non-modal helper that suggests regex search and replace candidates."""

    _ROOT_ATTR = "_regex_help_dialog"

    @classmethod
    def open_or_focus(cls, parent: tk.Misc) -> "RegexHelpDialog":
        root = parent.winfo_toplevel()
        existing = getattr(root, cls._ROOT_ATTR, None)
        if isinstance(existing, cls):
            try:
                if existing.winfo_exists():
                    existing._present()
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
        self._parent = parent
        self._instance_owner: Optional[tk.Misc] = None
        self._search_rows: List[_ExampleRowWidgets] = []
        self._replace_rows: List[_ExampleRowWidgets] = []
        self._annotation_state: Dict[str, Dict[str, Any]] = {}
        self._annotation_counter = 0
        self._annotation_tooltip: Optional[tk.Toplevel] = None
        self._refresh_job: Optional[str] = None
        self._candidate_lookup: Dict[str, RegexCandidate] = {}
        self._result: Optional[RegexGenerationResult] = None
        self._options_dialog: Optional[RegexOptionsDialog] = None
        self._options_state = load_regex_maker_option_defaults()

        self.title("RegEx Maker")
        self.minsize(980, 720)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        apply_window_preferences(
            self,
            parent=parent,
            window_key="RegexHelpDialog",
            default_geometry="1180x860",
        )

        self._build_shell()
        self.refresh_theme()
        self._add_search_row()
        self._sync_replace_rows()
        self._set_mode(MODE_SEARCH_ONLY)
        self._schedule_refresh(immediate=True)

    def _present(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            logger.debug("RegEx Maker dialog could not be presented", exc_info=True)

    def _clear_root_reference(self) -> None:
        owner = self._instance_owner
        if owner is None:
            return
        if getattr(owner, self._ROOT_ATTR, None) is self:
            setattr(owner, self._ROOT_ATTR, None)
        self._instance_owner = None

    def destroy(self) -> None:
        self._clear_root_reference()
        self._hide_annotation_tooltip()
        if self._options_dialog is not None:
            try:
                self._options_dialog.destroy()
            except tk.TclError:
                pass
            self._options_dialog = None
        try:
            super().destroy()
        except tk.TclError:
            pass

    def refresh_theme(self) -> None:
        theme = get_theme()
        apply_theme(self, theme=theme)
        for row in [*self._search_rows, *self._replace_rows]:
            row.text_widget.configure(
                bg=theme.bg_input,
                fg=theme.text_primary,
                insertbackground=theme.text_primary,
                selectbackground=theme.bg_selected,
                selectforeground=theme.text_primary,
            )
            self._reapply_widget_annotations(row.text_widget)

        for widget in (self._search_output, self._replace_output, self._why_text):
            widget.configure(
                bg=theme.bg_input,
                fg=theme.text_primary,
                insertbackground=theme.text_primary,
                selectbackground=theme.bg_selected,
                selectforeground=theme.text_primary,
            )

    def _build_shell(self) -> None:
        self._build_top_controls()

        body = ttk.PanedWindow(self, orient="vertical")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        example_band = ttk.Frame(body)
        output_band = ttk.Frame(body)
        body.add(example_band, weight=3)
        body.add(output_band, weight=2)

        instruction = ttk.Label(
            example_band,
            text="Highlight a span inside any example, then right-click to mark constants, variables, captures, or optional text.",
            wraplength=900,
            justify="left",
        )
        instruction.pack(fill="x", pady=(0, 8))

        groups = ttk.Frame(example_band)
        groups.pack(fill="both", expand=True)

        self._search_group = ttk.LabelFrame(groups, text="Line to find")
        self._search_group.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._search_rows_frame = ttk.Frame(self._search_group)
        self._search_rows_frame.pack(fill="both", expand=True, padx=6, pady=(6, 4))
        ttk.Button(
            self._search_group,
            text="Add Line",
            command=self._add_search_row,
        ).pack(anchor="w", padx=6, pady=(0, 6))

        self._replace_group = ttk.LabelFrame(groups, text="Replace Target")
        self._replace_group.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self._replace_rows_frame = ttk.Frame(self._replace_group)
        self._replace_rows_frame.pack(fill="both", expand=True, padx=6, pady=(6, 4))
        ttk.Label(
            self._replace_group,
            text="These rows stay index-aligned with the search examples.",
            wraplength=380,
            justify="left",
        ).pack(anchor="w", padx=6, pady=(0, 6))

        self._build_output_area(output_band)

        status_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        status_frame.pack(fill="x")
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self._status_var).pack(side="left")

    def _build_top_controls(self) -> None:
        toolbar = ttk.Frame(self, padding=(10, 10, 10, 8))
        toolbar.pack(fill="x")

        self._mode_var = tk.StringVar(value=_MODE_LABELS[MODE_SEARCH_ONLY])
        ttk.Label(toolbar, text="Mode:").grid(row=0, column=0, sticky="w")
        self._mode_combo = ttk.Combobox(
            toolbar,
            textvariable=self._mode_var,
            values=tuple(_MODE_LABELS.values()),
            state="readonly",
            width=16,
        )
        self._mode_combo.grid(row=0, column=1, sticky="w", padx=(4, 12))
        self._mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_mode_changed())

        self._compatibility_var = tk.StringVar(value="CherryAI (re, ignore-case search)")
        ttk.Label(toolbar, text="Compatibility:").grid(row=0, column=2, sticky="w")
        self._compatibility_combo = ttk.Combobox(
            toolbar,
            textvariable=self._compatibility_var,
            values=("CherryAI (re, ignore-case search)",),
            state="readonly",
            width=32,
        )
        self._compatibility_combo.grid(row=0, column=3, sticky="w", padx=(4, 12))

        self._realtime_var = tk.BooleanVar(value=True)
        self._realtime_check = ttk.Checkbutton(
            toolbar,
            text="Realtime",
            variable=self._realtime_var,
            command=self._on_realtime_toggled,
        )
        self._realtime_check.grid(row=0, column=4, sticky="w", padx=(0, 12))
        ttk.Button(toolbar, text="Options", command=self._open_options_dialog).grid(
            row=0,
            column=5,
            sticky="w",
            padx=(0, 8),
        )
        ttk.Button(toolbar, text="Refresh", command=lambda: self._schedule_refresh(immediate=True)).grid(
            row=0,
            column=6,
            sticky="w",
        )

        self._notes_var = tk.StringVar()
        ttk.Label(toolbar, text="Notes:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._notes_entry = ttk.Entry(toolbar, textvariable=self._notes_var)
        self._notes_entry.grid(row=1, column=1, columnspan=6, sticky="ew", pady=(8, 0))
        toolbar.columnconfigure(3, weight=1)
        toolbar.columnconfigure(6, weight=1)
        toolbar.columnconfigure(1, weight=1)

        self._notes_var.trace_add("write", lambda *_args: self._on_inputs_changed())

        attach_tooltip(self._mode_combo, "Switch between search-only suggestions and paired search/replace inference.")
        attach_tooltip(
            self._compatibility_combo,
            "CherryAI-compatible output uses Python's stdlib re with ignore-case search by default.",
        )
        attach_tooltip(self._realtime_check, "Rebuild candidates automatically after a short debounce.")
        attach_tooltip(self._notes_entry, "Advanced fallback commands like 'whole line', 'capture number', or 'no wildcard'.")

    def _build_output_area(self, parent: ttk.Frame) -> None:
        top_outputs = ttk.Frame(parent)
        top_outputs.pack(fill="x", pady=(0, 8))

        search_frame = ttk.LabelFrame(top_outputs, text="RegEx Search")
        search_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ttk.Button(search_frame, text="Copy", command=lambda: self._copy_widget_text(self._search_output)).pack(
            anchor="e", padx=6, pady=(6, 0)
        )
        self._search_output = tk.Text(search_frame, height=3, wrap="word")
        self._search_output.pack(fill="both", expand=True, padx=6, pady=(4, 6))

        replace_frame = ttk.LabelFrame(top_outputs, text="RegEx Replace")
        replace_frame.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ttk.Button(replace_frame, text="Copy", command=lambda: self._copy_widget_text(self._replace_output)).pack(
            anchor="e", padx=6, pady=(6, 0)
        )
        self._replace_output = tk.Text(replace_frame, height=3, wrap="word")
        self._replace_output.pack(fill="both", expand=True, padx=6, pady=(4, 6))

        lower = ttk.PanedWindow(parent, orient="horizontal")
        lower.pack(fill="both", expand=True)

        candidates_frame = ttk.LabelFrame(lower, text="RegEx Candidates")
        lower.add(candidates_frame, weight=3)
        self._candidate_tree = ttk.Treeview(
            candidates_frame,
            columns=("rank", "family", "score", "pattern"),
            show="headings",
            selectmode="browse",
        )
        self._candidate_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        self._candidate_tree.heading("rank", text="#")
        self._candidate_tree.heading("family", text="Family")
        self._candidate_tree.heading("score", text="Score")
        self._candidate_tree.heading("pattern", text="Pattern")
        self._candidate_tree.column("rank", width=36, anchor="e")
        self._candidate_tree.column("family", width=150, anchor="w")
        self._candidate_tree.column("score", width=72, anchor="e")
        self._candidate_tree.column("pattern", width=520, anchor="w")
        self._candidate_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_candidate_selected())
        self._candidate_tree.bind("<Double-1>", lambda _event: self._copy_selected_candidate_search())
        tree_scrollbar = ttk.Scrollbar(candidates_frame, orient="vertical", command=self._candidate_tree.yview)
        tree_scrollbar.pack(
            side="right", fill="y", padx=(0, 6), pady=6
        )
        self._candidate_tree.configure(yscrollcommand=tree_scrollbar.set)

        why_frame = ttk.LabelFrame(lower, text="Why this is ranked here")
        lower.add(why_frame, weight=2)
        self._why_text = tk.Text(why_frame, height=12, wrap="word")
        self._why_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _set_mode(self, mode: str) -> None:
        self._mode_var.set(_MODE_LABELS.get(mode, _MODE_LABELS[MODE_SEARCH_ONLY]))
        self._toggle_replace_group()

    def _on_mode_changed(self) -> None:
        self._toggle_replace_group()
        self._on_inputs_changed()

    def _toggle_replace_group(self) -> None:
        mode = _MODE_VALUES.get(self._mode_var.get(), MODE_SEARCH_ONLY)
        self._sync_replace_rows()
        if mode == MODE_SEARCH_REPLACE:
            if not self._replace_group.winfo_manager():
                self._replace_group.pack(side="left", fill="both", expand=True, padx=(6, 0))
        else:
            if self._replace_group.winfo_manager():
                self._replace_group.pack_forget()

    def _add_search_row(self, initial_text: str = "") -> None:
        row = self._create_row(self._search_rows_frame, ROW_KIND_SEARCH, len(self._search_rows), initial_text)
        self._search_rows.append(row)
        self._sync_replace_rows()
        self._reindex_rows()
        self._on_inputs_changed()

    def _create_row(
        self,
        parent: ttk.Frame,
        row_kind: str,
        index: int,
        initial_text: str,
    ) -> _ExampleRowWidgets:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 8))

        header = ttk.Frame(frame)
        header.pack(fill="x")
        label = ttk.Label(header, text=self._row_label(row_kind, index))
        label.pack(side="left")

        enabled_var: Optional[tk.BooleanVar] = None
        enabled_check: Optional[ttk.Checkbutton] = None
        if row_kind == ROW_KIND_SEARCH:
            enabled_var = tk.BooleanVar(value=True)
            enabled_check = ttk.Checkbutton(
                header,
                text="Use",
                variable=enabled_var,
                command=self._on_inputs_changed,
            )
            enabled_check.pack(side="left", padx=(8, 8))

        paste_button = ttk.Button(header, text="Paste")
        paste_button.pack(side="right")
        remove_button = ttk.Button(header, text="Remove")
        remove_button.pack(side="right", padx=(0, 6))

        text_widget = tk.Text(frame, height=4, wrap="word", undo=True)
        text_widget.pack(fill="x", pady=(6, 0))
        if initial_text:
            text_widget.insert("1.0", initial_text)
        text_widget._regex_row_kind = row_kind  # type: ignore[attr-defined]
        text_widget._regex_row_index = index  # type: ignore[attr-defined]

        text_widget.bind("<KeyRelease>", lambda _event: self._on_inputs_changed())
        text_widget.bind("<<Paste>>", lambda _event: self.after_idle(self._on_inputs_changed))
        text_widget.bind("<Button-3>", self._show_context_menu)
        text_widget.bind("<Leave>", lambda _event: self._hide_annotation_tooltip())

        attach_tooltip(
            paste_button,
            "Replace this example with the current clipboard text.",
        )
        attach_tooltip(
            remove_button,
            "Delete this row and keep the paired replace row aligned.",
        )

        row = _ExampleRowWidgets(
            row_kind=row_kind,
            index=index,
            frame=frame,
            label=label,
            text_widget=text_widget,
            paste_button=paste_button,
            remove_button=remove_button,
            enabled_var=enabled_var,
            enabled_check=enabled_check,
        )
        paste_button.configure(command=lambda widget=text_widget: self._paste_into_widget(widget))
        return row

    def _sync_replace_rows(self) -> None:
        while len(self._replace_rows) < len(self._search_rows):
            row = self._create_row(self._replace_rows_frame, ROW_KIND_REPLACE, len(self._replace_rows), "")
            self._replace_rows.append(row)
        while len(self._replace_rows) > len(self._search_rows):
            row = self._replace_rows.pop()
            self._drop_row_annotations(row.row_kind, row.index)
            row.frame.destroy()
        self._reindex_rows()

    def _reindex_rows(self) -> None:
        total = len(self._search_rows)
        for rows in (self._search_rows, self._replace_rows):
            for index, row in enumerate(rows):
                row.index = index
                row.label.configure(text=self._row_label(row.row_kind, index))
                row.text_widget._regex_row_index = index  # type: ignore[attr-defined]
                row.paste_button.configure(command=lambda widget=row.text_widget: self._paste_into_widget(widget))
                row.remove_button.configure(
                    command=lambda idx=index: self._remove_search_row(idx),
                    state=tk.NORMAL if total > 1 else tk.DISABLED,
                )

    def _row_label(self, row_kind: str, index: int) -> str:
        prefix = "Find" if row_kind == ROW_KIND_SEARCH else "Replace"
        return f"{prefix} {index + 1}"

    def _remove_search_row(self, index: int) -> None:
        if len(self._search_rows) <= 1:
            return

        search_row = self._search_rows.pop(index)
        replace_row = self._replace_rows.pop(index)
        self._drop_row_annotations(search_row.row_kind, index)
        self._drop_row_annotations(replace_row.row_kind, index)
        search_row.frame.destroy()
        replace_row.frame.destroy()
        self._shift_annotation_rows(search_row.row_kind, index)
        self._shift_annotation_rows(replace_row.row_kind, index)
        self._reindex_rows()
        self._on_inputs_changed()

    def _drop_row_annotations(self, row_kind: str, row_index: int) -> None:
        for tag_name, data in list(self._annotation_state.items()):
            if data["row_kind"] == row_kind and data["row_index"] == row_index:
                del self._annotation_state[tag_name]

    def _shift_annotation_rows(self, row_kind: str, removed_index: int) -> None:
        for data in self._annotation_state.values():
            if data["row_kind"] == row_kind and data["row_index"] > removed_index:
                data["row_index"] -= 1

    def _paste_into_widget(self, widget: tk.Text) -> None:
        try:
            content = self.clipboard_get()
        except tk.TclError:
            self._set_status("Clipboard is empty.")
            return
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        self._on_inputs_changed()

    def _on_realtime_toggled(self) -> None:
        if self._realtime_var.get():
            self._schedule_refresh(immediate=True)
        else:
            self._set_status("Realtime disabled. Press Refresh to rebuild candidates.")

    def _on_inputs_changed(self) -> None:
        if self._realtime_var.get():
            self._schedule_refresh()
        else:
            self._set_status("Inputs changed. Press Refresh to rebuild candidates.")

    def _schedule_refresh(self, *, immediate: bool = False) -> None:
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
            self._refresh_job = None
        delay = 0 if immediate else 160
        self._refresh_job = self.after(delay, self._refresh_candidates)
        if not immediate:
            self._set_status("Rebuilding candidates...")

    def _refresh_candidates(self) -> None:
        self._refresh_job = None
        example_set = self._build_example_set()
        self._result = generate_regex_suggestions(example_set)
        self._render_generation_result(self._result)

    def _build_example_set(self) -> RegexExampleSet:
        mode = _MODE_VALUES.get(self._mode_var.get(), MODE_SEARCH_ONLY)
        search_rows = tuple(
            RegexExampleRow(
                text=self._get_widget_text(row.text_widget),
                enabled=row.enabled_var.get() if row.enabled_var is not None else True,
            )
            for row in self._search_rows
        )
        replace_rows = tuple(
            RegexExampleRow(text=self._get_widget_text(row.text_widget), enabled=True)
            for row in self._replace_rows
        )
        annotations = tuple(self._collect_annotations())
        return RegexExampleSet(
            search_rows=search_rows,
            replace_rows=replace_rows,
            mode=mode,
            annotations=annotations,
            options=self._options_state,
            notes=self._notes_var.get().strip(),
            compatibility_profile=self._compatibility_var.get(),
        )

    def _collect_annotations(self) -> List[SpanAnnotation]:
        annotations: List[SpanAnnotation] = []
        for tag_name, data in list(self._annotation_state.items()):
            row = self._row_from_kind_index(data["row_kind"], data["row_index"])
            if row is None:
                continue
            ranges = row.text_widget.tag_ranges(tag_name)
            if len(ranges) != 2:
                continue
            start_index = str(ranges[0])
            end_index = str(ranges[1])
            start_offset = len(row.text_widget.get("1.0", start_index))
            end_offset = len(row.text_widget.get("1.0", end_index))
            annotations.append(
                SpanAnnotation(
                    row_kind=data["row_kind"],
                    row_index=data["row_index"],
                    start=start_offset,
                    end=end_offset,
                    annotation_type=data["annotation_type"],
                    detail=data["detail"],
                    scope=data["scope"],
                    hover_label=data["hover_label"],
                    capture_group=data["capture_group"],
                )
            )
        return annotations

    def _get_widget_text(self, widget: tk.Text) -> str:
        return widget.get("1.0", "end-1c")

    def _render_generation_result(self, result: RegexGenerationResult) -> None:
        self._candidate_tree.delete(*self._candidate_tree.get_children())
        self._candidate_lookup.clear()
        for rank, candidate in enumerate(result.candidates, start=1):
            item_id = f"candidate-{rank}"
            self._candidate_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(rank, candidate.family, f"{candidate.score:.1f}", candidate.search_pattern),
            )
            self._candidate_lookup[item_id] = candidate

        if result.candidates:
            first_id = self._candidate_tree.get_children()[0]
            self._candidate_tree.selection_set(first_id)
            self._on_candidate_selected()
        else:
            self._set_output_text(self._search_output, "")
            self._set_output_text(self._replace_output, "")
            self._set_output_text(self._why_text, "")

        status = f"{len(result.candidates)} candidate(s)"
        if result.warnings:
            status += " | " + " | ".join(result.warnings[:2])
        self._set_status(status)

    def _on_candidate_selected(self) -> None:
        selection = self._candidate_tree.selection()
        if not selection:
            return
        candidate = self._candidate_lookup.get(selection[0])
        if candidate is None:
            return
        self._set_output_text(self._search_output, candidate.search_pattern)
        self._set_output_text(self._replace_output, candidate.replace_pattern)
        explanation_lines = [candidate.explanation]
        if candidate.warnings:
            explanation_lines.append("")
            explanation_lines.append("Warnings:")
            explanation_lines.extend(f"- {warning}" for warning in candidate.warnings)
        self._set_output_text(self._why_text, "\n".join(explanation_lines).strip())

    def _copy_selected_candidate_search(self) -> None:
        selection = self._candidate_tree.selection()
        if not selection:
            return
        candidate = self._candidate_lookup.get(selection[0])
        if candidate is None:
            return
        self._copy_text(candidate.search_pattern)
        self._set_status("Copied search regex.")

    def _set_output_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", "end")
        if text:
            widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _copy_widget_text(self, widget: tk.Text) -> None:
        self._copy_text(widget.get("1.0", "end-1c"))

    def _copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)

    def _show_context_menu(self, event: tk.Event) -> str:
        widget = event.widget
        if not isinstance(widget, tk.Text):
            return "break"

        row_kind = getattr(widget, "_regex_row_kind", ROW_KIND_SEARCH)
        row_index = int(getattr(widget, "_regex_row_index", 0))
        selection = self._selection_range(widget)
        clicked_tag = self._annotation_tag_at(widget, event.x, event.y)
        if selection is None and clicked_tag is None:
            return "break"

        menu = tk.Menu(self, tearoff=0)
        if selection is not None:
            menu.add_command(
                label="Mark as constant",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "constant"),
            )
            variable_menu = tk.Menu(menu, tearoff=0)
            variable_menu.add_command(
                label="Word",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "variable", detail="word"),
            )
            variable_menu.add_command(
                label="Number",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "variable", detail="number"),
            )
            variable_menu.add_command(
                label="Any",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "variable", detail="any"),
            )
            variable_menu.add_command(
                label="Japanese",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "variable", detail="japanese"),
            )
            menu.add_cascade(label="Mark as variable", menu=variable_menu)
            menu.add_command(
                label="Capture this span",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "capture"),
            )
            menu.add_command(
                label="Use as capture group 1",
                command=lambda: self._apply_selection_annotation(
                    row_kind,
                    row_index,
                    "capture_group",
                    capture_group=1,
                ),
            )
            menu.add_command(
                label="Use as capture group 2",
                command=lambda: self._apply_selection_annotation(
                    row_kind,
                    row_index,
                    "capture_group",
                    capture_group=2,
                ),
            )
            menu.add_command(
                label="Ignore this span",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "ignore"),
            )
            menu.add_command(
                label="Treat as optional",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "optional"),
            )
            menu.add_command(
                label="Must match literally",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "must_literal"),
            )
            menu.add_command(
                label="Prefer digits",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "prefer_digits"),
            )
            menu.add_command(
                label="Prefer word characters",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "prefer_word"),
            )
            menu.add_command(
                label="Preserve punctuation here",
                command=lambda: self._apply_selection_annotation(row_kind, row_index, "preserve_punctuation"),
            )
            menu.add_separator()
            menu.add_command(
                label="Clear annotation",
                command=lambda: self._clear_annotations_in_selection(widget),
            )

        if clicked_tag is not None:
            if selection is not None:
                menu.add_separator()
            menu.add_command(
                label="Clear annotation under cursor",
                command=lambda tag_name=clicked_tag: self._clear_annotation(tag_name),
            )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _apply_selection_annotation(
        self,
        row_kind: str,
        row_index: int,
        annotation_type: str,
        *,
        detail: str = "",
        capture_group: int = 0,
    ) -> None:
        row = self._row_from_kind_index(row_kind, row_index)
        if row is None:
            return
        selection = self._selection_range(row.text_widget)
        if selection is None:
            return

        self._clear_annotations_in_range(row.text_widget, row_kind, row_index, *selection)
        tag_name = f"regex_ann_{self._annotation_counter}"
        self._annotation_counter += 1
        row.text_widget.tag_add(tag_name, selection[0], selection[1])
        style_key = _style_key(annotation_type, detail)
        style = _ANNOTATION_STYLES.get(style_key, _ANNOTATION_STYLES["variable"])
        row.text_widget.tag_configure(tag_name, background=style["background"])
        row.text_widget.tag_bind(tag_name, "<Enter>", lambda event, name=tag_name: self._show_annotation_tooltip(event, name))
        row.text_widget.tag_bind(tag_name, "<Leave>", lambda _event: self._hide_annotation_tooltip())
        self._annotation_state[tag_name] = {
            "row_kind": row_kind,
            "row_index": row_index,
            "annotation_type": annotation_type,
            "detail": detail,
            "scope": "local",
            "hover_label": _hover_label(annotation_type, detail, row_kind, capture_group),
            "capture_group": capture_group,
        }
        self._on_inputs_changed()

    def _reapply_widget_annotations(self, widget: tk.Text) -> None:
        for tag_name, data in self._annotation_state.items():
            style_key = _style_key(data["annotation_type"], data["detail"])
            style = _ANNOTATION_STYLES.get(style_key, _ANNOTATION_STYLES["variable"])
            try:
                widget.tag_configure(tag_name, background=style["background"])
            except tk.TclError:
                continue

    def _selection_range(self, widget: tk.Text) -> Optional[tuple[str, str]]:
        try:
            return widget.index("sel.first"), widget.index("sel.last")
        except tk.TclError:
            return None

    def _annotation_tag_at(self, widget: tk.Text, x: int, y: int) -> Optional[str]:
        for tag_name in widget.tag_names(f"@{x},{y}"):
            if tag_name in self._annotation_state:
                return tag_name
        return None

    def _clear_annotation(self, tag_name: str) -> None:
        data = self._annotation_state.pop(tag_name, None)
        if data is None:
            return
        row = self._row_from_kind_index(data["row_kind"], data["row_index"])
        if row is not None:
            try:
                row.text_widget.tag_delete(tag_name)
            except tk.TclError:
                pass
        self._on_inputs_changed()

    def _clear_annotations_in_selection(self, widget: tk.Text) -> None:
        selection = self._selection_range(widget)
        if selection is None:
            return
        row_kind = getattr(widget, "_regex_row_kind", ROW_KIND_SEARCH)
        row_index = int(getattr(widget, "_regex_row_index", 0))
        self._clear_annotations_in_range(widget, row_kind, row_index, *selection)
        self._on_inputs_changed()

    def _clear_annotations_in_range(
        self,
        widget: tk.Text,
        row_kind: str,
        row_index: int,
        start: str,
        end: str,
    ) -> None:
        for tag_name, data in list(self._annotation_state.items()):
            if data["row_kind"] != row_kind or data["row_index"] != row_index:
                continue
            tag_ranges = widget.tag_ranges(tag_name)
            if len(tag_ranges) != 2:
                continue
            tag_start = str(tag_ranges[0])
            tag_end = str(tag_ranges[1])
            if widget.compare(tag_start, "<", end) and widget.compare(tag_end, ">", start):
                self._clear_annotation(tag_name)

    def _show_annotation_tooltip(self, event: tk.Event, tag_name: str) -> None:
        self._hide_annotation_tooltip()
        data = self._annotation_state.get(tag_name)
        if data is None:
            return
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_attributes("-topmost", True)
        tooltip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        label = ttk.Label(
            tooltip,
            text=data["hover_label"],
            padding=(6, 4),
            wraplength=280,
            justify="left",
        )
        label.pack()
        self._annotation_tooltip = tooltip

    def _hide_annotation_tooltip(self) -> None:
        if self._annotation_tooltip is None:
            return
        try:
            self._annotation_tooltip.destroy()
        except tk.TclError:
            pass
        self._annotation_tooltip = None

    def _row_from_kind_index(self, row_kind: str, row_index: int) -> Optional[_ExampleRowWidgets]:
        rows = self._search_rows if row_kind == ROW_KIND_SEARCH else self._replace_rows
        if 0 <= row_index < len(rows):
            return rows[row_index]
        return None

    def _open_options_dialog(self) -> None:
        if self._options_dialog is not None:
            try:
                if self._options_dialog.winfo_exists():
                    self._options_dialog.present()
                    return
            except tk.TclError:
                pass
        self._options_dialog = RegexOptionsDialog(self)
        self._options_dialog.present()

    def set_options_state(self, options: RegexMakerOptions) -> None:
        self._options_state = options
        self._on_inputs_changed()

    def _on_close(self) -> None:
        self.destroy()


class RegexOptionsDialog(tk.Toplevel):
    """Structured popup for global RegEx Maker constraints."""

    def __init__(self, owner: RegexHelpDialog) -> None:
        super().__init__(owner)
        self._owner = owner
        self._ready = False
        self.title("RegEx Options")
        self.resizable(False, False)
        self.transient(owner)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        apply_theme(self, theme=get_theme())

        self._bool_vars = {
            "match_whole_line": tk.BooleanVar(value=owner._options_state.match_whole_line),
            "ignore_spaces": tk.BooleanVar(value=owner._options_state.ignore_spaces),
            "ignore_leading_spaces": tk.BooleanVar(value=owner._options_state.ignore_leading_spaces),
            "ignore_trailing_spaces": tk.BooleanVar(value=owner._options_state.ignore_trailing_spaces),
            "case_sensitive": tk.BooleanVar(value=owner._options_state.case_sensitive),
            "prefer_simple": tk.BooleanVar(value=owner._options_state.prefer_simple),
            "prefer_strict": tk.BooleanVar(value=owner._options_state.prefer_strict),
            "allow_wildcard_fallback": tk.BooleanVar(value=owner._options_state.allow_wildcard_fallback),
            "disallow_lookaround": tk.BooleanVar(value=owner._options_state.disallow_lookaround),
            "disallow_backreferences": tk.BooleanVar(value=owner._options_state.disallow_backreferences),
            "require_replace_suggestion": tk.BooleanVar(value=owner._options_state.require_replace_suggestion),
        }
        self._max_candidates_var = tk.IntVar(value=owner._options_state.max_candidates)
        self._build_ui()
        self._ready = True
        self._center_on_owner()

    def present(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        definitions = [
            ("match_whole_line", "Match whole line", "Anchor suggestions to the full line by default."),
            ("ignore_spaces", "Ignore spaces", "Treat internal whitespace runs as flexible when possible."),
            ("ignore_leading_spaces", "Ignore leading spaces", "Allow leading spaces to vary without changing the candidate."),
            ("ignore_trailing_spaces", "Ignore trailing spaces", "Allow trailing spaces to vary without changing the candidate."),
            ("case_sensitive", "Case sensitive", "Turn off CherryAI's default ignore-case search validation."),
            ("prefer_simple", "Prefer simple regex", "Bias the ranking toward readable, smaller patterns."),
            ("prefer_strict", "Prefer strict regex", "Boost anchored and more exact candidates."),
            ("allow_wildcard_fallback", "Allow wildcard fallback", "Keep broad catch-all candidates available at lower rank."),
            ("disallow_lookaround", "Disallow lookaround", "Reject advanced lookahead/lookbehind constructions."),
            ("disallow_backreferences", "Disallow backreferences", "Reject search candidates that depend on backreferences."),
            ("require_replace_suggestion", "Require replace suggestion", "Only keep candidates that also infer a stable replacement."),
        ]
        for row_index, (key, label_text, tooltip_text) in enumerate(definitions):
            check = ttk.Checkbutton(
                frame,
                text=label_text,
                variable=self._bool_vars[key],
                command=self._on_options_changed,
            )
            check.grid(row=row_index, column=0, sticky="w", pady=2)
            attach_tooltip(check, tooltip_text)

        ttk.Label(frame, text="Maximum candidate count:").grid(row=len(definitions), column=0, sticky="w", pady=(10, 2))
        spinbox = ttk.Spinbox(
            frame,
            from_=1,
            to=20,
            increment=1,
            textvariable=self._max_candidates_var,
            width=6,
            command=self._on_options_changed,
        )
        spinbox.grid(row=len(definitions), column=1, sticky="w", pady=(10, 2), padx=(8, 0))
        spinbox.bind("<KeyRelease>", lambda _event: self._on_options_changed())
        attach_tooltip(spinbox, "Limit how many ranked candidates stay visible in the main window.")

        button_row = ttk.Frame(frame)
        button_row.grid(row=len(definitions) + 1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(button_row, text="Save Defaults", command=self._save_defaults).pack(side="left")
        ttk.Button(button_row, text="Restore Defaults", command=self._restore_defaults).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="Close", command=self._on_close).pack(side="right")

    def _center_on_owner(self) -> None:
        self.update_idletasks()
        x = self._owner.winfo_rootx() + 60
        y = self._owner.winfo_rooty() + 60
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _collect_options(self) -> RegexMakerOptions:
        return RegexMakerOptions(
            match_whole_line=self._bool_vars["match_whole_line"].get(),
            ignore_spaces=self._bool_vars["ignore_spaces"].get(),
            ignore_leading_spaces=self._bool_vars["ignore_leading_spaces"].get(),
            ignore_trailing_spaces=self._bool_vars["ignore_trailing_spaces"].get(),
            case_sensitive=self._bool_vars["case_sensitive"].get(),
            prefer_simple=self._bool_vars["prefer_simple"].get(),
            prefer_strict=self._bool_vars["prefer_strict"].get(),
            allow_wildcard_fallback=self._bool_vars["allow_wildcard_fallback"].get(),
            disallow_lookaround=self._bool_vars["disallow_lookaround"].get(),
            disallow_backreferences=self._bool_vars["disallow_backreferences"].get(),
            require_replace_suggestion=self._bool_vars["require_replace_suggestion"].get(),
            max_candidates=max(1, min(20, int(self._max_candidates_var.get() or 5))),
        )

    def _apply_options(self, options: RegexMakerOptions) -> None:
        self._bool_vars["match_whole_line"].set(options.match_whole_line)
        self._bool_vars["ignore_spaces"].set(options.ignore_spaces)
        self._bool_vars["ignore_leading_spaces"].set(options.ignore_leading_spaces)
        self._bool_vars["ignore_trailing_spaces"].set(options.ignore_trailing_spaces)
        self._bool_vars["case_sensitive"].set(options.case_sensitive)
        self._bool_vars["prefer_simple"].set(options.prefer_simple)
        self._bool_vars["prefer_strict"].set(options.prefer_strict)
        self._bool_vars["allow_wildcard_fallback"].set(options.allow_wildcard_fallback)
        self._bool_vars["disallow_lookaround"].set(options.disallow_lookaround)
        self._bool_vars["disallow_backreferences"].set(options.disallow_backreferences)
        self._bool_vars["require_replace_suggestion"].set(options.require_replace_suggestion)
        self._max_candidates_var.set(options.max_candidates)
        self._owner.set_options_state(options)

    def _on_options_changed(self) -> None:
        if not self._ready:
            return
        self._owner.set_options_state(self._collect_options())

    def _save_defaults(self) -> None:
        options = self._collect_options()
        save_regex_maker_option_defaults(options)
        self._owner.set_options_state(options)
        self._owner._set_status("RegEx options saved as defaults.")

    def _restore_defaults(self) -> None:
        options = load_regex_maker_option_defaults()
        self._apply_options(options)
        self._owner._set_status("RegEx options restored from saved defaults.")

    def _on_close(self) -> None:
        self._owner._options_dialog = None
        self.destroy()


def _style_key(annotation_type: str, detail: str) -> str:
    kind = str(annotation_type or "").strip().lower().replace(" ", "_")
    detail_key = str(detail or "").strip().lower().replace(" ", "_")
    if kind == "variable" and detail_key:
        return f"variable_{detail_key}"
    return kind


def _hover_label(
    annotation_type: str,
    detail: str,
    row_kind: str,
    capture_group: int,
) -> str:
    key = _style_key(annotation_type, detail)
    label = _ANNOTATION_STYLES.get(key, _ANNOTATION_STYLES["variable"])["label"]
    scope = "search" if row_kind == ROW_KIND_SEARCH else "replace"
    if annotation_type == "capture_group" and capture_group > 0:
        label = f"Capture group {capture_group}"
    return f"{label} ({scope}, local selection)"


__all__ = [
    "RegexHelpDialog",
    "RegexOptionsDialog",
    "load_regex_maker_option_defaults",
    "save_regex_maker_option_defaults",
]