"""CherryAI GUI v2 Main Application.

Provides the main application window with:
- 10 workflow step tabs
- Right-side progress tracker (collapsible)
- Menu bar (File, Edit, Tools, Help)
- Status bar with progress indicator
- Keyboard shortcuts (Ctrl+D/Z/Y)
- Pastel blue theme
- Manifest-based state persistence (TASK 19)
"""

from __future__ import annotations

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pathlib import Path

from CherryAI.gui.dialogs.global_options import GlobalOptionsDialog, GlobalOptions
from CherryAI.gui.dialogs.project_dialog import (
    ProjectNameDialog,
    LoadManifestDialog,
    WelcomeDialog,
)
from CherryAI.gui.theme.colors import THEME, apply_theme
from CherryAI.gui.state.store import (
    SessionState,
    STEP_DEFINITIONS,
    get_session,
    reset_session,
    load_session_from_autosave,
)
from CherryAI.gui.progress import ProgressTracker
from CherryAI.gui.steps.analysis import AnalysisStep
from CherryAI.gui.steps.base import BaseStep, PlaceholderStep
from CherryAI.gui.steps.costs import CostsStep
from CherryAI.gui.steps.information import InformationStep
from CherryAI.gui.steps.input_extract import InputExtractionStep
from CherryAI.gui.steps.output_inject import OutputInjectStep
from CherryAI.gui.steps.postprocess import PostprocessingStep
from CherryAI.gui.steps.preprocess import PreprocessingStep
from CherryAI.gui.steps.qa import QAStep
from CherryAI.gui.steps.translate import TranslationStep
from CherryAI.gui.steps.wordwrap_overwrite import WordwrapOverwriteStep
from CherryAI.functions.manifest_manager import (
    ManifestManager,
    get_manifest_manager,
    reset_manifest_manager,
    MANIFEST_DIR,
    MANIFEST_EXT,
)
from CherryAI.functions import ini_manager

if TYPE_CHECKING:
    from CherryAI.gui.steps.base import BaseStep

logger = logging.getLogger(__name__)

# Application constants
APP_NAME = "CherryAI"
APP_VERSION = "2.0.0"
MIN_WIDTH = 1100
MIN_HEIGHT = 700
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800

# Session file paths
SESSION_FILE_EXT = ".cherrysession"


