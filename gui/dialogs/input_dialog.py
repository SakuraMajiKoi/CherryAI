"""CherryAI GUI v2 - Unified Input Dialog.

Dialog for unified file/folder selection when loading files.
PHASE 58.1: Replaces separate Load Files/Load Folder buttons with a combined interface.
PHASE 58.12: Remembers last directory, includes Project Name field.
"""

from __future__ import annotations

import logging
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Callable, List, Optional, Set, Tuple

from CherryAI.gui.theme.colors import THEME, apply_window_preferences

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _path_matches_format_filter(path: Path, format_filter: str) -> bool:
    """Return whether *path* should be visible for the selected format."""
    if format_filter == "auto":
        return path.suffix.lower() in SUPPORTED_SUFFIXES

    try:
        from CherryAI.formats import get_parser_registry

        parser = get_parser_registry().get(format_filter)
        if parser is not None:
            return parser.can_handle(path)
    except Exception:
        pass

    allowed_suffixes = FORMAT_EXTENSIONS.get(format_filter)
    if allowed_suffixes is None:
        return True
    return path.suffix.lower() in allowed_suffixes

# Supported file extensions
SUPPORTED_SUFFIXES: Set[str] = {
    ".txt", ".csv", ".tsv", ".json", ".xlsx", ".xp3",
    ".png", ".jpg", ".jpeg", ".bmp",
}

# Format extension mapping
FORMAT_EXTENSIONS = {
    "txt": {".txt"},
    "csv": {".csv"},
    "tsv": {".tsv"},
    "json": {".json"},
    "xlsx": {".xlsx"},
    "kirikiri2": {".ks", ".tjs", ".xp3"},
    "rpgmaker": {".json", ".js"},
    "image": {".png", ".jpg", ".jpeg", ".bmp"},
}


