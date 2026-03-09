"""CherryAI Manifest Field Helpers.

TASK 22.1: Type-specific helpers for ManifestManager field operations.
TASK 22.2: Special format helpers for complex data structures.

These helpers reduce code duplication across GUI steps by providing
reusable save/load operations for different field types.

IMPORTANT: These helpers work with ManifestManager._manifest_data v3.0 fields.
They do NOT modify the v2.1 processing fields (lines, operations, mappings).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


# ========================== Line Priority Resolution ========================== #

# Canonical pipeline field order (latest result first).
# Each downstream step writes its own field; reading backwards finds the
# most-processed version of a line.
PIPELINE_FIELDS: List[str] = [
    "qa_overwrite",  # QA manual overwrite (Step 8)
    "wordwr",        # Wordwrapped text    (Step 7)
    "postpro",       # Postprocessed text   (Step 6)
    "tl",            # Translation          (Step 5)
    "prepro",        # Preprocessed text    (Step 4)
    "orig",          # Original text        (Step 0)
]


def resolve_line_field(
    line: Dict[str, Any],
    priority: Optional[Sequence[str]] = None,
) -> str:
    """Return the highest-priority non-empty field value for a manifest line.

    The default priority walks the pipeline backwards from the latest
    processing stage to the original text so that every caller gets the
    most-processed version available.

    Args:
        line: A single manifest line dict (must contain at least ``orig``).
        priority: Field names to try in order.  Defaults to
            :data:`PIPELINE_FIELDS` (qa_overwrite → wordwr → … → orig).

    Returns:
        The first non-empty string found, or ``""`` if the line is
        completely empty.
    """
    if priority is None:
        priority = PIPELINE_FIELDS
    for field_name in priority:
        value = line.get(field_name) or ""
        if isinstance(value, str) and value:
            return value
    return ""


def resolve_line_field_from(
    line: Dict[str, Any],
    start_field: str,
) -> str:
    """Return the highest-priority field starting from *start_field* downward.

    Convenience wrapper that slices :data:`PIPELINE_FIELDS` from the
    requested starting point before delegating to :func:`resolve_line_field`.

    Example::

        # Get the best text starting from ``tl`` (tl → prepro → orig):
        text = resolve_line_field_from(line, "tl")

    Args:
        line: A single manifest line dict.
        start_field: The topmost field to consider.  Must be one of
            :data:`PIPELINE_FIELDS`.

    Returns:
        First non-empty string from *start_field* down to ``orig``, or ``""``.
    """
    try:
        idx = PIPELINE_FIELDS.index(start_field)
    except ValueError:
        logger.warning("Unknown pipeline field %r, falling back to full chain", start_field)
        return resolve_line_field(line)
    return resolve_line_field(line, PIPELINE_FIELDS[idx:])


def get_latest_line_text(manager: "ManifestManager", idx: int) -> str:
    """Get the most-processed text for a single manifest line by index.

    Args:
        manager: ManifestManager instance.
        idx: Line index.

    Returns:
        Most-processed text, or ``""`` if the line does not exist.
    """
    line = manager.get_line(idx)
    if line is None:
        return ""
    return resolve_line_field(line)


def get_all_lines_resolved(
    manager: "ManifestManager",
    start_field: Optional[str] = None,
) -> List[str]:
    """Return all manifest lines resolved through the priority chain.

    Args:
        manager: ManifestManager instance.
        start_field: Optional ceiling field (see
            :func:`resolve_line_field_from`).  When ``None`` the full
            pipeline chain is used.

    Returns:
        List of resolved strings, one per manifest line index in order.
    """
    lines = manager.get_lines()
    if start_field is not None:
        return [resolve_line_field_from(ln, start_field) for ln in lines]
    return [resolve_line_field(ln) for ln in lines]


# ========================== Text Field Helpers ========================== #

def save_text_field(manager: "ManifestManager", key: str, value: str) -> None:
    """Save a text field to manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        value: Text value to save.
    """
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    manager._manifest_data[key] = value
    manager._mark_dirty()
    logger.debug("Saved text field %s = %r", key, value[:50] if len(value) > 50 else value)


def load_text_field(manager: "ManifestManager", key: str, default: str = "") -> str:
    """Load a text field from manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        default: Default value if not found.
        
    Returns:
        Text value or default.
    """
    value = manager._manifest_data.get(key, default)
    if value is None:
        return default
    return str(value)


def save_nested_text_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    value: str
) -> None:
    """Save a text field to a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        value: Text value to save.
    """
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    if parent_key not in manager._manifest_data:
        manager._manifest_data[parent_key] = {}
    manager._manifest_data[parent_key][child_key] = value
    manager._mark_dirty()


def load_nested_text_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    default: str = ""
) -> str:
    """Load a text field from a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        default: Default value if not found.
        
    Returns:
        Text value or default.
    """
    parent = manager._manifest_data.get(parent_key, {})
    if not isinstance(parent, dict):
        return default
    value = parent.get(child_key, default)
    if value is None:
        return default
    return str(value)


# ========================== Boolean Field Helpers ========================== #

def save_bool_field(manager: "ManifestManager", key: str, value: bool) -> None:
    """Save a boolean field to manifest.
    
    Stores as Python bool (True/False) for JSON serialization.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        value: Boolean value to save.
    """
    # Normalize to actual boolean
    if isinstance(value, str):
        value = value.lower() in ("true", "1", "yes", "on")
    else:
        value = bool(value)
    manager._manifest_data[key] = value
    manager._mark_dirty()
    logger.debug("Saved bool field %s = %s", key, value)


def load_bool_field(manager: "ManifestManager", key: str, default: bool = False) -> bool:
    """Load a boolean field from manifest.
    
    Handles various boolean representations:
    - Python bool (True/False)
    - Strings ("true", "false", "1", "0", "yes", "no")
    - Numbers (0 = False, non-zero = True)
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        default: Default value if not found.
        
    Returns:
        Boolean value or default.
    """
    value = manager._manifest_data.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    if isinstance(value, (int, float)):
        return value != 0
    return default


def save_nested_bool_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    value: bool
) -> None:
    """Save a boolean field to a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        value: Boolean value to save.
    """
    if isinstance(value, str):
        value = value.lower() in ("true", "1", "yes", "on")
    else:
        value = bool(value)
    if parent_key not in manager._manifest_data:
        manager._manifest_data[parent_key] = {}
    manager._manifest_data[parent_key][child_key] = value
    manager._mark_dirty()


def load_nested_bool_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    default: bool = False
) -> bool:
    """Load a boolean field from a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        default: Default value if not found.
        
    Returns:
        Boolean value or default.
    """
    parent = manager._manifest_data.get(parent_key, {})
    if not isinstance(parent, dict):
        return default
    value = parent.get(child_key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    if isinstance(value, (int, float)):
        return value != 0
    return default


# ========================== Integer Field Helpers ========================== #

def save_int_field(
    manager: "ManifestManager", 
    key: str, 
    value: int,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> None:
    """Save an integer field to manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        value: Integer value to save.
        min_val: Optional minimum value (clamp if below).
        max_val: Optional maximum value (clamp if above).
    """
    # Convert to int
    try:
        if isinstance(value, str):
            value = int(float(value))  # Handle "3.0" strings
        else:
            value = int(value)
    except (ValueError, TypeError):
        logger.warning("Invalid int value for %s: %r, using 0", key, value)
        value = 0
    
    # Clamp to bounds
    if min_val is not None and value < min_val:
        value = min_val
    if max_val is not None and value > max_val:
        value = max_val
    
    manager._manifest_data[key] = value
    manager._mark_dirty()
    logger.debug("Saved int field %s = %d", key, value)


def load_int_field(
    manager: "ManifestManager", 
    key: str, 
    default: int = 0,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> int:
    """Load an integer field from manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        default: Default value if not found.
        min_val: Optional minimum value (clamp if below).
        max_val: Optional maximum value (clamp if above).
        
    Returns:
        Integer value or default.
    """
    value = manager._manifest_data.get(key)
    if value is None:
        return default
    
    try:
        if isinstance(value, str):
            result = int(float(value))
        else:
            result = int(value)
    except (ValueError, TypeError):
        logger.warning("Invalid int value for %s: %r, using default %d", key, value, default)
        return default
    
    # Clamp to bounds
    if min_val is not None and result < min_val:
        result = min_val
    if max_val is not None and result > max_val:
        result = max_val
    
    return result


def save_nested_int_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    value: int,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> None:
    """Save an integer field to a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        value: Integer value to save.
        min_val: Optional minimum value (clamp if below).
        max_val: Optional maximum value (clamp if above).
    """
    try:
        if isinstance(value, str):
            value = int(float(value))
        else:
            value = int(value)
    except (ValueError, TypeError):
        value = 0
    
    if min_val is not None and value < min_val:
        value = min_val
    if max_val is not None and value > max_val:
        value = max_val
    
    if parent_key not in manager._manifest_data:
        manager._manifest_data[parent_key] = {}
    manager._manifest_data[parent_key][child_key] = value
    manager._mark_dirty()


def load_nested_int_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    default: int = 0,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> int:
    """Load an integer field from a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        default: Default value if not found.
        min_val: Optional minimum value (clamp if below).
        max_val: Optional maximum value (clamp if above).
        
    Returns:
        Integer value or default.
    """
    parent = manager._manifest_data.get(parent_key, {})
    if not isinstance(parent, dict):
        return default
    value = parent.get(child_key)
    if value is None:
        return default
    
    try:
        if isinstance(value, str):
            result = int(float(value))
        else:
            result = int(value)
    except (ValueError, TypeError):
        return default
    
    if min_val is not None and result < min_val:
        result = min_val
    if max_val is not None and result > max_val:
        result = max_val
    
    return result


# ========================== Float Field Helpers ========================== #

def save_float_field(
    manager: "ManifestManager", 
    key: str, 
    value: float,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    precision: Optional[int] = None
) -> None:
    """Save a float field to manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        value: Float value to save.
        min_val: Optional minimum value (clamp if below).
        max_val: Optional maximum value (clamp if above).
        precision: Optional decimal places to round to.
    """
    try:
        value = float(value)
    except (ValueError, TypeError):
        logger.warning("Invalid float value for %s: %r, using 0.0", key, value)
        value = 0.0
    
    # Clamp to bounds
    if min_val is not None and value < min_val:
        value = min_val
    if max_val is not None and value > max_val:
        value = max_val
    
    # Round to precision
    if precision is not None:
        value = round(value, precision)
    
    manager._manifest_data[key] = value
    manager._mark_dirty()
    logger.debug("Saved float field %s = %f", key, value)


def load_float_field(
    manager: "ManifestManager", 
    key: str, 
    default: float = 0.0,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> float:
    """Load a float field from manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        default: Default value if not found.
        min_val: Optional minimum value (clamp if below).
        max_val: Optional maximum value (clamp if above).
        
    Returns:
        Float value or default.
    """
    value = manager._manifest_data.get(key)
    if value is None:
        return default
    
    try:
        result = float(value)
    except (ValueError, TypeError):
        logger.warning("Invalid float value for %s: %r, using default %f", key, value, default)
        return default
    
    # Clamp to bounds
    if min_val is not None and result < min_val:
        result = min_val
    if max_val is not None and result > max_val:
        result = max_val
    
    return result


def save_nested_float_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    value: float,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    precision: Optional[int] = None
) -> None:
    """Save a float field to a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        value: Float value to save.
        min_val: Optional minimum value (clamp if below).
        max_val: Optional maximum value (clamp if above).
        precision: Optional decimal places to round to.
    """
    try:
        value = float(value)
    except (ValueError, TypeError):
        value = 0.0
    
    if min_val is not None and value < min_val:
        value = min_val
    if max_val is not None and value > max_val:
        value = max_val
    if precision is not None:
        value = round(value, precision)
    
    if parent_key not in manager._manifest_data:
        manager._manifest_data[parent_key] = {}
    manager._manifest_data[parent_key][child_key] = value
    manager._mark_dirty()


def load_nested_float_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    default: float = 0.0,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> float:
    """Load a float field from a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        default: Default value if not found.
        min_val: Optional minimum value (clamp if below).
        max_val: Optional maximum value (clamp if above).
        
    Returns:
        Float value or default.
    """
    parent = manager._manifest_data.get(parent_key, {})
    if not isinstance(parent, dict):
        return default
    value = parent.get(child_key)
    if value is None:
        return default
    
    try:
        result = float(value)
    except (ValueError, TypeError):
        return default
    
    if min_val is not None and result < min_val:
        result = min_val
    if max_val is not None and result > max_val:
        result = max_val
    
    return result


# ========================== Enum Field Helpers ========================== #

def save_enum_field(
    manager: "ManifestManager", 
    key: str, 
    value: str, 
    options: List[str]
) -> None:
    """Save an enum (dropdown/radio) field to manifest.
    
    If value is not in options, the first option is used.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        value: Enum value to save.
        options: List of valid options.
    """
    if not options:
        logger.warning("No options provided for enum field %s", key)
        return
    
    value = str(value) if value is not None else ""
    if value not in options:
        logger.warning("Invalid enum value %r for %s, using first option %r", 
                      value, key, options[0])
        value = options[0]
    
    manager._manifest_data[key] = value
    manager._mark_dirty()
    logger.debug("Saved enum field %s = %r", key, value)


def load_enum_field(
    manager: "ManifestManager", 
    key: str, 
    default: str, 
    options: List[str]
) -> str:
    """Load an enum field from manifest.
    
    If stored value is not in options, returns default.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        default: Default value if not found or invalid.
        options: List of valid options.
        
    Returns:
        Enum value or default.
    """
    value = manager._manifest_data.get(key)
    if value is None:
        return default
    
    value = str(value)
    if value not in options:
        logger.warning("Invalid enum value %r for %s, using default %r", 
                      value, key, default)
        return default
    
    return value


def save_nested_enum_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    value: str, 
    options: List[str]
) -> None:
    """Save an enum field to a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        value: Enum value to save.
        options: List of valid options.
    """
    if not options:
        return
    
    value = str(value) if value is not None else ""
    if value not in options:
        value = options[0]
    
    if parent_key not in manager._manifest_data:
        manager._manifest_data[parent_key] = {}
    manager._manifest_data[parent_key][child_key] = value
    manager._mark_dirty()


def load_nested_enum_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    default: str, 
    options: List[str]
) -> str:
    """Load an enum field from a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        default: Default value if not found or invalid.
        options: List of valid options.
        
    Returns:
        Enum value or default.
    """
    parent = manager._manifest_data.get(parent_key, {})
    if not isinstance(parent, dict):
        return default
    value = parent.get(child_key)
    if value is None:
        return default
    
    value = str(value)
    if value not in options:
        return default
    
    return value


# ========================== List Field Helpers ========================== #

def save_list_field(
    manager: "ManifestManager", 
    key: str, 
    value: List[Any]
) -> None:
    """Save a list field to manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        value: List value to save.
    """
    if isinstance(value, list):
        pass  # Already a list
    elif isinstance(value, str):
        # Don't iterate strings - wrap them
        value = [value] if value else []
    elif value is None:
        value = []
    else:
        # Try to convert other iterables to list
        try:
            value = list(value)
        except (TypeError, ValueError):
            value = [value]
    
    manager._manifest_data[key] = value
    manager._mark_dirty()
    logger.debug("Saved list field %s with %d items", key, len(value))


def load_list_field(
    manager: "ManifestManager", 
    key: str, 
    default: Optional[List[Any]] = None
) -> List[Any]:
    """Load a list field from manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        default: Default value if not found.
        
    Returns:
        List value or default.
    """
    if default is None:
        default = []
    
    value = manager._manifest_data.get(key)
    if value is None:
        return default.copy() if isinstance(default, list) else []
    
    if not isinstance(value, list):
        # Handle comma-separated strings
        if isinstance(value, str) and value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return default.copy() if isinstance(default, list) else []
    
    return value.copy()


def save_nested_list_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    value: List[Any]
) -> None:
    """Save a list field to a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        value: List value to save.
    """
    if isinstance(value, list):
        pass  # Already a list
    elif isinstance(value, str):
        # Don't iterate strings - wrap them
        value = [value] if value else []
    elif value is None:
        value = []
    else:
        try:
            value = list(value)
        except (TypeError, ValueError):
            value = [value]
    
    if parent_key not in manager._manifest_data:
        manager._manifest_data[parent_key] = {}
    manager._manifest_data[parent_key][child_key] = value
    manager._mark_dirty()


def load_nested_list_field(
    manager: "ManifestManager", 
    parent_key: str, 
    child_key: str, 
    default: Optional[List[Any]] = None
) -> List[Any]:
    """Load a list field from a nested dict in manifest.
    
    Args:
        manager: ManifestManager instance.
        parent_key: Parent dict key in manifest.
        child_key: Child key within parent dict.
        default: Default value if not found.
        
    Returns:
        List value or default.
    """
    if default is None:
        default = []
    
    parent = manager._manifest_data.get(parent_key, {})
    if not isinstance(parent, dict):
        return default.copy() if isinstance(default, list) else []
    
    value = parent.get(child_key)
    if value is None:
        return default.copy() if isinstance(default, list) else []
    
    if not isinstance(value, list):
        if isinstance(value, str) and value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return default.copy() if isinstance(default, list) else []
    
    return value.copy()


# ========================== String List Field Helpers ========================== #

def save_string_list_field(
    manager: "ManifestManager", 
    key: str, 
    value: List[str]
) -> None:
    """Save a list of strings to manifest.
    
    Ensures all items are strings.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        value: List of strings to save.
    """
    if not isinstance(value, list):
        try:
            value = list(value)
        except (TypeError, ValueError):
            value = [str(value)] if value is not None else []
    
    # Ensure all items are strings
    value = [str(item) for item in value]
    
    manager._manifest_data[key] = value
    manager._mark_dirty()


def load_string_list_field(
    manager: "ManifestManager", 
    key: str, 
    default: Optional[List[str]] = None
) -> List[str]:
    """Load a list of strings from manifest.
    
    Ensures all items returned are strings.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        default: Default value if not found.
        
    Returns:
        List of strings or default.
    """
    if default is None:
        default = []
    
    value = manager._manifest_data.get(key)
    if value is None:
        return default.copy() if isinstance(default, list) else []
    
    if isinstance(value, str):
        if value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return default.copy() if isinstance(default, list) else []
    
    if isinstance(value, list):
        return [str(item) for item in value]
    
    return default.copy() if isinstance(default, list) else []


# ========================== Dict Field Helpers ========================== #

def save_dict_field(
    manager: "ManifestManager", 
    key: str, 
    value: Dict[str, Any]
) -> None:
    """Save a dict field to manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        value: Dict value to save.
    """
    if not isinstance(value, dict):
        logger.warning("Invalid dict value for %s: %r, using empty dict", key, value)
        value = {}
    
    manager._manifest_data[key] = value.copy()
    manager._mark_dirty()


def load_dict_field(
    manager: "ManifestManager", 
    key: str, 
    default: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Load a dict field from manifest.
    
    Args:
        manager: ManifestManager instance.
        key: Field key in manifest.
        default: Default value if not found.
        
    Returns:
        Dict value or default.
    """
    if default is None:
        default = {}
    
    value = manager._manifest_data.get(key)
    if value is None:
        return default.copy() if isinstance(default, dict) else {}
    
    if not isinstance(value, dict):
        return default.copy() if isinstance(default, dict) else {}
    
    return value.copy()


