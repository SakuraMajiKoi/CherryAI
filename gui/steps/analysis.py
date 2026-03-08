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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
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

# TASK 59.2: Import aggressive dedup projection calculator
from CherryAI.functions.analysis import calculate_aggressive_dedup_projection

# TASK 25.1: Import manifest field helpers for saving analysis counts
from CherryAI.functions.manifest_fields import (
    save_int_field,
    load_int_field,
    save_code_glossary,
    load_code_glossary,
    save_character_notes,
    load_character_notes,
    save_custom_placeholders,
    load_custom_placeholders,
    save_glossary_entries,
    load_glossary_entries,
)


if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


def _sanitize_translation(text: str) -> str:
    """Sanitize a translation value for safe TSV storage.

    Replaces tab characters with spaces and literal newlines with ``/n``.
    """
    return text.replace("\t", " ").replace("\r\n", "/n").replace("\n", "/n")


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
        self._instance_rows: Dict[int, List[TableRow]] = {}
        self._expanded_parents: set = set()
        self._findings_rows: List[TableRow] = []
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

        # Translate Terms button
        ttk.Button(
            header,
            text="Translate Terms",
            command=self._translate_terms,
        ).pack(side="right", padx=(5, 0))

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

        # TASK 59.3: Add right-click context menu binding
        self._findings_table._tree.bind("<Button-3>", self._on_findings_right_click)

        # Double-click to toggle instance expansion
        self._findings_table._tree.bind("<Double-1>", self._on_findings_toggle)

        # Initialize context menus
        self._speaker_menu: Optional[tk.Menu] = None
        self._code_pattern_menu: Optional[tk.Menu] = None
        self._generic_menu: Optional[tk.Menu] = None

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

        # Fallback: reconstruct from manifest lines[].orig
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            orig_lines = mgr.get_all_orig_lines()
            if orig_lines:
                class _LineWrapper:
                    def __init__(self, lines: List[str]) -> None:
                        self.lines = lines

                return [_LineWrapper(orig_lines)]

        # Legacy fallback: step_data all_lines (pre-migration sessions)
        input_step_data = self.session.get_step(0).data
        if "all_lines" in input_step_data:
            class _LineWrapper:  # type: ignore[no-redef]
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
            "characters": [],
            "speaker_count": 0,
            "code_patterns": [],
            "category_counts": {},
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

        # TASK 59.2: Calculate aggressive dedup projection
        results["aggressive_dedup"] = calculate_aggressive_dedup_projection(all_lines)

        # Get detailed results from adapter
        results["languages"] = analysis.get("languages", {})
        results["duplicates"] = analysis.get("duplicates", {})

        # Unified speakers: merge adapter speakers into manifest characters[]
        detected_speakers = analysis.get("speakers", {})
        existing_chars = self._load_characters()
        char_lookup = {c["original_name"]: c for c in existing_chars}

        unified_chars: List[Dict[str, Any]] = []
        for speaker_name, speaker_count in detected_speakers.items():
            existing = char_lookup.pop(speaker_name, None)
            if existing:
                existing["count"] = speaker_count
                unified_chars.append(existing)
            else:
                unified_chars.append({
                    "original_name": speaker_name,
                    "translation": "",
                    "notes": "",
                    "count": speaker_count,
                })

        # Keep user-added characters that weren't detected this run
        for remaining in char_lookup.values():
            remaining["count"] = 0
            unified_chars.append(remaining)

        self._save_characters(unified_chars)
        results["characters"] = unified_chars
        results["speaker_count"] = len(detected_speakers)

        # Build collapsed speakers list for manifest analysis entry
        go = getattr(self.session, "global_options", None)
        threshold = 10
        if go is not None:
            threshold = getattr(
                getattr(go, "utility", None), "speaker_threshold", 10
            )
        collapsed_names = [
            c["original_name"].replace(",", "\uFF0C")
            for c in unified_chars
            if c.get("count", 0) > 0
            and c.get("count", 0) < threshold
            and c.get("original_name")
        ]
        results["collapsed_speakers"] = ", ".join(collapsed_names)

        # Unified code_patterns: merge adapter individual_codes into manifest
        # code_patterns list, preserving user edits (translation, action, etc.)
        individual_codes = analysis.get("individual_codes", {})
        category_counts = analysis.get("code_patterns", {})
        existing_patterns = self._load_code_patterns()
        pattern_lookup = {p["pattern"]: p for p in existing_patterns}

        unified: List[Dict[str, Any]] = []
        for code_key, code_info in individual_codes.items():
            inst_map = code_info.get("instances", {})
            existing = pattern_lookup.pop(code_key, None)
            if existing:
                existing["count"] = code_info["count"]
                existing["raw_type"] = code_info.get("raw_type", "")
                existing["instances"] = list(inst_map.keys())
                existing["instance_counts"] = list(inst_map.values())
                if not existing.get("category"):
                    existing["category"] = code_info.get("type", "")
                unified.append(existing)
            else:
                unified.append({
                    "pattern": code_key,
                    "count": code_info["count"],
                    "category": code_info.get("type", ""),
                    "raw_type": code_info.get("raw_type", ""),
                    "instances": list(inst_map.keys()),
                    "instance_counts": list(inst_map.values()),
                    "action": "preserve",
                    "translation": "",
                    "example": "",
                    "notes": "",
                    "visible": True,
                    "spacing": "preserve",
                })

        # Keep user-added patterns that weren't detected this run
        for remaining in pattern_lookup.values():
            remaining["count"] = 0
            unified.append(remaining)

        self._save_code_patterns(unified)
        results["code_patterns"] = unified
        results["category_counts"] = category_counts

        # Build findings list
        results["findings"] = self._build_findings(results)

        return results

    # NOTE: _detect_language() and _detect_code_patterns() removed in TASK 16.6
    # These functions are now provided by gui.helpers.analysis_adapter

    def _build_findings(self, results: Dict[str, Any]) -> List[TableRow]:
        """Build findings table rows from results.

        Shows ALL speakers and individual code patterns, ordered by count
        descending. Details column is populated with sample lines for speakers
        and type classification for code patterns.

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

        # ALL Speakers from unified characters[], ordered by count descending
        # Speakers below threshold are collapsed into a single expandable row
        characters = results.get("characters", [])
        self._instance_rows.clear()
        self._expanded_parents.clear()
        go = getattr(self.session, "global_options", None)
        threshold = 10
        if go is not None:
            threshold = getattr(
                getattr(go, "utility", None), "speaker_threshold", 10
            )

        if isinstance(characters, list) and characters:
            chars_sorted = sorted(
                characters, key=lambda x: x.get("count", 0), reverse=True
            )
            above: list = []
            below: list = []
            for char in chars_sorted:
                name = char.get("original_name", "")
                count = char.get("count", 0)
                if not name or count == 0:
                    continue
                if count >= threshold:
                    above.append((name, count))
                else:
                    below.append((name, count))

            for name, count in above:
                details = self._get_character_details(name)
                findings.append(TableRow(
                    id=row_id,
                    values={
                        "category": "Speakers",
                        "item": name,
                        "count": count,
                        "details": details,
                    },
                ))
                row_id += 1

            if below:
                parent_id = row_id
                findings.append(TableRow(
                    id=parent_id,
                    values={
                        "category": "Speakers",
                        "item": f"[+] {len(below)} Speakers",
                        "count": threshold,
                        "details": f"below {threshold} occurrences",
                    },
                    meta={"expandable": True},
                ))
                children = []
                for i, (name, count) in enumerate(below):
                    details = self._get_character_details(name)
                    children.append(TableRow(
                        id=10000 + parent_id * 100 + i,
                        values={
                            "category": "",
                            "item": f"    {name}",
                            "count": count,
                            "details": details,
                        },
                        tags=["instance"],
                    ))
                self._instance_rows[parent_id] = children
                row_id += 1
        elif isinstance(characters, dict):
            # Legacy fallback: speakers dict (name→count)
            speakers_sorted = sorted(
                characters.items(), key=lambda x: x[1], reverse=True
            )
            above_legacy: list = []
            below_legacy: list = []
            for speaker, count in speakers_sorted:
                if count >= threshold:
                    above_legacy.append((speaker, count))
                else:
                    below_legacy.append((speaker, count))

            for speaker, count in above_legacy:
                details = self._get_character_details(speaker)
                findings.append(TableRow(
                    id=row_id,
                    values={
                        "category": "Speakers",
                        "item": speaker,
                        "count": count,
                        "details": details,
                    },
                ))
                row_id += 1

            if below_legacy:
                parent_id = row_id
                findings.append(TableRow(
                    id=parent_id,
                    values={
                        "category": "Speakers",
                        "item": f"[+] {len(below_legacy)} Speakers",
                        "count": threshold,
                        "details": f"below {threshold} occurrences",
                    },
                    meta={"expandable": True},
                ))
                children = []
                for i, (speaker, count) in enumerate(below_legacy):
                    details = self._get_character_details(speaker)
                    children.append(TableRow(
                        id=10000 + parent_id * 100 + i,
                        values={
                            "category": "",
                            "item": f"    {speaker}",
                            "count": count,
                            "details": details,
                        },
                        tags=["instance"],
                    ))
                self._instance_rows[parent_id] = children
                row_id += 1

        # Code patterns from unified code_patterns list, ordered by count
        # Patterns with instances sort before those without at equal count
        code_patterns = results.get("code_patterns", [])
        if isinstance(code_patterns, list) and code_patterns:
            codes_sorted = sorted(
                code_patterns,
                key=lambda x: (
                    x.get("count", 0),
                    1 if x.get("instances") else 0,
                ),
                reverse=True,
            )
            for entry in codes_sorted:
                pattern = entry.get("pattern", "")
                count = entry.get("count", 0)
                if not pattern or count == 0:
                    continue
                friendly_type = entry.get("category", "Unknown")
                instances = entry.get("instances", [])
                inst_counts = entry.get("instance_counts", [])
                has_instances = bool(instances)
                prefix = "[+] " if has_instances else ""
                findings.append(TableRow(
                    id=row_id,
                    values={
                        "category": "Code Patterns",
                        "item": prefix + pattern,
                        "count": count,
                        "details": friendly_type,
                    },
                    meta={
                        "raw_type": entry.get("raw_type", "UNKNOWN"),
                        "expandable": has_instances,
                    },
                ))
                if has_instances:
                    children = []
                    for i, inst in enumerate(instances):
                        child_count = (
                            inst_counts[i] if i < len(inst_counts) else 0
                        )
                        children.append(TableRow(
                            id=10000 + row_id * 100 + i,
                            values={
                                "category": "",
                                "item": f"    {inst}",
                                "count": child_count,
                                "details": "",
                            },
                            tags=["instance"],
                        ))
                    self._instance_rows[row_id] = children
                row_id += 1
        elif isinstance(code_patterns, dict):
            # Legacy fallback: grouped category→count dict
            for pattern_type, count in sorted(
                code_patterns.items(), key=lambda x: x[1], reverse=True
            ):
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

        # TASK 25.1: Save line counts to manifest for use in estimation
        self._save_line_counts_to_manifest(results)

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

        # TASK 59.2: Display aggressive dedup projection
        aggressive_dedup = results.get("aggressive_dedup", {})
        if aggressive_dedup and aggressive_dedup.get("original_count", 0) > 0:
            frame = ttk.Frame(self._stats_frame)
            frame.pack(fill="x", padx=10, pady=3)

            ttk.Label(
                frame,
                text="Aggressive Dedup:",
                font=("Segoe UI", 10),
                foreground=THEME.text_secondary,
            ).pack(side="left")

            unique = aggressive_dedup.get("unique_count", 0)
            reduction = aggressive_dedup.get("reduction_percent", 0.0)
            ttk.Label(
                frame,
                text=f"{unique:,} lines ({reduction:.1f}% reduction)",
                font=("Segoe UI", 10, "bold"),
                foreground=THEME.accent_info,
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
        if results.get("speaker_count"):
            ttk.Separator(self._stats_frame, orient="horizontal").pack(
                fill="x", padx=10, pady=10
            )

            ttk.Label(
                self._stats_frame,
                text=f"Speakers Detected: {results['speaker_count']}",
                font=("Segoe UI", 10, "bold"),
                foreground=THEME.text_primary,
            ).pack(anchor="w", padx=10, pady=(5, 2))

        # Code patterns (category summary)
        category_counts = results.get("category_counts", {})
        if category_counts:
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
                category_counts.items(), key=lambda x: x[1], reverse=True
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
        self._findings_rows = results.get("findings", [])
        self._refresh_findings_display()

    def _show_error(self, message: str) -> None:
        """Show error message.

        Args:
            message: Error message.
        """
        messagebox.showerror("Analysis Error", f"Analysis failed:\n{message}")

    def _refresh_findings_display(self) -> None:
        """Rebuild findings table rows incorporating expanded instances."""
        display: List[TableRow] = []
        for row in self._findings_rows:
            rid = row.id
            expandable = row.meta.get("expandable", False)
            if expandable:
                expanded = rid in self._expanded_parents
                prefix = "[-] " if expanded else "[+] "
                item_text = row.values.get("item", "")
                if item_text.startswith("[+] ") or item_text.startswith("[-] "):
                    item_text = item_text[4:]
                row.values["item"] = prefix + item_text
            display.append(row)
            if expandable and rid in self._expanded_parents:
                display.extend(self._instance_rows.get(rid, []))
        self._findings_table.set_data(display)

    def _on_findings_toggle(self, event: "tk.Event") -> None:
        """Handle double-click to toggle instance expansion."""
        tree = self._findings_table._tree
        iid = tree.identify_row(event.y)
        if not iid:
            return
        try:
            row_id = int(iid)
        except (ValueError, TypeError):
            return
        if row_id not in self._instance_rows:
            return
        if row_id in self._expanded_parents:
            self._expanded_parents.discard(row_id)
        else:
            self._expanded_parents.add(row_id)
        self._refresh_findings_display()

    def _export_findings(self) -> None:
        """Export findings to CSV."""
        if not self._analysis_results.get("findings"):
            messagebox.showwarning("No Data", "Run analysis first before exporting.")
            return

        # Use the table's export function
        self._findings_table._export_csv()

    def _translate_terms(self) -> None:
        """Translate terms in characters and code database.

        Uses the Term Translation mode configured in Global Options
        (Romaji / LLM).  Fills the ``translation`` field for
        characters and the Translation column for code database entries
        when the original/pattern is non-empty and translation is
        currently blank.  Tab and newline characters are sanitized.

        Reads source/target language from the manifest metadata.

        Runs translation in a background thread with a progress dialog
        so the GUI remains responsive for all modes (Romaji, LLM).
        """
        from CherryAI.functions.term_translation import (
            get_current_mode,
            translate_term,
        )

        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            messagebox.showwarning("No Project", "Load a project first.")
            return

        # Read source/target language from manifest metadata
        metadata = mgr.get_step_data_value(2, "metadata", {})
        source_lang = metadata.get("source_language", "Japanese")
        target_lang = metadata.get("target_language", "English")

        from CherryAI.functions.languages import get_language_by_name
        src_lang = get_language_by_name(source_lang)
        tgt_lang = get_language_by_name(target_lang)
        src_code = src_lang.code if src_lang else "ja"
        tgt_code = tgt_lang.code if tgt_lang else "en"

        mode = get_current_mode()

        # --- Collect items needing translation ---
        # Skip below-threshold speakers for term translation
        go = getattr(self.session, "global_options", None)
        threshold = 10
        if go is not None:
            threshold = getattr(
                getattr(go, "utility", None), "speaker_threshold", 10
            )
        characters = load_character_notes(mgr)
        char_items: list[tuple[int, str]] = []
        for i, ch in enumerate(characters):
            name = ch.get("original_name", "")
            count = ch.get("count", 0)
            if name and not ch.get("translation", "").strip():
                if count >= threshold or count == 0:
                    char_items.append((i, name))

        code_rows: list = []
        code_items: list[tuple[int, str]] = []
        try:
            from CherryAI.functions.glossaries.code_glossary_db import (
                read_all_rows_extended,
            )
            code_rows = read_all_rows_extended()
            for j, row in enumerate(code_rows):
                pattern = row[0] if row else ""
                translation = row[1] if len(row) > 1 else ""
                if pattern and not translation.strip():
                    code_items.append((j, pattern))
        except Exception as exc:
            logger.warning("Code DB read failed: %s", exc)

        total = len(char_items) + len(code_items)
        if total == 0:
            messagebox.showinfo(
                "Term Translation Complete",
                "No entries needed translation "
                "(all already filled or no kana detected).",
            )
            return

        # --- Build progress dialog ---
        dlg = tk.Toplevel(self.winfo_toplevel())
        dlg.title("Translating Terms")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.protocol("WM_DELETE_CLOSE", lambda: None)

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        mode_label = f"Mode: {mode}"
        ttk.Label(frame, text=mode_label).pack(anchor="w")

        progress = ttk.Progressbar(
            frame, orient="horizontal", length=380, mode="determinate",
        )
        progress.pack(fill=tk.X, pady=(5, 5))
        progress["maximum"] = total

        status_var = tk.StringVar(value=f"0 / {total}")
        ttk.Label(frame, textvariable=status_var).pack(anchor="w")

        cancel_event = threading.Event()

        def _on_cancel() -> None:
            cancel_event.set()
            cancel_btn.configure(state="disabled")
            status_var.set("Cancelling…")

        cancel_btn = ttk.Button(frame, text="Cancel", command=_on_cancel)
        cancel_btn.pack(pady=(10, 0))

        # --- Worker thread ---
        updated_chars = 0
        updated_codes = 0
        translated_speakers: list[str] = []
        translated_patterns: dict[str, str] = {}
        done_count = 0

        def _update(count: int, label: str) -> None:
            progress["value"] = count
            status_var.set(f"{count} / {total}  —  {label}")

        def _worker() -> None:
            nonlocal updated_chars, updated_codes, done_count

            try:
                # Translate characters
                for idx, name in char_items:
                    if cancel_event.is_set():
                        break
                    result = translate_term(
                        name, source_lang=src_code, target_lang=tgt_code,
                        prompt_type="glossary",
                    )
                    if result != name:
                        characters[idx]["translation"] = _sanitize_translation(
                            result,
                        )
                        updated_chars += 1
                        translated_speakers.append(name)
                    done_count += 1
                    dlg.after(0, _update, done_count, name)

                # Translate code patterns
                for idx, pattern in code_items:
                    if cancel_event.is_set():
                        break
                    result = translate_term(
                        pattern, source_lang=src_code, target_lang=tgt_code,
                        prompt_type="code",
                    )
                    if result != pattern:
                        code_rows[idx][1] = _sanitize_translation(result)
                        updated_codes += 1
                        translated_patterns[pattern] = code_rows[idx][1]
                    done_count += 1
                    dlg.after(0, _update, done_count, pattern)
            except RuntimeError as exc:
                logger.error("Term translation aborted: %s", exc)
                dlg.after(
                    0,
                    lambda: (
                        dlg.destroy(),
                        messagebox.showerror(
                            "Term Translation Failed",
                            str(exc),
                            parent=self.winfo_toplevel(),
                        ),
                    ),
                )
                return

            dlg.after(0, _finish)

        def _finish() -> None:
            # Save results (must run on main thread for manifest access)
            if updated_chars:
                save_character_notes(mgr, characters)

            if updated_codes:
                try:
                    from CherryAI.functions.glossaries.code_glossary_db import (
                        write_all_rows,
                    )
                    write_all_rows(code_rows)

                    tsv_map = {
                        r[0]: r[1] for r in code_rows if len(r) > 1
                    }
                    manifest_pats = load_code_glossary(mgr)
                    for pat in manifest_pats:
                        t = tsv_map.get(pat.get("pattern", ""), "")
                        if t:
                            pat["translation"] = t
                    save_code_glossary(mgr, manifest_pats)
                except Exception as exc:
                    logger.warning(
                        "Code DB term translation save failed: %s", exc,
                    )

            # Refresh findings table
            if translated_speakers:
                self._refresh_details_for_speakers(translated_speakers)
            if translated_patterns:
                self._refresh_details_for_code_patterns(translated_patterns)

            dlg.destroy()

            # Show summary
            if cancel_event.is_set():
                parts = []
                if updated_chars:
                    parts.append(f"{updated_chars} character(s)")
                if updated_codes:
                    parts.append(f"{updated_codes} code pattern(s)")
                msg = "Translation cancelled."
                if parts:
                    msg += f" Translated {' and '.join(parts)} before stop."
                messagebox.showinfo("Term Translation Cancelled", msg)
            else:
                parts = []
                if updated_chars:
                    parts.append(f"{updated_chars} character(s)")
                if updated_codes:
                    parts.append(f"{updated_codes} code pattern(s)")
                if parts:
                    messagebox.showinfo(
                        "Term Translation Complete",
                        f"Translated {' and '.join(parts)}.",
                    )
                else:
                    messagebox.showinfo(
                        "Term Translation Complete",
                        "No entries needed translation "
                        "(all already filled or no kana detected).",
                    )

        threading.Thread(target=_worker, daemon=True).start()

    # =========================================================================
    # TASK 59.3: Category-Aware Findings Table Context Menu
    # =========================================================================

    def _on_findings_right_click(self, event: tk.Event) -> None:
        """Handle right-click on findings table.

        Shows category-aware context menu based on selected rows.

        Args:
            event: Tkinter event with click coordinates.
        """
        # Get item under click and select it if not already selected
        item = self._findings_table._tree.identify_row(event.y)
        if not item:
            return

        selected = self._findings_table._tree.selection()
        if item not in selected:
            self._findings_table._tree.selection_set(item)
            selected = (item,)

        # Get categories of all selected rows
        categories: set[str] = set()
        for sel_item in selected:
            values = self._findings_table._tree.item(sel_item, "values")
            if values:
                # Category is the first column
                categories.add(str(values[0]))

        # Show appropriate menu based on categories
        if len(categories) == 1:
            category = categories.pop()
            if category == "Speakers":
                menu = self._create_speaker_menu()
            elif category == "Code Patterns":
                menu = self._create_code_pattern_menu()
            else:
                menu = self._create_generic_menu()
        else:
            # Mixed selection - show only generic options
            menu = self._create_generic_menu()

        menu.tk_popup(event.x_root, event.y_root)

    def _create_speaker_menu(self) -> tk.Menu:
        """Create context menu for Speaker category.

        Returns:
            Menu with speaker-specific options.
        """
        menu = tk.Menu(self, tearoff=0)

        menu.add_command(label="Add to Glossary", command=self._add_speaker_to_glossary)

        # Role submenu
        role_menu = tk.Menu(menu, tearoff=0)
        for role in ["Protagonist", "Love Interest", "Major", "Minor"]:
            role_menu.add_command(
                label=role, command=lambda r=role: self._set_speaker_role(r)
            )
        menu.add_cascade(label="Set Role", menu=role_menu)

        # Gender submenu
        gender_menu = tk.Menu(menu, tearoff=0)
        for gender in ["Male", "Female"]:
            gender_menu.add_command(
                label=gender, command=lambda g=gender: self._set_speaker_gender(g)
            )
        # Other submenu with Non-Binary, Transwoman, Transman
        other_gender_menu = tk.Menu(gender_menu, tearoff=0)
        for gender in ["Non-Binary", "Transwoman", "Transman"]:
            other_gender_menu.add_command(
                label=gender, command=lambda g=gender: self._set_speaker_gender(g)
            )
        gender_menu.add_cascade(label="Other", menu=other_gender_menu)
        menu.add_cascade(label="Set Gender", menu=gender_menu)

        menu.add_command(label="Set Translation...", command=self._set_speaker_translation)
        menu.add_separator()
        menu.add_command(label="Add to Code Glossary", command=self._add_speaker_to_code_glossary)
        menu.add_command(label="Copy Name", command=self._copy_speaker_name)
        menu.add_separator()
        menu.add_command(label="Select All with Speaker", command=self._select_all_with_speaker)

        return menu

    def _create_code_pattern_menu(self) -> tk.Menu:
        """Create context menu for Code Pattern category.

        Returns:
            Menu with code pattern-specific options.
        """
        menu = tk.Menu(self, tearoff=0)

        # Action options
        menu.add_command(
            label="Preserve",
            command=lambda: self._set_pattern_action("preserve"),
        )
        menu.add_command(
            label="Remove",
            command=lambda: self._set_pattern_action("remove"),
        )
        menu.add_command(
            label="Translate",
            command=lambda: self._set_pattern_action("translate"),
        )

        menu.add_separator()

        # Replace submenu
        replace_menu = tk.Menu(menu, tearoff=0)
        replace_menu.add_command(
            label="Generic",
            command=lambda: self._set_pattern_replace("generic"),
        )
        replace_menu.add_command(
            label="Custom...", command=self._set_pattern_replace_custom,
        )
        menu.add_cascade(label="Replace With", menu=replace_menu)

        menu.add_separator()

        # Classification options
        menu.add_command(
            label="Is a Name",
            command=lambda: self._set_pattern_type("name"),
        )
        menu.add_command(
            label="Is Text",
            command=lambda: self._set_pattern_type("text"),
        )
        menu.add_command(
            label="Is a Number",
            command=lambda: self._set_pattern_type("number"),
        )
        menu.add_command(
            label="Is Invisible",
            command=lambda: self._set_pattern_type("invisible"),
        )

        menu.add_separator()

        # Nameable dialog for name-type variables
        menu.add_command(
            label="Nameable...",
            command=self._show_nameable_dialog,
        )

        menu.add_separator()
        menu.add_command(label="Copy Pattern", command=self._copy_pattern)
        menu.add_command(
            label="Show Lines with Pattern",
            command=self._show_lines_with_pattern,
        )

        return menu

    def _create_generic_menu(self) -> tk.Menu:
        """Create generic context menu for mixed/other categories.

        Returns:
            Menu with generic options.
        """
        menu = tk.Menu(self, tearoff=0)

        menu.add_command(label="Copy", command=self._copy_selection)
        menu.add_command(label="Select All", command=self._select_all_findings)

        return menu

    def _get_selected_items(self) -> List[Tuple[str, str]]:
        """Get item names from selected rows.

        Returns:
            List of (category, item_name) tuples.
        """
        result = []
        for item_id in self._findings_table._tree.selection():
            values = self._findings_table._tree.item(item_id, "values")
            if values and len(values) >= 2:
                result.append((str(values[0]), str(values[1])))
        return result

    # Character glossary helpers — read/write character notes in manifest
    def _load_characters(self) -> List[Dict[str, Any]]:
        """Load character entries from manifest.

        Returns:
            List of character dicts with name, original_name, gender, role,
            notes, speaking_style.
        """
        try:
            if self.manifest_manager is None:
                return []
        except AttributeError:
            return []
        return load_character_notes(self.manifest_manager)

    def _save_characters(
        self, characters: List[Dict[str, Any]]
    ) -> None:
        """Save character entries to manifest.

        Args:
            characters: List of character dicts.
        """
        try:
            if self.manifest_manager is None:
                logger.debug("No manifest manager, skipping character save")
                return
        except AttributeError:
            logger.debug("No manifest manager, skipping character save")
            return
        save_character_notes(self.manifest_manager, characters)

    def _upsert_character_entry(
        self,
        original_name: str,
        *,
        translation: str = "",
        gender: str = "",
        role: str = "",
        notes: str = "",
    ) -> bool:
        """Add or update a character entry by original_name key.

        If an entry with the same ``original_name`` already exists its
        fields are updated.  ``translation`` overwrites; ``gender``,
        ``role``, and ``notes`` are **appended** to the existing notes
        (de-duplicated) so no information is lost.

        Args:
            original_name: Source-language name (lookup key).
            translation: Translated name.
            gender: Gender string (Male, Female, etc.) — appended to notes.
            role: Role string (Protagonist, etc.) — appended to notes.
            notes: Freeform notes — appended.

        Returns:
            True on success.
        """
        characters = self._load_characters()
        existing = next(
            (c for c in characters if c["original_name"] == original_name),
            None,
        )

        if existing:
            if translation:
                existing["translation"] = translation

            # Append gender/role/notes to the existing notes field
            current_notes = existing.get("notes", "")
            current_parts = [
                p.strip() for p in current_notes.split(",") if p.strip()
            ]
            for new_value in (gender, role, notes):
                if new_value and new_value not in current_parts:
                    current_parts.append(new_value)
            existing["notes"] = ", ".join(current_parts)
        else:
            # Build initial notes from provided fragments
            parts = [v for v in (gender, role, notes) if v]
            characters.append({
                "original_name": original_name,
                "translation": translation,
                "notes": ", ".join(parts),
            })

        self._save_characters(characters)
        return True

    def _get_character_details(self, original_name: str) -> str:
        """Return a display string for a character's glossary info.

        Used by the Findings table Details column to show the current
        translation and notes for a speaker.

        Args:
            original_name: The speaker's source-language name.

        Returns:
            Summary string like 'John — Male, Protagonist' or empty.
        """
        characters = self._load_characters()
        char = next(
            (c for c in characters if c["original_name"] == original_name),
            None,
        )
        if not char:
            return ""
        parts: list[str] = []
        if char.get("translation"):
            parts.append(char["translation"])
        if char.get("notes"):
            parts.append(char["notes"])
        return " — ".join(parts) if parts else ""

    def _refresh_details_for_speakers(
        self, speakers: List[str]
    ) -> None:
        """Update the Details column in the findings table for speakers.

        Called after a glossary action so the table reflects the new
        character data without a full rebuild.

        Args:
            speakers: List of speaker names to refresh.
        """
        if not hasattr(self, "_findings_table") or self._findings_table is None:
            return
        tree = self._findings_table._tree
        for item_id in tree.get_children():
            vals = tree.item(item_id, "values")
            if not vals:
                continue
            # vals order: category, item, count, details
            category = vals[0] if len(vals) > 0 else ""
            item_name = vals[1] if len(vals) > 1 else ""
            if category == "Speakers" and item_name in speakers:
                new_details = self._get_character_details(item_name)
                tree.set(item_id, "details", new_details)

    def _refresh_details_for_code_patterns(
        self, translations: Dict[str, str]
    ) -> None:
        """Update the Details column for code patterns after translation.

        Appends ``→ translation`` to existing details text so the user
        sees the result immediately.

        Args:
            translations: Mapping of pattern → translated text.
        """
        if not hasattr(self, "_findings_table") or self._findings_table is None:
            return
        tree = self._findings_table._tree
        for item_id in tree.get_children():
            vals = tree.item(item_id, "values")
            if not vals:
                continue
            category = vals[0] if len(vals) > 0 else ""
            item_name = vals[1] if len(vals) > 1 else ""
            if category == "Code Patterns" and item_name in translations:
                old_details = vals[3] if len(vals) > 3 else ""
                new_details = f"{old_details} → {translations[item_name]}"
                tree.set(item_id, "details", new_details)

    # Speaker actions
    def _add_speaker_to_glossary(self) -> None:
        """Add selected speakers to character glossary."""
        items = self._get_selected_items()
        speakers = [name for cat, name in items if cat == "Speakers"]
        if not speakers:
            return

        success_count = 0
        for speaker in speakers:
            if self._upsert_character_entry(speaker):
                success_count += 1

        logger.info(
            "Added %d/%d speakers to character glossary: %s",
            success_count, len(speakers), speakers,
        )
        if success_count > 0:
            messagebox.showinfo(
                "Added to Glossary",
                f"Added {success_count} speaker(s) to glossary.",
            )
            self._refresh_details_for_speakers(speakers)
        else:
            messagebox.showwarning("Failed", "Could not add speakers.")

    def _set_speaker_role(self, role: str) -> None:
        """Set role for selected speakers in the character glossary.

        When setting the Protagonist role, POV detection is automatically
        re-run with the new protagonist name(s) and the manifest is
        updated with the new POV result.
        """
        items = self._get_selected_items()
        speakers = [name for cat, name in items if cat == "Speakers"]
        if not speakers:
            return

        success_count = 0
        for speaker in speakers:
            if self._upsert_character_entry(speaker, role=role):
                success_count += 1

        logger.info(
            "Set role '%s' for %d speakers: %s",
            role, success_count, speakers,
        )
        if success_count > 0:
            messagebox.showinfo(
                "Role Set",
                f"Set role '{role}' for {success_count} speaker(s).",
            )
            self._refresh_details_for_speakers(speakers)

            # Task 75: Re-run POV detection when Protagonist role is set
            if role == "Protagonist":
                self._rerun_pov_with_protagonists()

    def _rerun_pov_with_protagonists(self) -> None:
        """Re-run POV detection with current protagonist names.

        Called after a Protagonist role is set.  Reads all lines from
        the input step, gathers protagonist characters, runs
        :func:`run_pov_with_protagonists`, and stores the result in
        the manifest under the ``POV`` key.
        """
        try:
            from CherryAI.functions.analysis import run_pov_with_protagonists
        except ImportError:
            try:
                from functions.analysis import run_pov_with_protagonists
            except ImportError:
                logger.warning("Cannot import run_pov_with_protagonists")
                return

        # Gather lines
        loaded_files = self._get_loaded_files()
        if not loaded_files:
            return
        all_lines: List[str] = []
        for lf in loaded_files:
            if hasattr(lf, "lines"):
                all_lines.extend(lf.lines)
        if not all_lines:
            return

        # Determine source language
        language = ""
        langs = self._analysis_results.get("languages", {})
        if langs:
            language = max(langs, key=lambda k: langs[k])

        # Gather characters and code patterns
        characters = self._load_characters()
        code_patterns = self._load_code_patterns()

        pov_result = run_pov_with_protagonists(
            all_lines, language, characters, code_patterns,
        )

        # Store in manifest
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr._manifest_data["POV"] = pov_result.to_dict()
            mgr.mark_dirty()
            logger.info(
                "POV re-run with protagonists: %s (confidence=%s)",
                pov_result.pov, pov_result.confidence,
            )

    def _set_speaker_gender(self, gender: str) -> None:
        """Set gender for selected speakers in the character glossary."""
        items = self._get_selected_items()
        speakers = [name for cat, name in items if cat == "Speakers"]
        if not speakers:
            return

        success_count = 0
        for speaker in speakers:
            if self._upsert_character_entry(speaker, gender=gender):
                success_count += 1

        logger.info(
            "Set gender '%s' for %d speakers: %s",
            gender, success_count, speakers,
        )
        if success_count > 0:
            messagebox.showinfo(
                "Gender Set",
                f"Set gender '{gender}' for {success_count} speaker(s).",
            )
            self._refresh_details_for_speakers(speakers)

    def _set_speaker_translation(self) -> None:
        """Set custom translation for selected speaker."""
        items = self._get_selected_items()
        speakers = [name for cat, name in items if cat == "Speakers"]
        if not speakers:
            return

        if len(speakers) > 1:
            messagebox.showinfo(
                "Single Select",
                "Please select only one speaker to set translation.",
            )
            return

        speaker = speakers[0]
        from tkinter import simpledialog
        translation = simpledialog.askstring(
            "Set Translation",
            f"Enter translation for '{speaker}':",
        )
        if not translation:
            return

        if self._upsert_character_entry(
            speaker, translation=translation,
        ):
            logger.info(
                "Set translation '%s' for speaker '%s'",
                translation, speaker,
            )
            messagebox.showinfo(
                "Translation Set",
                f"Set translation for '{speaker}'.",
            )
            self._refresh_details_for_speakers([speaker])
        else:
            messagebox.showwarning("Failed", "Could not set translation.")

    def _add_speaker_to_code_glossary(self) -> None:
        """Add selected speakers to code glossary (manifest)."""
        items = self._get_selected_items()
        speakers = [name for cat, name in items if cat == "Speakers"]
        if not speakers:
            return

        success_count = 0
        existing = self._load_code_patterns()
        existing_set = {p.get("pattern", "") for p in existing}

        for speaker in speakers:
            if speaker in existing_set:
                continue
            existing.append({
                "pattern": speaker,
                "category": "Speaker",
                "action": "preserve",
                "notes": "Protected speaker name",
            })
            existing_set.add(speaker)
            success_count += 1

        if success_count:
            self._save_code_patterns(existing)

        logger.info(
            "Added %d speakers to code glossary: %s",
            success_count, speakers,
        )
        if success_count > 0:
            messagebox.showinfo(
                "Added to Code Glossary",
                f"Added {success_count} speaker(s) to code glossary.",
            )

    def _copy_speaker_name(self) -> None:
        """Copy speaker name(s) to clipboard."""
        items = self._get_selected_items()
        speakers = [name for cat, name in items if cat == "Speakers"]
        if speakers:
            text = "\n".join(speakers)
            self.clipboard_clear()
            self.clipboard_append(text)
            logger.debug("Copied to clipboard: %s", speakers)

    def _select_all_with_speaker(self) -> None:
        """Select all rows with same speaker by setting filter."""
        items = self._get_selected_items()
        speakers = [name for cat, name in items if cat == "Speakers"]
        if speakers:
            logger.info("Filtering to show speaker: %s", speakers)
            self._findings_table._filter_var.set(speakers[0])
            self._findings_table._on_filter_change()

    # Code pattern actions — persistence helpers
    def _load_code_patterns(self) -> List[Dict[str, Any]]:
        """Load existing code patterns from manifest.

        Returns:
            List of code pattern dicts.
        """
        if self.manifest_manager is None:
            return []
        return load_code_glossary(self.manifest_manager)

    def _save_code_patterns(self, patterns: List[Dict[str, Any]]) -> None:
        """Save code patterns to manifest.

        Args:
            patterns: List of code pattern dicts.
        """
        if self.manifest_manager is None:
            logger.debug("No manifest manager, skipping code pattern save")
            return
        save_code_glossary(self.manifest_manager, patterns)

    def _upsert_code_pattern(
        self,
        pattern: str,
        *,
        action: Optional[str] = None,
        category: Optional[str] = None,
        notes: Optional[str] = None,
        example: Optional[str] = None,
    ) -> None:
        """Insert or update a single code pattern in the manifest.

        Only non-None keyword arguments overwrite existing fields.

        Args:
            pattern: Normalized code pattern string.
            action: Action to set (preserve/remove/translate/replace).
            category: Pattern category (Line Break, Variable Name, etc.).
            notes: User notes (e.g. "Type: name").
            example: Example occurrence from source text.
        """
        existing = self._load_code_patterns()
        found = False
        for entry in existing:
            if entry.get("pattern") == pattern:
                if action is not None:
                    entry["action"] = action
                if category is not None:
                    entry["category"] = category
                if notes is not None:
                    entry["notes"] = notes
                if example is not None:
                    entry["example"] = example
                found = True
                break

        if not found:
            # Look up meta from findings for category/example fallback
            meta_info = self._get_pattern_meta(pattern)
            existing.append({
                "pattern": pattern,
                "category": category or meta_info.get("type", ""),
                "action": action or "preserve",
                "example": example or "",
                "notes": notes or "",
            })

        self._save_code_patterns(existing)

    def _get_pattern_meta(self, pattern: str) -> Dict[str, Any]:
        """Get meta information for a pattern from analysis results.

        Args:
            pattern: Normalized code pattern string.

        Returns:
            Dict with type and raw_type from analysis results.
        """
        code_patterns = self._analysis_results.get("code_patterns", [])
        if isinstance(code_patterns, list):
            for entry in code_patterns:
                if isinstance(entry, dict) and entry.get("pattern") == pattern:
                    return {
                        "type": entry.get("category", "Unknown"),
                        "raw_type": entry.get("raw_type", "UNKNOWN"),
                    }
        return {"type": "Unknown", "raw_type": "UNKNOWN"}

    # Code pattern actions
    def _set_pattern_action(self, action: str) -> None:
        """Set action (preserve/remove/translate) for selected patterns.

        Persists to Code Database in manifest.
        """
        items = self._get_selected_items()
        patterns = [name for cat, name in items if cat == "Code Patterns"]
        if not patterns:
            return

        for pattern in patterns:
            self._upsert_code_pattern(pattern, action=action)

        logger.info(
            "Set action '%s' for %d patterns: %s",
            action, len(patterns), patterns,
        )
        messagebox.showinfo(
            "Action Set",
            f"Set '{action}' for {len(patterns)} pattern(s).",
        )

    def _set_pattern_replace(self, mode: str) -> None:
        """Set generic replacement for selected patterns.

        Persists to Code Database in manifest with action='replace'.
        """
        items = self._get_selected_items()
        patterns = [name for cat, name in items if cat == "Code Patterns"]
        if not patterns:
            return

        for pattern in patterns:
            self._upsert_code_pattern(
                pattern,
                action="replace",
                notes=f"Replacement: {mode}",
            )

        logger.info(
            "Set replacement mode '%s' for %d patterns: %s",
            mode, len(patterns), patterns,
        )
        messagebox.showinfo(
            "Replacement Set",
            f"Set '{mode}' replacement for {len(patterns)} pattern(s).",
        )

    def _set_pattern_replace_custom(self) -> None:
        """Set custom replacement for selected pattern.

        Opens dialog, then persists to Code Database with action='replace'.
        """
        items = self._get_selected_items()
        patterns = [name for cat, name in items if cat == "Code Patterns"]
        if len(patterns) == 1:
            from tkinter import simpledialog
            replacement = simpledialog.askstring(
                "Set Custom Replacement",
                f"Enter replacement for pattern '{patterns[0]}':",
            )
            if replacement:
                self._upsert_code_pattern(
                    patterns[0],
                    action="replace",
                    notes=f"Replacement: {replacement}",
                )
                logger.info(
                    "Set custom replacement '%s' for pattern '%s'",
                    replacement, patterns[0],
                )
                messagebox.showinfo(
                    "Replacement Set",
                    f"Set custom replacement for '{patterns[0]}'.",
                )
        elif patterns:
            messagebox.showinfo(
                "Single Select",
                "Please select only one pattern for custom replacement.",
            )

    # Default replacement names by category & gender
    _PROTAGONIST_NAMES = {
        "Male": ("John", "Smith"),
        "Female": ("Jane", "Smith"),
        "Non-Binary": ("Alex", "Smith"),
    }
    _COMPANY_NAMES = ["Acme Corp", "Globex", "Initech", "Umbrella"]
    _LOCATION_NAMES = ["Greenville", "Lakewood", "Oakmont", "Riverside"]

    def _set_pattern_type(self, type_name: str) -> None:
        """Set type classification for selected patterns.

        When type is 'name', the pattern is also added to the glossary with
        a temporary replacement for use in preprocessing.

        Persists to Code Database in manifest notes field.
        """
        items = self._get_selected_items()
        patterns = [name for cat, name in items if cat == "Code Patterns"]
        if not patterns:
            return

        for pattern in patterns:
            self._upsert_code_pattern(pattern, notes=f"Type: {type_name}")

        # When marked as a name, also add to glossary with temp replacement
        if type_name == "name":
            self._add_name_patterns_to_glossary(patterns)

        logger.info(
            "Set type '%s' for %d patterns: %s",
            type_name, len(patterns), patterns,
        )
        messagebox.showinfo(
            "Type Set",
            f"Set type '{type_name}' for {len(patterns)} pattern(s).",
        )

    def _add_name_patterns_to_glossary(
        self, patterns: List[str],
    ) -> None:
        """Add name-type code patterns to glossary with temp replacements.

        Creates a character glossary entry for the replacement name and
        a Custom Placeholder so the code pattern is protected during
        translation.

        Args:
            patterns: List of normalized code pattern strings.
        """
        from tkinter import simpledialog

        for pattern in patterns:
            replacement = simpledialog.askstring(
                "Name Replacement",
                f"Enter temporary replacement name for '{pattern}'\n"
                "(leave blank for auto-generated, e.g. 'John'):",
            )
            if replacement is None:
                # User cancelled
                continue
            if not replacement:
                replacement = "John"  # Default male protagonist name

            # Character entry — Original = replacement name
            self._upsert_character_entry(replacement)

            # Custom Placeholder — pattern→replacement during translation
            cur_ph = load_custom_placeholders(
                self.manifest_manager
            ) if self.manifest_manager else []
            cur_ph = [
                p for p in cur_ph if p.get("pattern") != pattern
            ]
            cur_ph.append({
                "pattern": pattern,
                "placeholder": replacement,
                "is_regex": False,
                "restore_after": True,
            })
            if self.manifest_manager:
                save_custom_placeholders(self.manifest_manager, cur_ph)

            logger.info(
                "Added name pattern '%s' → '%s' to character glossary "
                "and custom placeholders",
                pattern, replacement,
            )

    def _show_nameable_dialog(self) -> None:
        """Show the Nameable dialog for assigning a replacement to a code
        pattern.

        The dialog offers three mode buttons — Character, Company, Location
        — each pre-filling suitable defaults.  All fields (Custom
        Replacement, Role, Gender, Custom Notes) are fully editable.

        On OK/Apply the replacement name becomes a character glossary entry
        (Original = replacement, e.g. "John") and the code pattern is
        written to Preprocessing Custom Placeholders so it is protected
        during translation and replaced with the name.
        """
        items = self._get_selected_items()
        patterns = [name for cat, name in items if cat == "Code Patterns"]
        if not patterns:
            return

        if len(patterns) > 1:
            messagebox.showinfo(
                "Single Select",
                "Please select one pattern for the Nameable dialog.",
            )
            return

        pattern = patterns[0]

        # Check if a character entry already exists for this pattern
        characters = self._load_characters()
        # Look for an existing character whose notes reference this pattern
        existing_char: Dict[str, Any] | None = None
        for ch in characters:
            if ch.get("notes", "").find(pattern) != -1:
                existing_char = ch
                break
        # Also check existing custom placeholders
        existing_placeholders = load_custom_placeholders(
            self.manifest_manager
        ) if self.manifest_manager else []
        existing_ph = next(
            (p for p in existing_placeholders if p.get("pattern") == pattern),
            None,
        )

        dlg = tk.Toplevel(self)
        dlg.title(f"Nameable — {pattern}")
        dlg.geometry("420x360")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        # --- Mode buttons ---
        mode_frame = ttk.LabelFrame(dlg, text="Type")
        mode_frame.pack(fill="x", padx=10, pady=(10, 5))

        mode_var = tk.StringVar(value="Character")

        # Helper to pre-fill fields based on mode
        def _prefill(mode: str) -> None:
            mode_var.set(mode)
            if mode == "Character":
                gender_combo.configure(state="readonly")
                role_combo.configure(state="readonly")
                gender_var.set("Male")
                role_var.set("Protagonist")
                first, surname = self._PROTAGONIST_NAMES.get("Male", ("John", "Smith"))
                replacement_var.set(first)
                notes_var.set(f"Surname: {surname}")
            elif mode == "Company":
                gender_combo.configure(state="disabled")
                role_combo.configure(state="readonly")
                gender_var.set("")
                role_var.set("Organization")
                replacement_var.set(self._COMPANY_NAMES[0])
                notes_var.set("")
            elif mode == "Location":
                gender_combo.configure(state="disabled")
                role_combo.configure(state="readonly")
                gender_var.set("")
                role_var.set("Location")
                replacement_var.set(self._LOCATION_NAMES[0])
                notes_var.set("")

        for mode in ("Character", "Company", "Location"):
            ttk.Radiobutton(
                mode_frame, text=mode, variable=mode_var, value=mode,
                command=lambda m=mode: _prefill(m),
            ).pack(side="left", padx=10, pady=5)

        # --- Fields ---
        fields_frame = ttk.Frame(dlg)
        fields_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(fields_frame, text="Custom Replacement:").grid(
            row=0, column=0, sticky="w", pady=3,
        )
        replacement_var = tk.StringVar()
        ttk.Entry(
            fields_frame, textvariable=replacement_var, width=30,
        ).grid(row=0, column=1, sticky="ew", pady=3, padx=(5, 0))

        ttk.Label(fields_frame, text="Role:").grid(
            row=1, column=0, sticky="w", pady=3,
        )
        role_var = tk.StringVar()
        role_combo = ttk.Combobox(
            fields_frame, textvariable=role_var, width=28,
            values=[
                "Protagonist", "Love Interest", "Major", "Minor",
                "Organization", "Location", "Other",
            ],
            state="readonly",
        )
        role_combo.grid(row=1, column=1, sticky="ew", pady=3, padx=(5, 0))

        ttk.Label(fields_frame, text="Gender:").grid(
            row=2, column=0, sticky="w", pady=3,
        )
        gender_var = tk.StringVar()
        gender_combo = ttk.Combobox(
            fields_frame, textvariable=gender_var, width=28,
            values=[
                "", "Male", "Female", "Non-Binary",
                "Transwoman", "Transman", "Unknown",
            ],
            state="readonly",
        )
        gender_combo.grid(row=2, column=1, sticky="ew", pady=3, padx=(5, 0))

        ttk.Label(fields_frame, text="Custom Notes:").grid(
            row=3, column=0, sticky="nw", pady=3,
        )
        notes_var = tk.StringVar()
        ttk.Entry(
            fields_frame, textvariable=notes_var, width=30,
        ).grid(row=3, column=1, sticky="ew", pady=3, padx=(5, 0))

        fields_frame.columnconfigure(1, weight=1)

        # Warn if entry already exists
        if existing_char or existing_ph:
            ttk.Label(
                dlg,
                text="⚠ An entry for this pattern already exists and will be overwritten.",
                foreground="orange",
                font=("Segoe UI", 8),
                wraplength=380,
            ).pack(padx=10, pady=(5, 0))

        # Pre-fill with existing data or defaults
        if existing_char:
            replacement_var.set(existing_char.get("original_name", ""))
            # Gender/role are now stored inside notes — show notes as-is
            gender_var.set("")
            role_var.set("")
            notes_var.set(existing_char.get("notes", ""))
        else:
            _prefill("Character")

        # --- Buttons ---
        def _apply() -> None:
            repl = replacement_var.get().strip()
            if not repl:
                messagebox.showwarning(
                    "Required", "Please enter a replacement value.",
                )
                return

            role = role_var.get().strip()
            gender = gender_var.get().strip()
            notes = notes_var.get().strip()

            # 1. Update code pattern database (Analysis tracking)
            self._upsert_code_pattern(
                pattern,
                action="replace",
                notes=f"Type: name; Role: {role}; Replacement: {repl}",
            )

            # 2. Create character glossary entry —
            #    Original = replacement name (e.g. "John")
            self._upsert_character_entry(
                repl,
                gender=gender,
                role=role,
                notes=notes,
            )

            # 3. Add to Custom Placeholders in Preprocessing —
            #    pattern = code pattern, placeholder = replacement name
            cur_ph = load_custom_placeholders(
                self.manifest_manager
            ) if self.manifest_manager else []
            # Remove existing placeholder for this pattern if any
            cur_ph = [
                p for p in cur_ph if p.get("pattern") != pattern
            ]
            cur_ph.append({
                "pattern": pattern,
                "placeholder": repl,
                "is_regex": False,
                "restore_after": True,
            })
            if self.manifest_manager:
                save_custom_placeholders(self.manifest_manager, cur_ph)

            # 4. Add glossary entry with replacement name as source
            #    and role/gender/notes in the notes field
            if self.manifest_manager:
                glossary_entries = load_glossary_entries(self.manifest_manager)
                # Remove existing entry for this replacement name
                glossary_entries = [
                    e for e in glossary_entries
                    if e.get("source") != repl
                ]
                # Build notes string from gender, role, and custom notes
                note_parts: list[str] = []
                if gender:
                    note_parts.append(f"Gender: {gender}")
                if role:
                    note_parts.append(f"Role: {role}")
                if notes:
                    note_parts.append(notes)
                glossary_notes = "; ".join(note_parts)
                glossary_entries.append({
                    "source": repl,
                    "target": "",
                    "notes": glossary_notes,
                    "category": "",
                    "context": "",
                    "active": True,
                })
                save_glossary_entries(self.manifest_manager, glossary_entries)

            logger.info(
                "Nameable: '%s' → '%s' (role=%s, gender=%s); "
                "added custom placeholder",
                pattern, repl, role, gender,
            )

        def _ok() -> None:
            _apply()
            dlg.destroy()

        btn_row = ttk.Frame(dlg)
        btn_row.pack(pady=15)
        ttk.Button(btn_row, text="OK", command=_ok, width=8).pack(
            side="left", padx=5,
        )
        ttk.Button(
            btn_row, text="Cancel", command=dlg.destroy, width=8,
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_row, text="Apply", command=_apply, width=8,
        ).pack(side="left", padx=5)

    def _copy_pattern(self) -> None:
        """Copy pattern(s) to clipboard."""
        items = self._get_selected_items()
        patterns = [name for cat, name in items if cat == "Code Patterns"]
        if patterns:
            text = "\n".join(patterns)
            self.clipboard_clear()
            self.clipboard_append(text)
            logger.debug("Copied to clipboard: %s", patterns)

    def _show_lines_with_pattern(self) -> None:
        """Show lines containing selected pattern by setting filter."""
        items = self._get_selected_items()
        patterns = [name for cat, name in items if cat == "Code Patterns"]
        if patterns:
            logger.info("Filtering to show lines with patterns: %s", patterns)
            # Set the findings table filter to show the selected pattern
            self._findings_table._filter_var.set(patterns[0])
            self._findings_table._on_filter_change()

    # Generic actions
    def _copy_selection(self) -> None:
        """Copy selected row data to clipboard."""
        selected = self._findings_table._tree.selection()
        if not selected:
            return

        lines = []
        for item_id in selected:
            values = self._findings_table._tree.item(item_id, "values")
            if values:
                lines.append("\t".join(str(v) for v in values))

        if lines:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            logger.debug("Copied %d rows to clipboard", len(lines))

    def _select_all_findings(self) -> None:
        """Select all rows in findings table."""
        all_items = self._findings_table._tree.get_children()
        if all_items:
            self._findings_table._tree.selection_set(all_items)

    # =========================================================================
    # End of Context Menu Implementation
    # =========================================================================
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

    def _save_line_counts_to_manifest(self, results: Dict[str, Any]) -> None:
        """Save line count data to manifest (TASK 25.1).
        
        This saves the total_lines and unique_lines counts which are used
        by the Estimation step for initial token estimation.
        
        Args:
            results: Analysis results dictionary.
        """
        if self.manifest_manager is None:
            logger.debug("No manifest manager, skipping line count save")
            return
        
        total_lines = results.get("total_lines", 0)
        unique_lines = results.get("unique_lines", 0)
        empty_lines = results.get("empty_lines", 0)
        duplicate_count = results.get("duplicate_count", 0)
        
        # Save to manifest - InputLines will store effective line count
        # (total - empty, since empty lines are skipped in translation)
        effective_lines = total_lines - empty_lines
        save_int_field(self.manifest_manager, "InputLines", effective_lines)
        
        logger.debug(
            "Saved line counts to manifest: total=%d, unique=%d, empty=%d, effective=%d",
            total_lines, unique_lines, empty_lines, effective_lines
        )

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

    def on_new_project(self) -> None:
        """Reset cached state for a fresh project."""
        super().on_new_project()
        self._analysis_results.clear()
        self._is_analyzing = False
        self._instance_rows.clear()
        self._expanded_parents.clear()
        self._findings_rows.clear()
        logger.debug("Analysis step reset for new project")

    def on_enter(self) -> None:
        """Called when the step tab is selected.

        Refreshes the analysis if files have changed.
        Restores analysis results from session if available.
        """
        # First, try to restore analysis results from session
        step_data = self.get_step_data()
        if step_data.get("analysis_results") and not self._analysis_results:
            # TASK 74.1: Use deepcopy to avoid contaminating _manifest_data
            # with non-serializable TableRow objects when findings are
            # deserialized below.  get_step_data() returns a shared reference.
            from copy import deepcopy
            self._analysis_results = deepcopy(step_data["analysis_results"])
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
