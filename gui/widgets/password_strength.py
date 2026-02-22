"""Password Strength Meter Widget.

A reusable Tkinter widget that shows a password entry field coupled with a
real-time strength indicator based on the HiveSystems 2025 bcrypt crack-time
table (WF-10, 12× RTX 5090).

Usage
-----
::

    from CherryAI.gui.widgets.password_strength import PasswordStrengthWidget

    widget = PasswordStrengthWidget(parent_frame)
    widget.pack(fill="x", pady=5)

    # Read the entered password
    pw = widget.get()

    # Bind <Return> on the entry
    widget.bind_entry("<Return>", my_callback)

Strength tiers
--------------
+----------+---------+-------------------------------------------+
| Tier     | Colour  | Condition                                 |
+==========+=========+===========================================+
| Instantly| Purple  | < 8 characters                            |
+----------+---------+-------------------------------------------+
| Weak     | Red     | 8 chars, numbers/lowercase only           |
+----------+---------+-------------------------------------------+
| Good     | Orange  | Everything else below Great               |
+----------+---------+-------------------------------------------+
| Great    | Yellow  | 12+ chars with ≥ 3 character types       |
+----------+---------+-------------------------------------------+
| Safe     | Green   | 16+ chars, or 12+ with all 4 types       |
+----------+---------+-------------------------------------------+
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from CherryAI.functions.api_config import PasswordStrength


class PasswordStrengthWidget(ttk.Frame):
    """Combined password entry + real-time HiveSystems strength meter.

    Args:
        parent: Tkinter parent widget.
        show_label: Whether to show the field label on the left.
        label_text: Text shown in the label (only if *show_label* is True).
        label_width: Character width of the label column.
        entry_width: Character width of the password entry.
        on_change: Optional callback called ``on_change(password: str)``
            whenever the entered text changes.
        **kwargs: Extra keyword arguments passed to :class:`ttk.Frame`.

    Attributes:
        strength_var: :class:`tk.StringVar` exposing the current tier label.
        colour_var: :class:`tk.StringVar` exposing the current hex colour.

    Example::

        def _on_pw_change(pw: str) -> None:
            ok_btn.configure(state="normal" if len(pw) >= 8 else "disabled")

        widget = PasswordStrengthWidget(
            frame,
            label_text="New password:",
            on_change=_on_pw_change,
        )
        widget.pack(fill="x")
    """

    # Inert "empty" colours
    _EMPTY_BG = "#cccccc"
    _EMPTY_FG = "gray"
    _EMPTY_TEXT = "Enter a password"

    def __init__(
        self,
        parent: tk.Widget,
        *,
        show_label: bool = True,
        label_text: str = "Password:",
        label_width: int = 14,
        entry_width: int = 28,
        on_change: Optional[Callable[[str], None]] = None,
        **kwargs: object,
    ) -> None:
        super().__init__(parent, **kwargs)

        self._on_change = on_change
        self._show_var = tk.BooleanVar(value=False)
        self._password_var = tk.StringVar()

        # Public state vars (read-only; update on every keypress)
        self.strength_var = tk.StringVar(value="")
        self.colour_var = tk.StringVar(value=self._EMPTY_BG)

        self._build_ui(show_label, label_text, label_width, entry_width)

        # React to every keystroke
        self._password_var.trace_add("write", self._on_password_change)

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _build_ui(
        self,
        show_label: bool,
        label_text: str,
        label_width: int,
        entry_width: int,
    ) -> None:
        """Construct entry row and strength indicator row."""
        # ---- Entry row -----------------------------------------------
        entry_row = ttk.Frame(self)
        entry_row.pack(fill=tk.X)

        if show_label:
            ttk.Label(entry_row, text=label_text, width=label_width, anchor="w").pack(
                side=tk.LEFT
            )

        self._entry = ttk.Entry(
            entry_row,
            textvariable=self._password_var,
            show="\u2022",   # bullet (•)
            width=entry_width,
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        ttk.Checkbutton(
            entry_row,
            text="Show",
            variable=self._show_var,
            command=self._toggle_show,
        ).pack(side=tk.LEFT)

        # ---- Strength indicator row ----------------------------------
        meter_row = ttk.Frame(self)
        meter_row.pack(fill=tk.X, pady=(2, 0))

        # Spacer that lines up the meter under the entry (not the label)
        if show_label:
            ttk.Label(meter_row, text="", width=label_width).pack(side=tk.LEFT)

        # Coloured block: a plain tk.Label used as a filled rectangle
        self._colour_block = tk.Label(
            meter_row,
            text="",
            width=2,
            bg=self._EMPTY_BG,
            relief="flat",
        )
        self._colour_block.pack(side=tk.LEFT, padx=(0, 6), ipadx=4, ipady=4)

        # Strength text (tier name + char/type counts)
        self._strength_label = ttk.Label(
            meter_row,
            text=self._EMPTY_TEXT,
            foreground=self._EMPTY_FG,
        )
        self._strength_label.pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _toggle_show(self) -> None:
        """Toggle plain-text / bullet display on the entry."""
        self._entry.configure(show="" if self._show_var.get() else "\u2022")

    def _on_password_change(self, *_args: object) -> None:
        """Recompute and display password strength on every change."""
        password = self._password_var.get()

        if not password:
            self._colour_block.configure(bg=self._EMPTY_BG)
            self._strength_label.configure(
                text=self._EMPTY_TEXT, foreground=self._EMPTY_FG
            )
            self.strength_var.set("")
            self.colour_var.set(self._EMPTY_BG)
            if self._on_change:
                self._on_change(password)
            return

        tier, colour = PasswordStrength.assess(password)
        text = PasswordStrength.meter_text(password)

        self._colour_block.configure(bg=colour)
        self._strength_label.configure(text=text, foreground=colour)
        self.strength_var.set(tier)
        self.colour_var.set(colour)

        if self._on_change:
            self._on_change(password)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self) -> str:
        """Return the currently entered password."""
        return self._password_var.get()

    def set(self, value: str) -> None:
        """Programmatically set the password field content."""
        self._password_var.set(value)

    def clear(self) -> None:
        """Clear the password field."""
        self._password_var.set("")

    def focus(self) -> None:
        """Move keyboard focus to the entry widget."""
        self._entry.focus()

    def bind_entry(self, event: str, callback: Callable) -> None:
        """Bind *event* to the underlying :class:`ttk.Entry` widget.

        Args:
            event: Tkinter event string, e.g. ``"<Return>"``.
            callback: Callable invoked when the event fires.

        Example::

            widget.bind_entry("<Return>", lambda e: dialog.ok())
        """
        self._entry.bind(event, callback)

    def configure_entry(self, **kwargs: object) -> None:
        """Forward keyword arguments to the internal :class:`ttk.Entry`.

        Useful for disabling or re-enabling the entry::

            widget.configure_entry(state="disabled")
        """
        self._entry.configure(**kwargs)