# ========================== Special Format Helpers (TASK 22.2) ========================== #


def save_character_notes(
    manager: "ManifestManager",
    characters: List[Dict[str, Any]]
) -> None:
    """Save character notes to manifest.

    Characters are stored as a list of dicts with fields:
    - original_name: str (source-language name, lookup key)
    - translation: str (translated name)
    - notes: str (free-form — gender, role, speaking style, etc.)
    - count: int (occurrence count from analysis speaker detection)

    Args:
        manager: ManifestManager instance.
        characters: List of character dictionaries.
    """
    if not isinstance(characters, list):
        characters = []

    cleaned = []
    for char in characters:
        if isinstance(char, dict):
            # Accept either new or legacy field names
            translation = (
                str(char.get("translation", ""))
                or str(char.get("name", ""))
            )
            cleaned.append({
                "original_name": str(char.get("original_name", "")),
                "translation": translation,
                "notes": str(char.get("notes", "")),
                "count": int(char.get("count", 0)),
            })
        elif hasattr(char, "to_dict"):
            cleaned.append(char.to_dict())

    manager._manifest_data["characters"] = cleaned
    manager._mark_dirty()
    logger.debug("Saved %d character notes", len(cleaned))


def load_character_notes(
    manager: "ManifestManager"
) -> List[Dict[str, Any]]:
    """Load character notes from manifest.

    Returns list of character dicts with fields:
    original_name, translation, notes, count.

    Transparently migrates legacy manifests that still have separate
    ``name``, ``gender``, ``role``, ``speaking_style`` keys.

    Args:
        manager: ManifestManager instance.

    Returns:
        List of character dictionaries.
    """
    characters = manager._manifest_data.get("characters", [])
    if not isinstance(characters, list):
        return []

    result = []
    for char in characters:
        if isinstance(char, dict):
            # Accept either new or legacy field names
            translation = (
                str(char.get("translation", ""))
                or str(char.get("name", ""))
            )
            # Merge legacy separate fields into notes
            parts: list[str] = []
            for legacy_key in ("gender", "role", "speaking_style"):
                val = char.get(legacy_key, "")
                if val:
                    parts.append(str(val))
            existing_notes = char.get("notes", "")
            if existing_notes:
                parts.append(str(existing_notes))
            notes = ", ".join(parts)

            result.append({
                "original_name": str(char.get("original_name", "")),
                "translation": translation,
                "notes": notes,
                "count": int(char.get("count", 0)),
            })

    return result


