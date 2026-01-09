"""CherryAI GUI v2 Theme - Icon Constants.

Provides Unicode/emoji icons for:
- Workflow step indicators
- Status indicators (done, partial, pending)
- Button icons
- Common UI elements

Uses Unicode symbols that render well across platforms.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Icons:
    """Immutable icon set for GUI elements.

    Uses Unicode symbols that work across Windows, macOS, and Linux.
    Avoids emojis that may not render consistently in Tkinter.
    """

    # Step status indicators
    STATUS_DONE: str = "✓"  # Checkmark
    STATUS_PARTIAL: str = "◐"  # Half-filled circle
    STATUS_PENDING: str = "○"  # Empty circle
    STATUS_RUNNING: str = "◉"  # Filled circle with ring
    STATUS_FAILED: str = "✗"  # X mark
    STATUS_SKIPPED: str = "⊘"  # Slashed circle

    # Translation status per line
    LINE_PENDING: str = "○"  # Empty circle
    LINE_TRANSLATING: str = "◐"  # Half-filled
    LINE_COMPLETED: str = "✓"  # Checkmark
    LINE_FAILED: str = "✗"  # X mark
    LINE_SKIPPED: str = "⊘"  # Slashed circle

    # Workflow step icons (numbered 1-10)
    STEP_INPUT: str = "📁"  # Folder
    STEP_ANALYSIS: str = "🔍"  # Magnifying glass
    STEP_INFORMATION: str = "ℹ"  # Info
    STEP_PREPROCESS: str = "⚙"  # Gear
    STEP_ESTIMATE: str = "💰"  # Money bag (cost)
    STEP_TRANSLATE: str = "🌐"  # Globe
    STEP_QA: str = "✓"  # Check
    STEP_POSTPROCESS: str = "🔧"  # Wrench
    STEP_WORDWRAP: str = "↩"  # Return arrow
    STEP_OUTPUT: str = "💾"  # Floppy disk

    # Navigation icons
    NAV_PREV: str = "◀"  # Left triangle
    NAV_NEXT: str = "▶"  # Right triangle
    NAV_UP: str = "▲"  # Up triangle
    NAV_DOWN: str = "▼"  # Down triangle
    NAV_FIRST: str = "⏮"  # Skip to start
    NAV_LAST: str = "⏭"  # Skip to end

    # Action icons
    ACTION_ADD: str = "+"  # Plus
    ACTION_REMOVE: str = "−"  # Minus
    ACTION_EDIT: str = "✎"  # Pencil
    ACTION_DELETE: str = "🗑"  # Trash
    ACTION_SAVE: str = "💾"  # Floppy
    ACTION_LOAD: str = "📂"  # Open folder
    ACTION_REFRESH: str = "↻"  # Refresh
    ACTION_UNDO: str = "↶"  # Undo arrow
    ACTION_REDO: str = "↷"  # Redo arrow
    ACTION_COPY: str = "📋"  # Clipboard
    ACTION_PASTE: str = "📄"  # Document
    ACTION_CLEAR: str = "🧹"  # Broom
    ACTION_SEARCH: str = "🔍"  # Magnifying glass
    ACTION_FILTER: str = "🔽"  # Filter down

    # Transport controls
    PLAY: str = "▶"  # Play
    PAUSE: str = "⏸"  # Pause
    STOP: str = "⏹"  # Stop
    RESUME: str = "▶"  # Same as play

    # Toggle indicators
    TOGGLE_ON: str = "☑"  # Checked box
    TOGGLE_OFF: str = "☐"  # Unchecked box
    TOGGLE_RADIO_ON: str = "◉"  # Filled radio
    TOGGLE_RADIO_OFF: str = "○"  # Empty radio

    # Sort indicators
    SORT_ASC: str = "▲"  # Ascending
    SORT_DESC: str = "▼"  # Descending
    SORT_NONE: str = "⇅"  # Unsorted

    # Expand/collapse
    EXPAND: str = "▼"  # Expanded (arrow down)
    COLLAPSE: str = "▶"  # Collapsed (arrow right)
    EXPAND_ALL: str = "⊞"  # Expand all
    COLLAPSE_ALL: str = "⊟"  # Collapse all

    # Severity/log levels
    LOG_DEBUG: str = "🔍"  # Debug
    LOG_INFO: str = "ℹ"  # Info
    LOG_WARNING: str = "⚠"  # Warning
    LOG_ERROR: str = "⛔"  # Error

    # Misc UI elements
    SETTINGS: str = "⚙"  # Settings gear
    HELP: str = "?"  # Question mark
    CLOSE: str = "✕"  # Close X
    MENU: str = "☰"  # Hamburger menu
    PIN: str = "📌"  # Pin
    LOCK: str = "🔒"  # Locked
    UNLOCK: str = "🔓"  # Unlocked
    VISIBLE: str = "👁"  # Eye
    HIDDEN: str = "🙈"  # Hidden
    LINK: str = "🔗"  # Link
    EXTERNAL: str = "↗"  # External link

    # Progress indicators
    PROGRESS_0: str = "░"  # Empty progress block
    PROGRESS_25: str = "▒"  # Quarter progress
    PROGRESS_50: str = "▓"  # Half progress
    PROGRESS_75: str = "▓"  # Three-quarter progress
    PROGRESS_100: str = "█"  # Full progress block

    # File type indicators
    FILE_TEXT: str = "📄"  # Text file
    FILE_JSON: str = "📋"  # JSON
    FILE_CSV: str = "📊"  # Spreadsheet
    FILE_FOLDER: str = "📁"  # Folder


# Default icons instance
ICONS = Icons()


# Step icons mapping by step ID
STEP_ICONS: Dict[int, str] = {
    0: ICONS.STEP_INPUT,
    1: ICONS.STEP_ANALYSIS,
    2: ICONS.STEP_INFORMATION,
    3: ICONS.STEP_PREPROCESS,
    4: ICONS.STEP_ESTIMATE,
    5: ICONS.STEP_TRANSLATE,
    6: ICONS.STEP_QA,
    7: ICONS.STEP_POSTPROCESS,
    8: ICONS.STEP_WORDWRAP,
    9: ICONS.STEP_OUTPUT,
}


def get_step_icon(step_id: int) -> str:
    """Get the icon for a workflow step.

    Args:
        step_id: Step ID (0-9).

    Returns:
        Unicode icon string for the step.
    """
    return STEP_ICONS.get(step_id, "")


def get_status_icon(status: str) -> str:
    """Get the icon for a status string.

    Args:
        status: Status string (done, partial, pending, failed, skipped, running).

    Returns:
        Unicode icon string for the status.
    """
    status_map = {
        "done": ICONS.STATUS_DONE,
        "completed": ICONS.STATUS_DONE,
        "partial": ICONS.STATUS_PARTIAL,
        "in-progress": ICONS.STATUS_PARTIAL,
        "pending": ICONS.STATUS_PENDING,
        "not-started": ICONS.STATUS_PENDING,
        "failed": ICONS.STATUS_FAILED,
        "error": ICONS.STATUS_FAILED,
        "skipped": ICONS.STATUS_SKIPPED,
        "running": ICONS.STATUS_RUNNING,
    }
    return status_map.get(status.lower(), ICONS.STATUS_PENDING)


def get_log_level_icon(level: str) -> str:
    """Get the icon for a log level.

    Args:
        level: Log level string (debug, info, warning, error).

    Returns:
        Unicode icon string for the log level.
    """
    level_map = {
        "debug": ICONS.LOG_DEBUG,
        "info": ICONS.LOG_INFO,
        "warning": ICONS.LOG_WARNING,
        "error": ICONS.LOG_ERROR,
    }
    return level_map.get(level.lower(), ICONS.LOG_INFO)
