"""CherryAI GUI v2 State Management Package.

Provides session state, undo/redo, autosave, and preset functionality.
"""

from CherryAI.gui.state.store import (
    SessionState,
    StepState,
    UndoAction,
    STEP_DEFINITIONS,
    PRESET_DEFINITIONS,
    get_session,
    reset_session,
    load_session_from_autosave,
    get_preset_definitions,
    get_preset_names,
)

__all__ = [
    "SessionState",
    "StepState",
    "UndoAction",
    "STEP_DEFINITIONS",
    "PRESET_DEFINITIONS",
    "get_session",
    "reset_session",
    "load_session_from_autosave",
    "get_preset_definitions",
    "get_preset_names",
]
