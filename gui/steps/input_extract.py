"""CherryAI GUI v2 Input Step.

First workflow tab for loading files, previewing content, and detecting manifests.

TASK 39: Modernized Input step with unified selector, Treeview file tree,
auto-encoding, format filtering, multi-line preview, and progress dialog.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk

from CherryAI.gui.dialogs.loading_progress import LoadingProgressDialog
from CherryAI.gui.dialogs.input_dialog import UnifiedInputDialog

from CherryAI.functions.analysis import classify_file_type
from CherryAI.functions.ini_manager import get_default
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState

logger = logging.getLogger(__name__)

# Supported file extensions for loading (TASK 39.3: rpgmaker and image added)
SUPPORTED_EXTENSIONS = [
    ("All Supported", "*.txt *.csv *.tsv *.json *.xlsx *.png *.jpg *.jpeg *.bmp"),
    ("Text Files", "*.txt"),
    ("CSV Files", "*.csv"),
    ("TSV Files", "*.tsv"),
    ("JSON Files", "*.json"),
    ("Excel Files", "*.xlsx"),
    ("Image Files", "*.png *.jpg *.jpeg *.bmp"),
    ("All Files", "*.*"),
]

# Format detection map (TASK 39.3: rpgmaker and image formats added)
FORMAT_MAP = {
    ".txt": "txt",
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".xlsx": "xlsx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".bmp": "image",
}

# Format extension mapping for format filtering (TASK 39.3)
FORMAT_EXTENSIONS = {
    "txt": {".txt"},
    "csv": {".csv"},
    "tsv": {".tsv"},
    "json": {".json"},
    "xlsx": {".xlsx"},
    "rpgmaker": {".json", ".js"},
    "image": {".png", ".jpg", ".jpeg", ".bmp"},
}


class LoadedFile:
    """Represents a loaded file with its content and metadata.

    Attributes:
        path: Path to the file.
        format_id: Detected format (txt, csv, etc.).
        lines: Extracted text lines.
        manifest_path: Path to associated manifest, if found.
        line_count: Number of lines.
        encoding: Detected or assumed encoding.
    """

    def __init__(
        self,
        path: Path,
        format_id: str,
        lines: List[str],
        manifest_path: Optional[Path] = None,
        encoding: str = "utf-8",
    ) -> None:
        """Initialize LoadedFile.

        Args:
            path: File path.
            format_id: Format identifier.
            lines: Extracted lines.
            manifest_path: Associated manifest path.
            encoding: File encoding.
        """
        self.path = path
        self.format_id = format_id
        self.lines = lines
        self.manifest_path = manifest_path
        self.encoding = encoding

    @property
    def line_count(self) -> int:
        """Get line count."""
        return len(self.lines)

    @property
    def filename(self) -> str:
        """Get filename without path."""
        return self.path.name

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "path": str(self.path),
            "format_id": self.format_id,
            "line_count": self.line_count,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "encoding": self.encoding,
        }


# ======================================================================
# Import Translation Dialog
# ======================================================================

class _ImportTranslationDialog(tk.Toplevel):
    """Selection dialog for Import Translation.

    Shows two groups of checkboxes:
    * **Line Fields** — which per-line data to copy (prepro, tl, …)
    * **Settings Sections** — which manifest-level settings to import
    """

    def __init__(self, parent: tk.Widget, source_data: Dict[str, Any]) -> None:
        super().__init__(parent)
        self.title("Import Translation — Select Data")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: Optional[Dict[str, bool]] = None
        self._vars: Dict[str, tk.BooleanVar] = {}
        self._source = source_data

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Centre on parent
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(px, 0)}+{max(py, 0)}")

    # ---- UI ----

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 2}

        # --- Line Fields ---
        lf = ttk.LabelFrame(self, text="Line Fields")
        lf.pack(fill="x", padx=10, pady=(10, 4))

        self._add_check(lf, "import_prepro", "Preprocessed", True, **pad)
        self._add_check(lf, "import_tags", "Tags", True, **pad)
        self._add_check(lf, "import_translated", "Translated", True, **pad)
        self._add_check(lf, "import_postpro", "Postprocessed", True, **pad)
        self._add_check(lf, "import_wordwrap", "Wordwrap", True, **pad)
        self._add_check(lf, "import_qa", "QA (edits, TLC, overwrite)", True, **pad)
        ttk.Separator(lf, orient="horizontal").pack(fill="x", padx=8, pady=4)
        self._add_check(
            lf, "skip_new_lines",
            "Do not overwrite lines that already have translations",
            False, **pad,
        )

        # --- Settings Sections ---
        sf = ttk.LabelFrame(self, text="Settings Sections")
        sf.pack(fill="x", padx=10, pady=(4, 4))

        self._add_check(sf, "import_analysis", "Analysis", False, **pad)
        self._add_check(sf, "import_information", "Information (metadata, glossary, code DB)", True, **pad)
        self._add_check(sf, "import_preprocessing", "Preprocessing Settings", False, **pad)
        self._add_check(sf, "import_costs", "Costs / Request Settings", False, **pad)
        self._add_check(sf, "import_translation", "Translation Step State", False, **pad)
        self._add_check(sf, "import_postprocessing", "Postprocessing", False, **pad)
        self._add_check(sf, "import_wordwrap_settings", "Wordwrap Settings", False, **pad)
        self._add_check(sf, "import_qa_settings", "QA / Validation Rules", False, **pad)
        self._add_check(sf, "import_file_settings", "File / Output Settings", False, **pad)

        # --- Source info ---
        src_lines = len(self._source.get("lines", []))
        info_text = f"Source manifest contains {src_lines} line(s)."
        ttk.Label(self, text=info_text, foreground="gray").pack(
            padx=10, pady=(2, 4),
        )

        # --- Buttons ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(btn_frame, text="Import", command=self._on_ok).pack(
            side="right", padx=4,
        )
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(
            side="right", padx=4,
        )

    def _add_check(
        self,
        parent: tk.Widget,
        key: str,
        label: str,
        default: bool,
        **pack_kw: Any,
    ) -> None:
        var = tk.BooleanVar(value=default)
        self._vars[key] = var
        ttk.Checkbutton(parent, text=label, variable=var).pack(
            anchor="w", **pack_kw,
        )

    # ---- Actions ----

    def _on_ok(self) -> None:
        self.result = {k: v.get() for k, v in self._vars.items()}
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


class InputExtractionStep(BaseStep):
    """Input workflow step.

    Features:
    - File browser with multi-select
    - Format auto-detection
    - Preview table with raw lines
    - Manifest detection and loading
    - Batch summary widget
    - Format/encoding options panel
    """

    step_id = 0
    step_name = "Input"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        **kwargs: Any,
    ) -> None:
        """Initialize the Input step.

        Args:
            parent: Parent widget.
            session: Session state reference.
            **kwargs: Additional keyword arguments.
        """
        # Loaded files storage
        self._loaded_files: List[LoadedFile] = []
        self._current_file_index: int = -1

        # Folder root for relative path display (set when loading folder)
        self._folder_root: Optional[Path] = None

        # TASK 39.4: Tree item ID to LoadedFile index mapping
        self._tree_item_to_index: Dict[str, int] = {}

        # UI variables
        self._encoding_var = tk.StringVar(value="auto")
        self._format_var = tk.StringVar(value="auto")
        self._pipeline_var = tk.StringVar(value="3: Preprocess")

        super().__init__(parent, session, **kwargs)

    def _build_ui(self) -> None:
        """Build the Input UI."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Top toolbar
        self._build_toolbar()

        # Main content area (paned: left=file list, right=preview)
        self._build_content()

        # Bottom summary bar
        self._build_summary_bar()

    def _build_toolbar(self) -> None:
        """Build the top toolbar with action buttons."""
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # PHASE 58.1: Unified Input button with dropdown for file/folder/unified
        self._select_menu = tk.Menu(toolbar, tearoff=0)
        self._select_menu.add_command(
            label="📁 Unified Selection...",
            command=self._on_unified_input,
        )
        self._select_menu.add_separator()
        self._select_menu.add_command(
            label="Select File(s)...",
            command=self._on_load_files,
        )
        self._select_menu.add_command(
            label="Select Folder...",
            command=self._on_load_folder,
        )

        # Input button directly opens the unified selection dialog per specs
        self._select_btn = ttk.Button(
            toolbar,
            text="📁 Input",
            command=self._on_unified_input,
        )
        self._select_btn.pack(side="left", padx=2)

        # Import Translations button (Task 47.8)
        self._import_btn = ttk.Button(
            toolbar,
            text="📥 Import Translations",
            command=self._on_import_translations,
        )
        self._import_btn.pack(side="left", padx=2)

        # TASK 39.2: "Load Manifest" and "Clear All" buttons removed from toolbar.
        # Use File → Open Project... and File → New Project menus instead.



    def _build_content(self) -> None:
        """Build the main content area with file list and preview."""
        content = ttk.PanedWindow(self, orient="horizontal")
        content.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Left: File list
        left_frame = ttk.LabelFrame(content, text="Loaded Files")
        content.add(left_frame, weight=1)

        # Filter control row (replaces Sort combobox)
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill="x", padx=5, pady=(5, 0))
        ttk.Label(filter_frame, text="Filter:").pack(side="left")
        self._file_filter_var = tk.StringVar()
        self._file_filter_var.trace_add(
            "write", lambda *_a: self._update_file_list(),
        )
        self._file_filter_entry = ttk.Entry(
            filter_frame, textvariable=self._file_filter_var, width=16,
        )
        self._file_filter_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self._file_filter_clear_btn = ttk.Button(
            filter_frame, text="✕", width=3,
            command=lambda: self._file_filter_var.set(""),
        )
        self._file_filter_clear_btn.pack(side="left", padx=(2, 0))

        # Sort state for clickable column headers
        self._sort_column: str = ""  # "" = filetree default, "type", "lines", "name"
        self._sort_ascending: bool = True

        # File listbox with scrollbar
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # TASK 39.4: Treeview with collapsible folder hierarchy replaces flat Listbox
        self._file_tree = ttk.Treeview(
            list_frame,
            columns=("type", "lines"),
            show="tree headings",
            selectmode="extended",
        )
        self._file_tree.heading(
            "#0", text="Name", anchor="w",
            command=lambda: self._on_column_sort("name"),
        )
        self._file_tree.heading(
            "type", text="Type", anchor="w",
            command=lambda: self._on_column_sort("type"),
        )
        self._file_tree.heading(
            "lines", text="Lines", anchor="e",
            command=lambda: self._on_column_sort("lines"),
        )
        self._file_tree.column("#0", width=180, stretch=True)
        self._file_tree.column("type", width=70, stretch=False)
        self._file_tree.column("lines", width=60, stretch=False)
        self._file_tree.pack(side="left", fill="both", expand=True)
        self._file_tree.bind("<<TreeviewSelect>>", self._on_file_select)

        # Backward-compat alias so existing code referencing _file_listbox still works
        self._file_listbox = self._file_tree

        # Tree item ID to LoadedFile index mapping
        self._tree_item_to_index: Dict[str, int] = {}

        # Right-click context menu
        self._file_context_menu = tk.Menu(self._file_tree, tearoff=0)
        self._file_context_menu.add_command(
            label="Remove Selected", command=self._on_remove_selected_file,
        )
        self._file_context_menu.add_command(
            label="Select All in Folder", command=self._on_select_all_in_folder,
        )
        self._file_context_menu.add_separator()
        # PHASE 58.7: Additional context menu items
        self._file_context_menu.add_command(
            label="Select All", command=self._on_select_all_files,
        )
        self._file_context_menu.add_separator()
        # "Select Type" submenu for typing
        type_menu = tk.Menu(self._file_context_menu, tearoff=0)
        type_menu.add_command(
            label="Dialogue",
            command=lambda: self._set_selected_file_type("dialogue"),
        )
        type_menu.add_command(
            label="Menu",
            command=lambda: self._set_selected_file_type("menu"),
        )
        type_menu.add_command(
            label="Mixed",
            command=lambda: self._set_selected_file_type("mixed"),
        )
        self._file_context_menu.add_cascade(label="Select Type", menu=type_menu)
        self._file_tree.bind("<Button-3>", self._on_file_listbox_right_click)

        file_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self._file_tree.yview,
        )
        file_scroll.pack(side="right", fill="y")
        self._file_tree.configure(yscrollcommand=file_scroll.set)

        # Right: Preview table
        right_frame = ttk.LabelFrame(content, text="Preview")
        content.add(right_frame, weight=3)

        # Search bar for preview filtering
        search_frame = ttk.Frame(right_frame)
        search_frame.pack(fill="x", padx=5, pady=(5, 0))
        ttk.Label(search_frame, text="Search:").pack(side="left")
        self._preview_search_var = tk.StringVar()
        self._preview_search_var.trace_add(
            "write", lambda *_a: self._update_preview(),
        )
        search_entry = ttk.Entry(
            search_frame, textvariable=self._preview_search_var, width=30,
        )
        search_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self._preview_search_clear_btn = ttk.Button(
            search_frame, text="✕", width=3,
            command=self._on_preview_search_clear,
        )
        self._preview_search_clear_btn.pack(side="left", padx=(2, 0))

        # Preview Treeview
        preview_frame = ttk.Frame(right_frame)
        preview_frame.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("idx", "line", "content", "tags")
        self._preview_tree = ttk.Treeview(
            preview_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        self._preview_tree.heading("idx", text="Project", anchor="w")
        self._preview_tree.heading("line", text="File", anchor="w")
        self._preview_tree.heading("content", text="Content", anchor="w")
        self._preview_tree.heading("tags", text="Tags", anchor="w")
        self._preview_tree.column("idx", width=60, stretch=False)
        self._preview_tree.column("line", width=50, stretch=False)
        self._preview_tree.column("content", width=450, stretch=True)
        self._preview_tree.column("tags", width=80, stretch=False)
        self._preview_tree.pack(side="left", fill="both", expand=True)
        self._preview_tree.bind("<<TreeviewSelect>>", self._on_preview_select)

        # Preview right-click context menu for tag editing
        self._preview_context_menu = tk.Menu(self._preview_tree, tearoff=0)
        tag_menu = tk.Menu(self._preview_context_menu, tearoff=0)
        tag_menu.add_command(
            label="Dialogue",
            command=lambda: self._set_selected_line_tag("dialogue"),
        )
        tag_menu.add_command(
            label="Menu",
            command=lambda: self._set_selected_line_tag("menu"),
        )
        tag_menu.add_command(
            label="Choice",
            command=lambda: self._set_selected_line_tag("choice"),
        )
        tag_menu.add_command(
            label="Clear",
            command=lambda: self._set_selected_line_tag(""),
        )
        self._preview_context_menu.add_cascade(label="Set Tag", menu=tag_menu)
        self._preview_tree.bind("<Button-3>", self._on_preview_right_click)

        preview_scroll = ttk.Scrollbar(
            preview_frame,
            orient="vertical",
            command=self._preview_tree.yview,
        )
        preview_scroll.pack(side="right", fill="y")
        self._preview_tree.configure(yscrollcommand=preview_scroll.set)

        # TASK 39.6: Manifest status label removed from Preview panel.
        # Manifest status is shown in the window title bar instead.

    def _build_summary_bar(self) -> None:
        """Build the bottom summary bar."""
        summary = ttk.Frame(self)
        summary.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        # File count
        self._file_count_label = ttk.Label(
            summary,
            text="Files: 0",
            font=("Segoe UI", 10, "bold"),
        )
        self._file_count_label.pack(side="left", padx=10)

        # Total lines
        self._total_lines_label = ttk.Label(
            summary,
            text="Total Lines: 0",
        )
        self._total_lines_label.pack(side="left", padx=10)

        # Format breakdown
        self._format_breakdown_label = ttk.Label(
            summary,
            text="",
            foreground=THEME.text_secondary,
        )
        self._format_breakdown_label.pack(side="left", padx=10)

        # Ready indicator
        self._ready_label = ttk.Label(
            summary,
            text="",
            foreground=THEME.accent_success,
        )
        self._ready_label.pack(side="right", padx=10)

    # ----------------------------- Event Handlers ----------------------------- #

    def _show_select_menu(self) -> None:
        """Show the Select File(s) dropdown menu below the button."""
        try:
            x = self._select_btn.winfo_rootx()
            y = self._select_btn.winfo_rooty() + self._select_btn.winfo_height()
            self._select_menu.tk_popup(x, y)
        finally:
            self._select_menu.grab_release()

    def _on_unified_input(self) -> None:
        """Handle unified input dialog (PHASE 58.1, PHASE 58.12).

        Opens a combined file/folder selection window allowing users to
        select both files and folders in a single interface.
        
        PHASE 58.12: Dialog now includes project name field when creating new project.
        """
        encoding = self._encoding_var.get() if self._encoding_var else "auto"
        format_override = self._format_var.get() if self._format_var else "auto"

        # Determine initial directory - PHASE 58.12: Uses ini_manager if no other dir
        initial_dir = None
        if self._loaded_files:
            initial_dir = str(self._loaded_files[0].path.parent)
        elif self._folder_root:
            initial_dir = str(self._folder_root)
        # If no initial_dir, dialog will use ini_manager.get_last_input_dir()

        # PHASE 58.12: Show project name field if no manifest is loaded
        mgr = self.manifest_manager
        show_project_name = (mgr is None or not mgr.is_loaded)

        # Show unified input dialog
        pipeline_val = self._pipeline_var.get() if self._pipeline_var else "3: Preprocess"
        dialog = UnifiedInputDialog(
            self,
            format_filter=format_override,
            encoding=encoding,
            auto_pipeline=pipeline_val,
            initial_dir=initial_dir,
            show_project_name=show_project_name,
        )

        result = dialog.show()
        if result is None:
            return

        # Unpack 5-tuple result
        selected_paths, format_filter, enc, project_name, pipeline = result
        if not selected_paths:
            return

        # Update vars
        if self._format_var:
            self._format_var.set(format_filter)
        if self._encoding_var:
            self._encoding_var.set(enc)
        if self._pipeline_var:
            self._pipeline_var.set(pipeline)

        # PHASE 58.12: Process with optional project name
        self._load_selected_paths(selected_paths, enc, format_filter, project_name)

    def _load_selected_paths(
        self,
        paths: List[Path],
        encoding: str,
        format_override: str,
        project_name: str = "",
    ) -> None:
        """Load files from selected paths (files or folders).

        PHASE 58.1: Common loading method for unified input dialog.
        PHASE 58.12: Added project_name parameter.
        Non-destructive: when adding to an existing manifest, only new files
        are inserted and existing line entries are preserved.

        Args:
            paths: List of selected paths (files or folders).
            encoding: Encoding to use.
            format_override: Format filter to apply.
            project_name: Project name for new projects (bypasses dialog).
        """
        # PHASE 58.12: Store project name for later use
        self._pending_project_name = project_name
        
        files_to_load: List[Path] = []
        first_folder: Optional[Path] = None

        # Collect all files from paths
        for path in paths:
            if path.is_file():
                files_to_load.append(path)
            elif path.is_dir():
                if first_folder is None:
                    first_folder = path
                # Collect files from folder
                folder_files = self._collect_files_for_format(path, format_override)
                files_to_load.extend(folder_files)

        if not files_to_load:
            from tkinter import messagebox
            messagebox.showinfo(
                "No Files Found",
                "No supported files found in the selected paths.",
            )
            return

        # Set folder root if loading from folder
        if first_folder:
            self._folder_root = first_folder

        # Sort files alphabetically for consistent ordering
        files_to_load.sort()

        # Remove duplicates
        seen: set = set()
        unique_files = []
        for f in files_to_load:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
        files_to_load = unique_files

        # -----------------------------------------------------------
        # Source root validation for adding to existing manifest
        # -----------------------------------------------------------
        mgr = self.manifest_manager
        is_add_to_existing = (
            mgr is not None and mgr.is_loaded and bool(mgr.get_filedir())
        )

        if is_add_to_existing:
            existing_root = mgr.source_root
            if existing_root:
                # Check every new file path contains the source_root folder name
                rejected: List[str] = []
                for fp in files_to_load:
                    if existing_root not in str(fp):
                        rejected.append(fp.name)
                if rejected:
                    names = "\n".join(rejected[:10])
                    if len(rejected) > 10:
                        names += f"\n...and {len(rejected) - 10} more"
                    messagebox.showerror(
                        "Source Root Mismatch",
                        f"New input must have the same source directory: "
                        f"{existing_root}\n\nRejected files:\n{names}",
                    )
                    return

            # Filter out files already in the manifest
            existing_rel_paths = {e.rel_path for e in mgr.get_filedir()}
            already_loaded_names = {
                lf.path.name for lf in self._loaded_files
            }

        # Record the index where new LoadedFiles start
        new_files_start = len(self._loaded_files)

        loaded_count = 0
        skipped_files: List[str] = []

        # Show progress dialog for multi-file loading
        progress: Optional[LoadingProgressDialog] = None
        if len(files_to_load) > 3:
            progress = LoadingProgressDialog(self, len(files_to_load))

        # Handshake: validate parser once before iterating files
        if format_override != "auto":
            if not self._validate_parser_selection(format_override):
                if progress is not None:
                    progress.close()
                return

        for path in files_to_load:
            if progress is not None and progress.cancelled:
                break
            # Format filtering
            if format_override != "auto" and not self._file_matches_format(path, format_override):
                skipped_files.append(path.name)
                if progress is not None:
                    progress.update(path.name)
                continue

            # Skip files already in the manifest when adding
            if is_add_to_existing:
                if path.name in already_loaded_names:
                    if progress is not None:
                        progress.update(path.name)
                    continue

            if self._load_file(path, encoding, format_override):
                loaded_count += 1
            if progress is not None:
                progress.update(path.name)

        if progress is not None:
            progress.close()

        # Warn about skipped files
        if skipped_files:
            from tkinter import messagebox
            names = "\n".join(skipped_files[:10])
            if len(skipped_files) > 10:
                names += f"\n...and {len(skipped_files) - 10} more"
            messagebox.showwarning(
                "Files Skipped",
                f"The following files were skipped because they don't match "
                f"the '{format_override}' format filter:\n\n{names}",
            )

        if loaded_count > 0:
            self._update_summary()
            self._update_file_list()
            if self._current_file_index < 0 and self._loaded_files:
                self._select_first_file_in_tree()
            self.set_status("in-progress")
            logger.info("Loaded %d file(s)", loaded_count)

            if is_add_to_existing:
                # Non-destructive addition to existing manifest
                new_loaded = self._loaded_files[new_files_start:]
                self._add_files_to_existing_manifest(new_loaded, format_override)
            else:
                self._populate_project_info_from_files()
                self._ensure_project_created()

            # Parser Handshake P3: Wire optional components to manifest
            self._wire_parser_optionals(format_override)

            self._save_manifest_after_file_load()

            # Refresh file list after manifest sync to show Type column
            self._update_file_list()

            # PHASE 58.4: Execute automatic pipeline
            if not is_add_to_existing:
                self._execute_auto_pipeline()

    def _collect_files_for_format(self, folder: Path, format_filter: str) -> List[Path]:
        """Collect files from a folder based on format filter.

        For parser names, collects all files then filters via ``can_handle``.

        Args:
            folder: Folder to scan.
            format_filter: Format filter ("auto" or specific format).

        Returns:
            List of matching file paths.
        """
        # Check if format_filter is a parser name
        try:
            from CherryAI.formats import get_parser_registry
            parser = get_parser_registry().get(format_filter)
            if parser is not None:
                # Collect all files, then filter via can_handle
                all_files = self._collect_files_from_folder(
                    folder, {".txt", ".csv", ".tsv", ".json", ".xlsx", ".js"},
                )
                return [f for f in all_files if parser.can_handle(f)]
        except Exception:
            pass

        if format_filter != "auto" and format_filter in FORMAT_EXTENSIONS:
            suffixes = FORMAT_EXTENSIONS[format_filter]
        else:
            suffixes = {".txt", ".csv", ".tsv", ".json", ".xlsx",
                        ".png", ".jpg", ".jpeg", ".bmp"}
        return self._collect_files_from_folder(folder, suffixes)

    def _get_pipeline_level(self) -> int:
        """Get the current auto-pipeline level (0-4).

        PHASE 58.2: Returns the numeric pipeline level from the dropdown.
        """
        if not hasattr(self, "_pipeline_var") or self._pipeline_var is None:
            return 3  # Default: Preprocess
        value = self._pipeline_var.get()
        # Extract number from "N: Description" format
        try:
            return int(value.split(":")[0])
        except (ValueError, IndexError):
            return 3

    def _execute_auto_pipeline(self) -> None:
        """Execute the automatic pipeline based on settings.

        PHASE 58.4: Runs analysis, estimation, preprocessing etc. based
        on the configured pipeline level.
        """
        level = self._get_pipeline_level()
        if level < 1:
            return  # Manual mode - no auto pipeline

        logger.info("Executing auto-pipeline at level %d", level)

        # Level 1+: Run Analysis
        self._trigger_auto_analysis()

        if level < 2:
            return

        # Level 2+: Run Original Estimation
        # (handled in analysis callback)

        if level < 3:
            return

        # Level 3+: Run Preprocessing
        self._trigger_auto_preprocessing()

        if level < 4:
            return

        # Level 4: Run Mock Translation
        self._trigger_mock_translation()

    def _trigger_mock_translation(self) -> None:
        """Trigger mock translation for pipeline level 4.

        PHASE 58.6: Runs mock translation after preprocessing.
        """
        # Schedule after preprocessing completes
        self.after(100, self._do_mock_translation)

    def _do_mock_translation(self) -> None:
        """Execute mock translation.

        PHASE 58.6: Performs mock translation, QA, and postprocessing.
        """
        try:
            app = self.winfo_toplevel()
            # Check if translation step exists and has mock translation capability
            steps = getattr(app, "_steps", None)
            if steps is None:
                return

            # Find translation step (index 5)
            for step in steps:
                if getattr(step, "step_id", -1) == 5:
                    # Check if step has mock translation method
                    mock_method = getattr(step, "_do_mock_translation", None)
                    if mock_method is not None:
                        mock_method()
                    break
        except Exception as e:
            logger.warning("Mock translation failed: %s", e)

    def _select_first_file_in_tree(self) -> None:
        """Select the first file item in the file tree and update preview."""
        if not self._tree_item_to_index:
            return
        # Find the first leaf (file) item in tree order
        first_item = next(iter(self._tree_item_to_index))
        self._file_tree.selection_set(first_item)
        self._file_tree.see(first_item)
        self._current_file_index = self._tree_item_to_index[first_item]
        self._update_preview()

    def _on_load_files(self) -> None:
        """Handle Load Files button click.
        
        TASK 19 Phase 5: Prompts for project name when loading new files
        without an existing manifest. Creates a new project via ManifestManager.
        """
        filepaths = filedialog.askopenfilenames(
            title="Select Files to Load",
            filetypes=SUPPORTED_EXTENSIONS,
        )

        if not filepaths:
            return

        encoding = self._encoding_var.get() if self._encoding_var else "auto"
        format_override = self._format_var.get() if self._format_var else "auto"

        loaded_count = 0
        skipped_files: List[str] = []

        # TASK 39.7: Show progress dialog for multi-file loading
        paths_to_load = [Path(fp) for fp in filepaths]
        progress: Optional[LoadingProgressDialog] = None
        if len(paths_to_load) > 3:
            progress = LoadingProgressDialog(self, len(paths_to_load))

        for path in paths_to_load:
            if progress is not None and progress.cancelled:
                break
            # TASK 39.3: Format filtering - skip files that don't match forced format
            if format_override != "auto" and not self._file_matches_format(path, format_override):
                skipped_files.append(path.name)
                if progress is not None:
                    progress.update(path.name)
                continue
            if self._load_file(path, encoding, format_override):
                loaded_count += 1
            if progress is not None:
                progress.update(path.name)

        if progress is not None:
            progress.close()

        # TASK 39.3: Warn about skipped files
        if skipped_files:
            names = "\n".join(skipped_files[:10])
            if len(skipped_files) > 10:
                names += f"\n...and {len(skipped_files) - 10} more"
            messagebox.showwarning(
                "Files Skipped",
                f"The following files were skipped because they don't match "
                f"the '{format_override}' format filter:\n\n{names}",
            )

        if loaded_count > 0:
            self._update_summary()
            self._update_file_list()
            # Select first file if none selected
            if self._current_file_index < 0 and self._loaded_files:
                self._select_first_file_in_tree()
            self.set_status("in-progress")
            logger.info("Loaded %d file(s)", loaded_count)
            
            # Populate project info suggestion from file path
            self._populate_project_info_from_files()
            
            # TASK 19 Phase 5: Create project if no manifest loaded
            self._ensure_project_created()
            
            # TASK 29.2: Save manifest after file load
            self._save_manifest_after_file_load()

            # Refresh file list after manifest sync to show Type column
            self._update_file_list()
            
            # Trigger auto-analysis if enabled
            self._trigger_auto_analysis()
            
            # Trigger auto-preprocessing if enabled (runs after analysis)
            self._trigger_auto_preprocessing()

    def _on_load_folder(self) -> None:
        """Handle Load Folder button click.
        
        Allows selecting a directory to recursively load all supported files.
        Files from subfolders are displayed with their relative path.
        """
        folder_path = filedialog.askdirectory(
            title="Select Folder to Load",
        )

        if not folder_path:
            return

        root_folder = Path(folder_path)
        if not root_folder.is_dir():
            return

        # Store the root folder for relative path display
        self._folder_root = root_folder

        encoding = self._encoding_var.get() if self._encoding_var else "auto"
        format_override = self._format_var.get() if self._format_var else "auto"

        # TASK 39.3: Determine supported suffixes based on format filter
        if format_override != "auto" and format_override in FORMAT_EXTENSIONS:
            supported_suffixes = FORMAT_EXTENSIONS[format_override]
        else:
            supported_suffixes = {".txt", ".csv", ".tsv", ".json", ".xlsx",
                                  ".png", ".jpg", ".jpeg", ".bmp"}
        file_paths = self._collect_files_from_folder(root_folder, supported_suffixes)

        if not file_paths:
            messagebox.showinfo(
                "No Files Found",
                f"No supported files found in folder:\n{root_folder}\n\n"
                f"Supported formats: {', '.join(sorted(supported_suffixes))}",
            )
            return

        # Sort files by path for consistent ordering
        file_paths.sort()

        loaded_count = 0

        # TASK 39.7: Show progress dialog for folder loading
        progress: Optional[LoadingProgressDialog] = None
        if len(file_paths) > 3:
            progress = LoadingProgressDialog(self, len(file_paths))

        for filepath in file_paths:
            if progress is not None and progress.cancelled:
                break
            if self._load_file(filepath, encoding, format_override):
                loaded_count += 1
            if progress is not None:
                progress.update(filepath.name)

        if progress is not None:
            progress.close()

        if loaded_count > 0:
            self._update_summary()
            self._update_file_list()
            # Select first file if none selected
            if self._current_file_index < 0 and self._loaded_files:
                self._select_first_file_in_tree()
            self.set_status("in-progress")
            logger.info("Loaded %d file(s) from folder %s", loaded_count, root_folder)
            
            # Populate project info suggestion from folder name
            self._populate_project_info_from_files()
            
            # TASK 19 Phase 5: Create project if no manifest loaded
            self._ensure_project_created()
            
            # TASK 29.2: Save manifest after file load
            self._save_manifest_after_file_load()

            # Refresh file list after manifest sync to show Type column
            self._update_file_list()
            
            # Trigger auto-analysis if enabled
            self._trigger_auto_analysis()
            
            # Trigger auto-preprocessing if enabled (runs after analysis)
            self._trigger_auto_preprocessing()

    def _collect_files_from_folder(
        self,
        folder: Path,
        suffixes: set,
    ) -> List[Path]:
        """Recursively collect files from a folder.

        Args:
            folder: Root folder to search.
            suffixes: Set of allowed file suffixes (e.g., {".txt", ".csv"}).

        Returns:
            List of Path objects for all matching files.
        """
        files: List[Path] = []
        try:
            for item in folder.rglob("*"):
                if item.is_file() and item.suffix.lower() in suffixes:
                    files.append(item)
        except PermissionError as e:
            logger.warning("Permission denied accessing folder: %s", e)
        except Exception as e:
            logger.error("Error scanning folder %s: %s", folder, e)
        return files

    def _file_matches_format(self, path: Path, format_id: str) -> bool:
        """Check if a file matches the specified format filter.

        For parser names (e.g. ``lightvn``), delegates to the parser's
        ``can_handle`` method instead of checking extensions.

        Args:
            path: File path to check.
            format_id: Required format identifier.

        Returns:
            True if file matches the format, False otherwise.
        """
        # Check parser registry first
        try:
            from CherryAI.formats import get_parser_registry
            parser = get_parser_registry().get(format_id)
            if parser is not None:
                return parser.can_handle(path)
        except Exception:
            pass

        allowed = FORMAT_EXTENSIONS.get(format_id)
        if allowed is None:
            return True  # Unknown format, allow all
        return path.suffix.lower() in allowed

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate token count for a line of text.

        Uses tiktoken when available, otherwise ``len(text) * 0.3`` heuristic
        matching the chunker approach.
        """
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4o")
            return len(enc.encode(text))
        except Exception:
            return max(1, int(len(text) * 0.3))

    def _validate_extracted_lines(
        self, lines: List[str], filename: str,
    ) -> bool:
        """Run per-line token validation after extraction.

        - Lines >2048 tokens raise an error popup and abort.
        - Lines >1024 tokens emit a warning (non-blocking).

        Returns:
            True if no fatal errors, False if load should be aborted.
        """
        warnings: List[str] = []
        for idx, line in enumerate(lines):
            tok = self._estimate_tokens(line)
            if tok > 2048:
                messagebox.showerror(
                    "Token Limit Exceeded",
                    f"File: {filename}\n"
                    f"Line {idx + 1} is {tok} tokens (max 2048).\n"
                    f"Consider splitting this line.",
                )
                return False
            if tok > 1024:
                warnings.append(
                    f"Line {idx + 1}: {tok} tokens "
                    f"({tok - 1024} over recommended 1024)"
                )
        if warnings:
            msg = "\n".join(warnings[:10])
            if len(warnings) > 10:
                msg += f"\n...and {len(warnings) - 10} more"
            messagebox.showwarning(
                "Token Warning",
                f"File: {filename}\nSome lines exceed 1024 tokens "
                f"(recommended limit):\n\n{msg}",
            )
        return True

    def _validate_parser_selection(self, format_id: str) -> bool:
        """Run handshake validation when a parser is selected.

        Returns True if parser is valid, False if load should be blocked.
        """
        try:
            from CherryAI.formats import get_parser_registry, validate_parser
            parser = get_parser_registry().get(format_id)
            if parser is None:
                return True  # Not a parser, skip validation
            errors = validate_parser(parser)
            if errors:
                messagebox.showerror(
                    "Parser Validation Failed",
                    f"Parser '{parser.name}' failed handshake validation:\n\n"
                    + "\n".join(errors),
                )
                return False
        except Exception:
            pass
        return True

    @staticmethod
    def _detect_encoding(path: Path) -> str:
        """Detect file encoding using an 8 KB probe with fallback chain.

        Priority: BOM → parser detect_encoding → utf-8 → shift_jis →
        cp932 → latin-1 fallback.

        Args:
            path: File path.

        Returns:
            Detected encoding string.
        """
        try:
            with open(path, "rb") as f:
                raw = f.read(8192)
            # Check BOM markers
            if raw[:3] == b"\xef\xbb\xbf":
                return "utf-8-sig"
            if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
                return "utf-16"

            # Try parser-specific encoding if available
            try:
                from CherryAI.formats import detect_parser as _detect_parser
                parser = _detect_parser(path)
                if parser is not None:
                    detect_fn = getattr(parser, "detect_encoding", None)
                    if detect_fn is not None:
                        enc = detect_fn(path)
                        if enc:
                            return enc
            except Exception:
                pass

            # Fallback chain: utf-8 → shift_jis → cp932 → latin-1
            for enc in ("utf-8", "shift_jis", "cp932"):
                try:
                    raw.decode(enc)
                    return enc
                except (UnicodeDecodeError, LookupError):
                    continue
            return "latin-1"  # Always succeeds
        except Exception:
            return "utf-8"

    def _save_manifest_after_file_load(self) -> None:
        """Save manifest after files are loaded (TASK 29.2).
        
        Ensures the manifest is saved to disk after file load operations
        to prevent data loss if the application crashes.
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            try:
                if mgr.save():
                    logger.debug("Manifest saved after file load")
            except Exception as e:
                logger.warning("Failed to save manifest after file load: %s", e)

    def _wire_parser_optionals(self, format_id: str) -> None:
        """Wire parser optional components (O1-O8) to manifest after load.

        Reads optional attributes from the detected parser and writes them
        to manifest Options fields so downstream pipeline steps can use them.

        Parser Handshake P3: Called after file extraction and manifest
        creation in ``_load_selected_paths``.

        Args:
            format_id: Format identifier (may be a parser name).
        """
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        try:
            from CherryAI.formats import get_parser_registry
            from CherryAI.formats.parser_base import ParserScript
            parser = get_parser_registry().get(format_id)
        except Exception:
            parser = None

        if parser is None:
            return

        from CherryAI.functions.manifest_fields import (
            save_nested_bool_field,
            save_nested_text_field,
        )

        # Store parser name for downstream steps (output, translation, etc.)
        save_nested_text_field(mgr, "Options", "ParserName", parser.name)

        # ------------------------------------------------------------------
        # O4: Speaker Detection
        # ------------------------------------------------------------------
        if type(parser).detect_speakers is not ParserScript.detect_speakers:
            all_lines: List[str] = []
            for lf in self._loaded_files:
                all_lines.extend(lf.lines)
            speakers = parser.detect_speakers(all_lines)
            if speakers:
                save_nested_bool_field(
                    mgr, "Options", "ParserHandlesSpeakers", True,
                )
                # Merge parser-detected speakers into characters[]
                try:
                    from CherryAI.functions.manifest_fields import (
                        load_character_notes,
                        save_character_notes,
                    )
                    existing = load_character_notes(mgr)
                    existing_names = {c["original_name"] for c in existing}
                    for si in speakers:
                        if si.name not in existing_names:
                            existing.append({
                                "original_name": si.name,
                                "translation": "",
                                "notes": "",
                                "count": 1,
                            })
                        else:
                            for c in existing:
                                if c["original_name"] == si.name:
                                    c["count"] = c.get("count", 0) + 1
                    save_character_notes(mgr, existing)
                except Exception as e:
                    logger.debug("Could not merge parser speakers: %s", e)
                logger.info(
                    "O4: Parser '%s' detected %d speakers",
                    parser.name, len(speakers),
                )

        # ------------------------------------------------------------------
        # O6: Custom Wordwrap flag
        # ------------------------------------------------------------------
        if type(parser).wordwrap is not ParserScript.wordwrap:
            save_nested_bool_field(
                mgr, "Options", "ParserHandlesWordwrap", True,
            )
            logger.debug("O6: Parser '%s' provides custom wordwrap", parser.name)

        # ------------------------------------------------------------------
        # O7: Forbidden Characters
        # ------------------------------------------------------------------
        if parser.forbidden_chars is not None:
            fc = parser.forbidden_chars
            # Store serialised dict for downstream steps
            if "Options" not in mgr._manifest_data:
                mgr._manifest_data["Options"] = {}
            mgr._manifest_data["Options"]["ParserForbiddenChars"] = fc.to_dict()
            mgr._mark_dirty()
            logger.debug(
                "O7: Parser '%s' has %d forbidden chars",
                parser.name, len(fc.characters),
            )

        # ------------------------------------------------------------------
        # O8: Context Markers
        # ------------------------------------------------------------------
        if parser.context_marker_rules is not None:
            rules = parser.context_marker_rules
            compiled = rules.compiled()
            lines_data = mgr.get_lines()  # list of dicts with 'idx', 'orig'
            tagged_count = 0
            for entry in lines_data:
                text = entry.get("orig", "")
                tag = None
                for pattern_name, pattern in compiled.items():
                    if pattern and pattern.search(text):
                        tag = pattern_name.replace("_pattern", "")
                        break
                if tag:
                    entry["context_marker"] = tag
                    tagged_count += 1
            if tagged_count > 0:
                mgr.set_lines(lines_data)
                save_nested_bool_field(
                    mgr, "Options", "ParserHandlesContextMarkers", True,
                )
                logger.info(
                    "O8: Parser '%s' tagged %d lines with context markers",
                    parser.name, tagged_count,
                )

    def _ensure_project_created(self) -> None:
        """Ensure a project is created for loaded files (TASK 19 Phase 5).
        
        PHASE 58.12: Uses pending project name from unified dialog if available,
        bypassing the separate ProjectNameDialog.
        
        If ManifestManager has no loaded project, prompts user for project name
        and creates a new project. Called after files are loaded.
        """
        mgr = self.manifest_manager
        if mgr is not None and not mgr.is_loaded and self._loaded_files:
            # PHASE 58.12: Check for pending project name from unified dialog
            pending_name = getattr(self, "_pending_project_name", "")
            
            # Get suggested name from step data if no pending name
            if not pending_name:
                step_data = self.get_step_data()
                suggested_name = step_data.get("suggested_project_name", "")
            else:
                suggested_name = pending_name
            
            # If no suggested name, use first file's parent folder or stem
            if not suggested_name and self._loaded_files:
                first_path = self._loaded_files[0].path
                if first_path.parent.name and first_path.parent.name not in (".", ""):
                    suggested_name = first_path.parent.name
                else:
                    suggested_name = first_path.stem
            
            # Get source file paths
            source_files = [f.path for f in self._loaded_files]
            
            # PHASE 58.12: If we have a pending name, create project directly
            if pending_name:
                # Create project directly without showing dialog
                try:
                    manifest_path = mgr.create_new(pending_name, source_files)
                    if manifest_path:
                        # Update session for legacy compatibility
                        app = self.winfo_toplevel()
                        if hasattr(app, "session"):
                            app.session.manifest_path = manifest_path
                        # Update all steps with manifest manager
                        if hasattr(app, "_step_tabs"):
                            for tab in app._step_tabs:
                                tab._manifest_manager = mgr
                        logger.info("Project created directly: %s at %s", pending_name, manifest_path)
                        # Update manifest with lines from loaded files
                        if mgr.is_loaded:
                            self._sync_lines_to_manifest()
                except Exception as e:
                    logger.warning("Could not create project directly: %s", e)
                # Clear pending name
                self._pending_project_name = ""
                return
            
            # Call App.create_new_project via toplevel (shows dialog)
            try:
                app = self.winfo_toplevel()
                create_project_method = getattr(app, "create_new_project", None)
                if create_project_method is not None:
                    manifest_path = create_project_method(source_files, suggested_name)
                    if manifest_path:
                        logger.info("Project created: %s", manifest_path)
                        # Update manifest with lines from loaded files
                        if mgr.is_loaded:
                            self._sync_lines_to_manifest()
                    else:
                        logger.debug("User cancelled project creation")
            except Exception as e:
                logger.warning("Could not create project: %s", e)

    # ------------------------------------------------------------------
    # Non-destructive file addition
    # ------------------------------------------------------------------

    def _add_files_to_existing_manifest(
        self,
        new_loaded: List,
        format_override: str = "auto",
    ) -> None:
        """Add *new_loaded* files to an already-populated manifest.

        This is the non-destructive counterpart to ``_sync_lines_to_manifest``.
        Existing lines and filedir entries are preserved; only new files are
        appended and all idx values are re-sequenced contiguously.

        Args:
            new_loaded: List of ``LoadedFile`` objects that were just loaded
                        and are **not** yet in the manifest.
            format_override: Format string used during loading.
        """
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        if not new_loaded:
            return

        # Determine whether typing is enabled
        typing_enabled = get_default(
            "session", "typing_enabled", True, bool,
        )
        if len(self._loaded_files) <= 1:
            typing_enabled = False

        # Build file_infos and new_lines_by_rel --------------------------
        new_file_infos: List[Dict[str, Any]] = []
        new_lines_by_rel: Dict[str, List[str]] = {}

        # Derive rel_paths consistent with existing filedir
        new_paths = [lf.path for lf in new_loaded]
        if len(new_paths) > 1:
            base = mgr._find_common_base(new_paths)
        else:
            base = new_paths[0].parent

        for loaded_file in new_loaded:
            file_type = ""
            if typing_enabled:
                file_type = classify_file_type(loaded_file.lines)

            try:
                rel_path = str(loaded_file.path.relative_to(base))
            except ValueError:
                rel_path = loaded_file.path.name

            new_file_infos.append({
                "rel_path": rel_path,
                "format": loaded_file.format_id,
                "line_count": loaded_file.line_count,
                "encoding": loaded_file.encoding,
                "type": file_type,
            })

            new_lines_by_rel[rel_path] = list(loaded_file.lines)

        added = mgr.add_files(new_file_infos, new_lines_by_rel)
        logger.info("Added %d new file(s) to manifest", added)

        # Copy only the new originals to the project
        try:
            filedir = mgr.get_filedir()
            source_paths: Dict[str, Path] = {}
            new_rel_set = set(new_lines_by_rel.keys())
            for entry in filedir:
                if entry.rel_path in new_rel_set:
                    # Find the matching LoadedFile
                    for lf in new_loaded:
                        try:
                            rp = str(lf.path.relative_to(base))
                        except ValueError:
                            rp = lf.path.name
                        if rp == entry.rel_path:
                            source_paths[entry.rel_path] = lf.path
                            break

            if source_paths:
                copied = mgr.copy_originals_to_project(
                    source_paths=source_paths,
                )
                if copied:
                    logger.info(
                        "Copied %d new original(s) to project", len(copied),
                    )
        except Exception as e:
            logger.warning("Failed to copy new originals: %s", e)

    def _sync_lines_to_manifest(self) -> None:
        """Sync loaded file lines to the manifest (TASK 19 Phase 5).
        
        TASK 35.1: Also populates filedir for input/output decoupling.
        Lines no longer store source_file — filedir maps idx ranges to files.
        """
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return
        
        # Determine whether typing is enabled
        typing_enabled = get_default(
            "session", "typing_enabled", True, bool,
        )
        # Block typing when only one file loaded
        if len(self._loaded_files) <= 1:
            typing_enabled = False
        
        # Collect all lines (compact: idx + orig only)
        lines: List[Dict[str, Any]] = []
        file_infos: List[Dict[str, Any]] = []
        idx = 0
        
        for loaded_file in self._loaded_files:
            _file_start_idx = idx
            for line_text in loaded_file.lines:
                lines.append({
                    "idx": idx,
                    "orig": line_text,
                })
                idx += 1
            
            # Classify file type when typing is enabled
            file_type = ""
            if typing_enabled:
                file_type = classify_file_type(loaded_file.lines)
            
            # Build file info for filedir
            file_infos.append({
                "path": str(loaded_file.path),
                "format": loaded_file.format_id,
                "line_count": loaded_file.line_count,
                "encoding": loaded_file.encoding,
                "type": file_type,
            })
        
        # Update manifest with lines
        mgr.set_lines(lines)
        
        # TASK 35.1: Build and set filedir
        filedir_entries = mgr.build_filedir_from_files(file_infos)
        mgr.set_filedir(filedir_entries)
        
        # Compute and store source_root as folder name only
        source_paths = [f.path for f in self._loaded_files]
        mgr.source_root = mgr.compute_source_root(source_paths)
        
        # TASK 35.2: Copy original files to project folder
        self._copy_originals_to_project()

    def _copy_originals_to_project(self) -> None:
        """Copy source files to the project's Original/ directory.
        
        TASK 35.2: Ensures the project can be reopened and processed
        even if original source files are moved or deleted.
        """
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return
        
        try:
            # Build rel_path → absolute source path mapping from loaded files
            filedir = mgr.get_filedir()
            source_paths: Dict[str, Path] = {}
            for loaded_file in self._loaded_files:
                # Match by filename against filedir entries
                for entry in filedir:
                    entry_name = Path(entry.rel_path).name
                    if loaded_file.path.name == entry_name:
                        source_paths[entry.rel_path] = loaded_file.path
                        break

            copied = mgr.copy_originals_to_project(source_paths=source_paths)
            if copied:
                logger.info("Copied %d original file(s) to project", len(copied))
        except Exception as e:
            logger.warning("Failed to copy originals: %s", e)
            # Non-fatal - project can still work without copies

    def _on_load_manifest(self) -> None:
        """Handle Load Manifest button click."""
        filepath = filedialog.askopenfilename(
            title="Select Manifest File",
            filetypes=[
                ("CherryAI Manifest", "*.CherryAI.json"),
                ("JSON Files", "*.json"),
                ("All Files", "*.*"),
            ],
        )

        if not filepath:
            return

        path = Path(filepath)
        if self._load_manifest_file(path):
            messagebox.showinfo(
                "Manifest Loaded",
                f"Successfully loaded manifest:\n{path.name}",
            )

    def _on_load_detected_manifest(self) -> None:
        """Handle Load Manifest button for detected manifest."""
        if self._current_file_index < 0:
            return

        file = self._loaded_files[self._current_file_index]
        if file.manifest_path and file.manifest_path.exists():
            if self._load_manifest_file(file.manifest_path):
                messagebox.showinfo(
                    "Manifest Loaded",
                    f"Successfully loaded manifest:\n{file.manifest_path.name}",
                )

    def _on_clear_all(self) -> None:
        """Handle Clear All button click."""
        if not self._loaded_files:
            return

        if messagebox.askyesno(
            "Clear All",
            "Clear all loaded files? This cannot be undone.",
        ):
            self._loaded_files.clear()
            self._current_file_index = -1
            self._update_file_list()
            self._update_preview()
            self._update_summary()
            self.set_status("not-started")
            # Clear session state
            if self.session is not None:
                self.session.loaded_files.clear()
            self.set_step_data({})
            logger.info("Cleared all loaded files")

    # ------------------------------------------------------------------
    # Import Translation
    # ------------------------------------------------------------------

    def _on_import_translations(self) -> None:
        """Import translations from another manifest with a selection dialog.

        Opens a file dialog to select a source manifest, then shows
        a selection dialog to let the user choose which line fields
        and settings sections to import.
        """
        if not self._manifest_manager:
            messagebox.showwarning("Warning", "No project loaded.")
            return

        import json

        source_path = filedialog.askopenfilename(
            title="Select Source Manifest",
            filetypes=[
                ("CherryAI Manifest", "*.CherryAI.json"),
                ("All Files", "*.*"),
            ],
        )
        if not source_path:
            return

        try:
            with open(source_path, "r", encoding="utf-8") as f:
                source_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read manifest: {e}")
            return

        # Show selection dialog
        dialog = _ImportTranslationDialog(self, source_data)
        self.wait_window(dialog)
        if not dialog.result:
            return

        selections = dialog.result
        mgr = self._manifest_manager

        # ---- Import line fields ----
        line_stats = self._import_line_fields(
            source_data, selections, mgr,
        )

        # ---- Import settings sections ----
        section_count = self._import_settings_sections(
            source_data, selections, mgr,
        )

        # Log import metadata
        mgr.update_step_data(0, "last_import", {
            "source_manifest": str(source_path),
            "lines_matched": line_stats["matched"],
            "lines_total": line_stats["total"],
            "sections_imported": section_count,
            "timestamp": datetime.now().isoformat(),
        })

        # Build summary message
        parts: List[str] = []
        if line_stats["matched"] > 0:
            parts.append(
                f"Lines: {line_stats['matched']}/{line_stats['total']} matched"
            )
        if section_count > 0:
            parts.append(f"Settings sections: {section_count}")
        if not parts:
            parts.append("No data imported (nothing selected).")

        messagebox.showinfo("Import Complete", "\n".join(parts))
        logger.info(
            "Import from %s — lines: %d/%d, sections: %d",
            source_path, line_stats["matched"],
            line_stats["total"], section_count,
        )

        # Refresh preview
        self._update_preview()

    def _import_line_fields(
        self,
        source_data: Dict[str, Any],
        selections: Dict[str, bool],
        mgr: Any,
    ) -> Dict[str, int]:
        """Import selected line fields from source manifest.

        Args:
            source_data: Parsed JSON of the source manifest.
            selections: Checkbox selections from the dialog.
            mgr: ManifestManager of the current project.

        Returns:
            Dict with ``matched`` and ``total`` counts.
        """
        source_lines = source_data.get("lines", [])
        if not source_lines:
            return {"matched": 0, "total": 0}

        # Determine which field groups are selected
        field_map: Dict[str, List[str]] = {
            "import_prepro": ["prepro"],
            "import_tags": ["tag"],
            "import_translated": ["tl", "preedit"],
            "import_postpro": ["postpro"],
            "import_wordwrap": ["wordwr"],
        }

        fields_to_copy: List[str] = []
        for key, fields in field_map.items():
            if selections.get(key, False):
                fields_to_copy.extend(fields)

        # QA fields (numbered: edit1, edit2, tlc1, tlc2, overwrite)
        copy_qa = selections.get("import_qa", False)

        skip_new = selections.get("skip_new_lines", False)

        if not fields_to_copy and not copy_qa:
            return {"matched": 0, "total": 0}

        # Build lookup: orig → source line entry
        source_lookup: Dict[str, Dict[str, Any]] = {}
        for sl in source_lines:
            orig = sl.get("orig", "")
            if orig and orig not in source_lookup:
                source_lookup[orig] = sl

        current_lines = mgr.get_lines()
        matched = 0
        total = len(current_lines)

        for line in current_lines:
            orig = line.get("orig", "")
            if not orig:
                continue

            match = source_lookup.get(orig)
            if match is None:
                continue

            # Skip if line already has data and skip_new is on
            if skip_new and line.get("tl", ""):
                continue

            matched += 1

            for field in fields_to_copy:
                if field in match and match[field]:
                    line[field] = match[field]

            if copy_qa:
                for key, val in match.items():
                    if (key.startswith("edit") or key.startswith("tlc")
                            or key == "overwrite") and val:
                        line[key] = val

        mgr.set_lines(current_lines)
        return {"matched": matched, "total": total}

    def _import_settings_sections(
        self,
        source_data: Dict[str, Any],
        selections: Dict[str, bool],
        mgr: Any,
    ) -> int:
        """Import selected settings sections from source manifest.

        Args:
            source_data: Parsed JSON of the source manifest.
            selections: Checkbox selections from the dialog.
            mgr: ManifestManager of the current project.

        Returns:
            Number of sections imported.
        """
        count = 0

        # Analysis step state
        if selections.get("import_analysis", False):
            src_ss = source_data.get("step_state", {}).get("Analysis")
            if src_ss:
                mgr._manifest_data.setdefault("step_state", {})["Analysis"] = src_ss
                mgr._mark_dirty()
                count += 1

        # Information metadata
        if selections.get("import_information", False):
            src_ss = source_data.get("step_state", {}).get("Information")
            src_meta = (
                src_ss.get("data", {}).get("metadata", {}) if src_ss else {}
            )
            if src_meta:
                mgr.set_info_metadata(src_meta)
                count += 1

            # Glossary
            src_glossary = source_data.get("glossary")
            if src_glossary:
                mgr._manifest_data["glossary"] = src_glossary
                mgr._mark_dirty()

            # Code patterns (Code Database)
            src_cp = source_data.get("code_patterns")
            if src_cp:
                mgr._manifest_data["code_patterns"] = src_cp
                mgr._mark_dirty()

            # Characters
            src_chars = source_data.get("characters")
            if src_chars:
                mgr._manifest_data["characters"] = src_chars
                mgr._mark_dirty()

        # Preprocessing settings (top-level keys)
        if selections.get("import_preprocessing", False):
            _PREPRO_KEYS = [
                "Deduplication", "DeduplicationThreshold",
                "EllipsisCompression", "SymbolConversion",
                "SpeakerNameReplacement", "CodeSpacingRules",
                "ProtectCodePatterns", "CustomPlaceholders",
                "AnchorRemoval",
            ]
            for key in _PREPRO_KEYS:
                if key in source_data:
                    mgr._manifest_data[key] = source_data[key]
            mgr._mark_dirty()
            count += 1

        # Costs / Translation settings (RequestOptions)
        if selections.get("import_costs", False):
            src_ro = source_data.get("RequestOptions")
            if src_ro:
                mgr._manifest_data["RequestOptions"] = src_ro
                mgr._mark_dirty()
                count += 1

        if selections.get("import_translation", False):
            # Translation step state
            src_ss = source_data.get("step_state", {}).get("Translation")
            if src_ss:
                mgr._manifest_data.setdefault("step_state", {})["Translation"] = src_ss
                mgr._mark_dirty()
                count += 1

        # Postprocessing
        if selections.get("import_postprocessing", False):
            src_pp = source_data.get("PostProcessing")
            if src_pp:
                mgr._manifest_data["PostProcessing"] = src_pp
                mgr._mark_dirty()
                count += 1

        # Wordwrap
        if selections.get("import_wordwrap_settings", False):
            src_ww = source_data.get("WordwrapSettings")
            if src_ww:
                mgr._manifest_data["WordwrapSettings"] = src_ww
                mgr._mark_dirty()
                count += 1

        # QA (ValidationRules + QAOptions)
        if selections.get("import_qa_settings", False):
            src_vr = source_data.get("ValidationRules")
            if src_vr:
                mgr._manifest_data["ValidationRules"] = src_vr
            src_qa = source_data.get("QAOptions")
            if src_qa:
                mgr._manifest_data["QAOptions"] = src_qa
            # Character validation
            for k in ("CharacterWhitelist", "CharacterBlacklist",
                      "WordBlacklist", "AutofixMap"):
                if k in source_data:
                    mgr._manifest_data[k] = source_data[k]
            mgr._mark_dirty()
            count += 1

        # Output / File settings
        if selections.get("import_file_settings", False):
            src_of = source_data.get("OutputFormat")
            if src_of:
                mgr._manifest_data["OutputFormat"] = src_of
                mgr._mark_dirty()
                count += 1

        return count

    def _on_file_listbox_right_click(self, event: tk.Event) -> None:
        """Handle right-click on file tree to show context menu.

        Preserves multiselect: only changes selection when the clicked
        row is not already part of the current selection.
        """
        try:
            item = self._file_tree.identify_row(event.y)
            if item and item not in self._file_tree.selection():
                self._file_tree.selection_set(item)
            self._file_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._file_context_menu.grab_release()

    def _on_select_all_in_folder(self) -> None:
        """Select all files in the folder of the currently selected item."""
        selection = self._file_tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self._file_tree.parent(item)
        # If the item itself is a folder (has children), select children
        children = self._file_tree.get_children(item)
        if children:
            parent = item
        elif parent:
            children = self._file_tree.get_children(parent)
        else:
            children = self._file_tree.get_children("")

        file_items = [c for c in children if c in self._tree_item_to_index]
        if file_items:
            self._file_tree.selection_set(file_items)

    def _on_select_all_files(self) -> None:
        """Select all files in the tree (PHASE 58.7)."""
        # Get all file items (not folders)
        all_file_items = list(self._tree_item_to_index.keys())
        if all_file_items:
            self._file_tree.selection_set(all_file_items)

    def _set_selected_file_type(self, new_type: str) -> None:
        """Set the type of all selected file(s) in the filedir.

        Updates both the manifest filedir entry and the tree display.

        Args:
            new_type: One of ``"dialogue"``, ``"menu"``, or ``"mixed"``.
        """
        selection = self._file_tree.selection()
        if not selection:
            return

        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        filedir = mgr.get_filedir()

        for item_id in selection:
            # Resolve file indices (folders → all children)
            file_idx = self._tree_item_to_index.get(item_id)
            if file_idx is not None:
                indices = [file_idx]
            else:
                indices = [
                    self._tree_item_to_index[c]
                    for c in self._file_tree.get_children(item_id)
                    if c in self._tree_item_to_index
                ]

            for idx in indices:
                if 0 <= idx < len(filedir):
                    filedir[idx].type = new_type

        mgr.set_filedir(filedir)
        self._update_file_list()

    def _on_expand_all_tree(self) -> None:
        """Expand all folders in the tree (PHASE 58.7)."""
        def expand_recursive(item: str) -> None:
            for child in self._file_tree.get_children(item):
                self._file_tree.item(child, open=True)
                expand_recursive(child)

        # Expand all root items and their children
        for root_item in self._file_tree.get_children(""):
            self._file_tree.item(root_item, open=True)
            expand_recursive(root_item)

    def _on_collapse_all_tree(self) -> None:
        """Collapse all folders in the tree (PHASE 58.7)."""
        def collapse_recursive(item: str) -> None:
            for child in self._file_tree.get_children(item):
                collapse_recursive(child)
                self._file_tree.item(child, open=False)

        # Collapse all root items and their children
        for root_item in self._file_tree.get_children(""):
            collapse_recursive(root_item)
            self._file_tree.item(root_item, open=False)

    def _on_remove_selected_file(self) -> None:
        """Remove all selected files from the loaded files list."""
        selection = self._file_tree.selection()
        if not selection:
            return

        # Collect indices to remove (sorted descending to avoid index shift)
        indices_to_remove: List[int] = []
        for item_id in selection:
            if item_id in self._tree_item_to_index:
                indices_to_remove.append(self._tree_item_to_index[item_id])
            else:
                # It's a folder — remove all children
                for child in self._file_tree.get_children(item_id):
                    if child in self._tree_item_to_index:
                        indices_to_remove.append(self._tree_item_to_index[child])

        indices_to_remove = sorted(set(indices_to_remove), reverse=True)
        
        mgr = self.manifest_manager

        for idx in indices_to_remove:
            if 0 <= idx < len(self._loaded_files):
                removed = self._loaded_files[idx]
                
                # Remove from manifest manager if loaded
                if mgr is not None and mgr.is_loaded:
                    for entry in mgr.get_filedir():
                        if Path(entry.rel_path).name == removed.path.name:
                            mgr.remove_file(entry.rel_path)
                            break

                del self._loaded_files[idx]
                if self.session is not None and idx < len(self.session.loaded_files):
                    del self.session.loaded_files[idx]
                logger.info("Removed file: %s", removed.path)

        # Reset current index
        if self._loaded_files:
            self._current_file_index = 0
        else:
            self._current_file_index = -1

        self._update_file_list()
        self._update_preview()
        self._update_summary()

        if not self._loaded_files:
            self.set_status("not-started")
            
        if mgr is not None and mgr.is_loaded:
            mgr.save()

    def _on_file_select(self, event: tk.Event) -> None:
        """Handle file selection in tree."""
        selection = self._file_tree.selection()
        if selection:
            item_id = selection[0]
            if item_id in self._tree_item_to_index:
                self._current_file_index = self._tree_item_to_index[item_id]
                self._update_preview()

    def _on_column_sort(self, column: str) -> None:
        """Handle click on a column header to toggle sort.

        Clicking the same column toggles ascending/descending.
        Clicking a different column sorts ascending by that column.

        Args:
            column: Column identifier (``"name"``, ``"type"``, or ``"lines"``).
        """
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True
        self._refresh_sort_headings()
        self._update_file_list()

    def _refresh_sort_headings(self) -> None:
        """Update column heading text with sort direction indicators."""
        labels = {"name": "Name", "type": "Type", "lines": "Lines"}
        for col, base in labels.items():
            indicator = ""
            if self._sort_column == col:
                indicator = " ▲" if self._sort_ascending else " ▼"
            col_id = "#0" if col == "name" else col
            self._file_tree.heading(col_id, text=f"{base}{indicator}")

    # ----------------------------- File Loading ----------------------------- #

    def _load_file(
        self,
        path: Path,
        encoding: str = "auto",
        format_override: str = "auto",
    ) -> bool:
        """Load a file and extract its content.

        Args:
            path: Path to the file.
            encoding: Text encoding or "auto" for auto-detection.
            format_override: Format override or "auto".

        Returns:
            True if loaded successfully.
        """
        try:
            # TASK 39.3: Auto-detect encoding if set to "auto"
            if encoding == "auto":
                encoding = self._detect_encoding(path)

            # Detect format — try parser registry first for auto or parser names
            if format_override != "auto":
                format_id = format_override
            else:
                # Auto-detect: try parser registry, then fall back to extension map
                try:
                    from CherryAI.formats import detect_parser as _detect_parser
                    parser = _detect_parser(path)
                    if parser is not None:
                        format_id = parser.name.lower()
                    else:
                        format_id = FORMAT_MAP.get(path.suffix.lower(), "txt")
                except Exception:
                    format_id = FORMAT_MAP.get(path.suffix.lower(), "txt")

            # Handshake: validate parser selection (M1-M3 check)
            if not self._validate_parser_selection(format_id):
                return False

            # Extract lines using format handler
            lines = self._extract_lines(path, format_id, encoding)

            # Handshake: per-line token validation
            if not self._validate_extracted_lines(lines, path.name):
                return False

            # Check for existing manifest (don't auto-create individual manifests)
            # The unified manifest is created by _ensure_project_created() after all files load
            manifest_path = self._find_manifest(path)

            # Create LoadedFile
            loaded = LoadedFile(
                path=path,
                format_id=format_id,
                lines=lines,
                manifest_path=manifest_path,
                encoding=encoding,
            )

            self._loaded_files.append(loaded)

            # Update session state
            if self.session is not None:
                self.session.loaded_files.append(path)
            self._update_step_data()

            # Store last loaded manifest path for auto-restore
            if manifest_path and self.session is not None:
                self.session.manifest_path = manifest_path

            logger.info("Loaded file: %s (%d lines)", path.name, len(lines))
            return True

        except Exception as e:
            logger.error("Failed to load file %s: %s", path, e)
            messagebox.showerror(
                "Load Error",
                f"Failed to load file:\n{path.name}\n\nError: {e}",
            )
            return False

    def _extract_lines(
        self,
        path: Path,
        format_id: str,
        encoding: str,
    ) -> List[str]:
        """Extract lines from a file.

        Args:
            path: File path.
            format_id: Format identifier (handler id or parser name).
            encoding: Text encoding.

        Returns:
            List of extracted lines.
        """
        # Try parser registry first (handles parser names like "lightvn")
        try:
            from CherryAI.formats import get_parser_registry
            parser = get_parser_registry().get(format_id)
            if parser is not None:
                return parser.extract(path)
        except Exception:
            pass

        try:
            # Try to use formats module
            from CherryAI.formats import get_handler

            handler = get_handler(format_id)
            if handler:
                return handler.extract(path, encoding)
        except ImportError:
            pass

        # Fallback: simple text reading
        if format_id == "txt":
            content = path.read_text(encoding=encoding)
            return content.splitlines()
        elif format_id in ("csv", "tsv"):
            import csv
            delimiter = "," if format_id == "csv" else "\t"
            with open(path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f, delimiter=delimiter)
                return [row[0] if row else "" for row in reader]
        elif format_id == "json":
            with open(path, "r", encoding=encoding) as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(item) if not isinstance(item, str) else item for item in data]
            elif isinstance(data, dict):
                # Dictionary format: keys are original text
                return [str(key) for key in data.keys()]
            return []
        elif format_id == "xlsx":
            try:
                from openpyxl import load_workbook
                wb = load_workbook(path, read_only=True)
                ws = wb.active
                if ws is None:
                    return []
                lines = []
                for row in ws.iter_rows(values_only=True):
                    if row and row[0] is not None:
                        lines.append(str(row[0]))
                return lines
            except ImportError:
                raise ValueError("openpyxl required for Excel files")
        else:
            raise ValueError(f"Unsupported format: {format_id}")

    def _find_manifest(self, path: Path) -> Optional[Path]:
        """Find associated manifest for a file.

        Args:
            path: Source file path.

        Returns:
            Manifest path if found, None otherwise.
        """
        # Standard manifest naming: {filename}.CherryAI.json
        manifest_dir = path.parent / "Projects"
        manifest_name = f"{path.stem}.CherryAI.json"

        # Check in manifests/ subdirectory
        manifest_path = manifest_dir / manifest_name
        if manifest_path.exists():
            return manifest_path

        # Check in same directory
        manifest_path = path.parent / manifest_name
        if manifest_path.exists():
            return manifest_path

        # Check in project's manifests folder
        try:
            project_manifests = Path(__file__).parent.parent.parent / "Projects" / manifest_name
            if project_manifests.exists():
                return project_manifests
        except Exception:
            pass

        return None

    def _load_manifest_file(self, path: Path) -> bool:
        """Load a manifest file.

        Args:
            path: Manifest file path.

        Returns:
            True if loaded successfully.
        """
        try:
            # Use ManifestManager to load (handles migration)
            mgr = self.manifest_manager
            if mgr is None:
                # Fallback - direct load
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                if not mgr.load(path):
                    raise ValueError("ManifestManager failed to load manifest")
                data = mgr.get_raw_data()

            # Store manifest path in session
            if self.session is not None:
                self.session.manifest_path = path

            # Check source file status and show appropriate warnings
            source_files_status = self._check_source_files_status(data)
            
            # Update step data
            step_data = self.get_step_data()
            step_data["manifest_path"] = str(path)
            step_data["manifest_data"] = data
            step_data["source_files_status"] = source_files_status
            self.set_step_data(step_data)
            
            # Populate loaded files from manifest
            self._populate_from_manifest(data)

            logger.info("Loaded manifest: %s", path)
            return True

        except Exception as e:
            logger.error("Failed to load manifest %s: %s", path, e)
            messagebox.showerror(
                "Manifest Error",
                f"Failed to load manifest:\n{path.name}\n\nError: {e}",
            )
            return False

    def _check_source_files_status(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Check status of source files using filedir + Original/ directory.

        Files are expected in the project's ``Original/`` directory after the
        first load.  Falls back to ``step_state.Input.data.files`` for the
        original absolute paths when ``Original/`` has not been populated yet.

        Returns:
            Dict mapping rel_path (or abs path) to status:
            ``'found'``, ``'recoverable'``, ``'missing'``
        """
        status: Dict[str, str] = {}

        RECOVERABLE_FORMATS = {"txt", "csv", "tsv", "json"}
        _NON_RECOVERABLE_FORMATS = {"rpgm", "xlsx", "epub", "pdf"}  # noqa: F841

        mgr = self.manifest_manager
        filedir = data.get("filedir", [])
        has_lines = bool(data.get("lines"))

        # Determine where originals live
        original_dir: Optional[Path] = None
        if mgr is not None and mgr.is_loaded:
            original_dir = mgr.get_original_dir()

        for entry in filedir:
            rel_path = entry.get("rel_path", "unknown")
            file_format = entry.get("format", "txt")
            display_key = rel_path  # Use rel_path as status key

            # Check Original/ directory first
            found = False
            if original_dir is not None:
                candidate = original_dir / rel_path
                if candidate.exists():
                    found = True

            if found:
                status[display_key] = "found"
            elif has_lines and file_format in RECOVERABLE_FORMATS:
                status[display_key] = "recoverable"
            else:
                status[display_key] = "missing"

        # If no filedir, try legacy source_files for old manifests
        if not filedir:
            source_files = data.get("source_files", [])
            if not source_files:
                sf = data.get("source_file")
                if sf:
                    source_files = [sf]
            file_format = data.get("format", "txt")
            for sf in source_files:
                sp = Path(sf)
                if sp.exists():
                    status[sf] = "found"
                elif has_lines and file_format in RECOVERABLE_FORMATS:
                    status[sf] = "recoverable"
                else:
                    status[sf] = "missing"

        # Show warnings if needed
        recoverable_files = [f for f, s in status.items() if s == "recoverable"]
        missing_files = [f for f, s in status.items() if s == "missing"]

        if recoverable_files:
            file_list = "\n".join(Path(f).name for f in recoverable_files[:5])
            if len(recoverable_files) > 5:
                file_list += f"\n...and {len(recoverable_files) - 5} more"
            messagebox.showwarning(
                "Source Files Not Found",
                "Original source files not found, but content can be "
                f"recovered from manifest:\n\n{file_list}",
            )

        if missing_files:
            file_list = "\n".join(Path(f).name for f in missing_files[:5])
            if len(missing_files) > 5:
                file_list += f"\n...and {len(missing_files) - 5} more"

            response = messagebox.askyesno(
                "Source Files Missing",
                "Original source files not found and cannot be "
                f"recovered:\n\n{file_list}\n\n"
                "These files have complex formats that require the "
                "original file.\n\n"
                "Would you like to browse and relocate them?",
            )

            if response:
                for missing_file in missing_files:
                    original_name = Path(missing_file).name
                    relocated = filedialog.askopenfilename(
                        title=f"Locate: {original_name}",
                        initialfile=original_name,
                        filetypes=[
                            ("All Supported", "*.txt *.csv *.tsv *.json *.xlsx"),
                            ("All Files", "*.*"),
                        ],
                    )
                    if relocated:
                        # Update the status and manifest data
                        status[missing_file] = "relocated"
                        # Store the new path for later use
                        self._relocated_files = getattr(self, "_relocated_files", {})
                        self._relocated_files[missing_file] = relocated
        
        return status

    def _populate_from_manifest(self, data: Dict[str, Any]) -> None:
        """Populate loaded files from manifest data.
        
        Args:
            data: Manifest data dictionary.
        
        TASK 32.1: Uses relocated files if available.
        Files are resolved via the project's ``Original/`` directory;
        ``source_root`` is a display-only folder name.
        """
        # Clear existing loaded files
        self._loaded_files.clear()
        self._current_file_index = -1
        
        lines_data = data.get("lines", [])
        filedir = data.get("filedir", [])
        source_root = data.get("source_root", "")
        
        # Get relocated files (TASK 32.1)
        relocated = getattr(self, "_relocated_files", {})
        
        # Determine Original/ directory for file resolution
        mgr = self.manifest_manager
        original_dir: Optional[Path] = None
        if mgr is not None and mgr.is_loaded:
            original_dir = mgr.get_original_dir()
        
        # v3.2 format: use filedir to map lines to files
        if filedir:
            # Set folder root for display only (source_root is just a name)
            if source_root:
                self._folder_root = Path(source_root)
            
            for file_entry in filedir:
                first_idx = file_entry.get("first_idx", 0)
                last_idx = file_entry.get("last_idx", first_idx)
                rel_path = file_entry.get("rel_path", "unknown")
                file_format = file_entry.get("format", "txt")
                
                # Resolve via Original/ directory (project-local copies)
                if original_dir is not None:
                    file_path = original_dir / rel_path
                else:
                    file_path = Path(rel_path)
                
                # Check if file was relocated (TASK 32.1)
                actual_path = Path(relocated.get(rel_path, str(file_path)))
                
                # Extract lines for this file from lines_data using index range
                file_lines = []
                for idx in range(first_idx, last_idx + 1):
                    if idx < len(lines_data):
                        line_entry = lines_data[idx]
                        # Get the original text from the line entry
                        if isinstance(line_entry, dict):
                            file_lines.append(line_entry.get("orig", ""))
                        else:
                            file_lines.append(str(line_entry))
                
                # Create LoadedFile
                loaded = LoadedFile(
                    path=actual_path if actual_path.exists() else file_path,
                    format_id=file_format,
                    lines=file_lines,
                    manifest_path=self.session.manifest_path if self.session else None,
                )
                self._loaded_files.append(loaded)
        else:
            # Legacy format: fall back to source_files approach
            source_files = data.get("source_files", [])
            if not source_files:
                source_file = data.get("source_file")
                if source_file:
                    source_files = [source_file]
            
            file_format = data.get("format", "txt")
            
            # Group lines by source file (legacy format where lines have source_file)
            lines_by_file: Dict[str, List[str]] = {}
            for line in lines_data:
                if isinstance(line, dict):
                    source = line.get("source_file", source_files[0] if source_files else "unknown")
                    if source not in lines_by_file:
                        lines_by_file[source] = []
                    lines_by_file[source].append(line.get("orig", ""))
            
            # Create LoadedFile entries
            for source_file in source_files:
                # Check if file was relocated (TASK 32.1)
                actual_path = Path(relocated.get(source_file, source_file))
                path = Path(source_file)
                lines = lines_by_file.get(source_file, [])
                
                # If we have no lines from manifest but file exists, try loading it
                # Use actual_path which may be relocated (TASK 32.1)
                if not lines and actual_path.exists():
                    try:
                        encoding = self._encoding_var.get() if self._encoding_var else "utf-8"
                        format_override = self._format_var.get() if self._format_var else "auto"
                        self._load_file(actual_path, encoding, format_override)
                        continue
                    except Exception as e:
                        logger.warning("Could not load source file %s: %s", actual_path, e)
                
                # Create LoadedFile from manifest data (use actual_path for relocated files)
                loaded = LoadedFile(
                    path=actual_path if actual_path.exists() else path,
                    format_id=file_format,
                    lines=lines,
                    manifest_path=self.session.manifest_path if self.session else None,
                )
                self._loaded_files.append(loaded)
        
        # Update UI
        self._update_file_list()
        self._update_summary()
        if self._loaded_files:
            self._select_first_file_in_tree()
        
        # Mark step as in-progress if we have files
        if self._loaded_files:
            self.set_status("in-progress")

    # ----------------------------- UI Updates ----------------------------- #

    def _update_file_list(self) -> None:
        """Update the file tree with collapsible folder hierarchy.

        TASK 39.4: Builds a tree structure from loaded files. When files
        come from a folder, parent nodes are collapsible folders; leaf
        nodes are individual files with line counts.

        PHASE 58.7: Folders collapsed by default, folders sorted above files.

        Folders appear ABOVE files at the same directory level. This is achieved
        by a two-phase approach:
        1. First, collect all unique folder paths and create folder nodes
        2. Then, insert files under their respective parent nodes

        Clickable column headers control sort order (ascending/descending).
        Filter textbox filters rows by matching any column.
        """
        # Clear existing tree
        for item in self._file_tree.get_children():
            self._file_tree.delete(item)
        self._tree_item_to_index.clear()

        # Get source file status from step data
        step_data = self.get_step_data()
        source_status = step_data.get("source_files_status", {})

        # Build index→type map from manifest filedir
        type_map: Dict[int, str] = {}
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            for idx, entry in enumerate(mgr.get_filedir()):
                type_map[idx] = entry.type

        # Read sort state from clickable column headers
        sort_col = getattr(self, "_sort_column", "")
        sort_asc = getattr(self, "_sort_ascending", True)

        # Read filter text
        filter_text = ""
        if hasattr(self, "_file_filter_var"):
            filter_text = self._file_filter_var.get().strip().lower()

        # Build folder → tree item ID mapping for hierarchy
        folder_items: Dict[str, str] = {}

        # Phase 1: Collect all unique folder paths from all files
        all_folders: set = set()
        file_display_data: List[Tuple[str, int, 'LoadedFile']] = []

        for i, file in enumerate(self._loaded_files):
            display_name = self._get_display_name(file.path)
            file_type = type_map.get(i, "")

            # Apply filter: match against name, type, or line count
            if filter_text:
                name_match = filter_text in display_name.lower()
                type_match = filter_text in file_type.lower()
                count_match = filter_text in str(file.line_count)
                if not (name_match or type_match or count_match):
                    continue

            parts = display_name.replace("\\", "/").split("/")

            # Collect all parent folder paths
            for depth in range(1, len(parts)):
                folder_path = "/".join(parts[:depth])
                all_folders.add(folder_path)

            file_display_data.append((display_name, i, file))

        # Apply sort based on column header clicks
        if sort_col == "lines":
            file_display_data.sort(
                key=lambda x: x[2].line_count, reverse=not sort_asc,
            )
        elif sort_col == "type":
            file_display_data.sort(
                key=lambda x: type_map.get(x[1], "").lower(),
                reverse=not sort_asc,
            )
        elif sort_col == "name":
            file_display_data.sort(
                key=lambda x: x[0].lower(), reverse=not sort_asc,
            )
        else:
            # Default filetree: alphabetical by display name
            file_display_data.sort(key=lambda x: x[0].lower())

        # Phase 2: Create all folder nodes first (sorted alphabetically)
        # Only for default filetree sort — flat list for explicit column sorts
        use_folders = sort_col == "" and not filter_text

        if use_folders:
            sorted_folders = sorted(all_folders, key=str.lower)
            for folder_path in sorted_folders:
                parts = folder_path.split("/")
                parent = ""
                for depth, folder_name in enumerate(parts):
                    folder_key = "/".join(parts[:depth + 1])
                    if folder_key not in folder_items:
                        folder_id = self._file_tree.insert(
                            parent, "end", text=f"📂 {folder_name}", open=False,
                        )
                        folder_items[folder_key] = folder_id
                    parent = folder_items[folder_key]

        # Phase 3: Insert all files
        for display_name, i, file in file_display_data:
            parts = display_name.replace("\\", "/").split("/")

            # Determine status tag for coloring
            file_path_str = str(file.path)
            status = source_status.get(
                file_path_str, "found" if file.path.exists() else "missing",
            )
            tags: Tuple[str, ...] = ()
            if status == "found" and file.manifest_path:
                tags = ("manifest",)
            elif status == "recoverable":
                tags = ("recoverable",)
            elif status == "missing":
                tags = ("missing",)

            file_type = type_map.get(i, "")

            if use_folders and len(parts) > 1:
                parent_folder_path = "/".join(parts[:-1])
                parent = folder_items.get(parent_folder_path, "")
                item_id = self._file_tree.insert(
                    parent, "end", text=f"📄 {parts[-1]}",
                    values=(file_type, file.line_count), tags=tags,
                )
            else:
                label = parts[-1] if use_folders else display_name
                item_id = self._file_tree.insert(
                    "", "end", text=f"📄 {label}",
                    values=(file_type, file.line_count), tags=tags,
                )

            self._tree_item_to_index[item_id] = i

        # Configure tag colors
        self._file_tree.tag_configure("manifest", foreground=THEME.accent_success)
        self._file_tree.tag_configure("recoverable", foreground="#DAA520")
        self._file_tree.tag_configure("missing", foreground=THEME.accent_error)

    def _get_display_name(self, file_path: Path) -> str:
        """Get display name for a file, showing relative path if from folder.

        Args:
            file_path: The full path to the file.

        Returns:
            Display name showing subfolder prefix if applicable.
        """
        if self._folder_root is not None:
            try:
                relative = file_path.relative_to(self._folder_root)
                # Return with forward slashes for consistency
                return str(relative).replace("\\", "/")
            except ValueError:
                # Not relative to folder root, use filename
                pass
        return file_path.name

    def _update_preview(self) -> None:
        """Update the preview table for current file or cross-file search.

        When a search term is entered, searches across ALL loaded files and
        shows matching lines with their global idx. When no search term is
        active, shows lines from the currently selected file only.
        """
        # Clear existing
        for item in self._preview_tree.get_children():
            self._preview_tree.delete(item)

        if not self._loaded_files:
            return

        # Build line-level tag map from manifest
        tag_map: Dict[int, str] = {}
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            all_lines = mgr.get_lines()
            for line_data in all_lines:
                idx_val = line_data.get("idx", -1)
                line_tag = line_data.get("tag", "")
                if line_tag:
                    tag_map[idx_val] = line_tag

        # Read search text
        search_text = ""
        if hasattr(self, "_preview_search_var"):
            search_text = self._preview_search_var.get().strip().lower()

        # Build filedir offset map
        offsets: List[int] = []
        if mgr is not None and mgr.is_loaded:
            filedir = mgr.get_filedir()
            for entry in filedir:
                offsets.append(entry.first_idx)
        else:
            offset = 0
            for f in self._loaded_files:
                offsets.append(offset)
                offset += f.line_count

        if search_text:
            # Cross-file search: show matching lines from ALL files
            self._update_preview_cross_file(search_text, tag_map, offsets)
        else:
            # Single-file preview
            self._update_preview_single_file(tag_map, offsets)

    def _update_preview_single_file(
        self,
        tag_map: Dict[int, str],
        offsets: List[int],
    ) -> None:
        """Show preview lines from the currently selected file.

        Args:
            tag_map: Mapping of global idx to tag string.
            offsets: List of global start offsets per file.
        """
        if self._current_file_index < 0:
            return

        file = self._loaded_files[self._current_file_index]
        global_offset = (
            offsets[self._current_file_index]
            if self._current_file_index < len(offsets)
            else 0
        )

        max_preview = 1000
        shown = 0
        for i, line in enumerate(file.lines):
            if shown >= max_preview:
                break

            display_line = (
                line.replace("\r\n", "↵").replace("\n", "↵").replace("\r", "↵")
            )

            global_idx = global_offset + i
            line_tag = tag_map.get(global_idx, "")
            self._preview_tree.insert(
                "",
                "end",
                iid=str(global_idx),
                values=(global_idx + 1, i + 1, display_line, line_tag),
            )
            shown += 1

        remaining = len(file.lines) - shown
        if remaining > 0:
            self._preview_tree.insert(
                "",
                "end",
                values=("", "...", f"(+{remaining} more lines)", ""),
            )

    def _update_preview_cross_file(
        self,
        search_text: str,
        tag_map: Dict[int, str],
        offsets: List[int],
    ) -> None:
        """Show search results across all loaded files.

        Args:
            search_text: Lowercased search string to match.
            tag_map: Mapping of global idx to tag string.
            offsets: List of global start offsets per file.
        """
        max_results = 1000
        shown = 0

        for file_idx, file in enumerate(self._loaded_files):
            global_offset = offsets[file_idx] if file_idx < len(offsets) else 0

            for i, line in enumerate(file.lines):
                if shown >= max_results:
                    break

                display_line = (
                    line.replace("\r\n", "↵").replace("\n", "↵").replace("\r", "↵")
                )

                if search_text not in display_line.lower():
                    continue

                global_idx = global_offset + i
                line_tag = tag_map.get(global_idx, "")
                self._preview_tree.insert(
                    "",
                    "end",
                    iid=str(global_idx),
                    values=(global_idx + 1, i + 1, display_line, line_tag),
                )
                shown += 1

            if shown >= max_results:
                break

    def _on_preview_select(self, event: tk.Event) -> None:
        """Handle selection in the preview tree.

        During cross-file search, selecting a result switches the file
        tree selection to the file that contains the selected line so
        that clearing the search shows the surrounding context.
        """
        selection = self._preview_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        if not item_id.isdigit():
            return

        global_idx = int(item_id)

        # Find which file this idx belongs to
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            filedir = mgr.get_filedir()
            for file_idx, entry in enumerate(filedir):
                if entry.first_idx <= global_idx <= entry.last_idx:
                    if file_idx != self._current_file_index:
                        self._current_file_index = file_idx
                        # Update file tree selection without triggering preview refresh
                        self._select_file_in_tree(file_idx)
                    break
        else:
            # Fallback: compute from loaded file line counts
            offset = 0
            for file_idx, file in enumerate(self._loaded_files):
                if offset <= global_idx < offset + file.line_count:
                    if file_idx != self._current_file_index:
                        self._current_file_index = file_idx
                        self._select_file_in_tree(file_idx)
                    break
                offset += file.line_count

    def _select_file_in_tree(self, file_index: int) -> None:
        """Select a file in the file tree by its loaded file index.

        Args:
            file_index: Index into ``_loaded_files``.
        """
        for item_id, idx in self._tree_item_to_index.items():
            if idx == file_index:
                self._file_tree.selection_set(item_id)
                self._file_tree.see(item_id)
                break

    def _on_preview_search_clear(self) -> None:
        """Clear the preview search box and show current file."""
        self._preview_search_var.set("")

    def _on_preview_right_click(self, event: tk.Event) -> None:
        """Handle right-click on preview tree for tag editing.

        Preserves multiselect when clicking on an already-selected row.
        """
        try:
            item = self._preview_tree.identify_row(event.y)
            if item and item not in self._preview_tree.selection():
                self._preview_tree.selection_set(item)
            self._preview_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._preview_context_menu.grab_release()

    def _set_selected_line_tag(self, tag: str) -> None:
        """Set the tag for all selected lines in the manifest.

        Args:
            tag: One of ``"dialogue"``, ``"menu"``, ``"choice"``, or ``""``
                 (clear).
        """
        selection = self._preview_tree.selection()
        if not selection:
            return

        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        all_lines = mgr.get_lines()
        idx_set = {int(iid) for iid in selection if iid.isdigit()}

        for line_data in all_lines:
            if line_data.get("idx") in idx_set:
                if tag:
                    line_data["tag"] = tag
                else:
                    line_data.pop("tag", None)

        mgr.set_lines(all_lines)
        self._update_preview()

    def _update_summary(self) -> None:
        """Update the summary bar."""
        file_count = len(self._loaded_files)
        total_lines = sum(f.line_count for f in self._loaded_files)

        self._file_count_label.configure(text=f"Files: {file_count}")
        self._total_lines_label.configure(text=f"Total Lines: {total_lines:,}")

        # Format breakdown
        format_counts: Dict[str, int] = {}
        for file in self._loaded_files:
            format_counts[file.format_id] = format_counts.get(file.format_id, 0) + 1

        if format_counts:
            breakdown = " | ".join(
                f"{fmt.upper()}: {count}" for fmt, count in sorted(format_counts.items())
            )
            self._format_breakdown_label.configure(text=breakdown)
        else:
            self._format_breakdown_label.configure(text="")

        # Ready indicator
        if file_count > 0:
            self._ready_label.configure(text="✓ Ready for Analysis")
        else:
            self._ready_label.configure(text="")

    def _update_step_data(self) -> None:
        """Update step data in session state.

        Lines are already stored in the manifest ``lines[].orig`` via
        filedir, so we no longer duplicate them as ``all_lines``.
        File metadata is stored in the manifest ``filedir`` array, so
        we no longer duplicate it as ``files``.
        """
        data = {
            "total_lines": sum(f.line_count for f in self._loaded_files),
            "encoding": self._encoding_var.get() if self._encoding_var else "utf-8",
            "format_override": self._format_var.get() if self._format_var else "auto",
        }
        self.set_step_data(data)

    # ----------------------------- BaseStep Methods ----------------------------- #

    def on_new_project(self) -> None:
        """Reset all cached state for a fresh project.

        Called by ``App._on_new_session()`` to flush stale data from a
        previous project so no files, lines, or tree items leak across.
        """
        super().on_new_project()
        self._loaded_files.clear()
        self._current_file_index = -1
        self._folder_root = None
        self._tree_item_to_index.clear()
        if hasattr(self, "_pending_project_name"):
            self._pending_project_name = ""
        # Reset sort and filter state
        self._sort_column = ""
        self._sort_ascending = True
        if hasattr(self, "_file_filter_var"):
            self._file_filter_var.set("")
        self._refresh_sort_headings()
        self._update_file_list()
        self._update_preview()
        self._update_summary()
        logger.debug("Input step reset for new project")

    def on_enter(self) -> None:
        """Called when entering this step tab."""
        step_data = self.get_step_data()

        # Restore LoadedFile objects from manifest filedir + lines
        # (falls back to legacy step_data keys if manifest not available)
        if not self._loaded_files:
            self._restore_files_from_session(step_data)

        # PHASE 58.11: If still no loaded files but manifest has filedir/lines,
        # populate from manifest (happens when loading manifest via App menu)
        if not self._loaded_files:
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                raw_data = mgr.get_raw_data()
                filedir = raw_data.get("filedir", [])
                lines = raw_data.get("lines", [])
                if filedir and lines:
                    logger.debug(
                        "Populating from manifest: %d files, %d lines",
                        len(filedir), len(lines),
                    )
                    self._populate_from_manifest(raw_data)

        if self._loaded_files:
            self._update_file_list()
            self._update_summary()
            if self._current_file_index < 0:
                self._select_first_file_in_tree()
        logger.debug("Entered Input step")

    def _restore_files_from_session(self, step_data: Dict[str, Any]) -> None:
        """Restore LoadedFile objects from manifest filedir + lines.

        Reads file metadata from ``filedir`` and line text from
        ``lines[].orig`` so that no duplicate ``files`` or ``all_lines``
        arrays are needed in step_data.

        Falls back to legacy ``files``/``all_lines`` keys for older
        session data that hasn't been migrated yet.

        Args:
            step_data: Step data dictionary from session.
        """
        mgr = self.manifest_manager

        # ------- Primary path: manifest filedir + lines -------
        if mgr is not None and mgr.is_loaded:
            filedir = mgr.get_filedir()
            manifest_lines = mgr.get_lines()
            if filedir and manifest_lines:
                original_dir = mgr.get_original_dir()
                relocated = getattr(self, "_relocated_files", {})

                for entry in filedir:
                    rel_path = entry.rel_path
                    if original_dir is not None:
                        file_path = original_dir / rel_path
                    else:
                        file_path = Path(rel_path)
                    actual_path = Path(relocated.get(rel_path, str(file_path)))

                    # Extract orig lines from the manifest line entries
                    file_lines: List[str] = []
                    for idx in range(entry.first_idx, entry.last_idx + 1):
                        if idx < len(manifest_lines):
                            ln = manifest_lines[idx]
                            file_lines.append(
                                ln.get("orig", "") if isinstance(ln, dict) else str(ln)
                            )

                    loaded = LoadedFile(
                        path=actual_path if actual_path.exists() else file_path,
                        format_id=entry.format,
                        lines=file_lines,
                        manifest_path=(
                            self.session.manifest_path if self.session else None
                        ),
                        encoding=entry.encoding,
                    )
                    self._loaded_files.append(loaded)

                logger.info(
                    "Restored %d files from manifest filedir", len(self._loaded_files)
                )
                return

        # ------- Legacy fallback: step_data files + all_lines -------
        files_data = step_data.get("files", [])
        all_lines = step_data.get("all_lines", [])

        line_offset = 0
        for file_info in files_data:
            path = Path(file_info["path"])
            format_id = file_info.get("format_id", "txt")
            line_count = file_info.get("line_count", 0)
            manifest_path_str = file_info.get("manifest_path")
            encoding = file_info.get("encoding", "utf-8")

            if manifest_path_str:
                manifest_path = Path(manifest_path_str)
                if not manifest_path.exists():
                    manifest_path = self._find_manifest(path)
            else:
                manifest_path = self._find_manifest(path)

            if all_lines:
                file_lines = all_lines[line_offset:line_offset + line_count]
                line_offset += line_count
            else:
                try:
                    file_lines = self._extract_lines(path, format_id, encoding)
                except Exception as e:
                    logger.warning("Could not reload file %s: %s", path, e)
                    file_lines = []

            loaded = LoadedFile(
                path=path,
                format_id=format_id,
                lines=file_lines,
                manifest_path=manifest_path,
                encoding=encoding,
            )
            self._loaded_files.append(loaded)

            if manifest_path and self.session is not None and not self.session.manifest_path:
                self.session.manifest_path = manifest_path

        logger.info("Restored %d files from session (legacy)", len(self._loaded_files))

    def on_leave(self) -> None:
        """Called when leaving this step tab."""
        # Ensure state is saved
        self._update_step_data()
        logger.debug("Left Input step")

    def get_loaded_files(self) -> List[LoadedFile]:
        """Get the list of loaded files.

        Returns:
            List of LoadedFile objects.
        """
        return self._loaded_files

    def get_all_lines(self) -> List[Tuple[Path, int, str]]:
        """Get all lines from all loaded files.

        Returns:
            List of (file_path, line_index, line_content) tuples.
        """
        all_lines = []
        for file in self._loaded_files:
            for i, line in enumerate(file.lines):
                all_lines.append((file.path, i, line))
        return all_lines
    def _trigger_auto_analysis(self) -> None:
        """Trigger automatic analysis after file load.
        
        Checks if auto-analysis is enabled in global options and triggers
        the Analysis step to run without switching tabs.
        """
        # Check if auto-analysis is enabled (default: True)
        auto_analyze = True
        if self.session is not None and hasattr(self.session, "global_options"):
            global_opts = getattr(self.session, "global_options", None)
            if global_opts is not None and hasattr(global_opts, "session"):
                auto_analyze = getattr(global_opts.session, "auto_analyze_on_load", True)
        
        if not auto_analyze:
            return
            
        # Access the analysis step through the app
        try:
            app = self.winfo_toplevel()
            step_tabs = getattr(app, "_step_tabs", None)
            if step_tabs is not None and len(step_tabs) > 1:
                analysis_step = step_tabs[1]  # Step 1 is Analysis
                if hasattr(analysis_step, "_run_analysis"):
                    # Run analysis in background
                    logger.info("Auto-triggering analysis after file load")
                    analysis_step._run_analysis()
        except Exception as e:
            logger.debug("Could not trigger auto-analysis: %s", e)

    def _trigger_auto_preprocessing(self) -> None:
        """Trigger automatic preprocessing after file load.
        
        Checks if auto-preprocessing is enabled in global options and triggers
        the Preprocessing step to run without switching tabs.
        """
        # Check if auto-preprocessing is enabled (default: True)
        auto_preprocess = True
        if self.session is not None and hasattr(self.session, "global_options"):
            global_opts = getattr(self.session, "global_options", None)
            if global_opts is not None and hasattr(global_opts, "session"):
                auto_preprocess = getattr(global_opts.session, "auto_preprocess_on_load", True)
        
        if not auto_preprocess:
            return
            
        # Access the preprocessing step through the app
        try:
            app = self.winfo_toplevel()
            step_tabs = getattr(app, "_step_tabs", None)
            if step_tabs is not None and len(step_tabs) > 4:
                preprocess_step = step_tabs[4]  # Step 4 is Preprocessing
                if hasattr(preprocess_step, "_apply_rules"):
                    # Run preprocessing in background
                    logger.info("Auto-triggering preprocessing after file load")
                    # Small delay to let analysis complete first
                    self.after(500, preprocess_step._apply_rules)
        except Exception as e:
            logger.debug("Could not trigger auto-preprocessing: %s", e)

    def _populate_project_info_from_files(self) -> None:
        """Populate project name/title from loaded file path.
        
        Uses the file name or parent folder to suggest a project name
        if none is set in the Information step.
        """
        if not self._loaded_files:
            return
            
        # Get the first file's path
        first_path = self._loaded_files[0].path
        
        # Use parent folder name or file stem as suggestion
        if first_path.parent.name and first_path.parent.name not in (".", ""):
            project_name = first_path.parent.name
        else:
            project_name = first_path.stem
        
        # Clean up the name (remove common suffixes)
        for suffix in ["_translated", "_tl", "_en", "_jp", ".translated"]:
            if project_name.lower().endswith(suffix):
                project_name = project_name[:-len(suffix)]
        
        # Store suggestion in step data for Information step to pick up
        step_data = self.get_step_data()
        step_data["suggested_project_name"] = project_name
        self.set_step_data(step_data)
