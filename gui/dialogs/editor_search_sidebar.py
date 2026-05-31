"""Tk sidebar for Editor cross-file search and replace."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Iterator, Mapping, Optional

from CherryAI.functions.editor_search import (
	EditorFileSearchResult,
	EditorSearchMatch,
	EditorSearchOptions,
	LINE_SCOPE_ALL,
	LINE_SCOPE_NOT_PARSED,
	LINE_SCOPE_PARSED,
	iter_search_editor_file_results,
)
from CherryAI.gui.theme.icons import ICONS


FilePayloadProvider = Callable[[], Iterable[tuple[str, str, Iterable[Mapping[str, object]]]]]
SelectedFileProvider = Callable[[], Optional[str]]
MatchCallback = Callable[[EditorSearchMatch], None]
ReplaceCallback = Callable[[], None]


class EditorSearchSidebar(ttk.Frame):
	"""Compact VS-Code-style search sidebar with grouped cross-file results."""

	_SEARCH_STEP_BUDGET_SECONDS = 0.025
	_RENDER_INTERVAL_SECONDS = 1.0
	_RENDER_FILE_BATCH = 25

	def __init__(
		self,
		parent: tk.Misc,
		*,
		file_payload_provider: FilePayloadProvider,
		selected_file_provider: SelectedFileProvider,
		on_match_selected: MatchCallback,
		on_replace_current: ReplaceCallback,
		on_replace_all: ReplaceCallback,
		on_options_changed: Callable[[], None],
		style: str = "Sidebar.TFrame",
	) -> None:
		super().__init__(parent, style=style)
		self._file_payload_provider = file_payload_provider
		self._selected_file_provider = selected_file_provider
		self._on_match_selected = on_match_selected
		self._replace_current_callback = on_replace_current
		self._replace_all_callback = on_replace_all
		self._on_options_changed = on_options_changed
		self._result_by_iid: dict[str, EditorSearchMatch] = {}
		self._results: list[EditorFileSearchResult] = []
		self._pending_render_results: list[EditorFileSearchResult] = []
		self._search_result_iter: Optional[Iterator[EditorFileSearchResult]] = None
		self._search_generation = 0
		self._search_after_id: Optional[str] = None
		self._render_after_id: Optional[str] = None
		self._last_rendered_at = 0.0
		self._is_search_running = False
		self._paused_results: Optional[list[EditorFileSearchResult]] = None
		self._paused_summary = ""

		self.search_var = tk.StringVar()
		self.replace_var = tk.StringVar()
		self.file_patterns_var = tk.StringVar()
		self.regex_var = tk.BooleanVar(value=False)
		self.case_search_var = tk.BooleanVar(value=False)
		self.case_replace_var = tk.BooleanVar(value=False)
		self.whole_word_var = tk.BooleanVar(value=False)
		self.current_file_var = tk.BooleanVar(value=False)
		self.line_scope_var = tk.StringVar(value=LINE_SCOPE_ALL)
		self.summary_var = tk.StringVar(value="No results")
		self._control_var = tk.StringVar(value="Restore")

		self._build()
		for variable in (
			self.search_var,
			self.file_patterns_var,
			self.regex_var,
			self.case_search_var,
			self.whole_word_var,
			self.current_file_var,
			self.line_scope_var,
		):
			variable.trace_add("write", self._handle_query_option_changed)
		for variable in (self.replace_var, self.case_replace_var):
			variable.trace_add("write", self._handle_replace_option_changed)

	def _build(self) -> None:
		self.columnconfigure(0, weight=1)
		self.rowconfigure(8, weight=1)

		self.search_entry = ttk.Entry(self, textvariable=self.search_var)
		self.search_entry.grid(row=0, column=0, sticky="ew")

		replace_row = ttk.Frame(self, style="Sidebar.TFrame")
		replace_row.grid(row=1, column=0, sticky="ew", pady=(4, 6))
		replace_row.columnconfigure(0, weight=1)
		self.replace_entry = ttk.Entry(replace_row, textvariable=self.replace_var)
		self.replace_entry.grid(row=0, column=0, sticky="ew")
		ttk.Button(replace_row, text="1", width=3, command=self._on_replace_current).grid(
			row=0,
			column=1,
			padx=(4, 0),
		)
		ttk.Button(replace_row, text="All", width=5, command=self._on_replace_all).grid(
			row=0,
			column=2,
			padx=(4, 0),
		)

		pattern_row = ttk.Frame(self, style="Sidebar.TFrame")
		pattern_row.grid(row=2, column=0, sticky="ew")
		pattern_row.columnconfigure(0, weight=1)
		self.pattern_entry = ttk.Entry(pattern_row, textvariable=self.file_patterns_var)
		self.pattern_entry.grid(row=0, column=0, sticky="ew")
		ttk.Label(pattern_row, text="files").grid(row=0, column=1, padx=(4, 0))

		toggle_row = ttk.Frame(self, style="Sidebar.TFrame")
		toggle_row.grid(row=3, column=0, sticky="ew", pady=(6, 2))
		for col, text, var in (
			(0, "Aa", self.case_search_var),
			(1, "R Aa", self.case_replace_var),
			(2, ".*", self.regex_var),
			(3, "W", self.whole_word_var),
			(4, "File", self.current_file_var),
		):
			ttk.Checkbutton(toggle_row, text=text, variable=var, width=5).grid(row=0, column=col, sticky="w")

		scope_row = ttk.Frame(self, style="Sidebar.TFrame")
		scope_row.grid(row=4, column=0, sticky="ew", pady=(2, 6))
		for col, text, value in (
			(0, "All", LINE_SCOPE_ALL),
			(1, "Parsed", LINE_SCOPE_PARSED),
			(2, "Not parsed", LINE_SCOPE_NOT_PARSED),
		):
			ttk.Radiobutton(scope_row, text=text, value=value, variable=self.line_scope_var).grid(
				row=0,
				column=col,
				sticky="w",
			)

		nav_row = ttk.Frame(self, style="Sidebar.TFrame")
		nav_row.grid(row=5, column=0, sticky="ew", pady=(0, 6))
		nav_row.columnconfigure(1, weight=1)
		ttk.Button(nav_row, text=ICONS.NAV_PREV, width=3, command=self.select_previous).grid(row=0, column=0)
		ttk.Label(nav_row, textvariable=self.summary_var).grid(row=0, column=1, sticky="ew", padx=6)
		ttk.Button(nav_row, text=ICONS.NAV_NEXT, width=3, command=self.select_next).grid(row=0, column=2)

		control_row = ttk.Frame(self, style="Sidebar.TFrame")
		control_row.grid(row=6, column=0, sticky="ew", pady=(0, 6))
		self.control_button = ttk.Button(
			control_row,
			textvariable=self._control_var,
			command=self._on_control_button,
			width=8,
		)
		self.control_button.grid(row=0, column=0, sticky="w")
		self._refresh_control_button()

		self.results_tree = ttk.Treeview(self, show="tree", selectmode="browse")
		self.results_tree.grid(row=8, column=0, sticky="nsew")
		self.results_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
		scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.results_tree.yview)
		scrollbar.grid(row=8, column=1, sticky="ns")
		self.results_tree.configure(yscrollcommand=scrollbar.set)

	def focus_search(self) -> None:
		self.search_entry.focus_set()

	def get_options(self) -> EditorSearchOptions:
		return EditorSearchOptions(
			query=self.search_var.get().strip(),
			replace=self.replace_var.get(),
			use_regex=bool(self.regex_var.get()),
			case_sensitive_search=bool(self.case_search_var.get()),
			case_sensitive_replace=bool(self.case_replace_var.get()),
			whole_word=bool(self.whole_word_var.get()),
			file_patterns=self.file_patterns_var.get(),
			current_file_only=bool(self.current_file_var.get()),
			line_scope=self.line_scope_var.get(),
		)

	def has_query(self) -> bool:
		return bool(self.get_options().query)

	def refresh_results(self) -> list[EditorFileSearchResult]:
		self.start_search()
		return self._results

	def start_search(self) -> None:
		"""Start a cancellable incremental search."""
		options = self.get_options()
		self._cancel_running_search()
		if not options.query:
			self._results = []
			self._pending_render_results = []
			self._render_results(reset=True)
			self._refresh_control_button()
			return
		if self._results:
			self._paused_results = list(self._results)
			self._paused_summary = self.summary_var.get()
		files = self._file_payload_provider()
		if options.current_file_only:
			selected_rel_path = self._selected_file_provider()
			files = (payload for payload in files if payload[0] == selected_rel_path)
		self._search_generation += 1
		self._search_result_iter = iter(iter_search_editor_file_results(files, options))
		self._results = []
		self._pending_render_results = []
		self._last_rendered_at = 0.0
		self._is_search_running = True
		self._render_results(reset=True)
		self._refresh_control_button()
		self._schedule_search_step(self._search_generation)

	def cancel_search(self) -> None:
		"""Stop the current search and keep previous complete results restorable."""
		if not self._is_search_running:
			return
		self._cancel_running_search()
		self._pending_render_results = []
		self.summary_var.set(f"Search stopped. {self._paused_summary or 'No previous results'}")
		self._refresh_control_button()

	def restore_previous_results(self) -> None:
		"""Restore the last complete result set saved before cancellation."""
		if self._is_search_running or self._paused_results is None:
			return
		self._results = list(self._paused_results)
		self._pending_render_results = list(self._results)
		self._clear_rendered_results()
		self._schedule_render_flush()
		if self._paused_summary:
			self.summary_var.set(self._paused_summary)
		self._paused_results = None
		self._paused_summary = ""
		self._refresh_control_button()

	def _cancel_running_search(self) -> None:
		if getattr(self, "_search_after_id", None) is not None:
			try:
				self.after_cancel(self._search_after_id)
			except tk.TclError:
				pass
		if getattr(self, "_render_after_id", None) is not None:
			try:
				self.after_cancel(self._render_after_id)
			except tk.TclError:
				pass
		self._search_after_id = None
		self._render_after_id = None
		self._search_result_iter = None
		self._is_search_running = False

	def _schedule_search_step(self, generation: int) -> None:
		self._search_after_id = self.after(1, lambda: self._run_search_step(generation))

	def _run_search_step(self, generation: int) -> None:
		self._search_after_id = None
		if generation != self._search_generation or self._search_result_iter is None:
			return
		started = time.monotonic()
		while time.monotonic() - started < self._SEARCH_STEP_BUDGET_SECONDS:
			try:
				result = next(self._search_result_iter)
			except StopIteration:
				self._search_result_iter = None
				self._is_search_running = False
				self._paused_results = None
				self._paused_summary = ""
				self._flush_pending_results(force=False)
				self._schedule_render_flush()
				self._update_summary()
				self._refresh_control_button()
				return
			self._results.append(result)
			self._pending_render_results.append(result)
		self._flush_pending_results(force=False)
		self._update_summary(running=True)
		self._refresh_control_button()
		self._schedule_search_step(generation)

	def _flush_pending_results(self, *, force: bool) -> None:
		if not self._pending_render_results:
			return
		now = time.monotonic()
		if not force and now - self._last_rendered_at < self._RENDER_INTERVAL_SECONDS:
			return
		self._render_pending_results(limit=None if force else self._RENDER_FILE_BATCH)
		self._last_rendered_at = now
		if force and self._pending_render_results:
			self._render_pending_results(limit=None)

	def _schedule_render_flush(self) -> None:
		if self._render_after_id is not None or not self._pending_render_results:
			return
		self._render_after_id = self.after(50, self._run_render_flush)

	def _run_render_flush(self) -> None:
		self._render_after_id = None
		if not self._pending_render_results:
			return
		self._render_pending_results(limit=self._RENDER_FILE_BATCH)
		if self._pending_render_results:
			self._schedule_render_flush()

	def _render_pending_results(self, *, limit: Optional[int]) -> None:
		count = len(self._pending_render_results) if limit is None else min(limit, len(self._pending_render_results))
		for _ in range(count):
			self._append_result_to_tree(self._pending_render_results.pop(0))

	def current_match(self) -> Optional[EditorSearchMatch]:
		selection = self.results_tree.selection()
		if selection:
			match = self._result_by_iid.get(selection[0])
			if match is not None:
				return match
		for item_id in self._iter_match_iids():
			return self._result_by_iid.get(item_id)
		return None

	def select_next(self) -> None:
		self._select_relative(1)

	def select_previous(self) -> None:
		self._select_relative(-1)

	def _render_results(self, *, reset: bool = False) -> None:
		self._clear_rendered_results()
		for result in self._results:
			self._append_result_to_tree(result)
		self._update_summary(running=self._is_search_running)

	def _clear_rendered_results(self) -> None:
		self._result_by_iid.clear()
		self.results_tree.delete(*self.results_tree.get_children())

	def _append_result_to_tree(self, result: EditorFileSearchResult) -> None:
		file_iid = f"file:{result.rel_path}"
		count = len(result.matches)
		try:
			self.results_tree.insert("", "end", iid=file_iid, text=f"{result.rel_path} ({count})", open=True)
		except tk.TclError:
			file_iid = f"file:{len(self.results_tree.get_children(''))}:{result.rel_path}"
			self.results_tree.insert("", "end", iid=file_iid, text=f"{result.rel_path} ({count})", open=True)
		for idx, match in enumerate(result.matches):
			match_iid = f"match:{result.rel_path}:{idx}"
			while match_iid in self._result_by_iid:
				match_iid = f"{match_iid}:dup"
			self._result_by_iid[match_iid] = match
			self.results_tree.insert(
				file_iid,
				"end",
				iid=match_iid,
				text=f"{match.line}:{match.column + 1}  {match.preview}",
			)

	def _update_summary(self, *, running: bool = False) -> None:
		total = sum(len(result.matches) for result in self._results)
		file_count = len(self._results)
		prefix = "Searching... " if running else ""
		self.summary_var.set(
			f"{prefix}{total} result{'s' if total != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}"
		)

	def _refresh_control_button(self) -> None:
		if not hasattr(self, "control_button"):
			return
		if self._is_search_running:
			self._control_var.set("Stop")
			self.control_button.state(["!disabled"])
		elif self._paused_results is not None:
			self._control_var.set("Restore")
			self.control_button.state(["!disabled"])
		else:
			self._control_var.set("Restore")
			self.control_button.state(["disabled"])

	def _on_control_button(self) -> None:
		if self._is_search_running:
			self.cancel_search()
		else:
			self.restore_previous_results()

	def _iter_match_iids(self) -> list[str]:
		items: list[str] = []
		for file_iid in self.results_tree.get_children(""):
			items.extend(self.results_tree.get_children(file_iid))
		return items

	def _select_relative(self, delta: int) -> None:
		items = self._iter_match_iids()
		if not items:
			return
		selection = self.results_tree.selection()
		current = selection[0] if selection and selection[0] in items else None
		idx = items.index(current) if current is not None else (-1 if delta > 0 else 0)
		next_iid = items[(idx + delta) % len(items)]
		self.results_tree.selection_set(next_iid)
		self.results_tree.focus(next_iid)
		self.results_tree.see(next_iid)
		match = self._result_by_iid.get(next_iid)
		if match is not None:
			self._on_match_selected(match)

	def _on_tree_select(self, _event: tk.Event) -> None:
		match = self.current_match()
		if match is not None:
			self._on_match_selected(match)

	def _on_replace_current(self) -> None:
		self._replace_current_callback()

	def _on_replace_all(self) -> None:
		self._replace_all_callback()

	def _handle_query_option_changed(self, *_args: object) -> None:
		self._on_options_changed()

	def _handle_replace_option_changed(self, *_args: object) -> None:
		self._on_options_changed()
