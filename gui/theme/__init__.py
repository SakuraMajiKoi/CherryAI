"""CherryAI GUI v2 Theme Package.

Provides theming utilities for the pastel blue and high-contrast color schemes.
"""

from CherryAI.gui.theme.colors import (
    ColorPalette,
    HIGH_CONTRAST_THEME,
    THEME,
    ThemeMode,
    apply_theme,
    get_theme,
    get_theme_mode,
    get_ttk_style_map,
    set_theme,
)
from CherryAI.gui.theme.icons import (
    ICONS,
    STEP_ICONS,
    Icons,
    get_log_level_icon,
    get_status_icon,
    get_step_icon,
)

__all__ = [
    # Colors
    "ColorPalette",
    "HIGH_CONTRAST_THEME",
    "THEME",
    "ThemeMode",
    "apply_theme",
    "get_theme",
    "get_theme_mode",
    "get_ttk_style_map",
    "set_theme",
    # Icons
    "ICONS",
    "STEP_ICONS",
    "Icons",
    "get_log_level_icon",
    "get_status_icon",
    "get_step_icon",
]
