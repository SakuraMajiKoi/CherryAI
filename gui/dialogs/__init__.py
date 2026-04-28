"""CherryAI GUI v2 - Dialogs Package.

Provides dialogs for the GUI:
- GlobalOptionsDialog: Centralized application options
- ProjectNameDialog: New project creation (TASK 19)
- LoadManifestDialog: Load existing project (TASK 19)
- PatchEditorViewDialog: Shared Editor host / Full Files surface
- EditorDialog: Alias for the recycled PatchEditorViewDialog host
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
    LimitSettings,
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

try:
    from CherryAI.gui.dialogs.patch_editor_view import (
        PatchEditorViewDialog,
    )
except ImportError:
    PatchEditorViewDialog = None

try:
    from CherryAI.gui.dialogs.ledger_view import (
        LedgerViewDialog,
    )
except ImportError:
    LedgerViewDialog = None

try:
    from CherryAI.gui.dialogs.regex_help_view import (
        RegexHelpDialog,
    )
except ImportError:
    RegexHelpDialog = None

EditorDialog = PatchEditorViewDialog

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
    "LimitSettings",
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

if PatchEditorViewDialog is not None:
    __all__.append("PatchEditorViewDialog")
if EditorDialog is not None:
    __all__.append("EditorDialog")
if LedgerViewDialog is not None:
    __all__.append("LedgerViewDialog")
if RegexHelpDialog is not None:
    __all__.append("RegexHelpDialog")