def save_code_glossary(
    manager: "ManifestManager",
    patterns: List[Dict[str, Any]]
) -> None:
    """Save code glossary patterns to manifest.

    Code glossary stores patterns detected during analysis:
    - pattern: str (the code pattern regex or string)
    - category: str (RPG Maker Variable, Ruby Code, etc.)
    - action: str (preserve, translate, remove)
    - example: str (example occurrence from source)
    - notes: str (user notes)
    - count: int or list (total, or [total, inst1_ct, inst2_ct, ...])
    - raw_type: str (internal type constant from detection)
    - instances: list (concrete instances for aggregated patterns)

    When ``instance_counts`` is present in the input dict, ``count`` is
    serialized as ``[total, inst1_count, inst2_count, ...]``.

    Args:
        manager: ManifestManager instance.
        patterns: List of code pattern dictionaries.
    """
    if not isinstance(patterns, list):
        patterns = []

    cleaned = []
    for pat in patterns:
        if isinstance(pat, dict):
            entry: Dict[str, Any] = {
                "pattern": str(pat.get("pattern", "")),
                "translation": str(pat.get("translation", "")),
                "category": str(pat.get("category", "")),
                "action": str(pat.get("action", "preserve")),
                "example": str(pat.get("example", "")),
                "notes": str(pat.get("notes", "")),
                # TASK 42.7: Code spacing integration fields
                "visible": bool(pat.get("visible", True)),
                "spacing": str(pat.get("spacing", "preserve")),
                "raw_type": str(pat.get("raw_type", "")),
            }
            # Serialize count: merge instance_counts into list form
            count_val = pat.get("count", 0)
            inst_counts = pat.get("instance_counts", [])
            if isinstance(count_val, list):
                # Already in list form (e.g. from CodePattern.to_dict)
                entry["count"] = count_val
            elif inst_counts and isinstance(inst_counts, list):
                entry["count"] = [int(count_val)] + [int(c) for c in inst_counts]
            else:
                entry["count"] = int(count_val)
            instances = pat.get("instances", [])
            if instances and isinstance(instances, list):
                entry["instances"] = list(instances)
            cleaned.append(entry)
        elif hasattr(pat, "to_dict"):
            # Support CodePattern dataclass
            cleaned.append(pat.to_dict())

    manager._manifest_data["code_patterns"] = cleaned
    manager._mark_dirty()
    logger.debug("Saved %d code glossary patterns", len(cleaned))


