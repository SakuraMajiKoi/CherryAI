"""Tooltip helper for CherryAI GUI (TASK 17.10).

Provides a consistent tooltip implementation that can be attached/detached
to any tkinter widget, respects the tooltips_enabled flag, and optionally
uses i18n translation keys.

Usage:
    from CherryAI.gui.helpers.tooltip import attach_tooltip, detach_tooltip

    attach_tooltip(my_button, "This is a helpful tooltip")
    attach_tooltip(my_label, "tooltip.batch_mode", use_i18n=True)
    detach_tooltip(my_button)
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_tooltips_enabled: bool = True
_tooltip_delay_ms: int = 500  # Milliseconds before showing tooltip
_tooltip_wrap_length: int = 300  # Max tooltip text width in pixels

# Private tag used to track tooltip bindings on widgets
_TOOLTIP_ATTR = "_cherry_tooltip"
_TOOLTIP_AFTER_ATTR = "_cherry_tooltip_after"

# Default colours (overridden by THEME import if available)
_BG_COLOR = "#333333"
_FG_COLOR = "#FFFFFF"

try:
    from CherryAI.gui.theme.colors import THEME
    _BG_COLOR = THEME.bg_panel
    _FG_COLOR = THEME.text_primary
except Exception:
    pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_tooltips_enabled(enabled: bool) -> None:
    """Enable or disable tooltips globally.

    When disabled, no new tooltips will appear, and existing visible
    tooltips are hidden.

    Args:
        enabled: True to enable tooltips, False to disable.
    """
    global _tooltips_enabled
    _tooltips_enabled = enabled
    logger.debug("Tooltips %s", "enabled" if enabled else "disabled")


def are_tooltips_enabled() -> bool:
    """Return whether tooltips are currently enabled."""
    return _tooltips_enabled


def set_tooltip_delay(delay_ms: int) -> None:
    """Set the delay before a tooltip appears.

    Args:
        delay_ms: Delay in milliseconds (default 500).
    """
    global _tooltip_delay_ms
    _tooltip_delay_ms = max(0, delay_ms)


def attach_tooltip(
    widget: tk.Widget,
    text: str,
    use_i18n: bool = False,
    delay_ms: Optional[int] = None,
    wrap_length: Optional[int] = None,
) -> None:
    """Attach a tooltip to a widget.

    Args:
        widget: Tkinter widget to attach the tooltip to.
        text: Tooltip text, or an i18n key if use_i18n=True.
        use_i18n: If True, look up `text` as an i18n key via functions.i18n.t().
        delay_ms: Override the global delay for this tooltip.
        wrap_length: Override the wrap length for this tooltip.
    """
    # Remove any existing tooltip first
    detach_tooltip(widget)

    delay = delay_ms if delay_ms is not None else _tooltip_delay_ms
    wrap = wrap_length if wrap_length is not None else _tooltip_wrap_length

    def _resolve_text() -> str:
        if use_i18n:
            try:
                from CherryAI.functions.i18n import t
                return t(text)
            except Exception:
                return text
        return text

    def _on_enter(event: tk.Event) -> None:
        if not _tooltips_enabled:
            return
        # Schedule tooltip display after delay
        after_id = widget.after(delay, lambda: _show_tooltip(widget, event, _resolve_text(), wrap))
        setattr(widget, _TOOLTIP_AFTER_ATTR, after_id)

    def _on_leave(event: tk.Event) -> None:
        _cancel_pending(widget)
        _hide_tooltip(widget)

    def _on_click(event: tk.Event) -> None:
        _cancel_pending(widget)
        _hide_tooltip(widget)

    widget.bind("<Enter>", _on_enter, add="+")
    widget.bind("<Leave>", _on_leave, add="+")
    widget.bind("<Button>", _on_click, add="+")

    # Store metadata for detach
    setattr(widget, _TOOLTIP_ATTR, {
        "text": text,
        "use_i18n": use_i18n,
        "bindings": ["<Enter>", "<Leave>", "<Button>"],
    })


def detach_tooltip(widget: tk.Widget) -> None:
    """Remove a tooltip from a widget.

    Args:
        widget: Widget to remove the tooltip from.
    """
    _cancel_pending(widget)
    _hide_tooltip(widget)

    info = getattr(widget, _TOOLTIP_ATTR, None)
    if info is not None:
        delattr(widget, _TOOLTIP_ATTR)


def get_tooltip_text(widget: tk.Widget) -> Optional[str]:
    """Return the tooltip text attached to a widget, or None.

    Args:
        widget: Widget to inspect.

    Returns:
        The raw tooltip text, or None if no tooltip attached.
    """
    info = getattr(widget, _TOOLTIP_ATTR, None)
    if info is None:
        return None
    return info.get("text")


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _show_tooltip(
    widget: tk.Widget,
    event: tk.Event,
    text: str,
    wrap_length: int,
) -> None:
    """Display the tooltip popup near the widget."""
    if not _tooltips_enabled:
        return

    # Don't show if tooltip already visible
    existing = getattr(widget, "_cherry_tooltip_win", None)
    if existing is not None:
        return

    try:
        x = event.x_root + 12
        y = event.y_root + 12

        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")

        # Prevent tooltip from receiving focus
        tip.wm_attributes("-topmost", True)

        label = ttk.Label(
            tip,
            text=text,
            background=_BG_COLOR,
            foreground=_FG_COLOR,
            padding=(6, 4),
            wraplength=wrap_length,
        )
        label.pack()

        setattr(widget, "_cherry_tooltip_win", tip)
    except tk.TclError:
        pass  # Widget may have been destroyed


def _hide_tooltip(widget: tk.Widget) -> None:
    """Destroy the tooltip popup if visible."""
    tip = getattr(widget, "_cherry_tooltip_win", None)
    if tip is not None:
        try:
            tip.destroy()
        except tk.TclError:
            pass
        setattr(widget, "_cherry_tooltip_win", None)


def _cancel_pending(widget: tk.Widget) -> None:
    """Cancel a pending tooltip display."""
    after_id = getattr(widget, _TOOLTIP_AFTER_ATTR, None)
    if after_id is not None:
        try:
            widget.after_cancel(after_id)
        except (tk.TclError, ValueError):
            pass
        setattr(widget, _TOOLTIP_AFTER_ATTR, None)
