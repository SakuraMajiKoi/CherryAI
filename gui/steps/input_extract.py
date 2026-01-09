"""CherryAI GUI v2 Input and Extraction Step.

First workflow tab for loading files, previewing content, and detecting manifests.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk

from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState

logger = logging.getLogger(__name__)

# Supported file extensions for loading
SUPPORTED_EXTENSIONS = [
    ("All Supported", "*.txt *.csv *.tsv *.json *.xlsx"),
    ("Text Files", "*.txt"),
    ("CSV Files", "*.csv"),
    ("TSV Files", "*.tsv"),
    ("JSON Files", "*.json"),
    ("Excel Files", "*.xlsx"),
    ("All Files", "*.*"),
]

# Format detection map
FORMAT_MAP = {
    ".txt": "txt",
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".xlsx": "xlsx",
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


class InputExtractionStep(BaseStep):
    """Input and Extraction workflow step.

    Features:
    - File browser with multi-select
    - Format auto-detection
    - Preview table with raw lines
    - Manifest detection and loading
    - Batch summary widget
    - Format/encoding options panel
    """

    step_id = 0
    step_name = "Input and Extraction"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        **kwargs: Any,
    ) -> None:
        """Initialize the Input and Extraction step.

        Args:
            parent: Parent widget.
            session: Session state reference.
            **kwargs: Additional keyword arguments.
        """
        # Loaded files storage
        self._loaded_files: List[LoadedFile] = []
        self._current_file_index: int = -1

        # UI variables
        self._encoding_var: Optional[tk.StringVar] = None
        self._format_var: Optional[tk.StringVar] = None

        super().__init__(parent, session, **kwargs)

    def _build_ui(self) -> None:
        """Build the Input and Extraction UI."""
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

        # Load Files button
        load_btn = ttk.Button(
            toolbar,
            text="📁 Load Files...",
            command=self._on_load_files,
        )
        load_btn.pack(side="left", padx=2)

        # Load Manifest button
        manifest_btn = ttk.Button(
            toolbar,
            text="📋 Load Manifest...",
            command=self._on_load_manifest,
        )
        manifest_btn.pack(side="left", padx=2)

        # Clear button
        clear_btn = ttk.Button(
            toolbar,
            text="🗑 Clear All",
            command=self._on_clear_all,
        )
        clear_btn.pack(side="left", padx=2)

        # Separator
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)

        # Options panel
        options_frame = ttk.LabelFrame(toolbar, text="Options")
        options_frame.pack(side="left", padx=5)

        # Encoding selection
        ttk.Label(options_frame, text="Encoding:").pack(side="left", padx=2)
        self._encoding_var = tk.StringVar(value="utf-8")
        encoding_cb = ttk.Combobox(
            options_frame,
            textvariable=self._encoding_var,
            values=["utf-8", "utf-8-sig", "shift_jis", "cp932", "latin-1", "utf-16"],
            width=10,
            state="readonly",
        )
        encoding_cb.pack(side="left", padx=2)

        # Format override
        ttk.Label(options_frame, text="Format:").pack(side="left", padx=5)
        self._format_var = tk.StringVar(value="auto")
        format_cb = ttk.Combobox(
            options_frame,
            textvariable=self._format_var,
            values=["auto", "txt", "csv", "tsv", "json", "xlsx"],
            width=8,
            state="readonly",
        )
        format_cb.pack(side="left", padx=2)

    def _build_content(self) -> None:
        """Build the main content area with file list and preview."""
        content = ttk.PanedWindow(self, orient="horizontal")
        content.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Left: File list
        left_frame = ttk.LabelFrame(content, text="Loaded Files")
        content.add(left_frame, weight=1)

        # File listbox with scrollbar
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self._file_listbox = tk.Listbox(
            list_frame,
            selectmode="single",
            font=("Segoe UI", 10),
            bg=THEME.bg_input,
            fg=THEME.text_primary,
            selectbackground=THEME.bg_selected,
        )
        self._file_listbox.pack(side="left", fill="both", expand=True)
        self._file_listbox.bind("<<ListboxSelect>>", self._on_file_select)
        
        # Add right-click context menu
        self._file_context_menu = tk.Menu(self._file_listbox, tearoff=0)
        self._file_context_menu.add_command(label="Remove File", command=self._on_remove_selected_file)
        self._file_context_menu.add_command(label="Clear All", command=self._on_clear_all)
        self._file_listbox.bind("<Button-3>", self._on_file_listbox_right_click)
        
        # Add Delete key binding
        self._file_listbox.bind("<Delete>", lambda e: self._on_remove_selected_file())

        file_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self._file_listbox.yview,
        )
        file_scroll.pack(side="right", fill="y")
        self._file_listbox.configure(yscrollcommand=file_scroll.set)

        # Right: Preview table
        right_frame = ttk.LabelFrame(content, text="Preview")
        content.add(right_frame, weight=3)

        # Preview Treeview
        preview_frame = ttk.Frame(right_frame)
        preview_frame.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("line", "content")
        self._preview_tree = ttk.Treeview(
            preview_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        self._preview_tree.heading("line", text="#", anchor="w")
        self._preview_tree.heading("content", text="Content", anchor="w")
        self._preview_tree.column("line", width=60, stretch=False)
        self._preview_tree.column("content", width=600, stretch=True)
        self._preview_tree.pack(side="left", fill="both", expand=True)

        preview_scroll = ttk.Scrollbar(
            preview_frame,
            orient="vertical",
            command=self._preview_tree.yview,
        )
        preview_scroll.pack(side="right", fill="y")
        self._preview_tree.configure(yscrollcommand=preview_scroll.set)

        # Manifest info below preview
        self._manifest_frame = ttk.Frame(right_frame)
        self._manifest_frame.pack(fill="x", padx=5, pady=5)

        self._manifest_label = ttk.Label(
            self._manifest_frame,
            text="No manifest detected",
            foreground=THEME.text_secondary,
        )
        self._manifest_label.pack(side="left")

        self._load_manifest_btn = ttk.Button(
            self._manifest_frame,
            text="Load Manifest",
            command=self._on_load_detected_manifest,
            state="disabled",
        )
        self._load_manifest_btn.pack(side="right")

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

        encoding = self._encoding_var.get() if self._encoding_var else "utf-8"
        format_override = self._format_var.get() if self._format_var else "auto"

        loaded_count = 0
        for filepath in filepaths:
            path = Path(filepath)
            if self._load_file(path, encoding, format_override):
                loaded_count += 1

        if loaded_count > 0:
            self._update_summary()
            self._update_file_list()
            # Select first file if none selected
            if self._current_file_index < 0 and self._loaded_files:
                self._current_file_index = 0
                self._file_listbox.selection_set(0)
                self._update_preview()
            self.set_status("in-progress")
            logger.info("Loaded %d file(s)", loaded_count)
            
            # Populate project info suggestion from file path
            self._populate_project_info_from_files()
            
            # TASK 19 Phase 5: Create project if no manifest loaded
            self._ensure_project_created()
            
            # Trigger auto-analysis if enabled
            self._trigger_auto_analysis()
            
            # Trigger auto-preprocessing if enabled (runs after analysis)
            self._trigger_auto_preprocessing()

    def _ensure_project_created(self) -> None:
        """Ensure a project is created for loaded files (TASK 19 Phase 5).
        
        If ManifestManager has no loaded project, prompts user for project name
        and creates a new project. Called after files are loaded.
        """
        mgr = self.manifest_manager
        if mgr is not None and not mgr.is_loaded and self._loaded_files:
            # Get suggested name from step data
            step_data = self.get_step_data()
            suggested_name = step_data.get("suggested_project_name", "")
            
            # If no suggested name, use first file's parent folder or stem
            if not suggested_name and self._loaded_files:
                first_path = self._loaded_files[0].path
                if first_path.parent.name and first_path.parent.name not in (".", ""):
                    suggested_name = first_path.parent.name
                else:
                    suggested_name = first_path.stem
            
            # Get source file paths
            source_files = [f.path for f in self._loaded_files]
            
            # Call App.create_new_project via toplevel
            try:
                app = self.winfo_toplevel()
                if hasattr(app, "create_new_project"):
                    manifest_path = app.create_new_project(source_files, suggested_name)
                    if manifest_path:
                        logger.info("Project created: %s", manifest_path)
                        # Update manifest with lines from loaded files
                        if mgr.is_loaded:
                            self._sync_lines_to_manifest()
                    else:
                        logger.debug("User cancelled project creation")
            except Exception as e:
                logger.warning("Could not create project: %s", e)

    def _sync_lines_to_manifest(self) -> None:
        """Sync loaded file lines to the manifest (TASK 19 Phase 5)."""
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return
        
        # Collect all lines
        lines: List[Dict[str, Any]] = []
        idx = 0
        for loaded_file in self._loaded_files:
            for line_text in loaded_file.lines:
                lines.append({
                    "idx": idx,
                    "orig": line_text,
                    "source_file": str(loaded_file.path),
                })
                idx += 1
        
        # Update manifest
        mgr.set_lines(lines)
        mgr.set_source_files([f.path for f in self._loaded_files])

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
            self.session.loaded_files.clear()
            self.set_step_data({})
            logger.info("Cleared all loaded files")

    def _on_file_listbox_right_click(self, event: tk.Event) -> None:
        """Handle right-click on file listbox to show context menu."""
        # Select the item under the cursor
        try:
            index = self._file_listbox.nearest(event.y)
            if index >= 0:
                self._file_listbox.selection_clear(0, tk.END)
                self._file_listbox.selection_set(index)
                self._file_listbox.activate(index)
                self._current_file_index = index
            
            # Show the context menu
            self._file_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._file_context_menu.grab_release()

    def _on_remove_selected_file(self) -> None:
        """Remove the currently selected file from the loaded files list."""
        selection = self._file_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        if 0 <= index < len(self._loaded_files):
            removed_file = self._loaded_files[index]
            del self._loaded_files[index]
            
            # Update session state
            if index < len(self.session.loaded_files):
                del self.session.loaded_files[index]
            
            # Update current index
            if self._loaded_files:
                self._current_file_index = min(index, len(self._loaded_files) - 1)
            else:
                self._current_file_index = -1
            
            # Update UI
            self._update_file_list()
            self._update_preview()
            self._update_summary()
            
            # Select next file if available
            if self._loaded_files and self._current_file_index >= 0:
                self._file_listbox.selection_set(self._current_file_index)
            
            logger.info(f"Removed file: {removed_file.path}")
            
            # Update step status
            if not self._loaded_files:
                self.set_status("not-started")

    def _on_file_select(self, event: tk.Event) -> None:
        """Handle file selection in listbox."""
        selection = self._file_listbox.curselection()
        if selection:
            self._current_file_index = selection[0]
            self._update_preview()

    # ----------------------------- File Loading ----------------------------- #

    def _load_file(
        self,
        path: Path,
        encoding: str = "utf-8",
        format_override: str = "auto",
    ) -> bool:
        """Load a file and extract its content.

        Args:
            path: Path to the file.
            encoding: Text encoding.
            format_override: Format override or "auto".

        Returns:
            True if loaded successfully.
        """
        try:
            # Detect format
            if format_override != "auto":
                format_id = format_override
            else:
                format_id = FORMAT_MAP.get(path.suffix.lower(), "txt")

            # Extract lines using format handler
            lines = self._extract_lines(path, format_id, encoding)

            # Check for existing manifest, or auto-create one
            manifest_path = self._find_manifest(path)
            if manifest_path is None:
                # Auto-create manifest (TASK 18.8: Automated Manifest Management)
                manifest_path = self._create_manifest(path, lines, format_id)

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
            self.session.loaded_files.append(path)
            self._update_step_data()

            # Store last loaded manifest path for auto-restore
            if manifest_path:
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
            format_id: Format identifier.
            encoding: Text encoding.

        Returns:
            List of extracted lines.
        """
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

    def _create_manifest(
        self,
        path: Path,
        lines: List[str],
        format_id: str,
    ) -> Path:
        """Create a new manifest for a file.
        
        Args:
            path: Source file path.
            lines: Extracted text lines.
            format_id: Detected format.
            
        Returns:
            Path to the created manifest.
        """
        from datetime import datetime
        
        # Create manifest in the project's Projects folder
        manifest_dir = Path(__file__).parent.parent.parent / "Projects"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        
        manifest_name = f"{path.stem}.CherryAI.json"
        manifest_path = manifest_dir / manifest_name
        
        # Build manifest data following Manifest v2 spec
        manifest_data = {
            "version": "2.0",
            "summary": str(path),
            "source_file": str(path),
            "format": format_id,
            "line_count": len(lines),
            "operations": [],
            "metadata": {
                "created_utc": datetime.utcnow().isoformat() + "Z",
                "auto_created": True,
            },
        }
        
        # Write manifest
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)
        
        logger.info("Auto-created manifest: %s", manifest_path)
        return manifest_path

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
        """Check status of source files in manifest.
        
        Returns:
            Dict mapping file path to status: 'found', 'recoverable', 'missing'
        """
        status: Dict[str, str] = {}
        
        # Recoverable formats - have lines stored in manifest or can rebuild
        RECOVERABLE_FORMATS = {"txt", "csv", "tsv", "json"}
        # Non-recoverable formats - complex structure that can't be rebuilt
        NON_RECOVERABLE_FORMATS = {"rpgm", "xlsx", "epub", "pdf"}
        
        source_files = data.get("source_files", [])
        if not source_files:
            # Try legacy singular field
            source_file = data.get("source_file")
            if source_file:
                source_files = [source_file]
        
        file_format = data.get("format", "txt")
        has_lines = bool(data.get("lines"))
        
        for source_file in source_files:
            source_path = Path(source_file)
            
            if source_path.exists():
                status[source_file] = "found"
            elif has_lines and file_format in RECOVERABLE_FORMATS:
                status[source_file] = "recoverable"
            else:
                status[source_file] = "missing"
        
        # Show warnings if needed
        recoverable_files = [f for f, s in status.items() if s == "recoverable"]
        missing_files = [f for f, s in status.items() if s == "missing"]
        
        if recoverable_files:
            file_list = "\n".join(Path(f).name for f in recoverable_files[:5])
            if len(recoverable_files) > 5:
                file_list += f"\n...and {len(recoverable_files) - 5} more"
            messagebox.showwarning(
                "Source Files Not Found",
                f"Original source files not found, but content can be recovered from manifest:\n\n{file_list}",
            )
        
        if missing_files:
            file_list = "\n".join(Path(f).name for f in missing_files[:5])
            if len(missing_files) > 5:
                file_list += f"\n...and {len(missing_files) - 5} more"
            messagebox.showerror(
                "Source Files Missing",
                f"Original source files not found and cannot be recovered:\n\n{file_list}\n\n"
                "These files have complex formats that require the original file.",
            )
        
        return status

    def _populate_from_manifest(self, data: Dict[str, Any]) -> None:
        """Populate loaded files from manifest data.
        
        Args:
            data: Manifest data dictionary.
        """
        # Clear existing loaded files
        self._loaded_files.clear()
        self._current_file_index = -1
        
        source_files = data.get("source_files", [])
        if not source_files:
            source_file = data.get("source_file")
            if source_file:
                source_files = [source_file]
        
        file_format = data.get("format", "txt")
        lines_data = data.get("lines", [])
        
        # Group lines by source file
        lines_by_file: Dict[str, List[str]] = {}
        for line in lines_data:
            source = line.get("source_file", source_files[0] if source_files else "unknown")
            if source not in lines_by_file:
                lines_by_file[source] = []
            lines_by_file[source].append(line.get("orig", ""))
        
        # Create LoadedFile entries
        for source_file in source_files:
            path = Path(source_file)
            lines = lines_by_file.get(source_file, [])
            
            # If we have no lines from manifest but file exists, try loading it
            if not lines and path.exists():
                try:
                    encoding = self._encoding_var.get() if self._encoding_var else "utf-8"
                    format_override = self._format_var.get() if self._format_var else "auto"
                    self._load_file(path, encoding, format_override)
                    continue
                except Exception as e:
                    logger.warning("Could not load source file %s: %s", path, e)
            
            # Create LoadedFile from manifest data
            loaded = LoadedFile(
                path=path,
                format_id=file_format,
                lines=lines,
                manifest_path=self.session.manifest_path,
            )
            self._loaded_files.append(loaded)
        
        # Update UI
        self._update_file_list()
        self._update_summary()
        if self._loaded_files:
            self._current_file_index = 0
            self._file_listbox.selection_set(0)
            self._update_preview()
        
        # Mark step as in-progress if we have files
        if self._loaded_files:
            self.set_status("in-progress")

    # ----------------------------- UI Updates ----------------------------- #

    def _update_file_list(self) -> None:
        """Update the file listbox."""
        self._file_listbox.delete(0, tk.END)

        # Get source file status from step data
        step_data = self.get_step_data()
        source_status = step_data.get("source_files_status", {})

        for i, file in enumerate(self._loaded_files):
            display = f"{file.filename} ({file.line_count} lines)"
            self._file_listbox.insert(tk.END, display)
            
            # Determine color based on file status
            file_path = str(file.path)
            status = source_status.get(file_path, "found" if file.path.exists() else "missing")
            
            if status == "found":
                # File found - green if manifest exists, normal otherwise
                if file.manifest_path:
                    self._file_listbox.itemconfig(i, fg=THEME.accent_success)
            elif status == "recoverable":
                # File missing but recoverable - yellow warning
                self._file_listbox.itemconfig(i, fg="#DAA520")  # Goldenrod/yellow
            else:
                # File missing and not recoverable - red error
                self._file_listbox.itemconfig(i, fg=THEME.accent_error)

    def _update_preview(self) -> None:
        """Update the preview table for current file."""
        # Clear existing
        for item in self._preview_tree.get_children():
            self._preview_tree.delete(item)

        if self._current_file_index < 0 or not self._loaded_files:
            self._update_manifest_info(None)
            return

        file = self._loaded_files[self._current_file_index]

        # Show first 1000 lines (for performance)
        max_preview = 1000
        for i, line in enumerate(file.lines[:max_preview]):
            self._preview_tree.insert(
                "",
                "end",
                values=(i + 1, line),
            )

        if len(file.lines) > max_preview:
            self._preview_tree.insert(
                "",
                "end",
                values=("...", f"(+{len(file.lines) - max_preview} more lines)"),
            )

        # Update manifest info
        self._update_manifest_info(file)

    def _update_manifest_info(self, file: Optional[LoadedFile]) -> None:
        """Update manifest detection info.

        Args:
            file: Currently selected file.
        """
        if file is None:
            self._manifest_label.configure(
                text="No file selected",
                foreground=THEME.text_secondary,
            )
            self._load_manifest_btn.configure(state="disabled")
        elif file.manifest_path:
            self._manifest_label.configure(
                text=f"✓ Manifest found: {file.manifest_path.name}",
                foreground=THEME.accent_success,
            )
            self._load_manifest_btn.configure(state="normal")
        else:
            self._manifest_label.configure(
                text="No manifest detected for this file",
                foreground=THEME.text_secondary,
            )
            self._load_manifest_btn.configure(state="disabled")

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
        """Update step data in session state."""
        # Collect all lines from all files for analysis step
        all_lines: List[str] = []
        for f in self._loaded_files:
            all_lines.extend(f.lines)

        data = {
            "files": [f.to_dict() for f in self._loaded_files],
            "total_lines": sum(f.line_count for f in self._loaded_files),
            "encoding": self._encoding_var.get() if self._encoding_var else "utf-8",
            "format_override": self._format_var.get() if self._format_var else "auto",
            "all_lines": all_lines,  # For analysis step access
        }
        self.set_step_data(data)

    # ----------------------------- BaseStep Methods ----------------------------- #

    def on_enter(self) -> None:
        """Called when entering this step tab."""
        # Restore state from session
        step_data = self.get_step_data()
        
        # Restore LoadedFile objects from session data if not already loaded
        if not self._loaded_files and step_data.get("files"):
            self._restore_files_from_session(step_data)
        
        if self._loaded_files:
            # Files already loaded, refresh UI
            self._update_file_list()
            self._update_summary()
            # Select first file if none selected
            if self._current_file_index < 0:
                self._current_file_index = 0
                if self._file_listbox.size() > 0:
                    self._file_listbox.selection_set(0)
                self._update_preview()
        logger.debug("Entered Input and Extraction step")

    def _restore_files_from_session(self, step_data: Dict[str, Any]) -> None:
        """Restore LoadedFile objects from session step data.
        
        Args:
            step_data: Step data dictionary from session.
        """
        files_data = step_data.get("files", [])
        all_lines = step_data.get("all_lines", [])
        
        # Track line offset for multi-file support
        line_offset = 0
        
        for file_info in files_data:
            path = Path(file_info["path"])
            format_id = file_info.get("format_id", "txt")
            line_count = file_info.get("line_count", 0)
            manifest_path_str = file_info.get("manifest_path")
            encoding = file_info.get("encoding", "utf-8")
            
            # Restore manifest path from session or detect it
            if manifest_path_str:
                manifest_path = Path(manifest_path_str)
                # Verify it still exists
                if not manifest_path.exists():
                    manifest_path = self._find_manifest(path)
            else:
                # Try to detect manifest if not in session
                manifest_path = self._find_manifest(path)
            
            # Get lines for this file from all_lines
            if all_lines:
                file_lines = all_lines[line_offset:line_offset + line_count]
                line_offset += line_count
            else:
                # Try to reload from disk if lines not in session
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
            
            # Update session manifest path if we found one
            if manifest_path and not self.session.manifest_path:
                self.session.manifest_path = manifest_path
        
        logger.info("Restored %d files from session", len(self._loaded_files))

    def on_leave(self) -> None:
        """Called when leaving this step tab."""
        # Ensure state is saved
        self._update_step_data()
        logger.debug("Left Input and Extraction step")

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
        if hasattr(self.session, "global_options") and self.session.global_options:
            # GlobalOptions has session: SessionSettings which has auto_analyze_on_load
            if hasattr(self.session.global_options, "session"):
                auto_analyze = getattr(self.session.global_options.session, "auto_analyze_on_load", True)
        
        if not auto_analyze:
            return
            
        # Access the analysis step through the app
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 1:
                analysis_step = app._step_tabs[1]  # Step 1 is Analysis
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
        if hasattr(self.session, "global_options") and self.session.global_options:
            if hasattr(self.session.global_options, "session"):
                auto_preprocess = getattr(self.session.global_options.session, "auto_preprocess_on_load", True)
        
        if not auto_preprocess:
            return
            
        # Access the preprocessing step through the app
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 4:
                preprocess_step = app._step_tabs[4]  # Step 4 is Preprocessing
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