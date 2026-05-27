"""CherryAI GUI theme colors and window preference helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import tkinter as tk
from typing import Any, Dict, Iterable



class ThemeMode(Enum):
    """Available theme modes."""

    PALE_BLUE = "pale_blue"
    PASTEL_BLUE = "pastel_blue"
    SLATE_GRAPHITE = "slate_graphite"
    MIDNIGHT_TEAL = "midnight_teal"
    CARBON_AMBER = "carbon_amber"
    HIGH_CONTRAST = "high_contrast"


@dataclass(frozen=True)
class ColorPalette:
    """Immutable color palette for the GUI theme."""

    # Primary colors - pastel blue spectrum
    primary: str = "#B8D4E8"  # Light pastel blue (main background)
    primary_light: str = "#D6E8F5"  # Lighter blue (secondary backgrounds)
    primary_dark: str = "#8BB8D4"  # Darker blue (borders, accents)

    # Background colors
    bg_main: str = "#E8F4FC"  # Main window background
    bg_panel: str = "#D6E8F5"  # Panel backgrounds
    bg_input: str = "#FFFFFF"  # Input fields
    bg_hover: str = "#C5DCF0"  # Hover state
    bg_selected: str = "#A8CCE8"  # Selected items
    bg_disabled: str = "#E0E8EE"  # Disabled state

    # Text colors
    text_primary: str = "#1A3A5C"  # Primary text (dark blue)
    text_secondary: str = "#4A6A8C"  # Secondary text
    text_disabled: str = "#8A9AAC"  # Disabled text
    text_inverse: str = "#FFFFFF"  # Text on dark backgrounds

    # Accent colors (no yellow/red)
    accent_success: str = "#6BBF8E"  # Green for success
    accent_info: str = "#5BA4D9"  # Blue for info
    accent_warning: str = "#7BA3C9"  # Muted blue for warnings (no yellow)
    accent_error: str = "#9B7B9E"  # Muted purple for errors (no red)

    # Status colors for progress tracker
    status_done: str = "#6BBF8E"  # Green checkmark
    status_partial: str = "#5BA4D9"  # Blue dash
    status_pending: str = "#8A9AAC"  # Grey X

    # Border colors
    border_light: str = "#C5DCF0"
    border_normal: str = "#8BB8D4"
    border_focus: str = "#5BA4D9"

    # Tab colors
    tab_active: str = "#FFFFFF"
    tab_inactive: str = "#D6E8F5"
    tab_hover: str = "#E8F4FC"

    # Button colors
    btn_primary_bg: str = "#5BA4D9"
    btn_primary_fg: str = "#FFFFFF"
    btn_secondary_bg: str = "#D6E8F5"
    btn_secondary_fg: str = "#1A3A5C"
    btn_disabled_bg: str = "#E0E8EE"
    btn_disabled_fg: str = "#8A9AAC"

    # Table and log surfaces
    table_even_bg: str = "#FFFFFF"
    table_odd_bg: str = "#D6E8F5"
    table_changed_bg: str = "#FFF3CD"
    table_match_bg: str = "#D4EDFF"
    diff_add_bg: str = "#D4F5D4"
    diff_del_bg: str = "#F5D4D4"
    log_sent_bg: str = "#F0F7FF"
    log_received_bg: str = "#F0FFF4"
    header_text: str = "#34495E"
    highlight_bg: str = "#FFEB3B"
    highlight_fg: str = "#000000"


PALE_BLUE_THEME = ColorPalette()

SLATE_GRAPHITE_THEME = ColorPalette(
    primary="#23282E",
    primary_light="#2D333B",
    primary_dark="#161B22",
    bg_main="#1B1F24",
    bg_panel="#252B33",
    bg_input="#11161C",
    bg_hover="#353C45",
    bg_selected="#45515E",
    bg_disabled="#20262D",
    text_primary="#F2F5F7",
    text_secondary="#CBD3D9",
    text_disabled="#7D8791",
    text_inverse="#101316",
    accent_success="#59C98A",
    accent_info="#6FA9FF",
    accent_warning="#8DB7FF",
    accent_error="#C28ACF",
    status_done="#59C98A",
    status_partial="#6FA9FF",
    status_pending="#7D8791",
    border_light="#36404A",
    border_normal="#475361",
    border_focus="#6FA9FF",
    tab_active="#303741",
    tab_inactive="#252B33",
    tab_hover="#39424D",
    btn_primary_bg="#6FA9FF",
    btn_primary_fg="#08111C",
    btn_secondary_bg="#303741",
    btn_secondary_fg="#F2F5F7",
    btn_disabled_bg="#20262D",
    btn_disabled_fg="#7D8791",
    table_even_bg="#20252B",
    table_odd_bg="#2A3037",
    table_changed_bg="#51462A",
    table_match_bg="#243A4D",
    diff_add_bg="#1F3A2D",
    diff_del_bg="#462C32",
    log_sent_bg="#162536",
    log_received_bg="#162D25",
    header_text="#D7E0E7",
    highlight_bg="#FFD24D",
    highlight_fg="#11161C",
)

MIDNIGHT_TEAL_THEME = ColorPalette(
    primary="#10242A",
    primary_light="#17323A",
    primary_dark="#0B171B",
    bg_main="#0F1B1F",
    bg_panel="#16272D",
    bg_input="#0A1316",
    bg_hover="#1F3941",
    bg_selected="#29515C",
    bg_disabled="#132026",
    text_primary="#F3FAFB",
    text_secondary="#C6DADD",
    text_disabled="#6E8A90",
    text_inverse="#081012",
    accent_success="#56D0A0",
    accent_info="#59C3D2",
    accent_warning="#84D3E0",
    accent_error="#D093B7",
    status_done="#56D0A0",
    status_partial="#59C3D2",
    status_pending="#6E8A90",
    border_light="#28434B",
    border_normal="#37606A",
    border_focus="#59C3D2",
    tab_active="#1B3238",
    tab_inactive="#16272D",
    tab_hover="#24464F",
    btn_primary_bg="#59C3D2",
    btn_primary_fg="#081012",
    btn_secondary_bg="#1E363D",
    btn_secondary_fg="#F3FAFB",
    btn_disabled_bg="#132026",
    btn_disabled_fg="#6E8A90",
    table_even_bg="#142227",
    table_odd_bg="#1B2D33",
    table_changed_bg="#4A4026",
    table_match_bg="#1F4250",
    diff_add_bg="#17372B",
    diff_del_bg="#3F2430",
    log_sent_bg="#103543",
    log_received_bg="#113126",
    header_text="#D7ECEE",
    highlight_bg="#FFE07A",
    highlight_fg="#081012",
)

CARBON_AMBER_THEME = ColorPalette(
    primary="#1F1C19",
    primary_light="#2B2622",
    primary_dark="#14110F",
    bg_main="#171412",
    bg_panel="#211C19",
    bg_input="#100D0B",
    bg_hover="#332B26",
    bg_selected="#4A3C30",
    bg_disabled="#1B1714",
    text_primary="#FBF4EC",
    text_secondary="#DCC8B4",
    text_disabled="#8C7A69",
    text_inverse="#120F0D",
    accent_success="#7ED39A",
    accent_info="#E5A85A",
    accent_warning="#F0BF7A",
    accent_error="#CE8DB4",
    status_done="#7ED39A",
    status_partial="#E5A85A",
    status_pending="#8C7A69",
    border_light="#3A312B",
    border_normal="#56473E",
    border_focus="#E5A85A",
    tab_active="#2A231F",
    tab_inactive="#211C19",
    tab_hover="#3B3028",
    btn_primary_bg="#E5A85A",
    btn_primary_fg="#120F0D",
    btn_secondary_bg="#342B25",
    btn_secondary_fg="#FBF4EC",
    btn_disabled_bg="#1B1714",
    btn_disabled_fg="#8C7A69",
    table_even_bg="#1B1714",
    table_odd_bg="#251F1B",
    table_changed_bg="#534124",
    table_match_bg="#4A321B",
    diff_add_bg="#213426",
    diff_del_bg="#452631",
    log_sent_bg="#33251A",
    log_received_bg="#1D2A22",
    header_text="#F0DED0",
    highlight_bg="#FFD08A",
    highlight_fg="#120F0D",
)

# High-contrast theme for accessibility (WCAG AAA compliant contrast ratios)
HIGH_CONTRAST_THEME = ColorPalette(
    # Primary colors - dark background with bright accents
    primary="#1A1A2E",  # Dark navy (main background)
    primary_light="#2D2D44",  # Lighter navy (secondary backgrounds)
    primary_dark="#0F0F1A",  # Darker navy (borders, accents)
    # Background colors
    bg_main="#1A1A2E",  # Dark navy main
    bg_panel="#2D2D44",  # Panel backgrounds
    bg_input="#0F0F1A",  # Input fields (very dark)
    bg_hover="#3D3D54",  # Hover state
    bg_selected="#4A4A6A",  # Selected items
    bg_disabled="#252538",  # Disabled state
    # Text colors - high contrast white/bright
    text_primary="#FFFFFF",  # Pure white for primary text
    text_secondary="#E0E0E0",  # Off-white for secondary
    text_disabled="#808080",  # Grey for disabled
    text_inverse="#000000",  # Black text on light backgrounds
    # Accent colors - bright, high-contrast (no yellow/red)
    accent_success="#00FF7F",  # Bright green (Spring Green)
    accent_info="#00BFFF",  # Deep Sky Blue
    accent_warning="#87CEEB",  # Sky Blue (muted, no yellow)
    accent_error="#DDA0DD",  # Plum (purple, no red)
    # Status colors - high visibility
    status_done="#00FF7F",  # Bright green
    status_partial="#00BFFF",  # Bright blue
    status_pending="#808080",  # Grey
    # Border colors - visible against dark bg
    border_light="#4A4A6A",
    border_normal="#6A6A8A",
    border_focus="#00BFFF",
    # Tab colors
    tab_active="#3D3D54",
    tab_inactive="#2D2D44",
    tab_hover="#4A4A6A",
    # Button colors - bright for visibility
    btn_primary_bg="#00BFFF",
    btn_primary_fg="#000000",
    btn_secondary_bg="#4A4A6A",
    btn_secondary_fg="#FFFFFF",
    btn_disabled_bg="#252538",
    btn_disabled_fg="#808080",
    table_even_bg="#161623",
    table_odd_bg="#24243A",
    table_changed_bg="#5A5220",
    table_match_bg="#1E415E",
    diff_add_bg="#173824",
    diff_del_bg="#4A1F2A",
    log_sent_bg="#13263A",
    log_received_bg="#143122",
    header_text="#FFFFFF",
    highlight_bg="#FFF176",
    highlight_fg="#000000",
)


_THEME_PRESETS: Dict[ThemeMode, ColorPalette] = {
    ThemeMode.PALE_BLUE: PALE_BLUE_THEME,
    ThemeMode.PASTEL_BLUE: PALE_BLUE_THEME,
    ThemeMode.SLATE_GRAPHITE: SLATE_GRAPHITE_THEME,
    ThemeMode.MIDNIGHT_TEAL: MIDNIGHT_TEAL_THEME,
    ThemeMode.CARBON_AMBER: CARBON_AMBER_THEME,
    ThemeMode.HIGH_CONTRAST: HIGH_CONTRAST_THEME,
}

_THEME_DISPLAY_NAMES: Dict[ThemeMode, str] = {
    ThemeMode.PALE_BLUE: "Pale Blue",
    ThemeMode.PASTEL_BLUE: "Pale Blue",
    ThemeMode.SLATE_GRAPHITE: "Slate Graphite",
    ThemeMode.MIDNIGHT_TEAL: "Midnight Teal",
    ThemeMode.CARBON_AMBER: "Carbon Amber",
    ThemeMode.HIGH_CONTRAST: "High Contrast",
}

_DISPLAY_NAME_TO_MODE: Dict[str, ThemeMode] = {
    name: mode for mode, name in _THEME_DISPLAY_NAMES.items()
}


class _ThemeProxy(ColorPalette):
    """Proxy object so imported THEME references stay live after theme changes."""

    def __getattribute__(self, name: str) -> Any:
        if name in ColorPalette.__dataclass_fields__:
            return getattr(_active_theme, name)
        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("THEME is read-only")

    def __eq__(self, other: object) -> bool:
        return _active_theme == other

    def __repr__(self) -> str:
        return f"ThemeProxy(mode={_active_theme_mode.value!r})"


THEME = _ThemeProxy()

# Current active theme (can be changed at runtime)
_active_theme: ColorPalette = PALE_BLUE_THEME
_active_theme_mode: ThemeMode = ThemeMode.PALE_BLUE


def coerce_theme_mode(value: ThemeMode | str | None) -> ThemeMode:
    """Convert stored values or labels into a ThemeMode."""
    if isinstance(value, ThemeMode):
        return value
    if not value:
        return ThemeMode.PALE_BLUE

    normalized = str(value).strip()
    if normalized in _DISPLAY_NAME_TO_MODE:
        return _DISPLAY_NAME_TO_MODE[normalized]

    legacy_map = {
        "pastel_blue": ThemeMode.PALE_BLUE,
        "light": ThemeMode.PALE_BLUE,
        "dark": ThemeMode.SLATE_GRAPHITE,
        "system": ThemeMode.PALE_BLUE,
    }
    normalized = normalized.lower()
    return legacy_map.get(normalized, ThemeMode(normalized) if normalized in ThemeMode._value2member_map_ else ThemeMode.PALE_BLUE)


def get_theme_display_name(mode: ThemeMode | str | None = None) -> str:
    """Return the user-facing name for a theme mode."""
    current_mode = _active_theme_mode if mode is None else coerce_theme_mode(mode)
    return _THEME_DISPLAY_NAMES[current_mode]


def get_theme_display_names() -> list[str]:
    """Return all available theme labels for GUI dropdowns."""
    return list(dict.fromkeys(_THEME_DISPLAY_NAMES.values()))


def get_theme_mode_from_display(label: str) -> ThemeMode:
    """Convert a dropdown label into a ThemeMode."""
    return coerce_theme_mode(label)


def get_theme() -> ColorPalette:
    """Get the currently active theme.

    Returns:
        The active ColorPalette instance.
    """
    return _active_theme


def get_theme_mode() -> ThemeMode:
    """Get the current theme mode.

    Returns:
        The active ThemeMode.
    """
    return _active_theme_mode


def set_theme(mode: ThemeMode) -> ColorPalette:
    """Set the active theme mode.

    Args:
        mode: The ThemeMode to activate.

    Returns:
        The newly activated ColorPalette.
    """
    global _active_theme, _active_theme_mode
    _active_theme_mode = coerce_theme_mode(mode)
    _active_theme = _THEME_PRESETS[_active_theme_mode]
    return _active_theme


def load_theme_from_ini() -> ColorPalette:
    """Load the persisted GUI design from CherryAI.ini."""
    from CherryAI.functions import ini_manager

    return set_theme(coerce_theme_mode(ini_manager.get_gui_design()))


def get_ttk_style_map(theme: ColorPalette | None = None) -> Dict[str, Dict[str, Any]]:
    """Get ttk style configuration for themed widgets.

    Args:
        theme: The ColorPalette to use. If None, uses the active theme.

    Returns:
        Dict mapping widget type to style configuration.
    """
    if theme is None:
        theme = _active_theme

    return {
        "TNotebook": {
            "configure": {
                "background": theme.bg_main,
                "tabmargins": [2, 5, 2, 0],
            },
        },
        "TNotebook.Tab": {
            "configure": {
                "background": theme.tab_inactive,
                "foreground": theme.text_primary,
                "padding": [12, 6],
            },
            "map": {
                "background": [
                    ("selected", theme.tab_active),
                    ("active", theme.tab_hover),
                ],
                "foreground": [
                    ("selected", theme.text_primary),
                    ("disabled", theme.text_disabled),
                ],
            },
        },
        "TFrame": {
            "configure": {
                "background": theme.bg_main,
            },
        },
        "TLabel": {
            "configure": {
                "background": theme.bg_main,
                "foreground": theme.text_primary,
            },
        },
        "TButton": {
            "configure": {
                "background": theme.btn_secondary_bg,
                "foreground": theme.btn_secondary_fg,
                "padding": [10, 5],
                "font": ("Segoe UI", 10),
            },
            "map": {
                "background": [
                    ("active", theme.bg_hover),
                    ("disabled", theme.btn_disabled_bg),
                ],
                "foreground": [
                    ("disabled", theme.btn_disabled_fg),
                ],
            },
        },
        "Primary.TButton": {
            "configure": {
                "background": theme.btn_primary_bg,
                "foreground": theme.btn_primary_fg,
                "padding": [10, 5],
                "font": ("Segoe UI", 10),
            },
            "map": {
                "background": [
                    ("active", theme.bg_hover),
                    ("disabled", theme.btn_disabled_bg),
                ],
                "foreground": [
                    ("disabled", theme.btn_disabled_fg),
                ],
            },
        },
        "Accent.TButton": {
            "configure": {
                "background": theme.accent_success,
                "foreground": theme.text_inverse,
                "padding": [12, 6],
                "font": ("Segoe UI", 10, "bold"),
            },
            "map": {
                "background": [
                    ("active", theme.accent_info),
                    ("disabled", theme.btn_disabled_bg),
                ],
                "foreground": [
                    ("disabled", theme.btn_disabled_fg),
                ],
            },
        },
        "Danger.TButton": {
            "configure": {
                "background": "#C62828",
                "foreground": theme.text_inverse,
                "padding": [12, 6],
                "font": ("Segoe UI", 10, "bold"),
            },
            "map": {
                "background": [
                    ("active", "#A61B1B"),
                    ("disabled", theme.btn_disabled_bg),
                ],
                "foreground": [
                    ("disabled", theme.btn_disabled_fg),
                ],
            },
        },
        "TEntry": {
            "configure": {
                "fieldbackground": theme.bg_input,
                "foreground": theme.text_primary,
            },
            "map": {
                "fieldbackground": [
                    ("disabled", theme.bg_disabled),
                ],
            },
        },
        "TLabelframe": {
            "configure": {
                "background": theme.bg_panel,
            },
        },
        "TLabelframe.Label": {
            "configure": {
                "background": theme.bg_panel,
                "foreground": theme.text_primary,
            },
        },
        "Treeview": {
            "configure": {
                "background": theme.table_even_bg,
                "foreground": theme.text_primary,
                "fieldbackground": theme.table_even_bg,
            },
            "map": {
                "background": [
                    ("selected", theme.bg_selected),
                ],
                "foreground": [
                    ("selected", theme.text_primary),
                ],
            },
        },
        "TProgressbar": {
            "configure": {
                "background": theme.accent_info,
                "troughcolor": theme.bg_disabled,
            },
        },
        "Horizontal.TProgressbar": {
            "configure": {
                "background": theme.accent_info,
                "troughcolor": theme.bg_disabled,
            },
        },
        # Checkbox styling - light blue theme
        "TCheckbutton": {
            "configure": {
                "background": theme.bg_main,
                "foreground": theme.text_primary,
                "indicatorbackground": theme.bg_input,
                "indicatorforeground": theme.accent_info,
            },
            "map": {
                "background": [
                    ("active", theme.bg_hover),
                    ("disabled", theme.bg_disabled),
                ],
                "foreground": [
                    ("disabled", theme.text_disabled),
                ],
                "indicatorbackground": [
                    ("selected", theme.accent_info),
                    ("disabled", theme.bg_disabled),
                ],
            },
        },
        # Radiobutton styling - light blue theme
        "TRadiobutton": {
            "configure": {
                "background": theme.bg_main,
                "foreground": theme.text_primary,
                "indicatorbackground": theme.bg_input,
                "indicatorforeground": theme.accent_info,
            },
            "map": {
                "background": [
                    ("active", theme.bg_hover),
                    ("disabled", theme.bg_disabled),
                ],
                "foreground": [
                    ("disabled", theme.text_disabled),
                ],
                "indicatorbackground": [
                    ("selected", theme.accent_info),
                    ("disabled", theme.bg_disabled),
                ],
            },
        },
        # Combobox styling - light blue theme
        "TCombobox": {
            "configure": {
                "background": theme.bg_input,
                "foreground": theme.text_primary,
                "fieldbackground": theme.bg_input,
                "selectbackground": theme.bg_selected,
                "selectforeground": theme.text_primary,
                "arrowcolor": theme.accent_info,
            },
            "map": {
                "fieldbackground": [
                    ("readonly", theme.bg_input),
                    ("disabled", theme.bg_disabled),
                ],
                "background": [
                    ("active", theme.bg_hover),
                    ("disabled", theme.bg_disabled),
                ],
                "arrowcolor": [
                    ("disabled", theme.text_disabled),
                ],
            },
        },
        # Spinbox styling - light blue theme
        "TSpinbox": {
            "configure": {
                "background": theme.bg_input,
                "foreground": theme.text_primary,
                "fieldbackground": theme.bg_input,
                "arrowcolor": theme.accent_info,
            },
            "map": {
                "fieldbackground": [
                    ("disabled", theme.bg_disabled),
                ],
                "arrowcolor": [
                    ("disabled", theme.text_disabled),
                ],
            },
        },
        # Scale (slider) styling - light blue theme
        "TScale": {
            "configure": {
                "background": theme.bg_main,
                "troughcolor": theme.bg_disabled,
                "sliderlength": 20,
            },
        },
        "Horizontal.TScale": {
            "configure": {
                "background": theme.bg_main,
                "troughcolor": theme.bg_panel,
                "sliderlength": 20,
            },
        },
        "Vertical.TScale": {
            "configure": {
                "background": theme.bg_main,
                "troughcolor": theme.bg_panel,
                "sliderlength": 20,
            },
        },
        # Scrollbar styling - light blue theme
        "TScrollbar": {
            "configure": {
                "background": theme.bg_panel,
                "troughcolor": theme.bg_main,
                "arrowcolor": theme.text_secondary,
            },
            "map": {
                "background": [
                    ("active", theme.bg_hover),
                    ("disabled", theme.bg_disabled),
                ],
            },
        },
    }


def _safe_configure(widget: tk.Misc, **options: Any) -> None:
    """Configure a widget while ignoring unsupported Tk options."""
    for key, value in options.items():
        try:
            widget.configure(**{key: value})
        except tk.TclError:
            continue


def _apply_classic_widget_theme(widget: tk.Misc, theme: ColorPalette) -> None:
    """Apply colors to classic Tk widgets recursively."""
    if widget.winfo_class() in {"TFrame", "TLabel", "TButton", "TEntry", "Treeview"}:
        return

    base_bg = theme.bg_main
    if isinstance(widget, (tk.LabelFrame, tk.PanedWindow)):
        _safe_configure(widget, bg=theme.bg_panel, highlightbackground=theme.border_light)
    elif isinstance(widget, (tk.Frame, tk.Toplevel, tk.Tk)):
        _safe_configure(widget, bg=theme.bg_main)
    elif isinstance(widget, (tk.Label, tk.Message)):
        _safe_configure(widget, bg=base_bg, fg=theme.text_primary)
    elif isinstance(widget, (tk.Button, tk.Checkbutton, tk.Radiobutton)):
        _safe_configure(
            widget,
            bg=theme.btn_secondary_bg,
            fg=theme.btn_secondary_fg,
            activebackground=theme.bg_hover,
            activeforeground=theme.text_primary,
            disabledforeground=theme.text_disabled,
            selectcolor=theme.bg_input,
            highlightbackground=theme.border_light,
        )
    elif isinstance(widget, (tk.Entry, tk.Spinbox, tk.Listbox)):
        _safe_configure(
            widget,
            bg=theme.bg_input,
            fg=theme.text_primary,
            insertbackground=theme.text_primary,
            selectbackground=theme.bg_selected,
            selectforeground=theme.text_primary,
            disabledbackground=theme.bg_disabled,
            disabledforeground=theme.text_disabled,
            readonlybackground=theme.bg_input,
            highlightbackground=theme.border_light,
            highlightcolor=theme.border_focus,
        )
    elif isinstance(widget, tk.Text):
        _safe_configure(
            widget,
            bg=theme.bg_input,
            fg=theme.text_primary,
            insertbackground=theme.text_primary,
            selectbackground=theme.bg_selected,
            selectforeground=theme.text_primary,
            highlightbackground=theme.border_light,
            highlightcolor=theme.border_focus,
        )
    elif isinstance(widget, tk.Canvas):
        _safe_configure(widget, bg=theme.bg_main, highlightbackground=theme.border_light)
    elif isinstance(widget, tk.Scrollbar):
        _safe_configure(
            widget,
            bg=theme.bg_panel,
            troughcolor=theme.bg_main,
            activebackground=theme.bg_hover,
            highlightbackground=theme.border_light,
        )
    elif isinstance(widget, tk.Menu):
        _safe_configure(
            widget,
            bg=theme.bg_panel,
            fg=theme.text_primary,
            activebackground=theme.bg_hover,
            activeforeground=theme.text_primary,
        )

    for child in widget.winfo_children():
        _apply_classic_widget_theme(child, theme)


def _configure_combobox_popdown(root: tk.Misc, theme: ColorPalette) -> None:
    """Set option database colors used by the Tk combobox popdown list."""
    try:
        root.option_add("*TCombobox*Listbox.background", theme.bg_input)
        root.option_add("*TCombobox*Listbox.foreground", theme.text_primary)
        root.option_add("*TCombobox*Listbox.selectBackground", theme.bg_selected)
        root.option_add("*TCombobox*Listbox.selectForeground", theme.text_primary)
    except tk.TclError:
        pass


def _set_window_maximized(window: tk.Misc) -> None:
    """Best-effort window maximization across Tk variants."""
    for setter in (
        lambda: window.state("zoomed"),
        lambda: window.attributes("-zoomed", True),
    ):
        try:
            setter()
            return
        except tk.TclError:
            continue


def _center_on_parent(window: tk.Misc, parent: tk.Misc | None) -> None:
    """Center a window on its parent or screen."""
    try:
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        if parent is not None:
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        else:
            x = (window.winfo_screenwidth() - width) // 2
            y = (window.winfo_screenheight() - height) // 2
        window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    except tk.TclError:
        pass


def _save_window_geometry(window: tk.Misc, window_key: str) -> None:
    """Persist the current geometry for a window if normal-sized."""
    from CherryAI.functions import ini_manager

    try:
        if not ini_manager.get_save_window_dimensions():
            return
        state = window.state()
        ini_manager.set_window_state(window_key, state)
        if state == "normal":
            ini_manager.set_window_geometry(window_key, window.geometry())
    except tk.TclError:
        return


def register_window_preferences(window: tk.Misc, window_key: str) -> None:
    """Bind geometry persistence handlers for a themed window."""
    if getattr(window, "_cherry_window_pref_key", None) == window_key:
        return

    setattr(window, "_cherry_window_pref_key", window_key)
    setattr(window, "_cherry_window_pref_job", None)

    def _on_configure(_event: tk.Event) -> None:
        from CherryAI.functions import ini_manager

        if not ini_manager.get_save_window_dimensions():
            return
        current_job = getattr(window, "_cherry_window_pref_job", None)
        if current_job is not None:
            try:
                window.after_cancel(current_job)
            except tk.TclError:
                pass
        try:
            job = window.after(250, lambda: _save_window_geometry(window, window_key))
            setattr(window, "_cherry_window_pref_job", job)
        except tk.TclError:
            pass

    def _on_destroy(_event: tk.Event) -> None:
        if getattr(_event, "widget", None) is not window:
            return
        current_job = getattr(window, "_cherry_window_pref_job", None)
        if current_job is not None:
            try:
                window.after_cancel(current_job)
            except tk.TclError:
                pass
            setattr(window, "_cherry_window_pref_job", None)
        _save_window_geometry(window, window_key)

    window.bind("<Configure>", _on_configure, add="+")
    window.bind("<Destroy>", _on_destroy, add="+")


def apply_window_preferences(
    window: tk.Misc,
    *,
    parent: tk.Misc | None = None,
    window_key: str | None = None,
    default_geometry: str | None = None,
    center_on_parent: bool = False,
) -> None:
    """Apply theme plus persisted geometry/maximize behavior to a window."""
    from CherryAI.functions import ini_manager

    theme = get_theme()
    apply_theme(window, theme=theme)

    resolved_key = window_key or window.__class__.__name__
    if default_geometry:
        try:
            window.geometry(default_geometry)
        except tk.TclError:
            pass

    if ini_manager.get_launch_maximized():
        _set_window_maximized(window)
    else:
        saved_geometry = ini_manager.get_window_geometry(resolved_key)
        if saved_geometry and ini_manager.get_save_window_dimensions():
            try:
                window.geometry(saved_geometry)
            except tk.TclError:
                if center_on_parent:
                    _center_on_parent(window, parent)
        elif center_on_parent:
            _center_on_parent(window, parent)

    register_window_preferences(window, resolved_key)


def apply_theme(root, theme: ColorPalette | None = None) -> None:
    """Apply a theme to a Tkinter root window.

    Args:
        root: The Tkinter root window or Toplevel.
        theme: The ColorPalette to apply. If None, uses the active theme.
    """
    from tkinter import ttk

    if theme is None:
        theme = _active_theme

    style = ttk.Style(root)

    # Use clam theme as base (more customizable than default)
    style.theme_use("clam")

    # Apply custom styles
    style_map = get_ttk_style_map(theme)
    for widget_name, config in style_map.items():
        if "configure" in config:
            style.configure(widget_name, **config["configure"])
        if "map" in config:
            style.map(widget_name, **config["map"])

    # Set root window background
    root.configure(bg=theme.bg_main)
    _configure_combobox_popdown(root, theme)
    _apply_classic_widget_theme(root, theme)


# =============================================================================
# Style Name Helpers
# =============================================================================


def get_widget_style_name(widget_type: str) -> str:
    """Get the ttk style name for a widget type.
    
    Args:
        widget_type: Widget type (e.g., "checkbox", "button", "combobox")
        
    Returns:
        The ttk style name (e.g., "TCheckbutton")
    """
    style_map = {
        "checkbox": "TCheckbutton",
        "checkbutton": "TCheckbutton",
        "radio": "TRadiobutton",
        "radiobutton": "TRadiobutton",
        "button": "TButton",
        "primary_button": "Primary.TButton",
        "entry": "TEntry",
        "combobox": "TCombobox",
        "spinbox": "TSpinbox",
        "scale": "TScale",
        "slider": "TScale",
        "horizontal_scale": "Horizontal.TScale",
        "vertical_scale": "Vertical.TScale",
        "progressbar": "TProgressbar",
        "scrollbar": "TScrollbar",
        "treeview": "Treeview",
        "frame": "TFrame",
        "label": "TLabel",
        "labelframe": "TLabelframe",
        "notebook": "TNotebook",
    }
    return style_map.get(widget_type.lower(), f"T{widget_type.title()}")


def get_themed_colors() -> Dict[str, str]:
    """Get a dictionary of themed colors for use in custom widgets.
    
    Returns:
        Dictionary mapping color names to hex values.
    """
    theme = get_theme()
    return {
        "primary": theme.primary,
        "primary_light": theme.primary_light,
        "primary_dark": theme.primary_dark,
        "bg_main": theme.bg_main,
        "bg_panel": theme.bg_panel,
        "bg_input": theme.bg_input,
        "bg_hover": theme.bg_hover,
        "bg_selected": theme.bg_selected,
        "bg_disabled": theme.bg_disabled,
        "text_primary": theme.text_primary,
        "text_secondary": theme.text_secondary,
        "text_disabled": theme.text_disabled,
        "accent_info": theme.accent_info,
        "accent_success": theme.accent_success,
        "border_light": theme.border_light,
        "border_normal": theme.border_normal,
        "border_focus": theme.border_focus,
        "table_even_bg": theme.table_even_bg,
        "table_odd_bg": theme.table_odd_bg,
        "table_changed_bg": theme.table_changed_bg,
        "table_match_bg": theme.table_match_bg,
        "diff_add_bg": theme.diff_add_bg,
        "diff_del_bg": theme.diff_del_bg,
        "log_sent_bg": theme.log_sent_bg,
        "log_received_bg": theme.log_received_bg,
        "highlight_bg": theme.highlight_bg,
        "highlight_fg": theme.highlight_fg,
    }
