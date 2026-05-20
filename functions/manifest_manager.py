"""CherryAI Manifest Manager.

Unified state management using the manifest as the single source of truth.
Replaces the previous session-based system (gui/state/store.py).

TASK 19: All GUI state is now stored in the manifest file, including:
- Step state (status, last run, configuration)
- Project metadata (name, languages, style, characters)
- Translation data (lines with all progressive fields)
- Glossary entries (project-specific)
- Operations and mappings

Save Triggers (automatic):
- On close (WM_DELETE_WINDOW)
- On step change (tab switch)
- Before translation start
- During translation (after each batch)
- Autosave interval (TASK 29.1)

No manual save buttons required.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import codecs
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .mainhelper import Manifest, LineEntry, Operation

logger = logging.getLogger(__name__)


DEDUP_PLACEHOLDER = "__DEDUP__"
CONTENT_TAGS = frozenset({"file_end", "dialogue", "menu", "choice", "variable", "items"})
SOURCE_TEXT_ENCODING_CANDIDATES = (
    "utf-8-sig",
    "utf-8",
    "cp932",
    "shift_jis",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
)


def parse_line_tags(raw_tags: Any) -> List[str]:
    """Normalize manifest line tags into an ordered, duplicate-free list."""
    if raw_tags is None:
        return []

    if isinstance(raw_tags, str):
        candidates = raw_tags.split(",")
    elif isinstance(raw_tags, (list, tuple, set)):
        candidates = raw_tags
    else:
        candidates = [raw_tags]

    result: List[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        tag = str(candidate).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return result


def merge_line_tags(*raw_values: Any) -> str:
    """Merge one or more raw tag values into a canonical tag string."""
    merged: List[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        for tag in parse_line_tags(raw_value):
            if tag in seen:
                continue
            seen.add(tag)
            merged.append(tag)
    return ",".join(merged)


def has_line_tag(line_data: Dict[str, Any], tag: str) -> bool:
    """Return whether a line contains the given canonical tag."""
    clean_tag = str(tag).strip()
    if not clean_tag:
        return False
    return clean_tag in parse_line_tags(line_data.get("tags"))


def get_primary_line_tag(line_data: Dict[str, Any]) -> str:
    """Return the line's primary content tag from tags or legacy fields."""
    for tag in parse_line_tags(line_data.get("tags")):
        if tag in CONTENT_TAGS:
            return tag

    for field in ("tag", "context_marker"):
        raw_tag = str(line_data.get(field, "")).strip()
        if raw_tag:
            return raw_tag
    return ""


def set_primary_line_tag(line_data: Dict[str, Any], tag: str) -> None:
    """Store a content tag in canonical tags form without legacy tag fields."""
    non_content_tags = [
        existing_tag
        for existing_tag in parse_line_tags(line_data.get("tags"))
        if existing_tag not in CONTENT_TAGS
    ]
    clean_tag = tag.strip()
    if clean_tag:
        non_content_tags.append(clean_tag)

    merged_tags = merge_line_tags(non_content_tags)
    if merged_tags:
        line_data["tags"] = merged_tags
    else:
        line_data.pop("tags", None)


def _read_source_text_for_manifest(path: Path) -> str:
    """Read text files for manifest bootstrapping without assuming UTF-8.

    Project creation may ingest source scripts before a parser-specific extraction
    pass runs. KiriKiri sources are commonly cp932/Shift-JIS, so this bootstrap
    read must not hard-fail on UTF-8-only assumptions.
    """
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig")
    if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        return data.decode("utf-16")

    for encoding in SOURCE_TEXT_ENCODING_CANDIDATES:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return data.decode("utf-8", errors="replace")

    line_data.pop("tag", None)
    line_data.pop("context_marker", None)


def _should_keep_line_value(value: Any) -> bool:
    """Return True when a sparse manifest field should be serialized."""
    if value is None:
        return False
    if isinstance(value, str):
        return value != ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    if isinstance(value, bool):
        return value
    return True


def _coerce_int(value: Any, default: int = 0) -> int:
    """Return *value* as ``int`` when possible, else *default*."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_positive_int(value: Any) -> Optional[int]:
    """Return *value* as a positive integer, or ``None`` when invalid."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 1 else None


def _default_line_number(idx: int) -> int:
    """Return the fallback 1-based line number for a global line index."""
    return max(1, idx + 1)


def _extract_line_number(line_data: Dict[str, Any]) -> Optional[int]:
    """Read ``ln`` or legacy ``line`` from a raw line dict."""
    ln_value = _coerce_positive_int(line_data.get("ln"))
    if ln_value is not None:
        return ln_value
    return _coerce_positive_int(line_data.get("line"))


def _extract_field_discriminator(line_data: Dict[str, Any]) -> Optional[int]:
    """Read optional ``f`` or legacy ``field`` from a raw line dict."""
    field_value = _coerce_positive_int(line_data.get("f"))
    if field_value is not None:
        return field_value
    return _coerce_positive_int(line_data.get("field"))


def _backfill_line_mapping(
    lines: List[Dict[str, Any]],
    filedir: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Populate missing ``ln``/``f`` data from current line and file metadata."""
    normalized = [deepcopy(line) for line in lines]
    if not normalized:
        return normalized

    sorted_lines = sorted(normalized, key=lambda line: _coerce_int(line.get("idx"), 0))
    covered_indices: set[int] = set()
    line_position = 0

    for raw_entry in sorted(
        filedir or [],
        key=lambda entry: _coerce_int(entry.get("first_idx"), 0),
    ):
        first_idx = _coerce_int(raw_entry.get("first_idx"), 0)
        last_idx = _coerce_int(raw_entry.get("last_idx"), first_idx - 1)
        while line_position < len(sorted_lines):
            current_idx = _coerce_int(sorted_lines[line_position].get("idx"), 0)
            if current_idx >= first_idx:
                break
            line_position += 1

        probe_position = line_position
        local_line_number = 1
        while probe_position < len(sorted_lines):
            line = sorted_lines[probe_position]
            idx = _coerce_int(line.get("idx"), 0)
            if idx > last_idx:
                break

            explicit_line_number = _extract_line_number(line)
            if explicit_line_number is None:
                line["ln"] = local_line_number
            else:
                line["ln"] = explicit_line_number
            field_value = _extract_field_discriminator(line)
            if field_value is not None:
                line["f"] = field_value
            line.pop("line", None)
            line.pop("field", None)
            covered_indices.add(idx)
            local_line_number += 1
            probe_position += 1

    for line in sorted_lines:
        idx = _coerce_int(line.get("idx"), 0)
        if idx in covered_indices:
            continue
        explicit_line_number = _extract_line_number(line)
        if explicit_line_number is None:
            line["ln"] = _default_line_number(idx)
        else:
            line["ln"] = explicit_line_number
        field_value = _extract_field_discriminator(line)
        if field_value is not None:
            line["f"] = field_value
        line.pop("line", None)
        line.pop("field", None)

    return normalized


def _mapping_search_tokens(text: str) -> List[str]:
    """Return ordered candidate substrings for source-line matching.

    The first token is always the full extracted text. For speaker-prefixed
    dialogue like ``Speaker: text``, the dialogue payload is also added so
    parser outputs can still align with raw script lines that only contain the
    spoken text.
    """
    clean_text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    tokens: List[str] = []
    for candidate in (clean_text, clean_text.split(": ", 1)[1] if ": " in clean_text else ""):
        if candidate and candidate not in tokens:
            tokens.append(candidate)
    return tokens


def _source_window_matches(lines: List[str], start_idx: int, token: str) -> bool:
    """Return whether *token* appears in a source line window starting at *start_idx*."""
    if start_idx < 0 or start_idx >= len(lines):
        return False

    normalized_token = token.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized_token:
        return False

    window = lines[start_idx]
    if normalized_token in window:
        return True

    if "\n" not in normalized_token:
        return False

    max_extra_lines = min(len(normalized_token.split("\n")) - 1, len(lines) - start_idx - 1)
    for extra_lines in range(1, max_extra_lines + 1):
        window = "\n".join(lines[start_idx:start_idx + extra_lines + 1])
        if normalized_token in window:
            return True
    return False


def capture_source_line_mappings(
    source_text: str,
    extracted_lines: List[str],
) -> List[Dict[str, int]]:
    """Map extracted lines back to 1-based source line numbers and optional fields.

    The mapping is sequential and local: each extracted item is assigned to the
    earliest source line at or after the previous match whose raw text contains
    the extracted payload (or, for speaker-prefixed dialogue, the dialogue
    portion). When multiple extracted items map to the same physical line, all
    of them receive an ``f`` discriminator starting at 1.
    """
    physical_lines = source_text.splitlines()
    if not physical_lines:
        return [{"ln": max(1, i + 1)} for i, _ in enumerate(extracted_lines)]

    matched_line_numbers: List[int] = []
    search_start = 0
    last_match_idx = 0

    for extracted in extracted_lines:
        match_idx: Optional[int] = None
        tokens = _mapping_search_tokens(extracted)
        for candidate_idx in range(search_start, len(physical_lines)):
            if any(_source_window_matches(physical_lines, candidate_idx, token) for token in tokens):
                match_idx = candidate_idx
                break

        if match_idx is None:
            match_idx = min(last_match_idx, len(physical_lines) - 1)

        matched_line_numbers.append(match_idx + 1)
        last_match_idx = match_idx
        search_start = match_idx

    line_counts: Dict[int, int] = {}
    for line_number in matched_line_numbers:
        line_counts[line_number] = line_counts.get(line_number, 0) + 1

    line_offsets: Dict[int, int] = {}
    mappings: List[Dict[str, int]] = []
    for line_number in matched_line_numbers:
        mapping: Dict[str, int] = {"ln": line_number}
        if line_counts.get(line_number, 0) > 1:
            next_offset = line_offsets.get(line_number, 0) + 1
            line_offsets[line_number] = next_offset
            mapping["f"] = next_offset
        mappings.append(mapping)

    return mappings


def build_line_locator_index(
    lines: List[Dict[str, Any]],
    *,
    first_idx: Optional[int] = None,
    last_idx: Optional[int] = None,
) -> Dict[tuple[int, Optional[int]], Dict[str, Any]]:
    """Index manifest rows by ``(ln, f)`` for a single file slice."""
    result: Dict[tuple[int, Optional[int]], Dict[str, Any]] = {}
    for line in lines:
        idx = _coerce_int(line.get("idx"), 0)
        if first_idx is not None and idx < first_idx:
            continue
        if last_idx is not None and idx > last_idx:
            continue
        locator = (
            _coerce_positive_int(line.get("ln")) or _default_line_number(idx),
            _coerce_positive_int(line.get("f")),
        )
        result[locator] = line
    return result


def match_manifest_lines_to_source(
    source_text: str,
    extracted_lines: List[str],
    manifest_lines: List[Dict[str, Any]],
    *,
    first_idx: Optional[int] = None,
    last_idx: Optional[int] = None,
) -> List[Optional[Dict[str, Any]]]:
    """Match extracted source lines to manifest rows using captured ``ln``/``f`` locators."""
    locator_index = build_line_locator_index(
        manifest_lines,
        first_idx=first_idx,
        last_idx=last_idx,
    )
    source_mappings = capture_source_line_mappings(source_text, extracted_lines)
    matched_rows: List[Optional[Dict[str, Any]]] = []
    for mapping in source_mappings:
        locator = (mapping["ln"], mapping.get("f"))
        matched_rows.append(locator_index.get(locator))
    return matched_rows


def refresh_file_line_locators(
    lines: List[Dict[str, Any]],
    entry: "FileDirEntry",
    source_text: str,
    extracted_lines: List[str],
) -> bool:
    """Refresh ``ln``/``f`` locators for one file slice in place.

    This is used when the staged source view for a file changes without a full
    Step 0 rebuild. The helper reapplies CherryAI's shared source-line mapping
    to the existing manifest rows for the file's ``first_idx:last_idx`` slice.

    Returns:
        True when at least one line locator changed.
    """
    slice_lines = [
        line
        for line in lines
        if entry.first_idx <= _coerce_int(line.get("idx"), -1) <= entry.last_idx
    ]
    if not slice_lines or not extracted_lines:
        return False

    mappings = capture_source_line_mappings(source_text, extracted_lines)
    if len(slice_lines) != len(mappings):
        logger.warning(
            "Locator refresh count mismatch for %s: manifest=%d, extracted=%d",
            entry.rel_path,
            len(slice_lines),
            len(mappings),
        )

    changed = False
    for line_data, mapping in zip(slice_lines, mappings):
        current_ln = _coerce_positive_int(line_data.get("ln")) or _default_line_number(
            _coerce_int(line_data.get("idx"), 0)
        )
        current_f = _coerce_positive_int(line_data.get("f"))
        next_ln = mapping["ln"]
        next_f = mapping.get("f")

        if current_ln == next_ln and current_f == next_f:
            continue

        line_data["ln"] = next_ln
        if next_f is None:
            line_data.pop("f", None)
        else:
            line_data["f"] = next_f
        line_data.pop("line", None)
        line_data.pop("field", None)

        canonical = canonicalize_line_dict(line_data)
        line_data.clear()
        line_data.update(canonical)
        changed = True

    return changed


def canonicalize_line_dict(line_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw line dict into canonical CherryAI manifest order."""
    source = deepcopy(line_data)
    merged_tags = merge_line_tags(
        source.get("tags"),
        source.get("tag"),
        source.get("context_marker"),
    )

    idx = _coerce_int(source.get("idx"), 0)
    line_number = _extract_line_number(source)
    field_discriminator = _extract_field_discriminator(source)

    result: Dict[str, Any] = {"idx": idx, "ln": line_number or _default_line_number(idx)}
    if field_discriminator is not None:
        result["f"] = field_discriminator
    if merged_tags:
        result["tags"] = merged_tags
    result["orig"] = source.get("orig", "")

    for field in ("prepro", "tl", "postpro", "qa", "qa_overwrite", "wordwr", "final"):
        if field in source and _should_keep_line_value(source[field]):
            result[field] = source[field]

    trailing_fields = [
        "prepro_ops",
        "edited_prepro",
        "preedit",
        "overwrite",
        "log",
        "deleted",
        "updated",
    ]
    for field in trailing_fields:
        if field in source and _should_keep_line_value(source[field]):
            result[field] = source[field]

    dynamic_keys = sorted(
        key
        for key in source
        if (
            (key.startswith("tlc") and key[3:].isdigit())
            or (key.startswith("edit") and key[4:].isdigit())
        )
    )
    for key in dynamic_keys:
        if _should_keep_line_value(source[key]):
            result[key] = source[key]

    handled_keys = {
        "idx",
        "ln",
        "line",
        "f",
        "field",
        "tags",
        "tag",
        "context_marker",
        "orig",
        "prepro",
        "tl",
        "postpro",
        "qa",
        "qa_overwrite",
        "wordwr",
        "final",
        "prepro_ops",
        "edited_prepro",
        "preedit",
        "overwrite",
        "log",
        "deleted",
        "updated",
        *dynamic_keys,
    }
    for key, value in source.items():
        if key in handled_keys:
            continue
        if _should_keep_line_value(value):
            result[key] = value

    return result


def _line_is_canonical(line_data: Any, previous_idx: int | None) -> bool:
    """Return whether a line already matches CherryAI's canonical load shape."""
    if not isinstance(line_data, dict):
        return False

    idx = _coerce_int(line_data.get("idx"), 0)
    if previous_idx is not None and idx < previous_idx:
        return False

    if "orig" not in line_data:
        return False

    if _extract_line_number(line_data) is None:
        return False

    if any(key in line_data for key in ("line", "field", "tag", "context_marker")):
        return False

    raw_tags = line_data.get("tags")
    if raw_tags is not None:
        if not isinstance(raw_tags, str):
            return False
        if merge_line_tags(raw_tags) != raw_tags:
            return False

    if "f" in line_data and _extract_field_discriminator(line_data) is None:
        return False

    return True


def _lines_are_canonical(lines: List[Dict[str, Any]]) -> bool:
    """Return whether a manifest line array can bypass canonicalization."""
    previous_idx: int | None = None
    for line_data in lines:
        if not _line_is_canonical(line_data, previous_idx):
            return False
        previous_idx = _coerce_int(line_data.get("idx"), 0)
    return True


def _lines_need_locator_backfill(lines: List[Dict[str, Any]]) -> bool:
    """Return whether lines still contain legacy locator fields or gaps."""
    for line_data in lines:
        if _extract_line_number(line_data) is None:
            return True
        if "line" in line_data or "field" in line_data:
            return True
    return False


def canonicalize_lines(
    lines: List[Dict[str, Any]],
    filedir: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Normalize and sort line dictionaries by idx."""
    if not lines:
        return []

    if _lines_are_canonical(lines):
        return lines

    normalized = (
        _backfill_line_mapping(lines, filedir)
        if _lines_need_locator_backfill(lines)
        else lines
    )
    return [
        canonicalize_line_dict(line)
        for line in sorted(normalized, key=lambda item: _coerce_int(item.get("idx"), 0))
    ]


class _SafeManifestEncoder(json.JSONEncoder):
    """Defensive JSON encoder for manifest saves.

    Converts objects with a ``to_dict()`` method (e.g. ``TableRow``,
    ``FileDirEntry``) to plain dicts, and ``Path`` objects to strings.
    Prevents "is not JSON serializable" crashes during autosave if GUI
    objects leak into ``_manifest_data``.
    """

    def default(self, o: Any) -> Any:
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if isinstance(o, Path):
            return str(o)
        return super().default(o)


def _manifest_json_default(value: Any) -> Any:
    """Return a JSON-serializable representation for manifest values."""
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _to_manifest_jsonable(value: Any) -> Any:
    """Recursively normalize manifest values into JSON-safe primitives."""
    try:
        normalized = _manifest_json_default(value)
    except TypeError:
        normalized = value

    if isinstance(normalized, dict):
        return {
            str(key): _to_manifest_jsonable(item)
            for key, item in normalized.items()
        }
    if isinstance(normalized, list):
        return [_to_manifest_jsonable(item) for item in normalized]
    return normalized


def _format_manifest_compact_json(value: Any) -> str:
    """Return a compact single-line JSON fragment for *value*."""
    return json.dumps(
        _to_manifest_jsonable(value),
        ensure_ascii=False,
        separators=(", ", ": "),
    )


def _format_manifest_compact_object(value: Dict[str, Any]) -> str:
    """Return a spaced one-line JSON object for compact manifest arrays."""
    normalized = _to_manifest_jsonable(value)
    if not normalized:
        return "{}"
    parts = [
        f'{json.dumps(key, ensure_ascii=False)}: {_format_manifest_compact_json(item)}'
        for key, item in normalized.items()
    ]
    return "{ " + ", ".join(parts) + " }"


def _format_manifest_line_object(line_data: Dict[str, Any], indent: int) -> str:
    """Format a manifest line entry with compact locators and one field per line."""
    locator_keys = [key for key in ("idx", "ln", "f", "tags") if key in line_data]
    payload_keys = [key for key in line_data if key not in locator_keys]

    first_parts = [
        f'{json.dumps(key, ensure_ascii=False)}: {_format_manifest_compact_json(line_data[key])}'
        for key in locator_keys
    ]
    if payload_keys:
        first_line = "{ " + ", ".join(first_parts) + ","
    elif first_parts:
        first_line = "{ " + ", ".join(first_parts) + " }"
    else:
        first_line = "{}"

    if not payload_keys:
        return first_line

    lines = [(" " * indent) + first_line]
    payload_indent = " " * (indent + 2)
    for index, key in enumerate(payload_keys):
        value_text = _format_manifest_compact_json(line_data[key])
        suffix = "," if index < len(payload_keys) - 1 else " }"
        lines.append(
            f"{payload_indent}{json.dumps(key, ensure_ascii=False)}: {value_text}{suffix}"
        )
    return "\n".join(lines)


def _format_manifest_array_normalized(
    values: List[Any],
    indent: int,
    path: tuple[str, ...],
) -> str:
    """Format a manifest array after JSON-safe normalization."""
    if not values:
        return "[]"

    item_indent = indent + 2
    closing_indent = " " * indent
    special_compact_paths = {
        ("filedir",),
        ("code_patterns",),
        ("glossary", "project_entries"),
    }

    rendered_items: List[str] = []
    if path == ("lines",):
        rendered_items = [
            _format_manifest_line_object(item, item_indent)
            if isinstance(item, dict)
            else (" " * item_indent) + _format_manifest_compact_json(item)
            for item in values
        ]
    elif path in special_compact_paths:
        rendered_items = [
            (" " * item_indent)
            + (
                _format_manifest_compact_object(item)
                if isinstance(item, dict)
                else _format_manifest_compact_json(item)
            )
            for item in values
        ]
    else:
        rendered_items = [
            _indent_multiline(
                _format_manifest_value_normalized(item, item_indent, path + ("[]",)),
                item_indent,
            )
            for item in values
        ]

    return "[\n" + ",\n".join(rendered_items) + "\n" + closing_indent + "]"


def _format_manifest_dict_normalized(
    data: Dict[str, Any],
    indent: int,
    path: tuple[str, ...],
) -> str:
    """Format a manifest dict after JSON-safe normalization."""
    if not data:
        return "{}"

    indent_text = " " * indent
    child_indent = indent + 2
    rendered_items: List[str] = []
    for key, value in data.items():
        value_text = _format_manifest_value_normalized(
            value,
            child_indent,
            path + (str(key),),
        )
        value_lines = value_text.splitlines() or [value_text]
        first_line = (
            f'{" " * child_indent}{json.dumps(str(key), ensure_ascii=False)}: {value_lines[0]}'
        )
        if len(value_lines) == 1:
            rendered_items.append(first_line)
            continue
        remaining = value_lines[1:]
        rendered_items.append("\n".join([first_line, *remaining]))

    return "{\n" + ",\n".join(rendered_items) + "\n" + indent_text + "}"


def _format_manifest_value_normalized(
    normalized: Any,
    indent: int,
    path: tuple[str, ...],
) -> str:
    """Format an already-normalized manifest value using compact rules."""
    if isinstance(normalized, dict):
        return _format_manifest_dict_normalized(normalized, indent, path)
    if isinstance(normalized, list):
        return _format_manifest_array_normalized(normalized, indent, path)
    return _format_manifest_compact_json(normalized)


def _format_manifest_value(value: Any, indent: int, path: tuple[str, ...]) -> str:
    """Format a manifest value using the compact writer rules."""
    return _format_manifest_value_normalized(_to_manifest_jsonable(value), indent, path)


def _indent_multiline(text: str, indent: int) -> str:
    """Indent each line in *text* by *indent* spaces."""
    prefix = " " * indent
    return "\n".join(prefix + line if line else prefix for line in text.splitlines())


def format_manifest_json(data: Dict[str, Any]) -> str:
    """Return the manifest JSON text using CherryAI's compact writer rules."""
    return _format_manifest_value_normalized(_to_manifest_jsonable(data), 0, ()) + "\n"


# Constants
MANIFEST_DIR = Path("Projects")
MANIFEST_EXT = ".CherryAI.json"
MANIFEST_VERSION = "3.2"  # TASK 38: Optimized format - removed redundant per-line fields

CREATE_PATCH_SELECTIONS: Dict[str, bool] = {
    "import_prepro": True,
    "import_tags": True,
    "import_translated": True,
    "import_postpro": True,
    "import_wordwrap": True,
    "import_final": True,
    "import_qa": True,
    "skip_new_lines": False,
    "import_analysis": True,
    "import_information": True,
    "import_preprocessing": True,
    "import_costs": True,
    "import_translation": True,
    "import_postprocessing": True,
    "import_wordwrap_settings": True,
    "import_qa_settings": True,
    "import_file_settings": True,
}


def _file_sha256(path: Path) -> str:
    """Return a stable SHA-256 digest for *path*."""
    with path.open("rb") as handle:
        try:
            return hashlib.file_digest(handle, "sha256").hexdigest()
        except AttributeError:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            return digest.hexdigest()

# Step definitions matching GUI step order
STEP_NAMES = [
    "Input",
    "Analysis",
    "Information",
    "Preprocessing",
    "Estimation",
    "Translation",
    "Postprocessing",
    "Wordwrap",
    "Quality Assurance",
    "Output",
]


@dataclass
class StepState:
    """State for a single workflow step.
    
    Replaces gui/state/store.py::StepState but stored in manifest.
    """
    
    name: str
    status: str = "not-started"  # not-started, in-progress, completed
    skipped: bool = False
    last_run: Optional[str] = None  # ISO timestamp
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "name": self.name,
            "status": self.status,
        }
        if self.skipped:
            result["skipped"] = True
        if self.last_run:
            result["last_run"] = self.last_run
        if self.data:
            result["data"] = self._serialize_value(self.data)
        return result
    
    def _serialize_value(self, value: Any) -> Any:
        """Recursively serialize a value for JSON."""
        if hasattr(value, "to_dict"):
            return value.to_dict()
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, Path):
            return str(value)
        else:
            return value
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StepState":
        """Deserialize from dictionary."""
        return cls(
            name=d.get("name", ""),
            status=d.get("status", "not-started"),
            skipped=d.get("skipped", False),
            last_run=d.get("last_run"),
            data=d.get("data", {}),
        )
    
    def reset(self) -> None:
        """Reset step to initial state."""
        self.status = "not-started"
        self.skipped = False
        self.last_run = None
        self.data = {}