def load_code_glossary(
    manager: "ManifestManager"
) -> List[Dict[str, Any]]:
    """Load code glossary patterns from manifest.

    Returns list of pattern dicts with fields:
    pattern, category, action, example, notes, count, raw_type, instances,
    instance_counts.

    When ``count`` is stored as ``[total, inst1_ct, ...]``, it is split into
    ``count`` (int) and ``instance_counts`` (list[int]).

    Args:
        manager: ManifestManager instance.

    Returns:
        List of code pattern dictionaries.
    """
    patterns = manager._manifest_data.get("code_patterns", [])
    if not isinstance(patterns, list):
        return []

    result = []
    for pat in patterns:
        if isinstance(pat, dict):
            entry: Dict[str, Any] = {
                "pattern": str(pat.get("pattern", "")),
                "translation": str(pat.get("translation", "")),
                "category": str(pat.get("category", "")),
                "action": str(pat.get("action", "preserve")),
                "example": str(pat.get("example", "")),
                "notes": str(pat.get("notes", "")),
                # TASK 42.7: Code spacing integration fields
                "visible": bool(pat.get("visible", True)),
                "spacing": str(pat.get("spacing", "preserve")),
                "raw_type": str(pat.get("raw_type", "")),
            }
            # Deserialize count: may be int or [total, inst1_ct, ...]
            count_val = pat.get("count", 0)
            if isinstance(count_val, list):
                entry["count"] = int(count_val[0]) if count_val else 0
                entry["instance_counts"] = [int(c) for c in count_val[1:]]
            else:
                entry["count"] = int(count_val)
                entry["instance_counts"] = []
            instances = pat.get("instances", [])
            if instances and isinstance(instances, list):
                entry["instances"] = list(instances)
            else:
                entry["instances"] = []
            result.append(entry)

    return result


