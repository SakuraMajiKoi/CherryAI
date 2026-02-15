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

        self._dialog = tk.Toplevel(parent)
        self._dialog.title("Loading Files...")
        self._dialog.transient(parent)
        self._dialog.grab_set()
        self._dialog.resizable(False, False)

        # Center on parent
        self._dialog.geometry("400x130")
        self._dialog.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - 400) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 130) // 2
        self._dialog.geometry(f"+{max(px, 0)}+{max(py, 0)}")

        # Prevent closing via window manager
        self._dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        frame = ttk.Frame(self._dialog, padding=15)
        frame.pack(fill="both", expand=True)

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
        self._dialog.update_idletasks()

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
        self._dialog.update_idletasks()
