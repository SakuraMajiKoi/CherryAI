"""CherryAI GUI v2 - Project Dialog.

Dialog for entering a new project name when loading files without a manifest.
TASK 19: Part of the unified manifest state system.
TASK 21.4: Added WelcomeDialog for application startup.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Literal
from pathlib import Path

from CherryAI.gui.theme.colors import THEME, apply_theme

logger = logging.getLogger(__name__)


class WelcomeDialog(tk.Toplevel):
    """Welcome dialog shown on first launch or when no recent manifest found.

    Allows user to:
    - Create a new project
    - Load an existing project
    - Skip and start with empty session

    TASK 21.4: Part of Application Startup Manifest Loading.
    PHASE 58.11: Added auto-load last manifest checkbox option.
    """

    # Result types
    RESULT_NEW: str = "new"
    RESULT_LOAD: str = "load"
    RESULT_SKIP: str = "skip"
    RESULT_CANCEL: str = "cancel"

    def __init__(
        self,
        parent: tk.Tk,
        last_manifest_name: Optional[str] = None,
    ) -> None:
        """Initialize the welcome dialog.

        Args:
            parent: Parent window.
            last_manifest_name: Name of last manifest (shows "Resume" option if set).
        """
        super().__init__(parent)
        self._last_manifest_name = last_manifest_name
        self._result: str = self.RESULT_CANCEL
        
        # PHASE 58.11: Auto-load setting variable
        self._auto_load_var = tk.BooleanVar(value=False)

        self.title("Welcome to CherryAI")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        # Size and position
        self.geometry("500x360")  # Increased height for checkbox
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 250
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 180
        self.geometry(f"+{x}+{y}")

        # Apply theme
        apply_theme(self)
        self.configure(bg=THEME.bg_main)

        self._build_ui()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Bind keys
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main frame
        main_frame = ttk.Frame(self, padding=30)
        main_frame.pack(fill="both", expand=True)

        # Logo/Title area
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill="x", pady=(0, 20))

        title_label = ttk.Label(
            title_frame,
            text="🍒 CherryAI",
            font=("Segoe UI", 24, "bold"),
        )
        title_label.pack()

        subtitle_label = ttk.Label(
            title_frame,
            text="Comprehensive Translation Toolkit",
            font=("Segoe UI", 11),
            foreground=THEME.text_secondary,
        )
        subtitle_label.pack()

        # Options frame
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill="x", pady=20)

        # New project button
        new_btn = ttk.Button(
            options_frame,
            text="✨ Create New Project",
            command=self._on_new,
            style="Accent.TButton",
        )
        new_btn.pack(fill="x", pady=5, ipady=8)

        # Resume last project (if available)
        if self._last_manifest_name:
            resume_btn = ttk.Button(
                options_frame,
                text=f"📂 Resume: {self._last_manifest_name}",
                command=self._on_resume,
            )
            resume_btn.pack(fill="x", pady=5, ipady=8)

        # Load existing project button
        load_btn = ttk.Button(
            options_frame,
            text="📁 Load Existing Project",
            command=self._on_load,
        )
        load_btn.pack(fill="x", pady=5, ipady=8)

        # Auto-load tickbox — always visible so users can opt in/out
        auto_load_frame = ttk.Frame(main_frame)
        auto_load_frame.pack(fill="x", pady=(10, 5))

        # Load current setting from INI
        try:
            from CherryAI.functions import ini_manager
            self._auto_load_var.set(ini_manager.get_restore_on_launch())
        except Exception:
            pass

        auto_load_check = ttk.Checkbutton(
            auto_load_frame,
            text="Automatically load last project on startup",
            variable=self._auto_load_var,
            command=self._on_auto_load_toggled,
        )
        auto_load_check.pack(anchor="center")

        # Footer
        footer_label = ttk.Label(
            main_frame,
            text="Select an option to get started",
            foreground=THEME.text_secondary,
            font=("Segoe UI", 9),
        )
        footer_label.pack(side="bottom")

    def _on_auto_load_toggled(self) -> None:
        """Save auto-load preference immediately when tickbox is toggled."""
        try:
            from CherryAI.functions import ini_manager
            ini_manager.set_restore_on_launch(self._auto_load_var.get())
        except Exception as e:
            logger.warning("Failed to save auto-load preference: %s", e)

    def _on_resume(self) -> None:
        """Handle Resume button click.
        
        PHASE 58.11: Also saves auto-load preference if checkbox is checked.
        """
        # Save auto-load preference
        try:
            from CherryAI.functions import ini_manager
            ini_manager.set_restore_on_launch(self._auto_load_var.get())
        except Exception as e:
            logger.warning("Failed to save auto-load preference: %s", e)
        
        self._result = "resume"
        self.destroy()

    def _on_new(self) -> None:
        """Handle New Project button click.
        
        PHASE 58.11: Disables auto-load since user chose to create new project.
        """
        try:
            from CherryAI.functions import ini_manager
            ini_manager.set_restore_on_launch(False)
        except Exception:
            pass
        self._result = self.RESULT_NEW
        self.destroy()

    def _on_load(self) -> None:
        """Handle Load Project button click."""
        self._result = self.RESULT_LOAD
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel/Close."""
        self._result = self.RESULT_CANCEL
        self.destroy()

    @property
    def result(self) -> str:
        """Get the user's choice.

        Returns:
            One of: RESULT_NEW, RESULT_LOAD, RESULT_SKIP, RESULT_CANCEL, or "resume"
        """
        return self._result


