"""Suppressible confirmation dialogs.

Provides a ``confirm_action`` helper that wraps a standard yes/no
confirmation with a *"Don't ask again"* tick-box.  When the user
ticks the box and confirms, the dialog is suppressed for future
calls with the same *key*.  Suppressed dialogs always return
``True`` (i.e. proceed) without showing UI.

Suppression state is stored in the ``[confirmations]`` section of
the application INI file and can be reset from Global Options.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# INI helpers (lazy import to avoid circular deps)
# ---------------------------------------------------------------------------

_SECTION = "confirmations"


def _get_ini():  # noqa: ANN202
    """Lazy-import ini_manager."""
    from CherryAI.functions import ini_manager
    return ini_manager


def is_suppressed(key: str) -> bool:
    """Return ``True`` when the dialog identified by *key* is suppressed."""
    try:
        ini = _get_ini()
        return ini.get_bool(_SECTION, key, fallback=False)
    except Exception:
        return False


def suppress(key: str) -> None:
    """Mark dialog *key* as suppressed."""
    try:
        ini = _get_ini()
        ini.set_default(_SECTION, key, True)
    except Exception as exc:
        logger.warning("Failed to suppress confirmation '%s': %s", key, exc)


def reset_all_suppressions() -> None:
    """Clear **all** suppressed confirmations so every dialog shows again."""
    try:
        ini = _get_ini()
        ini.remove_section(_SECTION)
    except Exception as exc:
        logger.warning("Failed to reset confirmations: %s", exc)


# ---------------------------------------------------------------------------
# Custom confirmation dialog
# ---------------------------------------------------------------------------


def confirm_action(
    parent: Optional[tk.Widget],
    key: str,
    title: str,
    message: str,
) -> bool:
    """Show a yes/no dialog with a *"Don't ask again"* check-box.

    If the dialog was previously suppressed for *key*, returns
    ``True`` immediately without any UI.

    Args:
        parent:  Parent widget (may be ``None``).
        key:     Unique identifier stored in INI, e.g. ``"remove_character"``.
        title:   Dialog window title.
        message: Body text shown to the user.

    Returns:
        ``True`` if the user confirmed (or the dialog was suppressed),
        ``False`` if the user declined.
    """
    if is_suppressed(key):
        return True

    # Build a modal Toplevel with checkbox
    result = False  # pessimistic default
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.resizable(False, False)
    if parent is not None:
        dialog.transient(parent)
    dialog.grab_set()

    # Centre on parent
    dialog.update_idletasks()
    if parent is not None:
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
    else:
        px = dialog.winfo_screenwidth() // 2
        py = dialog.winfo_screenheight() // 2
    dialog.geometry(f"+{px - 150}+{py - 60}")

    # Message
    ttk.Label(
        dialog, text=message, wraplength=300, justify="left",
    ).pack(padx=20, pady=(15, 10))

    # "Don't ask again" check
    dont_ask_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        dialog, text="Don't ask again", variable=dont_ask_var,
    ).pack(padx=20, anchor="w")

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill="x", padx=20, pady=(10, 15))

    def _on_yes() -> None:
        nonlocal result
        result = True
        if dont_ask_var.get():
            suppress(key)
        dialog.destroy()

    def _on_no() -> None:
        nonlocal result
        result = False
        dialog.destroy()

    ttk.Button(btn_frame, text="Yes", command=_on_yes, width=8).pack(
        side="left", padx=(0, 5),
    )
    ttk.Button(btn_frame, text="No", command=_on_no, width=8).pack(
        side="left",
    )

    dialog.protocol("WM_DELETE_WINDOW", _on_no)
    dialog.bind("<Return>", lambda e: _on_yes())
    dialog.bind("<Escape>", lambda e: _on_no())

    dialog.wait_window()
    return result
