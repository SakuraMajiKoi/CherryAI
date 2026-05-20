"""CherryAI Output Resolution — Injection Priority Chain.

Resolves the final text for each line using the shared manifest pipeline first:
final → wordwr → qa → postpro → tl → prepro → orig.

Legacy fields (``overwrite``, ``edit{N}``, ``tlc{N}``, ``preedit``) are only
consulted as fallbacks when the canonical manifest pipeline has no text.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from CherryAI.formats.parser_base import _split_speaker_dialogue
from .manifest_fields import resolve_line_field_with_source

logger = logging.getLogger(__name__)

# Ordered priority chain (highest → lowest)
PRIORITY_CHAIN: List[str] = [
    "final",
    "overwrite",
    "wordwr",
    "qa",
    "postpro",
    # edit{N} and tlc{N} are handled dynamically (highest N first)
    "tl",
    "preedit",
    "prepro",
    "orig",
]

# Pattern for numbered fields (edit1, edit2, tlc1, tlc2, etc.)
_NUMBERED_FIELD_RE = re.compile(r"^(edit|tlc)(\d+)$")


def sanitize_output_text(text: Any) -> str:
    """Strip only trailing newline markers before writing or logging output."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return text.rstrip("\r\n")


def normalize_whitespace_for_comparison(text: str) -> str:
    """Normalize speaker-aware whitespace for injection verification.

    If the text uses the shared ``Speaker: dialogue`` contract, keep the
    speaker exactly as-is and trim only the dialogue segment. Otherwise trim
    leading and trailing whitespace from the full string.
    """
    speaker, dialogue = _split_speaker_dialogue(text)
    if speaker:
        return f"{speaker}: {dialogue.strip()}"
    return text.strip()


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

    Walks the final-output priority chain and returns the first non-empty
    value found, along with the field name that provided it.

    Priority (highest → lowest):
        1. ``final``     — final manual output
        2. ``wordwr``    — wordwrapped text
        3. ``qa``        — QA-reviewed text
        4. ``postpro``   — postprocessed text
        5. ``tl``        — base translation
        6. ``prepro``    — preprocessed text
        7. ``orig``      — original source text
        8. legacy ``overwrite`` / ``edit{N}`` / ``tlc{N}`` / ``preedit`` fallbacks

    Args:
        line_entry: A single manifest line dictionary.

    Returns:
        Tuple of (resolved_text, source_field_name).
        If no field has content, returns (``""``, ``"none"``).
    """
    resolved_text, resolved_field = resolve_line_field_with_source(line_entry)
    if resolved_text:
        return (sanitize_output_text(resolved_text), resolved_field)

    # Check fixed-priority legacy fields only when canonical pipeline is empty.
    for field in ("overwrite", "postpro"):
        val = line_entry.get(field)
        if val and str(val).strip():
            return (sanitize_output_text(val), field)

    # Check edit{N} — highest N wins
    edit_result = _find_highest_numbered_field(line_entry, "edit")
    if edit_result is not None:
        return (sanitize_output_text(edit_result[1]), edit_result[0])

    # Check tlc{N} — highest N wins
    tlc_result = _find_highest_numbered_field(line_entry, "tlc")
    if tlc_result is not None:
        return (sanitize_output_text(tlc_result[1]), tlc_result[0])

    # Check remaining fixed-priority legacy fields.
    for field in ("preedit",):
        val = line_entry.get(field)
        if val and str(val).strip():
            return (sanitize_output_text(val), field)

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