class App(tk.Tk):
    """Main application window for CherryAI GUI v2.

    Features:
    - 10 workflow step tabs
    - Right-side progress tracker
    - Menu bar with File, Edit, Tools, Help
    - Status bar with progress indicator
    - Keyboard shortcuts
    - Pastel blue theme
    - Manifest-based state persistence (TASK 19)
    """

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()

        # Window setup
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry(f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
        self.minsize(MIN_WIDTH, MIN_HEIGHT)

        # Initialize manifest manager (TASK 19 - primary state storage)
        self._manifest_manager: ManifestManager = get_manifest_manager()

        # Create session for backward compatibility (no autosave - manifest is primary)
        self._session_path: Optional[Path] = None
        self.session = get_session()
        
        # TASK 21.4: Flag to track if startup dialog should be shown
        self._show_startup_dialog = True
        
        # Try to restore manifest from INI (TASK 21.4)
        if ini_manager.get_restore_on_launch():
            last_manifest = ini_manager.get_last_manifest()
            if last_manifest and last_manifest.exists():
                try:
                    if self._manifest_manager.load(last_manifest):
                        self.session.manifest_path = last_manifest
                        ini_manager.add_to_recent_manifests(last_manifest)
                        logger.info("Restored last manifest: %s", last_manifest)
                        self._show_startup_dialog = False
                except Exception as e:
                    logger.warning("Failed to restore last manifest: %s", e)
        
        # Fallback: Try legacy autosave restore
        if self._show_startup_dialog:
            restored = load_session_from_autosave()
            if restored is not None and restored.manifest_path:
                restore_enabled = True
                if restored.global_options is not None:
                    try:
                        restore_enabled = restored.global_options.session.restore_on_launch
                    except AttributeError:
                        pass
                if restore_enabled and restored.manifest_path.exists():
                    self.session = restored
                    self._load_manifest_on_restore()
                    self._show_startup_dialog = False
                    logger.info("Restored session from legacy autosave")
        
        # TASK 19 Phase 3: No autosave thread - manifest auto-saves on step change/close

        # Step tab references
        self._step_tabs: List[BaseStep] = []
        self._current_tab_index = 0

        # Apply theme
        apply_theme(self)

        # Build UI
        self._build_menu()
        self._build_main_layout()
        self._build_status_bar()

        # Bind keyboard shortcuts
        self._bind_shortcuts()

        # Protocol handlers
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Restore session state in UI after build
        self._restore_session_ui()
        
        # TASK 21.4: Show startup dialog after main window is ready
        if self._show_startup_dialog:
            self.after(100, self._show_welcome_dialog)

        logger.info("CherryAI GUI v2 initialized")

    @property
    def manifest_manager(self) -> ManifestManager:
        """Get the manifest manager instance.
        
        TASK 19: Primary state storage for the application.
        """
        return self._manifest_manager

    def create_new_project(
        self, 
        source_files: List[Path], 
        suggested_name: Optional[str] = None
    ) -> Optional[Path]:
        """Create a new project with the given source files.
        
        TASK 19: Shows ProjectNameDialog and creates manifest.
        Called from InputExtractionStep when loading new files.
        
        Args:
            source_files: List of source file paths
            suggested_name: Suggested project name (e.g., from filename)
            
        Returns:
            Path to created manifest, or None if cancelled
        """
        result_path: Optional[Path] = None
        
        def on_create(project_name: str) -> None:
            nonlocal result_path
            # Create new manifest
            manifest_path = self._manifest_manager.create_new(project_name, source_files)
            result_path = manifest_path
            
            # Update session for legacy compatibility
            self.session.manifest_path = manifest_path
            
            # Update all steps with manifest manager
            for tab in self._step_tabs:
                tab._manifest_manager = self._manifest_manager
            
            self._set_status(f"Created project: {project_name}")
            logger.info("Created new project: %s at %s", project_name, manifest_path)
        
        # Show dialog
        dialog = ProjectNameDialog(
            self,
            source_files=source_files,
            suggested_name=suggested_name,
            on_create=on_create,
        )
        
        # Wait for dialog to close
        self.wait_window(dialog)
        
        return result_path

    def _build_menu(self) -> None:
        """Build the menu bar."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        # TASK 19 Phase 3: Simplified menu - manifest auto-saves, no manual session save
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project", command=self._on_new_session)
        file_menu.add_command(label="Open Project...", command=self._on_load_manifest)
        file_menu.add_separator()
        file_menu.add_command(label="Open Files...", command=self._on_open_files)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(
            label="Undo",
            command=self._on_undo,
            accelerator="Ctrl+Z",
        )
        edit_menu.add_command(
            label="Redo",
            command=self._on_redo,
            accelerator="Ctrl+Y",
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Mark Step Done",
            command=self._on_mark_done,
            accelerator="Ctrl+D",
        )

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Options...", command=self._on_options)
        tools_menu.add_command(label="Glossary Manager...", command=self._on_glossary)
        tools_menu.add_separator()
        tools_menu.add_command(label="Run CLI Test", command=self._on_cli_test)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self._on_help)
        help_menu.add_command(label="Keyboard Shortcuts", command=self._on_shortcuts_help)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._on_about)

    def _build_main_layout(self) -> None:
        """Build the main layout with tabs and progress tracker."""
        # Main horizontal paned window
        self._paned = ttk.PanedWindow(self, orient="horizontal")
        self._paned.pack(fill="both", expand=True)

        # Left side: Tab notebook
        self._notebook = ttk.Notebook(self._paned)
        self._paned.add(self._notebook, weight=4)

        # Create tabs for each step
        # NOTE: Step order changed - Estimation is now step 2 (after Analysis)
        for step_id, step_name in STEP_DEFINITIONS:
            tab: BaseStep
            if step_id == 0:
                # Input and Extraction - fully implemented
                tab = InputExtractionStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 1:
                # Analysis - fully implemented
                tab = AnalysisStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 2:
                # Costs step (renamed from Estimation in Phase 40)
                tab = CostsStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 3:
                # Information - fully implemented (moved from step 2)
                tab = InformationStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 4:
                # Preprocessing - fully implemented (moved from step 3)
                tab = PreprocessingStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 5:
                # Translation - fully implemented
                tab = TranslationStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 6:
                # Quality Assurance - fully implemented
                tab = QAStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 7:
                # Postprocessing - fully implemented
                tab = PostprocessingStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 8:
                # Wordwrap & Overwrite - fully implemented
                tab = WordwrapOverwriteStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            elif step_id == 9:
                # Output & Injection - fully implemented
                tab = OutputInjectStep(
                    self._notebook,
                    self.session,
                    manifest_manager=self._manifest_manager,
                )
            else:
                # Placeholder for unimplemented steps
                tab = PlaceholderStep(
                    self._notebook,
                    self.session,
                    step_id=step_id,
                    step_name=step_name,
                    manifest_manager=self._manifest_manager,
                )
            self._notebook.add(tab, text=f"{step_id + 1}. {step_name}")
            self._step_tabs.append(tab)

        # Bind tab change event
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Right side: Progress tracker
        self._progress_tracker = ProgressTracker(
            self._paned,
            self.session,
            on_step_click=self._on_progress_step_click,
        )
        self._paned.add(self._progress_tracker, weight=1)

    def _build_status_bar(self) -> None:
        """Build the status bar at the bottom."""
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", side="bottom")

        # Status message
        self._status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(
            status_frame,
            textvariable=self._status_var,
            anchor="w",
        )
        status_label.pack(side="left", fill="x", expand=True, padx=5, pady=2)

        # Progress bar (hidden by default)
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            status_frame,
            variable=self._progress_var,
            maximum=100,
            length=200,
        )
        self._progress_bar.pack(side="right", padx=5, pady=2)
        self._progress_bar.pack_forget()  # Hide initially

        # Separator above status bar
        ttk.Separator(self, orient="horizontal").pack(fill="x", side="bottom")

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        self.bind("<Control-d>", lambda e: self._on_mark_done())
        self.bind("<Control-D>", lambda e: self._on_mark_done())
        self.bind("<Control-z>", lambda e: self._on_undo())
        self.bind("<Control-Z>", lambda e: self._on_undo())
        self.bind("<Control-y>", lambda e: self._on_redo())
        self.bind("<Control-Y>", lambda e: self._on_redo())
        # TASK 19 Phase 3: Ctrl+S now triggers manual manifest save
        self.bind("<Control-s>", lambda e: self._on_manual_save())
        self.bind("<Control-S>", lambda e: self._on_manual_save())

    # ----------------------------- Event Handlers ----------------------------- #

    def _on_tab_changed(self, event: tk.Event) -> None:
        """Handle tab change event.
        
        TASK 19: Saves manifest on step change for automatic persistence.
        """
        old_index = self._current_tab_index
        new_index = self._notebook.index(self._notebook.select())

        # Notify old tab (captures form data to manifest)
        if 0 <= old_index < len(self._step_tabs):
            self._step_tabs[old_index].on_leave()

        # Save manifest after on_leave captures data (TASK 19)
        if self._manifest_manager.is_loaded:
            self._manifest_manager.current_step = new_index
            self._manifest_manager.save()
            logger.debug("Manifest saved on step change %d -> %d", old_index, new_index)

        # Update state
        self._current_tab_index = new_index
        self.session.current_step = new_index

        # Notify new tab
        if 0 <= new_index < len(self._step_tabs):
            self._step_tabs[new_index].on_enter()

        # Refresh progress tracker
        self._progress_tracker.refresh()

        self._set_status(f"Step {new_index + 1}: {STEP_DEFINITIONS[new_index][1]}")

    def _on_progress_step_click(self, step_id: int) -> None:
        """Handle click on progress tracker step.

        Args:
            step_id: Clicked step ID (0-9).
        """
        self._notebook.select(step_id)

    def _show_welcome_dialog(self) -> None:
        """Show welcome dialog on startup when no manifest is loaded.

        TASK 21.4: Handles first launch and cases where last manifest not found.
        """
        # Get last manifest name for resume option
        last_manifest = ini_manager.get_last_manifest()
        last_name = None
        if last_manifest and last_manifest.exists():
            # Manifest exists, so just load it (shouldn't reach here normally)
            last_name = last_manifest.stem
        
        # Show welcome dialog
        dialog = WelcomeDialog(
            self,
            show_skip=True,
            last_manifest_name=last_name,
        )
        
        # Wait for dialog
        self.wait_window(dialog)
        
        result = dialog.result
        logger.debug("Welcome dialog result: %s", result)
        
        if result == "resume" and last_manifest and last_manifest.exists():
            # Resume last project
            self._load_manifest_from_path(last_manifest)
            self._set_status(f"Resumed project: {last_manifest.stem}")
        elif result == WelcomeDialog.RESULT_NEW:
            # User wants to create new project - go to input step
            self._notebook.select(0)
            self._set_status("Create new project - load files to begin")
        elif result == WelcomeDialog.RESULT_LOAD:
            # Show load manifest dialog
            self._on_load_manifest()
        elif result == WelcomeDialog.RESULT_SKIP:
            # Start fresh
            self._set_status("Ready - load files or open a project")
        else:
            # Cancelled or closed
            self._set_status("Ready")

    def _load_manifest_from_path(self, manifest_path: Path) -> bool:
        """Load a manifest from a file path.

        Args:
            manifest_path: Path to manifest file.

        Returns:
            True if loaded successfully.
        """
        if not self._manifest_manager.load(manifest_path):
            logger.error("Failed to load manifest: %s", manifest_path)
            messagebox.showerror(
                "Load Error",
                f"Failed to load project:\n{manifest_path}",
            )
            return False

        # Update session with manifest path for legacy compatibility
        self.session.manifest_path = manifest_path

        # Update all steps with manifest manager
        for tab in self._step_tabs:
            tab._manifest_manager = self._manifest_manager

        # Navigate to saved step position
        saved_step = self._manifest_manager.current_step
        if 0 <= saved_step < len(self._step_tabs):
            self._notebook.select(saved_step)

        # Add to recent manifests
        ini_manager.add_to_recent_manifests(manifest_path)
        
        # Refresh UI
        self._progress_tracker.refresh()
        
        project_name = self._manifest_manager.project_name or manifest_path.stem
        logger.info("Loaded project: %s from %s", project_name, manifest_path)
        
        return True

    def _on_new_session(self) -> None:
        """Handle New Project menu item.
        
        TASK 19 Phase 3: Creates a new project (no session system).
        """
        if self._manifest_manager.dirty:
            response = messagebox.askyesnocancel(
                "Unsaved Changes",
                "Save changes before starting a new project?",
            )
            if response is None:  # Cancel
                return
            if response:  # Yes - save first
                if self._manifest_manager.is_loaded:
                    self._manifest_manager.save()

        # Reset manifest manager (TASK 19)
        self._manifest_manager.close()
        self._manifest_manager = reset_manifest_manager()
        
        # Reset session for legacy compatibility (no autosave)
        self.session = reset_session()
        self._session_path = None
        
        # Update all components with new state
        self._progress_tracker.session = self.session
        for tab in self._step_tabs:
            tab.session = self.session
            tab._manifest_manager = self._manifest_manager
        
        self._notebook.select(0)
        self._progress_tracker.refresh()
        self._set_status("New project - load files to begin")

    def _on_open_files(self) -> None:
        """Handle Open Files menu item."""
        self._show_not_implemented("Open Files")

    def _on_load_manifest(self) -> None:
        """Handle Load Manifest menu item.
        
        TASK 19: Opens LoadManifestDialog to select and load an existing project.
        """
        def on_load(manifest_path: Path) -> None:
            """Callback when manifest is selected."""
            if self._manifest_manager.load(manifest_path):
                # Update session with manifest path for legacy compatibility
                self.session.manifest_path = manifest_path
                
                # Update all steps with new manifest manager
                for tab in self._step_tabs:
                    tab._manifest_manager = self._manifest_manager
                
                # Navigate to saved step position
                saved_step = self._manifest_manager.current_step
                if 0 <= saved_step < len(self._step_tabs):
                    self._notebook.select(saved_step)
                
                # Refresh UI
                self._progress_tracker.refresh()
                project_name = self._manifest_manager.project_name or manifest_path.stem
                self._set_status(f"Loaded project: {project_name}")
                logger.info("Loaded manifest: %s", manifest_path)
            else:
                messagebox.showerror("Error", f"Failed to load manifest: {manifest_path}")
        
        LoadManifestDialog(self, on_load=on_load)

    def _on_manual_save(self) -> None:
        """Handle Ctrl+S - manual save trigger.
        
        TASK 19 Phase 3: Saves the current manifest.
        Manifest auto-saves on step change and close, but this allows manual save.
        """
        # Capture current step data first
        if 0 <= self._current_tab_index < len(self._step_tabs):
            self._step_tabs[self._current_tab_index].on_leave()
        
        if self._manifest_manager.is_loaded:
            if self._manifest_manager.save():
                self._set_status(f"Project saved: {self._manifest_manager.project_name}")
            else:
                self._set_status("Failed to save project")
        else:
            self._set_status("No project loaded - load files first")

    def _on_undo(self) -> None:
        """Handle Undo action."""
        desc = self.session.get_undo_description()
        if self.session.undo():
            self._set_status(f"Undo: {desc}")
            self._progress_tracker.refresh()
        else:
            self._set_status("Nothing to undo")

    def _on_redo(self) -> None:
        """Handle Redo action."""
        desc = self.session.get_redo_description()
        if self.session.redo():
            self._set_status(f"Redo: {desc}")
            self._progress_tracker.refresh()
        else:
            self._set_status("Nothing to redo")

    def _on_mark_done(self) -> None:
        """Handle Mark Step Done action."""
        step_id = self.session.current_step
        self.session.mark_done(step_id)
        self._progress_tracker.refresh()
        self._set_status(f"Step {step_id + 1} marked as done")

    def _on_options(self) -> None:
        """Handle Options menu item - opens Global Options dialog."""
        print("DEBUG: _on_options called")
        # Load current options from session or config
        current_options = getattr(self.session, "global_options", None)
        if current_options is None:
            print("DEBUG: Creating new GlobalOptions")
            current_options = GlobalOptions()

        def on_save(options: GlobalOptions) -> None:
            """Handle options save callback."""
            self.session.global_options = options
            self._set_status("Options saved")
            logger.info("Global options updated")

        print("DEBUG: Instantiating GlobalOptionsDialog")
        GlobalOptionsDialog(self, initial_options=current_options, on_save=on_save)
        print("DEBUG: GlobalOptionsDialog instantiated")

    def _on_glossary(self) -> None:
        """Handle Glossary Manager menu item."""
        self._show_not_implemented("Glossary Manager")

    def _on_cli_test(self) -> None:
        """Handle Run CLI Test menu item - runs one-click test suite.
        
        Runs the complete pipeline test in a background thread and shows
        results in a dialog. User can choose to skip API calls.
        """
        # Ask user if they want to skip API calls
        skip_api = messagebox.askyesno(
            "CLI Test Options",
            "Skip API calls during test?\n\n"
            "Yes = Quick test (no API charges)\n"
            "No = Full test (requires configured API)",
            default=messagebox.YES,
        )
        
        # Create progress dialog
        dialog = tk.Toplevel(self)
        dialog.title("Running CLI Test...")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Center dialog
        dialog.geometry("500x400")
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 250
        y = self.winfo_y() + (self.winfo_height() // 2) - 200
        dialog.geometry(f"+{x}+{y}")
        
        # Apply theme
        dialog.configure(bg=THEME.bg_main)
        
        # Status label
        status_var = tk.StringVar(value="Initializing test...")
        status_label = ttk.Label(dialog, textvariable=status_var)
        status_label.pack(padx=20, pady=10)
        
        # Progress bar
        progress = ttk.Progressbar(dialog, mode="indeterminate", length=300)
        progress.pack(padx=20, pady=10)
        progress.start(10)
        
        # Results text area (initially hidden, shown after test)
        results_frame = ttk.Frame(dialog)
        results_text = scrolledtext.ScrolledText(
            results_frame,
            width=60,
            height=15,
            font=("Consolas", 9),
            wrap=tk.WORD,
        )
        results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Close button (initially disabled)
        close_btn = ttk.Button(dialog, text="Close", command=dialog.destroy, state=tk.DISABLED)
        close_btn.pack(pady=10)
        
        def run_test() -> None:
            """Run test in background thread."""
            try:
                from CherryAI.functions.One_Click_Test import run_one_click_test
                
                # Update status
                dialog.after(0, lambda: status_var.set(
                    f"Running {'quick' if skip_api else 'full'} test..."
                ))
                
                # Run test
                report = run_one_click_test(skip_api=skip_api, verbose=False)
                
                # Format results
                summary = report.get_summary()
                
                # Update UI on main thread
                def show_results() -> None:
                    progress.stop()
                    progress.pack_forget()
                    
                    # Show results
                    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                    results_text.insert(tk.END, summary)
                    results_text.configure(state=tk.DISABLED)
                    
                    # Update status
                    if report.all_passed():
                        status_var.set("✓ All tests passed!")
                        dialog.title("CLI Test - Passed")
                    else:
                        passed = sum(1 for r in report.results if r.passed)
                        total = len(report.results)
                        status_var.set(f"✗ {passed}/{total} tests passed")
                        dialog.title("CLI Test - Failed")
                    
                    # Enable close button
                    close_btn.configure(state=tk.NORMAL)
                
                dialog.after(0, show_results)
                
            except Exception as e:
                def show_error() -> None:
                    progress.stop()
                    progress.pack_forget()
                    
                    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                    results_text.insert(tk.END, f"Test failed with error:\n\n{e}")
                    results_text.configure(state=tk.DISABLED)
                    
                    status_var.set("✗ Test failed with error")
                    dialog.title("CLI Test - Error")
                    close_btn.configure(state=tk.NORMAL)
                
                dialog.after(0, show_error)
        
        # Start background thread
        thread = threading.Thread(target=run_test, daemon=True)
        thread.start()

    def _on_help(self) -> None:
        """Handle Documentation menu item."""
        messagebox.showinfo(
            "Documentation",
            "CherryAI documentation is available in the doc/ folder.\n\n"
            "See features.md for user guide, technical.md for developers.",
        )

    def _on_shortcuts_help(self) -> None:
        """Handle Keyboard Shortcuts menu item."""
        shortcuts = """Keyboard Shortcuts:

Ctrl+D - Mark current step as done
Ctrl+Z - Undo last action
Ctrl+Y - Redo last undone action

Tab Navigation:
- Click tab or use progress tracker
- Steps can be accessed in any order
"""
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)

    def _on_about(self) -> None:
        """Handle About menu item."""
        about_text = f"""CherryAI v{APP_VERSION}

A tool to prepare text for AI translation.

GUI v2 - Step-Partitioned Workflow
10 workflow tabs for professional translation pipeline.

For more information, see the documentation.
"""
        messagebox.showinfo("About CherryAI", about_text)

    def _on_close(self) -> None:
        """Handle window close.
        
        TASK 19 Phase 3: Automatically saves manifest without prompting.
        TASK 21.4: Saves last manifest path to INI for startup restore.
        TASK 29.1: Properly closes ManifestManager (stops autosave thread).
        Manifest is always preserved to enable seamless resume.
        Calls on_leave() on current step to capture any pending form changes.
        """
        # Call on_leave on current step to capture any unsaved form data
        if 0 <= self._current_tab_index < len(self._step_tabs):
            try:
                self._step_tabs[self._current_tab_index].on_leave()
                logger.debug("Called on_leave for step %d before close", self._current_tab_index)
            except Exception as e:
                logger.warning("Failed to call on_leave for step %d: %s", self._current_tab_index, e)
        
        # Save manifest path before closing for INI storage
        manifest_path = self._manifest_manager.manifest_path
        
        # Save manifest if loaded (TASK 19 - primary state persistence)
        # TASK 29.1: close() will save if dirty and save_on_close is True, then stop autosave
        if self._manifest_manager.is_loaded:
            try:
                # Save first to capture latest state
                self._manifest_manager.save()
                logger.info("Manifest saved on close: %s", manifest_path)
                
                # TASK 21.4: Save last manifest path to INI for next launch
                if manifest_path:
                    ini_manager.set_last_manifest(manifest_path)
                    ini_manager.add_to_recent_manifests(manifest_path)
                    logger.debug("Saved last manifest to INI: %s", manifest_path)
            except Exception as e:
                logger.warning("Failed to save manifest on close: %s", e)
            
            # TASK 29.1: Properly close ManifestManager (stops autosave thread)
            try:
                self._manifest_manager.close()
                logger.debug("ManifestManager closed (autosave stopped)")
            except Exception as e:
                logger.warning("Failed to close ManifestManager: %s", e)
        
        # Save minimal session state for next launch (manifest path reference only)
        try:
            from CherryAI.gui.state.store import AUTOSAVE_DIR, AUTOSAVE_FILENAME
            autosave_path = AUTOSAVE_DIR / AUTOSAVE_FILENAME
            autosave_path.parent.mkdir(parents=True, exist_ok=True)
            # Store manifest path so we can restore on next launch
            if manifest_path:
                self.session.manifest_path = manifest_path
            self.session.save_to_file(autosave_path)
            logger.debug("Session reference saved to autosave on close")
        except Exception as e:
            logger.warning("Failed to save autosave on close: %s", e)

        # Destroy progress tracker (removes listener)
        self._progress_tracker.destroy()

        self.destroy()

    def _save_current_manifest(self) -> None:
        """Save the current manifest with session data.
        
        Updates the manifest file with current session state including
        step data that may have changed during the session.
        """
        if not self.session.manifest_path:
            return
            
        manifest_path = self.session.manifest_path
        
        try:
            # Load existing manifest
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            else:
                manifest_data = {"version": "2.0"}
            
            # Update with session state relevant to manifest
            from datetime import datetime
            manifest_data["metadata"] = manifest_data.get("metadata", {})
            manifest_data["metadata"]["last_modified"] = datetime.utcnow().isoformat() + "Z"
            
            # Store Information step metadata in manifest
            info_data = self.session.get_step(3).data  # Information step
            if info_data.get("metadata"):
                manifest_data["project_info"] = info_data["metadata"]
            
            # Write updated manifest
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, ensure_ascii=False, indent=2)
                
            logger.info("Manifest saved: %s", manifest_path)
            
        except Exception as e:
            logger.error("Failed to save manifest: %s", e)
            raise

    # ----------------------------- Helper Methods ----------------------------- #

    def _set_status(self, message: str) -> None:
        """Set status bar message.

        Args:
            message: Status message to display.
        """
        self._status_var.set(message)

    def _show_not_implemented(self, feature: str) -> None:
        """Show not implemented message.

        Args:
            feature: Feature name.
        """
        messagebox.showinfo(
            "Not Implemented",
            f"'{feature}' is not yet implemented.\n\n"
            "This feature will be available in a future phase.",
        )
        self._set_status(f"{feature} - not implemented")

    def _load_manifest_on_restore(self) -> None:
        """Load the manifest associated with the restored session.
        
        TASK 19: Uses ManifestManager for loading.
        Called during initialization when a session is restored from autosave.
        If the session has a manifest_path set, loads the manifest data.
        """
        if not self.session.manifest_path:
            return

        manifest_path = self.session.manifest_path
        if not manifest_path.exists():
            logger.warning(f"Manifest file not found: {manifest_path}")
            return

        try:
            # Load manifest using ManifestManager (TASK 19)
            if self._manifest_manager.load(manifest_path):
                # Also store in session for legacy compatibility
                self.session.manifest_data = self._manifest_manager.get_raw_data()
                logger.info(f"Loaded manifest via manager: {manifest_path}")
            else:
                # Fallback: try direct JSON load for legacy support
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                self.session.manifest_data = manifest_data
                logger.info(f"Loaded manifest (JSON fallback): {manifest_path}")
        except Exception as e:
            logger.warning(f"Failed to load manifest: {e}")

    def _restore_session_ui(self) -> None:
        """Restore UI state from loaded session.

        Called after UI is built to populate tabs with session data.
        """
        # Navigate to the saved current step
        if self.session.current_step != 0:
            try:
                self._notebook.select(self.session.current_step)
                self._current_tab_index = self.session.current_step
            except Exception as e:
                logger.warning("Failed to restore tab position: %s", e)

        # Refresh progress tracker with restored state
        self._progress_tracker.refresh()

        # Notify the current tab to refresh its data
        if 0 <= self._current_tab_index < len(self._step_tabs):
            try:
                self._step_tabs[self._current_tab_index].on_enter()
            except Exception as e:
                logger.warning("Failed to restore step %d: %s", self._current_tab_index, e)

        # Update status to reflect restored session
        if self.session.loaded_files:
            self._set_status(f"Session restored with {len(self.session.loaded_files)} file(s)")
        else:
            self._set_status("Ready")

    def show_progress(self, value: float) -> None:
        """Show and update progress bar.

        Args:
            value: Progress value (0-100).
        """
        self._progress_bar.pack(side="right", padx=5, pady=2)
        self._progress_var.set(value)

    def hide_progress(self) -> None:
        """Hide the progress bar."""
        self._progress_bar.pack_forget()


def main() -> None:
    """Entry point for the GUI application."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