def save_protect_code_patterns(
    manager: "ManifestManager",
    patterns: List[Dict[str, Any]]
) -> None:
    """Save protect code patterns to manifest.
    
    These are patterns for the Protect Code mode during preprocessing:
    - pattern: str (regex pattern)
    - replacement: str (placeholder name)
    - is_regex: bool (whether pattern is regex)
    - description: str (optional description)
    
    Args:
        manager: ManifestManager instance.
        patterns: List of pattern dictionaries.
    """
    if not isinstance(patterns, list):
        patterns = []
    
    cleaned = []
    for pat in patterns:
        if isinstance(pat, dict):
            cleaned.append({
                "pattern": str(pat.get("pattern", "")),
                "replacement": str(pat.get("replacement", "")),
                "is_regex": bool(pat.get("is_regex", False)),
                "description": str(pat.get("description", "")),
            })
    
    manager._manifest_data["ProtectCodePatterns"] = cleaned
    manager._mark_dirty()


def load_protect_code_patterns(
    manager: "ManifestManager"
) -> List[Dict[str, Any]]:
    """Load protect code patterns from manifest.
    
    Returns list of pattern dicts with fields:
    pattern, replacement, is_regex, description
    
    Args:
        manager: ManifestManager instance.
        
    Returns:
        List of protect code pattern dictionaries.
    """
    patterns = manager._manifest_data.get("ProtectCodePatterns", [])
    if not isinstance(patterns, list):
        return []
    
    result = []
    for pat in patterns:
        if isinstance(pat, dict):
            result.append({
                "pattern": str(pat.get("pattern", "")),
                "replacement": str(pat.get("replacement", "")),
                "is_regex": bool(pat.get("is_regex", False)),
                "description": str(pat.get("description", "")),
            })
    
    return result