class ProjectNameDialog(tk.Toplevel):
    """Dialog for entering a project name when creating a new manifest.
    
    Shown when user loads files that don't have an associated manifest.
    The project name is used for the manifest filename.
    """
    
    def __init__(
        self,
        parent: tk.Tk,
        source_files: Optional[list[Path]] = None,
        on_create: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        suggested_name: Optional[str] = None,
    ) -> None:
        """Initialize the dialog.
        
        Args:
            parent: Parent window.
            source_files: List of source files being loaded (optional).
            on_create: Callback when user creates project. Receives project name.
            on_cancel: Callback when user cancels.
            suggested_name: Pre-filled project name suggestion (optional).
        """
        super().__init__(parent)
        self._source_files = source_files or []
        self._on_create = on_create
        self._on_cancel = on_cancel
        self._result: Optional[str] = None
        self._suggested_name = suggested_name
        
        self.title("New Translation Project")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        
        # Center dialog - PHASE 58.3: Larger window to show all buttons
        self.geometry("500x280")
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 250
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 140
        self.geometry(f"+{x}+{y}")
        
        # Apply theme
        apply_theme(self)
        self.configure(bg=THEME.bg_main)
        
        self._build_ui()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel_click)
        
        # Focus on entry
        self._name_entry.focus_set()
        
        # Bind Enter to create
        self.bind("<Return>", lambda e: self._on_create_click())
        self.bind("<Escape>", lambda e: self._on_cancel_click())
    
    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main frame
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Create New Translation Project",
            font=("Segoe UI", 14, "bold"),
        )
        title_label.pack(pady=(0, 15))
        
        # Subtitle with file info
        if len(self._source_files) == 1:
            file_info = f"Loading: {self._source_files[0].name}"
        else:
            file_info = f"Loading {len(self._source_files)} files"
        
        subtitle_label = ttk.Label(
            main_frame,
            text=file_info,
            foreground=THEME.text_secondary,
        )
        subtitle_label.pack(pady=(0, 15))
        
        # Description
        desc_label = ttk.Label(
            main_frame,
            text="Enter a name for your translation project.\n"
                 "This will be used for the manifest file name.",
            justify="center",
            foreground=THEME.text_secondary,
        )
        desc_label.pack(pady=(0, 15))
        
        # Project name entry
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill="x", pady=10)
        
        name_label = ttk.Label(name_frame, text="Project Name:")
        name_label.pack(side="left", padx=(0, 10))
        
        self._name_var = tk.StringVar()
        
        # PHASE 58.3: Name field starts empty - no auto-suggestion
        # User must explicitly enter a project name
        
        self._name_entry = ttk.Entry(name_frame, textvariable=self._name_var, width=35)
        self._name_entry.pack(side="left", fill="x", expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(20, 0))
        
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel_click,
        )
        cancel_btn.pack(side="right", padx=(10, 0))
        
        create_btn = ttk.Button(
            button_frame,
            text="Create Project",
            command=self._on_create_click,
            style="Accent.TButton",
        )
        create_btn.pack(side="right")
    
    def _on_create_click(self) -> None:
        """Handle Create button click."""
        name = self._name_var.get().strip()
        
        if not name:
            from tkinter import messagebox
            messagebox.showwarning(
                "Name Required",
                "Please enter a project name.",
                parent=self,
            )
            return
        
        self._result = name
        logger.info("Creating project: %s", name)
        
        self.destroy()
        self._on_create(name)
    
    def _on_cancel_click(self) -> None:
        """Handle Cancel button click."""
        logger.debug("Project creation cancelled")
        self.destroy()
        if self._on_cancel:
            self._on_cancel()
    
    @property
    def result(self) -> Optional[str]:
        """Get the entered project name, or None if cancelled."""
        return self._result


