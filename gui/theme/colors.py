"""CherryAI GUI v2 Theme - Color Palette.

Provides pastel blue color scheme following the design ethos:
- Light/pastel blue base color
- Avoid dull grey/white monotony
- No yellow/red colors
- Modern, clean, professional appearance

Also provides high-contrast theme for accessibility.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, NamedTuple, Any



class ThemeMode(Enum):
    """Available theme modes."""

    PASTEL_BLUE = "pastel_blue"
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


# Default pastel blue theme
THEME = ColorPalette()

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
)

# Current active theme (can be changed at runtime)
_active_theme: ColorPalette = THEME
_active_theme_mode: ThemeMode = ThemeMode.PASTEL_BLUE


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
    _active_theme_mode = mode
    if mode == ThemeMode.HIGH_CONTRAST:
        _active_theme = HIGH_CONTRAST_THEME
    else:
        _active_theme = THEME
    return _active_theme


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
                "background": theme.bg_input,
                "foreground": theme.text_primary,
                "fieldbackground": theme.bg_input,
            },
            "map": {
                "background": [
                    ("selected", theme.bg_selected),
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
    }
