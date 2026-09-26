"""CherryAI GUI - Shared Editor host / Full Files surface.

This module restores the recycled Editor shell used for the first stage of the
Editor redesign. The host keeps the full-file surface inside this window and
hands off into the retained Full Table View dialog when the user switches to
Lines Only mode.
"""

from __future__ import annotations

import logging
import json
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional

from CherryAI.functions.editor_search import (
	EditorSearchMatch,
	EditorSearchOptions,
	LINE_SCOPE_ALL,
	find_search_match_ranges,
	find_search_spans,
	parsed_line_numbers,
	replace_all,
	replace_all_scoped,
	search_editor_files,
	text_offset_to_index,
)
from CherryAI.functions.manifest_manager import FileDirEntry, ManifestManager
from CherryAI.gui.dialogs.editor_search_sidebar import EditorSearchSidebar
from CherryAI.gui.dialogs.table_view import FullTableViewDialog
from CherryAI.gui.theme.colors import apply_theme, apply_window_preferences, get_theme
from CherryAI.gui.theme.icons import ICONS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EditorSelectionSpan:
	"""One replaceable editor selection or containing span."""

	start_offset: int
	end_offset: int
	text: str
	label: str = ""


@dataclass(frozen=True)
class EditorSpanCandidate:
	"""Balanced span around an editor selection."""

	open_char: str
	close_char: str
	open_offset: int
	close_offset: int
	content_start: int
	content_end: int
	content: str


_SPAN_PAIRS = {
	'"': '"',
	"'": "'",
	"<": ">",
	"[": "]",
	"(": ")",
	"{": "}",
}

_LOCAL_API_PROVIDERS = {"local", "lmstudio", "ollama", "koboldcpp"}


def _normalize_rel_path(rel_path: str) -> str:
	"""Normalize a manifest-relative file path for tree display."""
	parts = [part for part in str(rel_path).replace("\\", "/").split("/") if part]
	return "/".join(parts)


def _build_file_tree_rows(rel_paths: Iterable[str]) -> list[dict[str, str]]:
	"""Return folder-first tree rows for the editor file browser."""
	normalized_rel_paths = sorted(
		{
			normalized
			for normalized in (_normalize_rel_path(rel_path) for rel_path in rel_paths)
			if normalized
		},
		key=str.lower,
	)
	folder_paths: set[str] = set()
	for rel_path in normalized_rel_paths:
		parts = rel_path.split("/")
		for depth in range(1, len(parts)):
			folder_paths.add("/".join(parts[:depth]))

	rows: list[dict[str, str]] = []
	for folder_path in sorted(folder_paths, key=str.lower):
		parts = folder_path.split("/")
		rows.append(
			{
				"kind": "folder",
				"key": folder_path,
				"parent_key": "/".join(parts[:-1]),
				"text": parts[-1],
			}
		)
	for rel_path in normalized_rel_paths:
		parts = rel_path.split("/")
		rows.append(
			{
				"kind": "file",
				"key": rel_path,
				"parent_key": "/".join(parts[:-1]),
				"text": parts[-1],
				"rel_path": rel_path,
			}
		)
	return rows


def _find_search_spans(
	text: str,
	query: str,
	*,
	use_regex: bool = False,
	case_sensitive: bool = True,
	whole_word: bool = False,
) -> list[tuple[int, int]]:
	"""Return non-overlapping search spans for literal or regex editor search."""
	return find_search_spans(
		text,
		EditorSearchOptions(
			query=query,
			use_regex=use_regex,
			case_sensitive_search=case_sensitive,
			whole_word=whole_word,
		),
	)


def _text_offset_to_index(text: str, offset: int) -> str:
	"""Convert a character offset into Tk text ``line.column`` form."""
	return text_offset_to_index(text, offset)


def _find_search_match_ranges(
	text: str,
	query: str,
	*,
	use_regex: bool = False,
	case_sensitive: bool = True,
	whole_word: bool = False,
) -> list[tuple[str, str]]:
	"""Return Tk text index ranges for all current search matches."""
	return find_search_match_ranges(
		text,
		EditorSearchOptions(
			query=query,
			use_regex=use_regex,
			case_sensitive_search=case_sensitive,
			whole_word=whole_word,
		),
	)


def _physical_line_count(text: str) -> int:
	"""Return the number of physical lines represented by *text*."""
	normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
	return max(1, normalized.count("\n") + 1)


def _text_offset_to_line_index(text: str, offset: int) -> int:
	"""Return zero-based physical line index for a text offset."""
	safe_offset = max(0, min(int(offset), len(text)))
	return text.count("\n", 0, safe_offset)


def _line_context_for_offsets(text: str, start_offset: int, end_offset: int, radius: int) -> list[str]:
	"""Return surrounding physical lines around a selection."""
	lines = text.splitlines()
	if not lines:
		return []
	start_line = _text_offset_to_line_index(text, start_offset)
	end_line = _text_offset_to_line_index(text, max(start_offset, end_offset - 1))
	first = max(0, start_line - max(0, radius))
	last = min(len(lines), end_line + max(0, radius) + 1)
	return lines[first:last]


def _balanced_span_candidates(text: str, selection_start: int, selection_end: int) -> list[EditorSpanCandidate]:
	"""Find balanced quote/bracket spans that contain a selection."""
	start = max(0, min(selection_start, len(text)))
	end = max(start, min(selection_end, len(text)))
	candidates: list[EditorSpanCandidate] = []
	seen: set[tuple[int, int]] = set()

	for open_char, close_char in _SPAN_PAIRS.items():
		open_offset = _find_containing_span_open(text, start, open_char, close_char)
		if open_offset is None:
			continue
		close_offset = _find_matching_span_close(text, open_offset, open_char, close_char)
		if close_offset is None:
			continue
		content_start = open_offset + 1
		content_end = close_offset
		if not (content_start <= start and end <= content_end):
			continue
		key = (content_start, content_end)
		if key in seen:
			continue
		seen.add(key)
		candidates.append(
			EditorSpanCandidate(
				open_char=open_char,
				close_char=close_char,
				open_offset=open_offset,
				close_offset=close_offset,
				content_start=content_start,
				content_end=content_end,
				content=text[content_start:content_end],
			)
		)

	candidates.sort(key=lambda candidate: (candidate.content_end - candidate.content_start, candidate.open_offset))
	return candidates


def _find_containing_span_open(
	text: str,
	selection_start: int,
	open_char: str,
	close_char: str,
) -> Optional[int]:
	"""Return nearest opening delimiter that can contain the selection."""
	if open_char == close_char:
		open_offset = text.rfind(open_char, 0, selection_start + 1)
		while open_offset >= 0:
			close_offset = text.find(close_char, open_offset + 1)
			if close_offset >= selection_start:
				return open_offset
			open_offset = text.rfind(open_char, 0, open_offset)
		return None

	depth = 0
	for offset in range(selection_start, -1, -1):
		char = text[offset]
		if char == close_char:
			depth += 1
		elif char == open_char:
			if depth == 0:
				return offset
			depth -= 1
	return None


def _find_matching_span_close(
	text: str,
	open_offset: int,
	open_char: str,
	close_char: str,
) -> Optional[int]:
	"""Return matching close delimiter for an opening delimiter."""
	if open_char == close_char:
		close_offset = text.find(close_char, open_offset + 1)
		return close_offset if close_offset >= 0 else None

	depth = 0
	for offset in range(open_offset, len(text)):
		char = text[offset]
		if char == open_char:
			depth += 1
		elif char == close_char:
			depth -= 1
			if depth == 0:
				return offset
	return None