def save_custom_placeholders(
    manager: "ManifestManager",
    placeholders: List[Dict[str, Any]]
) -> None:
    """Save custom placeholder patterns to manifest.
    
    Custom placeholders for preprocessing:
    - pattern: str (text to match)
    - placeholder: str (replacement token)
    - is_regex: bool (whether pattern is regex)
    - restore_after: bool (whether to restore after translation)
    
    Args:
        manager: ManifestManager instance.
        placeholders: List of placeholder dictionaries.
    """
    if not isinstance(placeholders, list):
        placeholders = []
    
    cleaned = []
    for ph in placeholders:
        if isinstance(ph, dict):
            cleaned.append({
                "pattern": str(ph.get("pattern", "")),
                "placeholder": str(ph.get("placeholder", "")),
                "is_regex": bool(ph.get("is_regex", False)),
                "restore_after": bool(ph.get("restore_after", True)),
            })
    
    manager._manifest_data["CustomPlaceholders"] = cleaned
    manager._mark_dirty()


def load_custom_placeholders(
    manager: "ManifestManager"
) -> List[Dict[str, Any]]:
    """Load custom placeholder patterns from manifest.
    
    Returns list of placeholder dicts with fields:
    pattern, placeholder, is_regex, restore_after
    
    Args:
        manager: ManifestManager instance.
        
    Returns:
        List of custom placeholder dictionaries.
    """
    placeholders = manager._manifest_data.get("CustomPlaceholders", [])
    if not isinstance(placeholders, list):
        return []
    
    result = []
    for ph in placeholders:
        if isinstance(ph, dict):
            result.append({
                "pattern": str(ph.get("pattern", "")),
                "placeholder": str(ph.get("placeholder", "")),
                "is_regex": bool(ph.get("is_regex", False)),
                "restore_after": bool(ph.get("restore_after", True)),
            })
    
    return result


