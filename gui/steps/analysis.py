"""CherryAI GUI v2 Analysis Step.

Second workflow tab for static analysis of loaded files.
Displays line counts, duplicates, language detection, and code patterns.

Uses gui/helpers/analysis_adapter.py for core analysis functions (TASK 16.6).
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import tkinter as tk
from tkinter import ttk

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.helpers.analysis_adapter import (
    analyze_lines,
    count_duplicates,
    detect_code_patterns,
    detect_language,
    detect_speakers_batch,
    summarize_lines,
)
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


class AnalysisStep(BaseStep):
    """Analysis step for static file analysis.

    Features:
    - Line counts (total, empty, unique)
    - Duplicate detection
    - Language detection
    - Code/pattern detection
    - Speaker/character detection
    - Export findings to CSV
    """

    step_id = 1
    step_name = "Analysis"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize Analysis step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables BEFORE super().__init__ since it calls _build_ui()
        self._analysis_results: Dict[str, Any] = {}
        self._is_analyzing = False
        super().__init__(parent, session, manifest_manager=manifest_manager)
        # NOTE: Do NOT call _build_ui() here - BaseStep.__init__() already calls it

    def _build_ui(self) -> None:
        """Build the step UI."""
        self._build_header()
        self._build_content()

    def _build_header(self) -> None:
        """Build the header section."""
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # Run Analysis button
        self._analyze_btn = ttk.Button(
            header,
            text="▶ Run Analysis",
            command=self._run_analysis,
        )
        self._analyze_btn.pack(side="right", padx=(5, 0))

        # Export button
        ttk.Button(
            header,
            text="Export",
            command=self._export_findings,
        ).pack(side="right")

    def _build_content(self) -> None:
        """Build the main content area."""
        # Main paned window
        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Stats panel
        left_frame = ttk.LabelFrame(content, text="Statistics")
        content.add(left_frame, weight=1)
        self._build_stats_panel(left_frame)

        # Right: Findings table
        right_frame = ttk.LabelFrame(content, text="Findings")
        content.add(right_frame, weight=2)
        self._build_findings_panel(right_frame)

    def _build_stats_panel(self, parent: ttk.LabelFrame) -> None:
        """Build the statistics panel."""
        # Canvas for scrolling
        canvas = tk.Canvas(parent, bg=THEME.bg_panel, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._stats_frame = scrollable

        # Placeholder before analysis
        self._placeholder_label = ttk.Label(
            scrollable,
            text="Click 'Run Analysis' to analyze loaded files.",
            foreground=THEME.text_secondary,
        )
        self._placeholder_label.pack(pady=20, padx=10)

    def _build_findings_panel(self, parent: ttk.LabelFrame) -> None:
        """Build the findings table panel."""
        # Define columns for findings
        columns = [
            ColumnDef(key="category", title="Category", width=120),
            ColumnDef(key="item", title="Item", width=200, stretch=True),
            ColumnDef(key="count", title="Count", width=80, anchor="e"),
            ColumnDef(key="details", title="Details", width=200, stretch=True),
        ]

        self._findings_table = SharedTable(
            parent,
            columns=columns,
            show_filter=True,
            show_checkboxes=False,
        )
        self._findings_table.pack(fill="both", expand=True)

    def _run_analysis(self) -> None:
        """Run analysis on loaded files."""
        if self._is_analyzing:
            return

        # Get loaded files from session
        loaded_files = self._get_loaded_files()
        if not loaded_files:
            messagebox.showwarning(
                "No Files",
                "Please load files in the Input & Extraction step first.",
            )
            return

        self._is_analyzing = True
        self._analyze_btn.configure(state="disabled", text="Analyzing...")

        # Run in background thread
        thread = threading.Thread(target=self._analyze_files, args=(loaded_files,))
        thread.daemon = True
        thread.start()

    def _get_loaded_files(self) -> List[Any]:
        """Get loaded files from input step.

        Returns:
            List of LoadedFile objects from the Input & Extraction step.
        """
        # Try to get from input step through app
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "_step_tabs") and len(app._step_tabs) > 0:
                input_step = app._step_tabs[0]
                if hasattr(input_step, "get_loaded_files"):
                    loaded_files = input_step.get_loaded_files()
                    if loaded_files:
                        return loaded_files
        except Exception as e:
            logger.debug("Could not get loaded files from input step: %s", e)

        # Fallback: reconstruct from step data if stored there
        input_step_data = self.session.get_step(0).data
        if "all_lines" in input_step_data:
            # Create a simple wrapper with lines
            class _LineWrapper:
                def __init__(self, lines: List[str]) -> None:
                    self.lines = lines

            return [_LineWrapper(input_step_data["all_lines"])]

        return []

    def _analyze_files(self, loaded_files: List[Any]) -> None:
        """Analyze files in background thread.

        Args:
            loaded_files: List of LoadedFile objects.
        """
        try:
            results = self._perform_analysis(loaded_files)
            self._analysis_results = results

            # Update UI in main thread
            self.after(0, self._display_results)
        except Exception as e:
            logger.error("Analysis failed: %s", e)
            self.after(0, lambda: self._show_error(str(e)))
        finally:
            self._is_analyzing = False
            self.after(0, lambda: self._analyze_btn.configure(
                state="normal", text="▶ Run Analysis"
            ))

    def _perform_analysis(self, loaded_files: List[Any]) -> Dict[str, Any]:
        """Perform the actual analysis.

        Args:
            loaded_files: List of LoadedFile objects.

        Returns:
            Analysis results dictionary.
        """
        results: Dict[str, Any] = {
            "file_count": len(loaded_files),
            "total_lines": 0,
            "empty_lines": 0,
            "unique_lines": 0,
            "duplicate_count": 0,
            "duplicates": {},
            "languages": {},
            "speakers": {},
            "code_patterns": {},
            "findings": [],
        }

        all_lines: List[str] = []

        # Collect all lines
        for lf in loaded_files:
            if hasattr(lf, "lines"):
                all_lines.extend(lf.lines)

        results["total_lines"] = len(all_lines)

        # Use analysis adapter for comprehensive analysis (TASK 16.6)
        analysis = analyze_lines(
            all_lines,
            include_speakers=True,
            include_code_patterns=True,
            include_language=True,
            include_tokens=False,
        )

        # Map adapter results to GUI format
        summary = analysis.get("summary", {})
        results["empty_lines"] = summary.get("empty_lines", 0)
        results["unique_lines"] = summary.get("unique_lines", 0)
        results["duplicate_count"] = summary.get("duplicate_lines", 0)

        # Get detailed results from adapter
        results["languages"] = analysis.get("languages", {})
        results["speakers"] = analysis.get("speakers", {})
        results["code_patterns"] = analysis.get("code_patterns", {})
        results["duplicates"] = analysis.get("duplicates", {})

        # Build findings list
        results["findings"] = self._build_findings(results)

        return results

    # NOTE: _detect_language() and _detect_code_patterns() removed in TASK 16.6
    # These functions are now provided by gui.helpers.analysis_adapter

    def _build_findings(self, results: Dict[str, Any]) -> List[TableRow]:
        """Build findings table rows from results.

        Args:
            results: Analysis results.

        Returns:
            List of TableRow objects.
        """
        findings: List[TableRow] = []
        row_id = 1

        # Basic stats as findings
        findings.append(TableRow(
            id=row_id,
            values={
                "category": "Overview",
                "item": "Total Files",
                "count": results["file_count"],
                "details": "",
            },
        ))
        row_id += 1

        findings.append(TableRow(
            id=row_id,
            values={
                "category": "Overview",
                "item": "Total Lines",
                "count": results["total_lines"],
                "details": "",
            },
        ))
        row_id += 1

        findings.append(TableRow(
            id=row_id,
            values={
                "category": "Overview",
                "item": "Empty Lines",
                "count": results["empty_lines"],
                "details": f"{results['empty_lines'] / max(1, results['total_lines']) * 100:.1f}%",
            },
        ))
        row_id += 1

        findings.append(TableRow(
            id=row_id,
            values={
                "category": "Overview",
                "item": "Unique Lines",
                "count": results["unique_lines"],
                "details": "",
            },
        ))
        row_id += 1

        findings.append(TableRow(
            id=row_id,
            values={
                "category": "Duplicates",
                "item": "Duplicate Lines",
                "count": results["duplicate_count"],
                "details": f"{results['duplicate_count'] / max(1, results['total_lines']) * 100:.1f}%",
            },
            tags=["warning"] if results["duplicate_count"] > 100 else [],
        ))
        row_id += 1

        # Languages
        for lang, count in sorted(results["languages"].items(), key=lambda x: x[1], reverse=True):
            pct = count / max(1, results["total_lines"]) * 100
            findings.append(TableRow(
                id=row_id,
                values={
                    "category": "Language",
                    "item": lang,
                    "count": count,
                    "details": f"{pct:.1f}% of lines",
                },
            ))
            row_id += 1

        # Speakers (top 20)
        speakers_sorted = sorted(results["speakers"].items(), key=lambda x: x[1], reverse=True)[:20]
        for speaker, count in speakers_sorted:
            findings.append(TableRow(
                id=row_id,
                values={
                    "category": "Speakers",
                    "item": speaker,
                    "count": count,
                    "details": "",
                },
            ))
            row_id += 1

        # Code patterns
        for pattern_type, count in sorted(results["code_patterns"].items(), key=lambda x: x[1], reverse=True):
            findings.append(TableRow(
                id=row_id,
                values={
                    "category": "Code Patterns",
                    "item": pattern_type,
                    "count": count,
                    "details": "",
                },
            ))
            row_id += 1

        # Top duplicates
        for line, count in list(results["duplicates"].items())[:10]:
            display_line = line[:50] + "..." if len(line) > 50 else line
            findings.append(TableRow(
                id=row_id,
                values={
                    "category": "Top Duplicates",
                    "item": display_line,
                    "count": count,
                    "details": f"{count}x",
                },
            ))
            row_id += 1

        return findings

    def _display_results(self) -> None:
        """Display analysis results in UI."""
        # Clear placeholder
        self._placeholder_label.pack_forget()

        # Clear existing stats
        for widget in self._stats_frame.winfo_children():
            widget.destroy()

        results = self._analysis_results

        # Display summary stats
        stats = [
            ("Files Analyzed", results.get("file_count", 0)),
            ("Total Lines", results.get("total_lines", 0)),
            ("Empty Lines", results.get("empty_lines", 0)),
            ("Unique Lines", results.get("unique_lines", 0)),
            ("Duplicate Lines", results.get("duplicate_count", 0)),
        ]

        for label, value in stats:
            frame = ttk.Frame(self._stats_frame)
            frame.pack(fill="x", padx=10, pady=3)

            ttk.Label(
                frame,
                text=label + ":",
                font=("Segoe UI", 10),
                foreground=THEME.text_secondary,
            ).pack(side="left")

            ttk.Label(
                frame,
                text=str(value),
                font=("Segoe UI", 10, "bold"),
                foreground=THEME.text_primary,
            ).pack(side="right")

        # Separator
        ttk.Separator(self._stats_frame, orient="horizontal").pack(
            fill="x", padx=10, pady=10
        )

        # Language breakdown
        if results.get("languages"):
            ttk.Label(
                self._stats_frame,
                text="Language Detection:",
                font=("Segoe UI", 10, "bold"),
                foreground=THEME.text_primary,
            ).pack(anchor="w", padx=10, pady=(5, 2))

            for lang, count in sorted(
                results["languages"].items(), key=lambda x: x[1], reverse=True
            )[:5]:
                pct = count / max(1, results["total_lines"]) * 100
                frame = ttk.Frame(self._stats_frame)
                frame.pack(fill="x", padx=20, pady=1)

                ttk.Label(
                    frame,
                    text=lang,
                    foreground=THEME.text_secondary,
                ).pack(side="left")

                ttk.Label(
                    frame,
                    text=f"{pct:.1f}%",
                    foreground=THEME.text_primary,
                ).pack(side="right")

        # Speaker count
        if results.get("speakers"):
            ttk.Separator(self._stats_frame, orient="horizontal").pack(
                fill="x", padx=10, pady=10
            )

            ttk.Label(
                self._stats_frame,
                text=f"Speakers Detected: {len(results['speakers'])}",
                font=("Segoe UI", 10, "bold"),
                foreground=THEME.text_primary,
            ).pack(anchor="w", padx=10, pady=(5, 2))

        # Code patterns
        if results.get("code_patterns"):
            ttk.Separator(self._stats_frame, orient="horizontal").pack(
                fill="x", padx=10, pady=10
            )

            ttk.Label(
                self._stats_frame,
                text="Code Patterns Found:",
                font=("Segoe UI", 10, "bold"),
                foreground=THEME.text_primary,
            ).pack(anchor="w", padx=10, pady=(5, 2))

            for pattern, count in sorted(
                results["code_patterns"].items(), key=lambda x: x[1], reverse=True
            ):
                frame = ttk.Frame(self._stats_frame)
                frame.pack(fill="x", padx=20, pady=1)

                ttk.Label(
                    frame,
                    text=pattern,
                    foreground=THEME.text_secondary,
                ).pack(side="left")

                ttk.Label(
                    frame,
                    text=str(count),
                    foreground=THEME.accent_info,
                ).pack(side="right")

        # Update findings table
        self._findings_table.set_data(results.get("findings", []))

    def _show_error(self, message: str) -> None:
        """Show error message.

        Args:
            message: Error message.
        """
        messagebox.showerror("Analysis Error", f"Analysis failed:\n{message}")

    def _export_findings(self) -> None:
        """Export findings to CSV."""
        if not self._analysis_results.get("findings"):
            messagebox.showwarning("No Data", "Run analysis first before exporting.")
            return

        # Use the table's export function
        self._findings_table._export_csv()

    def get_analysis_results(self) -> Dict[str, Any]:
        """Get the current analysis results.

        Returns:
            Analysis results dictionary.
        """
        return self._analysis_results.copy()

    def has_results(self) -> bool:
        """Check if analysis has been run.

        Returns:
            True if results are available.
        """
        return bool(self._analysis_results)

    def _deserialize_findings(self, findings: List[Any]) -> List[TableRow]:
        """Deserialize findings from session storage back to TableRow objects.

        Args:
            findings: List of findings (may be dicts from JSON or TableRow objects).

        Returns:
            List of TableRow objects.
        """
        result = []
        for item in findings:
            if isinstance(item, TableRow):
                result.append(item)
            elif isinstance(item, dict):
                # Reconstruct TableRow from serialized dict
                result.append(TableRow.from_dict(item))
            else:
                logger.warning("Unexpected finding type: %s", type(item))
        return result

    def on_enter(self) -> None:
        """Called when the step tab is selected.

        Refreshes the analysis if files have changed.
        Restores analysis results from session if available.
        """
        # First, try to restore analysis results from session
        step_data = self.get_step_data()
        if step_data.get("analysis_results") and not self._analysis_results:
            self._analysis_results = step_data["analysis_results"]
            # TASK 18.5: Deserialize findings from session storage
            # When saved to JSON, TableRow objects become dicts; need to convert back
            if "findings" in self._analysis_results:
                self._analysis_results["findings"] = self._deserialize_findings(
                    self._analysis_results["findings"]
                )
            self._display_results()
            logger.debug("Restored analysis results from session")
            return

        # Auto-run analysis if files are loaded and no results yet
        if not self._analysis_results:
            loaded_files = self._get_loaded_files()
            if loaded_files and not self._is_analyzing:
                # Optionally auto-run analysis
                pass

    def on_leave(self) -> None:
        """Called when leaving this step tab.

        Saves analysis results to session state.
        """
        if self._analysis_results:
            self.set_step_data({"analysis_results": self._analysis_results})
