"""CherryAI GUI v2 Input Step.

First workflow tab for loading files, previewing content, and detecting manifests.

TASK 39: Modernized Input step with unified selector, Treeview file tree,
auto-encoding, format filtering, multi-line preview, and progress dialog.
"""

from __future__ import annotations

from contextlib import nullcontext
import codecs
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import TYPE_CHECKING, Any, Callable, ContextManager, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk

from CherryAI.gui.dialogs.loading_progress import LoadingProgressDialog
from CherryAI.gui.dialogs.input_dialog import UnifiedInputDialog

from CherryAI.functions.analysis import classify_file_type
from CherryAI.functions.ini_manager import get_default
from CherryAI.functions.manifest_manager import (
    capture_source_line_mappings,
    get_primary_line_tag,
    merge_line_tags,
    set_primary_line_tag,
)
from CherryAI.functions.postprocess import capture_dialogue_edge_whitespace
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState

logger = logging.getLogger(__name__)


PROGRESS_RENDER_INTERVAL_FILES = 8
PROGRESS_RENDER_INTERVAL_SECONDS = 2.0


SAME_AS_SOURCE_DESTINATION = "Same as Source"
SAME_AS_INPUT_ENCODING = "Same as Input"
DEFAULT_OUTPUT_PAIR_MODE = "custom"
DEFAULT_OUTPUT_NAMING = "subfolder"
DEFAULT_OUTPUT_TEXT_OPTION = "translated"
DEFAULT_OUTPUT_BACKUP = "timestamp"
DEFAULT_OUTPUT_BACKUP_EXTENSION = ".bk"