@dataclass
class ProjectInfo:
    """Project metadata stored in manifest.
    
    Consolidates InformationStep metadata into manifest.
    """
    
    project_name: str = ""
    game_title: str = ""
    source_language: str = "Japanese"
    target_language: str = "English"
    genre: str = ""
    summary: str = ""
    style_preset: str = "natural"
    custom_style: str = ""
    tone_preset: str = "neutral"
    custom_tone: str = ""
    system_instructions: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (sparse - only non-empty values)."""
        result: Dict[str, Any] = {}
        if self.project_name:
            result["project_name"] = self.project_name
        if self.game_title:
            result["game_title"] = self.game_title
        if self.source_language != "Japanese":
            result["source_language"] = self.source_language
        if self.target_language != "English":
            result["target_language"] = self.target_language
        if self.genre:
            result["genre"] = self.genre
        if self.summary:
            result["summary"] = self.summary
        if self.style_preset != "natural":
            result["style_preset"] = self.style_preset
        if self.custom_style:
            result["custom_style"] = self.custom_style
        if self.tone_preset != "neutral":
            result["tone_preset"] = self.tone_preset
        if self.custom_tone:
            result["custom_tone"] = self.custom_tone
        if self.system_instructions:
            result["system_instructions"] = self.system_instructions
        return result
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProjectInfo":
        """Deserialize from dictionary."""
        return cls(
            project_name=d.get("project_name", ""),
            game_title=d.get("game_title", ""),
            source_language=d.get("source_language", "Japanese"),
            target_language=d.get("target_language", "English"),
            genre=d.get("genre", ""),
            summary=d.get("summary", ""),
            style_preset=d.get("style_preset", "natural"),
            custom_style=d.get("custom_style", ""),
            tone_preset=d.get("tone_preset", "neutral"),
            custom_tone=d.get("custom_tone", ""),
            system_instructions=d.get("system_instructions", d.get("custom_notes", "")),
        )


@dataclass
class GlossaryConfig:
    """Glossary configuration in manifest.
    
    Controls whether to use global glossary and stores project-specific entries.
    """
    
    use_global: bool = True  # Use global user/glossary.csv
    project_entries: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {"use_global": self.use_global}
        if self.project_entries:
            result["project_entries"] = self.project_entries
        return result
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GlossaryConfig":
        """Deserialize from dictionary."""
        return cls(
            use_global=d.get("use_global", True),
            project_entries=d.get("project_entries", []),
        )


@dataclass
class FileDirEntry:
    """File directory entry mapping line index ranges to source files.
    
    TASK 35.1: Maps global line indices to source files for input/output decoupling.
    TASK 38: Optimized - source_hint removed (use source_root + rel_path).
    
    Attributes:
        first_idx: First line index (inclusive, global 0-based).
        last_idx: Last line index (inclusive, global 0-based).
        format: File format (txt, csv, tsv, json, xlsx, rpgm, etc.).
        rel_path: Path relative to source_root (preserves folder structure).
        encoding: File encoding (utf-8, shift_jis, etc.).
        type: Content type classification (dialogue, menu?, menu, or empty).
    """
    
    first_idx: int
    last_idx: int
    format: str
    rel_path: str
    encoding: str = "utf-8"
    type: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (sparse format)."""
        result: Dict[str, Any] = {}
        if self.type:
            result["type"] = self.type
        result["first_idx"] = self.first_idx
        result["last_idx"] = self.last_idx
        result["format"] = self.format
        result["rel_path"] = self.rel_path
        if self.encoding != "utf-8":
            result["encoding"] = self.encoding
        return result
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FileDirEntry":
        """Deserialize from dictionary."""
        return cls(
            first_idx=d.get("first_idx", 0),
            last_idx=d.get("last_idx", 0),
            format=d.get("format", "txt"),
            rel_path=d.get("rel_path", ""),
            encoding=d.get("encoding", "utf-8"),
            type=d.get("type", ""),
        )
    
    @property
    def line_count(self) -> int:
        """Get number of lines in this file."""
        return self.last_idx - self.first_idx + 1
    
    def contains_idx(self, idx: int) -> bool:
        """Check if this entry contains the given line index."""
        return self.first_idx <= idx <= self.last_idx
    
    @property
    def filename(self) -> str:
        """Get just the filename from rel_path."""
        return Path(self.rel_path).name


