"""Loading progress dialog for file loading operations.

TASK 39.7: Shows progress window during file loading with:
- Progress bar (determinate mode)
- Current file label
- Files loaded / total files count
- Cancel button
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional

from CherryAI.gui.theme.colors import apply_window_preferences

logger = logging.getLogger(__name__)


class LoadingProgressDialog:
    """Modal progress dialog for file loading operations.

    Attributes:
        cancelled: Whether the user cancelled the operation.
    """

    def __init__(self, parent: tk.Widget, total_files: int) -> None:
        """Initialize the progress dialog.

        Args:
            parent: Parent widget.
            total_files: Total number of files to load.
        """
        self.cancelled = False
        self._total = max(total_files, 1)
        self._loaded = 0
        self._phase_text = "Preparing"

        self._dialog = tk.Toplevel(parent)
        self._dialog.title("Loading Files...")
        self._dialog.transient(parent)
        self._dialog.grab_set()
        self._dialog.resizable(False, False)
        apply_window_preferences(
            self._dialog,
            parent=parent,
            window_key="LoadingProgressDialog",
            default_geometry="420x170",
            center_on_parent=True,
        )

        # Prevent closing via window manager
        self._dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        frame = ttk.Frame(self._dialog, padding=15)
        frame.pack(fill="both", expand=True)

        self._phase_label = ttk.Label(frame, text=self._phase_text, anchor="w")
        self._phase_label.pack(fill="x", pady=(0, 4))

        # Current file label
        self._file_label = ttk.Label(
            frame,
            text="Preparing...",
            wraplength=360,
            anchor="w",
        )
        self._file_label.pack(fill="x", pady=(0, 5))

        # Progress bar
        self._progress = ttk.Progressbar(
            frame, orient="horizontal", length=360, mode="determinate",
        )
        self._progress["maximum"] = self._total
        self._progress.pack(fill="x", pady=(0, 5))

        self._detail_label = ttk.Label(
            frame,
            text="",
            anchor="w",
        )
        self._detail_label.pack(fill="x", pady=(0, 5))

        # Count label + Cancel button
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x")

        self._count_label = ttk.Label(
            bottom, text=f"0 / {self._total} files",
        )
        self._count_label.pack(side="left")

        cancel_btn = ttk.Button(bottom, text="Cancel", command=self._on_cancel)
        cancel_btn.pack(side="right")

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #

    def update(self, current_file: str) -> None:
        """Update progress for the next file.

        Args:
            current_file: Display name of the file being loaded.
        """
        self._loaded += 1
        self._progress["value"] = self._loaded
        self._count_label.configure(text=f"{self._loaded} / {self._total} files")
        self._file_label.configure(text=current_file)
        self._detail_label.configure(text="")
        self._pump_events()

    def set_phase(self, text: str) -> None:
        """Update the current phase label."""
        self._phase_text = text
        self._phase_label.configure(text=text)
        self._pump_events()

    def update_staging(
        self,
        *,
        rel_path: str,
        current_file: int,
        total_files: int,
        file_bytes: int,
        file_total_bytes: int,
    ) -> bool:
        """Update progress while staging full source trees."""
        self._total = max(total_files, 1)
        self._progress["maximum"] = self._total
        self._loaded = min(max(current_file, 0), self._total)
        self._progress["value"] = self._loaded
        self._count_label.configure(text=f"{min(current_file, total_files)} / {total_files} files")
        self._phase_label.configure(text="Staging Original tree")
        self._file_label.configure(text=rel_path)
        if file_total_bytes > 0:
            self._detail_label.configure(
                text=f"{self._format_size(file_bytes)} / {self._format_size(file_total_bytes)}",
            )
        else:
            self._detail_label.configure(text="")
        self._pump_events()
        return not self.cancelled

    def close(self) -> None:
        """Close the progress dialog."""
        try:
            self._dialog.grab_release()
            self._dialog.destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ #
    # Private
    # ------------------------------------------------------------------ #

    def _on_cancel(self) -> None:
        """Handle cancel button or window close."""
        self.cancelled = True
        self._file_label.configure(text="Cancelling...")
        self._pump_events()

    def _pump_events(self) -> None:
        """Process pending UI events so long copies stay responsive."""
        try:
            self._dialog.update_idletasks()
            self._dialog.update()
        except tk.TclError:
            pass

    @staticmethod
    def _format_size(size: int) -> str:
        """Format a byte count for the detail label."""
        value = float(max(size, 0))
        units = ["B", "KB", "MB", "GB", "TB"]
        for unit in units:
            if value < 1024.0 or unit == units[-1]:
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{int(size)} B"
