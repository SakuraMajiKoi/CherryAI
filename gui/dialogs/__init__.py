"""CherryAI GUI v2 - Dialogs Package.

Provides modal dialogs for the GUI:
- GlobalOptionsDialog: Centralized application options
- ProjectNameDialog: New project creation (TASK 19)
- LoadManifestDialog: Load existing project (TASK 19)
"""

from CherryAI.gui.dialogs.global_options import (
    GlobalOptionsDialog,
    OptionSection,
    OptionCategory,
    LogLevel,
    ThemeMode,
    LineEnding,
    EncodingOption,
    APISettings,
    RequestSettings,
    CachingSettings,
    LoggingSettings,
    SessionSettings,
    SafetySettings,
    FileIOSettings,
    GlobalOptions,
    SECTION_DESCRIPTIONS,
    CATEGORY_ORDER,
    CATEGORY_NAMES,
    SECTION_NAMES,
    API_PROVIDERS,
    COMMON_BAN_TOKENS,
)

from CherryAI.gui.dialogs.project_dialog import (
    ProjectNameDialog,
    LoadManifestDialog,
)

from CherryAI.gui.dialogs.input_dialog import (
    UnifiedInputDialog,
)

__all__ = [
    "GlobalOptionsDialog",
    "OptionSection",
    "OptionCategory",
    "LogLevel",
    "ThemeMode",
    "LineEnding",
    "EncodingOption",
    "APISettings",
    "RequestSettings",
    "CachingSettings",
    "LoggingSettings",
    "SessionSettings",
    "SafetySettings",
    "FileIOSettings",
    "GlobalOptions",
    "SECTION_DESCRIPTIONS",
    "CATEGORY_ORDER",
    "CATEGORY_NAMES",
    "SECTION_NAMES",
    "API_PROVIDERS",
    "COMMON_BAN_TOKENS",
    # TASK 19: Project dialogs
    "ProjectNameDialog",
    "LoadManifestDialog",
    # PHASE 58.1: Unified input dialog
    "UnifiedInputDialog",
]