def save_anchor_removal(
    manager: "ManifestManager",
    anchors: List[Dict[str, Any]]
) -> None:
    """Save anchor removal patterns to manifest.
    
    Anchor removal patterns for preprocessing (TASK 42.1 redesign):
    - pattern: str (anchor pattern to match)
    - action: str (remove, preserve, replace)
    - anchor_spec: str (anchor position spec, e.g. "line_start;line_end")
    - is_regex: bool (whether pattern is regex, default True)
    - description: str (human-readable description)
    
    Args:
        manager: ManifestManager instance.
        anchors: List of anchor dictionaries.
    """
    if not isinstance(anchors, list):
        anchors = []
    
    cleaned = []
    for anchor in anchors:
        if isinstance(anchor, dict):
            cleaned.append({
                "pattern": str(anchor.get("pattern", "")),
                "action": str(anchor.get("action", "remove")),
                "anchor_spec": str(anchor.get(
                    "anchor_spec", anchor.get("replacement", "")
                )),
                "is_regex": bool(anchor.get("is_regex", True)),
                "description": str(anchor.get("description", "")),
            })
    
    manager._manifest_data["AnchorRemoval"] = cleaned
    manager._mark_dirty()


def load_anchor_removal(
    manager: "ManifestManager"
) -> List[Dict[str, Any]]:
    """Load anchor removal patterns from manifest.
    
    Returns list of anchor dicts with fields (TASK 42.1):
    pattern, action, anchor_spec, is_regex, description
    
    Args:
        manager: ManifestManager instance.
        
    Returns:
        List of anchor removal dictionaries.
    """
    anchors = manager._manifest_data.get("AnchorRemoval", [])
    if not isinstance(anchors, list):
        return []
    
    result = []
    for anchor in anchors:
        if isinstance(anchor, dict):
            result.append({
                "pattern": str(anchor.get("pattern", "")),
                "action": str(anchor.get("action", "remove")),
                "anchor_spec": str(anchor.get(
                    "anchor_spec", anchor.get("replacement", "")
                )),
                "is_regex": bool(anchor.get("is_regex", True)),
                "description": str(anchor.get("description", "")),
            })
    
    return result


# ---------------------------------------------------------------------------
# Code Pattern → Preprocessing Sync
# ---------------------------------------------------------------------------

_SYNC_SOURCE = "code_pattern"


def sync_code_pattern_actions(manager: "ManifestManager") -> None:
    """Sync code_patterns actions to preprocessing manifest sections.

    For each code pattern:
    - action='protect' → add regex to ProtectCodePatterns
    - action='custom_placeholder' → add to CustomPlaceholders
    - action='strip_with_anchor' → add to AnchorRemoval

    Auto-synced entries carry ``source: 'code_pattern'`` so manual
    entries are never modified.  Stale auto-synced entries whose
    source pattern no longer has the matching action are removed.
    """
    from CherryAI.functions.glossaries.code_glossary_functions import (
        generate_regex_pattern,
    )

    code_patterns = manager._manifest_data.get("code_patterns", [])
    if not isinstance(code_patterns, list):
        code_patterns = []

    # Collect desired patterns per section
    want_protect: Dict[str, Dict[str, Any]] = {}
    want_custom: Dict[str, Dict[str, Any]] = {}
    want_anchor: Dict[str, Dict[str, Any]] = {}

    for cp in code_patterns:
        if not isinstance(cp, dict):
            continue
        pat = cp.get("pattern", "")
        action = cp.get("action", "preserve")
        raw_type = cp.get("raw_type", "UNKNOWN")
        if not pat:
            continue

        regex = generate_regex_pattern(pat, raw_type)

        if action == "protect":
            want_protect[pat] = {
                "pattern": regex,
                "replacement": "__PROTECTED__",
                "is_regex": True,
                "description": f"Auto: {pat}",
                "source": _SYNC_SOURCE,
                "source_pattern": pat,
            }
        elif action == "custom_placeholder":
            placeholder = cp.get("translation", "") or f"__{pat}__"
            want_custom[pat] = {
                "pattern": regex,
                "placeholder": placeholder,
                "is_regex": True,
                "restore_after": True,
                "description": f"Auto: {pat}",
                "source": _SYNC_SOURCE,
                "source_pattern": pat,
            }
        elif action == "strip_with_anchor":
            want_anchor[pat] = {
                "pattern": regex,
                "action": "remove",
                "anchor_spec": cp.get("notes", ""),
                "is_regex": True,
                "description": f"Auto: {pat}",
                "source": _SYNC_SOURCE,
                "source_pattern": pat,
            }

    # --- ProtectCodePatterns ---
    _merge_sync_entries(
        manager, "ProtectCodePatterns", want_protect,
    )
    # --- CustomPlaceholders ---
    _merge_sync_entries(
        manager, "CustomPlaceholders", want_custom,
    )
    # --- AnchorRemoval ---
    _merge_sync_entries(
        manager, "AnchorRemoval", want_anchor,
    )


