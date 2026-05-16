"""CherryAI GUI - Shared Editor host / Full Files surface.

This module restores the recycled Editor shell used for the first stage of the
Editor redesign. The host keeps the full-file surface inside this window and
hands off into the retained Full Table View dialog when the user switches to
Lines Only mode.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Dict, Optional

from CherryAI.functions.manifest_manager import FileDirEntry, ManifestManager
from CherryAI.gui.dialogs.table_view import FullTableViewDialog
from CherryAI.gui.theme.colors import apply_theme, apply_window_preferences, get_theme

logger = logging.getLogger(__name__)


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
		self._locator_lines_by_idx: Dict[int, list[int]] = {}
		self._current_locator_target: Optional[Dict[str, Any]] = None

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
				selectbackground=theme.bg_selected,
				selectforeground=theme.text_primary,
			)
			self._editor_text.tag_configure(
				"locator_match",
				background=theme.table_match_bg,
			)
			self._editor_text.tag_configure(
				"locator_active",
				background=theme.bg_selected,
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

		ttk.Label(top_bar, text="Search:").pack(side="left")
		self._search_var = tk.StringVar()
		self._search_entry = ttk.Entry(top_bar, textvariable=self._search_var, width=30)
		self._search_entry.pack(side="left", padx=(4, 6))
		ttk.Label(top_bar, text="Replace:").pack(side="left", padx=(6, 0))
		self._replace_var = tk.StringVar()
		self._replace_entry = ttk.Entry(top_bar, textvariable=self._replace_var, width=24)
		self._replace_entry.pack(side="left", padx=(4, 6))
		ttk.Button(top_bar, text="Replace", command=self._replace_current).pack(
			side="left", padx=(0, 4)
		)
		ttk.Button(top_bar, text="Replace All", command=self._replace_all).pack(
			side="left", padx=(0, 8)
		)
		ttk.Button(top_bar, text="Save", command=self._save_current_file).pack(
			side="left", padx=(0, 8)
		)
		ttk.Button(top_bar, text="◀", width=3, command=self._search_previous).pack(
			side="left", padx=(0, 2)
		)
		ttk.Button(top_bar, text="▶", width=3, command=self._search_next).pack(side="left")

		paned = ttk.PanedWindow(self._full_files_frame, orient="horizontal")
		paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

		tree_frame = ttk.Frame(paned)
		paned.add(tree_frame, weight=1)

		self._file_tree = ttk.Treeview(tree_frame, show="tree")
		self._file_tree.pack(side="left", fill="both", expand=True)
		self._file_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
		ttk.Scrollbar(tree_frame, orient="vertical", command=self._file_tree.yview).pack(
			side="right", fill="y"
		)
		self._file_tree.configure(yscrollcommand=lambda first, last: None)

		right_frame = ttk.Frame(paned)
		paned.add(right_frame, weight=4)

		self._editor_text = tk.Text(right_frame, wrap="word", undo=True)
		self._editor_text.pack(fill="both", expand=True)
		self._editor_text.bind("<<Modified>>", self._on_editor_modified)
		self._editor_text.bind("<ButtonRelease-1>", self._on_editor_cursor_changed)
		self._editor_text.bind("<KeyRelease>", self._on_editor_cursor_changed)

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
			entry.rel_path: entry for entry in self._mgr.get_filedir()
		}
		self._tree_item_to_rel_path.clear()
		if not hasattr(self, "_file_tree"):
			return

		self._file_tree.delete(*self._file_tree.get_children())
		for rel_path in sorted(self._entry_by_rel_path):
			item_id = self._file_tree.insert("", "end", text=rel_path)
			self._tree_item_to_rel_path[item_id] = rel_path

	def _select_first_file_if_available(self) -> None:
		"""Select the first available file when the host opens."""
		if not self._entry_by_rel_path:
			return
		self.set_selected_file(sorted(self._entry_by_rel_path)[0])

	def set_selected_file(self, rel_path: str) -> None:
		"""Update the active file context used by both Editor modes."""
		if rel_path not in self._entry_by_rel_path:
			return

		self._selected_rel_path = rel_path
		self._selected_file_var.set(rel_path)

		if hasattr(self, "_file_tree"):
			for item_id, item_rel_path in self._tree_item_to_rel_path.items():
				if item_rel_path == rel_path:
					self._file_tree.selection_set(item_id)
					self._file_tree.focus(item_id)
					self._file_tree.see(item_id)
					break

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
		selection = self._file_tree.selection()
		if not selection:
			return
		rel_path = self._tree_item_to_rel_path.get(selection[0])
		if rel_path is not None:
			self.set_selected_file(rel_path)

	def _load_selected_file(self) -> None:
		"""Load the selected file into the editor and refresh aux views."""
		if self._selected_rel_path is None or self._selected_rel_path not in self._entry_by_rel_path:
			self._replace_editor_text("")
			self._set_diff_text("")
			self._set_patch_diff_text("")
			self._history_tree.delete(*self._history_tree.get_children())
			return

		view = self._mgr.get_editor_file_view(self._selected_rel_path)
		self._replace_editor_text(view["current_text"])
		self._refresh_aux_views(view)

	def _replace_editor_text(self, text: str) -> None:
		"""Replace the editor buffer without leaving the modified flag set."""
		self._editor_text.delete("1.0", "end")
		self._editor_text.insert("1.0", text)
		self._editor_text.edit_modified(False)
		self._current_search_index = "1.0"

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
		for row in view.get("line_history", []):
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
		self._locator_lines_by_idx.clear()
		self._editor_text.tag_remove("locator_match", "1.0", "end")
		self._editor_text.tag_remove("locator_active", "1.0", "end")
		for metadata in locator_metadata:
			if not metadata.get("matched"):
				continue
			editor_ln = _coerce_optional_int(metadata.get("editor_ln"))
			idx = _coerce_optional_int(metadata.get("idx"))
			if editor_ln is None or idx is None:
				continue
			start = f"{editor_ln}.0"
			end = f"{editor_ln}.0 lineend +1c"
			self._editor_text.tag_add("locator_match", start, end)
			self._locator_lines_by_idx.setdefault(idx, []).append(editor_ln)

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
				for editor_ln in self._locator_lines_by_idx.get(idx, []):
					start = f"{editor_ln}.0"
					end = f"{editor_ln}.0 lineend +1c"
					self._editor_text.tag_add("locator_active", start, end)
				try:
					self._history_tree.selection_set(str(idx))
					self._history_tree.focus(str(idx))
					self._history_tree.see(str(idx))
				except tk.TclError:
					pass

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

	def _on_editor_cursor_changed(self, _event: tk.Event) -> None:
		"""Promote the locator target that owns the current editor line."""
		line_number = _coerce_optional_int(self._editor_text.index("insert").split(".", 1)[0])
		if line_number is None:
			return
		for metadata in self._locator_metadata:
			if not metadata.get("matched"):
				continue
			if _coerce_optional_int(metadata.get("editor_ln")) != line_number:
				continue
			target: Dict[str, Any] = {"idx": metadata.get("idx"), "ln": metadata.get("ln")}
			if "f" in metadata:
				target["f"] = metadata.get("f")
			self.set_locator_target(target)
			return

	def _on_editor_modified(self, _event: tk.Event) -> None:
		"""Refresh auxiliary views when the visible editor buffer changes."""
		if not self._editor_text.edit_modified():
			return
		self._editor_text.edit_modified(False)
		if self._selected_rel_path is None or self._selected_rel_path not in self._entry_by_rel_path:
			return
		current_text = self._editor_text.get("1.0", "end-1c")
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

	def _search_next(self) -> None:
		"""Jump to the next match in the current editor buffer."""
		query = self._search_var.get().strip()
		if not query:
			return
		next_index = self._editor_text.search(query, self._current_search_index, stopindex="end")
		if not next_index:
			next_index = self._editor_text.search(query, "1.0", stopindex="end")
		if not next_index:
			return
		end_index = f"{next_index}+{len(query)}c"
		self._editor_text.tag_remove("sel", "1.0", "end")
		self._editor_text.tag_add("sel", next_index, end_index)
		self._editor_text.mark_set("insert", end_index)
		self._editor_text.see(next_index)
		self._current_search_index = end_index

	def _search_previous(self) -> None:
		"""Jump to the previous match in the current editor buffer."""
		query = self._search_var.get().strip()
		if not query:
			return
		previous_index = self._editor_text.search(
			query,
			self._current_search_index,
			stopindex="1.0",
			backwards=True,
		)
		if not previous_index:
			previous_index = self._editor_text.search(query, "end", stopindex="1.0", backwards=True)
		if not previous_index:
			return
		end_index = f"{previous_index}+{len(query)}c"
		self._editor_text.tag_remove("sel", "1.0", "end")
		self._editor_text.tag_add("sel", previous_index, end_index)
		self._editor_text.mark_set("insert", previous_index)
		self._editor_text.see(previous_index)
		self._current_search_index = previous_index

	def _replace_current(self) -> None:
		"""Replace the selected match, or the next match if none is active."""
		query = self._search_var.get().strip()
		if not query:
			return
		replacement = self._replace_var.get()
		ranges = self._editor_text.tag_ranges("sel")
		if len(ranges) == 2:
			start_index = str(ranges[0])
			end_index = str(ranges[1])
			if self._editor_text.get(start_index, end_index) != query:
				start_index = self._editor_text.search(query, start_index, stopindex="end")
				if not start_index:
					start_index = self._editor_text.search(query, "1.0", stopindex="end")
				if not start_index:
					return
				end_index = f"{start_index}+{len(query)}c"
		else:
			start_index = self._editor_text.search(query, "insert", stopindex="end")
			if not start_index:
				start_index = self._editor_text.search(query, "1.0", stopindex="end")
			if not start_index:
				return
			end_index = f"{start_index}+{len(query)}c"

		self._editor_text.delete(start_index, end_index)
		self._editor_text.insert(start_index, replacement)
		new_end = f"{start_index}+{len(replacement)}c"
		self._editor_text.tag_remove("sel", "1.0", "end")
		self._editor_text.tag_add("sel", start_index, new_end)
		self._editor_text.mark_set("insert", new_end)
		self._editor_text.see(start_index)
		self._current_search_index = new_end

	def _replace_all(self) -> None:
		"""Replace all matches in the current editor buffer."""
		query = self._search_var.get().strip()
		if not query:
			return
		replacement = self._replace_var.get()
		replacement_count = 0
		start_index = "1.0"
		while True:
			match_index = self._editor_text.search(query, start_index, stopindex="end")
			if not match_index:
				break
			end_index = f"{match_index}+{len(query)}c"
			self._editor_text.delete(match_index, end_index)
			self._editor_text.insert(match_index, replacement)
			start_index = f"{match_index}+{len(replacement)}c"
			replacement_count += 1

		if replacement_count:
			messagebox.showinfo(
				"Replace",
				f"Replaced {replacement_count} occurrence(s).",
				parent=self,
			)

	def _on_close(self) -> None:
		"""Close the shared Editor host and clear the root registration."""
		if getattr(self._window_root, self._WINDOW_ATTR, None) is self:
			setattr(self._window_root, self._WINDOW_ATTR, None)
		self.destroy()


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
