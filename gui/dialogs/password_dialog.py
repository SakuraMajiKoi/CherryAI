"""Password Setup and Change Dialogs.

Provides modal Tk dialogs for setting and changing the master password used
to encrypt API keys stored in ``user/API.ini``.

Dialogs
-------
- :class:`SetPasswordDialog`  — first-time password creation.
- :class:`ChangePasswordDialog` — authenticated password change.
- :class:`VerifyPasswordDialog` — authenticate to view a stored key.

All business logic is delegated to :mod:`CherryAI.functions.api_config`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from CherryAI.functions import api_config
from CherryAI.gui.widgets.password_strength import PasswordStrengthWidget

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _center(dialog: tk.Toplevel, parent: Optional[tk.Widget] = None) -> None:
    """Center *dialog* on *parent* (or screen if parent is None)."""
    dialog.update_idletasks()
    w, h = dialog.winfo_width(), dialog.winfo_height()
    if parent is not None:
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
    else:
        px = dialog.winfo_screenwidth() // 2
        py = dialog.winfo_screenheight() // 2
    dialog.geometry(f"+{px - w // 2}+{py - h // 2}")


# ---------------------------------------------------------------------------
# Set Password Dialog
# ---------------------------------------------------------------------------

class SetPasswordDialog(tk.Toplevel):
    """First-time master password creation dialog.

    Shows two :class:`PasswordStrengthWidget` fields (new + confirm) and a
    HiveSystems-style strength meter.  Password is accepted when:

    - Both fields match.
    - Strength tier is *not* "Instantly" (i.e. ≥ 8 characters).

    After a successful submission the password hash + key-salt are persisted
    to ``user/API.ini`` via :func:`api_config.set_password`.

    Args:
        parent: Tkinter parent window.

    Returns (via ``result`` attribute):
        ``True`` if a password was successfully set, ``False`` otherwise.

    Example::

        dlg = SetPasswordDialog(root)
        dlg.wait_window()
        if dlg.result:
            messagebox.showinfo("Done", "Password set!")
    """

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Set Master Password")
        self.resizable(False, False)
        self.result: bool = False

        self._build_ui()
        self.transient(parent)
        self.grab_set()
        _center(self, parent)
        self._pw_widget.focus()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(
            outer,
            text="Set Master Password",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            outer,
            text=(
                "This password encrypts your API keys stored in user/API.ini.\n"
                "Choose a strong password — it cannot be recovered if lost."
            ),
            foreground="gray",
            justify="left",
            wraplength=380,
        ).pack(anchor="w", pady=(0, 14))

        # New password
        self._pw_widget = PasswordStrengthWidget(
            outer,
            label_text="New password:",
            label_width=15,
            on_change=self._on_pw_change,
        )
        self._pw_widget.pack(fill=tk.X, pady=(0, 8))

        # Confirm password
        confirm_row = ttk.Frame(outer)
        confirm_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(confirm_row, text="Confirm:", width=15, anchor="w").pack(side=tk.LEFT)
        self._confirm_var = tk.StringVar()
        self._confirm_entry = ttk.Entry(
            confirm_row,
            textvariable=self._confirm_var,
            show="\u2022",
            width=28,
        )
        self._confirm_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._confirm_var.trace_add("write", self._on_pw_change)

        # Match indicator
        self._match_label = ttk.Label(outer, text="", foreground="gray")
        self._match_label.pack(anchor="w", pady=(2, 12))

        # Buttons
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._ok_btn = ttk.Button(
            btn_frame, text="Set Password", command=self._on_ok, state="disabled"
        )
        self._ok_btn.pack(side=tk.RIGHT)

        # Bind Enter key
        self._confirm_entry.bind("<Return>", lambda _: self._on_ok())

    # ------------------------------------------------------------------
    def _on_pw_change(self, *_: object) -> None:
        """Validate inputs and enable/disable the OK button."""
        pw = self._pw_widget.get()
        confirm = self._confirm_var.get()
        tier = self._pw_widget.strength_var.get()

        # Match check
        if not pw:
            self._match_label.configure(text="", foreground="gray")
        elif pw == confirm:
            self._match_label.configure(text="\u2714 Passwords match", foreground="#2ECC71")
        else:
            self._match_label.configure(text="\u2718 Passwords do not match", foreground="#E74C3C")

        # Enable OK only when tier is not Instantly and passwords match
        ok_state = (
            "normal"
            if (pw and pw == confirm and tier != api_config.PasswordStrength.INSTANTLY)
            else "disabled"
        )
        self._ok_btn.configure(state=ok_state)

    # ------------------------------------------------------------------
    def _on_ok(self) -> None:
        password = self._pw_widget.get()
        tier = self._pw_widget.strength_var.get()

        if tier == api_config.PasswordStrength.INSTANTLY:
            messagebox.showwarning(
                "Weak Password",
                "Password is too short. Use at least 8 characters.",
                parent=self,
            )
            return

        if password != self._confirm_var.get():
            messagebox.showwarning(
                "Mismatch",
                "Passwords do not match.",
                parent=self,
            )
            return

        try:
            api_config.set_password(password)
            self.result = True
            self.destroy()
        except Exception as exc:
            logger.exception("set_password failed: %s", exc)
            messagebox.showerror(
                "Error",
                f"Failed to set password:\n{exc}",
                parent=self,
            )


# ---------------------------------------------------------------------------
# Change Password Dialog
# ---------------------------------------------------------------------------

class ChangePasswordDialog(tk.Toplevel):
    """Authenticated master password change dialog.

    Prompts for the current password before accepting a new one.

    Args:
        parent: Tkinter parent window.

    Returns (via ``result`` attribute):
        ``True`` if the password was successfully changed, ``False`` otherwise.
    """

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Change Master Password")
        self.resizable(False, False)
        self.result: bool = False

        self._build_ui()
        self.transient(parent)
        self.grab_set()
        _center(self, parent)
        self._current_entry.focus()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="Change Master Password",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            outer,
            text="All stored API keys will be re-encrypted with the new password.",
            foreground="gray",
            wraplength=380,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        # Current password
        cur_row = ttk.Frame(outer)
        cur_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(cur_row, text="Current password:", width=17, anchor="w").pack(side=tk.LEFT)
        self._current_var = tk.StringVar()
        self._current_entry = ttk.Entry(
            cur_row, textvariable=self._current_var, show="\u2022", width=28
        )
        self._current_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Separator(outer, orient="horizontal").pack(fill=tk.X, pady=8)

        # New password with strength meter
        self._pw_widget = PasswordStrengthWidget(
            outer,
            label_text="New password:",
            label_width=17,
            on_change=self._on_pw_change,
        )
        self._pw_widget.pack(fill=tk.X, pady=(0, 8))

        # Confirm
        confirm_row = ttk.Frame(outer)
        confirm_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(confirm_row, text="Confirm:", width=17, anchor="w").pack(side=tk.LEFT)
        self._confirm_var = tk.StringVar()
        self._confirm_entry = ttk.Entry(
            confirm_row,
            textvariable=self._confirm_var,
            show="\u2022",
            width=28,
        )
        self._confirm_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._confirm_var.trace_add("write", self._on_pw_change)

        # Match indicator
        self._match_label = ttk.Label(outer, text="", foreground="gray")
        self._match_label.pack(anchor="w", pady=(2, 12))

        # Buttons
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._ok_btn = ttk.Button(
            btn_frame, text="Change Password", command=self._on_ok, state="disabled"
        )
        self._ok_btn.pack(side=tk.RIGHT)

        self._confirm_entry.bind("<Return>", lambda _: self._on_ok())

    # ------------------------------------------------------------------
    def _on_pw_change(self, *_: object) -> None:
        pw = self._pw_widget.get()
        confirm = self._confirm_var.get()
        tier = self._pw_widget.strength_var.get()

        if not pw:
            self._match_label.configure(text="", foreground="gray")
        elif pw == confirm:
            self._match_label.configure(text="\u2714 Passwords match", foreground="#2ECC71")
        else:
            self._match_label.configure(text="\u2718 Passwords do not match", foreground="#E74C3C")

        ok_state = (
            "normal"
            if (
                self._current_var.get()
                and pw
                and pw == confirm
                and tier != api_config.PasswordStrength.INSTANTLY
            )
            else "disabled"
        )
        self._ok_btn.configure(state=ok_state)

    # ------------------------------------------------------------------
    def _on_ok(self) -> None:
        old_pw = self._current_var.get()
        new_pw = self._pw_widget.get()
        tier = self._pw_widget.strength_var.get()

        if tier == api_config.PasswordStrength.INSTANTLY:
            messagebox.showwarning(
                "Weak Password",
                "New password is too short. Use at least 8 characters.",
                parent=self,
            )
            return

        if new_pw != self._confirm_var.get():
            messagebox.showwarning("Mismatch", "New passwords do not match.", parent=self)
            return

        try:
            ok = api_config.change_password(old_pw, new_pw)
            if ok:
                self.result = True
                self.destroy()
            else:
                messagebox.showerror(
                    "Incorrect Password",
                    "The current password is incorrect.",
                    parent=self,
                )
        except Exception as exc:
            logger.exception("change_password failed: %s", exc)
            messagebox.showerror("Error", f"Failed to change password:\n{exc}", parent=self)


# ---------------------------------------------------------------------------
# Verify Password Dialog  (single-entry — used to unlock an operation)
# ---------------------------------------------------------------------------

class VerifyPasswordDialog(tk.Toplevel):
    """Simple modal dialog asking for the master password.

    Args:
        parent: Tkinter parent window.
        prompt: Descriptive text shown below the title.

    Returns (via ``password`` attribute):
        The entered password string if OK was clicked, ``None`` if cancelled.
    """

    def __init__(self, parent: tk.Widget, prompt: str = "Enter your master password:") -> None:
        super().__init__(parent)
        self.title("Master Password Required")
        self.resizable(False, False)
        self.password: Optional[str] = None

        self._build_ui(prompt)
        self.transient(parent)
        self.grab_set()
        _center(self, parent)
        self._entry.focus()

    def _build_ui(self, prompt: str) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text=prompt, wraplength=340, justify="left").pack(
            anchor="w", pady=(0, 12)
        )

        entry_row = ttk.Frame(outer)
        entry_row.pack(fill=tk.X, pady=(0, 14))
        ttk.Label(entry_row, text="Password:", width=10).pack(side=tk.LEFT)
        self._var = tk.StringVar()
        self._entry = ttk.Entry(
            entry_row, textvariable=self._var, show="\u2022", width=28
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._entry.bind("<Return>", lambda _: self._on_ok())

        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.RIGHT)

    def _on_ok(self) -> None:
        self.password = self._var.get()
        self.destroy()