class UnifiedInputDialog(tk.Toplevel):
    """Unified file and folder selection dialog.

    Features:
    - Dual-pane interface with folder tree and file list
    - Multi-select support for both files and folders
    - Add Selection button queues items without closing
    - Load button finalizes and begins pipeline
    - Format filtering based on selected format
    - Project Name field for new projects (PHASE 58.12)
    - Remembers last used directory (PHASE 58.12)

    PHASE 58.1: Input Button Unified Window implementation.
    """

    def __init__(
        self,
        parent: tk.Widget,
        format_filter: str = "auto",
        encoding: str = "auto",
        auto_pipeline: str = "3: Preprocess",
        initial_dir: Optional[str] = None,
        on_load: Optional[Callable[[List[Path], str, str], None]] = None,
        show_project_name: bool = False,
        suggested_project_name: str = "",
    ) -> None:
        """Initialize the unified input dialog."""
        super().__init__(parent)
        self._format_filter = format_filter
        self._encoding = encoding
        self._auto_pipeline = auto_pipeline
        self._on_load_callback = on_load
        self._show_project_name = show_project_name
        
        # PHASE 58.12: Get initial directory from ini_manager if not provided
        if initial_dir:
            self._initial_dir = initial_dir
        else:
            from CherryAI.functions import ini_manager
            last_dir = ini_manager.get_last_input_dir()
            self._initial_dir = str(last_dir) if last_dir else str(Path.home())
        
        # Selection queue
        self._selected_paths: List[Path] = []
        
        # Project name (PHASE 58.12)
        self._suggested_project_name = suggested_project_name
        self._project_name: str = ""
        
        # Result - now includes project_name, auto_pipeline, and source handling.
        self.result: Optional[Tuple[List[Path], str, str, str, str, str]] = None
        
        self.title("Select Files or Folders")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(700, 450)
        parent_window = parent.winfo_toplevel()
        apply_window_preferences(
            self,
            parent=parent_window,
            window_key="UnifiedInputDialog",
            default_geometry="900x600",
            center_on_parent=True,
        )

        self._build_ui()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.bind("<Return>", lambda e: self._on_load())

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main container
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # PanedWindow for left/right split
        paned = ttk.PanedWindow(main_frame, orient="horizontal")
        paned.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        # Left panel: Folder browser
        left_frame = self._build_folder_browser(paned)
        paned.add(left_frame, weight=2)

        # Right panel: Selection queue
        right_frame = self._build_selection_queue(paned)
        paned.add(right_frame, weight=1)

        # Options panel at bottom
        self._build_options_panel(main_frame)

        # Button panel at bottom
        self._build_button_panel(main_frame)

    def _build_folder_browser(self, parent: ttk.PanedWindow) -> ttk.LabelFrame:
        """Build the folder browser panel."""
        frame = ttk.LabelFrame(parent, text="Browse Files and Folders", padding=5)

        # Current path display
        import string
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]

        path_frame = ttk.Frame(frame)
        path_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(path_frame, text="Location:").pack(side="left")
        self._path_var = tk.StringVar(value=self._initial_dir)
        path_entry = ttk.Combobox(
            path_frame, 
            textvariable=self._path_var,
            values=drives,
        )
        path_entry.pack(side="left", fill="x", expand=True, padx=5)
        path_entry.bind("<Return>", lambda e: self._navigate_to_path())
        path_entry.bind("<<ComboboxSelected>>", lambda e: self._navigate_to_path())

        go_btn = ttk.Button(path_frame, text="Go", command=self._navigate_to_path, width=5)
        go_btn.pack(side="left")

        up_btn = ttk.Button(path_frame, text="\u2191 Up", command=self._go_up, width=6)
        up_btn.pack(side="left", padx=2)

        # File/folder tree
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)

        self._browser_tree = ttk.Treeview(
            tree_frame,
            columns=("type", "size"),
            show="tree headings",
            selectmode="extended",
        )
        self._browser_tree.heading("#0", text="Name", anchor="w")
        self._browser_tree.heading("type", text="Type", anchor="w")
        self._browser_tree.heading("size", text="Size", anchor="e")
        self._browser_tree.column("#0", width=300, stretch=True)
        self._browser_tree.column("type", width=80, stretch=False)
        self._browser_tree.column("size", width=80, stretch=False)
        self._browser_tree.pack(side="left", fill="both", expand=True)

        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._browser_tree.yview)
        y_scroll.pack(side="right", fill="y")
        self._browser_tree.configure(yscrollcommand=y_scroll.set)

        # Bind events
        self._browser_tree.bind("<Double-1>", self._on_browser_double_click)
        self._browser_tree.bind("<Return>", self._on_browser_enter)

        # Populate initial directory
        self._populate_browser(Path(self._initial_dir))

        # Add Selection button
        add_frame = ttk.Frame(frame)
        add_frame.pack(fill="x", pady=(5, 0))

        add_btn = ttk.Button(
            add_frame,
            text="➕ Add Selection to Queue",
            command=self._add_selection_to_queue,
            style="Primary.TButton",
        )
        add_btn.pack(side="left")

        ttk.Label(
            add_frame,
            text="(Double-click folder to open, select items then click Add)",
            foreground=THEME.text_secondary,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=10)

        return frame

    def _build_selection_queue(self, parent: ttk.PanedWindow) -> ttk.LabelFrame:
        """Build the selection queue panel."""
        frame = ttk.LabelFrame(parent, text="Selected Items", padding=5)

        # Queue list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="both", expand=True)

        self._queue_tree = ttk.Treeview(
            list_frame,
            columns=("type",),
            show="tree headings",
            selectmode="extended",
        )
        self._queue_tree.heading("#0", text="Path", anchor="w")
        self._queue_tree.heading("type", text="Type", anchor="w")
        self._queue_tree.column("#0", width=250, stretch=True)
        self._queue_tree.column("type", width=60, stretch=False)
        self._queue_tree.pack(side="left", fill="both", expand=True)

        q_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self._queue_tree.yview)
        q_scroll.pack(side="right", fill="y")
        self._queue_tree.configure(yscrollcommand=q_scroll.set)

        # Queue controls
        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.pack(fill="x", pady=(5, 0))

        remove_btn = ttk.Button(ctrl_frame, text="🗑️ Remove Selected", command=self._remove_from_queue)
        remove_btn.pack(side="left")

        clear_btn = ttk.Button(ctrl_frame, text="Clear All", command=self._clear_queue)
        clear_btn.pack(side="left", padx=5)

        # Selection count
        self._count_label = ttk.Label(
            frame,
            text="0 items selected",
            foreground=THEME.text_secondary,
        )
        self._count_label.pack(anchor="w", pady=(5, 0))

        return frame

    def _build_options_panel(self, parent: ttk.Frame) -> None:
        """Build the options panel.
        
        PHASE 58.12: Added Project Name field (left of Format/Encoding).
        """
        options_frame = ttk.LabelFrame(parent, text="Options", padding=5)
        options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # PHASE 58.12: Project Name field (only if show_project_name is True)
        if self._show_project_name:
            ttk.Label(options_frame, text="Project Name:").pack(side="left", padx=(0, 5))
            self._project_name_var = tk.StringVar(value=self._suggested_project_name)
            project_entry = ttk.Entry(
                options_frame,
                textvariable=self._project_name_var,
                width=20,
            )
            project_entry.pack(side="left")
            
            # Separator
            ttk.Separator(options_frame, orient="vertical").pack(side="left", fill="y", padx=15)

        # Format filter — base formats + registered parsers
        ttk.Label(options_frame, text="Format:").pack(side="left", padx=(0, 5))
        self._format_var = tk.StringVar(value=self._format_filter)
        format_values = ["auto", "txt", "csv", "tsv", "json", "xlsx", "rpgmaker", "image"]
        try:
            from CherryAI.formats import list_parser_names
            for pname in list_parser_names():
                lower = pname.lower()
                if lower not in format_values:
                    format_values.append(lower)
        except Exception:
            pass
        format_cb = ttk.Combobox(
            options_frame,
            textvariable=self._format_var,
            values=format_values,
            width=12,
            state="readonly",
        )
        format_cb.pack(side="left")

        # Encoding
        ttk.Label(options_frame, text="Encoding:").pack(side="left", padx=(20, 5))
        self._encoding_var = tk.StringVar(value=self._encoding)
        encoding_cb = ttk.Combobox(
            options_frame,
            textvariable=self._encoding_var,
            values=["auto", "utf-8", "utf-8-sig", "shift_jis", "cp932", "latin-1", "utf-16", "utf-16-le", "utf-16-be"],
            width=10,
            state="readonly",
        )
        encoding_cb.pack(side="left")

        ttk.Label(options_frame, text="Original:").pack(side="left", padx=(20, 5))
        self._source_mode_var = tk.StringVar(value="copy")
        source_mode_cb = ttk.Combobox(
            options_frame,
            textvariable=self._source_mode_var,
            values=["copy", "move", "external"],
            width=10,
            state="readonly",
        )
        source_mode_cb.pack(side="left")

        # Typing Enabled toggle button
        from CherryAI.functions.ini_manager import get_default, set_default
        typing_on = get_default("session", "typing_enabled", True, bool)
        self._typing_enabled = tk.BooleanVar(value=typing_on)
        self._typing_btn = ttk.Button(
            options_frame,
            text="Typing Enabled" if typing_on else "Typing Disabled",
            command=self._toggle_typing,
            width=16,
        )
        self._typing_btn.pack(side="left", padx=(20, 0))

        # Auto-Pipeline – hidden pending rework; widgets created but not packed
        # ttk.Label(options_frame, text="Auto-Pipeline:").pack(side="left", padx=(20, 5))
        self._pipeline_var = tk.StringVar(value=self._auto_pipeline)
        pipeline_cb = ttk.Combobox(
            options_frame,
            textvariable=self._pipeline_var,
            values=[
                "0: Manual",
                "1: Analyze",
                "2: Estimate Original",
                "3: Preprocess",
                "4: Mock Translate",
            ],
            width=18,
            state="readonly",
        )
        # pipeline_cb.pack(side="left")  # hidden pending rework

    def _build_button_panel(self, parent: ttk.Frame) -> None:
        """Build the button panel."""
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=2, column=0, sticky="ew")

        # Cancel button
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._on_cancel)
        cancel_btn.pack(side="right", padx=5)

        # Load button
        load_btn = ttk.Button(
            btn_frame,
            text="📥 Load Selected Items",
            command=self._on_load,
            style="Accent.TButton",
        )
        load_btn.pack(side="right")

        # Quick file dialog button
        file_btn = ttk.Button(
            btn_frame,
            text="📄 Quick File Select...",
            command=self._quick_file_select,
        )
        file_btn.pack(side="left")

    def _toggle_typing(self) -> None:
        """Toggle Typing Enabled/Disabled and persist to INI."""
        from CherryAI.functions.ini_manager import set_default

        new_val = not self._typing_enabled.get()
        self._typing_enabled.set(new_val)
        self._typing_btn.configure(
            text="Typing Enabled" if new_val else "Typing Disabled",
        )
        set_default("session", "typing_enabled", str(new_val))

    # ----------------------------- Browser Operations ----------------------------- #

    def _populate_browser(self, path: Path) -> None:
        """Populate the browser tree with contents of the given directory."""
        path = path.resolve()
        # Clear existing items
        for item in self._browser_tree.get_children():
            self._browser_tree.delete(item)

        if not path.exists() or not path.is_dir():
            return

        self._path_var.set(str(path))

        try:
            entries = list(path.iterdir())
        except PermissionError:
            logger.warning("Permission denied: %s", path)
            return
        except Exception as e:
            logger.error("Error reading directory: %s", e)
            return

        # Sort: folders first, then files, both alphabetically
        folders = sorted([e for e in entries if e.is_dir()], key=lambda p: p.name.lower())
        files = sorted([e for e in entries if e.is_file()], key=lambda p: p.name.lower())

        # Filter files by format if needed
        format_filter = self._format_var.get() if hasattr(self, "_format_var") else "auto"
        files = [f for f in files if _path_matches_format_filter(f, format_filter)]

        # Add folders
        for folder in folders:
            self._browser_tree.insert(
                "",
                "end",
                text=f"📁 {folder.name}",
                values=("Folder", ""),
                tags=("folder",),
            )

        # Add files
        for file in files:
            size = self._format_size(file.stat().st_size)
            file_type = file.suffix.upper()[1:] if file.suffix else "File"
            self._browser_tree.insert(
                "",
                "end",
                text=f"📄 {file.name}",
                values=(file_type, size),
                tags=("file",),
            )

    def _format_size(self, size: int) -> str:
        """Format file size to human-readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _navigate_to_path(self) -> None:
        """Navigate to the path in the path entry."""
        path = Path(self._path_var.get()).resolve()
        if path.exists() and path.is_dir():
            self._populate_browser(path)

    def _go_up(self) -> None:
        """Navigate to parent directory."""
        current = Path(self._path_var.get()).resolve()
        parent = current.parent
        if parent != current:  # Not at root
            self._populate_browser(parent)

    def _on_browser_double_click(self, event: tk.Event) -> None:
        """Handle double-click in browser tree."""
        item = self._browser_tree.identify_row(event.y)
        if not item:
            return

        item_text = self._browser_tree.item(item, "text")
        # Remove icon prefix
        name = item_text[2:].strip() if item_text.startswith(("📁", "📄")) else item_text

        current_path = Path(self._path_var.get())
        target_path = current_path / name

        if target_path.is_dir():
            self._populate_browser(target_path)
        elif target_path.is_file():
            # Double-click on file adds it to queue
            self._add_path_to_queue(target_path)

    def _on_browser_enter(self, event: tk.Event) -> None:
        """Handle Enter key in browser tree."""
        selection = self._browser_tree.selection()
        if not selection:
            return

        item = selection[0]
        item_text = self._browser_tree.item(item, "text")
        name = item_text[2:].strip() if item_text.startswith(("📁", "📄")) else item_text

        current_path = Path(self._path_var.get())
        target_path = current_path / name

        if target_path.is_dir():
            self._populate_browser(target_path)

    # ----------------------------- Queue Operations ----------------------------- #

    def _add_selection_to_queue(self) -> None:
        """Add selected items from browser to the queue."""
        selection = self._browser_tree.selection()
        if not selection:
            return

        current_path = Path(self._path_var.get())

        for item in selection:
            item_text = self._browser_tree.item(item, "text")
            name = item_text[2:].strip() if item_text.startswith(("📁", "📄")) else item_text
            full_path = current_path / name

            self._add_path_to_queue(full_path)

    def _add_path_to_queue(self, path: Path) -> None:
        """Add a path to the selection queue."""
        if path in self._selected_paths:
            return  # Already in queue

        self._selected_paths.append(path)

        path_type = "Folder" if path.is_dir() else "File"
        icon = "📁" if path.is_dir() else "📄"

        self._queue_tree.insert(
            "",
            "end",
            text=f"{icon} {path}",
            values=(path_type,),
        )

        self._update_count_label()

    def _remove_from_queue(self) -> None:
        """Remove selected items from the queue."""
        selection = self._queue_tree.selection()
        if not selection:
            return

        for item in selection:
            item_text = self._queue_tree.item(item, "text")
            # Extract path from text (remove icon prefix)
            path_str = item_text[2:].strip() if item_text.startswith(("📁", "📄")) else item_text
            path = Path(path_str)

            if path in self._selected_paths:
                self._selected_paths.remove(path)

            self._queue_tree.delete(item)

        self._update_count_label()

    def _clear_queue(self) -> None:
        """Clear all items from the queue."""
        self._selected_paths.clear()
        for item in self._queue_tree.get_children():
            self._queue_tree.delete(item)
        self._update_count_label()

    def _update_count_label(self) -> None:
        """Update the selection count label."""
        count = len(self._selected_paths)
        text = f"{count} item{'s' if count != 1 else ''} selected"
        self._count_label.configure(text=text)

    def _quick_file_select(self) -> None:
        """Open a quick file dialog for direct file selection."""
        filetypes = [
            ("All Supported", "*.txt *.csv *.tsv *.json *.xlsx *.xp3 *.png *.jpg *.jpeg *.bmp"),
            ("Text Files", "*.txt"),
            ("CSV Files", "*.csv"),
            ("JSON Files", "*.json"),
            ("Excel Files", "*.xlsx"),
            ("XP3 Archives", "*.xp3"),
            ("Image Files", "*.png *.jpg *.jpeg *.bmp"),
            ("All Files", "*.*"),
        ]

        files = filedialog.askopenfilenames(
            parent=self,
            title="Select Files",
            filetypes=filetypes,
            initialdir=self._path_var.get(),
        )

        for filepath in files:
            self._add_path_to_queue(Path(filepath))

    # ----------------------------- Dialog Actions ----------------------------- #

    def _on_load(self) -> None:
        """Handle Load button click.
        
        PHASE 58.12: Validates project name, saves last directory.
        """
        if not self._selected_paths:
            return

        format_filter = self._format_var.get()
        encoding = self._encoding_var.get()
        
        # PHASE 58.12: Get project name if shown
        project_name = ""
        if self._show_project_name:
            project_name = self._project_name_var.get().strip()
            if not project_name:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Project Name Required",
                    "Please enter a project name.",
                    parent=self,
                )
                return
        
        # PHASE 58.12: Save last used directory
        current_dir = Path(self._path_var.get()).resolve()
        if current_dir.exists() and current_dir.is_dir():
            from CherryAI.functions import ini_manager
            ini_manager.set_last_input_dir(current_dir)

        self.result = (
            list(self._selected_paths),
            format_filter,
            encoding,
            project_name,
            self._pipeline_var.get(),
            self._source_mode_var.get(),
        )

        if self._on_load_callback:
            self._on_load_callback(self._selected_paths, format_filter, encoding)

        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel button click or window close."""
        self.result = None
        self.destroy()

    def show(self) -> Optional[Tuple[List[Path], str, str, str, str, str]]:
        """Show the dialog and wait for result.

        PHASE 58.12: Result now includes project name.

        Returns:
            Tuple of (paths, format, encoding, project_name) or None if cancelled.
        """
        self.wait_window()
        return self.result