def _merge_sync_entries(
    manager: "ManifestManager",
    section: str,
    wanted: Dict[str, Dict[str, Any]],
) -> None:
    """Merge auto-synced entries into a manifest section.

    Keeps manual entries untouched.  Updates existing auto entries
    whose source_pattern is still wanted, removes stale ones, and
    adds new ones.
    """
    existing: List[Dict[str, Any]] = manager._manifest_data.get(section, [])
    if not isinstance(existing, list):
        existing = []

    # Partition into manual vs auto-synced
    manual = [e for e in existing if e.get("source") != _SYNC_SOURCE]
    auto_by_src = {
        e.get("source_pattern", ""): e
        for e in existing
        if e.get("source") == _SYNC_SOURCE
    }

    # Build new auto list: keep wanted, drop stale
    new_auto: List[Dict[str, Any]] = []
    for src_pat, entry in wanted.items():
        new_auto.append(entry)

    manager._manifest_data[section] = manual + new_auto
    manager._mark_dirty()


def save_glossary_entries(
    manager: "ManifestManager",
    entries: List[Dict[str, Any]]
) -> None:
    """Save project glossary entries to manifest.
    
    Glossary entries stored in project manifest:
    - source: str (original text)
    - target: str (translated text)
    - category: str (name, term, place, etc.)
    - gender: str (Male, Female, Non-Binary, etc.)
    - context: str (usage context)
    - notes: str (additional notes)
    - active: bool (TASK 41.10 — whether entry is used in prompt)
    
    Args:
        manager: ManifestManager instance.
        entries: List of glossary entry dictionaries.
    """
    if not isinstance(entries, list):
        entries = []
    
    cleaned = []
    for entry in entries:
        if isinstance(entry, dict):
            cleaned.append({
                "source": str(entry.get("source", "")),
                "target": str(entry.get("target", "")),
                "category": str(entry.get("category", "")),
                "gender": str(entry.get("gender", "")),
                "context": str(entry.get("context", "")),
                "notes": str(entry.get("notes", "")),
                "active": bool(entry.get("active", True)),
            })
    
    # Store in glossary.project_entries
    if "glossary" not in manager._manifest_data:
        manager._manifest_data["glossary"] = {}
    manager._manifest_data["glossary"]["project_entries"] = cleaned
    manager._mark_dirty()
    logger.debug("Saved %d glossary entries", len(cleaned))


def load_glossary_entries(
    manager: "ManifestManager"
) -> List[Dict[str, Any]]:
    """Load project glossary entries from manifest.
    
    Returns list of entry dicts with fields:
    source, target, category, context, notes, active
    
    Args:
        manager: ManifestManager instance.
        
    Returns:
        List of glossary entry dictionaries.
    """
    glossary = manager._manifest_data.get("glossary", {})
    if not isinstance(glossary, dict):
        return []
    
    entries = glossary.get("project_entries", [])
    if not isinstance(entries, list):
        return []
    
    result = []
    for entry in entries:
        if isinstance(entry, dict):
            result.append({
                "source": str(entry.get("source", "")),
                "target": str(entry.get("target", "")),
                "category": str(entry.get("category", "")),
                "gender": str(entry.get("gender", "")),
                "context": str(entry.get("context", "")),
                "notes": str(entry.get("notes", "")),
                "active": bool(entry.get("active", True)),
            })
    
    return result


# ========================== Information Metadata Helpers ========================== #


def save_info_metadata_field(
    manager: "ManifestManager", key: str, value: str
) -> None:
    """Save a text field into step_state.Information.data.metadata.

    This is the canonical write path for project metadata fields that
    used to live at the top level (ProjectName, SourceLanguage, etc.).

    Args:
        manager: ManifestManager instance.
        key: snake_case metadata key (e.g. ``project_name``).
        value: Text value to save.
    """
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    manager.set_info_metadata_field(key, value)
    logger.debug("Saved info metadata %s = %r", key, value[:50] if value else "")


def load_info_metadata_field(
    manager: "ManifestManager", key: str, default: str = ""
) -> str:
    """Load a text field from step_state.Information.data.metadata.

    Args:
        manager: ManifestManager instance.
        key: snake_case metadata key (e.g. ``project_name``).
        default: Default value if not found.

    Returns:
        Text value or *default*.
    """
    value = manager.get_info_metadata_field(key, default)
    if value is None:
        return default
    return str(value)
