"""CherryAI GUI v2 Output Step.

Tenth workflow tab for final output generation and file writing.
Provides format selection, naming options, and export functionality.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME
from CherryAI.gui.helpers.manifest_binding import (
    BindingInfo,
    bind_checkbox_to_field,
    bind_combobox_to_field,
    bind_entry_to_field,
)
from CherryAI.functions.manifest_fields import (
    get_all_lines_resolved,
    save_nested_text_field,
)

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager, FileDirEntry

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class OutputFormat(Enum):
    """Output file format."""

    TXT = "txt"
    CSV = "csv"
    TSV = "tsv"
    JSON = "json"
    XLSX = "xlsx"


class NamingStrategy(Enum):
    """File naming strategy."""

    SUFFIX = "suffix"
    PREFIX = "prefix"
    REPLACE = "replace"
    SUBFOLDER = "subfolder"


def _safe_naming_strategy(raw: str) -> NamingStrategy:
    """Parse a NamingStrategy from *raw*."""
    try:
        return NamingStrategy(raw)
    except ValueError:
        logger.warning("Unknown naming strategy %r, defaulting to SUFFIX", raw)
        return NamingStrategy.SUFFIX


class BackupStrategy(Enum):
    """Backup strategy for existing files."""

    NONE = "none"
    TIMESTAMP = "timestamp"
    NUMBERED = "numbered"
    EXTENSION = "extension"


class PairMode(Enum):
    """How to handle original/translated pairs."""

    TRANSLATED_ONLY = "translated_only"
    SIDE_BY_SIDE = "side_by_side"
    INTERLEAVED = "interleaved"
    SEPARATE_FILES = "separate_files"


class ExportStatus(Enum):
    """Status of export operation."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class OutputFile:
    """A file to be written."""

    idx: int
    source_path: str
    output_path: str
    format: OutputFormat = OutputFormat.TXT
    line_count: int = 0
    status: str = "pending"
    error: str = ""
    written: bool = False
    backup_path: str = ""

    @property
    def filename(self) -> str:
        """Get output filename."""
        return Path(self.output_path).name if self.output_path else ""

    @property
    def source_filename(self) -> str:
        """Get source filename."""
        return Path(self.source_path).name if self.source_path else ""


@dataclass
class NamingOptions:
    """Options for file naming."""

    strategy: NamingStrategy = NamingStrategy.SUBFOLDER
    suffix: str = "_translated"
    prefix: str = "translated_"
    replace_pattern: str = ""
    replace_with: str = "_translated"
    subfolder: str = "translated"


@dataclass
class BackupOptions:
    """Options for backup handling."""

    strategy: BackupStrategy = BackupStrategy.TIMESTAMP
    extension: str = ".bak"
    timestamp_format: str = "%Y%m%d_%H%M%S"


@dataclass
class OutputOptions:
    """Options for output generation."""

    format: OutputFormat = OutputFormat.TXT
    destination: str = ""
    naming: NamingOptions = field(default_factory=NamingOptions)
    backup: BackupOptions = field(default_factory=BackupOptions)
    pair_mode: PairMode = PairMode.TRANSLATED_ONLY
    preserve_structure: bool = True
    overwrite: bool = False
    encoding: str = "utf-8"


@dataclass
class ExportStats:
    """Statistics for export operation."""

    total_files: int = 0
    files_written: int = 0
    files_failed: int = 0
    files_skipped: int = 0
    total_lines: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    failure_log: List[Dict[str, str]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.files_written / self.total_files) * 100.0


@dataclass
class ManifestExportOptions:
    """Options for manifest export."""

    export_manifest: bool = True
    export_logs: bool = True
    export_glossary: bool = False
    manifest_path: str = ""
    log_path: str = ""


# ============================================================================
# Constants
# ============================================================================


FORMAT_DESCRIPTIONS: Dict[OutputFormat, str] = {
    OutputFormat.TXT: "Plain text (one line per line)",
    OutputFormat.CSV: "Comma-separated values",
    OutputFormat.TSV: "Tab-separated values",
    OutputFormat.JSON: "JSON array of lines",
    OutputFormat.XLSX: "Excel spreadsheet",
}


FORMAT_EXTENSIONS: Dict[OutputFormat, str] = {
    OutputFormat.TXT: ".txt",
    OutputFormat.CSV: ".csv",
    OutputFormat.TSV: ".tsv",
    OutputFormat.JSON: ".json",
    OutputFormat.XLSX: ".xlsx",
}


PAIR_MODE_DESCRIPTIONS: Dict[PairMode, str] = {
    PairMode.TRANSLATED_ONLY: "Output translated text only",
    PairMode.SIDE_BY_SIDE: "Original and translated in columns",
    PairMode.INTERLEAVED: "Alternating original/translated lines",
    PairMode.SEPARATE_FILES: "Separate files for original and translated",
}


NAMING_EXAMPLES: Dict[NamingStrategy, str] = {
    NamingStrategy.SUFFIX: "input.txt → input_translated.txt",
    NamingStrategy.PREFIX: "input.txt → translated_input.txt",
    NamingStrategy.REPLACE: "input.txt → output.txt (custom)",
    NamingStrategy.SUBFOLDER: "input.txt → translated/input.txt",
}


# ============================================================================
# OutputInjectStep Class
# ============================================================================