class LoadManifestDialog(tk.Toplevel):
    """Dialog for loading an existing manifest file.
    
    Shows available manifests in the manifests directory.
    """
    
    def __init__(
        self,
        parent: tk.Tk,
        on_load: Callable[[Path], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize the dialog.
        
        Args:
            parent: Parent window.
            on_load: Callback when user loads a manifest. Receives manifest path.
            on_cancel: Callback when user cancels.
        """
        super().__init__(parent)
        self._on_load = on_load
        self._on_cancel = on_cancel
        self._result: Optional[Path] = None
        
        self.title("Load Translation Project")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        
        # Size and position
        self.geometry("600x400")
        self.minsize(400, 300)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 300
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 200
        self.geometry(f"+{x}+{y}")
        
        # Apply theme
        apply_theme(self)
        self.configure(bg=THEME.bg_main)
        
        self._build_ui()
        self._refresh_manifest_list()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel_click)
        
        # Bind keys
        self.bind("<Return>", lambda e: self._on_load_click())
        self.bind("<Escape>", lambda e: self._on_cancel_click())
        self.bind("<Double-1>", lambda e: self._on_load_click())
    
    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main frame
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Select a Translation Project",
            font=("Segoe UI", 14, "bold"),
        )
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 15))
        
        # Manifest list
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Treeview with scrollbar
        columns = ("name", "files", "modified")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        
        self._tree.heading("name", text="Project Name")
        self._tree.heading("files", text="Source Files")
        self._tree.heading("modified", text="Last Modified")
        
        self._tree.column("name", width=200)
        self._tree.column("files", width=200)
        self._tree.column("modified", width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        
        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky="ew")
        
        browse_btn = ttk.Button(
            button_frame,
            text="Browse...",
            command=self._on_browse_click,
        )
        browse_btn.pack(side="left")
        
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel_click,
        )
        cancel_btn.pack(side="right", padx=(10, 0))
        
        load_btn = ttk.Button(
            button_frame,
            text="Load Project",
            command=self._on_load_click,
            style="Accent.TButton",
        )
        load_btn.pack(side="right")
    
    def _refresh_manifest_list(self) -> None:
        """Refresh the list of available manifests."""
        from CherryAI.functions.manifest_manager import MANIFEST_DIR, MANIFEST_EXT
        import json
        from datetime import datetime
        
        # Clear existing items
        for item in self._tree.get_children():
            self._tree.delete(item)
        
        # Find all manifests
        manifest_dir = MANIFEST_DIR
        if not manifest_dir.exists():
            return
        
        # PHASE 58.11: Collect manifests with their data for sorting by date
        manifest_entries = []
        for manifest_path in manifest_dir.glob(f"*{MANIFEST_EXT}"):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                name = data.get("project_name", manifest_path.stem)
                files = data.get("source_files", [])
                files_str = ", ".join(Path(f).name for f in files[:3])
                if len(files) > 3:
                    files_str += f" +{len(files) - 3} more"
                
                modified = data.get("updated_at", "")
                modified_display = ""
                modified_sort = ""  # For sorting (ISO format or empty)
                if modified:
                    try:
                        dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                        modified_display = dt.strftime("%Y-%m-%d %H:%M")
                        modified_sort = modified  # Keep original ISO for sorting
                    except Exception:
                        modified_display = modified
                        modified_sort = modified
                
                manifest_entries.append({
                    "path": manifest_path,
                    "name": name,
                    "files_str": files_str,
                    "modified_display": modified_display,
                    "modified_sort": modified_sort,
                })
                
            except Exception as e:
                logger.warning("Failed to read manifest %s: %s", manifest_path, e)
        
        # Sort by modification date descending (latest first)
        manifest_entries.sort(key=lambda x: x["modified_sort"], reverse=True)
        
        # Insert into tree
        for entry in manifest_entries:
            self._tree.insert("", "end", iid=str(entry["path"]), values=(
                entry["name"], entry["files_str"], entry["modified_display"]
            ))
    
    def _on_load_click(self) -> None:
        """Handle Load button click."""
        selection = self._tree.selection()
        if not selection:
            from tkinter import messagebox
            messagebox.showwarning(
                "No Selection",
                "Please select a project to load.",
                parent=self,
            )
            return
        
        manifest_path = Path(selection[0])
        self._result = manifest_path
        
        self.destroy()
        self._on_load(manifest_path)
    
    def _on_browse_click(self) -> None:
        """Handle Browse button click."""
        from tkinter import filedialog
        from CherryAI.functions.manifest_manager import MANIFEST_DIR, MANIFEST_EXT
        
        # Default to Projects directory
        initial_dir = str(MANIFEST_DIR) if MANIFEST_DIR.exists() else str(Path.cwd())
        
        file_path = filedialog.askopenfilename(
            title="Select Project File",
            initialdir=initial_dir,
            filetypes=[
                ("CherryAI Project", f"*{MANIFEST_EXT}"),
                ("JSON Files", "*.json"),
                ("All Files", "*.*"),
            ],
            parent=self,
        )
        
        if file_path:
            self._result = Path(file_path)
            self.destroy()
            self._on_load(self._result)
    
    def _on_cancel_click(self) -> None:
        """Handle Cancel button click."""
        self.destroy()
        if self._on_cancel:
            self._on_cancel()
    
    @property
    def result(self) -> Optional[Path]:
        """Get the selected manifest path, or None if cancelled."""
        return self._result
