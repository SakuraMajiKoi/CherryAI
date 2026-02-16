"""Lenient JSON format handler for CherryAI.

TASK 17.4: Supports reading "bad" JSON files that are not strictly valid:
- Trailing commas
- Single quotes instead of double quotes
- Unquoted keys
- C-style comments (// and /* */)

The handler sanitises the input into valid JSON, extracts translatable
string values, and writes the translated content back as valid JSON.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import FormatHandler

__all__ = ["JsonLenientHandler", "get_handlers"]

logger = logging.getLogger(__name__)


# Regex patterns for sanitisation
_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_SINGLE_QUOTED = re.compile(r"(?<=[\[{,:\s])'((?:[^'\\]|\\.)*)'")
_UNQUOTED_KEY = re.compile(r'(?<=[{,])\s*([A-Za-z_]\w*)\s*:')


def sanitise_json(raw: str) -> str:
    """Sanitise lenient JSON into strict JSON.

    Handles:
    - C-style comments (``//`` and ``/* … */``)
    - Trailing commas before ``}`` or ``]``
    - Single-quoted strings (converted to double-quoted)
    - Unquoted object keys

    Args:
        raw: Raw JSON-like text.

    Returns:
        A cleaned string that ``json.loads`` can parse.
    """
    text = raw

    # 1. Remove block comments first (may span multiple lines)
    text = _BLOCK_COMMENT.sub("", text)

    # 2. Remove line comments (be careful not to remove // inside strings)
    # Simple approach: remove // only outside of strings
    text = _remove_line_comments(text)

    # 3. Convert single-quoted strings to double-quoted
    text = _single_to_double_quotes(text)

    # 4. Quote unquoted keys
    text = _UNQUOTED_KEY.sub(r' "\1":', text)

    # 5. Remove trailing commas
    text = _TRAILING_COMMA.sub(r"\1", text)

    return text


def _remove_line_comments(text: str) -> str:
    """Remove ``//`` line comments while respecting strings."""
    result: List[str] = []
    in_string = False
    escape_next = False
    string_char = ""
    i = 0

    while i < len(text):
        ch = text[i]

        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue

        if ch == "\\":
            escape_next = True
            result.append(ch)
            i += 1
            continue

        if in_string:
            result.append(ch)
            if ch == string_char:
                in_string = False
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            result.append(ch)
            i += 1
            continue

        # Check for // comment
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            # Skip to end of line
            while i < len(text) and text[i] != "\n":
                i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def _single_to_double_quotes(text: str) -> str:
    """Convert single-quoted strings to double-quoted (outside of double-quoted strings)."""
    result: List[str] = []
    in_double = False
    in_single = False
    escape_next = False
    i = 0

    while i < len(text):
        ch = text[i]

        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue

        if ch == "\\":
            escape_next = True
            result.append(ch)
            i += 1
            continue

        if in_double:
            result.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if in_single:
            if ch == "'":
                result.append('"')
                in_single = False
            elif ch == '"':
                # Escape an interior double-quote
                result.append('\\"')
            else:
                result.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            result.append(ch)
        elif ch == "'":
            in_single = True
            result.append('"')
        else:
            result.append(ch)

        i += 1

    return "".join(result)


class JsonLenientHandler(FormatHandler):
    """Lenient JSON handler that accepts "bad" JSON.

    Sanitises the input before parsing, then extracts string values
    in the same fashion as the standard JSON handler.
    """

    format_id = "json_lenient"
    extensions = (".json5", ".jsonc")
    description = "Lenient JSON (comments, trailing commas, single quotes)"
    supports_pairs = True

    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract text lines from a lenient JSON file.

        Strings are extracted from:
        - A top-level JSON array of strings.
        - A top-level JSON array of ``[original, translated]`` pairs
          → returns the *original* column.
        - A top-level JSON object values (string values only, sorted by key).

        Args:
            path: Path to the JSON(-ish) file.
            encoding: Text encoding.

        Returns:
            List of text lines.
        """
        if not path.exists():
            logger.error("Lenient JSON file not found: %s", path)
            return []

        raw = path.read_text(encoding=encoding)
        clean = sanitise_json(raw)

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse lenient JSON: %s", exc)
            return []

        return _extract_strings(data)

    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8",
    ) -> None:
        """Write translated lines as valid JSON.

        Output is always strict JSON. If *original_lines* is provided, writes
        ``[[original, translated], …]`` pairs.  Otherwise, writes a flat
        ``[line, …]`` array.

        Args:
            path: Path to write the file.
            lines: Translated lines.
            original_lines: Optional original lines for pair output.
            encoding: Text encoding.
        """
        if original_lines and len(original_lines) == len(lines):
            data: Any = [
                [orig, tl] for orig, tl in zip(original_lines, lines)
            ]
        else:
            data = lines

        json_text = json.dumps(data, ensure_ascii=False, indent=2)
        path.write_text(json_text, encoding=encoding, newline="")

    def get_metadata(self, path: Path) -> Dict[str, Any]:
        """Extract metadata from a lenient JSON file."""
        meta = super().get_metadata(path)
        if not path.exists():
            return meta

        try:
            raw = path.read_text(encoding="utf-8")
            clean = sanitise_json(raw)
            data = json.loads(clean)
            if isinstance(data, list):
                meta["entry_count"] = len(data)
                meta["structure"] = "array"
            elif isinstance(data, dict):
                meta["entry_count"] = len(data)
                meta["structure"] = "object"
            meta["sanitised"] = raw != clean
        except Exception as exc:
            logger.warning("Failed to read lenient JSON metadata: %s", exc)

        return meta


def _extract_strings(data: Any) -> List[str]:
    """Extract translatable strings from parsed JSON data."""
    if isinstance(data, list):
        result: List[str] = []
        for item in data:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, list) and len(item) >= 1:
                # Take the first element (original)
                result.append(str(item[0]))
        return result

    if isinstance(data, dict):
        return [str(v) for v in data.values() if isinstance(v, str)]

    return []


def get_handlers() -> List[FormatHandler]:
    """Return all lenient JSON format handlers."""
    return [JsonLenientHandler()]