class OutputInjectStep(BaseStep):
    """Output step for file writing.

    Features:
    - Inject format selection (TXT, CSV, TSV, JSON, XLSX)
    - File naming options (_translated suffix, prefix, subfolder)
    - Destination path browser
    - Overwrite/backup rules
    - Export manifest and logs
    - Final summary: files written, time taken
    - Preview of output files before writing
    """

    step_id = 9
    step_name = "Output"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize Output step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables BEFORE super().__init__
        # because base class calls _build_ui() which needs these
        self._files: List[OutputFile] = []
        self._output_options = OutputOptions()
        self._manifest_options = ManifestExportOptions()
        self._status = ExportStatus.IDLE
        self._stats = ExportStats()
        self._export_thread: Optional[threading.Thread] = None
        self._cancel_requested = False
        self._selected_file_idx: int = -1
        # TASK 28.2: Manifest binding tracking
        self._manifest_bindings: List[BindingInfo] = []
        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the step UI."""
        self._build_header()
        self._build_content()
        self._build_summary_panel()

    def _build_header(self) -> None:
        """Build the header section with controls."""
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # Left: Title and status
        left_frame = ttk.Frame(header)
        left_frame.pack(side="left")

        ttk.Label(
            left_frame,
            text="Output & Injection",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side="left")

        self._status_label = ttk.Label(
            left_frame,
            text="Ready",
            foreground=THEME.text_secondary,
        )
        self._status_label.pack(side="left", padx=(10, 0))

        # Right: Buttons
        right_frame = ttk.Frame(header)
        right_frame.pack(side="right")

        self._export_btn = ttk.Button(
            right_frame,
            text="▶ Export All",
            command=self._export_all,
        )
        self._export_btn.pack(side="right")

        self._cancel_btn = ttk.Button(
            right_frame,
            text="✕ Cancel",
            command=self._cancel_export,
            state="disabled",
        )
        self._cancel_btn.pack(side="right", padx=(0, 5))

        ttk.Button(
            right_frame,
            text="↻ Refresh Preview",
            command=self._refresh_preview,
        ).pack(side="right", padx=(0, 5))

    def _build_content(self) -> None:
        """Build the main content area."""
        # Main paned window (horizontal)
        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Output files table
        left_frame = ttk.Frame(content)
        content.add(left_frame, weight=2)
        self._build_files_panel(left_frame)

        # Right: Options panels
        right_frame = ttk.Frame(content)
        content.add(right_frame, weight=1)
        self._build_options_panels(right_frame)

    def _build_files_panel(self, parent: ttk.Frame) -> None:
        """Build the output files table."""
        frame = ttk.LabelFrame(parent, text="Output Files")
        frame.pack(fill="both", expand=True)

        # Filter controls
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(filter_frame, text="Filter:").pack(side="left")

        self._filter_var = tk.StringVar(value="all")
        filter_options = [
            ("All", "all"),
            ("Pending", "pending"),
            ("Written", "written"),
            ("Failed", "failed"),
        ]
        for text, value in filter_options:
            ttk.Radiobutton(
                filter_frame,
                text=text,
                variable=self._filter_var,
                value=value,
                command=self._apply_filter,
            ).pack(side="left", padx=2)

        # Define columns
        columns = [
            ColumnDef(key="idx", title="#", width=50, anchor="center"),
            ColumnDef(key="status", title="Status", width=80, anchor="center"),
            ColumnDef(key="source", title="Source", width=150),
            ColumnDef(key="output", title="Output", width=200),
            ColumnDef(key="format", title="Format", width=60, anchor="center"),
            ColumnDef(key="lines", title="Lines", width=60, anchor="center"),
        ]

        self._files_table = SharedTable(
            frame,
            columns=columns,
            show_filter=True,
            show_checkboxes=True,
            show_count_filter=False,
            on_select=self._on_file_selected,
        )
        self._files_table.pack(fill="both", expand=True, padx=5, pady=5)

        # Batch action buttons
        batch_frame = ttk.Frame(frame)
        batch_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(
            batch_frame,
            text="▶ Export Selected",
            command=self._export_selected,
        ).pack(side="left", padx=2)

        ttk.Button(
            batch_frame,
            text="📂 Open Destination",
            command=self._open_destination,
        ).pack(side="left", padx=2)

        ttk.Button(
            batch_frame,
            text="📋 Copy Paths",
            command=self._copy_paths,
        ).pack(side="left", padx=2)

    def _build_options_panels(self, parent: ttk.Frame) -> None:
        """Build the right-side options panels."""
        # Create a scrollable frame
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Destination panel
        self._build_destination_panel(scrollable_frame)

        # Format options panel
        self._build_format_panel(scrollable_frame)

        # Naming options panel
        self._build_naming_panel(scrollable_frame)

        # Backup options panel
        self._build_backup_panel(scrollable_frame)

        # Export options panel
        self._build_export_panel(scrollable_frame)

        # Enable mousewheel scrolling (scoped to canvas, not bind_all)
        def _on_mousewheel(event: tk.Event) -> None:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        # Also bind on child frames so scrolling works when hovering over content
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)

    def _build_destination_panel(self, parent: ttk.Frame) -> None:
        """Build the destination path panel."""
        frame = ttk.LabelFrame(parent, text="Destination")
        frame.pack(fill="x", padx=5, pady=5)

        # Path entry with browse button
        path_frame = ttk.Frame(frame)
        path_frame.pack(fill="x", padx=5, pady=5)

        self._dest_var = tk.StringVar(value="")
        dest_entry = ttk.Entry(
            path_frame,
            textvariable=self._dest_var,
            width=30,
        )
        dest_entry.pack(side="left", fill="x", expand=True)

        ttk.Button(
            path_frame,
            text="Browse...",
            command=self._browse_destination,
        ).pack(side="right", padx=(5, 0))

        # Quick options
        opts_frame = ttk.Frame(frame)
        opts_frame.pack(fill="x", padx=5, pady=3)

        ttk.Button(
            opts_frame,
            text="Same as Source",
            command=self._use_source_dir,
        ).pack(side="left", padx=2)

        ttk.Button(
            opts_frame,
            text="Output Folder",
            command=self._use_output_dir,
        ).pack(side="left", padx=2)

        # Preserve structure checkbox
        self._preserve_var = tk.BooleanVar(value=True)
        preserve_cb = ttk.Checkbutton(
            frame,
            text="Preserve folder structure",
            variable=self._preserve_var,
        )
        preserve_cb.pack(anchor="w", padx=5, pady=3)

        # TASK 28.2: Bind to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_checkbox_to_field(
                    checkbox=preserve_cb,
                    var=self._preserve_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="PreserveFolderStructure",
                    default=True,
                    parent_key="OutputFormat",
                )
            )

    def _build_format_panel(self, parent: ttk.Frame) -> None:
        """Build the output format panel."""
        frame = ttk.LabelFrame(parent, text="Output Format")
        frame.pack(fill="x", padx=5, pady=5)

        # Format selection
        format_frame = ttk.Frame(frame)
        format_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(format_frame, text="Format:").pack(side="left")

        format_options = [f.value for f in OutputFormat]
        self._format_var = tk.StringVar(value=OutputFormat.TXT.value)
        format_combo = ttk.Combobox(
            format_frame,
            textvariable=self._format_var,
            values=[f.upper() for f in format_options],
            state="readonly",
            width=10,
        )
        format_combo.pack(side="left", padx=5)
        format_combo.bind("<<ComboboxSelected>>", self._on_format_changed)

        # TASK 28.2: Bind Format to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_combobox_to_field(
                    combobox=format_combo,
                    var=self._format_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="Format",
                    options=format_options,
                    default="txt",
                    parent_key="OutputFormat",
                )
            )

        # Format description
        self._format_desc = ttk.Label(
            frame,
            text=FORMAT_DESCRIPTIONS[OutputFormat.TXT],
            foreground=THEME.text_secondary,
        )
        self._format_desc.pack(anchor="w", padx=5, pady=3)

        # Pair mode
        pair_frame = ttk.Frame(frame)
        pair_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(pair_frame, text="Pair Mode:").pack(side="left")

        pair_options = [p.value for p in PairMode]
        self._pair_var = tk.StringVar(value=PairMode.TRANSLATED_ONLY.value)
        pair_combo = ttk.Combobox(
            pair_frame,
            textvariable=self._pair_var,
            values=[p.value.replace("_", " ").title() for p in PairMode],
            state="readonly",
            width=15,
        )
        pair_combo.pack(side="left", padx=5)

        # TASK 28.2: Bind PairMode to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_combobox_to_field(
                    combobox=pair_combo,
                    var=self._pair_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="PairMode",
                    options=pair_options,
                    default="translated_only",
                    parent_key="OutputFormat",
                )
            )

        # Encoding
        enc_frame = ttk.Frame(frame)
        enc_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(enc_frame, text="Encoding:").pack(side="left")

        encoding_options = ["utf-8", "utf-8-sig", "utf-16", "shift_jis", "cp932"]
        self._encoding_var = tk.StringVar(value="utf-8")
        enc_combo = ttk.Combobox(
            enc_frame,
            textvariable=self._encoding_var,
            values=encoding_options,
            width=12,
        )
        enc_combo.pack(side="left", padx=5)

        # TASK 28.2: Bind Encoding to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_combobox_to_field(
                    combobox=enc_combo,
                    var=self._encoding_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="Encoding",
                    options=encoding_options,
                    default="utf-8",
                    parent_key="OutputFormat",
                )
            )

    def _build_naming_panel(self, parent: ttk.Frame) -> None:
        """Build the file naming options panel."""
        frame = ttk.LabelFrame(parent, text="File Naming")
        frame.pack(fill="x", padx=5, pady=5)

        # Strategy selection
        self._naming_var = tk.StringVar(value=NamingStrategy.SUFFIX.value)

        strategies = [
            (NamingStrategy.SUFFIX, "Add suffix"),
            (NamingStrategy.PREFIX, "Add prefix"),
            (NamingStrategy.SUBFOLDER, "Put in subfolder"),
            (NamingStrategy.REPLACE, "Replace pattern"),
        ]

        for strategy, text in strategies:
            rb_frame = ttk.Frame(frame)
            rb_frame.pack(fill="x", padx=5, pady=2)

            ttk.Radiobutton(
                rb_frame,
                text=text,
                variable=self._naming_var,
                value=strategy.value,
                command=self._on_naming_changed,
            ).pack(side="left")

            ttk.Label(
                rb_frame,
                text=NAMING_EXAMPLES[strategy],
                foreground=THEME.text_secondary,
                font=("TkDefaultFont", 8),
            ).pack(side="left", padx=5)

        # TASK 28.2: Bind FileNaming radio buttons to manifest via trace
        if self._manifest_manager:
            self._naming_var.trace_add("write", self._save_file_naming_to_manifest)

        # Suffix/prefix entry (renamed to "Text Option" per todo.md)
        value_frame = ttk.Frame(frame)
        value_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(value_frame, text="Text Option:").pack(side="left")

        self._naming_value_var = tk.StringVar(value="_translated")
        self._naming_entry = ttk.Entry(
            value_frame,
            textvariable=self._naming_value_var,
            width=20,
        )
        self._naming_entry.pack(side="left", padx=5)

        # TASK 28.2: Bind TextOption entry to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_entry_to_field(
                    entry=self._naming_entry,
                    var=self._naming_value_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="TextOption",
                    default="_translated",
                    parent_key="OutputFormat",
                )
            )

    def _build_backup_panel(self, parent: ttk.Frame) -> None:
        """Build the backup options panel."""
        frame = ttk.LabelFrame(parent, text="Backup & Overwrite")
        frame.pack(fill="x", padx=5, pady=5)

        # Overwrite checkbox
        self._overwrite_var = tk.BooleanVar(value=False)
        overwrite_cb = ttk.Checkbutton(
            frame,
            text="Overwrite existing files",
            variable=self._overwrite_var,
            command=self._on_overwrite_changed,
        )
        overwrite_cb.pack(anchor="w", padx=5, pady=3)

        # TASK 28.2: Bind OverwriteExistingFiles to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_checkbox_to_field(
                    checkbox=overwrite_cb,
                    var=self._overwrite_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="OverwriteExistingFiles",
                    default=False,
                    parent_key="OutputFormat",
                )
            )

        # Backup strategy
        backup_frame = ttk.Frame(frame)
        backup_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(backup_frame, text="Backup:").pack(side="left")

        backup_options = ["none", "timestamp", "numbered", "extension"]
        self._backup_var = tk.StringVar(value=BackupStrategy.TIMESTAMP.value)
        backup_combo = ttk.Combobox(
            backup_frame,
            textvariable=self._backup_var,
            values=backup_options,
            state="readonly",
            width=12,
        )
        backup_combo.pack(side="left", padx=5)

        # TASK 28.2: Bind Backup to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_combobox_to_field(
                    combobox=backup_combo,
                    var=self._backup_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="Backup",
                    options=backup_options,
                    default="timestamp",
                    parent_key="OutputFormat",
                )
            )

        # Backup extension
        ext_frame = ttk.Frame(frame)
        ext_frame.pack(fill="x", padx=5, pady=3)

        ttk.Label(ext_frame, text="Backup ext:").pack(side="left")

        self._backup_ext_var = tk.StringVar(value=".bak")
        backup_ext_entry = ttk.Entry(
            ext_frame,
            textvariable=self._backup_ext_var,
            width=10,
        )
        backup_ext_entry.pack(side="left", padx=5)

        # TASK 28.2: Bind BackupExtension to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_entry_to_field(
                    entry=backup_ext_entry,
                    var=self._backup_ext_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="BackupExtension",
                    default=".bak",
                    parent_key="OutputFormat",
                )
            )

    def _build_export_panel(self, parent: ttk.Frame) -> None:
        """Build the export options panel."""
        frame = ttk.LabelFrame(parent, text="Export Options")
        frame.pack(fill="x", padx=5, pady=5)

        # Export manifest
        self._export_manifest_var = tk.BooleanVar(value=False)
        export_manifest_cb = ttk.Checkbutton(
            frame,
            text="Export manifest file",
            variable=self._export_manifest_var,
        )
        export_manifest_cb.pack(anchor="w", padx=5, pady=3)

        # TASK 28.2: Bind ExportManifestFile to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_checkbox_to_field(
                    checkbox=export_manifest_cb,
                    var=self._export_manifest_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="ExportManifestFile",
                    default=False,
                    parent_key="OutputFormat",
                )
            )

        # Export logs
        self._export_logs_var = tk.BooleanVar(value=False)
        export_logs_cb = ttk.Checkbutton(
            frame,
            text="Export processing logs",
            variable=self._export_logs_var,
        )
        export_logs_cb.pack(anchor="w", padx=5, pady=3)

        # TASK 28.2: Bind ExportProcessingLogs to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_checkbox_to_field(
                    checkbox=export_logs_cb,
                    var=self._export_logs_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="ExportProcessingLogs",
                    default=False,
                    parent_key="OutputFormat",
                )
            )

        # Export glossary
        self._export_glossary_var = tk.BooleanVar(value=False)
        export_glossary_cb = ttk.Checkbutton(
            frame,
            text="Export glossary entries",
            variable=self._export_glossary_var,
        )
        export_glossary_cb.pack(anchor="w", padx=5, pady=3)

        # TASK 28.2: Bind ExportGlossaryEntries to manifest
        if self._manifest_manager:
            self._manifest_bindings.append(
                bind_checkbox_to_field(
                    checkbox=export_glossary_cb,
                    var=self._export_glossary_var,
                    manager_getter=lambda: self.manifest_manager,
                    field_key="ExportGlossaryEntries",
                    default=False,
                    parent_key="OutputFormat",
                )
            )

    def _build_summary_panel(self) -> None:
        """Build the summary statistics panel."""
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=5)

        # Dirty flag indicators (Task 47.10)
        flag_frame = ttk.Frame(frame)
        flag_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(flag_frame, text="Pipeline:").pack(side="left")
        self._process_flag_label = ttk.Label(
            flag_frame,
            text="✓ Process",
            foreground=THEME.accent_success,
        )
        self._process_flag_label.pack(side="left", padx=5)
        self._wordwrap_flag_label = ttk.Label(
            flag_frame,
            text="✓ Wordwrap",
            foreground=THEME.accent_success,
        )
        self._wordwrap_flag_label.pack(side="left", padx=5)

        # Stats labels
        stats_frame = ttk.Frame(frame)
        stats_frame.pack(side="left")

        self._stats_labels: Dict[str, ttk.Label] = {}

        stats = [
            ("total", "Files:"),
            ("written", "Written:"),
            ("failed", "Failed:"),
            ("lines", "Lines:"),
            ("time", "Time:"),
        ]

        for key, text in stats:
            lbl_frame = ttk.Frame(stats_frame)
            lbl_frame.pack(side="left", padx=10)

            ttk.Label(lbl_frame, text=text).pack(side="left")
            value_lbl = ttk.Label(
                lbl_frame,
                text="0",
                foreground=THEME.accent_info,
            )
            value_lbl.pack(side="left", padx=2)
            self._stats_labels[key] = value_lbl

        # Progress bar
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            frame,
            variable=self._progress_var,
            maximum=100,
            length=200,
        )
        self._progress_bar.pack(side="right", padx=5)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_format_changed(self, event: Optional[tk.Event] = None) -> None:
        """Handle format selection change."""
        try:
            format_val = self._format_var.get().lower()
            output_format = OutputFormat(format_val)
            self._format_desc.configure(text=FORMAT_DESCRIPTIONS[output_format])
            self._refresh_preview()
        except (ValueError, KeyError):
            pass

    def _on_naming_changed(self) -> None:
        """Handle naming strategy change."""
        strategy = _safe_naming_strategy(self._naming_var.get())

        # Update the value entry placeholder
        if strategy == NamingStrategy.SUFFIX:
            self._naming_value_var.set("_translated")
        elif strategy == NamingStrategy.PREFIX:
            self._naming_value_var.set("translated_")
        elif strategy == NamingStrategy.SUBFOLDER:
            self._naming_value_var.set("translated")
        else:
            self._naming_value_var.set("")

        self._refresh_preview()

    def _on_overwrite_changed(self) -> None:
        """Handle overwrite checkbox change."""
        # Disable backup options if overwrite is unchecked and file exists
        pass

    def _on_file_selected(self, row_ids: List[int]) -> None:
        """Handle file selection in table."""
        if not row_ids:
            self._selected_file_idx = -1
            return

        self._selected_file_idx = row_ids[0]

    def _apply_filter(self) -> None:
        """Apply filter to the files table."""
        filter_val = self._filter_var.get()
        self._refresh_table(filter_val)

    # =========================================================================
    # Actions
    # =========================================================================

    def _browse_destination(self) -> None:
        """Open folder browser for destination."""
        folder = filedialog.askdirectory(
            title="Select Destination Folder",
            initialdir=self._dest_var.get() or Path.cwd(),
        )
        if folder:
            self._dest_var.set(folder)
            self._refresh_preview()

    def _use_source_dir(self) -> None:
        """Set destination to source directory."""
        if self._files:
            source_path = Path(self._files[0].source_path)
            if source_path.parent.exists():
                self._dest_var.set(str(source_path.parent))
                self._refresh_preview()

    def _use_output_dir(self) -> None:
        """Set destination to project's Patch directory (TASK 35.3).
        
        Uses Projects/{project_name}/Patch/ as the default output location.
        Falls back to output/ folder if no manifest is loaded.
        """
        # TASK 35.3: Use project's Patch directory as default
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            patch_dir = mgr.get_patch_dir()
            patch_dir.mkdir(parents=True, exist_ok=True)
            self._dest_var.set(str(patch_dir))
            self._refresh_preview()
            return
        
        # Fallback to output/ folder
        output_dir = Path(__file__).parent.parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        self._dest_var.set(str(output_dir))
        self._refresh_preview()

    def _open_destination(self) -> None:
        """Open destination folder in file explorer."""
        dest = self._dest_var.get()
        if dest and Path(dest).exists():
            import subprocess
            import sys
            if sys.platform == "win32":
                subprocess.run(["explorer", dest], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", dest], check=False)
            else:
                subprocess.run(["xdg-open", dest], check=False)
        else:
            messagebox.showwarning("Warning", "Destination folder does not exist.")

    def _copy_paths(self) -> None:
        """Copy output paths to clipboard."""
        selected = self._files_table.get_selected_items()
        if not selected:
            paths = [f.output_path for f in self._files]
        else:
            indices = set()
            for row in selected:
                try:
                    indices.add(int(row.values.get("idx", -1)))
                except (ValueError, TypeError):
                    pass
            paths = [f.output_path for f in self._files if f.idx in indices]

        if paths:
            self.clipboard_clear()
            self.clipboard_append("\n".join(paths))
            messagebox.showinfo("Info", f"Copied {len(paths)} path(s) to clipboard.")

    def _export_selected(self) -> None:
        """Export only selected files."""
        selected = self._files_table.get_selected_items()
        if not selected:
            messagebox.showinfo("Info", "No files selected.")
            return

        indices = set()
        for row in selected:
            try:
                indices.add(int(row.values.get("idx", -1)))
            except (ValueError, TypeError):
                pass

        files_to_export = [f for f in self._files if f.idx in indices]
        self._run_export(files_to_export)

    def _export_all(self) -> None:
        """Export all files."""
        if not self._files:
            messagebox.showinfo("Info", "No files to export.")
            return

        if not self._dest_var.get():
            messagebox.showwarning("Warning", "Please select a destination folder.")
            return

        self._run_export(self._files)

    def _run_export(self, files: List[OutputFile]) -> None:
        """Run export operation in background thread."""
        if self._status == ExportStatus.RUNNING:
            messagebox.showinfo("Info", "Export is already running.")
            return

        # Pre-export dirty flag check (Task 47.5)
        if self._manifest_manager:
            try:
                flags = self._manifest_manager.get_dirty_flags()
                dirty_names = [
                    name for name, dirty in flags.items() if dirty
                ]
                if dirty_names:
                    msg = (
                        f"Pipeline stages need re-running: {', '.join(dirty_names)}.\n\n"
                        "Export anyway?"
                    )
                    if not messagebox.askokcancel("Dirty Flags", msg):
                        return
            except Exception:
                pass

        self._status = ExportStatus.RUNNING
        self._cancel_requested = False
        self._status_label.configure(text="Exporting...")
        self._export_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")

        self._stats = ExportStats(
            total_files=len(files),
            start_time=time.time(),
        )

        def run_export() -> None:
            # Phase 48: Write output step log
            _out_log = None
            import time as _time
            _out_start = _time.perf_counter()
            try:
                from CherryAI.functions.mainhelper import (
                    _rotate_log, write_step_log_header,
                    write_step_log_footer,
                )
                mm = self._manifest_manager
                if mm:
                    pdir = getattr(mm, "_project_dir", None)
                    pname = (
                        mm.get_project_info().project_name
                        if hasattr(mm, "get_project_info") else None
                    )
                    if pdir and pname:
                        from pathlib import Path as _P
                        _out_log = _rotate_log(
                            _P(str(pdir)), pname, "output",
                        )
                        write_step_log_header(_out_log, {
                            "CherryAI Output Log": "",
                            "Started": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "Total Files": str(len(files)),
                            "Naming Strategy": self._naming_var.get(),
                        })
            except Exception:
                pass

            try:
                self._process_export(files)
                self._stats.end_time = time.time()
                self._status = ExportStatus.COMPLETED
                # Phase 48: Footer
                try:
                    if _out_log:
                        dur = _time.perf_counter() - _out_start
                        write_step_log_footer(_out_log, {
                            "Output Summary": "",
                            "Completed": _time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ",
                            ),
                            "Duration": f"{dur:.2f}s",
                            "Files Written": str(
                                self._stats.files_written,
                            ),
                            "Files Failed": str(
                                self._stats.files_failed,
                            ),
                        })
                except Exception:
                    pass
                self.after(0, self._on_export_complete)
            except Exception as e:
                logger.exception("Export failed")
                self._status = ExportStatus.FAILED
                self.after(0, lambda: self._on_export_error(str(e)))

        self._export_thread = threading.Thread(target=run_export, daemon=True)
        self._export_thread.start()

    def _process_export(self, files: List[OutputFile]) -> None:
        """Process the export operation."""
        dest_base = Path(self._dest_var.get())
        dest_base.mkdir(parents=True, exist_ok=True)

        for i, output_file in enumerate(files):
            if self._cancel_requested:
                break

            try:
                self._write_file(output_file, dest_base)
                output_file.status = "written"
                output_file.written = True
                self._stats.files_written += 1
            except Exception as e:
                output_file.status = "failed"
                output_file.error = str(e)
                self._stats.files_failed += 1
                self._stats.failure_log.append({
                    "file": output_file.output_path,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })
                logger.error(f"Failed to write {output_file.output_path}: {e}")

            # Update progress
            progress = ((i + 1) / len(files)) * 100
            self.after(0, lambda p=progress: self._progress_var.set(p))  # type: ignore[misc]
            self.after(0, self._refresh_table)

        # Export manifest if requested
        if self._export_manifest_var.get() and not self._cancel_requested:
            self._export_manifest(dest_base)

        # Export logs if requested
        if self._export_logs_var.get() and not self._cancel_requested:
            self._export_logs(dest_base)

    def _write_file(self, output_file: OutputFile, dest_base: Path) -> None:
        """Write a single output file."""
        output_path = Path(output_file.output_path)

        # Create backup if needed
        if output_path.exists() and not self._overwrite_var.get():
            backup_strategy = BackupStrategy(self._backup_var.get())
            if backup_strategy != BackupStrategy.NONE:
                backup_path = self._create_backup(output_path, backup_strategy)
                output_file.backup_path = str(backup_path)

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get lines from session
        step_data = self.get_step_data()
        lines = step_data.get("lines", [])

        # Write based on format
        format_val = OutputFormat(self._format_var.get().lower())
        encoding = self._encoding_var.get()

        if format_val == OutputFormat.TXT:
            self._write_txt(output_path, lines, encoding)
        elif format_val == OutputFormat.CSV:
            self._write_csv(output_path, lines, encoding)
        elif format_val == OutputFormat.TSV:
            self._write_tsv(output_path, lines, encoding)
        elif format_val == OutputFormat.JSON:
            self._write_json(output_path, lines, encoding)
        elif format_val == OutputFormat.XLSX:
            self._write_xlsx(output_path, lines)

        output_file.line_count = len(lines)
        self._stats.total_lines += len(lines)

    def _write_txt(self, path: Path, lines: List[str], encoding: str) -> None:
        """Write lines as plain text."""
        with open(path, "w", encoding=encoding) as f:
            f.write("\n".join(lines))

    def _write_csv(self, path: Path, lines: List[str], encoding: str) -> None:
        """Write lines as CSV."""
        import csv
        with open(path, "w", encoding=encoding, newline="") as f:
            writer = csv.writer(f)
            for line in lines:
                writer.writerow([line])

    def _write_tsv(self, path: Path, lines: List[str], encoding: str) -> None:
        """Write lines as TSV."""
        with open(path, "w", encoding=encoding) as f:
            for line in lines:
                f.write(f"{line}\n")

    def _write_json(self, path: Path, lines: List[str], encoding: str) -> None:
        """Write lines as JSON array."""
        import json
        with open(path, "w", encoding=encoding) as f:
            json.dump(lines, f, ensure_ascii=False, indent=2)

    def _write_xlsx(self, path: Path, lines: List[str]) -> None:
        """Write lines as Excel spreadsheet."""
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            if ws is None:
                ws = wb.create_sheet()
            for i, line in enumerate(lines, 1):
                ws.cell(row=i, column=1, value=line)
            wb.save(path)
        except ImportError:
            # Fallback to CSV if openpyxl not available
            self._write_csv(path.with_suffix(".csv"), lines, "utf-8")

    def _create_backup(self, path: Path, strategy: BackupStrategy) -> Path:
        """Create a backup of existing file."""
        if strategy == BackupStrategy.TIMESTAMP:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = path.with_suffix(f".{timestamp}{path.suffix}")
        elif strategy == BackupStrategy.NUMBERED:
            i = 1
            while True:
                backup_path = path.with_suffix(f".{i}{path.suffix}")
                if not backup_path.exists():
                    break
                i += 1
        else:  # EXTENSION
            ext = self._backup_ext_var.get() or ".bak"
            backup_path = path.with_suffix(path.suffix + ext)

        shutil.copy2(path, backup_path)
        return backup_path

    def _export_manifest(self, dest_base: Path) -> None:
        """Export manifest file."""
        manifest_path = dest_base / "manifest.json"
        step_data = self.get_step_data()

        try:
            import json
            manifest_data = {
                "exported_at": datetime.now().isoformat(),
                "files": [
                    {
                        "source": f.source_path,
                        "output": f.output_path,
                        "status": f.status,
                        "lines": f.line_count,
                    }
                    for f in self._files
                ],
                "options": {
                    "format": self._format_var.get(),
                    "encoding": self._encoding_var.get(),
                    "naming": self._naming_var.get(),
                },
                "stats": {
                    "total_files": self._stats.total_files,
                    "files_written": self._stats.files_written,
                    "total_lines": self._stats.total_lines,
                    "duration": self._stats.duration,
                },
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to export manifest: {e}")

    def _export_logs(self, dest_base: Path) -> None:
        """Export processing logs and step-specific log files."""
        log_path = dest_base / "export_log.txt"

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"CherryAI Export Log\n")
                f.write(f"{'=' * 50}\n")
                f.write(f"Exported at: {datetime.now().isoformat()}\n")
                f.write(f"Total files: {self._stats.total_files}\n")
                f.write(f"Written: {self._stats.files_written}\n")
                f.write(f"Failed: {self._stats.files_failed}\n")
                f.write(f"Duration: {self._stats.duration:.2f}s\n\n")

                for output_file in self._files:
                    status_icon = "✓" if output_file.written else "✗"
                    f.write(f"{status_icon} {output_file.source_filename}")
                    f.write(f" → {output_file.filename}\n")
                    if output_file.error:
                        f.write(f"  Error: {output_file.error}\n")
        except Exception as e:
            logger.error(f"Failed to export logs: {e}")

        # Phase 48: Also bundle per-project step logs
        try:
            mm = self._manifest_manager
            if mm:
                pdir = getattr(mm, "_project_dir", None)
                pname = (
                    mm.get_project_info().project_name
                    if hasattr(mm, "get_project_info") else None
                )
                if pdir and pname:
                    import glob
                    logs_dest = dest_base / "logs"
                    logs_dest.mkdir(parents=True, exist_ok=True)
                    project_dir = Path(str(pdir))
                    # Active + archived step logs
                    for pattern in [
                        f"{pname}.*.log",
                    ]:
                        for lf in project_dir.glob(pattern):
                            try:
                                import shutil
                                shutil.copy2(lf, logs_dest / lf.name)
                            except Exception:
                                pass
        except Exception:
            pass

    def _cancel_export(self) -> None:
        """Cancel the export operation."""
        self._cancel_requested = True
        self._status_label.configure(text="Cancelling...")

    def _on_export_complete(self) -> None:
        """Handle export completion."""
        self._status_label.configure(text="Completed")
        self._export_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._refresh_table()
        self._update_summary()

        # Show completion message
        msg = f"Export complete!\n\n"
        msg += f"Files written: {self._stats.files_written}\n"
        msg += f"Files failed: {self._stats.files_failed}\n"
        msg += f"Time: {self._stats.duration:.2f}s"
        messagebox.showinfo("Export Complete", msg)

    def _on_export_error(self, error: str) -> None:
        """Handle export error."""
        self._status_label.configure(text="Failed")
        self._export_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        messagebox.showerror("Error", f"Export failed: {error}")

    def _refresh_preview(self) -> None:
        """Refresh the output file preview."""
        self._build_file_list()
        self._refresh_table()

    def _build_file_list(self) -> None:
        """Build the list of output files from session data or manifest filedir.
        
        TASK 35.3: Uses filedir entries when available for accurate per-file
        output generation with preserved folder structure.
        """
        # Try to use filedir from manifest first (TASK 35.3)
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            filedir = mgr.get_filedir()
            if filedir:
                self._build_file_list_from_filedir(filedir)
                return
        
        # Fallback to session data (legacy behavior)
        self._build_file_list_from_session()
    
    def _build_file_list_from_filedir(
        self,
        filedir: List["FileDirEntry"],
    ) -> None:
        """Build output file list from filedir entries.
        
        TASK 35.3: Uses filedir for per-file output with accurate line counts
        and preserved folder structure.
        """
        from CherryAI.functions.manifest_manager import FileDirEntry
        
        # Get output options
        strategy = _safe_naming_strategy(self._naming_var.get())
        value = self._naming_value_var.get()
        dest_base = self._dest_var.get() or ""
        format_ext = FORMAT_EXTENSIONS.get(
            OutputFormat(self._format_var.get().lower()),
            ".txt"
        )
        
        # If no destination set, use Patch/ directory
        mgr = self.manifest_manager
        if not dest_base and mgr is not None and mgr.is_loaded:
            dest_base = str(mgr.get_patch_dir())
        
        self._files = []
        
        for i, entry in enumerate(filedir):
            # Preserve folder structure from rel_path
            rel_path = Path(entry.rel_path)
            stem = rel_path.stem
            parent = rel_path.parent
            
            # Generate output name
            output_name = self._generate_output_name(rel_path, strategy, value, format_ext)
            
            # Build full output path preserving structure
            if self._preserve_var.get() and parent != Path("."):
                if strategy == NamingStrategy.SUBFOLDER and dest_base:
                    output_path = Path(dest_base) / value / parent / output_name
                elif dest_base:
                    output_path = Path(dest_base) / parent / output_name
                else:
                    output_path = parent / output_name
            else:
                if strategy == NamingStrategy.SUBFOLDER and dest_base:
                    output_path = Path(dest_base) / value / output_name
                elif dest_base:
                    output_path = Path(dest_base) / output_name
                else:
                    output_path = Path(output_name)
            
            self._files.append(OutputFile(
                idx=i,
                source_path=str(mgr.resolve_file_path(entry.rel_path)) if mgr else entry.rel_path,
                output_path=str(output_path),
                format=OutputFormat(self._format_var.get().lower()),
                line_count=entry.line_count,
            ))
    
    def _build_file_list_from_session(self) -> None:
        """Build output file list from session data (legacy method)."""
        step_data = self.get_step_data()
        source_files = step_data.get("source_files", [])
        lines = step_data.get("lines", [])

        # Get naming options
        strategy = _safe_naming_strategy(self._naming_var.get())
        value = self._naming_value_var.get()
        dest_base = self._dest_var.get() or ""
        format_ext = FORMAT_EXTENSIONS.get(
            OutputFormat(self._format_var.get().lower()),
            ".txt"
        )

        self._files = []

        if not source_files:
            # Create a single output file if no source files
            if lines:
                output_name = f"output{value if strategy == NamingStrategy.SUFFIX else ''}{format_ext}"
                output_path = str(Path(dest_base) / output_name) if dest_base else output_name

                self._files.append(OutputFile(
                    idx=0,
                    source_path="",
                    output_path=output_path,
                    format=OutputFormat(self._format_var.get().lower()),
                    line_count=len(lines),
                ))
            return

        for i, source_path in enumerate(source_files):
            source = Path(source_path)
            output_name = self._generate_output_name(source, strategy, value, format_ext)

            if strategy == NamingStrategy.SUBFOLDER and dest_base:
                output_path = str(Path(dest_base) / value / output_name)
            elif dest_base:
                output_path = str(Path(dest_base) / output_name)
            else:
                output_path = output_name

            self._files.append(OutputFile(
                idx=i,
                source_path=source_path,
                output_path=output_path,
                format=OutputFormat(self._format_var.get().lower()),
                line_count=len(lines) // max(1, len(source_files)),
            ))

    def _generate_output_name(
        self,
        source: Path,
        strategy: NamingStrategy,
        value: str,
        format_ext: str,
    ) -> str:
        """Generate output filename based on naming strategy."""
        stem = source.stem

        if strategy == NamingStrategy.SUFFIX:
            return f"{stem}{value}{format_ext}"
        elif strategy == NamingStrategy.PREFIX:
            return f"{value}{stem}{format_ext}"
        elif strategy == NamingStrategy.REPLACE:
            return f"{stem.replace(source.suffix, '')}{value}{format_ext}"
        else:  # SUBFOLDER
            return f"{stem}{format_ext}"

    # =========================================================================
    # UI Updates
    # =========================================================================

    def _refresh_table(self, filter_val: str = "all") -> None:
        """Refresh the files table with current data."""
        rows: List[TableRow] = []

        for output_file in self._files:
            # Apply filter
            if filter_val == "pending" and output_file.status != "pending":
                continue
            elif filter_val == "written" and not output_file.written:
                continue
            elif filter_val == "failed" and output_file.status != "failed":
                continue

            # Status icon
            if output_file.written:
                status = "✓ Written"
            elif output_file.status == "failed":
                status = "✗ Failed"
            else:
                status = "○ Pending"

            row = TableRow(
                id=output_file.idx,
                values={
                    "idx": str(output_file.idx),
                    "status": status,
                    "source": output_file.source_filename,
                    "output": output_file.filename,
                    "format": output_file.format.value.upper(),
                    "lines": str(output_file.line_count),
                },
            )
            rows.append(row)

        self._files_table.load_data(rows)

    def _update_summary(self) -> None:
        """Update summary display."""
        self._stats_labels["total"].configure(text=str(self._stats.total_files))
        self._stats_labels["written"].configure(text=str(self._stats.files_written))
        self._stats_labels["failed"].configure(text=str(self._stats.files_failed))
        self._stats_labels["lines"].configure(text=str(self._stats.total_lines))
        self._stats_labels["time"].configure(text=f"{self._stats.duration:.1f}s")

        # Update dirty flag indicators (Task 47.10)
        self._update_dirty_flags()

    def _update_dirty_flags(self) -> None:
        """Update dirty flag indicator labels from manifest."""
        if not self._manifest_manager:
            return
        try:
            flags = self._manifest_manager.get_dirty_flags()
            if flags.get("process", False):
                self._process_flag_label.configure(
                    text="⚠ Process", foreground=THEME.accent_warning,
                )
            else:
                self._process_flag_label.configure(
                    text="✓ Process", foreground=THEME.accent_success,
                )
            if flags.get("wordwrap", False):
                self._wordwrap_flag_label.configure(
                    text="⚠ Wordwrap", foreground=THEME.accent_warning,
                )
            else:
                self._wordwrap_flag_label.configure(
                    text="✓ Wordwrap", foreground=THEME.accent_success,
                )
        except Exception:
            pass

    # =========================================================================
    # Manifest Integration Methods (TASK 28.2)
    # =========================================================================

    def _save_file_naming_to_manifest(self, *args: Any) -> None:
        """Save FileNaming radio button value to manifest."""
        if self._manifest_manager:
            value = self._naming_var.get()
            save_nested_text_field(
                self._manifest_manager,
                "OutputFormat",
                "FileNaming",
                value,
            )

    def _load_output_settings_from_manifest(self) -> None:
        """Load output format settings from manifest on tab entry."""
        if not self._manifest_manager:
            return

        try:
            output_format = self._manifest_manager.get_output_options()

            # Load PreserveFolderStructure
            if "PreserveFolderStructure" in output_format:
                self._preserve_var.set(output_format["PreserveFolderStructure"])

            # Load Format
            if "Format" in output_format:
                self._format_var.set(output_format["Format"])

            # Load PairMode
            if "PairMode" in output_format:
                self._pair_var.set(output_format["PairMode"])

            # Load Encoding
            if "Encoding" in output_format:
                self._encoding_var.set(output_format["Encoding"])

            # Load FileNaming
            if "FileNaming" in output_format:
                self._naming_var.set(output_format["FileNaming"])

            # Load TextOption
            if "TextOption" in output_format:
                self._naming_value_var.set(output_format["TextOption"])

            # Load OverwriteExistingFiles
            if "OverwriteExistingFiles" in output_format:
                self._overwrite_var.set(output_format["OverwriteExistingFiles"])

            # Load Backup
            if "Backup" in output_format:
                self._backup_var.set(output_format["Backup"])

            # Load BackupExtension
            if "BackupExtension" in output_format:
                self._backup_ext_var.set(output_format["BackupExtension"])

            # Load ExportManifestFile
            if "ExportManifestFile" in output_format:
                self._export_manifest_var.set(output_format["ExportManifestFile"])

            # Load ExportProcessingLogs
            if "ExportProcessingLogs" in output_format:
                self._export_logs_var.set(output_format["ExportProcessingLogs"])

            # Load ExportGlossaryEntries
            if "ExportGlossaryEntries" in output_format:
                self._export_glossary_var.set(output_format["ExportGlossaryEntries"])

            logger.debug("Loaded output format settings from manifest")
        except Exception as e:
            logger.warning(f"Failed to load output settings from manifest: {e}")

    # =========================================================================
    # BaseStep Implementation
    # =========================================================================

    def on_new_project(self) -> None:
        """Reset cached state for a fresh project."""
        super().on_new_project()
        self._files.clear()
        self._cancel_requested = False
        self._selected_file_idx = -1
        self._manifest_bindings.clear()
        logger.debug("Output step reset for new project")

    def on_enter(self) -> None:
        """Called when entering this tab."""
        # TASK 28.2: Load output settings from manifest
        self._load_output_settings_from_manifest()
        self._load_from_session()
        self._refresh_preview()
        self._update_summary()

    def on_leave(self) -> None:
        """Called when leaving this tab."""
        self._save_to_session()

    def _load_from_session(self) -> None:
        """Load data from session state.

        Populates ``step_data["lines"]`` from manifest using the full
        pipeline resolution so the latest processed text is available
        for export.
        """
        step_data = self.get_step_data()

        # Populate lines from manifest (latest processed text)
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            resolved = get_all_lines_resolved(mgr)
            if resolved:
                step_data["lines"] = resolved

        # Load destination if saved
        if "destination" in step_data:
            self._dest_var.set(step_data["destination"])

        # Load options if saved
        if "output_options" in step_data:
            opts = step_data["output_options"]
            self._format_var.set(opts.get("format", "txt"))
            self._encoding_var.set(opts.get("encoding", "utf-8"))
            self._naming_var.set(opts.get("naming", "suffix"))
            self._naming_value_var.set(opts.get("naming_value", "_translated"))

    def _save_to_session(self) -> None:
        """Save current state to session."""
        step_data = self.get_step_data()
        step_data["destination"] = self._dest_var.get()
        step_data["output_options"] = {
            "format": self._format_var.get(),
            "encoding": self._encoding_var.get(),
            "naming": self._naming_var.get(),
            "naming_value": self._naming_value_var.get(),
        }
        step_data["export_stats"] = {
            "total_files": self._stats.total_files,
            "files_written": self._stats.files_written,
            "files_failed": self._stats.files_failed,
            "total_lines": self._stats.total_lines,
            "duration": self._stats.duration,
        }
        self.set_step_data(step_data)

    # =========================================================================
    # Public API
    # =========================================================================

    def get_output_options(self) -> OutputOptions:
        """Get current output options.

        Returns:
            OutputOptions with current settings.
        """
        return OutputOptions(
            format=OutputFormat(self._format_var.get().lower()),
            destination=self._dest_var.get(),
            naming=NamingOptions(
                strategy=_safe_naming_strategy(self._naming_var.get()),
                suffix=self._naming_value_var.get() if self._naming_var.get() == "suffix" else "_translated",
                prefix=self._naming_value_var.get() if self._naming_var.get() == "prefix" else "translated_",
                subfolder=self._naming_value_var.get() if self._naming_var.get() == "subfolder" else "translated",
            ),
            backup=BackupOptions(
                strategy=BackupStrategy(self._backup_var.get()),
                extension=self._backup_ext_var.get(),
            ),
            overwrite=self._overwrite_var.get(),
            encoding=self._encoding_var.get(),
        )

    def get_files(self) -> List[OutputFile]:
        """Get all output files.

        Returns:
            List of OutputFile objects.
        """
        return list(self._files)

    def get_export_stats(self) -> ExportStats:
        """Get export statistics.

        Returns:
            ExportStats with current statistics.
        """
        return self._stats

    def get_manifest_options(self) -> ManifestExportOptions:
        """Get manifest export options.

        Returns:
            ManifestExportOptions with current settings.
        """
        return ManifestExportOptions(
            export_manifest=self._export_manifest_var.get(),
            export_logs=self._export_logs_var.get(),
            export_glossary=self._export_glossary_var.get(),
        )