class ManifestManager:
    """Centralized manifest operations for GUI state management.
    
    This class replaces SessionState from gui/state/store.py.
    All state is stored in a single manifest file per project.
    
    TASK 29.1: Added autosave functionality with configurable interval.
    Autosave runs in a background thread and only saves when dirty flag is set.
    
    Usage:
        manager = ManifestManager()
        manager.create_new("My Project", [Path("file.txt")])
        manager.set_step_data(3, {"metadata": {...}})
        manager.save()  # Called automatically on close/step change
        
        # Autosave (started automatically, can be disabled via INI)
        manager.start_autosave()  # Manual start if needed
        manager.stop_autosave()   # Manual stop if needed
    """
    
    def __init__(self) -> None:
        """Initialize manager with no loaded manifest."""
        self._manifest_path: Optional[Path] = None
        self._manifest_data: Dict[str, Any] = self._create_empty_manifest()
        self._dirty: bool = False
        self._change_listeners: List[Callable[[], None]] = []
        self._current_step: int = 0
        
        # TASK 29.1: Autosave configuration
        self._autosave_enabled: bool = True
        self._autosave_interval: int = 60  # seconds (matches [session] default)
        self._save_on_close: bool = True
        self._autosave_thread: Optional[threading.Thread] = None
        self._autosave_stop_event: threading.Event = threading.Event()
        self._autosave_lock: threading.Lock = threading.Lock()
        
        # Load autosave settings from INI
        self._load_autosave_settings()
        
        # Ensure manifests directory exists
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_autosave_settings(self) -> None:
        """Load autosave settings from ``[session]`` INI section.

        Reads the ``autosave`` (bool) and ``interval`` (int, seconds) keys
        that are set by Global Options → Session Settings.  ``save_on_close``
        is always ``True`` (no INI toggle — we never want to lose work).
        """
        try:
            from .ini_manager import get_default

            self._autosave_enabled = bool(
                get_default("session", "autosave", True, bool)
            )
            self._autosave_interval = int(
                get_default("session", "interval", 60, int) or 60
            )
            # save_on_close is always True — no user toggle needed
            self._save_on_close = True

            # Clamp interval to reasonable bounds (5-300 seconds)
            self._autosave_interval = max(5, min(300, self._autosave_interval))

            logger.debug(
                "Autosave settings: enabled=%s, interval=%ds, save_on_close=%s",
                self._autosave_enabled,
                self._autosave_interval,
                self._save_on_close,
            )
        except Exception as e:
            logger.warning("Failed to load autosave settings: %s", e)
    
    @property
    def autosave_enabled(self) -> bool:
        """Check if autosave is enabled."""
        return self._autosave_enabled
    
    @autosave_enabled.setter
    def autosave_enabled(self, value: bool) -> None:
        """Enable or disable autosave."""
        self._autosave_enabled = value
        if value and self._autosave_thread is None:
            self.start_autosave()
        elif not value:
            self.stop_autosave()
    
    @property
    def autosave_interval(self) -> int:
        """Get the autosave interval in seconds."""
        return self._autosave_interval
    
    @autosave_interval.setter
    def autosave_interval(self, value: int) -> None:
        """Set the autosave interval in seconds."""
        self._autosave_interval = max(5, min(300, value))
    
    @property
    def save_on_close(self) -> bool:
        """Check if save on close is enabled."""
        return self._save_on_close
    
    @save_on_close.setter
    def save_on_close(self, value: bool) -> None:
        """Enable or disable save on close."""
        self._save_on_close = value
    
    def start_autosave(self) -> None:
        """Start the autosave background thread.
        
        The thread will periodically check the dirty flag and save if needed.
        Safe to call multiple times - will not start duplicate threads.
        """
        if not self._autosave_enabled:
            logger.debug("Autosave disabled, not starting thread")
            return
        
        with self._autosave_lock:
            if self._autosave_thread is not None and self._autosave_thread.is_alive():
                logger.debug("Autosave thread already running")
                return
            
            self._autosave_stop_event.clear()
            self._autosave_thread = threading.Thread(
                target=self._autosave_loop,
                name="ManifestAutosave",
                daemon=True,  # Thread dies when main thread exits
            )
            self._autosave_thread.start()
            logger.info(
                "Started autosave thread (interval=%ds)", self._autosave_interval
            )
    
    def stop_autosave(self) -> None:
        """Stop the autosave background thread.
        
        Signals the thread to stop and waits for it to finish.
        Safe to call multiple times.
        """
        with self._autosave_lock:
            if self._autosave_thread is None:
                return
            
            self._autosave_stop_event.set()
            
            # Wait for thread to finish (with timeout)
            if self._autosave_thread.is_alive():
                self._autosave_thread.join(timeout=2.0)
            
            self._autosave_thread = None
            logger.info("Stopped autosave thread")
    
    def _autosave_loop(self) -> None:
        """Background thread loop for autosave.
        
        Runs until stop event is set. Checks dirty flag every interval
        and saves if manifest has unsaved changes.
        """
        logger.debug("Autosave loop started")
        
        while not self._autosave_stop_event.is_set():
            # Wait for interval or stop event
            if self._autosave_stop_event.wait(timeout=self._autosave_interval):
                # Stop event was set
                break
            
            # Check if we have unsaved changes
            if self._dirty and self._manifest_path is not None:
                logger.debug("Autosave triggered (dirty=%s)", self._dirty)
                try:
                    self.save()
                except Exception as e:
                    logger.error("Autosave failed: %s", e)
        
        logger.debug("Autosave loop ended")
    
    @property
    def is_loaded(self) -> bool:
        """Check if a manifest is currently loaded."""
        return self._manifest_path is not None
    
    @property
    def manifest_path(self) -> Optional[Path]:
        """Get the current manifest file path."""
        return self._manifest_path
    
    @property
    def project_name(self) -> str:
        """Get the project name from Information metadata."""
        meta = self.get_info_metadata()
        name = meta.get("project_name", "")
        if not name:
            # Fallback to manifest filename stem
            if self._manifest_path is not None:
                name = self._manifest_path.stem.replace(MANIFEST_EXT.replace(".", ""), "").rstrip(".")
        return name
    
    @property
    def current_step(self) -> int:
        """Get the current step index."""
        return self._current_step
    
    @current_step.setter
    def current_step(self, value: int) -> None:
        """Set the current step index."""
        if 0 <= value < len(STEP_NAMES):
            self._current_step = value
            self._manifest_data["current_step"] = value
            self._mark_dirty()
    
    @property
    def dirty(self) -> bool:
        """Check if there are unsaved changes."""
        return self._dirty
    
    def _create_empty_manifest(self) -> Dict[str, Any]:
        """Create an empty manifest structure with all v3.1 fields.
        
        TASK 21.2: Extended to include ALL fields needed by GUI and processing.
        TASK 35.1: Added filedir for input/output decoupling.
        Uses defaults from INI file via ini_manager.
        Defaults for system_instructions and summary are seeded at creation
        so that Steps 4/5 can operate without the Information tab being
        visited first.
        """
        now = datetime.utcnow().isoformat() + "Z"
        defaults = self._get_manifest_defaults()
        
        # Seed Information step metadata with default values.
        info_metadata = self._get_info_defaults()
        step_states: Dict[str, Any] = {}
        for name in STEP_NAMES:
            ss = StepState(name=name).to_dict()
            if name == "Information":
                ss["data"] = {"metadata": info_metadata}
            step_states[name] = ss
        
        return {
            # === Core Metadata ===
            "version": MANIFEST_VERSION,
            "created_at": now,
            "updated_at": now,
            
            # === Project Identity ===
            "current_step": 0,
            
            # === v3.2 Source Path Management (TASK 38) ===
            # source_root: Display-only folder name of the nearest common
            # ancestor.  NOT a resolvable path.  File resolution uses the
            # project's Original/ directory instead.
            "source_root": "",
            # mode: internal resolves via staged Original/, external resolves
            # via absolute source_root.
            "mode": "internal",
            
            # === v3.1 File Directory (TASK 35.1) ===
            # Maps line index ranges to source files for input/output decoupling
            # TASK 38: rel_path is now relative to source_root, source_hint removed
            "filedir": [],
            
            # === v2.1 Processing Data (TASK 38: lines no longer need source_file) ===
            "lines": [],
            "operations": [],
            "mappings": {},
            "summary": "",
            "metadata": {},
            
            # === v3.0 Project Settings ===
            "characters": [],
            "code_patterns": [],
            "step_state": step_states,
            "glossary": GlossaryConfig().to_dict(),
            
            # === v3.0 Preprocessing Options ===
            "Deduplication": defaults.get("deduplication", True),
            "DeduplicationThreshold": defaults.get("deduplication_threshold", 1),
            "EllipsisCompression": defaults.get("ellipsis_compression", True),
            "SymbolConversion": defaults.get("symbol_conversion", True),
            "SpeakerNameReplacement": defaults.get("speaker_name_replacement", False),
            "CodeSpacingRules": defaults.get("code_spacing_rules", True),
            "ProtectCodePatterns": [],
            "CustomPlaceholders": [],
            "AnchorRemoval": [],
            
            # === v3.0 Estimation Data ===
            "InputLines": 0,
            "InputTokens": 0,
            "OutputTokens": 0,
            
            # === v3.0 Validation Rules ===
            "ValidationRules": {
                "PlaceholderPreservation": defaults.get("validation_placeholder_preservation", True),
                "AnchorPreservation": defaults.get("validation_anchor_preservation", True),
                "SourceLanguageDetection": defaults.get("validation_source_language_detection", defaults.get("validation_japanese_character_detection", True)),
                "SpeakerFormat": defaults.get("validation_speaker_format", True),
                "QuoteBalance": defaults.get("validation_quote_balance", True),
                "EmptyTranslation": defaults.get("validation_empty_translation", True),
            },
            
            # === v3.1 Character/Word Validation (TASK 36.1) ===
            # Whitelist: allowed characters (empty = all allowed)
            # Blacklist: forbidden characters (checked after whitelist)
            # WordBlacklist: forbidden words/phrases (case-insensitive, whole word match)
            # AutofixMap: character replacements for auto-correction
            "CharacterWhitelist": defaults.get("character_whitelist", ""),
            "CharacterBlacklist": defaults.get("character_blacklist", ""),
            "WordBlacklist": self._parse_list_default(
                defaults.get("word_blacklist", "")
            ),
            "AutofixMap": self._parse_dict_default(
                defaults.get("autofix_map", "")
            ),
            
            # === v3.0 QA Options ===
            "QAOptions": {
                "RerunPolicy": defaults.get("qa_rerun_policy", "FailedOnly"),
                "MaxSourceLanguageChars": defaults.get("qa_max_source_language_chars", defaults.get("qa_max_japanese_chars", 4)),
                "MaxLineLength": defaults.get("qa_max_line_length", 0),
                "EncodingSafetyEnabled": defaults.get(
                    "qa_encoding_safety_enabled",
                    False,
                ),
                "EncodingCheckEncoding": defaults.get(
                    "qa_encoding_check_encoding",
                    "shift_jis",
                ),
            },
            
            # === v3.0 Request Options (passed to API client) ===
            "RequestOptions": {
                "Model": "",  # Uses global API model by default
                "Temperature": defaults.get("request_temperature", 0.2),
                "LinesPerChunk": defaults.get("request_lines_per_chunk", 30),
                "RetryStrategy": defaults.get("request_retry_strategy", "Batch"),
                "MaxRetries": defaults.get("request_max_retries", 3),
                "EnableRequestCaching": defaults.get("request_enable_caching", True),
                "LineByLineMode": defaults.get("request_line_by_line_mode", False),
                "Thinking": defaults.get("request_thinking", False),
                "ThinkingBudget": defaults.get("request_thinking_budget", 1000),
            },
            
            # === v3.0 Post Processing Options ===
            "PostProcessing": {
                "PlaceholderRecovery": defaults.get("post_placeholder_recovery", True),
                "BracketBalanceRecovery": defaults.get("post_bracket_balance_recovery", True),
                "QuoteBalanceRecovery": defaults.get("post_quote_balance_recovery", True),
                "RestoreCodeCharacters": defaults.get("post_restore_code_characters", True),
                "RestoreLinebreaks": defaults.get("post_restore_linebreaks", True),
                "EnableSymbolConversion": defaults.get("post_enable_symbol_conversion", True),
                "FullwidthToHalfwidth": defaults.get("post_fullwidth_to_halfwidth", True),
                "FailureHandling": defaults.get("post_failure_handling", "flag"),
            },
            
            # === v3.0 Wordwrap Settings ===
            "WordwrapSettings": {
                "Mode": defaults.get("wordwrap_mode", "Custom"),
                "Width": defaults.get("wordwrap_width", 48),
                "BreakChar": defaults.get("wordwrap_break_char", ""),
                "MaxLines": defaults.get("wordwrap_max_lines", 4),
                "PrettyWrap": defaults.get("wordwrap_pretty_wrap", True),
                "PreventOrphans": defaults.get("wordwrap_prevent_orphans", True),
                "PreferPunctuationBreaks": defaults.get("wordwrap_prefer_punctuation_breaks", True),
                "SpeakerHandling": defaults.get("wordwrap_speaker_handling", "Sameline"),
                "IgnorePatterns": self._parse_list_default(
                    defaults.get("wordwrap_ignore_patterns", "Angle,Square,Curly,En")
                ),
                "Typography": defaults.get("wordwrap_typography", "Western"),
                "TagConfigs": [],
                "FormatConfigs": [],
            },
            
            # === v3.0 Output Format ===
            "OutputFormat": {
                "Destination": defaults.get("output_destination", "Same as Source"),
                "PreserveFolderStructure": defaults.get("output_preserve_folder_structure", True),
                "Format": "",  # Auto-detect from input
                "PairMode": defaults.get("output_pair_mode", "custom"),
                "Encoding": defaults.get("output_encoding", "Same as Input"),
                "FileNaming": defaults.get("output_file_naming", "subfolder"),
                "TextOption": defaults.get("output_text_option", "translated"),
                "OverwriteExistingFiles": defaults.get("output_overwrite_existing_files", True),
                "Backup": defaults.get("output_backup", "timestamp"),
                "BackupExtension": defaults.get("output_backup_extension", ".bk"),
                "ExportManifestFile": defaults.get("output_export_manifest_file", False),
                "ExportProcessingLogs": defaults.get("output_export_processing_logs", False),
                "ExportGlossaryEntries": defaults.get("output_export_glossary_entries", False),
            },

            # === Archive Metadata ===
            "ArchiveSettings": {},

            # === API Log ===
            "log": "",
        }
    
    def _get_manifest_defaults(self) -> Dict[str, Any]:
        """Get manifest defaults from INI file.
        
        Returns:
            Dictionary of default values for manifest fields.
        """
        try:
            from . import ini_manager
            return ini_manager.get_all_manifest_defaults()
        except ImportError:
            logger.warning("ini_manager not available, using builtin defaults")
            return self._get_builtin_defaults()
    
    def _get_builtin_defaults(self) -> Dict[str, Any]:
        """Get hardcoded defaults as fallback.
        
        Used when ini_manager is not available.
        """
        return {
            "project_name": "Project1",
            "title": "Title1",
            "genre": "fictional, nonfictional",
            "source_language": "Japanese",
            "target_language": "English",
            "summary": "[Summary of the Content]",
            "style_preset": "neutral",
            "tone_preset": "natural",
            "deduplication": True,
            "deduplication_threshold": 1,
            "ellipsis_compression": True,
            "symbol_conversion": True,
            "speaker_name_replacement": False,
            "code_spacing_rules": True,
            "validation_placeholder_preservation": True,
            "validation_anchor_preservation": True,
            "validation_japanese_character_detection": True,
            "validation_speaker_format": True,
            "validation_quote_balance": True,
            "validation_empty_translation": True,
            "qa_rerun_policy": "FailedOnly",
            "qa_max_japanese_chars": 4,
            "qa_max_line_length": 0,
            "request_temperature": 0.2,
            "request_lines_per_chunk": 30,
            "request_retry_strategy": "Batch",
            "request_max_retries": 3,
            "request_enable_caching": True,
            "request_line_by_line_mode": False,
            "request_thinking": False,
            "request_thinking_budget": 1000,
            "post_placeholder_recovery": True,
            "post_bracket_balance_recovery": True,
            "post_quote_balance_recovery": True,
            "post_restore_code_characters": True,
            "post_restore_linebreaks": True,
            "post_enable_symbol_conversion": True,
            "post_fullwidth_to_halfwidth": True,
            "post_failure_handling": "flag",
            "wordwrap_mode": "Custom",
            "wordwrap_width": 48,
            "wordwrap_break_char": "",
            "wordwrap_max_lines": 4,
            "wordwrap_prevent_orphans": True,
            "wordwrap_prefer_punctuation_breaks": True,
            "wordwrap_speaker_handling": "Sameline",
            "wordwrap_ignore_patterns": "Angle,Square,Curly,En",
            "wordwrap_typography": "Western",
            "output_destination": "Same as Source",
            "output_preserve_folder_structure": True,
            "output_pair_mode": "custom",
            "output_file_naming": "subfolder",
            "output_text_option": "translated",
            "output_overwrite_existing_files": True,
            "output_backup": "timestamp",
            "output_backup_extension": ".bk",
            "output_export_manifest_file": False,
            "output_export_processing_logs": False,
            "output_export_glossary_entries": False,
        }
    
    # _create_project_info_defaults removed — project_info is no longer a
    # top-level manifest key.  Metadata lives in step_state.Information.data.metadata.

    def _get_info_defaults(self) -> Dict[str, Any]:
        """Return default Information metadata seeded at manifest creation.

        Ensures that system_instructions, si_preset, summary, and other
        defaults are present in the manifest from the start so that
        Steps 4 (Costs) and 5 (Translation) can operate without
        requiring the Information tab to be visited first.
        """
        try:
            from . import ini_manager
            si_text = ini_manager.get_default_text("SystemInstruction")
            summary_text = ini_manager.get_default_text("Summary")
        except ImportError:
            si_text = ""
            summary_text = ""
        return {
            "source_language": "Japanese",
            "target_language": "English",
            "system_instructions": si_text,
            "si_preset": "Default",
            "io_examples": "disabled",
            "summary": summary_text,
            "style_preset": "Natural",
            "tone_preset": "Neutral",
            "system_instructions_enabled": True,
            "glossary_enabled": True,
            "code_database_enabled": True,
            "genre_enabled": False,
            "summary_enabled": False,
            "style_enabled": False,
            "tone_enabled": False,
        }
    
    def _parse_list_default(self, value: Any) -> list:
        """Parse a comma-separated string into a list.
        
        Args:
            value: String like "A,B,C" or already a list.
            
        Returns:
            List of strings.
        """
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return []
    
    def _parse_dict_default(self, value: Any) -> Dict[str, str]:
        """Parse a string into a dictionary for autofix mappings.
        
        TASK 36.1: Supports two formats:
        - Comma-separated pairs: "a=b,c=d" -> {"a": "b", "c": "d"}
        - JSON dict: '{"a": "b"}' -> {"a": "b"}
        
        Args:
            value: String like "a=b,c=d" or JSON dict, or already a dict.
            
        Returns:
            Dictionary mapping offending chars to replacements.
        """
        if isinstance(value, dict):
            return value
        if not isinstance(value, str) or not value:
            return {}
        
        # Try JSON format first
        value = value.strip()
        if value.startswith("{"):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                pass
        
        # Parse comma-separated key=value pairs
        result: Dict[str, str] = {}
        for pair in value.split(","):
            if "=" in pair:
                key, val = pair.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key:
                    result[key] = val
        return result
    
    def _mark_dirty(self) -> None:
        """Mark the manifest as having unsaved changes."""
        self._dirty = True
        self._manifest_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._notify_listeners()
    
    def _notify_listeners(self) -> None:
        """Notify all change listeners."""
        for listener in self._change_listeners:
            try:
                listener()
            except Exception as e:
                logger.warning("Change listener error: %s", e)
    
    def add_change_listener(self, listener: Callable[[], None]) -> None:
        """Add a listener for state changes."""
        self._change_listeners.append(listener)
    
    def remove_change_listener(self, listener: Callable[[], None]) -> None:
        """Remove a change listener."""
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)
    
    # ========================== Source Path Helpers (TASK 38) ========================== #
    
    @property
    def source_root(self) -> str:
        """Folder name (display-only) of the common source ancestor."""
        return self._manifest_data.get("source_root", "")
    
    @source_root.setter
    def source_root(self, value: str) -> None:
        """Set the source root folder name."""
        self._manifest_data["source_root"] = value
        self._mark_dirty()

    @property
    def source_mode(self) -> str:
        """Return how ``source_root`` should be interpreted."""
        raw_mode = str(self._manifest_data.get("mode", "internal")).strip().lower()
        if raw_mode == "external":
            return "external"
        return "internal"

    @source_mode.setter
    def source_mode(self, value: str) -> None:
        """Set how ``source_root`` should be interpreted."""
        clean_mode = str(value).strip().lower()
        self._manifest_data["mode"] = "external" if clean_mode == "external" else "internal"
        self._mark_dirty()
    
    def resolve_file_path(self, rel_path: str) -> Path:
        """Resolve a relative path to an absolute path.

        Internal projects resolve via staged ``Original/``. External projects
        resolve via the absolute ``source_root``.

        Args:
            rel_path: Path relative to the original files directory
                (e.g. ``"battle_on.json"`` or ``"event/arena/arena_01.json"``).

        Returns:
            Absolute source path for the requested relative path.
        """
        archive_name = self.get_archive_name_for_rel_path(rel_path)
        if archive_name:
            return self.get_package_original_dir() / rel_path
        if self.source_mode == "external":
            source_root = str(self.source_root).strip()
            if source_root:
                return Path(source_root) / rel_path
        return self.get_original_dir() / rel_path
    
    def make_relative_path(self, abs_path: Path) -> str:
        """Convert an absolute path to a path relative to Original/ dir.
        
        Args:
            abs_path: Absolute file path.
            
        Returns:
            Relative path string, or filename if path is outside Original/.
        """
        orig_dir = self.get_original_dir()
        try:
            return str(abs_path.relative_to(orig_dir))
        except ValueError:
            return abs_path.name
    
    def get_file_for_line_idx(self, idx: int) -> Optional[Dict[str, Any]]:
        """Get the filedir entry for a given line index.
        
        Args:
            idx: Global line index (0-based).
            
        Returns:
            Filedir entry dict or None if not found.
        """
        for entry in self._manifest_data.get("filedir", []):
            first = entry.get("first_idx", 0)
            last = entry.get("last_idx", 0)
            if first <= idx <= last:
                return entry
        return None
    
    def get_source_file_for_line(self, idx: int) -> Optional[Path]:
        """Get the absolute source file path for a given line index.
        
        Args:
            idx: Global line index (0-based).
            
        Returns:
            Absolute Path to source file, or None if not found.
        """
        entry = self.get_file_for_line_idx(idx)
        if entry:
            return self.resolve_file_path(entry.get("rel_path", ""))
        return None
    
    @staticmethod
    def _compute_full_root(source_files: List[Any]) -> str:
        """Compute the full common root path from a list of source files.

        Used internally during project creation for building relative paths.
        Not stored in the manifest — only the folder name is persisted.

        Args:
            source_files: List of source file paths (str or Path).

        Returns:
            Full common ancestor directory as string, or empty string.
        """
        if not source_files:
            return ""

        paths = [Path(f) if isinstance(f, str) else f for f in source_files]

        if len(paths) == 1:
            return str(paths[0].parent)

        import os
        try:
            common = os.path.commonpath([str(p) for p in paths])
            return common
        except ValueError:
            return ""

    @staticmethod
    def compute_source_root(source_files: List[Any]) -> str:
        """Return the folder name (last path component) of the common root.

        This is the value stored in ``source_root`` — a short, portable,
        privacy-safe identifier.  It is **not** a resolvable path.

        Args:
            source_files: List of source file paths (str or Path).

        Returns:
            Folder name string, or empty string if no files.
        """
        full = ManifestManager._compute_full_root(source_files)
        if not full:
            return ""
        return Path(full).name
    
    # ========================== Project Operations ========================== #
    
    def create_new(
        self,
        project_name: str,
        source_files: List[Path],
        *,
        save_immediately: bool = True,
    ) -> Path:
        """Create a new project manifest.
        
        Args:
            project_name: Name for the project (used in filename)
            source_files: List of source file paths
            save_immediately: Whether to write the initial manifest to disk
                right away.
            
        Returns:
            Path to the created manifest file
            
        TASK 29.1: Starts autosave thread after creation.
        TASK 38: Uses optimized format with source_root and compact lines.
        """
        # Sanitize project name for filename
        safe_name = "".join(c for c in project_name if c.isalnum() or c in " -_").strip()
        if not safe_name:
            safe_name = "Untitled"
        
        # Create manifest path
        self._manifest_path = MANIFEST_DIR / f"{safe_name}{MANIFEST_EXT}"
        
        # Handle duplicate names
        counter = 1
        while self._manifest_path.exists():
            self._manifest_path = MANIFEST_DIR / f"{safe_name}_{counter}{MANIFEST_EXT}"
            counter += 1
        
        # Initialize manifest data
        self._manifest_data = self._create_empty_manifest()
        
        # Store project_name in Information metadata (single source of truth)
        self.set_info_metadata_field("project_name", project_name)
        
        # Compute full common root (for building rel_paths) and folder name
        full_root = self._compute_full_root(source_files)
        folder_name = Path(full_root).name if full_root else ""
        self._manifest_data["source_root"] = folder_name
        
        # Initialize lines and filedir using the *full* root for rel_paths
        self._initialize_lines_from_files(source_files, full_root)
        
        # Initialize API log for this project
        log_filename = self._manifest_path.stem + ".api_log.jsonl"
        self._manifest_data["log"] = log_filename
        log_path = self._manifest_path.parent / log_filename
        try:
            from .api_log import reset_api_log_store
            reset_api_log_store(log_path)
        except Exception:
            logger.debug("API log store init skipped")

        self._dirty = True
        self._current_step = 0
        if save_immediately:
            self.save()
        
        # Start autosave thread
        self.start_autosave()
        
        logger.info("Created new manifest: %s", self._manifest_path)
        return self._manifest_path
    
    def _initialize_lines_from_files(
        self,
        source_files: List[Path],
        full_root: str = "",
    ) -> None:
        """Initialize lines array and filedir from source files.

        Args:
            source_files: Absolute paths to source files.
            full_root: Full common ancestor path used *only* to compute
                relative paths for filedir.  Not stored in the manifest.

        TASK 38: Lines no longer store source_file - use filedir for lookup.
        """
        lines: List[Dict[str, Any]] = []
        filedir: List[Dict[str, Any]] = []
        idx = 0
        
        for file_path in source_files:
            try:
                first_idx = idx
                content = _read_source_text_for_manifest(file_path)
                file_lines = content.split("\n")
                
                for line_number, line_text in enumerate(file_lines, start=1):
                    # TASK 38: Compact line format - only idx and orig
                    lines.append({
                        "idx": idx,
                        "ln": line_number,
                        "orig": line_text,
                    })
                    idx += 1
                
                # Build filedir entry — rel_path relative to full_root
                if full_root:
                    try:
                        rel_path = str(file_path.relative_to(full_root))
                    except ValueError:
                        rel_path = file_path.name
                else:
                    rel_path = file_path.name
                
                # Detect format from extension
                ext = file_path.suffix.lower()
                format_map = {
                    ".txt": "txt", ".csv": "csv", ".tsv": "tsv",
                    ".json": "json", ".xlsx": "xlsx", ".html": "html",
                }
                file_format = format_map.get(ext, "txt")
                
                filedir.append({
                    "first_idx": first_idx,
                    "last_idx": idx - 1,
                    "format": file_format,
                    "rel_path": rel_path,
                })
                
            except Exception as e:
                logger.warning("Failed to read source file %s: %s", file_path, e)
        
        self._manifest_data["lines"] = lines
        self._manifest_data["filedir"] = filedir
    
    def load(self, manifest_path: Path) -> bool:
        """Load an existing manifest.
        
        Args:
            manifest_path: Path to the manifest file
            
        Returns:
            True if loaded successfully
            
        TASK 29.1: Starts autosave thread after loading.
        """
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Migrate older versions if needed
            data = self._migrate_manifest(data)
            data["lines"] = canonicalize_lines(
                data.get("lines", []),
                data.get("filedir", []),
            )
            
            self._manifest_path = manifest_path
            self._manifest_data = data
            
            self._current_step = data.get("current_step", 0)
            self._dirty = False

            # Load API log for this project
            log_filename = data.get("log", "")
            if log_filename:
                log_path = manifest_path.parent / log_filename
            else:
                log_filename = manifest_path.stem + ".api_log.jsonl"
                log_path = manifest_path.parent / log_filename
                self._manifest_data["log"] = log_filename
            try:
                from .api_log import reset_api_log_store
                store = reset_api_log_store(log_path)
                store.load()
            except Exception:
                logger.debug("API log store load skipped")
            
            # Start autosave thread
            self.start_autosave()
            
            logger.info("Loaded manifest: %s (v%s)", manifest_path, data.get("version", "?"))
            return True
            
        except Exception as e:
            logger.error("Failed to load manifest %s: %s", manifest_path, e)
            return False
    
    def _migrate_manifest(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate older manifest versions to v3.2.
        
        Handles migration from v1.x, v2.x, v3.0, and v3.1 manifests, preserving all 
        line data, operations, and settings.
        
        TASK 35.1: Adds filedir migration.
        TASK 38: v3.2 optimization - remove redundant fields, add source_root.
        """
        version = data.get("version", "1.0")
        
        # Handle v1.x, v2.x, v3.0 migrations
        if version.startswith("1.") or version.startswith("2.") or version == "3.0":
            logger.info("Migrating manifest from v%s to v%s", version, MANIFEST_VERSION)
            
            # Ensure all v3.0 fields exist
            if "step_state" not in data:
                data["step_state"] = {name: StepState(name=name).to_dict() for name in STEP_NAMES}
            
            # Migrate project_info from various old fields
            if "project_info" not in data or not data["project_info"]:
                metadata = data.get("metadata", {})
                old_project_info = data.get("project_info", {})
                
                # Build merged project info
                merged_info: Dict[str, Any] = {}
                
                # Get project name from various sources
                project_name = (
                    old_project_info.get("project_name") or
                    data.get("project_name") or
                    metadata.get("project_name") or
                    ""
                )
                if not project_name:
                    # Derive from source_file or origin_file
                    source = data.get("source_file") or data.get("origin_file") or ""
                    if source:
                        merged_info["project_name"] = Path(source).stem
                else:
                    merged_info["project_name"] = project_name
                
                # Migrate languages
                if "language_source" in data:
                    merged_info["source_language"] = data["language_source"]
                if "language_target" in data:
                    merged_info["target_language"] = data["language_target"]
                
                # Merge any existing old metadata
                for key, value in old_project_info.items():
                    if key not in merged_info and value:
                        merged_info[key] = value
                for key, value in metadata.items():
                    if key not in merged_info and value and key not in ("auto_created", "created_utc"):
                        merged_info[key] = value
                
                data["project_info"] = merged_info
            
            # Also set top-level project_name for easy access
            if not data.get("project_name"):
                data["project_name"] = data.get("project_info", {}).get("project_name", "")
            
            if "glossary" not in data:
                data["glossary"] = GlossaryConfig().to_dict()
            
            if "current_step" not in data:
                data["current_step"] = 0

            if "mode" not in data:
                data["mode"] = "internal"

            if "ArchiveSettings" not in data:
                data["ArchiveSettings"] = {}
            
            # Migrate source files - handle both singular and plural
            if "source_files" not in data:
                # v2.0 uses 'source_file', older uses 'origin_file'
                source_file = data.get("source_file") or data.get("origin_file")
                if source_file:
                    data["source_files"] = [source_file]
                else:
                    data["source_files"] = []
            
            if "characters" not in data:
                data["characters"] = []
            
            if "code_patterns" not in data:
                data["code_patterns"] = []
            
            # Ensure lines exist - v2.0 should already have them
            if "lines" not in data:
                data["lines"] = []
            
            # Ensure operations exist
            if "operations" not in data:
                data["operations"] = []
            
            # Ensure mappings exist
            if "mappings" not in data:
                data["mappings"] = {}
            
            # Copy essential timestamps
            if "created_at" not in data:
                if "metadata" in data and "created_utc" in data["metadata"]:
                    data["created_at"] = data["metadata"]["created_utc"]
                else:
                    data["created_at"] = datetime.utcnow().isoformat() + "Z"
            
            if "updated_at" not in data:
                data["updated_at"] = datetime.utcnow().isoformat() + "Z"
            
            # TASK 35.1: Migrate filedir
            # Build filedir from lines if not present (backward compatibility)
            if "filedir" not in data:
                data["filedir"] = self._build_filedir_from_legacy(data)
            
            # Also run v3.1→v3.2 optimization
            version = "3.1"
        
        # TASK 38: v3.1 → v3.2 optimization
        # Remove redundant source_file from lines, store source_root as folder name
        if version == "3.1":
            logger.info("Optimizing manifest from v3.1 to v3.2")
            
            # Compute full common root (for building rel_paths) and folder name
            source_files = data.get("source_files", [])
            full_root = self._compute_full_root(source_files) if source_files else ""
            folder_name = Path(full_root).name if full_root else ""
            data["source_root"] = folder_name
            data["mode"] = str(data.get("mode", "internal") or "internal").lower()
            data.setdefault("ArchiveSettings", {})
            
            # Update filedir entries — remove source_hint, make rel_path relative
            filedir = data.get("filedir", [])
            for entry in filedir:
                if "source_hint" in entry:
                    del entry["source_hint"]
                rel_path = entry.get("rel_path", "")
                if full_root and rel_path:
                    try:
                        rel_path_obj = Path(rel_path)
                        if rel_path_obj.is_absolute():
                            rel_path = str(rel_path_obj.relative_to(full_root))
                            entry["rel_path"] = rel_path
                    except ValueError:
                        pass
            
            # Remove source_file from all line entries (compact format)
            lines = data.get("lines", [])
            for line in lines:
                if "source_file" in line:
                    del line["source_file"]
            
            # Remove source_files array (no longer needed)
            data.pop("source_files", None)
            
            data["version"] = MANIFEST_VERSION

        if "mode" not in data:
            data["mode"] = "internal"
        elif str(data.get("mode", "internal")).strip().lower() != "external":
            data["mode"] = "internal"
        
        # TASK 71: Strip redundant step_state arrays.
        # all_lines, processed_lines, postprocessed_lines duplicate lines[].orig /
        # prepro / postpro.  files duplicates filedir[].  Remove them on load so
        # the next save produces a compact manifest.
        _REDUNDANT_STEP_KEYS: Dict[str, List[str]] = {
            "Input": ["all_lines", "files"],
            "Preprocessing": ["processed_lines"],
            "Postprocessing": ["postprocessed_lines"],
            "Output": ["lines"],
        }
        step_state = data.get("step_state", {})
        for step_name, keys in _REDUNDANT_STEP_KEYS.items():
            step_entry = step_state.get(step_name, {})
            step_data = step_entry.get("data", {})
            for key in keys:
                if key in step_data:
                    logger.debug("Stripping redundant key '%s' from %s step_data",
                                 key, step_name)
                    del step_data[key]

        editor_state = data.get("EditorState")
        if isinstance(editor_state, dict):
            files = editor_state.get("files")
            if isinstance(files, dict):
                redundant_editor_keys = {
                    "diff_to_patch",
                    "edited_text",
                    "diff_to_original",
                    "line_history",
                    "locator_metadata",
                    "latest_saved_row_state",
                }
                for state in files.values():
                    if not isinstance(state, dict):
                        continue
                    for key in redundant_editor_keys:
                        if key in state:
                            logger.debug(
                                "Stripping redundant EditorState key '%s'",
                                key,
                            )
                            del state[key]
        
        return data
    
    def _build_filedir_from_legacy(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build filedir entries from legacy manifest data.
        
        TASK 35.1: For backward compatibility when loading older manifests
        that don't have filedir.
        TASK 38: v3.2 format - no source_hint, rel_path relative to source_root.
        
        Args:
            data: Legacy manifest data.
            
        Returns:
            List of filedir entry dictionaries.
        """
        lines = data.get("lines", [])
        source_files = data.get("source_files", [])
        source_root = data.get("source_root", "")
        file_format = data.get("format", "txt")
        
        if not lines:
            return []
        
        if not source_files:
            # No source file info - create single entry for all lines
            source_file = data.get("source_file") or data.get("origin_file") or "unknown.txt"
            rel_path = Path(source_file).name
            if source_root:
                try:
                    rel_path = str(Path(source_file).relative_to(source_root))
                except ValueError:
                    pass
            return [{
                "first_idx": 0,
                "last_idx": len(lines) - 1,
                "format": file_format,
                "rel_path": rel_path,
            }]
        
        # Group lines by source_file
        files_with_lines: Dict[str, List[int]] = {}
        for line in lines:
            source = line.get("source_file", source_files[0])
            idx = line.get("idx", 0)
            if source not in files_with_lines:
                files_with_lines[source] = []
            files_with_lines[source].append(idx)
        
        # Build filedir entries
        filedir: List[Dict[str, Any]] = []
        for source_file in source_files:
            indices = files_with_lines.get(source_file, [])
            if not indices:
                continue
            
            # Make rel_path relative to source_root
            rel_path = Path(source_file).name
            if source_root:
                try:
                    rel_path = str(Path(source_file).relative_to(source_root))
                except ValueError:
                    pass
            
            filedir.append({
                "first_idx": min(indices),
                "last_idx": max(indices),
                "format": file_format,
                "rel_path": rel_path,
            })
        
        return filedir
    
    def save(self) -> bool:
        """Save the manifest to disk atomically.

        Writes to a temporary file first, then replaces the real file via
        ``os.replace`` so readers never see a partially-written manifest.
        Uses ``deepcopy`` to prevent "dictionary changed size during
        iteration" when autosave runs while the main thread modifies data
        and a custom JSON encoder as safety net for objects with
        ``to_dict()`` (e.g. ``TableRow``, ``FileDirEntry``).

        Thread-safe: uses ``_autosave_lock`` to prevent the autosave
        thread and main thread from writing simultaneously (WinError 32).

        Returns:
            True if saved successfully.
        """
        if self._manifest_path is None:
            logger.warning("Cannot save: no manifest path set")
            return False

        with self._autosave_lock:
            try:
                self._manifest_path.parent.mkdir(parents=True, exist_ok=True)

                # Snapshot to prevent concurrent modification
                data_snapshot = deepcopy(self._manifest_data)
                data_snapshot["lines"] = canonicalize_lines(
                    data_snapshot.get("lines", []),
                    data_snapshot.get("filedir", []),
                )

                # Atomic write: temp file → rename
                tmp_path = self._manifest_path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(format_manifest_json(data_snapshot))
                    f.flush()
                    os.fsync(f.fileno())

                # Retry os.replace up to 3 times for transient Windows locks
                for attempt in range(3):
                    try:
                        os.replace(str(tmp_path), str(self._manifest_path))
                        break
                    except OSError:
                        if attempt == 2:
                            raise
                        time.sleep(0.1 * (attempt + 1))

                self._dirty = False

                # Also persist the API log
                try:
                    from .api_log import get_api_log_store
                    store = get_api_log_store()
                    if store.dirty:
                        store.save()
                except Exception:
                    logger.debug("API log save skipped")

                logger.debug("Saved manifest: %s", self._manifest_path)
                return True

            except Exception as e:
                logger.error("Failed to save manifest: %s", e)
                # Clean up temp file on failure
                try:
                    tmp_path = self._manifest_path.with_suffix(".tmp")
                    if tmp_path.exists():
                        tmp_path.unlink()
                except OSError:
                    pass
                return False
    
    def close(self) -> None:
        """Close the current manifest.
        
        TASK 29.1: Respects save_on_close setting and stops autosave thread.
        """
        # Stop autosave thread first
        self.stop_autosave()
        
        # Save if dirty and save_on_close is enabled
        if self._dirty and self._save_on_close:
            self.save()
        
        # Clear API log store
        try:
            from .api_log import get_api_log_store
            store = get_api_log_store()
            store.save()
            store.clear()
        except Exception:
            logger.debug("API log store close skipped")

        self._manifest_path = None
        self._manifest_data = self._create_empty_manifest()
        self._dirty = False
        self._current_step = 0
    
    # ========================== Information Metadata Access ======================== #

    def get_info_metadata(self) -> Dict[str, Any]:
        """Get the Information step metadata dict (single source of truth).

        Returns a *reference* to the dict inside step_state so callers can
        mutate it directly (followed by ``_mark_dirty()``).  If the path
        does not exist yet it is created with safe defaults.
        """
        ss = self._manifest_data.setdefault("step_state", {})
        info = ss.setdefault(
            "Information",
            {"name": "Information", "status": "not-started"},
        )
        data = info.setdefault("data", {})
        meta = data.setdefault("metadata", {})
        return meta

    def set_info_metadata(self, metadata: Dict[str, Any]) -> None:
        """Replace the Information step metadata dict wholesale."""
        ss = self._manifest_data.setdefault("step_state", {})
        info = ss.setdefault(
            "Information",
            {"name": "Information", "status": "not-started"},
        )
        data = info.setdefault("data", {})
        data["metadata"] = metadata
        self._mark_dirty()

    def set_info_metadata_field(self, key: str, value: Any) -> None:
        """Set a single field inside Information metadata."""
        meta = self.get_info_metadata()
        meta[key] = value
        self._mark_dirty()

    def get_info_metadata_field(
        self, key: str, default: Any = ""
    ) -> Any:
        """Read a single field from Information metadata."""
        return self.get_info_metadata().get(key, default)

    # ========================== Step State Operations ========================== #
    
    def get_step_state(self, step_index: int) -> StepState:
        """Get state for a specific step.
        
        Args:
            step_index: Step index (0-9)
            
        Returns:
            StepState for the step
        """
        if step_index < 0 or step_index >= len(STEP_NAMES):
            raise ValueError(f"Invalid step index: {step_index}")
        
        step_name = STEP_NAMES[step_index]
        step_data = self._manifest_data.get("step_state", {}).get(step_name, {})
        
        if not step_data:
            return StepState(name=step_name)
        
        return StepState.from_dict(step_data)
    
    def set_step_state(self, step_index: int, state: StepState) -> None:
        """Set state for a specific step.
        
        Args:
            step_index: Step index (0-9)
            state: StepState to set
        """
        if step_index < 0 or step_index >= len(STEP_NAMES):
            raise ValueError(f"Invalid step index: {step_index}")
        
        step_name = STEP_NAMES[step_index]
        if "step_state" not in self._manifest_data:
            self._manifest_data["step_state"] = {}
        
        self._manifest_data["step_state"][step_name] = state.to_dict()
        self._mark_dirty()
    
    def get_step_data(self, step_index: int) -> Dict[str, Any]:
        """Get data dictionary for a step.
        
        Args:
            step_index: Step index (0-9)
            
        Returns:
            Step data dictionary
        """
        return self.get_step_state(step_index).data
    
    def set_step_data(self, step_index: int, data: Dict[str, Any]) -> None:
        """Set data dictionary for a step.
        
        Args:
            step_index: Step index (0-9)
            data: Data dictionary to set
        """
        state = self.get_step_state(step_index)
        state.data = data
        self.set_step_state(step_index, state)
    
    def update_step_data(self, step_index: int, key: str, value: Any) -> None:
        """Update a single key in step data.
        
        Args:
            step_index: Step index (0-9)
            key: Data key
            value: Value to set
        """
        state = self.get_step_state(step_index)
        state.data[key] = value
        self.set_step_state(step_index, state)
    
    def get_step_data_value(self, step_index: int, key: str, default: Any = None) -> Any:
        """Get a single value from step data.
        
        Args:
            step_index: Step index (0-9)
            key: Data key
            default: Default value if not found
            
        Returns:
            Value or default
        """
        return self.get_step_data(step_index).get(key, default)
    
    def set_step_status(self, step_index: int, status: str) -> None:
        """Set status for a step.
        
        Args:
            step_index: Step index (0-9)
            status: Status string ('not-started', 'in-progress', 'completed')
        """
        state = self.get_step_state(step_index)
        state.status = status
        if status == "completed":
            state.last_run = datetime.utcnow().isoformat() + "Z"
        self.set_step_state(step_index, state)
    
    def mark_step_done(self, step_index: int) -> None:
        """Mark a step as completed."""
        self.set_step_status(step_index, "completed")
    
    def mark_step_skipped(self, step_index: int) -> None:
        """Mark a step as skipped."""
        state = self.get_step_state(step_index)
        state.skipped = True
        state.status = "completed"
        self.set_step_state(step_index, state)

    def set_step_metrics(self, step_name: str, metrics: Dict[str, Any]) -> None:
        """Store utility metrics for a pipeline step.

        Merges *metrics* into the top-level manifest under the given
        *step_name* key (e.g. ``"Translation"``, ``"Postprocessing"``).

        Args:
            step_name: Canonical step identifier.
            metrics: Metric key-value pairs to store/update.
        """
        section = self._manifest_data.setdefault(step_name, {})
        section.update(metrics)
        self._mark_dirty()

    def get_step_metrics(self, step_name: str) -> Dict[str, Any]:
        """Retrieve stored utility metrics for a pipeline step.

        Args:
            step_name: Canonical step identifier.

        Returns:
            Copy of the metrics dict (empty dict if none stored).
        """
        from copy import deepcopy
        return deepcopy(self._manifest_data.get(step_name, {}))
    
    # ========================== Project Info Operations ========================== #
    
    def get_project_info(self) -> ProjectInfo:
        """Get project information from Information metadata."""
        data = self.get_info_metadata()
        return ProjectInfo.from_dict(data)
    
    def set_project_info(self, info: ProjectInfo) -> None:
        """Set project information into Information metadata."""
        meta = self.get_info_metadata()
        for key, value in info.to_dict().items():
            if value:  # Only write populated fields
                meta[key] = value
        self._mark_dirty()
    
    def update_project_info(self, **kwargs: Any) -> None:
        """Update specific project info fields in Information metadata."""
        meta = self.get_info_metadata()
        for key, value in kwargs.items():
            meta[key] = value
        self._mark_dirty()
    
    # ========================== Characters Operations ========================== #
    
    def get_characters(self) -> List[Dict[str, Any]]:
        """Get character list."""
        return self._manifest_data.get("characters", [])
    
    def set_characters(self, characters: List[Dict[str, Any]]) -> None:
        """Set character list."""
        self._manifest_data["characters"] = characters
        self._mark_dirty()
    
    def add_character(self, character: Dict[str, Any]) -> None:
        """Add a character."""
        if "characters" not in self._manifest_data:
            self._manifest_data["characters"] = []
        self._manifest_data["characters"].append(character)
        self._mark_dirty()
    
    # ========================== Code Patterns Operations ========================== #
    
    def get_code_patterns(self) -> List[Dict[str, Any]]:
        """Get code pattern list."""
        return self._manifest_data.get("code_patterns", [])
    
    def set_code_patterns(self, patterns: List[Dict[str, Any]]) -> None:
        """Set code pattern list."""
        self._manifest_data["code_patterns"] = patterns
        self._mark_dirty()
    
    # ========================== Glossary Operations ========================== #
    
    def get_glossary_config(self) -> GlossaryConfig:
        """Get glossary configuration."""
        data = self._manifest_data.get("glossary", {})
        return GlossaryConfig.from_dict(data)
    
    def set_glossary_config(self, config: GlossaryConfig) -> None:
        """Set glossary configuration."""
        self._manifest_data["glossary"] = config.to_dict()
        self._mark_dirty()
    
    def set_use_global_glossary(self, use_global: bool) -> None:
        """Set whether to use global glossary."""
        config = self.get_glossary_config()
        config.use_global = use_global
        self.set_glossary_config(config)
    
    def add_glossary_entry(self, entry: Dict[str, Any]) -> None:
        """Add a project-specific glossary entry."""
        config = self.get_glossary_config()
        config.project_entries.append(entry)
        self.set_glossary_config(config)
    
    # ========================== Lines Operations ========================== #
    
    def get_lines(self) -> List[Dict[str, Any]]:
        """Get all lines."""
        return self._manifest_data.get("lines", [])
    
    def set_lines(self, lines: List[Dict[str, Any]]) -> None:
        """Set all lines."""
        self._manifest_data["lines"] = canonicalize_lines(
            lines,
            self._manifest_data.get("filedir", []),
        )
        self._mark_dirty()
    
    def get_line(self, idx: int) -> Optional[Dict[str, Any]]:
        """Get a line by index."""
        for line in self._manifest_data.get("lines", []):
            if line.get("idx") == idx:
                return line
        return None
    
    def get_all_orig_lines(self) -> List[str]:
        """Return the ``orig`` text for every line in index order.

        This replaces the legacy ``all_lines`` flat array that was
        previously duplicated in ``step_state.Input.data``.  All callers
        that need the original extracted text should use this method or
        the manifest ``lines[].orig`` field directly.
        """
        return [ln.get("orig", "") for ln in self._manifest_data.get("lines", [])]

    def _infer_line_number_for_idx(self, idx: int) -> int:
        """Return the default 1-based per-file line number for *idx*."""
        entry = self.get_filedir_entry_for_idx(idx)
        if entry is not None:
            return max(1, idx - entry.first_idx + 1)
        return _default_line_number(idx)

    def set_line_field(
        self,
        idx: int,
        field: str,
        value: Any,
    ) -> bool:
        """Set a field on a specific line.

        Only marks the manifest dirty when the value actually changes
        to prevent unnecessary autosave cycles.
        """
        lines = self._manifest_data.get("lines", [])
        for line in lines:
            if line.get("idx") == idx:
                if field in line and line[field] == value:
                    return True  # No change

                if field in {"ln", "line"}:
                    normalized = _coerce_positive_int(value)
                    if normalized is None:
                        line.pop("ln", None)
                    else:
                        line["ln"] = normalized
                    line.pop("line", None)
                elif field in {"f", "field"}:
                    normalized = _coerce_positive_int(value)
                    if normalized is None:
                        line.pop("f", None)
                    else:
                        line["f"] = normalized
                    line.pop("field", None)
                else:
                    line[field] = value

                if "ln" not in line:
                    line["ln"] = self._infer_line_number_for_idx(idx)

                canonical = canonicalize_line_dict(line)
                line.clear()
                line.update(canonical)
                self._mark_dirty()
                return True
        # Line not found - create it
        line = {"idx": idx, "ln": self._infer_line_number_for_idx(idx)}
        if field in {"ln", "line"}:
            normalized = _coerce_positive_int(value)
            if normalized is not None:
                line["ln"] = normalized
        elif field in {"f", "field"}:
            normalized = _coerce_positive_int(value)
            if normalized is not None:
                line["f"] = normalized
        else:
            line[field] = value
        lines.append(canonicalize_line_dict(line))
        self._mark_dirty()
        return True

    def clear_line_field(
        self,
        idx: int,
        field: str,
    ) -> bool:
        """Remove a field from a specific line if it exists.

        This is used for sparse manifest persistence where unchanged stage
        outputs should be omitted entirely instead of stored as empty strings.
        """
        lines = self._manifest_data.get("lines", [])
        for line in lines:
            if line.get("idx") != idx:
                continue
            if field not in line:
                return True
            del line[field]
            self._mark_dirty()
            return True
        return True
    
    def update_translation(
        self,
        idx: int,
        translation: str,
    ) -> bool:
        """Update translation for a line (called during translation)."""
        return self.set_line_field(idx, "tl", translation)
    
    # ========================== Operations ========================== #
    
    def get_operations(self) -> List[Dict[str, Any]]:
        """Get operations list."""
        return self._manifest_data.get("operations", [])
    
    def set_operations(self, operations: List[Dict[str, Any]]) -> None:
        """Set operations list."""
        self._manifest_data["operations"] = operations
        self._mark_dirty()
    
    # ========================== Source Files ========================== #
    
    # source_files removed — use filedir + source_root instead.
    # Legacy callers that still call get_source_files/set_source_files will
    # get empty results / log warnings.

    def get_source_files(self) -> List[Path]:
        """Deprecated — source_files no longer stored. Use filedir."""
        logger.warning("get_source_files() is deprecated; use get_filedir()")
        return []

    def set_source_files(self, files: List[Path]) -> None:
        """Deprecated — source_files no longer stored. Use filedir."""
        logger.warning("set_source_files() is deprecated; use set_filedir()")
    
    # ========================== File Directory (TASK 35.1) ========================== #
    
    def get_filedir(self) -> List[FileDirEntry]:
        """Get file directory entries.
        
        Returns list of FileDirEntry objects mapping line index ranges to files.
        """
        entries = self._manifest_data.get("filedir", [])
        return [FileDirEntry.from_dict(e) for e in entries]
    
    def set_filedir(self, entries: List[FileDirEntry]) -> None:
        """Set file directory entries.
        
        Args:
            entries: List of FileDirEntry objects.
        """
        self._manifest_data["filedir"] = [e.to_dict() for e in entries]
        self._mark_dirty()
    
    def add_filedir_entry(self, entry: FileDirEntry) -> None:
        """Add a file directory entry.
        
        Args:
            entry: FileDirEntry to add.
        """
        if "filedir" not in self._manifest_data:
            self._manifest_data["filedir"] = []
        self._manifest_data["filedir"].append(entry.to_dict())
        self._mark_dirty()
    
    def clear_filedir(self) -> None:
        """Clear all file directory entries."""
        self._manifest_data["filedir"] = []
        self._mark_dirty()

    def remove_file(self, rel_path: str) -> bool:
        """Remove a file and its lines from the manifest, shifting subsequent indices.
        
        Args:
            rel_path: Relative path of the file to remove.
            
        Returns:
            True if removed, False if not found.
        """
        entries = self.get_filedir()
        target_entry = None
        target_index = -1
        for i, entry in enumerate(entries):
            if entry.rel_path == rel_path:
                target_entry = entry
                target_index = i
                break
                
        if not target_entry:
            return False
            
        line_count = target_entry.last_idx - target_entry.first_idx + 1
        
        # 1. Remove lines and shift existing
        new_lines = []
        for line in self._manifest_data.get("lines", []):
            idx = line.get("idx", 0)
            if target_entry.first_idx <= idx <= target_entry.last_idx:
                continue
            if idx > target_entry.last_idx:
                line["idx"] = idx - line_count
            new_lines.append(line)
        self._manifest_data["lines"] = new_lines
        
        # 2. Update subsequent filedir entries
        new_entries = []
        for i, entry in enumerate(entries):
            if i == target_index:
                continue
            if i > target_index:
                entry.first_idx -= line_count
                entry.last_idx -= line_count
            new_entries.append(entry)
            
        self.set_filedir(new_entries)
        
        # 3. Update total line counts
        if "metadata" in self._manifest_data:
            old_total = self._manifest_data["metadata"].get("total_lines", 0)
            if old_total >= line_count:
                self._manifest_data["metadata"]["total_lines"] = old_total - line_count
        
        self._mark_dirty()
        # Save immediately to prevent desync
        self.save()
        return True

    def remove_files(
        self,
        rel_paths: List[str],
        *,
        delete_originals: bool = False,
    ) -> Dict[str, int]:
        """Remove multiple files from the manifest in one reindex pass.

        Args:
            rel_paths: Relative file paths to remove.
            delete_originals: When True, also remove matching files from
                the project ``Original/`` directory.

        Returns:
            Summary dict with removed file and line counts.
        """
        remove_set = {str(rel_path) for rel_path in rel_paths if str(rel_path).strip()}
        if not remove_set:
            return {"files_removed": 0, "lines_removed": 0}

        entries = self.get_filedir()
        lines = self.get_lines()
        lines_by_idx = {line.get("idx", -1): line for line in lines}

        kept_entries: List[FileDirEntry] = []
        kept_lines: List[Dict[str, Any]] = []
        removed_entries: List[FileDirEntry] = []
        next_idx = 0

        for entry in entries:
            if entry.rel_path in remove_set:
                removed_entries.append(entry)
                continue

            first_idx = next_idx
            for old_idx in range(entry.first_idx, entry.last_idx + 1):
                line_data = lines_by_idx.get(old_idx)
                if line_data is None:
                    continue
                line_copy = dict(line_data)
                line_copy["idx"] = next_idx
                kept_lines.append(line_copy)
                next_idx += 1

            if next_idx == first_idx:
                continue

            kept_entries.append(
                FileDirEntry(
                    first_idx=first_idx,
                    last_idx=next_idx - 1,
                    format=entry.format,
                    rel_path=entry.rel_path,
                    encoding=entry.encoding,
                    type=entry.type,
                )
            )

        self._manifest_data["lines"] = canonicalize_lines(kept_lines)
        self._manifest_data["filedir"] = [entry.to_dict() for entry in kept_entries]

        if delete_originals:
            self._delete_original_copies([entry.rel_path for entry in removed_entries])

        self._mark_dirty()

        lines_removed = sum(entry.line_count for entry in removed_entries)
        logger.info(
            "Removed %d file(s) and %d line(s) from manifest",
            len(removed_entries),
            lines_removed,
        )
        return {
            "files_removed": len(removed_entries),
            "lines_removed": lines_removed,
        }

    def _delete_original_copies(self, rel_paths: List[str]) -> None:
        """Delete copied originals for the given manifest-relative paths."""
        original_dir = self.get_original_dir()
        if not original_dir.exists():
            return

        for rel_path in rel_paths:
            original_path = original_dir / rel_path
            try:
                original_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to delete original copy %s: %s", original_path, exc)
                continue

            parent = original_path.parent
            while parent != original_dir and parent.exists():
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

    def import_line_fields_from_manifest_data(
        self,
        source_data: Dict[str, Any],
        selections: Dict[str, bool],
    ) -> Dict[str, int]:
        """Import selected per-line fields from another manifest payload."""
        source_lines = source_data.get("lines", [])
        if not source_lines:
            return {"matched": 0, "total": 0}

        field_map: Dict[str, List[str]] = {
            "import_prepro": ["prepro"],
            "import_translated": ["tl", "preedit"],
            "import_postpro": ["postpro"],
            "import_wordwrap": ["wordwr"],
            "import_final": ["final"],
            "import_qa": ["qa", "qa_overwrite"],
        }

        fields_to_copy: List[str] = []
        for key, fields in field_map.items():
            if selections.get(key, False):
                fields_to_copy.extend(fields)

        merge_tags = selections.get("import_tags", False)
        skip_new = selections.get("skip_new_lines", False)

        source_lookup: Dict[str, Dict[str, Any]] = {}
        for source_line in source_lines:
            orig = source_line.get("orig", "")
            if orig not in source_lookup:
                source_lookup[orig] = source_line

        current_lines = self.get_lines()
        matched = 0
        total = len(current_lines)

        for line in current_lines:
            orig = line.get("orig", "")
            match = source_lookup.get(orig)
            if match is None:
                continue

            if skip_new and line.get("tl", ""):
                continue

            matched += 1
            is_dedup_line = (
                str(line.get("prepro", "")).strip() == DEDUP_PLACEHOLDER
                or str(match.get("prepro", "")).strip() == DEDUP_PLACEHOLDER
            )

            if merge_tags:
                merged_tags = merge_line_tags(
                    line.get("tags"),
                    line.get("tag"),
                    line.get("context_marker"),
                    match.get("tags"),
                    match.get("tag"),
                    match.get("context_marker"),
                )
                if merged_tags:
                    line["tags"] = merged_tags
                else:
                    line.pop("tags", None)
                line.pop("tag", None)
                line.pop("context_marker", None)

            for field in fields_to_copy:
                if is_dedup_line and field == "tl":
                    continue
                if field in match and match[field]:
                    line[field] = match[field]

            if selections.get("import_qa", False):
                if not line.get("qa"):
                    if match.get("qa"):
                        line["qa"] = match["qa"]
                    elif match.get("wordwr"):
                        line["qa"] = match["wordwr"]
                    elif match.get("postpro"):
                        line["qa"] = match["postpro"]

                for key, value in match.items():
                    if (key.startswith("edit") or key.startswith("tlc")) and value:
                        line[key] = value

                qa_overwrite = match.get("qa_overwrite") or match.get("overwrite")
                if qa_overwrite:
                    line["qa_overwrite"] = qa_overwrite

        self.set_lines(current_lines)
        return {"matched": matched, "total": total}

    def import_settings_sections_from_manifest_data(
        self,
        source_data: Dict[str, Any],
        selections: Dict[str, bool],
    ) -> int:
        """Import selected manifest-level settings from another manifest payload."""
        count = 0

        if selections.get("import_analysis", False):
            source_step_state = source_data.get("step_state", {}).get("Analysis")
            if source_step_state:
                self._manifest_data.setdefault("step_state", {})["Analysis"] = source_step_state
                self._mark_dirty()
                count += 1

        if selections.get("import_information", False):
            source_step_state = source_data.get("step_state", {}).get("Information")
            source_metadata = (
                source_step_state.get("data", {}).get("metadata", {})
                if source_step_state else {}
            )
            if source_metadata:
                merged_metadata = dict(self.get_info_metadata())
                for key, value in source_metadata.items():
                    if key == "project_name":
                        continue
                    merged_metadata[key] = value
                self.set_info_metadata(merged_metadata)
                count += 1

            for key in ("glossary", "code_patterns", "characters"):
                source_value = source_data.get(key)
                if source_value:
                    self._manifest_data[key] = source_value
                    self._mark_dirty()

        if selections.get("import_preprocessing", False):
            preprocessing_keys = [
                "Deduplication",
                "DeduplicationThreshold",
                "EllipsisCompression",
                "SymbolConversion",
                "SpeakerNameReplacement",
                "CodeSpacingRules",
                "ProtectCodePatterns",
                "CustomPlaceholders",
                "AnchorRemoval",
            ]
            for key in preprocessing_keys:
                if key in source_data:
                    self._manifest_data[key] = source_data[key]
            self._mark_dirty()
            count += 1

        if selections.get("import_costs", False):
            source_request_options = source_data.get("RequestOptions")
            if source_request_options:
                self._manifest_data["RequestOptions"] = source_request_options
                self._mark_dirty()
                count += 1

        if selections.get("import_translation", False):
            source_step_state = source_data.get("step_state", {}).get("Translation")
            if source_step_state:
                self._manifest_data.setdefault("step_state", {})["Translation"] = source_step_state
                self._mark_dirty()
                count += 1

        if selections.get("import_postprocessing", False):
            source_postprocessing = source_data.get("PostProcessing")
            if source_postprocessing:
                self._manifest_data["PostProcessing"] = source_postprocessing
                self._mark_dirty()
                count += 1

        if selections.get("import_wordwrap_settings", False):
            source_wordwrap = source_data.get("WordwrapSettings")
            if source_wordwrap:
                self._manifest_data["WordwrapSettings"] = source_wordwrap
                self._mark_dirty()
                count += 1

        if selections.get("import_qa_settings", False):
            source_validation_rules = source_data.get("ValidationRules")
            if source_validation_rules:
                self._manifest_data["ValidationRules"] = source_validation_rules
            source_qa_options = source_data.get("QAOptions")
            if source_qa_options:
                self._manifest_data["QAOptions"] = source_qa_options
            for key in (
                "CharacterWhitelist",
                "CharacterBlacklist",
                "WordBlacklist",
                "AutofixMap",
            ):
                if key in source_data:
                    self._manifest_data[key] = source_data[key]
            self._mark_dirty()
            count += 1

        if selections.get("import_file_settings", False):
            source_output_format = source_data.get("OutputFormat")
            if source_output_format:
                self._manifest_data["OutputFormat"] = source_output_format
                self._mark_dirty()
                count += 1

        return count

    def import_from_manifest_data(
        self,
        source_data: Dict[str, Any],
        selections: Dict[str, bool],
    ) -> Dict[str, int]:
        """Import line and settings data from another manifest payload."""
        line_stats = self.import_line_fields_from_manifest_data(source_data, selections)
        section_count = self.import_settings_sections_from_manifest_data(
            source_data,
            selections,
        )
        return {
            "matched": line_stats["matched"],
            "total": line_stats["total"],
            "sections_imported": section_count,
        }

    def find_files_with_full_orig_match(
        self,
        source_data: Dict[str, Any],
    ) -> List[str]:
        """Return filedir paths whose every ``orig`` line exists in *source_data*."""
        source_orig_values = {
            line.get("orig", "")
            for line in source_data.get("lines", [])
            if isinstance(line, dict) and "orig" in line
        }
        if not source_orig_values and not source_data.get("lines"):
            return []

        lines = self.get_lines()
        removable: List[str] = []
        for entry in self.get_filedir():
            matched_count = 0
            total_count = 0
            for idx in range(entry.first_idx, entry.last_idx + 1):
                if idx >= len(lines):
                    continue
                line = lines[idx]
                total_count += 1
                if line.get("orig", "") in source_orig_values:
                    matched_count += 1
            if total_count > 0 and matched_count == total_count:
                removable.append(entry.rel_path)
        return removable

    def find_identical_original_files(self, other: "ManifestManager") -> List[str]:
        """Return shared ``rel_path`` values whose copied Originals are byte-identical."""
        other_lookup = {entry.rel_path: entry for entry in other.get_filedir()}
        shared_paths = [
            entry.rel_path
            for entry in self.get_filedir()
            if entry.rel_path in other_lookup
        ]
        if not shared_paths:
            return []

        identical: List[str] = []
        self_original_dir = self.get_original_dir()
        other_original_dir = other.get_original_dir()
        for rel_path in shared_paths:
            current_path = self_original_dir / rel_path
            source_path = other_original_dir / rel_path
            if not current_path.is_file() or not source_path.is_file():
                continue
            try:
                if current_path.stat().st_size != source_path.stat().st_size:
                    continue
                if _file_sha256(current_path) == _file_sha256(source_path):
                    identical.append(rel_path)
            except OSError as exc:
                logger.debug("Skipping identical-original compare for %s: %s", rel_path, exc)
        return identical

    def create_patch_from_manifest_path(self, source_manifest_path: Path) -> Dict[str, Any]:
        """Import data from *source_manifest_path* and prune unchanged files.

        The current manifest becomes the patch manifest: first identical files are
        removed via ``Original/`` hash comparison, then the source manifest is fully
        imported, and finally any remaining file whose every ``orig`` line exists in
        the source manifest is removed as complete.
        """
        if not self.is_loaded:
            raise ValueError("No current manifest is loaded")

        source_manager = ManifestManager()
        if not source_manager.load(source_manifest_path):
            raise ValueError(f"Failed to load source manifest: {source_manifest_path}")

        try:
            source_data = deepcopy(source_manager.get_raw_data())
            identical_files = self.find_identical_original_files(source_manager)
            identical_summary = self.remove_files(identical_files, delete_originals=True)

            import_summary = self.import_from_manifest_data(
                source_data,
                dict(CREATE_PATCH_SELECTIONS),
            )

            matched_files = self.find_files_with_full_orig_match(source_data)
            matched_summary = self.remove_files(matched_files, delete_originals=True)

            self.save()

            return {
                "matched": import_summary["matched"],
                "total": import_summary["total"],
                "sections_imported": import_summary["sections_imported"],
                "identical_files_removed": identical_summary["files_removed"],
                "identical_lines_removed": identical_summary["lines_removed"],
                "matched_files_removed": matched_summary["files_removed"],
                "matched_lines_removed": matched_summary["lines_removed"],
                "remaining_files": len(self.get_filedir()),
                "remaining_lines": len(self.get_lines()),
            }
        finally:
            source_manager.close()
    
    def get_filedir_entry_for_idx(self, idx: int) -> Optional[FileDirEntry]:
        """Get the FileDirEntry that contains the given line index.
        
        Args:
            idx: Line index to look up.
            
        Returns:
            FileDirEntry containing idx, or None if not found.
        """
        for entry_dict in self._manifest_data.get("filedir", []):
            entry = FileDirEntry.from_dict(entry_dict)
            if entry.contains_idx(idx):
                return entry
        return None
    
    def get_lines_for_filedir_entry(self, entry: FileDirEntry) -> List[Dict[str, Any]]:
        """Get all lines belonging to a FileDirEntry.
        
        Args:
            entry: FileDirEntry to get lines for.
            
        Returns:
            List of line dictionaries in the entry's index range.
        """
        lines = []
        for line in self._manifest_data.get("lines", []):
            idx = line.get("idx", -1)
            if entry.first_idx <= idx <= entry.last_idx:
                lines.append(line)
        return lines

    def get_lines_for_locator_target(
        self,
        *,
        rel_path: Optional[str] = None,
        idx: Optional[int] = None,
        ln: Optional[int] = None,
        field: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return manifest rows matching a file-scoped ``idx``/``ln``/``f`` target."""
        if rel_path is not None:
            entry = self.get_filedir_entry_by_rel_path(rel_path)
            if entry is None:
                return []
            candidate_lines = self.get_lines_for_filedir_entry(entry)
        else:
            candidate_lines = list(self._manifest_data.get("lines", []))

        result: List[Dict[str, Any]] = []
        for line in candidate_lines:
            line_idx = _coerce_int(line.get("idx"), -1)
            line_ln = _coerce_int(line.get("ln"), -1)
            line_field = _coerce_int(line.get("f"), -1) if "f" in line else None
            if idx is not None and line_idx != idx:
                continue
            if ln is not None and line_ln != ln:
                continue
            if field is not None and line_field != field:
                continue
            result.append(line)

        result.sort(key=lambda line: _coerce_int(line.get("idx"), -1))
        return result

    def get_filedir_entry_by_rel_path(self, rel_path: str) -> Optional[FileDirEntry]:
        """Return the filedir entry for *rel_path*, if present."""
        normalized = str(rel_path).replace("\\", "/")
        for entry_dict in self._manifest_data.get("filedir", []):
            entry = FileDirEntry.from_dict(entry_dict)
            if entry.rel_path.replace("\\", "/") == normalized:
                return entry
        return None

    def get_editor_file_view(
        self,
        rel_path: str,
        *,
        current_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return shared Full Files view data for one staged file.

        The returned payload centralizes path resolution, locator-aware line
        history assembly, and unified diff generation so GUI consumers do not
        duplicate those responsibilities.
        """
        entry = self.get_filedir_entry_by_rel_path(rel_path)
        if entry is None:
            raise ValueError(f"Unknown editor file path: {rel_path}")

        current_path = self._resolve_editor_current_file_path(entry)
        original_path = self.get_original_file_path(entry)
        encoding = entry.encoding or "utf-8"
        staged_current_text = self._read_editor_text(current_path, encoding)
        editor_state = self._get_editor_state_files(create=False).get(entry.rel_path, {})

        resolved_current_text = current_text
        if resolved_current_text is None:
            resolved_current_text = staged_current_text
        original_text = self._read_editor_text(original_path, encoding)
        line_history, locator_metadata = self._build_editor_line_history(
            entry,
            resolved_current_text,
            current_path,
            fallback_text=original_text,
            allow_path_extract=current_text is None,
        )

        diff_to_original = "\n".join(
            difflib.unified_diff(
                original_text.splitlines(),
                resolved_current_text.splitlines(),
                fromfile=f"Original/{entry.rel_path}",
                tofile=f"Current/{entry.rel_path}",
                lineterm="",
            )
        )
        if current_text is None:
            diff_to_patch = self._load_saved_patch_diff_text(
                entry,
                current_text=resolved_current_text,
                current_path=current_path,
                original_text=original_text,
            )
        else:
            diff_to_patch = self._build_diff_between_versions(
                staged_current_text,
                resolved_current_text,
                entry.rel_path,
                tofile=f"Edited/{entry.rel_path}",
            )

        return {
            "entry": entry,
            "rel_path": entry.rel_path,
            "current_path": current_path,
            "original_path": original_path,
            "current_text": resolved_current_text,
            "original_text": original_text,
            "diff_to_original": diff_to_original,
            "diff_to_patch": diff_to_patch,
            "line_history": line_history,
            "locator_metadata": locator_metadata,
            "history": editor_state.get("history", []),
            "patch_translated_path": editor_state.get("patch_translated_path"),
        }

    def save_editor_patch(
        self,
        rel_path: str,
        text: str,
        *,
        change_label: str = "",
        max_history: int = 10,
    ) -> Dict[str, Any]:
        """Persist one Full Files save into the staged translated layout."""
        entry = self.get_filedir_entry_by_rel_path(rel_path)
        if entry is None:
            raise ValueError(f"Unknown editor file path: {rel_path}")

        return self._stage_editor_text_save(
            entry,
            text,
            change_label=change_label,
            source="full_files",
            max_history=max_history,
        )

    def save_lines_only_changes(
        self,
        changes: Dict[int, Dict[str, Any]],
        deleted_fields: Optional[Dict[int, set[str]]] = None,
        *,
        selected_indices: Optional[set[int]] = None,
        change_label: str = "",
        max_history: int = 10,
    ) -> Dict[str, Any]:
        """Persist sparse row edits and refresh staged translated artifacts."""
        deleted_fields = deleted_fields or {}
        if selected_indices is not None:
            target_indices = {
                idx for idx in set(selected_indices)
                if idx in changes or idx in deleted_fields
            }
        else:
            target_indices = set(changes) | set(deleted_fields)

        if not target_indices:
            return {
                "fields_saved": 0,
                "files_updated": 0,
                "artifacts": [],
                "saved_indices": [],
            }

        affected_rel_paths: set[str] = set()
        fields_saved = 0
        for idx in sorted(target_indices):
            line_changes = dict(changes.get(idx, {}))
            deleted = set(deleted_fields.get(idx, set()))

            for field_name, value in line_changes.items():
                if field_name in deleted:
                    continue
                self.set_line_field(idx, field_name, value)
                fields_saved += 1

            for field_name in deleted:
                self.clear_line_field(idx, field_name)
                fields_saved += 1

            self._promote_saved_stage_for_idx(
                idx,
                changed_fields=set(line_changes),
                deleted_fields=deleted,
            )

            entry = self.get_filedir_entry_for_idx(idx)
            if entry is not None:
                affected_rel_paths.add(entry.rel_path)

        artifacts: List[Dict[str, Any]] = []
        for rel_path in sorted(affected_rel_paths):
            entry = self.get_filedir_entry_by_rel_path(rel_path)
            if entry is None:
                continue
            rendered_path = self._render_manifest_entry_to_temp_path(entry)
            try:
                artifacts.append(
                    self.stage_translated_output_file(
                        entry,
                        rendered_path,
                        change_label=change_label,
                        source="lines_only",
                        max_history=max_history,
                        synthesize_patch_if_missing=True,
                    )
                )
            finally:
                try:
                    rendered_path.unlink(missing_ok=True)
                except OSError:
                    logger.debug("Failed to remove temporary rendered file: %s", rendered_path)
                parent = rendered_path.parent
                try:
                    parent.rmdir()
                except OSError:
                    pass

        return {
            "fields_saved": fields_saved,
            "files_updated": len(artifacts),
            "artifacts": artifacts,
            "saved_indices": sorted(target_indices),
        }

    def refresh_line_locators_for_entry(
        self,
        entry: FileDirEntry,
        source_text: str,
        extracted_lines: List[str],
    ) -> bool:
        """Refresh ``ln``/``f`` locators for *entry* from a changed source view."""
        changed = refresh_file_line_locators(
            self._manifest_data.get("lines", []),
            entry,
            source_text,
            extracted_lines,
        )
        if changed:
            self._mark_dirty()
        return changed

    def _get_editor_state_files(self, *, create: bool = False) -> Dict[str, Any]:
        """Return the top-level ``EditorState.files`` mapping."""
        editor_state = self._manifest_data.get("EditorState")
        if not isinstance(editor_state, dict):
            if not create:
                return {}
            editor_state = {}
            self._manifest_data["EditorState"] = editor_state

        files = editor_state.get("files")
        if not isinstance(files, dict):
            if not create:
                return {}
            files = {}
            editor_state["files"] = files
        return files

    def _stage_editor_text_save(
        self,
        entry: FileDirEntry,
        text: str,
        *,
        change_label: str,
        source: str,
        max_history: int,
    ) -> Dict[str, Any]:
        """Stage editor text into the current translated layout and state."""
        previous_view = self.get_editor_file_view(entry.rel_path)
        encoding = entry.encoding or "utf-8"
        new_bytes = text.encode(encoding)
        staged = self._stage_translated_bytes(
            entry,
            new_bytes,
            decoded_text=text,
            change_label=change_label,
            source=source,
            max_history=max_history,
            synthesize_patch_if_missing=False,
            previous_view=previous_view,
        )
        return staged

    def _build_diff_between_versions(
        self,
        old_text: str,
        new_text: str,
        rel_path: str,
        *,
        tofile: str,
    ) -> str:
        """Build a unified diff between two editor-visible text versions."""
        return "\n".join(
            difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile=f"Previous/{rel_path}",
                tofile=tofile,
                lineterm="",
            )
        )

    def _promote_saved_stage_for_idx(
        self,
        idx: int,
        *,
        changed_fields: set[str],
        deleted_fields: set[str],
    ) -> None:
        """Clear later pipeline fields so the saved stage becomes current."""
        from CherryAI.functions.manifest_fields import PIPELINE_FIELDS

        chosen_stage: Optional[str] = None
        for field_name in PIPELINE_FIELDS:
            if field_name in changed_fields and field_name not in deleted_fields:
                chosen_stage = field_name
                break

        if not chosen_stage:
            return

        line_data = self.get_line(idx)
        if line_data is None or not _should_keep_line_value(line_data.get(chosen_stage)):
            return

        for field_name in PIPELINE_FIELDS:
            if field_name == chosen_stage:
                break
            if field_name in changed_fields:
                continue
            if _should_keep_line_value(line_data.get(field_name)):
                self.clear_line_field(idx, field_name)

    def _render_manifest_entry_to_temp_path(self, entry: FileDirEntry) -> Path:
        """Render one manifest-backed file to a temporary path."""
        temp_dir = Path(tempfile.mkdtemp(prefix="cherryai-stage-"))
        render_path = temp_dir / Path(entry.rel_path).name
        self.render_manifest_entry_to_path(entry, render_path)
        return render_path

    def render_manifest_entry_to_path(self, entry: FileDirEntry, output_path: Path) -> Dict[str, Any]:
        """Render one manifest-backed file to *output_path*."""
        from CherryAI.formats import get_handler, get_parser_registry
        from CherryAI.formats.parser_base import ParserScript
        from CherryAI.functions.manifest_fields import resolve_line_field
        from CherryAI.functions.output import sanitize_output_text

        output_path.parent.mkdir(parents=True, exist_ok=True)

        parser = get_parser_registry().get(entry.format)
        if parser is not None:
            source_path = self.resolve_file_path(entry.rel_path)
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")

            source_text = self._read_editor_text(source_path, entry.encoding or "utf-8")
            extracted_keys = parser.extract(source_path)
            self.refresh_line_locators_for_entry(entry, source_text, extracted_keys)
            manifest_lines = self._manifest_data.get("lines", [])
            matched_manifest_lines = match_manifest_lines_to_source(
                source_text,
                extracted_keys,
                manifest_lines,
                first_idx=entry.first_idx,
                last_idx=entry.last_idx,
            )

            inject_items: List[tuple[int, str, str]] = []
            failures: List[str] = []
            for offset, key in enumerate(extracted_keys):
                clean_key = sanitize_output_text(key)
                matched = matched_manifest_lines[offset] if offset < len(matched_manifest_lines) else None
                if matched is None:
                    manifest_idx = entry.first_idx + offset
                    if entry.first_idx <= manifest_idx <= entry.last_idx and manifest_idx < len(manifest_lines):
                        matched = manifest_lines[manifest_idx]
                    else:
                        failures.append(
                            f"Position {offset}: no manifest row for extracted locator {clean_key!r}"
                        )
                        inject_items.append((offset, clean_key, clean_key))
                        continue

                orig = sanitize_output_text(matched.get("orig", ""))
                # For injection verification, normalize leading/trailing whitespace
                # since indent: and trail: tags may not be populated in all projects
                from .output import normalize_whitespace_for_comparison
                clean_key_normalized = normalize_whitespace_for_comparison(clean_key)
                orig_normalized = normalize_whitespace_for_comparison(orig)
                
                if orig_normalized != clean_key_normalized:
                    failures.append(
                        f"Position {offset} (ln={matched.get('ln')}, f={matched.get('f')}): "
                        f"orig mismatch — extracted {clean_key!r}, manifest {orig!r}"
                    )
                    inject_items.append((offset, clean_key, orig))
                    continue

                inject_items.append((
                    offset,
                    sanitize_output_text(resolve_line_field(matched)),
                    orig,
                ))

            inject_sequence = list(reversed(inject_items))
            if type(parser).inject_to is not ParserScript.inject_to:
                inject_sequence = inject_items

            translated_lines = [translated for _position, translated, _orig in inject_sequence]
            orig_lines = [orig for _position, _translated, orig in inject_sequence]
            inject_failures = parser.inject_to(
                source_path,
                output_path,
                translated_lines,
                orig_lines=orig_lines,
            )
            return {
                "line_count": len(extracted_keys),
                "failures": failures,
                "inject_failures": inject_failures,
            }

        handler = get_handler(entry.format) or get_handler(output_path.suffix)
        if handler is None:
            raise ValueError(f"No output handler for format {entry.format!r}")

        lines = [
            sanitize_output_text(resolve_line_field(line_data))
            for line_data in self.get_lines_for_filedir_entry(entry)
        ]
        original_lines = [
            sanitize_output_text(line_data.get("orig", ""))
            for line_data in self.get_lines_for_filedir_entry(entry)
        ]
        handler.inject(
            output_path,
            lines,
            original_lines=original_lines,
            encoding=entry.encoding or "utf-8",
        )
        return {
            "line_count": len(lines),
            "failures": [],
            "inject_failures": [],
        }

    def _derive_entry_input_root(self, entry: FileDirEntry) -> Optional[Path]:
        """Return the reconstructed source root for one filedir entry."""
        rel_path = Path(entry.rel_path)
        if not rel_path.parts:
            return None

        source_path = self.resolve_file_path(entry.rel_path)
        root = source_path
        for _part in rel_path.parts:
            root = root.parent
        return root

    def run_parser_post_inject_hooks(
        self,
        project_root: Path,
        *,
        file_indices: Optional[List[int]] = None,
    ) -> List[str]:
        """Run optional project-level hooks for parsers touched by Step 9."""
        from CherryAI.formats import get_parser_registry

        filedir = self.get_filedir()
        indices = file_indices if file_indices is not None else list(range(len(filedir)))
        seen: set[str] = set()
        ran: List[str] = []

        for index in indices:
            if index < 0 or index >= len(filedir):
                continue

            entry = filedir[index]
            parser = get_parser_registry().get(entry.format)
            if parser is None or parser.name in seen:
                continue

            hook = getattr(parser, "post_inject_project", None)
            if not callable(hook):
                continue

            hook(Path(project_root), input_root=self._derive_entry_input_root(entry))
            seen.add(parser.name)
            ran.append(parser.name)

        return ran

    def stage_translated_output_file(
        self,
        entry: FileDirEntry,
        output_path: Path,
        *,
        change_label: str = "",
        source: str = "output",
        max_history: int = 10,
        synthesize_patch_if_missing: bool = False,
        mark_dirty: bool = True,
    ) -> Dict[str, Any]:
        """Mirror a written output file into CherryAI's staged translated layout."""
        previous_view = self.get_editor_file_view(entry.rel_path)
        decoded_text: Optional[str]
        try:
            decoded_text = output_path.read_text(encoding=entry.encoding or "utf-8")
        except (OSError, UnicodeDecodeError):
            decoded_text = None
        return self._stage_translated_bytes(
            entry,
            output_path.read_bytes(),
            decoded_text=decoded_text,
            change_label=change_label,
            source=source,
            max_history=max_history,
            synthesize_patch_if_missing=synthesize_patch_if_missing,
            mark_dirty=mark_dirty,
            previous_view=previous_view,
        )

    def _stage_translated_bytes(
        self,
        entry: FileDirEntry,
        new_bytes: bytes,
        *,
        decoded_text: Optional[str],
        change_label: str,
        source: str,
        max_history: int,
        synthesize_patch_if_missing: bool,
        mark_dirty: bool,
        previous_view: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist translated bytes and update manifest-backed editor state."""
        previous_view = previous_view or self.get_editor_file_view(entry.rel_path)
        translated_path = self.get_translated_file_path(entry)

        artifact_info: Dict[str, Any]
        if source == "step9":
            self._remove_patch_translated_artifacts_for_entry(entry)
            target_path = self.ensure_translated_file_path(entry)
            target_path.write_bytes(new_bytes)
            artifact_info = {
                "decision": "replaced" if translated_path.exists() else "written",
                "artifact_path": None,
                "translated_path": translated_path,
            }
        elif translated_path.exists():
            artifact_info = self.capture_reverse_patch_for_translated_bytes(entry, new_bytes)
            target_path = self.ensure_translated_file_path(entry)
            target_path.write_bytes(new_bytes)
        elif synthesize_patch_if_missing:
            target_path = self.ensure_patch_translated_file_path(entry)
            target_path.write_bytes(new_bytes)
            artifact_info = {
                "decision": "add",
                "artifact_path": target_path,
                "translated_path": translated_path,
            }
        else:
            target_path = self.ensure_translated_file_path(entry)
            target_path.write_bytes(new_bytes)
            artifact_info = {
                "decision": "missing",
                "artifact_path": None,
                "translated_path": translated_path,
            }

        current_view = self.get_editor_file_view(entry.rel_path)
        saved_at = datetime.utcnow().isoformat() + "Z"
        patch_artifact = artifact_info.get("artifact_path")
        patch_rel_path = self._relativize_project_path(patch_artifact)

        history_entry: Optional[Dict[str, Any]] = None
        if patch_artifact is not None:
            history_entry = {
                "saved_at": saved_at,
                "source": source,
                "patch_path": patch_rel_path,
                "patch_decision": artifact_info.get("decision"),
            }
            if change_label:
                history_entry["change_label"] = change_label

        files_state = self._get_editor_state_files(create=True)
        existing_record = files_state.get(entry.rel_path, {})
        history = existing_record.get("history", [])
        if not isinstance(history, list):
            history = []
        if source == "step9":
            history = []
        if history_entry is not None:
            history.append(history_entry)
            if max_history > 0:
                history = history[-max_history:]

        files_state[entry.rel_path] = {
            "saved_at": saved_at,
            "translated_path": self._relativize_project_path(
                translated_path if translated_path.exists() else None
            ),
            "patch_original_path": self._current_patch_original_reference(entry),
            "patch_translated_path": None if source == "step9" else patch_rel_path,
            "history": history,
        }
        if mark_dirty:
            self._mark_dirty()

        result = {
            "rel_path": entry.rel_path,
            "saved_at": saved_at,
            "translated_path": target_path,
            "patch_info": artifact_info,
            "line_history": current_view["line_history"],
            "locator_metadata": current_view["locator_metadata"],
        }
        result["diff_to_patch"] = self._load_saved_patch_diff_text(
            entry,
            current_text=current_view["current_text"],
            current_path=current_view["current_path"],
            original_text=current_view["original_text"],
        )
        if decoded_text is not None:
            result["text"] = decoded_text
        return result

    def mark_dirty(self) -> None:
        """Public dirty marker for callers that batch manifest updates."""
        self._mark_dirty()

    def _display_stage_path(self, path: Path) -> str:
        """Return a stable staged display path for diffs."""
        try:
            return str(path.relative_to(self.get_project_dir())).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def _resolve_project_relative_path(self, rel_path: Optional[str]) -> Optional[Path]:
        """Return a project-scoped path from stored manifest metadata."""
        if not rel_path:
            return None
        path = Path(str(rel_path))
        if path.is_absolute():
            return path
        return self.get_project_dir() / path

    def _relativize_project_path(self, path: Optional[Path]) -> Optional[str]:
        """Return *path* relative to the current project directory when possible."""
        if path is None:
            return None
        try:
            return str(path.relative_to(self.get_project_dir())).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def _current_patch_original_reference(self, entry: FileDirEntry) -> Optional[str]:
        """Return the current patch-original artifact path for *entry*, if any."""
        artifact_path = self.get_patch_original_file_path(entry)
        diff_path = artifact_path.with_name(artifact_path.name + ".patch")
        if diff_path.exists():
            return self._relativize_project_path(diff_path)
        if artifact_path.exists():
            return self._relativize_project_path(artifact_path)
        return None

    def _apply_unified_diff_to_text(self, source_text: str, diff_text: str) -> Optional[str]:
        """Apply a unified diff generated from *source_text* and return the target text."""
        source_lines = source_text.splitlines()
        diff_lines = diff_text.splitlines()
        result: List[str] = []
        source_index = 0
        line_index = 0
        saw_hunk = False

        while line_index < len(diff_lines):
            line = diff_lines[line_index]
            if not line.startswith("@@ "):
                line_index += 1
                continue

            saw_hunk = True
            try:
                header = line.split("@@", 2)[1].strip()
                source_range = header.split(" ")[0]
                source_start_text = source_range[1:].split(",", 1)[0]
                source_start = max(int(source_start_text) - 1, 0)
            except (IndexError, ValueError):
                return None

            while source_index < source_start and source_index < len(source_lines):
                result.append(source_lines[source_index])
                source_index += 1

            line_index += 1
            while line_index < len(diff_lines):
                diff_line = diff_lines[line_index]
                if diff_line.startswith("@@ "):
                    break
                if diff_line.startswith("--- ") or diff_line.startswith("+++ "):
                    line_index += 1
                    continue
                if diff_line.startswith("\\ No newline"):
                    line_index += 1
                    continue
                if not diff_line:
                    tag = " "
                    content = ""
                else:
                    tag = diff_line[0]
                    content = diff_line[1:]

                if tag == " ":
                    if source_index >= len(source_lines):
                        return None
                    result.append(source_lines[source_index])
                    source_index += 1
                elif tag == "-":
                    if source_index >= len(source_lines):
                        return None
                    source_index += 1
                elif tag == "+":
                    result.append(content)
                else:
                    return None
                line_index += 1

        if not saw_hunk:
            return None

        result.extend(source_lines[source_index:])
        return "\n".join(result)

    def _load_saved_patch_diff_text(
        self,
        entry: FileDirEntry,
        *,
        current_text: str,
        current_path: Path,
        original_text: str,
    ) -> str:
        """Rebuild patch diff text from staged artifacts instead of manifest state."""
        editor_state = self._get_editor_state_files(create=False).get(entry.rel_path, {})
        patch_path = self._resolve_project_relative_path(editor_state.get("patch_translated_path"))
        if patch_path is None or not patch_path.exists():
            return ""

        if patch_path.suffix == ".patch":
            try:
                reverse_diff_text = patch_path.read_text(encoding="utf-8")
            except OSError:
                logger.debug("Failed to read patch diff artifact: %s", patch_path)
                return ""

            previous_text = self._apply_unified_diff_to_text(current_text, reverse_diff_text)
            if previous_text is None:
                return reverse_diff_text

            return self._build_diff_between_versions(
                previous_text,
                current_text,
                entry.rel_path,
                tofile=self._display_stage_path(current_path),
            )

        baseline_text = original_text
        if patch_path != current_path:
            baseline_text = self._read_editor_text(patch_path, entry.encoding or "utf-8")

        return self._build_diff_between_versions(
            baseline_text,
            current_text,
            entry.rel_path,
            tofile=self._display_stage_path(current_path),
        )

    def _build_latest_saved_row_state(self, entry: FileDirEntry) -> Dict[str, Dict[str, Any]]:
        """Build the latest effective row state for one file slice."""
        from CherryAI.functions.manifest_fields import resolve_line_field_with_source

        state: Dict[str, Dict[str, Any]] = {}
        for line_data in self.get_lines_for_filedir_entry(entry):
            idx = _coerce_int(line_data.get("idx"), -1)
            if idx < 0:
                continue
            resolved_text, source_field = resolve_line_field_with_source(line_data)
            row_state: Dict[str, Any] = {
                "text": resolved_text,
                "field": source_field,
                "ln": _coerce_positive_int(line_data.get("ln")) or _default_line_number(idx),
            }
            field_value = _coerce_positive_int(line_data.get("f"))
            if field_value is not None:
                row_state["f"] = field_value
            state[str(idx)] = row_state
        return state

    def _resolve_editor_current_file_path(self, entry: FileDirEntry) -> Path:
        """Return the preferred current staged file path for Full Files."""
        translated_path = self.get_translated_file_path(entry)
        if translated_path.exists():
            return translated_path

        patch_path = self.get_patch_translated_file_path(entry)
        if patch_path.exists():
            return patch_path

        return self.get_original_file_path(entry)

    def _read_editor_text(self, path: Path, encoding: str) -> str:
        """Read text for editor consumers, returning an empty string on failure."""
        try:
            return path.read_text(encoding=encoding, errors="ignore")
        except OSError:
            logger.debug("Editor source file unavailable: %s", path)
            return ""

    def _extract_editor_lines(
        self,
        entry: FileDirEntry,
        path: Path,
    ) -> List[str]:
        """Extract current staged lines using shared parser/format handlers."""
        try:
            from CherryAI.formats import get_handler, get_parser_registry
        except Exception:
            return self._read_editor_text(path, entry.encoding or "utf-8").splitlines()

        parser_registry = get_parser_registry()
        parser = parser_registry.get(entry.format) or parser_registry.detect(path)
        if parser is not None:
            try:
                return parser.extract(path)
            except Exception as exc:
                logger.debug("Editor parser extract failed for %s: %s", path, exc)

        handler = get_handler(entry.format) or get_handler(path.suffix)
        if handler is not None:
            try:
                return handler.extract(path, encoding=entry.encoding or "utf-8")
            except TypeError:
                try:
                    return handler.extract(path)
                except Exception as exc:
                    logger.debug("Editor handler extract failed for %s: %s", path, exc)
            except Exception as exc:
                logger.debug("Editor handler extract failed for %s: %s", path, exc)

        return self._read_editor_text(path, entry.encoding or "utf-8").splitlines()

    def _build_editor_line_history(
        self,
        entry: FileDirEntry,
        source_text: str,
        source_path: Path,
        *,
        fallback_text: str = "",
        allow_path_extract: bool = True,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Build locator-aware line history rows for one editor file view."""
        from CherryAI.functions.manifest_fields import resolve_line_field

        manifest_lines = self.get_lines_for_filedir_entry(entry)
        extracted_lines = []
        if allow_path_extract:
            extracted_lines = self._extract_editor_lines(entry, source_path)
        if not extracted_lines:
            extracted_lines = source_text.splitlines()
        if not extracted_lines and fallback_text:
            extracted_lines = fallback_text.splitlines()

        mappings = capture_source_line_mappings(source_text, extracted_lines)
        matched_rows = match_manifest_lines_to_source(
            source_text,
            extracted_lines,
            self._manifest_data.get("lines", []),
            first_idx=entry.first_idx,
            last_idx=entry.last_idx,
        )

        current_by_idx: Dict[int, str] = {}
        locator_metadata: List[Dict[str, Any]] = []
        for extracted_line, mapping, matched_row in zip(extracted_lines, mappings, matched_rows):
            metadata: Dict[str, Any] = {
                "editor_ln": mapping["ln"],
            }
            if "f" in mapping:
                metadata["editor_f"] = mapping["f"]
            if matched_row is None:
                metadata["matched"] = False
                metadata["current"] = extracted_line
                locator_metadata.append(metadata)
                continue

            idx = _coerce_int(matched_row.get("idx"), -1)
            current_by_idx[idx] = extracted_line
            metadata.update({
                "matched": True,
                "idx": idx,
                "ln": matched_row.get("ln"),
                "current": extracted_line,
            })
            if "f" in matched_row:
                metadata["f"] = matched_row.get("f")
            locator_metadata.append(metadata)

        fallback_lines = source_text.splitlines()
        line_history: List[Dict[str, Any]] = []
        for offset, line_data in enumerate(manifest_lines):
            idx = _coerce_int(line_data.get("idx"), offset)
            current_line = current_by_idx.get(idx, "")
            if not current_line and offset < len(fallback_lines):
                current_line = fallback_lines[offset]

            original_line = str(line_data.get("orig", ""))
            translated_line = resolve_line_field(line_data)
            status = "all"
            if current_line != original_line and current_line == translated_line:
                status = "translated"
            elif current_line != original_line:
                status = "edited"

            history_row: Dict[str, Any] = {
                "idx": idx,
                "ln": line_data.get("ln"),
                "status": status,
                "original": original_line,
                "translated": translated_line,
                "current": current_line,
            }
            if "f" in line_data:
                history_row["f"] = line_data.get("f")
            line_history.append(history_row)

        return line_history, locator_metadata
    
    def get_project_dir(self) -> Path:
        """Get the project directory path.
        
        Returns path like Projects/{project_name}/ for storing Original/ and Patch/.
        """
        name = self.project_name or "Untitled"
        safe_name = "".join(c for c in name if c.isalnum() or c in " -_").strip()
        if not safe_name:
            safe_name = "Untitled"
        return MANIFEST_DIR / safe_name
    
    def get_original_dir(self) -> Path:
        """Get the Original/ directory path for copied source files.
        
        TASK 35.2: Returns Projects/{project_name}/Original/
        """
        return self.get_project_dir() / "Original"

    def get_translated_dir(self) -> Path:
        """Get the Translated/ directory path for latest translated files."""
        return self.get_project_dir() / "Translated"

    def get_patch_original_dir(self) -> Path:
        """Get the Patch/Original/ directory path for staged source patches."""
        return self.get_project_dir() / "Patch" / "Original"

    def get_patch_translated_dir(self) -> Path:
        """Get the Patch/Translated/ directory path for translated patch files."""
        return self.get_project_dir() / "Patch" / "Translated"

    def get_backup_dir(self) -> Path:
        """Get the Backups/ directory path for saved translated branches."""
        return self.get_project_dir() / "Backups"

    def get_package_original_dir(self) -> Path:
        """Get the Package/Original/ directory path for unpacked archives."""
        return self.get_project_dir() / "Package" / "Original"

    def get_package_translated_dir(self) -> Path:
        """Get the Package/Translated/ directory path for rebuilt archives."""
        return self.get_project_dir() / "Package" / "Translated"

    def get_archive_settings(self) -> Dict[str, Dict[str, Any]]:
        """Return manifest-backed archive settings keyed by archive filename."""
        raw_settings = self._manifest_data.get("ArchiveSettings", {})
        if not isinstance(raw_settings, dict):
            return {}
        return deepcopy(raw_settings)

    def set_archive_settings(self, settings: Dict[str, Dict[str, Any]]) -> None:
        """Replace the archive settings mapping."""
        self._manifest_data["ArchiveSettings"] = deepcopy(settings)
        self._mark_dirty()

    def get_archive_setting(self, archive_name: str) -> Dict[str, Any]:
        """Return stored settings for *archive_name*, or an empty dict."""
        return deepcopy(self.get_archive_settings().get(str(archive_name), {}))

    def set_archive_setting(self, archive_name: str, settings: Dict[str, Any]) -> None:
        """Store manifest-backed settings for one archive."""
        archive_settings = self.get_archive_settings()
        archive_settings[str(archive_name)] = deepcopy(settings)
        self._manifest_data["ArchiveSettings"] = archive_settings
        self._mark_dirty()

    def get_archive_name_for_rel_path(self, rel_path: str) -> str:
        """Return the archive filename prefix for *rel_path*, if any."""
        parts = Path(rel_path).parts
        if not parts:
            return ""

        archive_name = parts[0]
        if archive_name in self.get_archive_settings():
            return archive_name
        if archive_name.lower().endswith(".xp3"):
            return archive_name
        return ""
    
    def get_patch_dir(self) -> Path:
        """Get the legacy Patch/ root for backward-compatible callers."""
        return self.get_project_dir() / "Patch"

    def has_active_translated_branch(self) -> bool:
        """Return whether the project currently has an active translated branch."""
        translated_dir = self.get_translated_dir()
        patch_dir = self.get_patch_translated_dir()
        if translated_dir.exists() and any(translated_dir.iterdir()):
            return True
        if patch_dir.exists() and any(patch_dir.iterdir()):
            return True

        files_state = self._get_editor_state_files(create=False)
        for state in files_state.values():
            if not isinstance(state, dict):
                continue
            if state.get("translated_path") or state.get("patch_translated_path"):
                return True
        return False

    def _get_editor_state_backups(self, *, create: bool = False) -> List[Dict[str, Any]]:
        """Return the top-level ``EditorState.backups`` list."""
        editor_state = self._manifest_data.get("EditorState")
        if not isinstance(editor_state, dict):
            if not create:
                return []
            editor_state = {}
            self._manifest_data["EditorState"] = editor_state

        backups = editor_state.get("backups")
        if not isinstance(backups, list):
            if not create:
                return []
            backups = []
            editor_state["backups"] = backups
        return backups

    def _capture_active_translated_editor_state(self) -> Dict[str, Dict[str, Any]]:
        """Capture active translated-branch metadata for backup/restore."""
        files_state = self._get_editor_state_files(create=False)
        snapshot: Dict[str, Dict[str, Any]] = {}
        for rel_path, state in files_state.items():
            if not isinstance(state, dict):
                continue
            record: Dict[str, Any] = {}
            for key in ("saved_at", "translated_path", "patch_translated_path", "history"):
                value = state.get(key)
                if value:
                    record[key] = deepcopy(value)
            if record:
                snapshot[rel_path] = record
        return snapshot

    def _clear_active_translated_editor_state(self) -> bool:
        """Remove active translated-branch metadata while preserving unrelated editor state."""
        files_state = self._get_editor_state_files(create=False)
        changed = False
        for rel_path in list(files_state):
            state = files_state.get(rel_path)
            if not isinstance(state, dict):
                continue
            for key in ("saved_at", "translated_path", "patch_translated_path", "history"):
                if key in state:
                    del state[key]
                    changed = True
            if not state:
                del files_state[rel_path]
        return changed

    def _restore_active_translated_editor_state(
        self,
        snapshot: Dict[str, Dict[str, Any]],
    ) -> bool:
        """Restore active translated-branch metadata from a backup snapshot."""
        if not snapshot:
            return False

        files_state = self._get_editor_state_files(create=True)
        changed = False
        for rel_path, backup_state in snapshot.items():
            existing = files_state.get(rel_path, {})
            if not isinstance(existing, dict):
                existing = {}
            existing.update(deepcopy(backup_state))
            files_state[rel_path] = existing
            changed = True
        return changed

    def _remove_patch_translated_artifacts_for_entry(self, entry: FileDirEntry) -> bool:
        """Delete active Patch/Translated artifacts for one file entry."""
        changed = False
        patch_base = self.get_patch_translated_file_path(entry)
        for candidate in (patch_base.with_name(patch_base.name + ".patch"), patch_base):
            try:
                if candidate.exists():
                    candidate.unlink()
                    changed = True
            except OSError:
                logger.debug("Failed to remove translated patch artifact: %s", candidate)

        parent = patch_base.parent
        patch_root = self.get_patch_translated_dir()
        while parent != patch_root and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
        return changed

    def backup_active_translated_branch(self, *, reason: str = "step9_export") -> Dict[str, Any]:
        """Rename the active translated branch into Backups/ and snapshot its metadata."""
        snapshot = self._capture_active_translated_editor_state()
        translated_dir = self.get_translated_dir()
        patch_dir = self.get_patch_translated_dir()
        has_translated = translated_dir.exists() and any(translated_dir.iterdir())
        has_patch = patch_dir.exists() and any(patch_dir.iterdir())
        if not has_translated and not has_patch and not snapshot:
            return {"created": False}

        backup_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        backup_root = self.get_backup_dir()
        translated_backup_rel: Optional[str] = None
        patch_backup_rel: Optional[str] = None

        if has_translated:
            translated_backup = backup_root / "Translated" / backup_id
            translated_backup.parent.mkdir(parents=True, exist_ok=True)
            translated_dir.rename(translated_backup)
            translated_backup_rel = self._relativize_project_path(translated_backup)

        if has_patch:
            patch_backup = backup_root / "Patch" / "Translated" / backup_id
            patch_backup.parent.mkdir(parents=True, exist_ok=True)
            patch_dir.rename(patch_backup)
            patch_backup_rel = self._relativize_project_path(patch_backup)

        backup_record: Dict[str, Any] = {
            "id": backup_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "reason": reason,
        }
        if translated_backup_rel:
            backup_record["translated_dir"] = translated_backup_rel
        if patch_backup_rel:
            backup_record["patch_translated_dir"] = patch_backup_rel
        if snapshot:
            backup_record["files"] = snapshot

        backups = self._get_editor_state_backups(create=True)
        backups.append(backup_record)
        changed = self._clear_active_translated_editor_state()
        if backups or changed:
            self._mark_dirty()
        return {
            "created": True,
            "backup": backup_record,
        }

    def discard_active_translated_branch(self) -> Dict[str, Any]:
        """Delete the active translated branch and clear its editor metadata."""
        removed = False
        for path in (self.get_translated_dir(), self.get_patch_translated_dir()):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                removed = True

        metadata_cleared = self._clear_active_translated_editor_state()
        if removed or metadata_cleared:
            self._mark_dirty()
        return {
            "removed": removed or metadata_cleared,
        }

    def restore_translated_branch_backup(
        self,
        backup_id: str,
        *,
        backup_current: bool = False,
    ) -> Dict[str, Any]:
        """Restore one saved translated-branch backup into the active branch."""
        backups = self._get_editor_state_backups(create=True)
        backup_index = next(
            (index for index, item in enumerate(backups) if item.get("id") == backup_id),
            None,
        )
        if backup_index is None:
            raise ValueError(f"Unknown translated backup id: {backup_id}")

        current_backup: Optional[Dict[str, Any]] = None
        if self.has_active_translated_branch():
            if backup_current:
                current_backup = self.backup_active_translated_branch(
                    reason=f"restore:{backup_id}",
                )
            else:
                self.discard_active_translated_branch()

        backup_record = backups.pop(backup_index)
        translated_backup = self._resolve_project_relative_path(backup_record.get("translated_dir"))
        patch_backup = self._resolve_project_relative_path(backup_record.get("patch_translated_dir"))

        if translated_backup is not None and translated_backup.exists():
            translated_target = self.get_translated_dir()
            translated_target.parent.mkdir(parents=True, exist_ok=True)
            translated_backup.rename(translated_target)

        if patch_backup is not None and patch_backup.exists():
            patch_target = self.get_patch_translated_dir()
            patch_target.parent.mkdir(parents=True, exist_ok=True)
            patch_backup.rename(patch_target)

        restored = self._restore_active_translated_editor_state(
            backup_record.get("files", {}),
        )
        if restored or translated_backup is not None or patch_backup is not None:
            self._mark_dirty()

        return {
            "restored": True,
            "backup": backup_record,
            "current_backup": current_backup,
        }
    
    def copy_originals_to_project(
        self,
        source_paths: Optional[Dict[str, Path]] = None,
        force: bool = False,
        move_files: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], bool]] = None,
        source_text_cache: Optional[Dict[str, str]] = None,
        source_text_encodings: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Copy source files into the project's Original/ directory.

        ``source_root`` is now a display-only folder name, so callers must
        provide the actual absolute paths via *source_paths*.

        Args:
            source_paths: Mapping of ``rel_path`` → absolute source ``Path``.
                If *None*, falls back to looking in ``step_state.Input.data.files``.
            force: If True, overwrite existing copies.
            move_files: If True, remove the original file after staging.
            progress_callback: Optional callback receiving staging progress.
                Return ``False`` to cancel the operation.
            source_text_cache: Optional rel-path text cache populated while bytes
                are staged so later manifest sync can reuse the same read.
            source_text_encodings: Optional rel-path encoding lookup used when
                populating ``source_text_cache``.

        Returns:
            Dict mapping original paths to copied paths.
        """
        explicit_source_paths = source_paths is not None
        filedir = self.get_filedir()

        # Build source_paths from step_state.Input if not provided.
        if source_paths is None:
            source_paths = self._build_source_paths_from_input()

        if not source_paths:
            logger.warning("No source paths available to copy")
            return {}

        if explicit_source_paths:
            rel_paths = list(source_paths.keys())
        elif filedir:
            rel_paths = [entry.rel_path for entry in filedir if entry.rel_path in source_paths]
        else:
            rel_paths = []

        # Allow callers to stage explicit rel_path mappings before filedir is
        # updated, which is required when parser-backed extraction depends on the
        # staged Original/ project context.
        if not rel_paths:
            rel_paths = list(source_paths.keys())

        original_dir = self.get_original_dir()
        original_dir.mkdir(parents=True, exist_ok=True)

        copied_files: Dict[str, str] = {}
        total_files = len(rel_paths)
        total_bytes = 0
        for rel_path in rel_paths:
            abs_source = source_paths.get(rel_path)
            if abs_source is None or not abs_source.exists():
                continue
            try:
                total_bytes += abs_source.stat().st_size
            except OSError:
                continue

        bytes_completed = 0

        for index, rel_path in enumerate(rel_paths, start=1):
            abs_source = source_paths.get(rel_path)
            if abs_source is None or not abs_source.exists():
                logger.warning("Source file not found for rel_path=%s", rel_path)
                continue

            dest_path = original_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            file_size = 0
            try:
                file_size = abs_source.stat().st_size
            except OSError:
                file_size = 0

            if dest_path.exists() and not force:
                logger.debug("Original already exists: %s", dest_path)
                copied_files[str(abs_source)] = str(dest_path)
                bytes_completed += file_size
                if progress_callback is not None:
                    should_continue = progress_callback({
                        "phase": "stage-originals",
                        "rel_path": rel_path,
                        "current_file": index,
                        "total_files": total_files,
                        "file_bytes": file_size,
                        "file_total_bytes": file_size,
                        "total_bytes": bytes_completed,
                        "total_bytes_max": total_bytes,
                    })
                    if should_continue is False:
                        break
                continue

            try:
                staged = self._stage_file_with_progress(
                    abs_source,
                    dest_path,
                    delete_source=move_files,
                    progress_callback=progress_callback,
                    source_text_cache=source_text_cache,
                    source_text_encoding=(source_text_encodings or {}).get(rel_path),
                    rel_path=rel_path,
                    current_file=index,
                    total_files=total_files,
                    total_bytes_before=bytes_completed,
                    total_bytes_max=total_bytes,
                )
                if not staged:
                    break
                copied_files[str(abs_source)] = str(dest_path)
                bytes_completed += file_size
                logger.info("Copied original: %s -> %s", abs_source.name, dest_path)
            except Exception as e:
                logger.error("Failed to copy %s: %s", abs_source, e)

        return copied_files

    def _stage_file_with_progress(
        self,
        source_path: Path,
        dest_path: Path,
        *,
        delete_source: bool,
        progress_callback: Optional[Callable[[Dict[str, Any]], bool]],
        source_text_cache: Optional[Dict[str, str]],
        source_text_encoding: Optional[str],
        rel_path: str,
        current_file: int,
        total_files: int,
        total_bytes_before: int,
        total_bytes_max: int,
    ) -> bool:
        """Stage one file into Original/ while optionally reporting byte progress."""
        import shutil

        file_total_bytes = 0
        try:
            file_total_bytes = source_path.stat().st_size
        except OSError:
            file_total_bytes = 0

        bytes_written = 0
        captured_bytes = bytearray() if source_text_cache is not None else None
        if progress_callback is not None:
            should_continue = progress_callback({
                "phase": "stage-originals",
                "rel_path": rel_path,
                "current_file": current_file,
                "total_files": total_files,
                "file_bytes": 0,
                "file_total_bytes": file_total_bytes,
                "total_bytes": total_bytes_before,
                "total_bytes_max": total_bytes_max,
            })
            if should_continue is False:
                return False

        with source_path.open("rb") as src_handle, dest_path.open("wb") as dst_handle:
            while True:
                chunk = src_handle.read(1024 * 1024)
                if not chunk:
                    break
                dst_handle.write(chunk)
                if captured_bytes is not None:
                    captured_bytes.extend(chunk)
                bytes_written += len(chunk)
                if progress_callback is not None:
                    should_continue = progress_callback({
                        "phase": "stage-originals",
                        "rel_path": rel_path,
                        "current_file": current_file,
                        "total_files": total_files,
                        "file_bytes": bytes_written,
                        "file_total_bytes": file_total_bytes,
                        "total_bytes": total_bytes_before + bytes_written,
                        "total_bytes_max": total_bytes_max,
                    })
                    if should_continue is False:
                        dst_handle.close()
                        try:
                            dest_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        return False

        if captured_bytes is not None:
            try:
                source_text_cache[rel_path] = captured_bytes.decode(
                    source_text_encoding or "utf-8",
                    errors="ignore",
                )
            except Exception:
                pass

        shutil.copystat(source_path, dest_path)
        if delete_source:
            source_path.unlink(missing_ok=True)
        return True

    def _build_source_paths_from_input(self) -> Dict[str, Path]:
        """Build rel_path → absolute-source-path map from Input step state.

        Falls back to matching filedir rel_paths against Input.data.files[].path.
        Matching priority: rel_path suffix match → filename (only when unique).
        """
        result: Dict[str, Path] = {}
        ss = self._manifest_data.get("step_state", {})
        input_data = ss.get("Input", {}).get("data", {})
        files_list = input_data.get("files", [])

        filedir = self.get_filedir()

        # Collect all absolute paths from Input step
        abs_paths: List[Path] = []
        for f in files_list:
            raw = f.get("path", "")
            if raw:
                abs_paths.append(Path(raw))

        # Build filename → list of absolute paths (detect ambiguity)
        from collections import defaultdict
        name_to_paths: Dict[str, List[Path]] = defaultdict(list)
        for p in abs_paths:
            name_to_paths[p.name].append(p)

        for entry in filedir:
            rel = entry.rel_path
            rel_parts = Path(rel).parts  # e.g. ("cg", "coliseum_mob.txt")

            # 1) Suffix match: find an abs path whose tail matches rel_path
            matched = None
            for p in abs_paths:
                p_parts = p.parts
                if (len(p_parts) >= len(rel_parts)
                        and p_parts[-len(rel_parts):] == rel_parts):
                    matched = p
                    break

            if matched is not None:
                result[rel] = matched
                continue

            # 2) Filename-only match, but only when unambiguous
            fname = Path(rel).name
            candidates = name_to_paths.get(fname, [])
            if len(candidates) == 1:
                result[rel] = candidates[0]

        return result
    
    def get_original_file_path(self, entry: FileDirEntry) -> Path:
        """Get the path to the copied original file for a filedir entry.
        
        TASK 35.2: Returns the path in Original/ directory.
        
        Args:
            entry: FileDirEntry to get original path for.
            
        Returns:
            Path to the original file in Original/ directory.
        """
        return self.get_original_dir() / entry.rel_path

    def get_translated_file_path(self, entry: FileDirEntry) -> Path:
        """Get the path to the translated file for a filedir entry."""
        return self.get_translated_dir() / entry.rel_path

    def get_patch_original_file_path(self, entry: FileDirEntry) -> Path:
        """Get the path to the Patch/Original file for a filedir entry."""
        return self.get_patch_original_dir() / entry.rel_path

    def get_patch_translated_file_path(self, entry: FileDirEntry) -> Path:
        """Get the path to the Patch/Translated file for a filedir entry."""
        return self.get_patch_translated_dir() / entry.rel_path

    def get_package_original_file_path(self, entry: FileDirEntry) -> Path:
        """Get the path to the Package/Original file for a filedir entry."""
        return self.get_package_original_dir() / entry.rel_path

    def get_package_translated_file_path(self, entry: FileDirEntry) -> Path:
        """Get the path to the Package/Translated file for a filedir entry."""
        return self.get_package_translated_dir() / entry.rel_path

    def stage_package_original_archive(
        self,
        archive_path: Path,
        *,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Path]:
        """Unpack *archive_path* into Package/Original and return staged files."""
        from CherryAI.formats.KiriKiri2 import unpack_xp3_archive

        archive_path = Path(archive_path)
        package_root = self.get_package_original_dir() / archive_path.name
        extracted = unpack_xp3_archive(archive_path, package_root, settings=settings)
        return {
            f"{archive_path.name}/{path.relative_to(package_root).as_posix()}": path
            for path in extracted
        }

    def build_package_translated_archive(
        self,
        source_dir: Path,
        archive_name: str,
        *,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Pack *source_dir* into Package/Translated/*archive_name*."""
        from CherryAI.formats.KiriKiri2 import pack_xp3_archive

        archive_file = Path(archive_name)
        if archive_file.suffix.lower() != ".xp3":
            archive_file = archive_file.with_suffix(".xp3")
        output_path = self.get_package_translated_dir() / archive_file.name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return pack_xp3_archive(Path(source_dir), output_path, settings=settings)

    def get_patch_file_path(self, entry: FileDirEntry) -> Path:
        """Get the legacy translated patch path for a filedir entry."""
        return self.get_patch_translated_file_path(entry)

    def ensure_translated_file_path(self, entry: FileDirEntry) -> Path:
        """Return the Translated/ path for *entry* after creating its parent tree."""
        translated_path = self.get_translated_file_path(entry)
        translated_path.parent.mkdir(parents=True, exist_ok=True)
        return translated_path

    def ensure_patch_original_file_path(self, entry: FileDirEntry) -> Path:
        """Return the Patch/Original path for *entry* after creating its parent tree."""
        patch_path = self.get_patch_original_file_path(entry)
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        return patch_path

    def ensure_patch_translated_file_path(self, entry: FileDirEntry) -> Path:
        """Return the Patch/Translated path for *entry* after creating its parent tree."""
        patch_path = self.get_patch_translated_file_path(entry)
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        return patch_path

    def create_forward_patch_for_original(
        self,
        entry: FileDirEntry,
        updated_source_path: Path,
    ) -> Dict[str, Any]:
        """Create a hash-first Patch/Original artifact for an updated source file.

        Returns a payload with a ``decision`` of ``skip``, ``add``, ``diff``,
        or ``full_copy`` plus the artifact path chosen for that decision.
        """
        if not updated_source_path.exists():
            raise FileNotFoundError(updated_source_path)

        original_path = self.get_original_file_path(entry)
        artifact_path = self.ensure_patch_original_file_path(entry)
        diff_path = artifact_path.with_name(artifact_path.name + ".patch")

        updated_bytes = updated_source_path.read_bytes()
        updated_hash = hashlib.sha256(updated_bytes).hexdigest()

        if not original_path.exists():
            artifact_path.write_bytes(updated_bytes)
            return {
                "decision": "add",
                "artifact_path": artifact_path,
                "baseline_path": original_path,
                "candidate_path": updated_source_path,
                "baseline_hash": None,
                "candidate_hash": updated_hash,
            }

        original_bytes = original_path.read_bytes()
        original_hash = hashlib.sha256(original_bytes).hexdigest()
        if original_hash == updated_hash:
            return {
                "decision": "skip",
                "artifact_path": None,
                "baseline_path": original_path,
                "candidate_path": updated_source_path,
                "baseline_hash": original_hash,
                "candidate_hash": updated_hash,
            }

        encoding = entry.encoding or "utf-8"
        try:
            original_text = original_bytes.decode(encoding)
            updated_text = updated_bytes.decode(encoding)
        except UnicodeDecodeError:
            artifact_path.write_bytes(updated_bytes)
            return {
                "decision": "full_copy",
                "artifact_path": artifact_path,
                "baseline_path": original_path,
                "candidate_path": updated_source_path,
                "baseline_hash": original_hash,
                "candidate_hash": updated_hash,
            }

        diff_text = "\n".join(
            difflib.unified_diff(
                original_text.splitlines(),
                updated_text.splitlines(),
                fromfile=f"Original/{entry.rel_path}",
                tofile=f"Patch/Original/{entry.rel_path}",
                lineterm="",
            )
        )
        if not diff_text:
            return {
                "decision": "skip",
                "artifact_path": None,
                "baseline_path": original_path,
                "candidate_path": updated_source_path,
                "baseline_hash": original_hash,
                "candidate_hash": updated_hash,
            }

        diff_path.write_text(diff_text, encoding="utf-8", newline="")
        return {
            "decision": "diff",
            "artifact_path": diff_path,
            "baseline_path": original_path,
            "candidate_path": updated_source_path,
            "baseline_hash": original_hash,
            "candidate_hash": updated_hash,
        }

    def capture_reverse_patch_for_translated(
        self,
        entry: FileDirEntry,
        new_text: str,
    ) -> Dict[str, Any]:
        """Capture rollback material in Patch/Translated before an overwrite.

        Returns a payload with a ``decision`` of ``missing``, ``skip``,
        ``diff``, or ``full_copy`` plus the chosen artifact path.
        """
        translated_path = self.get_translated_file_path(entry)
        if not translated_path.exists():
            return {
                "decision": "missing",
                "artifact_path": None,
                "translated_path": translated_path,
            }

        current_bytes = translated_path.read_bytes()
        current_hash = hashlib.sha256(current_bytes).hexdigest()
        new_hash = hashlib.sha256(new_text.encode(entry.encoding or "utf-8")).hexdigest()
        if current_hash == new_hash:
            return {
                "decision": "skip",
                "artifact_path": None,
                "translated_path": translated_path,
                "previous_hash": current_hash,
                "new_hash": new_hash,
            }

        artifact_path = self.ensure_patch_translated_file_path(entry)
        diff_path = artifact_path.with_name(artifact_path.name + ".patch")
        encoding = entry.encoding or "utf-8"
        try:
            current_text = current_bytes.decode(encoding)
        except UnicodeDecodeError:
            artifact_path.write_bytes(current_bytes)
            return {
                "decision": "full_copy",
                "artifact_path": artifact_path,
                "translated_path": translated_path,
                "previous_hash": current_hash,
                "new_hash": new_hash,
            }

        diff_text = "\n".join(
            difflib.unified_diff(
                new_text.splitlines(),
                current_text.splitlines(),
                fromfile=f"Translated/{entry.rel_path}",
                tofile=f"Patch/Translated/{entry.rel_path}",
                lineterm="",
            )
        )
        if not diff_text:
            return {
                "decision": "skip",
                "artifact_path": None,
                "translated_path": translated_path,
                "previous_hash": current_hash,
                "new_hash": new_hash,
            }

        diff_path.write_text(diff_text, encoding="utf-8", newline="")
        return {
            "decision": "diff",
            "artifact_path": diff_path,
            "translated_path": translated_path,
            "previous_hash": current_hash,
            "new_hash": new_hash,
        }

    def capture_reverse_patch_for_translated_bytes(
        self,
        entry: FileDirEntry,
        new_bytes: bytes,
    ) -> Dict[str, Any]:
        """Capture rollback material for a translated overwrite from raw bytes."""
        translated_path = self.get_translated_file_path(entry)
        if not translated_path.exists():
            return {
                "decision": "missing",
                "artifact_path": None,
                "translated_path": translated_path,
            }

        current_bytes = translated_path.read_bytes()
        current_hash = hashlib.sha256(current_bytes).hexdigest()
        new_hash = hashlib.sha256(new_bytes).hexdigest()
        if current_hash == new_hash:
            return {
                "decision": "skip",
                "artifact_path": None,
                "translated_path": translated_path,
                "previous_hash": current_hash,
                "new_hash": new_hash,
            }

        artifact_path = self.ensure_patch_translated_file_path(entry)
        diff_path = artifact_path.with_name(artifact_path.name + ".patch")
        encoding = entry.encoding or "utf-8"
        try:
            current_text = current_bytes.decode(encoding)
            new_text = new_bytes.decode(encoding)
        except UnicodeDecodeError:
            artifact_path.write_bytes(current_bytes)
            return {
                "decision": "full_copy",
                "artifact_path": artifact_path,
                "translated_path": translated_path,
                "previous_hash": current_hash,
                "new_hash": new_hash,
            }

        diff_text = "\n".join(
            difflib.unified_diff(
                new_text.splitlines(),
                current_text.splitlines(),
                fromfile=f"Translated/{entry.rel_path}",
                tofile=f"Patch/Translated/{entry.rel_path}",
                lineterm="",
            )
        )
        if not diff_text:
            return {
                "decision": "skip",
                "artifact_path": None,
                "translated_path": translated_path,
                "previous_hash": current_hash,
                "new_hash": new_hash,
            }

        diff_path.write_text(diff_text, encoding="utf-8", newline="")
        return {
            "decision": "diff",
            "artifact_path": diff_path,
            "translated_path": translated_path,
            "previous_hash": current_hash,
            "new_hash": new_hash,
        }
    
    def has_original_copies(self) -> bool:
        """Check if original files have been copied to the project.
        
        Returns:
            True if Original/ directory exists and has files.
        """
        original_dir = self.get_original_dir()
        if not original_dir.exists():
            return False
        return any(original_dir.iterdir())
    
    def build_filedir_from_files(
        self,
        file_infos: List[Dict[str, Any]],
    ) -> List[FileDirEntry]:
        """Build filedir entries from a list of file information.
        
        Args:
            file_infos: List of dicts with keys:
                - path: Path to file (absolute)
                - format: File format (txt, csv, etc.)
                - line_count: Number of lines
                - encoding: File encoding (optional, defaults to utf-8)
                
        Returns:
            List of FileDirEntry objects covering all files.
        """
        entries: List[FileDirEntry] = []
        current_idx = 0
        
        # Determine common base path for relative paths
        paths = [Path(f["path"]) for f in file_infos]
        base_path = self._find_common_base(paths) if paths else Path.cwd()
        
        for file_info in file_infos:
            file_path = Path(file_info["path"])
            line_count = file_info.get("line_count", 0)
            
            if line_count == 0:
                continue
                
            explicit_rel_path = str(file_info.get("rel_path", "")).strip()
            if explicit_rel_path:
                rel_path = Path(explicit_rel_path)
            else:
                # Calculate relative path from common base
                try:
                    rel_path = file_path.relative_to(base_path)
                except ValueError:
                    # If can't make relative, use just filename
                    rel_path = Path(file_path.name)
            
            # TASK 38: v3.2 - no source_hint, rel_path is relative to source_root
            entry = FileDirEntry(
                first_idx=current_idx,
                last_idx=current_idx + line_count - 1,
                format=file_info.get("format", "txt"),
                rel_path=str(rel_path),
                encoding=file_info.get("encoding", "utf-8"),
                type=file_info.get("type", ""),
            )
            entries.append(entry)
            current_idx += line_count
        
        return entries
    
    def _find_common_base(self, paths: List[Path]) -> Path:
        """Find the common base directory for a list of paths.
        
        Args:
            paths: List of file paths.
            
        Returns:
            Common parent directory.
        """
        if not paths:
            return Path.cwd()
        
        if len(paths) == 1:
            return paths[0].parent
        
        # Get all parts for each path
        parts_list = [list(p.resolve().parts) for p in paths]
        
        # Find common prefix
        common_parts: List[str] = []
        for parts in zip(*parts_list):
            if len(set(parts)) == 1:
                common_parts.append(parts[0])
            else:
                break
        
        if not common_parts:
            return Path.cwd()
        
        return Path(*common_parts)

    # ======================== Non-Destructive File Addition ======================== #

    def add_files(
        self,
        new_file_infos: List[Dict[str, Any]],
        new_lines_by_rel: Dict[str, List[Any]],
    ) -> int:
        """Add new files to an existing manifest without destroying existing data.

        New files are merged into the sorted filedir list and all idx values
        (both existing and new) are recomputed to maintain a contiguous,
        sorted global index.  Existing line entries retain all their fields
        (tl, prepro, postpro, tags, etc.) — only their ``idx`` is updated.

        Args:
            new_file_infos: List of dicts with keys:
                - rel_path: str — relative path (same base as existing filedir)
                - format: str — file format id
                - line_count: int — number of lines
                - encoding: str (optional, default utf-8)
                - type: str (optional, default "")
                - lines: List[str] — the orig text of each line
            new_lines_by_rel: Mapping of rel_path → list of orig line strings
                or prebuilt manifest line dicts for the new files.

        Returns:
            Number of new files added.

        Raises:
            ValueError: If a file with the same rel_path already exists.
        """
        existing_filedir = self.get_filedir()
        existing_lines = self._manifest_data.get("lines", [])

        # Build lookup of existing rel_paths
        existing_paths = {e.rel_path for e in existing_filedir}

        # Validate no duplicates
        for info in new_file_infos:
            rel = info["rel_path"]
            if rel in existing_paths:
                raise ValueError(f"File already exists in manifest: {rel}")

        # Build new FileDirEntry objects (temporary idx — will be recomputed)
        new_entries: List[FileDirEntry] = []
        for info in new_file_infos:
            entry = FileDirEntry(
                first_idx=0,
                last_idx=info["line_count"] - 1,
                format=info.get("format", "txt"),
                rel_path=info["rel_path"],
                encoding=info.get("encoding", "utf-8"),
                type=info.get("type", ""),
            )
            new_entries.append(entry)

        # Build a combined list: (rel_path, entry_or_new, is_new)
        # Sort by rel_path to maintain consistent alphabetical ordering
        combined: List[tuple] = []
        for entry in existing_filedir:
            combined.append((entry.rel_path, entry, False))
        for entry in new_entries:
            combined.append((entry.rel_path, entry, True))
        combined.sort(key=lambda x: x[0].lower())

        # Build mapping from old_idx → existing line dict for existing entries
        old_lines_by_idx: Dict[int, Dict[str, Any]] = {}
        for line in existing_lines:
            old_lines_by_idx[line.get("idx", -1)] = line

        # Recompute all indices and build final lines + filedir
        final_lines: List[Dict[str, Any]] = []
        final_filedir: List[FileDirEntry] = []
        current_idx = 0

        for rel_path, entry, is_new in combined:
            first_idx = current_idx

            if is_new:
                # Insert new lines
                new_orig_lines = new_lines_by_rel.get(rel_path, [])
                for raw_line in new_orig_lines:
                    if isinstance(raw_line, dict):
                        line_data = dict(raw_line)
                        line_data["idx"] = current_idx
                    else:
                        line_data = {
                            "idx": current_idx,
                            "orig": raw_line,
                        }
                    final_lines.append(canonicalize_line_dict(line_data))
                    current_idx += 1
            else:
                # Preserve existing lines with all their fields, just update idx
                old_first = entry.first_idx
                old_last = entry.last_idx
                for old_idx in range(old_first, old_last + 1):
                    line_data = old_lines_by_idx.get(old_idx)
                    if line_data is not None:
                        line_copy = dict(line_data)
                        line_copy["idx"] = current_idx
                        final_lines.append(line_copy)
                    else:
                        # Shouldn't happen, but create a placeholder
                        final_lines.append({"idx": current_idx, "orig": ""})
                    current_idx += 1

            last_idx = current_idx - 1

            final_entry = FileDirEntry(
                first_idx=first_idx,
                last_idx=last_idx,
                format=entry.format,
                rel_path=entry.rel_path,
                encoding=entry.encoding,
                type=entry.type,
            )
            final_filedir.append(final_entry)

        # Commit to manifest
        self._manifest_data["lines"] = final_lines
        self.set_filedir(final_filedir)
        self._mark_dirty()

        added = len(new_file_infos)
        logger.info(
            "Added %d new file(s) to manifest, total %d files, %d lines",
            added, len(final_filedir), len(final_lines),
        )
        return added

    # ========================== Integration with mainhelper Manifest ========================== #
    
    def import_from_mainhelper_manifest(self, manifest: "Manifest") -> None:
        """Import data from a mainhelper.py Manifest into this project manifest.
        
        This bridges the processing manifest (mainhelper.Manifest) with the
        project manifest (ManifestManager). Called after processing to persist
        line data, operations, and mappings.
        
        Args:
            manifest: mainhelper.Manifest instance with processing results
        """
        from .mainhelper import Manifest as MainhelperManifest
        
        if not isinstance(manifest, MainhelperManifest):
            logger.warning("Expected mainhelper.Manifest, got %s", type(manifest))
            return
        
        # Import lines array
        if manifest.lines:
            lines_data = [line.to_dict() for line in manifest.lines]
            self._manifest_data["lines"] = lines_data
        
        # Import operations
        if manifest.operations:
            ops_data = [op.__dict__ for op in manifest.operations]
            self._manifest_data["operations"] = ops_data
        
        # Import mappings
        if manifest.mappings:
            self._manifest_data["mappings"] = manifest.mappings
        
        # Import metadata (but don't overwrite project info)
        if manifest.metadata:
            # Store processing metadata separately
            self._manifest_data.setdefault("processing_metadata", {})
            self._manifest_data["processing_metadata"].update(manifest.metadata)
        
        # Track origin file
        if manifest.origin_file:
            if "source_files" not in self._manifest_data:
                self._manifest_data["source_files"] = []
            if manifest.origin_file not in self._manifest_data["source_files"]:
                self._manifest_data["source_files"].append(manifest.origin_file)
        
        self._mark_dirty()
        logger.info("Imported %d lines from mainhelper manifest", len(manifest.lines))
    
    def export_to_mainhelper_manifest(self) -> "Manifest":
        """Export data to a mainhelper.py Manifest for processing.
        
        Creates a new Manifest instance from the project manifest data,
        suitable for use with Processor.
        
        Returns:
            mainhelper.Manifest instance ready for processing
        """
        from .mainhelper import Manifest as MainhelperManifest, LineEntry, Operation
        
        # Create new manifest
        manifest = MainhelperManifest(
            summary=self._manifest_data.get("summary", ""),
            metadata=self._manifest_data.get("processing_metadata", {}),
            operations=[],
            mappings=self._manifest_data.get("mappings", {}),
        )
        
        # Import operations
        for op_data in self._manifest_data.get("operations", []):
            manifest.operations.append(Operation(**op_data))
        
        # Import lines
        for line_data in self._manifest_data.get("lines", []):
            entry = LineEntry.from_dict(line_data)
            manifest.lines.append(entry)
        
        # Set origin file
        source_files = self._manifest_data.get("source_files", [])
        if source_files:
            manifest.origin_file = source_files[0]
        
        return manifest
    
    # ========================== Settings Access (TASK 21.3) ========================== #
    
    def get_request_options(self) -> Dict[str, Any]:
        """Get request options for API client.
        
        Returns settings in format expected by api_client functions:
        - Model: Model name/identifier
        - Temperature: Sampling temperature
        - LinesPerChunk: Lines per translation chunk
        - RetryStrategy: How to handle failures
        - MaxRetries: Maximum retry attempts
        - EnableRequestCaching: Cache responses
        - LineByLineMode: Translate line by line
        - Thinking: Enable thinking mode
        - ThinkingBudget: Token budget for thinking
        """
        return deepcopy(self._manifest_data.get("RequestOptions", {
            "Model": "",
            "Temperature": 0.2,
            "LinesPerChunk": 30,
            "RetryStrategy": "Batch",
            "MaxRetries": 3,
            "EnableRequestCaching": True,
            "LineByLineMode": False,
            "Thinking": False,
            "ThinkingBudget": 1000,
        }))
    
    def set_request_options(self, options: Dict[str, Any]) -> None:
        """Set request options."""
        self._manifest_data["RequestOptions"] = options
        self._mark_dirty()
    
    def get_preprocessing_options(self) -> Dict[str, Any]:
        """Get preprocessing options for preprocess step.
        
        Returns flat dict of preprocessing settings:
        - Deduplication: Enable deduplication
        - DeduplicationThreshold: Similarity threshold
        - EllipsisCompression: Compress ellipsis
        - SymbolConversion: Convert symbols
        - SpeakerNameReplacement: Replace speaker names
        - CodeSpacingRules: Apply code spacing
        - ProtectCodePatterns: Patterns to protect
        - CustomPlaceholders: Custom placeholder patterns
        - AnchorRemoval: Anchors to remove
        """
        return {
            "Deduplication": self._manifest_data.get("Deduplication", True),
            "DeduplicationThreshold": self._manifest_data.get("DeduplicationThreshold", 1),
            "EllipsisCompression": self._manifest_data.get("EllipsisCompression", True),
            "SymbolConversion": self._manifest_data.get("SymbolConversion", True),
            "SpeakerNameReplacement": self._manifest_data.get("SpeakerNameReplacement", False),
            "CodeSpacingRules": self._manifest_data.get("CodeSpacingRules", True),
            "ProtectCodePatterns": self._manifest_data.get("ProtectCodePatterns", []),
            "CustomPlaceholders": self._manifest_data.get("CustomPlaceholders", []),
            "AnchorRemoval": self._manifest_data.get("AnchorRemoval", []),
        }
    
    def set_preprocessing_options(self, options: Dict[str, Any]) -> None:
        """Set preprocessing options."""
        for key, value in options.items():
            if key in ("Deduplication", "DeduplicationThreshold", "EllipsisCompression",
                      "SymbolConversion", "SpeakerNameReplacement", "CodeSpacingRules",
                      "ProtectCodePatterns", "CustomPlaceholders", "AnchorRemoval"):
                self._manifest_data[key] = value
        self._mark_dirty()
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get validation rules for QA step.
        
        Returns settings for translation validation:
        - PlaceholderPreservation: Check placeholder preservation
        - AnchorPreservation: Check anchor preservation
        - SourceLanguageDetection: Detect remaining source-language content
        - SpeakerFormat: Validate speaker format
        - QuoteBalance: Check quote balance
        - EmptyTranslation: Flag empty translations
        """
        rules = deepcopy(self._manifest_data.get("ValidationRules", {
            "PlaceholderPreservation": True,
            "AnchorPreservation": True,
            "SourceLanguageDetection": True,
            "SpeakerFormat": True,
            "QuoteBalance": True,
            "EmptyTranslation": True,
        }))
        if (
            "SourceLanguageDetection" not in rules
            and "JapaneseCharacterDetection" in rules
        ):
            rules["SourceLanguageDetection"] = rules["JapaneseCharacterDetection"]
            self._manifest_data.setdefault("ValidationRules", {})["SourceLanguageDetection"] = rules["SourceLanguageDetection"]
            self._manifest_data["ValidationRules"].pop("JapaneseCharacterDetection", None)
            self._mark_dirty()
        return rules
    
    def set_validation_rules(self, rules: Dict[str, Any]) -> None:
        """Set validation rules."""
        rules = deepcopy(rules)
        if "SourceLanguageDetection" not in rules and "JapaneseCharacterDetection" in rules:
            rules["SourceLanguageDetection"] = rules["JapaneseCharacterDetection"]
        rules.pop("JapaneseCharacterDetection", None)
        self._manifest_data["ValidationRules"] = rules
        self._mark_dirty()
    
    # ========================== Character/Word Validation (TASK 36.1) ========================== #
    
    def get_character_whitelist(self) -> str:
        """Get the character whitelist string.
        
        TASK 36.1: Returns allowed characters. Empty string means all allowed.
        
        Returns:
            String of allowed characters.
        """
        return self._manifest_data.get("CharacterWhitelist", "")
    
    def set_character_whitelist(self, whitelist: str) -> None:
        """Set the character whitelist string.
        
        TASK 36.1: Set allowed characters for validation.
        
        Args:
            whitelist: String of allowed characters. Empty = all allowed.
        """
        self._manifest_data["CharacterWhitelist"] = whitelist
        self._mark_dirty()
    
    def get_character_blacklist(self) -> str:
        """Get the character blacklist string.
        
        TASK 36.1: Returns forbidden characters.
        
        Returns:
            String of forbidden characters.
        """
        return self._manifest_data.get("CharacterBlacklist", "")
    
    def set_character_blacklist(self, blacklist: str) -> None:
        """Set the character blacklist string.
        
        TASK 36.1: Set forbidden characters for validation.
        
        Args:
            blacklist: String of forbidden characters.
        """
        self._manifest_data["CharacterBlacklist"] = blacklist
        self._mark_dirty()
    
    def get_word_blacklist(self) -> List[str]:
        """Get the word blacklist.
        
        TASK 36.1: Returns forbidden words/phrases.
        Case-insensitive, whole word matching.
        
        Returns:
            List of forbidden words/phrases.
        """
        return deepcopy(self._manifest_data.get("WordBlacklist", []))
    
    def set_word_blacklist(self, blacklist: List[str]) -> None:
        """Set the word blacklist.
        
        TASK 36.1: Set forbidden words/phrases for validation.
        
        Args:
            blacklist: List of forbidden words/phrases.
        """
        self._manifest_data["WordBlacklist"] = blacklist
        self._mark_dirty()
    
    def add_word_to_blacklist(self, word: str) -> None:
        """Add a word to the blacklist.
        
        TASK 36.1: Add a single word to the forbidden list.
        
        Args:
            word: Word to blacklist.
        """
        if "WordBlacklist" not in self._manifest_data:
            self._manifest_data["WordBlacklist"] = []
        if word and word not in self._manifest_data["WordBlacklist"]:
            self._manifest_data["WordBlacklist"].append(word)
            self._mark_dirty()
    
    def remove_word_from_blacklist(self, word: str) -> None:
        """Remove a word from the blacklist.
        
        TASK 36.1: Remove a single word from the forbidden list.
        
        Args:
            word: Word to remove.
        """
        if "WordBlacklist" in self._manifest_data:
            try:
                self._manifest_data["WordBlacklist"].remove(word)
                self._mark_dirty()
            except ValueError:
                pass  # Word not in list
    
    def get_autofix_map(self) -> Dict[str, str]:
        """Get the autofix mapping.
        
        TASK 36.1: Returns mapping from offending characters to replacements.
        
        Returns:
            Dict mapping offending chars to replacement chars.
        """
        return deepcopy(self._manifest_data.get("AutofixMap", {}))
    
    def set_autofix_map(self, autofix_map: Dict[str, str]) -> None:
        """Set the autofix mapping.
        
        TASK 36.1: Set character replacement mappings for auto-correction.
        
        Args:
            autofix_map: Dict mapping offending chars to replacement chars.
        """
        self._manifest_data["AutofixMap"] = autofix_map
        self._mark_dirty()
    
    def add_autofix_entry(self, offending: str, replacement: str) -> None:
        """Add an autofix mapping entry.
        
        TASK 36.1: Add a single character replacement mapping.
        
        Args:
            offending: Offending character to replace.
            replacement: Replacement character.
        """
        if "AutofixMap" not in self._manifest_data:
            self._manifest_data["AutofixMap"] = {}
        if offending:
            self._manifest_data["AutofixMap"][offending] = replacement
            self._mark_dirty()
    
    def remove_autofix_entry(self, offending: str) -> None:
        """Remove an autofix mapping entry.
        
        TASK 36.1: Remove a single character replacement mapping.
        
        Args:
            offending: Offending character to remove from map.
        """
        if "AutofixMap" in self._manifest_data:
            if offending in self._manifest_data["AutofixMap"]:
                del self._manifest_data["AutofixMap"][offending]
                self._mark_dirty()
    
    def get_character_validation_config(self) -> Dict[str, Any]:
        """Get full character/word validation configuration.
        
        TASK 36.1: Returns all validation lists and mappings in one call.
        
        Returns:
            Dict with CharacterWhitelist, CharacterBlacklist, WordBlacklist, AutofixMap.
        """
        return {
            "CharacterWhitelist": self.get_character_whitelist(),
            "CharacterBlacklist": self.get_character_blacklist(),
            "WordBlacklist": self.get_word_blacklist(),
            "AutofixMap": self.get_autofix_map(),
        }
    
    def set_character_validation_config(self, config: Dict[str, Any]) -> None:
        """Set full character/word validation configuration.
        
        TASK 36.1: Set all validation lists and mappings in one call.
        
        Args:
            config: Dict with CharacterWhitelist, CharacterBlacklist, WordBlacklist, AutofixMap.
        """
        if "CharacterWhitelist" in config:
            self._manifest_data["CharacterWhitelist"] = config["CharacterWhitelist"]
        if "CharacterBlacklist" in config:
            self._manifest_data["CharacterBlacklist"] = config["CharacterBlacklist"]
        if "WordBlacklist" in config:
            self._manifest_data["WordBlacklist"] = config["WordBlacklist"]
        if "AutofixMap" in config:
            self._manifest_data["AutofixMap"] = config["AutofixMap"]
        self._mark_dirty()

    def get_qa_options(self) -> Dict[str, Any]:
        """Get QA options for quality assurance step.
        
        Returns QA configuration:
        - RerunPolicy: Which lines to rerun
        - MaxSourceLanguageChars: Max allowed source-language characters or markers
        - MaxLineLength: Max line length (0 = unlimited)
        - EncodingSafetyEnabled: Enable legacy encoding compatibility checks
        - EncodingCheckEncoding: Target encoding to validate against
        """
        options = deepcopy(self._manifest_data.get("QAOptions", {
            "RerunPolicy": "FailedOnly",
            "MaxSourceLanguageChars": 4,
            "MaxLineLength": 0,
            "EncodingSafetyEnabled": False,
            "EncodingCheckEncoding": "shift_jis",
        }))
        if "MaxSourceLanguageChars" not in options and "MaxJapaneseChars" in options:
            options["MaxSourceLanguageChars"] = options["MaxJapaneseChars"]
            self._manifest_data.setdefault("QAOptions", {})["MaxSourceLanguageChars"] = options["MaxSourceLanguageChars"]
            self._manifest_data["QAOptions"].pop("MaxJapaneseChars", None)
            self._mark_dirty()
        options.setdefault("EncodingSafetyEnabled", False)
        options.setdefault("EncodingCheckEncoding", "shift_jis")
        return options
    
    def set_qa_options(self, options: Dict[str, Any]) -> None:
        """Set QA options."""
        options = deepcopy(options)
        if "MaxSourceLanguageChars" not in options and "MaxJapaneseChars" in options:
            options["MaxSourceLanguageChars"] = options["MaxJapaneseChars"]
        options.pop("MaxJapaneseChars", None)
        self._manifest_data["QAOptions"] = options
        self._mark_dirty()
    
    def get_postprocessing_options(self) -> Dict[str, Any]:
        """Get post-processing options.
        
        Returns settings for translation cleanup:
        - PlaceholderRecovery: Recover lost placeholders
        - BracketBalanceRecovery: Fix bracket balance
        - QuoteBalanceRecovery: Fix quote balance
        - RestoreCodeCharacters: Restore code characters
        - RestoreLinebreaks: Restore linebreaks
        - EnableSymbolConversion: Convert symbols back
        - FullwidthToHalfwidth: Convert fullwidth to halfwidth
        - FailureHandling: How to handle failures
        """
        return deepcopy(self._manifest_data.get("PostProcessing", {
            "PlaceholderRecovery": True,
            "BracketBalanceRecovery": True,
            "QuoteBalanceRecovery": True,
            "RestoreCodeCharacters": True,
            "RestoreLinebreaks": True,
            "EnableSymbolConversion": True,
            "FullwidthToHalfwidth": True,
            "FailureHandling": "flag",
        }))
    
    def set_postprocessing_options(self, options: Dict[str, Any]) -> None:
        """Set post-processing options."""
        self._manifest_data["PostProcessing"] = options
        self._mark_dirty()
    
    def get_wordwrap_options(self) -> Dict[str, Any]:
        """Get wordwrap settings for wordwrap step.
        
        Returns wordwrap configuration:
        - Mode: Wrap mode (Custom or Simple)
        - Width: Line width in characters
        - BreakChar: Character to use for line breaks
        - MaxLines: Maximum lines per text block
        - PreventOrphans: Prevent orphan words
        - PreferPunctuationBreaks: Break at punctuation
        - SpeakerHandling: How to handle speaker names
        - IgnorePatterns: Patterns to skip wrapping
        - Typography: Typography style (Western, Japanese)
        """
        return deepcopy(self._manifest_data.get("WordwrapSettings", {
            "Mode": "Custom",
            "Width": 48,
            "BreakChar": "",
            "MaxLines": 4,
            "PrettyWrap": True,
            "PreventOrphans": True,
            "PreferPunctuationBreaks": True,
            "SpeakerHandling": "Sameline",
            "IgnorePatterns": [],
            "Typography": "Western",
            "TagConfigs": [],
            "FormatConfigs": [],
        }))
    
    def set_wordwrap_options(self, options: Dict[str, Any]) -> None:
        """Set wordwrap options."""
        self._manifest_data["WordwrapSettings"] = options
        self._mark_dirty()

    def get_wordwrap_tag_configs(self) -> List[Dict[str, Any]]:
        """Get per-tag wordwrap configuration list.

        Each entry is ``{"tag": str, "Width": int, "BreakChar": str,
        "MaxLines": int, "Mode": str, "ParserManaged": bool}``.

        Returns:
            List of tag config dicts (empty list if none defined).
        """
        ws = self._manifest_data.get("WordwrapSettings", {})
        return list(ws.get("TagConfigs", []))

    def set_wordwrap_tag_configs(self, configs: List[Dict[str, Any]]) -> None:
        """Replace the full per-tag wordwrap configuration list.

        Args:
            configs: List of tag config dicts.
        """
        ws = self._manifest_data.setdefault("WordwrapSettings", {})
        ws["TagConfigs"] = list(configs)
        self._mark_dirty()

    def get_wordwrap_format_configs(self) -> List[Dict[str, Any]]:
        """Get per-format wordwrap configuration list."""
        ws = self._manifest_data.get("WordwrapSettings", {})
        return list(ws.get("FormatConfigs", []))

    def set_wordwrap_format_configs(self, configs: List[Dict[str, Any]]) -> None:
        """Replace the full per-format wordwrap configuration list."""
        ws = self._manifest_data.setdefault("WordwrapSettings", {})
        ws["FormatConfigs"] = list(configs)
        self._mark_dirty()
    
    def get_output_options(self) -> Dict[str, Any]:
        """Get output format options.
        
        Returns output configuration:
        - Destination: Destination mode or path
        - PreserveFolderStructure: Keep folder structure
        - Format: Output format (auto-detect if empty)
        - PairMode: How to output pairs
        - Encoding: Output encoding (auto-detect if empty)
        - FileNaming: File naming convention
        - TextOption: Text output option
        - OverwriteExistingFiles: Overwrite existing
        - Backup: Backup strategy
        - BackupExtension: Backup file extension
        - ExportManifestFile: Export manifest
        - ExportProcessingLogs: Export logs
        - ExportGlossaryEntries: Export glossary
        """
        return deepcopy(self._manifest_data.get("OutputFormat", {
            "Destination": "Same as Source",
            "PreserveFolderStructure": True,
            "Format": "",
            "PairMode": "custom",
            "Encoding": "Same as Input",
            "FileNaming": "subfolder",
            "TextOption": "translated",
            "OverwriteExistingFiles": True,
            "Backup": "timestamp",
            "BackupExtension": ".bk",
            "ExportManifestFile": False,
            "ExportProcessingLogs": False,
            "ExportGlossaryEntries": False,
        }))
    
    def set_output_options(self, options: Dict[str, Any]) -> None:
        """Set output options."""
        self._manifest_data["OutputFormat"] = options
        self._mark_dirty()

    def get_output_patch_lookup_folders(self) -> Dict[str, str]:
        """Return saved lookup folders for manual parser project patches."""
        options = self.get_output_options()
        raw = options.get("PatchLookupFolders", {})
        return dict(raw) if isinstance(raw, dict) else {}

    def set_output_patch_lookup_folder(self, patch_key: str, folder: str) -> None:
        """Persist one manual parser patch lookup folder."""
        options = self.get_output_options()
        raw = options.get("PatchLookupFolders", {})
        folders = dict(raw) if isinstance(raw, dict) else {}
        if folders.get(patch_key) == folder:
            return
        folders[patch_key] = folder
        options["PatchLookupFolders"] = folders
        self.set_output_options(options)

    def get_dirty_flags(self) -> Dict[str, bool]:
        """Get pipeline dirty flags.

        Returns dict with ``process`` and ``wordwrap`` booleans indicating
        whether those pipeline stages need re-running before export.
        """
        return deepcopy(self._manifest_data.get("DirtyFlags", {
            "process": False,
            "wordwrap": False,
        }))

    def set_dirty_flag(self, flag_name: str, value: bool) -> None:
        """Set a single pipeline dirty flag.

        Args:
            flag_name: ``"process"`` or ``"wordwrap"``.
            value: True if the stage needs re-running.
        """
        flags = self._manifest_data.setdefault("DirtyFlags", {
            "process": False,
            "wordwrap": False,
        })
        flags[flag_name] = value
        self._mark_dirty()

    def get_estimation_data(self) -> Dict[str, int]:
        """Get estimation data.
        
        Returns token/line estimates:
        - InputLines: Number of input lines
        - InputTokens: Estimated input tokens
        - OutputTokens: Estimated output tokens
        """
        return {
            "InputLines": self._manifest_data.get("InputLines", 0),
            "InputTokens": self._manifest_data.get("InputTokens", 0),
            "OutputTokens": self._manifest_data.get("OutputTokens", 0),
        }
    
    def set_estimation_data(self, data: Dict[str, int]) -> None:
        """Set estimation data."""
        if "InputLines" in data:
            self._manifest_data["InputLines"] = data["InputLines"]
        if "InputTokens" in data:
            self._manifest_data["InputTokens"] = data["InputTokens"]
        if "OutputTokens" in data:
            self._manifest_data["OutputTokens"] = data["OutputTokens"]
        self._mark_dirty()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all v3.0 settings as a single dict.
        
        This is useful for passing complete settings to functions
        or for displaying all settings in a UI.
        
        Returns:
            Dict containing all processing settings grouped by category.
        """
        return {
            "project_info": deepcopy(self.get_info_metadata()),
            "preprocessing": self.get_preprocessing_options(),
            "request": self.get_request_options(),
            "validation": self.get_validation_rules(),
            "qa": self.get_qa_options(),
            "postprocessing": self.get_postprocessing_options(),
            "wordwrap": self.get_wordwrap_options(),
            "output": self.get_output_options(),
            "estimation": self.get_estimation_data(),
        }
    
    # ========================== Raw Access ========================== #
    
    def get_raw_data(self) -> Dict[str, Any]:
        """Get the raw manifest data dictionary.
        
        Use with caution - prefer specific getters.
        """
        return self._manifest_data
    
    def set_raw_data(self, data: Dict[str, Any]) -> None:
        """Set the raw manifest data dictionary.
        
        Use with caution - prefer specific setters.
        """
        self._manifest_data = data
        self._mark_dirty()


# ========================== Global Instance ========================== #

_manager: Optional[ManifestManager] = None


def get_manifest_manager() -> ManifestManager:
    """Get the global ManifestManager instance."""
    global _manager
    if _manager is None:
        _manager = ManifestManager()
    return _manager


def reset_manifest_manager() -> ManifestManager:
    """Reset and return a fresh ManifestManager instance."""
    global _manager
    if _manager is not None:
        _manager.close()
    _manager = ManifestManager()
    return _manager


def replace_manifest_manager(manager: ManifestManager) -> ManifestManager:
    """Replace the shared manifest manager instance with a loaded manager."""
    global _manager
    _manager = manager
    return _manager
