"""CherryAI Output Resolution — Injection Priority Chain.

Resolves the final text for each line using a 9-level priority chain:
overwrite → wordwr → postpro → edit{N} (highest) → tlc{N} (highest) →
tl → preedit → prepro → orig.

This module is used by the Output step (Step 9) to determine which text
to inject into output files.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Ordered priority chain (highest → lowest)
PRIORITY_CHAIN: List[str] = [
    "overwrite",
    "wordwr",
    "postpro",
    # edit{N} and tlc{N} are handled dynamically (highest N first)
    "tl",
    "preedit",
    "prepro",
    "orig",
]

# Pattern for numbered fields (edit1, edit2, tlc1, tlc2, etc.)
_NUMBERED_FIELD_RE = re.compile(r"^(edit|tlc)(\d+)$")


def _find_highest_numbered_field(
    line_entry: Dict[str, Any],
    prefix: str,
) -> Optional[Tuple[str, str]]:
    """Find the highest-numbered field with a non-empty value.

    Scans line_entry for keys matching ``{prefix}{N}`` and returns the
    value from the highest N that has non-empty content.

    Args:
        line_entry: Manifest line dictionary.
        prefix: Field prefix (``"edit"`` or ``"tlc"``).

    Returns:
        Tuple of (field_name, value) or None if none found.
    """
    best_n: int = -1
    best_key: Optional[str] = None
    best_val: Optional[str] = None

    for key, val in line_entry.items():
        m = _NUMBERED_FIELD_RE.match(key)
        if m and m.group(1) == prefix:
            n = int(m.group(2))
            if n > best_n and val and str(val).strip():
                best_n = n
                best_key = key
                best_val = str(val)

    if best_key is not None and best_val is not None:
        return (best_key, best_val)
    return None


def get_final_output(line_entry: Dict[str, Any]) -> Tuple[str, str]:
    """Resolve the final output text for a single line.

    Walks the 9-level priority chain and returns the first non-empty
    value found, along with the field name that provided it.

    Priority (highest → lowest):
        1. ``overwrite`` — manually overwritten / injection-ready text
        2. ``wordwr``    — wordwrapped text
        3. ``postpro``   — postprocessed text
        4. ``edit{N}``   — highest-numbered edit round
        5. ``tlc{N}``    — highest-numbered TLC round
        6. ``tl``        — base translation
        7. ``preedit``   — pre-edited text
        8. ``prepro``    — preprocessed text
        9. ``orig``      — original source text

    Args:
        line_entry: A single manifest line dictionary.

    Returns:
        Tuple of (resolved_text, source_field_name).
        If no field has content, returns (``""``, ``"none"``).
    """
    # Check fixed-priority fields first (overwrite, wordwr, postpro)
    for field in ("overwrite", "wordwr", "postpro"):
        val = line_entry.get(field)
        if val and str(val).strip():
            return (str(val), field)

    # Check edit{N} — highest N wins
    edit_result = _find_highest_numbered_field(line_entry, "edit")
    if edit_result is not None:
        return (edit_result[1], edit_result[0])

    # Check tlc{N} — highest N wins
    tlc_result = _find_highest_numbered_field(line_entry, "tlc")
    if tlc_result is not None:
        return (tlc_result[1], tlc_result[0])

    # Check remaining fixed-priority fields (tl, preedit, prepro, orig)
    for field in ("tl", "preedit", "prepro", "orig"):
        val = line_entry.get(field)
        if val and str(val).strip():
            return (str(val), field)

    return ("", "none")


def resolve_all_lines(
    lines: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    """Resolve final output for all lines.

    Args:
        lines: List of manifest line dictionaries.

    Returns:
        List of (resolved_text, source_field) tuples, one per line.
    """
    return [get_final_output(line) for line in lines]


def get_source_breakdown(
    lines: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Get breakdown of how many lines came from each priority level.

    Args:
        lines: List of manifest line dictionaries.

    Returns:
        Dict mapping field names to counts (e.g. ``{"tl": 50, "orig": 10}``).
    """
    breakdown: Dict[str, int] = {}
    for line in lines:
        _, source = get_final_output(line)
        breakdown[source] = breakdown.get(source, 0) + 1
    return breakdown