# Supported file extensions for loading (TASK 39.3: rpgmaker and image added)
SUPPORTED_EXTENSIONS = [
    ("All Supported", "*.txt *.csv *.tsv *.json *.xlsx *.xp3 *.png *.jpg *.jpeg *.bmp"),
    ("Text Files", "*.txt"),
    ("CSV Files", "*.csv"),
    ("TSV Files", "*.tsv"),
    ("JSON Files", "*.json"),
    ("Excel Files", "*.xlsx"),
    ("XP3 Archives", "*.xp3"),
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
    ".xp3": "KiriKiri2",
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
    "KiriKiri2": {".ks", ".tjs", ".xp3"},
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
        tags: Per-line parser tags (dialogue, menu, variable, etc.).
        source_mappings: Optional precomputed ``ln``/``f`` locator data.
    """

    def __init__(
        self,
        path: Path,
        format_id: str,
        lines: Optional[List[str]] = None,
        manifest_path: Optional[Path] = None,
        encoding: str = "utf-8",
        tags: Optional[List[str]] = None,
        source_mappings: Optional[List[Dict[str, int]]] = None,
        line_count: Optional[int] = None,
        content_loader: Optional[
            Callable[[], Tuple[List[str], Optional[List[str]]]]
        ] = None,
        detection_source: str = "",
    ) -> None:
        """Initialize LoadedFile.

        Args:
            path: File path.
            format_id: Format identifier.
            lines: Extracted lines.
            manifest_path: Associated manifest path.
            encoding: File encoding.
            tags: Per-line parser tags from extract_tagged.
            line_count: Preserved line count when content is loaded lazily.
            content_loader: Optional lazy loader for lines and tags.
            detection_source: Encoding detection source metadata.
        """
        self.path = path
        self.format_id = format_id
        self._lines = list(lines) if lines is not None else None
        self._line_count = len(lines) if lines is not None else max(int(line_count or 0), 0)
        self.manifest_path = manifest_path
        self.encoding = encoding
        self._tags = list(tags) if tags is not None else None
        self.source_mappings = [dict(item) for item in source_mappings] if source_mappings else None
        self._content_loader = content_loader
        self.detection_source = detection_source

    def _ensure_content_loaded(self) -> None:
        """Load lines and tags on first access when backed by a manifest slice."""
        if self._lines is not None:
            return
        if self._content_loader is None:
            self._lines = []
            return
        lines, tags = self._content_loader()
        self._lines = list(lines)
        self._line_count = len(self._lines)
        self._tags = list(tags) if tags is not None else None
        self._content_loader = None

    @property
    def lines(self) -> List[str]:
        """Get extracted lines, loading them lazily when possible."""
        self._ensure_content_loaded()
        assert self._lines is not None
        return self._lines

    @lines.setter
    def lines(self, value: List[str]) -> None:
        """Replace extracted lines and discard any lazy loader."""
        self._lines = list(value)
        self._line_count = len(self._lines)
        self._content_loader = None

    @property
    def tags(self) -> Optional[List[str]]:
        """Get parser tags, loading them with the lines when needed."""
        if self._tags is None and self._content_loader is not None and self._lines is None:
            self._ensure_content_loaded()
        return self._tags

    @tags.setter
    def tags(self, value: Optional[List[str]]) -> None:
        """Replace parser tags explicitly."""
        self._tags = list(value) if value is not None else None

    @property
    def line_count(self) -> int:
        """Get line count."""
        if self._lines is not None:
            return len(self._lines)
        return self._line_count

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


def _make_manifest_content_loader(
    lines_data: List[Any],
    first_idx: int,
    last_idx: int,
) -> Callable[[], Tuple[List[str], Optional[List[str]]]]:
    """Create a lazy loader for a contiguous manifest line slice."""

    def _load() -> Tuple[List[str], Optional[List[str]]]:
        file_lines: List[str] = []
        file_tags: List[str] = []
        has_tags = False
        upper_bound = min(last_idx, len(lines_data) - 1)
        for idx in range(first_idx, upper_bound + 1):
            line_entry = lines_data[idx]
            if isinstance(line_entry, dict):
                file_lines.append(line_entry.get("orig", ""))
                tag_value = str(line_entry.get("tags", ""))
                file_tags.append(tag_value)
                has_tags = has_tags or bool(tag_value)
            else:
                file_lines.append(str(line_entry))
                file_tags.append("")
        return file_lines, file_tags if has_tags else None

    return _load

# ======================================================================
# Import Translation Dialog
# ======================================================================

class _ImportTranslationDialog(tk.Toplevel):
    """Selection dialog for Import Translation.

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
        self._add_check(lf, "import_final", "Final", True, **pad)
        self._add_check(lf, "import_qa", "QA (reviewed text, overwrite, TLC, edits)", True, **pad)
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
        self._add_check(
            sf,
            "import_information",
            "Information (metadata, glossary, code DB)",
            True,
            **pad,
        )
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
        self._pending_source_base: Optional[Path] = None
        self._pending_source_handling: str = "copy"
        self._pending_stage_source_paths: Dict[str, Path] = {}
        self._extraction_validation_batch_depth: int = 0
        self._pending_extraction_validation_issues: List[Dict[str, Any]] = []
        self._last_extraction_validation_log: Optional[Path] = None
        self._bulk_load_depth: int = 0
        self._pending_bulk_step_data_sync: bool = False
        self._bulk_load_state_context: Optional[ContextManager[None]] = None
        self._manifest_source_text_cache: Optional[Dict[str, str]] = None

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

        self._create_patch_btn = ttk.Button(
            toolbar,
            text="Create Patch",
            command=self._on_create_patch,
        )
        self._create_patch_btn.pack(side="left", padx=2)

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

        # Unpack dialog result.
        selected_paths, format_filter, enc, project_name, pipeline, source_handling = result
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
        self._load_selected_paths(
            selected_paths,
            enc,
            format_filter,
            project_name,
            source_handling,
        )

    def _load_selected_paths(
        self,
        paths: List[Path],
        encoding: str,
        format_override: str,
        project_name: str = "",
        source_handling: str = "copy",
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
        self._begin_extraction_validation_batch()
        self._begin_bulk_load_state_updates()

        # PHASE 58.12: Store project name for later use
        self._pending_project_name = project_name
        self._pending_source_handling = source_handling
        self._pending_stage_source_paths = {}
        self._pending_source_base = None
        
        files_to_load: List[Path] = []
        first_folder: Optional[Path] = None

        stage_source_paths, source_base = self._build_stage_source_paths(paths)
        self._pending_stage_source_paths = stage_source_paths
        self._pending_source_base = source_base

        # Collect all parseable files from paths
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

        if stage_source_paths and files_to_load:
            filtered_stage_source_paths: Dict[str, Path] = {}
            for file_path in files_to_load:
                if source_base is not None:
                    try:
                        rel_path = str(file_path.relative_to(source_base))
                    except ValueError:
                        rel_path = file_path.name
                else:
                    rel_path = file_path.name
                filtered_stage_source_paths[rel_path] = file_path
            stage_source_paths = filtered_stage_source_paths
            self._pending_stage_source_paths = dict(filtered_stage_source_paths)

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

        # Show one progress dialog for the entire input flow.
        progress: Optional[LoadingProgressDialog] = None
        if len(files_to_load) > 3 or len(stage_source_paths) > 3:
            progress = LoadingProgressDialog(self, len(files_to_load))
            progress.set_phase("Loading selected files")

        last_progress_refresh = 0.0

        # Handshake: validate parser once before iterating files
        if format_override != "auto":
            if not self._validate_parser_selection(format_override):
                if progress is not None:
                    progress.close()
                return

        for path in files_to_load:
            if progress is not None and progress.cancelled:
                break
            processed_count = loaded_count + len(skipped_files)
            # Format filtering
            if format_override != "auto" and not self._file_matches_format(path, format_override):
                skipped_files.append(path.name)
                if progress is not None:
                    last_progress_refresh = self._maybe_update_load_progress(
                        progress=progress,
                        processed_count=processed_count + 1,
                        total_files=len(files_to_load),
                        current_file=path.name,
                        last_refresh=last_progress_refresh,
                    )
                continue

            # Skip files already in the manifest when adding
            if is_add_to_existing:
                if path.name in already_loaded_names:
                    if progress is not None:
                        last_progress_refresh = self._maybe_update_load_progress(
                            progress=progress,
                            processed_count=processed_count + 1,
                            total_files=len(files_to_load),
                            current_file=path.name,
                            last_refresh=last_progress_refresh,
                        )
                    continue

            if self._load_file(path, encoding, format_override):
                loaded_count += 1
            if progress is not None:
                last_progress_refresh = self._maybe_update_load_progress(
                    progress=progress,
                    processed_count=loaded_count + len(skipped_files),
                    total_files=len(files_to_load),
                    current_file=path.name,
                    last_refresh=last_progress_refresh,
                )

        # Warn about skipped files
        if skipped_files:
            names = "\n".join(skipped_files[:10])
            if len(skipped_files) > 10:
                names += f"\n...and {len(skipped_files) - 10} more"
            messagebox.showwarning(
                "Files Skipped",
                f"The following files were skipped because they don't match "
                f"the '{format_override}' format filter:\n\n{names}",
            )

        try:
            if loaded_count > 0:
                self._update_summary()
                self._update_file_list()
                if self._current_file_index < 0 and self._loaded_files:
                    self._select_first_file_in_tree()
                self.set_status("in-progress")
                logger.info("Loaded %d file(s)", loaded_count)

                if progress is not None and progress.cancelled:
                    logger.info("Input load cancelled before manifest sync")
                    return

                if is_add_to_existing:
                    # Non-destructive addition to existing manifest
                    new_loaded = self._loaded_files[new_files_start:]
                    self._add_files_to_existing_manifest(new_loaded, format_override)
                else:
                    self._populate_project_info_from_files()
                    mgr = self.manifest_manager
                    if mgr is not None and mgr.is_loaded:
                        self._sync_lines_to_manifest(progress=progress)
                    else:
                        self._ensure_project_created(progress=progress)

                if progress is not None and progress.cancelled:
                    logger.info("Input load cancelled after manifest sync")
                    return

                # Parser Handshake P3: Wire optional components to manifest
                self._wire_parser_optionals(format_override)

                self._save_manifest_after_file_load(progress=progress)

                # Refresh file list after manifest sync to show Type column
                self._update_file_list()

                # PHASE 58.4: Execute automatic pipeline
                if not is_add_to_existing:
                    self._execute_auto_pipeline()
        finally:
            if progress is not None:
                progress.close()
            self._end_bulk_load_state_updates()
            self._end_extraction_validation_batch()

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
                # Collect all files so parser-owned package targets such as
                # `.xp3` are not filtered out before `can_handle()` runs.
                all_files = self._collect_all_files_from_folder(folder)
                matched = [f for f in all_files if parser.can_handle(f)]
                dedup_fn = getattr(parser, "deduplicate_input_paths", None)
                if callable(dedup_fn):
                    return dedup_fn(matched, root=folder)
                return matched
        except Exception:
            pass

        if format_filter != "auto" and format_filter in FORMAT_EXTENSIONS:
            suffixes = FORMAT_EXTENSIONS[format_filter]
        else:
            suffixes = {".txt", ".csv", ".tsv", ".json", ".xlsx", ".xp3",
                        ".png", ".jpg", ".jpeg", ".bmp"}
        return self._collect_files_from_folder(folder, suffixes)

    def _maybe_update_load_progress(
        self,
        *,
        progress: LoadingProgressDialog,
        processed_count: int,
        total_files: int,
        current_file: str,
        last_refresh: float,
    ) -> float:
        """Refresh the load dialog at coarse checkpoints during Step 0."""
        now = time.perf_counter()
        should_refresh = (
            processed_count >= total_files
            or processed_count == 1
            or processed_count % PROGRESS_RENDER_INTERVAL_FILES == 0
            or now - last_refresh >= PROGRESS_RENDER_INTERVAL_SECONDS
        )
        if not should_refresh:
            return last_refresh

        progress.set_progress(
            current=processed_count,
            current_file=current_file,
            force=processed_count >= total_files,
        )
        return now

    def _begin_bulk_load_state_updates(self) -> None:
        """Defer session-driven UI refreshes while Step 0 is bulk-loading."""
        if self._bulk_load_depth == 0:
            if self.session is not None:
                context: ContextManager[None] = self.session.defer_notifications()
            else:
                context = nullcontext()
            context.__enter__()
            self._bulk_load_state_context = context
        self._bulk_load_depth += 1

    def _end_bulk_load_state_updates(self) -> None:
        """Flush one final Step 0 state update after bulk loading ends."""
        if self._bulk_load_depth <= 0:
            return

        self._bulk_load_depth -= 1
        if self._bulk_load_depth != 0:
            return

        try:
            if self._pending_bulk_step_data_sync:
                self._pending_bulk_step_data_sync = False
                self._update_step_data(force=True)
        finally:
            context = self._bulk_load_state_context
            self._bulk_load_state_context = None
            if context is not None:
                context.__exit__(None, None, None)

    def _begin_manifest_source_text_cache(self) -> None:
        """Enable a temporary staged-source cache for manifest line building."""
        if self._manifest_source_text_cache is None:
            self._manifest_source_text_cache = {}

    def _end_manifest_source_text_cache(self) -> None:
        """Release the temporary staged-source cache after manifest sync."""
        self._manifest_source_text_cache = None

    def _prime_manifest_source_text_cache(
        self,
        source_paths: Dict[str, Path],
    ) -> None:
        """Populate the temporary source-text cache from known rel-path inputs."""
        cache = self._manifest_source_text_cache
        if cache is None:
            return

        loaded_by_path = {
            str(loaded_file.path): loaded_file
            for loaded_file in self._loaded_files
        }

        for rel_path, source_path in source_paths.items():
            if rel_path in cache:
                continue
            try:
                loaded_file = loaded_by_path.get(str(source_path))
                encoding = loaded_file.encoding if loaded_file is not None else "utf-8"
                cache[rel_path] = source_path.read_text(
                    encoding=encoding,
                    errors="ignore",
                )
            except Exception:
                continue

    def _get_manifest_source_text_encodings(
        self,
        source_paths: Dict[str, Path],
    ) -> Dict[str, str]:
        """Return rel-path encodings for staged-source cache population."""
        loaded_by_path = {
            str(loaded_file.path): loaded_file.encoding
            for loaded_file in self._loaded_files
        }
        return {
            rel_path: loaded_by_path.get(str(source_path), "utf-8")
            for rel_path, source_path in source_paths.items()
        }

    def _read_manifest_source_text(
        self,
        loaded_file: LoadedFile,
        rel_path: str,
    ) -> Optional[str]:
        """Read staged source text once per file during manifest entry construction."""
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded or not loaded_file.lines:
            return None

        cache = self._manifest_source_text_cache
        if cache is not None and rel_path in cache:
            return cache[rel_path]

        staged_path = mgr.resolve_file_path(rel_path)
        source_path = staged_path if staged_path.exists() else loaded_file.path

        with open(source_path, "r", encoding=loaded_file.encoding, errors="ignore") as fh:
            source_text = fh.read()

        if cache is not None:
            cache[rel_path] = source_text
        return source_text

    def _prepare_folder_tree_staging(self, root_folder: Path) -> None:
        """Prepare full-tree staging data for a selected folder."""
        stage_source_paths, source_base = self._build_stage_source_paths([root_folder])
        self._pending_stage_source_paths = stage_source_paths
        self._pending_source_base = source_base

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

        self._begin_extraction_validation_batch()

        encoding = self._encoding_var.get() if self._encoding_var else "auto"
        format_override = self._format_var.get() if self._format_var else "auto"

        loaded_count = 0
        skipped_files: List[str] = []

        # TASK 39.7: Show progress dialog for multi-file loading
        paths_to_load = [Path(fp) for fp in filepaths]
        progress: Optional[LoadingProgressDialog] = None
        if len(paths_to_load) > 3:
            progress = LoadingProgressDialog(self, len(paths_to_load))

        try:
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
                mgr = self.manifest_manager
                if mgr is not None and mgr.is_loaded:
                    self._sync_lines_to_manifest()
                else:
                    self._ensure_project_created()
                
                # TASK 29.2: Save manifest after file load
                self._save_manifest_after_file_load()

                # Refresh file list after manifest sync to show Type column
                self._update_file_list()
                
                # Trigger auto-analysis if enabled
                self._trigger_auto_analysis()
                
                # Trigger auto-preprocessing if enabled (runs after analysis)
                self._trigger_auto_preprocessing()
        finally:
            self._end_extraction_validation_batch()

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

        self._begin_extraction_validation_batch()

        # Store the root folder for relative path display
        self._folder_root = root_folder
        self._prepare_folder_tree_staging(root_folder)

        encoding = self._encoding_var.get() if self._encoding_var else "auto"
        format_override = self._format_var.get() if self._format_var else "auto"

        file_paths = self._collect_files_for_format(root_folder, format_override)

        if not file_paths:
            supported_desc = format_override if format_override != "auto" else "default supported formats"
            messagebox.showinfo(
                "No Files Found",
                f"No supported files found in folder:\n{root_folder}\n\n"
                f"Selected filter: {supported_desc}",
            )
            return

        # Sort files by path for consistent ordering
        file_paths.sort()

        loaded_count = 0

        # TASK 39.7: Show progress dialog for folder loading
        progress: Optional[LoadingProgressDialog] = None
        if len(file_paths) > 3:
            progress = LoadingProgressDialog(self, len(file_paths))

        try:
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
                mgr = self.manifest_manager
                if mgr is not None and mgr.is_loaded:
                    self._sync_lines_to_manifest()
                else:
                    self._ensure_project_created()
                
                # TASK 29.2: Save manifest after file load
                self._save_manifest_after_file_load()

                # Refresh file list after manifest sync to show Type column
                self._update_file_list()
                
                # Trigger auto-analysis if enabled
                self._trigger_auto_analysis()
                
                # Trigger auto-preprocessing if enabled (runs after analysis)
                self._trigger_auto_preprocessing()
        finally:
            self._end_extraction_validation_batch()

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

    def _collect_all_files_from_folder(self, folder: Path) -> List[Path]:
        """Recursively collect every file from *folder*."""
        files: List[Path] = []
        try:
            for item in folder.rglob("*"):
                if item.is_file():
                    files.append(item)
        except PermissionError as e:
            logger.warning("Permission denied accessing folder: %s", e)
        except Exception as e:
            logger.error("Error scanning folder %s: %s", folder, e)
        return files

    def _resolve_selection_anchor(self, path: Path, source_root_hint: str = "") -> Path:
        """Resolve the folder anchor used to build relative staging paths."""
        anchor = path if path.is_dir() else path.parent
        if not source_root_hint:
            return anchor

        for candidate in (anchor, *anchor.parents):
            if candidate.name == source_root_hint:
                return candidate
        return anchor

    def _build_stage_source_paths(
        self,
        paths: List[Path],
    ) -> Tuple[Dict[str, Path], Optional[Path]]:
        """Build the full source-tree staging map for the selected input paths."""
        mgr = self.manifest_manager
        source_root_hint = ""
        if mgr is not None and mgr.is_loaded and mgr.source_mode != "external":
            source_root_hint = mgr.source_root

        anchors: List[Path] = []
        for path in paths:
            anchors.append(self._resolve_selection_anchor(path, source_root_hint))

        if not anchors:
            return {}, None

        if mgr is not None:
            if len(anchors) > 1:
                base_path = mgr._find_common_base(anchors)
            else:
                base_path = anchors[0]
        else:
            base_path = anchors[0]

        staged: Dict[str, Path] = {}
        for path in paths:
            if path.is_file():
                try:
                    rel_path = str(path.relative_to(base_path))
                except ValueError:
                    rel_path = path.name
                staged[rel_path] = path
                continue

            try:
                for item in path.rglob("*"):
                    if not item.is_file():
                        continue
                    try:
                        rel_path = str(item.relative_to(base_path))
                    except ValueError:
                        rel_path = item.name
                    staged[rel_path] = item
            except PermissionError as exc:
                logger.warning("Permission denied accessing folder: %s", exc)
            except Exception as exc:
                logger.error("Error scanning folder %s: %s", path, exc)

        return staged, base_path

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

    @staticmethod
    def _build_extraction_issue_preview(text: str, *, limit: int = 160) -> str:
        """Return a single-line preview for extraction validation logs."""
        cleaned = text.replace("\r", " ").replace("\n", " | ").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3] + "..."

    def _begin_extraction_validation_batch(self) -> None:
        """Start buffering extraction validation issues for one load batch."""
        if self._extraction_validation_batch_depth == 0:
            self._pending_extraction_validation_issues = []
            self._last_extraction_validation_log = None
        self._extraction_validation_batch_depth += 1

    def _record_extraction_validation_issue(
        self,
        *,
        severity: str,
        filename: str,
        line_number: int,
        tokens: int,
        limit: int,
        text: str,
    ) -> None:
        """Buffer one extraction validation issue for later summary/logging."""
        self._pending_extraction_validation_issues.append({
            "severity": severity,
            "filename": filename,
            "line_number": line_number,
            "tokens": tokens,
            "limit": limit,
            "chars": len(text),
            "preview": self._build_extraction_issue_preview(text),
        })

    def _write_extraction_validation_log(self) -> Optional[Path]:
        """Persist buffered extraction validation issues to one log file."""
        if not self._pending_extraction_validation_issues:
            return None

        mgr = self.manifest_manager
        manifest_path = mgr.manifest_path if mgr is not None and mgr.is_loaded else None
        if manifest_path is not None:
            log_path = manifest_path.parent / (
                f"{manifest_path.stem}.input_extract_validation.log"
            )
        else:
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = log_dir / f"input_extract_validation_{timestamp}.log"

        lines = [
            "CherryAI Step 0 Extraction Validation Log",
            f"Generated: {datetime.now().isoformat()}",
            f"Issues: {len(self._pending_extraction_validation_issues)}",
            "",
        ]
        for issue in self._pending_extraction_validation_issues:
            lines.extend([
                (
                    f"[{issue['severity'].upper()}] {issue['filename']} "
                    f"line {issue['line_number']}"
                ),
                (
                    f"tokens={issue['tokens']} limit={issue['limit']} "
                    f"chars={issue['chars']}"
                ),
                f"preview={issue['preview']}",
                "",
            ])

        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(lines), encoding="utf-8")

        step_data = self.get_step_data()
        step_data["last_extraction_validation_log"] = str(log_path)
        self.set_step_data(step_data)
        self._last_extraction_validation_log = log_path
        return log_path

    def _end_extraction_validation_batch(self) -> None:
        """Flush a buffered extraction validation batch to one dialog/log."""
        if self._extraction_validation_batch_depth <= 0:
            return

        self._extraction_validation_batch_depth -= 1
        if self._extraction_validation_batch_depth != 0:
            return

        issues = list(self._pending_extraction_validation_issues)
        self._pending_extraction_validation_issues = []
        if not issues:
            return

        self._pending_extraction_validation_issues = issues
        log_path = self._write_extraction_validation_log()
        self._pending_extraction_validation_issues = []

        error_count = sum(1 for issue in issues if issue["severity"] == "error")
        warning_count = len(issues) - error_count
        summary_lines = [
            f"{issue['filename']} line {issue['line_number']}: {issue['tokens']} tokens"
            for issue in issues[:8]
        ]
        if len(issues) > 8:
            summary_lines.append(f"...and {len(issues) - 8} more")

        message = (
            f"Step 0 found {error_count} fatal and {warning_count} warning "
            f"extraction issue(s)."
        )
        if summary_lines:
            message += "\n\n" + "\n".join(summary_lines)
        if log_path is not None:
            message += f"\n\nLog written to:\n{log_path}"

        messagebox.showwarning("Extraction Validation Log", message)

    def _validate_extracted_lines(
        self, lines: List[str], filename: str,
    ) -> bool:
        """Run per-line token validation after extraction.

        - Lines >2048 tokens raise an error popup and abort.
        - Lines >1024 tokens emit a warning (non-blocking).

        Returns:
            True if no fatal errors, False if load should be aborted.
        """
        for idx, line in enumerate(lines):
            tok = self._estimate_tokens(line)
            if tok > 2048:
                self._record_extraction_validation_issue(
                    severity="error",
                    filename=filename,
                    line_number=idx + 1,
                    tokens=tok,
                    limit=2048,
                    text=line,
                )
                return False
            if tok > 1024:
                self._record_extraction_validation_issue(
                    severity="warning",
                    filename=filename,
                    line_number=idx + 1,
                    tokens=tok,
                    limit=1024,
                    text=line,
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
    def _decode_roundtrip_matches(
        raw: bytes,
        encoding: str,
        bom: bytes = b"",
    ) -> bool:
        """Return True when strict decode/encode reproduces the original bytes."""
        try:
            if bom:
                payload = raw[len(bom):]
                text = payload.decode(encoding)
                return text.encode(encoding) == payload
            text = raw.decode(encoding)
            return text.encode(encoding) == raw
        except (UnicodeDecodeError, LookupError):
            return False

    @staticmethod
    def _detect_encoding_info(
        path: Path,
        *,
        parser_encoding: Optional[str] = None,
        manual_encoding: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Detect encoding and source metadata for a file.

        Priority: BOM (authoritative) → parser/manual hints → heuristic.
        UTF-16 LE BOM is treated as authoritative when present.
        """
        raw = path.read_bytes()

        if raw.startswith(codecs.BOM_UTF16_LE):
            if InputExtractionStep._decode_roundtrip_matches(
                raw,
                "utf-16-le",
                bom=codecs.BOM_UTF16_LE,
            ):
                return "utf-16", "bom:utf-16-le"
            logger.warning(
                "Encoding detection failed strict roundtrip for UTF-16 LE BOM: %s",
                path,
            )
            raise UnicodeDecodeError("utf-16-le", raw, 0, 1, "BOM-decode roundtrip failed")

        if raw.startswith(codecs.BOM_UTF16_BE):
            if InputExtractionStep._decode_roundtrip_matches(
                raw,
                "utf-16-be",
                bom=codecs.BOM_UTF16_BE,
            ):
                return "utf-16", "bom:utf-16-be"
            logger.warning(
                "Encoding detection failed strict roundtrip for UTF-16 BE BOM: %s",
                path,
            )
            raise UnicodeDecodeError("utf-16-be", raw, 0, 1, "BOM-decode roundtrip failed")

        if raw.startswith(codecs.BOM_UTF8):
            if InputExtractionStep._decode_roundtrip_matches(raw, "utf-8", bom=codecs.BOM_UTF8):
                return "utf-8-sig", "bom:utf-8"
            logger.warning(
                "Encoding detection failed strict roundtrip for UTF-8 BOM: %s",
                path,
            )
            raise UnicodeDecodeError("utf-8", raw, 0, 1, "BOM-decode roundtrip failed")

        candidate_chain: List[Tuple[str, str]] = []
        if parser_encoding:
            candidate_chain.append((parser_encoding, "parser"))
        if manual_encoding:
            candidate_chain.append((manual_encoding, "manual"))

        # CP932 must win over Shift-JIS when both decode successfully.
        candidate_chain.extend(
            [
                ("utf-8", "heuristic"),
                ("cp932", "heuristic"),
                ("shift_jis", "heuristic"),
                ("utf-16-le", "heuristic"),
                ("utf-16-be", "heuristic"),
            ]
        )

        attempted: Set[Tuple[str, str]] = set()
        failed_attempts: List[str] = []
        for candidate, source in candidate_chain:
            key = (candidate.lower(), source)
            if key in attempted:
                continue
            attempted.add(key)
            if InputExtractionStep._decode_roundtrip_matches(raw, candidate):
                return candidate, source
            failed_attempts.append(f"{candidate} ({source})")
            logger.warning(
                "Encoding failed decode roundtrip for %s using %s from %s",
                path,
                candidate,
                source,
            )

        detail = ", ".join(failed_attempts) if failed_attempts else "no candidates"
        raise UnicodeDecodeError("unknown", raw, 0, 1, f"no strict encoding match: {detail}")

    @staticmethod
    def _detect_encoding(path: Path) -> str:
        """Backward-compatible wrapper returning only the detected encoding string."""
        detected, _source = InputExtractionStep._detect_encoding_info(path)
        return detected

    def _suggest_project_name_for_path(self, path: Path) -> str:
        """Return a stable fallback project name for a selected input path."""
        pending_name = getattr(self, "_pending_project_name", "")
        if pending_name:
            return pending_name
        if path.stem:
            return path.stem
        if path.parent.name:
            return path.parent.name
        return "Untitled"

    def _ensure_archive_project_loaded(self, archive_path: Path) -> bool:
        """Create a manifest early when archive extraction needs project staging."""
        mgr = self.manifest_manager
        if mgr is None:
            return False
        if mgr.is_loaded:
            return True

        project_name = self._suggest_project_name_for_path(archive_path)
        try:
            manifest_path = mgr.create_new(project_name, [])
        except Exception as exc:
            logger.error("Failed to create archive project for %s: %s", archive_path, exc)
            messagebox.showerror(
                "Archive Load Error",
                f"Failed to create a project for archive input:\n{archive_path.name}\n\nError: {exc}",
            )
            return False

        app = self.winfo_toplevel()
        if hasattr(app, "session"):
            app.session.manifest_path = manifest_path
        if hasattr(app, "_step_tabs"):
            for tab in app._step_tabs:
                tab._manifest_manager = mgr
        return True

    def _prompt_xp3_archive_settings(self, archive_path: Path) -> Optional[Dict[str, Any]]:
        """Prompt for manual XP3 archive settings when auto-detection fails."""
        custom_magic = simpledialog.askstring(
            "XP3 Custom Magic",
            (
                f"CherryAI could not find standard XP3 magic in {archive_path.name}.\n\n"
                "Enter custom magic as plain text or as hex:..."
            ),
            parent=self,
        )
        if custom_magic is None:
            return None

        header_offset_raw = simpledialog.askstring(
            "XP3 Header Offset",
            "Enter the archive header offset as a non-negative integer.",
            initialvalue="0",
            parent=self,
        )
        if header_offset_raw is None:
            return None
        try:
            header_offset = max(0, int(header_offset_raw))
        except ValueError:
            messagebox.showerror(
                "XP3 Header Offset",
                f"Invalid header offset: {header_offset_raw}",
            )
            return None

        key = simpledialog.askstring(
            "XP3 Key",
            "Enter the archive key if one is required. Leave blank if unused.",
            initialvalue="",
            parent=self,
        )
        if key is None:
            return None

        return {
            "custom_magic": custom_magic,
            "header_offset": header_offset,
            "key": key,
        }

    def _can_load_archive_member(self, path: Path) -> bool:
        """Return whether an extracted archive member should be loaded into Step 0."""
        try:
            from CherryAI.formats import detect_parser

            return detect_parser(path) is not None
        except Exception:
            return False

    def _load_archive_file(self, path: Path) -> bool:
        """Load an XP3 archive by unpacking it into Package/Original first."""
        mgr = self.manifest_manager
        if mgr is None:
            raise ValueError("Manifest manager unavailable for archive input")
        if not self._ensure_archive_project_loaded(path):
            return False

        from CherryAI.formats.KiriKiri2 import detect_xp3_archive_settings
        from CherryAI.formats.KiriKiri2 import infer_xp3_archive_key
        from CherryAI.formats.KiriKiri2 import list_xp3_entries

        detected = detect_xp3_archive_settings(path)
        settings = detected.to_dict() if detected is not None else self._prompt_xp3_archive_settings(path)
        if settings is None:
            return False

        if not settings.get("key"):
            inferred_key = infer_xp3_archive_key(path, settings=settings)
            if inferred_key:
                settings["key"] = inferred_key

        entries = list_xp3_entries(path, settings=settings)
        if not any(self._can_load_archive_member(Path(entry.name)) for entry in entries):
            return False

        settings.update({
            "format": "KiriKiri2",
            "source_path": str(path),
        })
        mgr.set_archive_setting(path.name, settings)

        staged = mgr.stage_package_original_archive(path, settings=settings)

        loadable_members = [
            extracted_path
            for extracted_path in staged.values()
            if self._can_load_archive_member(extracted_path)
        ]
        if not loadable_members:
            return False

        try:
            from CherryAI.formats import get_parser_registry

            parser = get_parser_registry().get("KiriKiri2")
        except Exception:
            parser = None

        package_root = mgr.get_package_original_dir()
        if parser is not None and hasattr(parser, "deduplicate_input_paths"):
            load_candidates = parser.deduplicate_input_paths(loadable_members, root=package_root)
        else:
            load_candidates = sorted(loadable_members)

        loaded_any = False
        for extracted_path in load_candidates:
            loaded_any = self._load_file(extracted_path, "auto", "auto") or loaded_any

        self._apply_kirikiri2_package_precedence(package_root)

        if loaded_any:
            self._sync_lines_to_manifest()
            self._sync_output_defaults_to_manifest()
            self._save_manifest_after_file_load()

        return loaded_any

    def _apply_kirikiri2_package_precedence(self, package_root: Path) -> None:
        """Prune loaded package members using KiriKiri2 patch/xp3 precedence."""
        try:
            from CherryAI.formats import get_parser_registry

            parser = get_parser_registry().get("KiriKiri2")
        except Exception:
            parser = None
        if parser is None or not hasattr(parser, "deduplicate_input_paths"):
            return

        package_files: List[LoadedFile] = []
        for loaded in self._loaded_files:
            if str(loaded.format_id).lower() != "kirikiri2":
                continue
            try:
                loaded.path.relative_to(package_root)
            except ValueError:
                continue
            package_files.append(loaded)

        if not package_files:
            return

        keep_paths = {
            str(path_obj)
            for path_obj in parser.deduplicate_input_paths(
                [loaded.path for loaded in package_files],
                root=package_root,
            )
        }

        changed = False
        filtered_loaded: List[LoadedFile] = []
        for loaded in self._loaded_files:
            if str(loaded.format_id).lower() != "kirikiri2":
                filtered_loaded.append(loaded)
                continue
            try:
                loaded.path.relative_to(package_root)
            except ValueError:
                filtered_loaded.append(loaded)
                continue
            if str(loaded.path) in keep_paths:
                filtered_loaded.append(loaded)
            else:
                changed = True

        if not changed:
            return

        self._loaded_files = filtered_loaded
        if self.session is not None and self.session.loaded_files:
            keep_loaded_paths = {str(loaded.path) for loaded in self._loaded_files}
            self.session.loaded_files = [
                path_obj for path_obj in self.session.loaded_files
                if str(path_obj) in keep_loaded_paths
            ]
        update_fn = getattr(self, "_update_step_data", None)
        if callable(update_fn):
            try:
                update_fn(force=True)
            except Exception:
                logger.debug("Deferred step-data refresh after KiriKiri2 pruning failed", exc_info=True)

    def _save_manifest_after_file_load(
        self,
        progress: Optional[LoadingProgressDialog] = None,
    ) -> None:
        """Save manifest after files are loaded (TASK 29.2).
        
        Ensures the manifest is saved to disk after file load operations
        to prevent data loss if the application crashes.
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            try:
                if progress is not None:
                    progress.set_phase("Saving project")
                    progress.set_progress(
                        current=progress._total,
                        current_file=mgr.project_name or "Current project",
                        detail="Writing manifest to disk",
                    )
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
        # O8: Tags
        # When parser tags were already applied during extraction (via
        # extract_tagged), only tag lines that don't have a tag yet.
        # ------------------------------------------------------------------
        if parser.tag_rules is not None:
            rules = parser.tag_rules
            compiled = rules.compiled()
            lines_data = mgr.get_lines()  # list of dicts with 'idx', 'orig'
            tagged_count = 0
            for entry in lines_data:
                if get_primary_line_tag(entry):
                    tagged_count += 1
                    continue
                text = entry.get("orig", "")
                tag = None
                for pattern_name, pattern in compiled.items():
                    if pattern and pattern.search(text):
                        tag = pattern_name.replace("_pattern", "")
                        break
                if tag:
                    set_primary_line_tag(entry, tag)
                    tagged_count += 1
            if tagged_count > 0:
                mgr.set_lines(lines_data)
                save_nested_bool_field(
                    mgr, "Options", "ParserHandlesTags", True,
                )
                logger.info(
                    "O8: Parser '%s' tagged %d lines with context markers",
                    parser.name, tagged_count,
                )

    def _ensure_project_created(
        self,
        progress: Optional[LoadingProgressDialog] = None,
    ) -> None:
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
                    manifest_path = mgr.create_new(
                        pending_name,
                        source_files,
                        save_immediately=False,
                    )
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
                            self._sync_lines_to_manifest(progress=progress)
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
                    manifest_path = create_project_method(
                        source_files,
                        suggested_name,
                        save_immediately=False,
                    )
                    if manifest_path:
                        logger.info("Project created: %s", manifest_path)
                        # Update manifest with lines from loaded files
                        if mgr.is_loaded:
                            self._sync_lines_to_manifest(progress=progress)
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
        new_lines_by_rel: Dict[str, List[Dict[str, Any]]] = {}

        # Derive rel_paths consistent with existing filedir
        new_paths = [lf.path for lf in new_loaded]
        if len(new_paths) > 1:
            base = mgr._find_common_base(new_paths)
        else:
            base = new_paths[0].parent

        source_paths: Dict[str, Path] = {}
        for loaded_file in new_loaded:
            try:
                rel_path = str(loaded_file.path.relative_to(base))
            except ValueError:
                rel_path = loaded_file.path.name
            source_paths[rel_path] = loaded_file.path

        # Copy to the staged Original/ tree before syncing lines so parser-backed
        # extraction sees the same project context during load and inject.
        try:
            if source_paths:
                self._begin_manifest_source_text_cache()
                mgr.copy_originals_to_project(
                    source_paths=source_paths,
                    source_text_cache=self._manifest_source_text_cache,
                    source_text_encodings=self._get_manifest_source_text_encodings(source_paths),
                )
                self._refresh_loaded_files_from_project_originals(
                    new_loaded,
                    base_path=base,
                )
        except Exception as e:
            logger.warning("Failed to stage new originals before sync: %s", e)

        self._begin_manifest_source_text_cache()
        try:
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
                new_lines_by_rel[rel_path] = self._build_manifest_line_entries(
                    loaded_file,
                    rel_path,
                )
        finally:
            self._end_manifest_source_text_cache()

        added = mgr.add_files(new_file_infos, new_lines_by_rel)
        logger.info("Added %d new file(s) to manifest", added)

        # Apply parser tags for newly added lines
        _tags_by_rel: Dict[str, List[str]] = {}
        for loaded_file in new_loaded:
            if loaded_file.tags:
                try:
                    rp = str(loaded_file.path.relative_to(base))
                except ValueError:
                    rp = loaded_file.path.name
                _tags_by_rel[rp] = loaded_file.tags
        if _tags_by_rel:
            lines_data = mgr.get_lines()
            filedir = mgr.get_filedir()
            for entry in filedir:
                t_list = _tags_by_rel.get(entry.rel_path)
                if t_list is None:
                    continue
                for j, tag_val in enumerate(t_list):
                    m_idx = entry.first_idx + j
                    if m_idx <= entry.last_idx and m_idx < len(lines_data):
                        set_primary_line_tag(lines_data[m_idx], tag_val)
            mgr.set_lines(lines_data)

    def _sync_lines_to_manifest(
        self,
        progress: Optional[LoadingProgressDialog] = None,
    ) -> None:
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

        source_handling = getattr(self, "_pending_source_handling", "copy")
        stage_source_paths = dict(getattr(self, "_pending_stage_source_paths", {}))
        source_base = getattr(self, "_pending_source_base", None)
        package_original_dir = mgr.get_package_original_dir().resolve()

        if not stage_source_paths and self._loaded_files:
            fallback_paths = [loaded_file.path for loaded_file in self._loaded_files]
            if len(fallback_paths) > 1:
                source_base = mgr._find_common_base(fallback_paths)
            elif fallback_paths:
                source_base = fallback_paths[0].parent
            if source_base is not None:
                for loaded_file in self._loaded_files:
                    try:
                        rel_path = str(loaded_file.path.relative_to(source_base))
                    except ValueError:
                        rel_path = loaded_file.path.name
                    stage_source_paths[rel_path] = loaded_file.path

        archive_only = bool(self._loaded_files) and all(
            package_original_dir in loaded_file.path.resolve().parents
            or loaded_file.path.resolve() == package_original_dir
            for loaded_file in self._loaded_files
        )

        if source_handling == "external":
            mgr.source_mode = "external"
            mgr.source_root = str(source_base.resolve()) if source_base is not None else ""
        else:
            mgr.source_mode = "internal"
            mgr.source_root = source_base.name if source_base is not None else ""
            self._begin_manifest_source_text_cache()
            if not archive_only and not self._copy_originals_to_project(
                stage_source_paths,
                source_handling,
                progress=progress,
            ):
                self._end_manifest_source_text_cache()
                return

        self._refresh_loaded_files_from_project_originals(base_path=source_base)
        
        # Collect all lines (compact: idx + orig only)
        lines: List[Dict[str, Any]] = []
        file_infos: List[Dict[str, Any]] = []
        idx = 0
        source_paths = [f.path for f in self._loaded_files]
        if source_base is not None:
            base_path = source_base
        elif archive_only:
            base_path = mgr.get_package_original_dir()
        elif len(source_paths) > 1:
            base_path = mgr._find_common_base(source_paths)
        elif source_paths:
            base_path = source_paths[0].parent
        else:
            base_path = Path.cwd()
        
        self._begin_manifest_source_text_cache()
        try:
            for loaded_file in self._loaded_files:
                _file_start_idx = idx
                try:
                    rel_path = str(loaded_file.path.relative_to(base_path))
                except ValueError:
                    rel_path = loaded_file.path.name

                for entry in self._build_manifest_line_entries(loaded_file, rel_path):
                    entry["idx"] = idx
                    lines.append(entry)
                    idx += 1
                
                # Classify file type when typing is enabled
                file_type = ""
                if typing_enabled:
                    file_type = classify_file_type(loaded_file.lines)
                
                # Build file info for filedir
                file_infos.append({
                    "path": str(loaded_file.path),
                    "rel_path": rel_path,
                    "format": loaded_file.format_id,
                    "line_count": loaded_file.line_count,
                    "encoding": loaded_file.encoding,
                    "type": file_type,
                })
        finally:
            self._end_manifest_source_text_cache()
        
        # Update manifest with lines
        mgr.set_lines(lines)
        
        # TASK 35.1: Build and set filedir
        filedir_entries = mgr.build_filedir_from_files(file_infos)
        mgr.set_filedir(filedir_entries)
        
        if mgr.source_mode != "external":
            mgr.source_root = base_path.name if base_path is not None else mgr.compute_source_root(source_paths)

        self._sync_output_defaults_to_manifest()

    def _build_manifest_line_entries(
        self,
        loaded_file: LoadedFile,
        rel_path: str,
    ) -> List[Dict[str, Any]]:
        """Build canonical manifest line entries with source ``ln``/``f`` capture."""
        mappings: List[Dict[str, int]] = []

        if loaded_file.lines:
            try:
                source_text = self._read_manifest_source_text(loaded_file, rel_path)
                if source_text is not None:
                    mappings = capture_source_line_mappings(source_text, loaded_file.lines)
            except Exception as exc:
                logger.warning(
                    "Failed to capture source line mappings for %s: %s",
                    rel_path,
                    exc,
                )

        if len(mappings) < len(loaded_file.lines):
            start_ln = len(mappings)
            mappings.extend(
                {"ln": start_ln + i + 1}
                for i in range(len(loaded_file.lines) - len(mappings))
            )

        entries: List[Dict[str, Any]] = []
        for j, line_text in enumerate(loaded_file.lines):
            primary_tag = ""
            if loaded_file.tags and j < len(loaded_file.tags):
                primary_tag = str(loaded_file.tags[j] or "").strip()
            normalized_text, whitespace_tags = capture_dialogue_edge_whitespace(
                line_text,
                primary_tag,
            )
            entry: Dict[str, Any] = {
                "orig": normalized_text,
                "ln": mappings[j].get("ln", j + 1),
            }
            if "f" in mappings[j]:
                entry["f"] = mappings[j]["f"]
            if primary_tag:
                set_primary_line_tag(entry, primary_tag)
            merged_tags = merge_line_tags(entry.get("tags"), whitespace_tags)
            if merged_tags:
                entry["tags"] = merged_tags
            entries.append(entry)
        return entries

    def _refresh_loaded_files_from_project_originals(
        self,
        loaded_files: Optional[List[LoadedFile]] = None,
        base_path: Optional[Path] = None,
    ) -> bool:
        """Refresh parser-backed loaded files from the staged ``Original/`` tree.

        LightVN and similar parsers can depend on project-local context during
        extraction. Step 0 therefore stages originals first, then re-extracts
        parser-backed files from ``Original/`` so the manifest matches the same
        parser view later used by Output injection.
        """
        mgr = self.manifest_manager
        files = loaded_files if loaded_files is not None else self._loaded_files
        if mgr is None or not mgr.is_loaded or not files:
            return False

        if base_path is None:
            paths = [loaded_file.path for loaded_file in files]
            if len(paths) > 1:
                base_path = mgr._find_common_base(paths)
            else:
                base_path = paths[0].parent

        try:
            from CherryAI.formats import get_parser_registry
            registry = get_parser_registry()
        except Exception as exc:
            logger.warning("Failed to access parser registry for staged refresh: %s", exc)
            return False

        refreshed = False

        for loaded_file in files:
            parser = registry.get(loaded_file.format_id)
            if parser is None:
                continue
            if not getattr(parser, "requires_staged_refresh", False):
                continue

            try:
                rel_path = str(loaded_file.path.relative_to(base_path))
            except ValueError:
                rel_path = loaded_file.path.name

            staged_path = mgr.resolve_file_path(rel_path)
            if not staged_path.exists():
                continue

            try:
                tagged = parser.extract_tagged(staged_path)
                if tagged is not None:
                    new_lines = [item.text for item in tagged]
                    new_tags = [item.tag for item in tagged]
                    if all(getattr(item, "ln", 0) > 0 for item in tagged):
                        new_source_mappings: Optional[List[Dict[str, int]]] = []
                        for item in tagged:
                            mapping: Dict[str, int] = {"ln": int(item.ln)}
                            if getattr(item, "f", 0) > 0:
                                mapping["f"] = int(item.f)
                            new_source_mappings.append(mapping)
                    else:
                        new_source_mappings = None
                else:
                    new_lines = parser.extract(staged_path)
                    new_tags = None
                    new_source_mappings = None
            except Exception as exc:
                logger.warning(
                    "Failed staged parser refresh for %s: %s",
                    rel_path,
                    exc,
                )
                continue

            if (
                loaded_file.lines == new_lines
                and loaded_file.tags == new_tags
                and loaded_file.source_mappings == new_source_mappings
            ):
                continue

            logger.info(
                "Refreshed staged parser extraction for %s (%d -> %d lines)",
                rel_path,
                len(loaded_file.lines),
                len(new_lines),
            )
            loaded_file.lines = new_lines
            loaded_file.tags = new_tags
            loaded_file.source_mappings = (
                [dict(item) for item in new_source_mappings]
                if new_source_mappings is not None
                else None
            )
            refreshed = True

        return refreshed

    def _sync_output_defaults_to_manifest(self) -> None:
        """Ensure manifest output defaults stay valid and input-driven."""
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded or not self._loaded_files:
            return

        output_options = mgr.get_output_options()
        first_file = self._loaded_files[0]
        changed = False

        if not str(output_options.get("Destination", "")).strip():
            output_options["Destination"] = SAME_AS_SOURCE_DESTINATION
            changed = True

        if not str(output_options.get("Format", "")).strip():
            output_options["Format"] = first_file.format_id
            changed = True

        output_encoding = str(output_options.get("Encoding", "")).strip()
        valid_output_encodings = {
            SAME_AS_INPUT_ENCODING,
            "utf-8",
            "utf-8-sig",
            "utf-16",
            "utf-16-le",
            "utf-16-be",
            "shift_jis",
            "cp932",
        }
        if not output_encoding or output_encoding.lower() == "auto" or output_encoding not in valid_output_encodings:
            output_options["Encoding"] = SAME_AS_INPUT_ENCODING
            changed = True

        if not isinstance(output_options.get("PreserveFolderStructure"), bool):
            output_options["PreserveFolderStructure"] = True
            changed = True

        if str(output_options.get("PairMode", "")).strip().lower() not in {
            DEFAULT_OUTPUT_PAIR_MODE,
            "translated_only",
            "side_by_side",
            "interleaved",
            "separate_files",
        }:
            output_options["PairMode"] = DEFAULT_OUTPUT_PAIR_MODE
            changed = True

        if str(output_options.get("FileNaming", "")).strip().lower() not in {
            "suffix",
            "prefix",
            DEFAULT_OUTPUT_NAMING,
            "replace",
        }:
            output_options["FileNaming"] = DEFAULT_OUTPUT_NAMING
            changed = True

        if not str(output_options.get("TextOption", "")).strip():
            output_options["TextOption"] = DEFAULT_OUTPUT_TEXT_OPTION
            changed = True

        if not isinstance(output_options.get("OverwriteExistingFiles"), bool):
            output_options["OverwriteExistingFiles"] = True
            changed = True

        if str(output_options.get("Backup", "")).strip().lower() not in {
            "none",
            DEFAULT_OUTPUT_BACKUP,
            "numbered",
            "extension",
        }:
            output_options["Backup"] = DEFAULT_OUTPUT_BACKUP
            changed = True

        if not str(output_options.get("BackupExtension", "")).strip():
            output_options["BackupExtension"] = DEFAULT_OUTPUT_BACKUP_EXTENSION
            changed = True

        for field_name in (
            "ExportManifestFile",
            "ExportProcessingLogs",
            "ExportGlossaryEntries",
        ):
            if not isinstance(output_options.get(field_name), bool):
                output_options[field_name] = False
                changed = True

        if changed:
            mgr.set_output_options(output_options)

    def _copy_originals_to_project(
        self,
        source_paths: Optional[Dict[str, Path]] = None,
        source_handling: str = "copy",
        progress: Optional[LoadingProgressDialog] = None,
    ) -> bool:
        """Copy source files to the project's Original/ directory.
        
        TASK 35.2: Ensures the project can be reopened and processed
        even if original source files are moved or deleted.
        Matches by computed rel_path instead of filename to handle
        duplicate filenames in different subdirectories correctly.
        """
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return False

        if source_handling == "external":
            return True
        
        try:
            stage_source_paths = dict(source_paths or getattr(self, "_pending_stage_source_paths", {}))
            if not stage_source_paths:
                filedir = mgr.get_filedir()
                all_abs = [lf.path for lf in self._loaded_files]
                base = mgr._find_common_base(all_abs)
                for loaded_file in self._loaded_files:
                    try:
                        rel = str(loaded_file.path.relative_to(base))
                    except ValueError:
                        rel = loaded_file.path.name
                    for entry in filedir:
                        if entry.rel_path == rel:
                            stage_source_paths[entry.rel_path] = loaded_file.path
                            break

            owned_progress = False
            if progress is None and len(stage_source_paths) > 3:
                progress = LoadingProgressDialog(self, len(stage_source_paths))
                owned_progress = True
            if progress is not None:
                progress.set_total(len(stage_source_paths))
                progress.set_phase("Staging Original tree")
                progress.set_progress(
                    current=0,
                    current_file="Preparing staged source copy",
                    detail="",
                )

            def _progress_callback(payload: Dict[str, Any]) -> bool:
                if progress is None:
                    self.update_idletasks()
                    return True
                return progress.update_staging(
                    rel_path=payload.get("rel_path", ""),
                    current_file=int(payload.get("current_file", 0)),
                    total_files=int(payload.get("total_files", len(stage_source_paths))),
                    file_bytes=int(payload.get("file_bytes", 0)),
                    file_total_bytes=int(payload.get("file_total_bytes", 0)),
                )

            copied = mgr.copy_originals_to_project(
                source_paths=stage_source_paths,
                force=True,
                move_files=(source_handling == "move"),
                progress_callback=_progress_callback if stage_source_paths else None,
                source_text_cache=self._manifest_source_text_cache,
                source_text_encodings=self._get_manifest_source_text_encodings(stage_source_paths),
            )
            if owned_progress and progress is not None:
                progress.close()
            if progress is not None and progress.cancelled:
                return False
            if copied:
                logger.info("Copied %d original file(s) to project", len(copied))
            return True
        except Exception as e:
            logger.warning("Failed to copy originals: %s", e)
            # Non-fatal - project can still work without copies
            return False

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
        if mgr is None:
            messagebox.showwarning("Warning", "No project loaded.")
            return

        import_stats = mgr.import_from_manifest_data(source_data, selections)

        # Log import metadata
        mgr.update_step_data(0, "last_import", {
            "source_manifest": str(source_path),
            "lines_matched": import_stats["matched"],
            "lines_total": import_stats["total"],
            "sections_imported": import_stats["sections_imported"],
            "timestamp": datetime.now().isoformat(),
        })

        # Build summary message
        parts: List[str] = []
        if import_stats["matched"] > 0:
            parts.append(
                f"Lines: {import_stats['matched']}/{import_stats['total']} matched"
            )
        if import_stats["sections_imported"] > 0:
            parts.append(f"Settings sections: {import_stats['sections_imported']}")
        if not parts:
            parts.append("No data imported (nothing selected).")

        messagebox.showinfo("Import Complete", "\n".join(parts))
        logger.info(
            "Import from %s — lines: %d/%d, sections: %d",
            source_path, import_stats["matched"],
            import_stats["total"], import_stats["sections_imported"],
        )

        # Refresh preview
        self._update_preview()

    def _on_create_patch(self) -> None:
        """Create a patch manifest by importing from another manifest and pruning unchanged files."""
        mgr = self._manifest_manager
        if mgr is None:
            messagebox.showwarning("Warning", "No project loaded.")
            return

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
            patch_summary = mgr.create_patch_from_manifest_path(Path(source_path))
        except Exception as exc:
            messagebox.showerror("Create Patch Failed", str(exc))
            logger.exception("Create Patch failed")
            return

        mgr.update_step_data(0, "last_patch", {
            "source_manifest": str(source_path),
            **patch_summary,
            "timestamp": datetime.now().isoformat(),
        })

        self._populate_from_manifest(mgr.get_raw_data())
        self._update_file_list()
        self._update_preview()
        self._update_summary()

        if self._loaded_files:
            self._select_first_file_in_tree()
            self.set_status("in-progress")
        else:
            self.set_status("completed")

        messagebox.showinfo(
            "Patch Created",
            "\n".join([
                f"Imported lines: {patch_summary['matched']}/{patch_summary['total']}",
                f"Settings sections: {patch_summary['sections_imported']}",
                f"Identical files removed: {patch_summary['identical_files_removed']}",
                f"Matched files removed: {patch_summary['matched_files_removed']}",
                f"Remaining files: {patch_summary['remaining_files']}",
            ]),
        )
        logger.info(
            "Create Patch from %s — identical removed: %d, matched removed: %d, remaining files: %d",
            source_path,
            patch_summary["identical_files_removed"],
            patch_summary["matched_files_removed"],
            patch_summary["remaining_files"],
        )

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
        return mgr.import_line_fields_from_manifest_data(source_data, selections)

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
        return mgr.import_settings_sections_from_manifest_data(source_data, selections)

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
            if path.suffix.lower() == ".xp3":
                return self._load_archive_file(path)

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

            parser_detected_encoding: Optional[str] = None
            if encoding == "auto":
                try:
                    from CherryAI.formats import get_parser_registry
                    parser = get_parser_registry().get(format_id)
                except Exception:
                    parser = None

                if parser is not None:
                    detect_fn = getattr(parser, "detect_encoding", None)
                    if callable(detect_fn):
                        parser_detected_encoding = detect_fn(path) or None

                encoding, detection_source = self._detect_encoding_info(
                    path,
                    parser_encoding=parser_detected_encoding,
                )
            else:
                encoding, detection_source = self._detect_encoding_info(
                    path,
                    manual_encoding=encoding,
                )

            logger.info(
                "Detected encoding for %s: %s (source=%s)",
                path,
                encoding,
                detection_source,
            )

            # Handshake: validate parser selection (M1-M3 check)
            if not self._validate_parser_selection(format_id):
                return False

            # Extract parser lines/tags in one pass when tagged extraction exists.
            lines, tags, source_mappings = self._extract_file_content(
                path,
                format_id,
                encoding,
            )

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
                tags=tags,
                source_mappings=source_mappings,
                detection_source=detection_source,
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

    def _extract_file_content(
        self,
        path: Path,
        format_id: str,
        encoding: str,
    ) -> Tuple[List[str], Optional[List[str]], Optional[List[Dict[str, int]]]]:
        """Extract lines plus optional parser tags and locator mappings."""
        try:
            from CherryAI.formats import get_parser_registry

            parser = get_parser_registry().get(format_id)
        except Exception:
            parser = None

        if parser is not None and hasattr(parser, "extract_tagged"):
            try:
                tagged = parser.extract_tagged(path)
            except Exception:
                tagged = None

            if tagged is not None:
                lines = [item.text for item in tagged]
                tags = [item.tag for item in tagged]
                source_mappings: Optional[List[Dict[str, int]]] = None
                if all(getattr(item, "ln", 0) > 0 for item in tagged):
                    source_mappings = []
                    for item in tagged:
                        mapping: Dict[str, int] = {"ln": int(item.ln)}
                        if getattr(item, "f", 0) > 0:
                            mapping["f"] = int(item.f)
                        source_mappings.append(mapping)
                return lines, tags, source_mappings

        return self._extract_lines(path, format_id, encoding), None, None

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

        # Determine source root for file resolution.
        mgr = self.manifest_manager
        
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
                
                if mgr is not None and mgr.is_loaded:
                    file_path = mgr.resolve_file_path(rel_path)
                else:
                    file_path = Path(rel_path)
                
                # Check if file was relocated (TASK 32.1)
                actual_path = Path(relocated.get(rel_path, str(file_path)))

                # Create LoadedFile
                loaded = LoadedFile(
                    path=actual_path if actual_path.exists() else file_path,
                    format_id=file_format,
                    line_count=max(last_idx - first_idx + 1, 0),
                    manifest_path=self.session.manifest_path if self.session else None,
                    content_loader=_make_manifest_content_loader(
                        lines_data,
                        first_idx,
                        last_idx,
                    ),
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
                line_tag = get_primary_line_tag(line_data)
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
                set_primary_line_tag(line_data, tag)

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

    def _update_step_data(self, *, force: bool = False) -> None:
        """Update step data in session state.

        Lines are already stored in the manifest ``lines[].orig`` via
        filedir, so we no longer duplicate them as ``all_lines``.
        File metadata is stored in the manifest ``filedir`` array, so
        we no longer duplicate it as ``files``.

        Merges into existing step data to preserve keys set elsewhere
        (e.g. ``manifest_path``, ``suggested_project_name``).
        """
        if self._bulk_load_depth > 0 and not force:
            self._pending_bulk_step_data_sync = True
            return

        data = self.get_step_data()
        data["total_lines"] = sum(f.line_count for f in self._loaded_files)
        data["encoding"] = self._encoding_var.get() if self._encoding_var else "utf-8"
        data["format_override"] = self._format_var.get() if self._format_var else "auto"
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
        self._pending_source_base = None
        self._pending_source_handling = "copy"
        self._pending_stage_source_paths = {}
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

                    loaded = LoadedFile(
                        path=actual_path if actual_path.exists() else file_path,
                        format_id=entry.format,
                        line_count=max(entry.last_idx - entry.first_idx + 1, 0),
                        manifest_path=(
                            self.session.manifest_path if self.session else None
                        ),
                        encoding=entry.encoding,
                        content_loader=_make_manifest_content_loader(
                            manifest_lines,
                            entry.first_idx,
                            entry.last_idx,
                        ),
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