class PatchEditorViewDialog(tk.Toplevel):
	"""Shared Editor host for the current migration slice.

	``Full Files`` remains inside this non-modal window. ``Lines Only`` is still
	the retained Full Table View dialog, so switching modes hands off into that
	surface while preserving the currently selected file context.
	"""

	_WINDOW_ATTR = "_editor_dialog"

	@classmethod
	def open_or_focus(
		cls,
		parent: tk.Misc,
		manifest_manager: ManifestManager,
		*,
		initial_file: Optional[str] = None,
		initial_locator: Optional[Dict[str, Any]] = None,
		initial_mode: str = "full_files",
	) -> "PatchEditorViewDialog":
		"""Open or focus the shared Editor window for *parent*'s root."""
		root = parent.winfo_toplevel()
		existing = getattr(root, cls._WINDOW_ATTR, None)
		if isinstance(existing, cls) and existing.winfo_exists():
			existing._mgr = manifest_manager
			existing._refresh_file_tree()
			if initial_file is not None:
				existing.set_selected_file(initial_file)
			if initial_locator is not None:
				existing.set_locator_target(initial_locator)
			existing.switch_mode(initial_mode)
			existing.deiconify()
			existing.lift()
			existing.focus_force()
			return existing

		init_kwargs: Dict[str, Any] = {
			"initial_file": initial_file,
			"initial_mode": initial_mode,
		}
		if initial_locator is not None:
			init_kwargs["initial_locator"] = initial_locator
		dialog = cls(
			parent,
			manifest_manager,
			**init_kwargs,
		)
		setattr(root, cls._WINDOW_ATTR, dialog)
		return dialog

	def __init__(
		self,
		parent: tk.Misc,
		manifest_manager: ManifestManager,
		*,
		initial_file: Optional[str] = None,
		initial_locator: Optional[Dict[str, Any]] = None,
		initial_mode: str = "full_files",
	) -> None:
		super().__init__(parent)
		self._parent = parent
		self._window_root = parent.winfo_toplevel()
		self._mgr = manifest_manager
		self._entry_by_rel_path: Dict[str, FileDirEntry] = {}
		self._selected_rel_path: Optional[str] = None
		self._tree_item_to_rel_path: Dict[str, str] = {}
		self._mode_var = tk.StringVar(value="full_files")
		self._current_search_index = "1.0"
		self._locator_metadata: list[Dict[str, Any]] = []
		self._locator_ranges_by_idx: Dict[int, list[tuple[int, int]]] = {}
		self._line_history_by_idx: Dict[int, Dict[str, Any]] = {}
		self._current_locator_target: Optional[Dict[str, Any]] = None
		self._suspend_file_tree_select = False
		self._suspend_history_tree_select = False
		self._line_number_refresh_pending = False
		self._search_highlight_after_id: Optional[str] = None
		self._search_match_ranges: list[tuple[str, str]] = []
		self._search_match_query = ""
		self._search_match_use_regex = False
		self._current_search_match_idx = -1
		self._sidebar_active_panel = "files"
		self._sidebar_visible = True
		self._activity_buttons: Dict[str, tk.Button] = {}
		self._sidebar_panels: Dict[str, ttk.Frame] = {}
		self._unsaved_file_text_by_rel_path: Dict[str, str] = {}
		self._loading_editor_text = False
		self._refresh_search_results_after_highlight = False

		self.title("Editor")
		self.minsize(1100, 700)
		apply_window_preferences(
			self,
			parent=parent,
			window_key="EditorDialog",
			default_geometry="1400x900",
		)

		self._build_shell()
		self.refresh_theme()
		self._refresh_file_tree()

		if initial_file is not None:
			self.set_selected_file(initial_file)
		else:
			self._select_first_file_if_available()
		if initial_locator is not None:
			self.set_locator_target(initial_locator)

		self.switch_mode(initial_mode)
		self.protocol("WM_DELETE_WINDOW", self._on_close)
		self.bind("<Control-s>", self._on_save_shortcut)
		self.bind("<Control-S>", self._on_save_shortcut)

	def refresh_theme(self) -> None:
		"""Reapply the active theme to the Editor shell."""
		theme = get_theme()
		apply_theme(self, theme=theme)

		if hasattr(self, "_editor_text"):
			self._editor_text.configure(
				bg=theme.bg_input,
				fg=theme.text_primary,
				insertbackground=theme.text_primary,
				selectbackground=theme.bg_hover,
				selectforeground=theme.text_primary,
			)
			self._editor_text.tag_configure(
				"search_match",
				background=theme.table_changed_bg,
			)
			self._editor_text.tag_configure(
				"locator_match",
				background=theme.table_match_bg,
			)
			self._editor_text.tag_configure(
				"locator_active",
				background=theme.bg_selected,
			)
			self._editor_text.tag_lower("locator_match")
			self._editor_text.tag_raise("locator_active", "locator_match")
			self._editor_text.tag_raise("search_match", "locator_active")
			self._editor_text.tag_raise("sel", "search_match")
		if hasattr(self, "_activity_bar"):
			self._activity_bar.configure(bg=theme.primary_dark, highlightbackground=theme.border_light)
		if hasattr(self, "_sidebar_frame"):
			self._sidebar_frame.configure(style="Sidebar.TFrame")
		if hasattr(self, "_sidebar_header_label"):
			self._sidebar_header_label.configure(background=theme.bg_panel, foreground=theme.text_primary)
		self._refresh_sidebar_activity_buttons(theme)
		if hasattr(self, "_line_number_canvas"):
			self._line_number_canvas.configure(
				bg=theme.bg_panel,
				highlightbackground=theme.border_light,
			)
		if hasattr(self, "_diff_text"):
			self._diff_text.configure(
				bg=theme.bg_input,
				fg=theme.text_primary,
				insertbackground=theme.text_primary,
			)
		if hasattr(self, "_patch_diff_text"):
			self._patch_diff_text.configure(
				bg=theme.bg_input,
				fg=theme.text_primary,
				insertbackground=theme.text_primary,
			)

	def _build_shell(self) -> None:
		"""Build the shared Editor shell and both mode surfaces."""
		mode_bar = ttk.Frame(self, padding=(8, 8, 8, 4))
		mode_bar.pack(fill="x")

		ttk.Label(mode_bar, text="Full Files").pack(side="left")
		ttk.Radiobutton(
			mode_bar,
			text="",
			value="full_files",
			variable=self._mode_var,
			command=self._on_mode_changed,
		).pack(side="left", padx=(6, 2))
		ttk.Radiobutton(
			mode_bar,
			text="",
			value="lines_only",
			variable=self._mode_var,
			command=self._on_mode_changed,
		).pack(side="left", padx=(0, 6))
		ttk.Label(mode_bar, text="Lines Only").pack(side="left")

		self._selected_file_var = tk.StringVar(value="No file selected")
		ttk.Label(mode_bar, textvariable=self._selected_file_var).pack(side="right")
		self._locator_var = tk.StringVar(value="Locator: none")
		ttk.Label(mode_bar, textvariable=self._locator_var).pack(side="right", padx=(0, 12))

		self._content_frame = ttk.Frame(self)
		self._content_frame.pack(fill="both", expand=True)

		self._full_files_frame = ttk.Frame(self._content_frame)
		self._lines_only_frame = ttk.Frame(self._content_frame, padding=24)

		self._build_full_files_surface()
		self._build_lines_only_surface()

	def _build_full_files_surface(self) -> None:
		"""Build the retained Full Files editor surface."""
		top_bar = ttk.Frame(self._full_files_frame, padding=(8, 0, 8, 6))
		top_bar.pack(fill="x")

		ttk.Button(top_bar, text="Save", command=self._save_current_file).pack(side="left")
		self._sidebar_hint_var = tk.StringVar(value="Sidebar: Files")
		ttk.Label(top_bar, textvariable=self._sidebar_hint_var).pack(side="right")

		paned = ttk.PanedWindow(self._full_files_frame, orient="horizontal")
		paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

		self._sidebar_shell = ttk.Frame(paned)
		self._sidebar_shell.columnconfigure(1, weight=1)
		self._sidebar_shell.rowconfigure(0, weight=1)
		paned.add(self._sidebar_shell, weight=1)

		self._activity_bar = tk.Frame(
			self._sidebar_shell,
			width=46,
			highlightthickness=1,
			bd=0,
		)
		self._activity_bar.grid(row=0, column=0, sticky="ns")
		self._activity_bar.grid_propagate(False)

		self._sidebar_frame = ttk.Frame(self._sidebar_shell, style="Sidebar.TFrame", padding=(8, 8, 8, 8))
		self._sidebar_frame.grid(row=0, column=1, sticky="nsew")
		self._sidebar_frame.columnconfigure(0, weight=1)
		self._sidebar_frame.rowconfigure(1, weight=1)

		self._sidebar_header_label = tk.Label(self._sidebar_frame, anchor="w", font=("Segoe UI", 10, "bold"))
		self._sidebar_header_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))

		self._sidebar_content = ttk.Frame(self._sidebar_frame, style="Sidebar.TFrame")
		self._sidebar_content.grid(row=1, column=0, sticky="nsew")
		self._sidebar_content.columnconfigure(0, weight=1)
		self._sidebar_content.rowconfigure(0, weight=1)

		self._build_activity_button(
			"files",
			ICONS.FILE_FOLDER,
			"Files",
			row=0,
		)
		self._build_activity_button(
			"search",
			ICONS.ACTION_SEARCH,
			"Search",
			row=1,
		)

		self._build_file_tree_sidebar(self._sidebar_content)
		self._build_search_sidebar(self._sidebar_content)
		self._show_sidebar_panel(self._sidebar_active_panel, visible=True)

		right_frame = ttk.Frame(paned)
		paned.add(right_frame, weight=4)

		editor_frame = ttk.Frame(right_frame)
		editor_frame.pack(fill="both", expand=True)
		editor_frame.columnconfigure(1, weight=1)
		editor_frame.rowconfigure(0, weight=1)

		self._line_number_canvas = tk.Canvas(
			editor_frame,
			width=48,
			highlightthickness=1,
			bd=0,
			takefocus=False,
		)
		self._line_number_canvas.grid(row=0, column=0, sticky="ns")

		self._editor_text = tk.Text(right_frame, wrap="word", undo=True)
		self._editor_text.grid(in_=editor_frame, row=0, column=1, sticky="nsew")
		self._editor_scrollbar = ttk.Scrollbar(
			editor_frame,
			orient="vertical",
			command=self._editor_text.yview,
		)
		self._editor_scrollbar.grid(row=0, column=2, sticky="ns")
		self._editor_text.configure(yscrollcommand=self._on_editor_text_scrolled)
		self._editor_text.bind("<<Modified>>", self._on_editor_modified)
		self._editor_text.bind("<ButtonRelease-1>", self._on_editor_cursor_changed)
		self._editor_text.bind("<KeyRelease>", self._on_editor_cursor_changed)
		self._editor_text.bind("<Configure>", self._schedule_line_number_refresh, add="+")
		self._editor_text.bind("<MouseWheel>", self._schedule_line_number_refresh, add="+")
		self._editor_text.bind("<Button-4>", self._schedule_line_number_refresh, add="+")
		self._editor_text.bind("<Button-5>", self._schedule_line_number_refresh, add="+")
		self._editor_text.bind("<Button-3>", self._show_editor_context_menu)
		self._editor_text.bind("<Control-Button-1>", self._show_editor_context_menu)

		self._bottom_tabs = ttk.Notebook(right_frame)
		self._bottom_tabs.pack(fill="both", expand=False, pady=(8, 0))

		diff_frame = ttk.Frame(self._bottom_tabs)
		self._diff_text = tk.Text(diff_frame, wrap="none", height=12)
		self._diff_text.pack(fill="both", expand=True)
		self._bottom_tabs.add(diff_frame, text="Diff")

		patch_diff_frame = ttk.Frame(self._bottom_tabs)
		self._patch_diff_text = tk.Text(patch_diff_frame, wrap="none", height=12)
		self._patch_diff_text.pack(fill="both", expand=True)
		self._bottom_tabs.add(patch_diff_frame, text="Patch Diff")

		history_frame = ttk.Frame(self._bottom_tabs)
		self._history_tree = ttk.Treeview(
			history_frame,
			columns=("idx", "ln", "f", "status", "original", "translated", "current"),
			show="headings",
			height=8,
		)
		for name, text, width in (
			("idx", "Idx", 60),
			("ln", "Ln", 60),
			("f", "F", 50),
			("status", "Status", 90),
			("original", "Original", 220),
			("translated", "Translated", 220),
			("current", "Current", 220),
		):
			self._history_tree.heading(name, text=text)
			self._history_tree.column(name, width=width, stretch=True)
		self._history_tree.pack(fill="both", expand=True)
		self._history_tree.bind("<<TreeviewSelect>>", self._on_history_tree_select)
		self._bottom_tabs.add(history_frame, text="Line History")

	def _build_activity_button(self, key: str, icon: str, tooltip_text: str, *, row: int) -> None:
		"""Create one VS Code-like activity-bar button."""
		button = tk.Button(
			self._activity_bar,
			text=icon,
			width=3,
			relief="flat",
			bd=0,
			command=lambda panel_key=key: self._toggle_sidebar_panel(panel_key),
			takefocus=False,
		)
		button.grid(row=row, column=0, padx=4, pady=(6 if row == 0 else 2, 2), sticky="ew")
		button.configure(font=("Segoe UI Symbol", 14))
		button.bind("<Enter>", lambda _event, text=tooltip_text: self._sidebar_hint_var.set(f"Sidebar: {text}"))
		button.bind(
			"<Leave>",
			lambda _event: self._sidebar_hint_var.set(
				f"Sidebar: {self._get_sidebar_panel_label(self._sidebar_active_panel)}"
			),
		)
		self._activity_buttons[key] = button

	def _build_file_tree_sidebar(self, parent: ttk.Frame) -> None:
		"""Build the Explorer-style sidebar panel."""
		panel = ttk.Frame(parent, style="Sidebar.TFrame")
		panel.grid(row=0, column=0, sticky="nsew")
		panel.columnconfigure(0, weight=1)
		panel.rowconfigure(0, weight=1)

		self._file_tree = ttk.Treeview(panel, show="tree")
		self._file_tree.grid(row=0, column=0, sticky="nsew")
		self._file_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
		self._file_tree_scrollbar = ttk.Scrollbar(
			panel,
			orient="vertical",
			command=self._file_tree.yview,
		)
		self._file_tree_scrollbar.grid(row=0, column=1, sticky="ns")
		self._file_tree.configure(yscrollcommand=self._file_tree_scrollbar.set)

		self._sidebar_panels["files"] = panel

	def _build_search_sidebar(self, parent: ttk.Frame) -> None:
		"""Build the search-and-replace sidebar panel."""
		panel = EditorSearchSidebar(
			parent,
			file_payload_provider=self._iter_search_file_payloads,
			selected_file_provider=lambda: self._selected_rel_path,
			on_match_selected=self._select_search_result_match,
			on_search_requested=self._run_search_from_sidebar,
			on_replace_current=self._replace_current,
			on_replace_file=self._replace_all,
			on_replace_all_files=self._replace_all_found_files,
			on_options_changed=self._schedule_search_from_sidebar_change,
		)
		panel.grid(row=0, column=0, sticky="nsew")
		panel.columnconfigure(0, weight=1)

		self._search_sidebar = panel
		self._search_entry = panel.search_entry
		self._sidebar_panels["search"] = panel

	def _get_sidebar_panel_label(self, panel_key: str) -> str:
		"""Return the UI label for one sidebar panel key."""
		return {"files": "Files", "search": "Search"}.get(panel_key, "Sidebar")

	def _refresh_sidebar_activity_buttons(self, theme: Optional[Any] = None) -> None:
		"""Apply active/inactive visuals to the activity-bar icon buttons."""
		if not hasattr(self, "_activity_buttons"):
			return
		if theme is None:
			theme = get_theme()
		for panel_key, button in self._activity_buttons.items():
			is_active = self._sidebar_visible and self._sidebar_active_panel == panel_key
			button.configure(
				bg=theme.bg_selected if is_active else theme.primary_dark,
				fg=theme.text_primary,
				activebackground=theme.bg_hover,
				activeforeground=theme.text_primary,
				highlightthickness=0,
			)

	def _show_sidebar_panel(self, panel_key: str, *, visible: bool) -> None:
		"""Show or hide one sidebar panel while keeping the activity bar visible."""
		if panel_key not in self._sidebar_panels:
			return

		self._sidebar_active_panel = panel_key
		self._sidebar_visible = visible
		for other_panel in self._sidebar_panels.values():
			other_panel.grid_remove()

		if visible:
			self._sidebar_frame.grid()
			self._sidebar_panels[panel_key].grid()
			self._sidebar_header_label.configure(text=self._get_sidebar_panel_label(panel_key))
			self._sidebar_hint_var.set(f"Sidebar: {self._get_sidebar_panel_label(panel_key)}")
			if panel_key == "search" and hasattr(self, "_search_entry"):
				self._search_entry.focus_set()
		else:
			self._sidebar_frame.grid_remove()
			self._sidebar_hint_var.set("Sidebar: Hidden")

		self._refresh_sidebar_activity_buttons()

	def _toggle_sidebar_panel(self, panel_key: str) -> None:
		"""Toggle the requested sidebar panel in a VS Code-like way."""
		if self._sidebar_visible and self._sidebar_active_panel == panel_key:
			self._show_sidebar_panel(panel_key, visible=False)
			return
		self._show_sidebar_panel(panel_key, visible=True)

	def _build_lines_only_surface(self) -> None:
		"""Build the migration-time handoff surface for Lines Only mode."""
		ttk.Label(
			self._lines_only_frame,
			text="Lines Only stays in the retained Full Table View during this migration slice.",
			wraplength=700,
			justify="left",
		).pack(anchor="w")

		self._handoff_var = tk.StringVar(value="Open the retained Lines Only surface.")
		ttk.Label(
			self._lines_only_frame,
			textvariable=self._handoff_var,
			wraplength=700,
			justify="left",
		).pack(anchor="w", pady=(12, 12))

		ttk.Button(
			self._lines_only_frame,
			text="Open Lines Only",
			command=self._open_lines_only_handoff,
		).pack(anchor="w")

	def _refresh_file_tree(self) -> None:
		"""Populate the file tree from the manifest filedir entries."""
		self._entry_by_rel_path = {
			_normalize_rel_path(entry.rel_path): entry for entry in self._mgr.get_filedir()
		}
		self._tree_item_to_rel_path.clear()
		if not hasattr(self, "_file_tree"):
			return

		self._file_tree.delete(*self._file_tree.get_children())
		folder_items: Dict[str, str] = {}
		for row in _build_file_tree_rows(self._entry_by_rel_path):
			parent = folder_items.get(row["parent_key"], "")
			item_id = self._file_tree.insert(
				parent,
				"end",
				text=row["text"],
				open=False,
			)
			if row["kind"] == "folder":
				folder_items[row["key"]] = item_id
				continue
			self._tree_item_to_rel_path[item_id] = row["rel_path"]

		if self._selected_rel_path in self._entry_by_rel_path:
			self._select_file_tree_row(self._selected_rel_path)

	def _select_first_file_if_available(self) -> None:
		"""Select the first available file when the host opens."""
		if not self._entry_by_rel_path:
			return
		self.set_selected_file(sorted(self._entry_by_rel_path)[0])

	def set_selected_file(self, rel_path: str) -> None:
		"""Update the active file context used by both Editor modes."""
		if rel_path not in self._entry_by_rel_path:
			return
		if rel_path == getattr(self, "_selected_rel_path", None):
			return

		self._capture_current_unsaved_buffer()

		self._selected_rel_path = rel_path
		self._selected_file_var.set(rel_path)

		if hasattr(self, "_file_tree"):
			self._select_file_tree_row(rel_path)

		if self._mode_var.get() == "full_files":
			self._load_selected_file()
		else:
			self._update_lines_only_text()

	def switch_mode(self, mode: str) -> None:
		"""Switch the visible host surface and trigger mode-specific handoff."""
		normalized = "lines_only" if mode == "lines_only" else "full_files"
		self._mode_var.set(normalized)
		self._show_current_mode()

	def _on_mode_changed(self) -> None:
		"""Handle the visible Full Files / Lines Only switch."""
		self._show_current_mode()

	def _show_current_mode(self) -> None:
		"""Show the active mode frame and perform any required handoff."""
		self._full_files_frame.pack_forget()
		self._lines_only_frame.pack_forget()

		if self._mode_var.get() == "lines_only":
			self._update_lines_only_text()
			self._lines_only_frame.pack(fill="both", expand=True)
			self._open_lines_only_handoff()
			return

		self._full_files_frame.pack(fill="both", expand=True)
		self._load_selected_file()

	def _update_lines_only_text(self) -> None:
		"""Update the migration handoff message for the currently selected file."""
		if self._selected_rel_path:
			message = f"Open Lines Only scoped to {self._selected_rel_path}."
			if self._current_locator_target is not None:
				message += f" Target {self._format_locator_target(self._current_locator_target)}."
			self._handoff_var.set(message)
		else:
			self._handoff_var.set("Open the retained Lines Only surface.")

	def _open_lines_only_handoff(self) -> None:
		"""Open or focus the retained Lines Only surface with shared file context."""
		kwargs: Dict[str, Any] = {
			"initial_file": self._selected_rel_path,
			"title": "Lines Only",
			"modal": False,
		}
		if self._current_locator_target is not None:
			kwargs["initial_locator"] = self._current_locator_target
		FullTableViewDialog.open_or_focus(
			self._parent,
			self._mgr,
			**kwargs,
		)

	def _on_tree_select(self, _event: tk.Event) -> None:
		"""Handle file-tree selection changes."""
		if self._suspend_file_tree_select:
			return
		selection = self._file_tree.selection()
		if not selection:
			return
		rel_path = self._tree_item_to_rel_path.get(selection[0])
		if rel_path is not None:
			self.set_selected_file(rel_path)

	def _select_file_tree_row(self, rel_path: str) -> None:
		"""Select a file-tree row without retriggering its selection binding."""
		for item_id, item_rel_path in self._tree_item_to_rel_path.items():
			if item_rel_path != rel_path:
				continue
			if self._file_tree.selection() == (item_id,):
				self._file_tree.focus(item_id)
				self._file_tree.see(item_id)
				return

			self._suspend_file_tree_select = True
			try:
				self._file_tree.selection_set(item_id)
				self._file_tree.focus(item_id)
				self._file_tree.see(item_id)
			finally:
				self.after_idle(self._clear_file_tree_select_guard)
			return

	def _clear_file_tree_select_guard(self) -> None:
		"""Release programmatic file-tree selection guard after Tk goes idle."""
		self._suspend_file_tree_select = False

	def _load_selected_file(self) -> None:
		"""Load the selected file into the editor and refresh aux views."""
		if self._selected_rel_path is None or self._selected_rel_path not in self._entry_by_rel_path:
			self._replace_editor_text("")
			self._set_diff_text("")
			self._set_patch_diff_text("")
			self._history_tree.delete(*self._history_tree.get_children())
			return

		current_text = getattr(self, "_unsaved_file_text_by_rel_path", {}).get(self._selected_rel_path)
		if current_text is None:
			view = self._mgr.get_editor_file_view(self._selected_rel_path)
			current_text = str(view.get("current_text", ""))
		else:
			view = self._mgr.get_editor_file_view(
				self._selected_rel_path,
				current_text=current_text,
			)
		self._replace_editor_text(current_text)
		self._refresh_aux_views(view)
		self._refresh_search_highlights()

	def _iter_search_file_payloads(self) -> Iterable[tuple[str, str, Iterable[Dict[str, Any]]]]:
		"""Yield ordered file text and locator metadata for the search sidebar."""
		options = self._search_sidebar.get_options() if hasattr(self, "_search_sidebar") else EditorSearchOptions()
		rel_paths = sorted(self._entry_by_rel_path, key=str.lower)
		if options.current_file_only:
			rel_paths = [self._selected_rel_path] if self._selected_rel_path else []
		include_locator_metadata = options.line_scope != LINE_SCOPE_ALL
		buffers = getattr(self, "_unsaved_file_text_by_rel_path", {})
		for rel_path in rel_paths:
			if rel_path == self._selected_rel_path and hasattr(self, "_editor_text"):
				current_text = self._editor_text.get("1.0", "end-1c")
				view = self._mgr.get_editor_search_file_payload(
					rel_path,
					current_text=current_text,
					include_locator_metadata=include_locator_metadata,
				)
			elif rel_path in buffers:
				current_text = buffers[rel_path]
				view = self._mgr.get_editor_search_file_payload(
					rel_path,
					current_text=current_text,
					include_locator_metadata=include_locator_metadata,
				)
			else:
				view = self._mgr.get_editor_search_file_payload(
					rel_path,
					include_locator_metadata=include_locator_metadata,
				)
				current_text = str(view.get("current_text", ""))
			yield rel_path, current_text, list(view.get("locator_metadata", []))

	def _select_search_result_match(self, match: EditorSearchMatch) -> None:
		"""Open the match's file and select the range in the editor buffer."""
		if match.rel_path != self._selected_rel_path:
			self.set_selected_file(match.rel_path)
		start_index = _text_offset_to_index(self._editor_text.get("1.0", "end-1c"), match.start)
		end_index = _text_offset_to_index(self._editor_text.get("1.0", "end-1c"), match.end)
		self._editor_text.tag_remove("sel", "1.0", "end")
		self._editor_text.tag_add("sel", start_index, end_index)
		self._editor_text.mark_set("insert", end_index)
		self._editor_text.see(start_index)
		if (start_index, end_index) in self._search_match_ranges:
			self._current_search_match_idx = self._search_match_ranges.index((start_index, end_index))

	def _replace_editor_text(self, text: str) -> None:
		"""Replace the editor buffer without leaving the modified flag set."""
		self._loading_editor_text = True
		try:
			self._editor_text.delete("1.0", "end")
			self._editor_text.insert("1.0", text)
			self._editor_text.edit_modified(False)
		finally:
			self._loading_editor_text = False
		self._current_search_index = "1.0"
		self._schedule_line_number_refresh()
		self._refresh_search_highlights()

	def _set_diff_text(self, text: str) -> None:
		"""Replace the diff buffer contents."""
		self._diff_text.delete("1.0", "end")
		self._diff_text.insert("1.0", text)

	def _set_patch_diff_text(self, text: str) -> None:
		"""Replace the patch-diff buffer contents."""
		self._patch_diff_text.delete("1.0", "end")
		self._patch_diff_text.insert("1.0", text)

	def _refresh_aux_views(self, view: Dict[str, object]) -> None:
		"""Refresh the diff and line-history panes from shared backend data."""
		self._set_diff_text(str(view.get("diff_to_original", "")))
		self._set_patch_diff_text(str(view.get("diff_to_patch", "")))

		self._locator_metadata = list(view.get("locator_metadata", []))
		self._apply_locator_highlights(self._locator_metadata)

		self._history_tree.delete(*self._history_tree.get_children())
		self._line_history_by_idx = {}
		for row in view.get("line_history", []):
			idx = _coerce_optional_int(row.get("idx"))
			if idx is not None:
				self._line_history_by_idx[idx] = row
			self._history_tree.insert(
				"",
				"end",
				iid=str(row.get("idx", "")),
				values=(
					row.get("idx", ""),
					row.get("ln", ""),
					row.get("f", ""),
					row.get("status", "all"),
					row.get("original", ""),
					row.get("translated", ""),
					row.get("current", ""),
				),
			)

		if self._current_locator_target is not None:
			self.set_locator_target(self._current_locator_target)
		else:
			first_target = next(
				(
					{
						"idx": metadata.get("idx"),
						"ln": metadata.get("ln"),
						**({"f": metadata.get("f")} if "f" in metadata else {}),
					}
					for metadata in self._locator_metadata
					if metadata.get("matched")
				),
				None,
			)
			self.set_locator_target(first_target)

	def _apply_locator_highlights(self, locator_metadata: list[Dict[str, Any]]) -> None:
		"""Highlight matched editor lines that have manifest locator ownership."""
		self._locator_ranges_by_idx.clear()
		self._editor_text.tag_remove("locator_match", "1.0", "end")
		self._editor_text.tag_remove("locator_active", "1.0", "end")
		for metadata in locator_metadata:
			if not metadata.get("matched"):
				continue
			editor_ln = _coerce_optional_int(metadata.get("editor_ln"))
			idx = _coerce_optional_int(metadata.get("idx"))
			if editor_ln is None or idx is None:
				continue
			line_count = max(1, _coerce_optional_int(metadata.get("editor_line_count")) or 1)
			start = f"{editor_ln}.0"
			end = f"{editor_ln + line_count - 1}.0 lineend +1c"
			self._editor_text.tag_add("locator_match", start, end)
			self._locator_ranges_by_idx.setdefault(idx, []).append((editor_ln, line_count))

	def set_locator_target(self, target: Optional[Dict[str, Any]]) -> None:
		"""Set the active locator target for highlighting and Lines Only handoff."""
		if target is None:
			self._current_locator_target = None
			self._editor_text.tag_remove("locator_active", "1.0", "end")
			self._locator_var.set("Locator: none")
			self._update_lines_only_text()
			return

		normalized: Dict[str, Any] = {}
		for key in ("idx", "ln", "f"):
			value = _coerce_optional_int(target.get(key))
			if value is not None:
				normalized[key] = value
		self._current_locator_target = normalized or None

		self._editor_text.tag_remove("locator_active", "1.0", "end")
		if self._current_locator_target is not None:
			idx = _coerce_optional_int(self._current_locator_target.get("idx"))
			if idx is not None:
				locator_ranges = list(self._locator_ranges_by_idx.get(idx, []))
				if not locator_ranges:
					history_row = self._line_history_by_idx.get(idx, {})
					target_ln = _coerce_optional_int(self._current_locator_target.get("ln"))
					if target_ln is not None:
						locator_ranges.append(
							(
								target_ln,
								max(
									1,
									_coerce_optional_int(history_row.get("line_count")) or 1,
								),
							)
						)
				for editor_ln, line_count in locator_ranges:
					start = f"{editor_ln}.0"
					end = f"{editor_ln + line_count - 1}.0 lineend +1c"
					self._editor_text.tag_add("locator_active", start, end)
				self._select_history_row(idx)

		if self._current_locator_target is None:
			self._locator_var.set("Locator: none")
		else:
			self._locator_var.set(
				"Locator: " + self._format_locator_target(self._current_locator_target)
			)
		self._update_lines_only_text()

	def _format_locator_target(self, target: Dict[str, Any]) -> str:
		"""Return a compact ``idx``/``ln``/``f`` label for the active locator."""
		parts = []
		for key in ("idx", "ln", "f"):
			value = target.get(key)
			if value is not None:
				parts.append(f"{key}={value}")
		return "  ".join(parts) if parts else "none"

	def _on_history_tree_select(self, _event: tk.Event) -> None:
		"""Set the active locator target from the selected history row."""
		if self._suspend_history_tree_select:
			return
		selection = self._history_tree.selection()
		if not selection:
			return
		idx = _coerce_optional_int(selection[0])
		if idx is None:
			return
		for row in self._mgr.get_lines_for_locator_target(rel_path=self._selected_rel_path, idx=idx):
			target: Dict[str, Any] = {"idx": idx, "ln": row.get("ln")}
			if "f" in row:
				target["f"] = row.get("f")
			self.set_locator_target(target)
			break

	def _select_history_row(self, idx: int) -> None:
		"""Select a history row without retriggering locator promotion loops."""
		if not hasattr(self, "_history_tree"):
			return
		row_id = str(idx)
		if self._history_tree.selection() == (row_id,):
			try:
				self._history_tree.focus(row_id)
				self._history_tree.see(row_id)
			except tk.TclError:
				pass
			return

		self._suspend_history_tree_select = True
		try:
			self._history_tree.selection_set(row_id)
			self._history_tree.focus(row_id)
			self._history_tree.see(row_id)
		except tk.TclError:
			pass
		finally:
			self.after_idle(self._clear_history_tree_select_guard)

	def _clear_history_tree_select_guard(self) -> None:
		"""Release the programmatic history-selection guard after Tk goes idle."""
		self._suspend_history_tree_select = False

	def _on_editor_cursor_changed(self, _event: tk.Event) -> None:
		"""Promote the locator target that owns the current editor line."""
		self._schedule_line_number_refresh()
		line_number = _coerce_optional_int(self._editor_text.index("insert").split(".", 1)[0])
		if line_number is None:
			return
		for metadata in self._locator_metadata:
			if not metadata.get("matched"):
				continue
			start_line = _coerce_optional_int(metadata.get("editor_ln"))
			line_count = max(1, _coerce_optional_int(metadata.get("editor_line_count")) or 1)
			if start_line is None or not (start_line <= line_number < start_line + line_count):
				continue
			target: Dict[str, Any] = {"idx": metadata.get("idx"), "ln": metadata.get("ln")}
			if "f" in metadata:
				target["f"] = metadata.get("f")
			self.set_locator_target(target)
			return

	def _get_staged_current_text(self, rel_path: str) -> str:
		"""Return the saved/staged editor text for one manifest file."""
		view = self._mgr.get_editor_search_file_payload(rel_path, include_locator_metadata=False)
		return str(view.get("current_text", ""))

	def _set_unsaved_buffer_for_rel_path(self, rel_path: str, text: str) -> None:
		"""Track or clear one in-memory editor buffer against the staged baseline."""
		buffers = getattr(self, "_unsaved_file_text_by_rel_path", None)
		if buffers is None:
			self._unsaved_file_text_by_rel_path = {}
			buffers = self._unsaved_file_text_by_rel_path
		try:
			staged_text = self._get_staged_current_text(rel_path)
		except Exception:
			staged_text = None
		if staged_text is not None and text == staged_text:
			buffers.pop(rel_path, None)
		else:
			buffers[rel_path] = text

	def _capture_current_unsaved_buffer(self) -> None:
		"""Copy the visible editor text into the in-memory buffer map if needed."""
		rel_path = getattr(self, "_selected_rel_path", None)
		if rel_path is None or rel_path not in getattr(self, "_entry_by_rel_path", {}):
			return
		if not hasattr(self, "_editor_text"):
			return
		current_text = self._editor_text.get("1.0", "end-1c")
		self._set_unsaved_buffer_for_rel_path(rel_path, current_text)

	def _on_editor_modified(self, _event: tk.Event) -> None:
		"""Refresh auxiliary views when the visible editor buffer changes."""
		if not self._editor_text.edit_modified():
			return
		self._editor_text.edit_modified(False)
		if getattr(self, "_loading_editor_text", False):
			return
		self._schedule_line_number_refresh()
		self._schedule_search_highlight_refresh(refresh_results=False)
		if self._selected_rel_path is None or self._selected_rel_path not in self._entry_by_rel_path:
			return
		current_text = self._editor_text.get("1.0", "end-1c")
		self._set_unsaved_buffer_for_rel_path(self._selected_rel_path, current_text)
		view = self._mgr.get_editor_file_view(
			self._selected_rel_path,
			current_text=current_text,
		)
		self._refresh_aux_views(view)

	def _save_current_file(self) -> None:
		"""Persist the current Full Files buffer through the staged save pipeline."""
		if self._selected_rel_path is None or self._selected_rel_path not in self._entry_by_rel_path:
			messagebox.showinfo("Save", "No file selected.")
			return

		change_label = simpledialog.askstring(
			"Save",
			"Optional change label:",
			parent=self,
			initialvalue="",
		)
		if change_label is None:
			return

		current_text = self._editor_text.get("1.0", "end-1c")
		result = self._mgr.save_editor_patch(
			self._selected_rel_path,
			current_text,
			change_label=change_label.strip(),
		)
		getattr(self, "_unsaved_file_text_by_rel_path", {}).pop(self._selected_rel_path, None)
		self._load_selected_file()
		patch_info = result.get("patch_info", {})
		patch_decision = patch_info.get("decision", "missing") if isinstance(patch_info, dict) else "missing"
		messagebox.showinfo(
			"Save",
			f"Saved {self._selected_rel_path} to staged translated output. "
			f"Rollback artifact: {patch_decision}.",
		)

	def _on_save_shortcut(self, _event: tk.Event) -> str:
		"""Handle the standard editor save shortcut."""
		self._save_current_file()
		return "break"

	def _get_search_query(self) -> str:
		"""Return the current editor search query."""
		return self._get_search_options().query

	def _search_uses_regex(self) -> bool:
		"""Return whether editor search should treat the query as a regex."""
		return self._get_search_options().use_regex

	def _get_search_options(self) -> EditorSearchOptions:
		"""Return the current sidebar search options."""
		if hasattr(self, "_search_sidebar"):
			return self._search_sidebar.get_options()
		return EditorSearchOptions(
			query=self._search_var.get().strip() if hasattr(self, "_search_var") else "",
			replace=self._replace_var.get() if hasattr(self, "_replace_var") else "",
			use_regex=bool(self._search_regex_var.get()) if hasattr(self, "_search_regex_var") else False,
			case_sensitive_search=True,
			case_sensitive_replace=True,
		)

	def _cancel_pending_search_highlight_refresh(self) -> None:
		"""Cancel any queued debounced search-highlight refresh."""
		if self._search_highlight_after_id is None:
			return
		try:
			self.after_cancel(self._search_highlight_after_id)
		except tk.TclError:
			pass
		self._search_highlight_after_id = None

	def _schedule_search_from_sidebar_change(self) -> None:
		"""Debounce highlighting and cross-file results after search controls change."""
		self._schedule_search_highlight_refresh(refresh_results=True)

	def _run_search_from_sidebar(self) -> None:
		"""Run a search immediately from the sidebar's explicit search action."""
		self._cancel_pending_search_highlight_refresh()
		self._refresh_search_highlights()
		if hasattr(self, "_search_sidebar"):
			self._search_sidebar.refresh_results()

	def _schedule_search_highlight_refresh(
		self,
		_event: Optional[tk.Event] = None,
		*,
		refresh_results: bool = False,
	) -> None:
		"""Debounce search highlighting so fast typing does not thrash the editor UI."""
		if not hasattr(self, "after"):
			return
		self._refresh_search_results_after_highlight = bool(refresh_results)
		self._cancel_pending_search_highlight_refresh()
		self._search_highlight_after_id = self.after(1000, self._run_search_highlight_refresh)

	def _run_search_highlight_refresh(self) -> None:
		"""Execute the queued debounced search-highlight refresh."""
		self._search_highlight_after_id = None
		self._refresh_search_highlights()
		refresh_results = getattr(self, "_refresh_search_results_after_highlight", False)
		self._refresh_search_results_after_highlight = False
		if refresh_results and hasattr(self, "_search_sidebar"):
			self._search_sidebar.refresh_results()

	def _refresh_search_highlights(self) -> list[tuple[str, str]]:
		"""Recompute and paint all current search matches in the editor buffer."""
		if not hasattr(self, "_editor_text"):
			return []

		options = self._get_search_options()
		query = options.query
		use_regex = options.use_regex
		self._editor_text.tag_remove("search_match", "1.0", "end")
		self._search_match_ranges = []
		self._search_match_query = query
		self._search_match_use_regex = use_regex
		self._current_search_match_idx = -1
		if not query:
			return []

		current_text = self._editor_text.get("1.0", "end-1c")
		selected_rel_path = getattr(self, "_selected_rel_path", None)
		if selected_rel_path:
			current_results = search_editor_files(
				[(selected_rel_path, current_text, getattr(self, "_locator_metadata", []))],
				options,
			)
			match_ranges = [
				(_text_offset_to_index(current_text, match.start), _text_offset_to_index(current_text, match.end))
				for result in current_results
				for match in result.matches
			]
		else:
			match_ranges = find_search_match_ranges(current_text, options)
		self._search_match_ranges = match_ranges
		for start_index, end_index in match_ranges:
			self._editor_text.tag_add("search_match", start_index, end_index)

		ranges = self._editor_text.tag_ranges("sel")
		if len(ranges) == 2:
			selected_range = (str(ranges[0]), str(ranges[1]))
			if selected_range in match_ranges:
				self._current_search_match_idx = match_ranges.index(selected_range)
		return match_ranges

	def _ensure_search_match_ranges(self) -> list[tuple[str, str]]:
		"""Return up-to-date search ranges, forcing refresh when the query changed."""
		options = self._get_search_options()
		query = options.query
		use_regex = options.use_regex
		if (
			query == self._search_match_query
			and use_regex == self._search_match_use_regex
			and (self._search_match_ranges or not query)
		):
			return self._search_match_ranges
		self._cancel_pending_search_highlight_refresh()
		return self._refresh_search_highlights()

	def _select_search_match(self, match_idx: int, *, insert_at_end: bool) -> None:
		"""Select one search match and make sure it is visible."""
		if not (0 <= match_idx < len(self._search_match_ranges)):
			return
		start_index, end_index = self._search_match_ranges[match_idx]
		self._editor_text.tag_remove("sel", "1.0", "end")
		self._editor_text.tag_add("sel", start_index, end_index)
		self._editor_text.mark_set("insert", end_index if insert_at_end else start_index)
		self._editor_text.see(start_index)
		self._current_search_match_idx = match_idx
		self._current_search_index = end_index if insert_at_end else start_index

	def _get_active_search_match_index(self) -> Optional[int]:
		"""Return the selected or last-navigated search match index."""
		match_ranges = self._ensure_search_match_ranges()
		if not match_ranges:
			return None
		ranges = self._editor_text.tag_ranges("sel")
		if len(ranges) == 2:
			selected_range = (str(ranges[0]), str(ranges[1]))
			if selected_range in match_ranges:
				return match_ranges.index(selected_range)
		if 0 <= self._current_search_match_idx < len(match_ranges):
			return self._current_search_match_idx
		return 0

	def _resolve_current_replacement_text(self, matched_text: str) -> Optional[str]:
		"""Return the replacement text for one selected search match."""
		options = self._get_search_options()
		if not options.use_regex:
			return options.replace
		new_text, replacement_count = replace_all(matched_text, options)
		return new_text if replacement_count else None

	def _search_next(self) -> None:
		"""Jump to the next match in the current editor buffer."""
		if not self._get_search_query():
			return
		match_ranges = self._ensure_search_match_ranges()
		if not match_ranges:
			return
		next_match_idx = (self._current_search_match_idx + 1) % len(match_ranges)
		self._select_search_match(next_match_idx, insert_at_end=True)

	def _search_previous(self) -> None:
		"""Jump to the previous match in the current editor buffer."""
		if not self._get_search_query():
			return
		match_ranges = self._ensure_search_match_ranges()
		if not match_ranges:
			return
		if self._current_search_match_idx < 0:
			previous_match_idx = len(match_ranges) - 1
		else:
			previous_match_idx = (self._current_search_match_idx - 1) % len(match_ranges)
		self._select_search_match(previous_match_idx, insert_at_end=False)

	def _replace_current(self) -> None:
		"""Replace the selected match, or the next match if none is active."""
		if not self._get_search_query():
			return
		match_idx = self._get_active_search_match_index()
		if match_idx is None:
			return
		start_index, end_index = self._search_match_ranges[match_idx]
		replacement_text = self._resolve_current_replacement_text(
			self._editor_text.get(start_index, end_index)
		)
		if replacement_text is None:
			return

		self._editor_text.delete(start_index, end_index)
		self._editor_text.insert(start_index, replacement_text)
		if getattr(self, "_selected_rel_path", None) is not None:
			self._set_unsaved_buffer_for_rel_path(
				self._selected_rel_path,
				self._editor_text.get("1.0", "end-1c"),
			)
		new_end = f"{start_index}+{len(replacement_text)}c"
		self._editor_text.tag_remove("sel", "1.0", "end")
		self._editor_text.tag_add("sel", start_index, new_end)
		self._editor_text.mark_set("insert", new_end)
		self._editor_text.see(start_index)
		self._current_search_index = new_end
		self._refresh_search_highlights()
		if (start_index, new_end) in self._search_match_ranges:
			self._current_search_match_idx = self._search_match_ranges.index((start_index, new_end))

	def _replace_all(self) -> None:
		"""Replace all matches in the current editor buffer."""
		options = self._get_search_options()
		query = options.query
		if not query:
			return
		current_text = self._editor_text.get("1.0", "end-1c")
		new_text, replacement_count = replace_all_scoped(
			current_text,
			options,
			parsed_lines=parsed_line_numbers(getattr(self, "_locator_metadata", [])),
		)

		if replacement_count:
			self._editor_text.delete("1.0", "end")
			self._editor_text.insert("1.0", new_text)
			if getattr(self, "_selected_rel_path", None) is not None:
				self._set_unsaved_buffer_for_rel_path(self._selected_rel_path, new_text)
			self._current_search_index = "1.0"
			self._refresh_search_highlights()
			if hasattr(self, "_search_sidebar"):
				self._search_sidebar.refresh_results()

			messagebox.showinfo(
				"Replace",
				f"Replaced {replacement_count} occurrence(s) in the current file.",
				parent=self,
			)

	def _replace_all_found_files(self) -> None:
		"""Replace all matches across every file in the current search result set."""
		options = self._get_search_options()
		if not options.query:
			return

		payloads = list(self._iter_search_file_payloads())
		results = search_editor_files(payloads, options)
		if not results:
			return

		payload_by_rel_path = {
			rel_path: (text, list(locator_metadata))
			for rel_path, text, locator_metadata in payloads
		}
		total_replacements = 0
		replaced_files = 0
		selected_new_text: Optional[str] = None

		for result in results:
			payload = payload_by_rel_path.get(result.rel_path)
			if payload is None:
				continue
			current_text, locator_metadata = payload
			new_text, replacement_count = replace_all_scoped(
				current_text,
				options,
				parsed_lines=parsed_line_numbers(locator_metadata),
			)
			if not replacement_count:
				continue
			total_replacements += replacement_count
			replaced_files += 1
			self._set_unsaved_buffer_for_rel_path(result.rel_path, new_text)
			if result.rel_path == self._selected_rel_path:
				selected_new_text = new_text

		if not total_replacements:
			return

		if selected_new_text is not None:
			self._editor_text.delete("1.0", "end")
			self._editor_text.insert("1.0", selected_new_text)
			self._current_search_index = "1.0"
			view = self._mgr.get_editor_file_view(
				self._selected_rel_path,
				current_text=selected_new_text,
			)
			self._refresh_aux_views(view)
			self._refresh_search_highlights()

		if hasattr(self, "_search_sidebar"):
			self._search_sidebar.refresh_results()

		messagebox.showinfo(
			"Replace",
			f"Replaced {total_replacements} occurrence(s) across {replaced_files} file(s).",
			parent=self,
		)

	def _show_editor_context_menu(self, event: tk.Event) -> str:
		"""Open the Full Files text-selection context menu."""
		menu = tk.Menu(self, tearoff=False)
		has_selection = self._get_editor_selection_span() is not None
		try:
			if not has_selection:
				index = self._editor_text.index(f"@{event.x},{event.y}")
				self._editor_text.mark_set("insert", index)
		except tk.TclError:
			pass

		menu.add_command(label="Cut", command=lambda: self._editor_text.event_generate("<<Cut>>"))
		menu.add_command(label="Copy", command=lambda: self._editor_text.event_generate("<<Copy>>"))
		menu.add_command(label="Paste", command=lambda: self._editor_text.event_generate("<<Paste>>"))

		if has_selection:
			menu.add_separator()
			menu.add_command(label="Cycle through translation history", command=self._open_selection_history_cycle)
			translate_menu = tk.Menu(menu, tearoff=False)
			model_label = self._get_selected_translation_model_label()
			translate_menu.add_command(label=f"Model: {model_label}", state="disabled")
			translate_menu.add_separator()
			translate_menu.add_command(label="Simple", command=lambda: self._translate_editor_selection("simple"))
			translate_menu.add_command(label="Comprehensive", command=lambda: self._translate_editor_selection("comprehensive"))
			translate_menu.add_command(label="Explain only", command=self._explain_editor_selection)

			span_candidates = self._get_selection_span_candidates()
			if span_candidates:
				span_menu = tk.Menu(translate_menu, tearoff=False)
				for idx, candidate in enumerate(span_candidates, start=1):
					preview = json.dumps(candidate.content[:60], ensure_ascii=False)
					if len(candidate.content) > 60:
						preview = preview[:-1] + '..."'
					item_menu = tk.Menu(span_menu, tearoff=False)
					item_menu.add_command(
						label="Simple",
						command=lambda span=candidate: self._translate_editor_selection("simple", span_candidate=span),
					)
					item_menu.add_command(
						label="Comprehensive",
						command=lambda span=candidate: self._translate_editor_selection(
							"comprehensive",
							span_candidate=span,
						),
					)
					span_menu.add_cascade(
						label=f"{idx}. {candidate.open_char}{preview}{candidate.close_char}",
						menu=item_menu,
					)
				translate_menu.add_cascade(label="Translate within Span", menu=span_menu)

			menu.add_cascade(label="Translate", menu=translate_menu)

		try:
			menu.tk_popup(event.x_root, event.y_root)
		finally:
			menu.grab_release()
		return "break"

	def _get_editor_selection_span(self) -> Optional[EditorSelectionSpan]:
		"""Return the current selected editor span as offsets."""
		try:
			ranges = self._editor_text.tag_ranges("sel")
		except tk.TclError:
			return None
		if len(ranges) != 2:
			return None
		start_index = str(ranges[0])
		end_index = str(ranges[1])
		if self._editor_text.compare(start_index, ">=", end_index):
			return None
		current_text = self._editor_text.get("1.0", "end-1c")
		start_offset = self._editor_index_to_offset(start_index)
		end_offset = self._editor_index_to_offset(end_index)
		return EditorSelectionSpan(
			start_offset=start_offset,
			end_offset=end_offset,
			text=current_text[start_offset:end_offset],
		)

	def _editor_index_to_offset(self, index: str) -> int:
		"""Convert a Tk text index to a character offset."""
		try:
			count = self._editor_text.count("1.0", index, "chars")
		except tk.TclError:
			count = None
		if count:
			return int(count[0])
		if hasattr(self._editor_text, "_index_to_offset"):
			return int(self._editor_text._index_to_offset(index))
		return 0

	def _offset_to_editor_index(self, offset: int) -> str:
		"""Convert a character offset to a Tk text index."""
		try:
			return self._editor_text.index(f"1.0+{max(0, int(offset))}c")
		except tk.TclError:
			current_text = self._editor_text.get("1.0", "end-1c")
			return _text_offset_to_index(current_text, max(0, int(offset)))

	def _replace_editor_span(self, span: EditorSelectionSpan, replacement: str) -> None:
		"""Replace one editor offset span and select the inserted text."""
		start_index = self._offset_to_editor_index(span.start_offset)
		end_index = self._offset_to_editor_index(span.end_offset)
		self._editor_text.delete(start_index, end_index)
		self._editor_text.insert(start_index, replacement)
		new_end = self._offset_to_editor_index(span.start_offset + len(replacement))
		self._editor_text.tag_remove("sel", "1.0", "end")
		self._editor_text.tag_add("sel", start_index, new_end)
		self._editor_text.mark_set("insert", new_end)
		self._editor_text.see(start_index)
		self._refresh_live_editor_views()

	def _refresh_live_editor_views(self) -> None:
		"""Refresh diffs, locators, search, and line numbers after direct buffer edits."""
		self._schedule_line_number_refresh()
		self._schedule_search_highlight_refresh()
		if self._selected_rel_path is None or self._selected_rel_path not in self._entry_by_rel_path:
			return
		current_text = self._editor_text.get("1.0", "end-1c")
		self._set_unsaved_buffer_for_rel_path(self._selected_rel_path, current_text)
		view = self._mgr.get_editor_file_view(
			self._selected_rel_path,
			current_text=current_text,
		)
		self._refresh_aux_views(view)

	def _get_selection_span_candidates(self) -> list[EditorSpanCandidate]:
		"""Return balanced containing spans for the current selection."""
		selection = self._get_editor_selection_span()
		if selection is None:
			return []
		current_text = self._editor_text.get("1.0", "end-1c")
		return _balanced_span_candidates(current_text, selection.start_offset, selection.end_offset)

	def _open_selection_history_cycle(self) -> None:
		"""Open a small control popup for cycling selected span versions."""
		selection = self._get_editor_selection_span()
		if selection is None:
			return
		candidates = self._build_selection_history_candidates(selection)
		if not candidates:
			messagebox.showinfo("History", "No alternate text found for this span.", parent=self)
			return

		state = {
			"index": 0,
			"span": selection,
			"initial": selection.text,
			"candidates": candidates,
		}
		dialog = tk.Toplevel(self)
		dialog.title("Selection History")
		dialog.transient(self)
		dialog.resizable(True, True)
		container = ttk.Frame(dialog, padding=10)
		container.pack(fill="both", expand=True)
		label_var = tk.StringVar(value="")
		ttk.Label(container, textvariable=label_var).pack(anchor="w")
		preview = tk.Text(container, height=8, width=70, wrap="word")
		preview.pack(fill="both", expand=True, pady=(8, 8))
		buttons = ttk.Frame(container)
		buttons.pack(fill="x")

		def _show_candidate() -> None:
			candidate = state["candidates"][state["index"]]
			label_var.set(f"{candidate.label} ({state['index'] + 1}/{len(state['candidates'])})")
			preview.delete("1.0", "end")
			preview.insert("1.0", candidate.text)

		def _move(delta: int) -> None:
			state["index"] = (state["index"] + delta) % len(state["candidates"])
			_show_candidate()

		def _set_candidate() -> None:
			candidate = state["candidates"][state["index"]]
			current_span = EditorSelectionSpan(
				start_offset=state["span"].start_offset,
				end_offset=state["span"].end_offset,
				text=self._editor_text.get(
					self._offset_to_editor_index(state["span"].start_offset),
					self._offset_to_editor_index(state["span"].end_offset),
				),
			)
			self._replace_editor_span(current_span, candidate.text)
			state["span"] = EditorSelectionSpan(
				start_offset=current_span.start_offset,
				end_offset=current_span.start_offset + len(candidate.text),
				text=candidate.text,
			)

		def _restore_initial() -> None:
			current_span = EditorSelectionSpan(
				start_offset=state["span"].start_offset,
				end_offset=state["span"].end_offset,
				text=self._editor_text.get(
					self._offset_to_editor_index(state["span"].start_offset),
					self._offset_to_editor_index(state["span"].end_offset),
				),
			)
			self._replace_editor_span(current_span, state["initial"])
			dialog.destroy()

		ttk.Button(buttons, text="<", width=4, command=lambda: _move(-1)).pack(side="left")
		ttk.Button(buttons, text=">", width=4, command=lambda: _move(1)).pack(side="left", padx=(6, 0))
		ttk.Button(buttons, text="✓", width=4, command=_set_candidate).pack(side="right")
		ttk.Button(buttons, text="x", width=4, command=_restore_initial).pack(side="right", padx=(0, 6))
		_show_candidate()

	def _build_selection_history_candidates(self, selection: EditorSelectionSpan) -> list[EditorSelectionSpan]:
		"""Build same-offset history candidates from Original, saved, and current views."""
		if self._selected_rel_path is None:
			return []
		current_text = self._editor_text.get("1.0", "end-1c")
		live_view = self._mgr.get_editor_file_view(self._selected_rel_path, current_text=current_text)
		saved_view = self._mgr.get_editor_file_view(self._selected_rel_path)
		sources = [
			("Initial", current_text),
			("Original", str(live_view.get("original_text", ""))),
			("Saved final", str(saved_view.get("current_text", ""))),
		]
		candidates: list[EditorSelectionSpan] = []
		seen: set[str] = set()
		for label, source_text in sources:
			if selection.end_offset > len(source_text):
				continue
			value = source_text[selection.start_offset:selection.end_offset]
			if value in seen:
				continue
			seen.add(value)
			candidates.append(
				EditorSelectionSpan(
					start_offset=selection.start_offset,
					end_offset=selection.end_offset,
					text=value,
					label=label,
				)
			)
		return candidates

	def _translate_editor_selection(
		self,
		mode: str,
		*,
		span_candidate: Optional[EditorSpanCandidate] = None,
	) -> None:
		"""Translate the selected span in a background thread."""
		selection = self._get_editor_selection_span()
		if selection is None:
			return
		target_span = selection
		if span_candidate is not None:
			target_span = EditorSelectionSpan(
				start_offset=span_candidate.content_start,
				end_offset=span_candidate.content_end,
				text=span_candidate.content,
			)
		if not target_span.text.strip():
			return
		self._run_selection_llm_request(
			target_span,
			mode=mode,
			on_success=lambda result, span=target_span: self._replace_editor_span(span, result),
		)

	def _explain_editor_selection(self) -> None:
		"""Ask the LLM for a concise explanation and show it in a non-modal popup."""
		selection = self._get_editor_selection_span()
		if selection is None or not selection.text.strip():
			return
		dialog = tk.Toplevel(self)
		dialog.title("Explanation")
		dialog.transient(self)
		dialog.resizable(True, True)
		text = tk.Text(dialog, height=12, width=70, wrap="word")
		text.pack(fill="both", expand=True, padx=10, pady=10)
		text.insert("1.0", "Please Wait")

		def _show_explanation(result: str) -> None:
			if not dialog.winfo_exists():
				return
			text.delete("1.0", "end")
			text.insert("1.0", result)

		self._run_selection_llm_request(selection, mode="explain", on_success=_show_explanation)

	def _run_selection_llm_request(
		self,
		span: EditorSelectionSpan,
		*,
		mode: str,
		on_success: Callable[[str], None],
	) -> None:
		"""Execute one selection LLM request on a worker thread."""
		try:
			request = self._build_selection_llm_request(span, mode)
		except Exception as exc:
			messagebox.showerror("Translate", str(exc), parent=self)
			return

		def _worker() -> None:
			try:
				result = self._execute_selection_llm_request(request["system"], request["user"])
			except Exception as exc:
				self.after(0, lambda error=exc: messagebox.showerror("Translate", str(error), parent=self))
				return
			self.after(0, lambda value=result: on_success(value))

		threading.Thread(target=_worker, daemon=True).start()

	def _build_selection_llm_request(self, span: EditorSelectionSpan, mode: str) -> Dict[str, str]:
		"""Build system/user text for a selection translation request."""
		source_lang = self._get_manifest_language("source_language", "Japanese")
		target_lang = self._get_manifest_language("target_language", "English")
		if mode == "simple":
			system = (
				f"Translate from {source_lang} to {target_lang}. "
				"Return only the translated text, with no markdown or explanation."
			)
			user = span.text
		elif mode == "explain":
			system = "Concisely explain the selected text. Return only the explanation."
			user = span.text
		else:
			current_text = self._editor_text.get("1.0", "end-1c")
			radius = self._get_selection_context_radius()
			context_lines = _line_context_for_offsets(
				current_text,
				span.start_offset,
				span.end_offset,
				radius,
			)
			rolling_context = "\n".join(context_lines)
			try:
				from CherryAI.gui.helpers.prompt_adapter import gather_prompt_data, build_request_prompt

				prompt_data = gather_prompt_data(self._mgr, sample_lines=[span.text])
				system, _breakdown = build_request_prompt(
					prompt_data,
					chunk_lines=[span.text],
					rolling_context_text=rolling_context,
					code_patterns=prompt_data.get("code_patterns"),
				)
			except Exception:
				system = ""
			if not system:
				system = (
					f"You are a professional translator translating from {source_lang} to {target_lang}. "
					"Use the surrounding context only for meaning. Return only the translated selected text."
				)
			user = (
				"Translate only the selected text.\n\n"
				f"Selected text:\n{span.text}\n\n"
				f"Surrounding context:\n{rolling_context}"
			)
		return {"system": system, "user": user}

	def _execute_selection_llm_request(self, system_prompt: str, user_content: str) -> str:
		"""Run a selection request through the standard API client configuration."""
		from CherryAI.functions.api_client import APIClient, APIConfig, TranslationError
		from CherryAI.functions.api_config import PROVIDER_BASE_URLS, get_api_key_plain
		from CherryAI.functions.llm_request import send_chat_completion

		options = self._mgr.get_request_options() if self._mgr is not None else {}
		provider = str(options.get("ApiKeyProvider", "") or "").strip().lower()
		key_name = str(options.get("ApiKeyName", "") or "").strip()
		model = str(options.get("Model", "") or "").strip()
		if not model:
			raise TranslationError("No translation model is selected in Request Options.")
		if not provider:
			provider = "openai"
		api_key = get_api_key_plain(provider, key_name or "default") or ""
		is_local = provider in _LOCAL_API_PROVIDERS
		if not api_key and not is_local:
			raise TranslationError("No API key is selected for the translation provider.")

		client = APIClient(
			enable_api_log=True,
			initial_config=APIConfig(
				provider=provider,
				api_key=api_key or "local",
				base_url=PROVIDER_BASE_URLS.get(provider) or None,
				model=model,
				temperature=float(options.get("Temperature", 0.2) or 0.2),
				retries=int(options.get("MaxRetries", 3) or 3),
				cache_enabled=self._coerce_bool_option(options.get("EnableRequestCaching", True), True),
				no_api_key=is_local,
				source_lang=self._get_manifest_language("source_language", "Japanese"),
				target_lang=self._get_manifest_language("target_language", "English"),
			),
		)
		if not client.client:
			raise TranslationError("API Client not initialized.")

		client._raise_if_model_blocked()
		result = send_chat_completion(
			provider=provider,
			api_key=api_key,
			base_url=client.config.base_url,
			model=client.config.model,
			messages=[
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": user_content},
			],
			temperature=client.config.temperature,
		)
		content = result.content
		if not content:
			raise TranslationError("Empty response from translation model.")
		return str(content).strip()

	def _coerce_bool_option(self, value: Any, default: bool) -> bool:
		"""Coerce manifest/API option values to bool."""
		if isinstance(value, bool):
			return value
		if value is None:
			return default
		if isinstance(value, (int, float)):
			return bool(value)
		if isinstance(value, str):
			text = value.strip().lower()
			if text in {"1", "true", "yes", "on"}:
				return True
			if text in {"0", "false", "no", "off"}:
				return False
		return default

	def _get_selected_translation_model_label(self) -> str:
		"""Return the selected Translation-step model label."""
		try:
			options = self._mgr.get_request_options()
		except Exception:
			options = {}
		model = str(options.get("Model", "") or "").strip()
		provider = str(options.get("ApiKeyProvider", "") or "").strip()
		if provider and model:
			return f"{provider}.{model}"
		return model or "(none)"

	def _get_manifest_language(self, field_name: str, fallback: str) -> str:
		"""Return an Information metadata language field."""
		if self._mgr is not None and getattr(self._mgr, "is_loaded", False):
			value = str(self._mgr.get_info_metadata_field(field_name, fallback) or "").strip()
			if value:
				return value
			metadata = self._mgr.get_step_data_value(2, "metadata", {})
			if isinstance(metadata, dict):
				value = str(metadata.get(field_name, fallback) or "").strip()
				if value:
					return value
		return fallback

	def _get_selection_context_radius(self) -> int:
		"""Return the largest configured rolling context line radius."""
		try:
			from CherryAI.functions.api_config import get_model_settings

			model = str(self._mgr.get_request_options().get("Model", "") or "")
			settings = get_model_settings(model) if model else {}
		except Exception:
			settings = {}
		values = []
		for key in ("rolling_context_before", "rolling_context_between", "rolling_context_after"):
			try:
				values.append(int(settings.get(key, 0)))
			except (TypeError, ValueError):
				pass
		try:
			go = getattr(getattr(self._window_root, "session", None), "global_options", None)
			if go is not None:
				values.extend(
					[
						int(getattr(go.request, "rolling_context_lines", 0)),
						int(getattr(go.request, "rolling_context_between", 0)),
						int(getattr(go.request, "rolling_context_after", 0)),
					]
				)
		except (TypeError, ValueError, AttributeError):
			pass
		return max(values) if values else 0

	def _on_editor_text_scrolled(self, first: str, last: str) -> None:
		"""Keep the editor scrollbar and line-number gutter in sync."""
		self._editor_scrollbar.set(first, last)
		self._schedule_line_number_refresh()

	def _schedule_line_number_refresh(self, _event: Optional[tk.Event] = None) -> None:
		"""Queue one gutter redraw after Tk settles the latest text layout."""
		if self._line_number_refresh_pending:
			return
		self._line_number_refresh_pending = True
		self.after_idle(self._refresh_line_numbers)

	def _refresh_line_numbers(self) -> None:
		"""Redraw line numbers for the visible editor viewport."""
		self._line_number_refresh_pending = False
		if not hasattr(self, "_line_number_canvas") or not hasattr(self, "_editor_text"):
			return

		canvas = self._line_number_canvas
		text_widget = self._editor_text
		theme = get_theme()
		canvas.delete("all")
		canvas.configure(bg=theme.bg_panel, highlightbackground=theme.border_light)

		try:
			last_line = max(int(text_widget.index("end-1c").split(".", 1)[0]), 1)
		except (tk.TclError, ValueError):
			last_line = 1
		canvas.configure(width=18 + max(len(str(last_line)), 2) * 10)

		index = text_widget.index("@0,0")
		while True:
			line_info = text_widget.dlineinfo(index)
			if line_info is None:
				break
			line_number = index.split(".", 1)[0]
			y_position = line_info[1] + (line_info[3] / 2)
			canvas.create_text(
				max(canvas.winfo_width() - 8, 8),
				y_position,
				anchor="e",
				text=line_number,
				fill=theme.text_secondary,
			)
			next_index = text_widget.index(f"{index}+1line linestart")
			if text_widget.compare(next_index, "==", index):
				break
			index = next_index

		canvas.create_line(
			max(canvas.winfo_width() - 1, 1),
			0,
			max(canvas.winfo_width() - 1, 1),
			max(canvas.winfo_height(), 1),
			fill=theme.border_light,
		)

	def _on_close(self) -> None:
		"""Close the shared Editor host and clear the root registration."""
		if not self._confirm_close_with_unsaved_buffers():
			return
		self._cancel_pending_search_highlight_refresh()
		if getattr(self._window_root, self._WINDOW_ATTR, None) is self:
			setattr(self._window_root, self._WINDOW_ATTR, None)
		self.destroy()

	def _confirm_close_with_unsaved_buffers(self) -> bool:
		"""Prompt for save/discard when the Editor has in-memory file edits."""
		self._capture_current_unsaved_buffer()
		buffers = getattr(self, "_unsaved_file_text_by_rel_path", {})
		if not buffers:
			return True

		response = messagebox.askyesnocancel(
			"Unsaved Editor Changes",
			"There are unsaved Editor changes. Save before closing?",
			parent=self,
		)
		if response is None:
			return False
		if response is False:
			buffers.clear()
			return True

		for rel_path, text in list(buffers.items()):
			try:
				self._mgr.save_editor_patch(
					rel_path,
					text,
					change_label="editor close",
				)
			except Exception as exc:
				messagebox.showerror(
					"Save",
					f"Failed to save {rel_path}:\n{exc}",
					parent=self,
				)
				return False
			buffers.pop(rel_path, None)
		return True


def _coerce_optional_int(value: Any) -> Optional[int]:
	"""Return ``value`` as an ``int`` when possible, else ``None``."""
	if value is None:
		return None
	text = str(value).strip()
	if not text:
		return None
	try:
		return int(text)
	except ValueError:
		return None
