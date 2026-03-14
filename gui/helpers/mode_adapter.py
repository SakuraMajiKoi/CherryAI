"""GUI Mode Adapter for CherryAI.

Bridge between GUI preprocessing configuration and modi/ module functions.
Provides lightweight wrappers that can apply preprocessing without requiring
a full Processor instance, making modi functionality accessible to the GUI.

TASK 16.5: Integrate Modi Modules with GUI Step 4

This adapter:
- Imports functions from modi/ modules (standard_mode, protect_code, custom_placeholder)
- Exposes simple function interfaces for GUI preprocessing
- Does not require Processor or Manifest instances
- Records changes for preview display

Created: TASK 16.5 - Phase 16B Integration
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Import modi functions directly where possible
# Fall back to local implementations if imports fail

try:
    from CherryAI.modi.standard_mode import (
        compress_ellipsis_line,
        decompress_ellipsis_line,
        _build_symbol_replacements,
    )
    HAS_STANDARD_MODE = True
except ImportError:
    HAS_STANDARD_MODE = False
    logger.debug("Could not import standard_mode functions, using fallback")


# ─────────────────────────────────────────────────────────────────────────────
# Ellipsis Compression (from modi/standard_mode.py)
# ─────────────────────────────────────────────────────────────────────────────

# Pattern for ellipsis-like runs (copied from standard_mode if not available)
ELLIPSIS_PATTERN = re.compile(r"(?:\.[\s]*){3,}|…+|[\.\s]*…[\.\s]*")


def apply_ellipsis_compression(line: str) -> Tuple[str, bool]:
    """Apply ellipsis compression to a line.

    Args:
        line: Line to process.

    Returns:
        Tuple of (processed_line, was_changed).
    """
    if HAS_STANDARD_MODE:
        new_line, counts = compress_ellipsis_line(line)
        return new_line, bool(counts)
    else:
        # Fallback implementation
        original = line
        # Compress Japanese ellipsis (……… etc) to single ……
        line = re.sub(r"…{2,}", "……", line)
        # Compress Western ellipsis (.... etc) to single ...
        line = re.sub(r"\.{4,}", "...", line)
        return line, line != original


def apply_ellipsis_batch(
    lines: List[str],
) -> Tuple[List[str], int, List[int], Dict[int, List[int]]]:
    """Apply ellipsis compression to multiple lines.

    Args:
        lines: Lines to process.

    Returns:
        Tuple of (processed_lines, change_count, changed_indices,
        counts_by_line).  *counts_by_line* maps line index to the list
        of triplet counts returned by ``compress_ellipsis_line`` so that
        postprocessing can decompress back to the original length.
    """
    result: List[str] = []
    changed_count = 0
    changed_indices: List[int] = []
    counts_by_line: Dict[int, List[int]] = {}

    for idx, line in enumerate(lines):
        if HAS_STANDARD_MODE:
            new_line, counts = compress_ellipsis_line(line)
            changed = bool(counts)
        else:
            new_line, changed = apply_ellipsis_compression(line)
            counts = []
        result.append(new_line)
        if changed:
            changed_count += 1
            changed_indices.append(idx)
            if counts:
                counts_by_line[idx] = counts

    return result, changed_count, changed_indices, counts_by_line


# ─────────────────────────────────────────────────────────────────────────────
# Symbol Conversion (from modi/standard_mode.py)
# ─────────────────────────────────────────────────────────────────────────────

# Symbol conversion tables (simplified from standard_mode.py)
SYMBOL_CONVERSIONS_JA_EN: Dict[str, str] = {
    "。": ".",
    "、": ",",
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
    "（": "(",
    "）": ")",
    "「": '"',
    "」": '"',
    "『": "'",
    "』": "'",
    "【": "[",
    "】": "]",
    "〈": "<",
    "〉": ">",
    "ー": "-",
    "　": " ",  # Fullwidth space
    # Fullwidth digits
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
}


def get_symbol_table(src_lang: str = "ja", tgt_lang: str = "en") -> Dict[str, str]:
    """Get symbol conversion table for language pair.

    Args:
        src_lang: Source language code.
        tgt_lang: Target language code.

    Returns:
        Dictionary mapping source symbols to target symbols.
    """
    if HAS_STANDARD_MODE:
        try:
            return _build_symbol_replacements(src_lang, tgt_lang)
        except Exception:
            pass

    # Fallback: only ja->en supported
    if src_lang.lower() in ("ja", "japanese", "jpn"):
        if tgt_lang.lower() in ("en", "english", "eng"):
            return SYMBOL_CONVERSIONS_JA_EN
    return {}


def apply_symbol_conversion(
    line: str,
    src_lang: str = "ja",
    tgt_lang: str = "en",
    table: Optional[Dict[str, str]] = None,
) -> Tuple[str, bool]:
    """Apply symbol conversion to a line.

    Args:
        line: Line to process.
        src_lang: Source language code.
        tgt_lang: Target language code.
        table: Pre-built conversion table (optional, for efficiency).

    Returns:
        Tuple of (processed_line, was_changed).
    """
    if table is None:
        table = get_symbol_table(src_lang, tgt_lang)

    if not table:
        return line, False

    original = line
    for src, tgt in table.items():
        line = line.replace(src, tgt)

    return line, line != original


def apply_symbol_batch(
    lines: List[str],
    src_lang: str = "ja",
    tgt_lang: str = "en",
) -> Tuple[List[str], int, List[int]]:
    """Apply symbol conversion to multiple lines.

    Args:
        lines: Lines to process.
        src_lang: Source language code.
        tgt_lang: Target language code.

    Returns:
        Tuple of (processed_lines, change_count, changed_indices).
    """
    table = get_symbol_table(src_lang, tgt_lang)
    result: List[str] = []
    changed_count = 0
    changed_indices: List[int] = []

    for idx, line in enumerate(lines):
        new_line, changed = apply_symbol_conversion(line, src_lang, tgt_lang, table)
        result.append(new_line)
        if changed:
            changed_count += 1
            changed_indices.append(idx)

    return result, changed_count, changed_indices


# ─────────────────────────────────────────────────────────────────────────────
# PROTECTED Token Compression (from modi/standard_mode.py)
# ─────────────────────────────────────────────────────────────────────────────

PROT_PATTERN = re.compile(r"(__PROTECTED__)+")


def apply_prot_compression(line: str) -> Tuple[str, bool]:
    """Compress adjacent __PROTECTED__ tokens into indexed form.

    __PROTECTED____PROTECTED__ → __PROTECTED_2__

    Args:
        line: Line to process.

    Returns:
        Tuple of (processed_line, was_changed).
    """
    original = line

    def replace_prot_run(match: re.Match[str]) -> str:
        run = match.group(0)
        count = run.count("__PROTECTED__")
        if count > 1:
            return f"__PROTECTED_{count}__"
        return run

    line = PROT_PATTERN.sub(replace_prot_run, line)
    return line, line != original


def apply_prot_batch(lines: List[str]) -> Tuple[List[str], int, List[int]]:
    """Apply PROTECTED compression to multiple lines.

    Args:
        lines: Lines to process.

    Returns:
        Tuple of (processed_lines, change_count, changed_indices).
    """
    result: List[str] = []
    changed_count = 0
    changed_indices: List[int] = []

    for idx, line in enumerate(lines):
        new_line, changed = apply_prot_compression(line)
        result.append(new_line)
        if changed:
            changed_count += 1
            changed_indices.append(idx)

    return result, changed_count, changed_indices


# ─────────────────────────────────────────────────────────────────────────────
# Protect Code Patterns (from modi/protect_code.py)
# ─────────────────────────────────────────────────────────────────────────────


def apply_protect_code(
    line: str,
    patterns: List[str],
) -> Tuple[str, bool, List[str]]:
    """Apply protect code patterns to replace matches with __PROTECTED__.

    Collects all matches across all patterns first, resolves overlaps
    (leftmost wins), then replaces in right-to-left order.  The
    ``captured`` list is always in left-to-right order matching the
    ``__PROTECTED__`` token order in the result.

    Args:
        line: Line to process.
        patterns: List of regex patterns (str) or dicts with a ``pattern`` key.

    Returns:
        Tuple of (processed_line, was_changed, captured_values).
    """
    original = line
    all_matches: List[Tuple[int, int, str]] = []  # (start, end, value)

    for entry in patterns:
        # Handle both dict entries and raw strings
        if isinstance(entry, dict):
            pattern_str = entry.get("pattern", "")
        else:
            pattern_str = str(entry) if entry is not None else ""

        if not pattern_str.strip():
            continue
        try:
            compiled = re.compile(pattern_str)
            for m in compiled.finditer(line):
                val = m.group(0)
                if val:
                    all_matches.append((m.start(), m.end(), val))
        except re.error as e:
            logger.warning("Invalid protect code pattern %r: %s", pattern_str, e)

    if not all_matches:
        return line, False, []

    # Sort by position; resolve overlaps (leftmost wins)
    all_matches.sort(key=lambda x: x[0])
    filtered: List[Tuple[int, int, str]] = []
    last_end = 0
    for start, end, val in all_matches:
        if start >= last_end:
            filtered.append((start, end, val))
            last_end = end

    # captured in left-to-right order (matches __PROTECTED__ token order)
    captured = [val for _, _, val in filtered]

    # Replace from right-to-left to preserve positions
    for start, end, _val in reversed(filtered):
        line = line[:start] + "__PROTECTED__" + line[end:]

    return line, line != original, captured


def apply_protect_batch(
    lines: List[str],
    patterns: List[str],
) -> Tuple[List[str], int, List[int], Dict[int, List[str]]]:
    """Apply protect code patterns to multiple lines.

    Args:
        lines: Lines to process.
        patterns: List of regex patterns to protect.

    Returns:
        Tuple of (processed_lines, change_count, changed_indices, captured_by_line).
    """
    result: List[str] = []
    changed_count = 0
    changed_indices: List[int] = []
    captured_by_line: Dict[int, List[str]] = {}

    for idx, line in enumerate(lines):
        new_line, changed, captured = apply_protect_code(line, patterns)
        result.append(new_line)
        if changed:
            changed_count += 1
            changed_indices.append(idx)
            if captured:
                captured_by_line[idx] = captured

    return result, changed_count, changed_indices, captured_by_line


# ─────────────────────────────────────────────────────────────────────────────
# Custom Placeholder (from modi/custom_placeholder.py)
# ─────────────────────────────────────────────────────────────────────────────


def apply_custom_placeholder(
    line: str,
    pattern: str,
    token: str = "__CUST__",
    is_regex: bool = True,
) -> Tuple[str, bool, List[str]]:
    """Apply custom placeholder replacement.

    Args:
        line: Line to process.
        pattern: Pattern to match (regex or literal).
        token: Token to replace matches with.
        is_regex: Whether pattern is regex.

    Returns:
        Tuple of (processed_line, was_changed, captured_values).
    """
    original = line
    captured: List[str] = []

    if not pattern.strip():
        return line, False, captured

    token = token.strip() or "__CUST__"

    try:
        if is_regex:
            compiled = re.compile(pattern)
            matches = list(compiled.finditer(line))
            for m in reversed(matches):
                val = m.group(0)
                if val:
                    captured.insert(0, val)
                    line = line[: m.start()] + token + line[m.end() :]
        else:
            while pattern in line:
                idx = line.find(pattern)
                if idx >= 0:
                    captured.append(pattern)
                    line = line[:idx] + token + line[idx + len(pattern) :]
                else:
                    break
    except re.error as e:
        logger.warning("Invalid placeholder pattern %r: %s", pattern, e)

    return line, line != original, captured


def apply_placeholder_batch(
    lines: List[str],
    rules: List[Dict[str, Any]],
) -> Tuple[List[str], int, List[int], Dict[int, List[str]]]:
    """Apply custom placeholder rules to multiple lines.

    Args:
        lines: Lines to process.
        rules: List of placeholder rules with 'pattern', 'token', 'is_regex' keys.

    Returns:
        Tuple of (processed_lines, change_count, changed_indices, captured_by_line).
    """
    result = list(lines)
    changed_count = 0
    changed_indices: List[int] = []
    captured_by_line: Dict[int, List[str]] = {}

    for rule in rules:
        pattern = rule.get("pattern", "")
        token = rule.get("token", "__CUST__")
        is_regex = rule.get("is_regex", True)

        for idx, line in enumerate(result):
            new_line, changed, captured = apply_custom_placeholder(
                line, pattern, token, is_regex
            )
            if changed:
                result[idx] = new_line
                if idx not in changed_indices:
                    changed_indices.append(idx)
                    changed_count += 1
                captured_by_line.setdefault(idx, []).extend(captured)

    return result, changed_count, sorted(changed_indices), captured_by_line


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication (lightweight — no Processor required)
# ─────────────────────────────────────────────────────────────────────────────

# Import aggressive helpers from dedup.py when available
try:
    from CherryAI.functions.dedup import (
        aggressive_normalize_line,
        aggressive_mask_line,
        aggressive_restore_line,
        AGGR_NUM_TOKEN,
    )
    _HAS_DEDUP = True
except ImportError:
    _HAS_DEDUP = False
    AGGR_NUM_TOKEN = "<NUM>"

    def aggressive_normalize_line(line: str) -> str:  # type: ignore[misc]
        """Fallback normalizer: replace digits with <NUM>."""
        if not line:
            return ""
        s = re.sub(r"[0-9０-９]+", f" {AGGR_NUM_TOKEN} ", str(line))
        return re.sub(r"\s+", " ", s).strip()

    def aggressive_mask_line(line: str) -> Tuple[str, List[str]]:  # type: ignore[misc]
        """Fallback masker."""
        nums: List[str] = []
        def _repl(m: re.Match) -> str:
            nums.append(m.group(0))
            return AGGR_NUM_TOKEN
        s = re.sub(r"[0-9０-９]+", _repl, str(line))
        return s, nums

    def aggressive_restore_line(masked: str, numbers: List[str]) -> str:  # type: ignore[misc]
        """Fallback restorer."""
        parts = masked.split(AGGR_NUM_TOKEN)
        out: List[str] = []
        for idx_p, part in enumerate(parts):
            out.append(part)
            if idx_p < len(parts) - 1:
                if idx_p < len(numbers):
                    out.append(numbers[idx_p])
                else:
                    out.append(AGGR_NUM_TOKEN)
        return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Anchoring (anchor-relative — remove patterns only when adjacent to an
# anchor character; restore relative to that anchor in postprocessing)
# ─────────────────────────────────────────────────────────────────────────────

# Characters that can serve as anchors for safe removal and restoration.
# Includes punctuation, brackets, and quotes in both halfwidth and fullwidth.
_ANCHOR_CHARS: set[str] = set(
    list('.,!?;:()[]<>{}\'"')
    + list("。、！？；：（）「」『』【】〔〕《》〈〉［］｛｝＜＞")
    + ["\u201c", "\u201d", "\u2018", "\u2019"]  # Smart quotes
)


def _find_anchor(
    line: str,
    match_start: int,
    match_end: int,
) -> Optional[Dict[str, Any]]:
    """Find the best anchor adjacent to a match.

    Checks the character immediately before and after the match, plus
    line start (position 0) and line end (end of string).

    Returns a dict with ``anchor_type`` ("line_start", "line_end", or
    "char"), ``anchor_char`` (the character if type is "char"), and
    ``side`` ("left" = pattern is left of anchor, "right" = pattern is
    right of anchor).  Returns ``None`` if no anchor is found.
    """
    # Prefer right-side anchor first (pattern is LEFT of anchor char)
    if match_end < len(line):
        right_ch = line[match_end]
        if right_ch in _ANCHOR_CHARS:
            return {
                "anchor_type": "char",
                "anchor_char": right_ch,
                "side": "left",
            }

    # Then check left-side anchor (pattern is RIGHT of anchor char)
    if match_start > 0:
        left_ch = line[match_start - 1]
        if left_ch in _ANCHOR_CHARS:
            return {
                "anchor_type": "char",
                "anchor_char": left_ch,
                "side": "right",
            }

    # Line end
    if match_end == len(line):
        return {"anchor_type": "line_end", "anchor_char": "", "side": "left"}

    # Line start
    if match_start == 0:
        return {
            "anchor_type": "line_start",
            "anchor_char": "",
            "side": "right",
        }

    return None


def apply_anchor_removal(
    line: str,
    anchor_entries: List[Dict[str, Any]],
) -> Tuple[str, bool, List[Dict[str, Any]]]:
    """Remove anchor patterns from a line only where a valid anchor exists.

    A pattern is only removed when the character immediately before or
    after it is a recognised anchor character (punctuation, bracket,
    quote), or when the match is at line start/end.  Patterns with no
    adjacent anchor are left in the text unchanged.

    Each removed occurrence is recorded with the anchor information so
    that postprocessing can re-insert at the correct position.

    Args:
        line: Line to process.
        anchor_entries: List of anchor entry dicts with ``pattern``,
            ``action``, ``anchor_spec``, ``is_regex``.

    Returns:
        Tuple of (processed_line, was_changed, removal_records).
        Each record is a dict with keys: ``value``, ``anchor_type``,
        ``anchor_char``, ``side``.
    """
    if not anchor_entries or not line:
        return line, False, []

    # Collect all potential removals across all entries
    removals: List[Tuple[int, int, str, Dict[str, Any]]] = []

    for entry in anchor_entries:
        pattern_str = entry.get("pattern", "")
        if not pattern_str.strip():
            continue
        is_regex = entry.get("is_regex", True)
        try:
            if is_regex:
                pat = re.compile(pattern_str)
            else:
                pat = re.compile(re.escape(pattern_str))
            for m in pat.finditer(line):
                anchor_info = _find_anchor(line, m.start(), m.end())
                if anchor_info is not None:
                    removals.append(
                        (m.start(), m.end(), m.group(0), anchor_info)
                    )
        except re.error as err:
            logger.warning("Invalid anchor pattern %r: %s", pattern_str, err)

    if not removals:
        return line, False, []

    # Sort by start position, resolve overlaps (leftmost wins)
    removals.sort(key=lambda x: x[0])
    filtered: List[Tuple[int, int, str, Dict[str, Any]]] = []
    last_end = 0
    for start, end, val, info in removals:
        if start >= last_end:
            filtered.append((start, end, val, info))
            last_end = end

    # Build records in left-to-right order
    records: List[Dict[str, Any]] = []
    for _start, _end, val, info in filtered:
        records.append({
            "value": val,
            "anchor_type": info["anchor_type"],
            "anchor_char": info["anchor_char"],
            "side": info["side"],
        })

    # Remove from right to left to preserve positions
    current = line
    for start, end, _val, _info in reversed(filtered):
        current = current[:start] + current[end:]

    return current, current != line, records


def apply_anchor_batch(
    lines: List[str],
    anchor_entries: List[Dict[str, Any]],
) -> Tuple[List[str], int, List[int], Dict[int, List[Dict[str, Any]]]]:
    """Apply anchoring (removal) to multiple lines.

    Args:
        lines: Lines to process.
        anchor_entries: Anchor entry dicts.

    Returns:
        Tuple of (processed_lines, change_count, changed_indices,
        anchor_captured ``{line_idx: [removal_records]}``).
    """
    result: List[str] = []
    changed_count = 0
    changed_indices: List[int] = []
    anchor_captured: Dict[int, List[Dict[str, Any]]] = {}

    for idx, line in enumerate(lines):
        new_line, changed, records = apply_anchor_removal(line, anchor_entries)
        result.append(new_line)
        if changed:
            changed_count += 1
            changed_indices.append(idx)
            if records:
                anchor_captured[idx] = records

    return result, changed_count, changed_indices, anchor_captured


def restore_anchors_in_line(
    translated: str,
    records: List[Dict[str, Any]],
) -> str:
    """Re-insert previously removed anchor patterns into translated text.

    Uses the anchor character recorded during removal to find the
    correct insertion point.  Falls back to symbol-conversion equivalents
    when the original anchor character is not found.

    Records are processed from right to left so that each insertion does
    not shift the positions relevant to earlier (leftward) records.

    Args:
        translated: The translated line.
        records: Removal records produced by ``apply_anchor_removal``.

    Returns:
        Line with anchor patterns re-inserted.
    """
    if not records:
        return translated

    text = translated

    # Process from right to left (last record first)
    for rec in reversed(records):
        value = rec["value"]
        anchor_type = rec.get("anchor_type", "char")
        anchor_char = rec.get("anchor_char", "")
        side = rec.get("side", "left")

        if anchor_type == "line_end":
            text = text + value
            continue

        if anchor_type == "line_start":
            text = value + text
            continue

        # Character anchor — find in the translated text
        # Try original anchor char first, then symbol-converted equivalent
        candidates = [anchor_char]
        equiv = SYMBOL_CONVERSIONS_JA_EN.get(anchor_char)
        if equiv and equiv != anchor_char:
            candidates.append(equiv)
        # Also check the reverse mapping
        for src, tgt in SYMBOL_CONVERSIONS_JA_EN.items():
            if tgt == anchor_char and src not in candidates:
                candidates.append(src)

        inserted = False
        for ch in candidates:
            if not ch:
                continue
            if side == "left":
                # Pattern was LEFT of anchor → insert BEFORE anchor
                # Use rfind to find the rightmost occurrence
                pos = text.rfind(ch)
                if pos >= 0:
                    text = text[:pos] + value + text[pos:]
                    inserted = True
                    break
            else:
                # Pattern was RIGHT of anchor → insert AFTER anchor
                # Use rfind to find the rightmost occurrence
                pos = text.rfind(ch)
                if pos >= 0:
                    text = text[:pos + len(ch)] + value + text[pos + len(ch):]
                    inserted = True
                    break

        if not inserted:
            # Last resort: append at end if side was "left" (before
            # a char that no longer exists) or prepend if "right".
            if side == "left":
                text = text + value
            else:
                text = value + text

    return text


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication (lightweight — no Processor required)
# ─────────────────────────────────────────────────────────────────────────────

DEDUP_PLACEHOLDER = "__DEDUP__"


def apply_dedup_batch(
    lines: List[str],
    threshold: int = 1,
) -> Tuple[List[str], int, List[int], Dict[int, int]]:
    """Apply standard deduplication to lines.

    Keeps the first occurrence of each line; replaces later duplicates
    with ``__DEDUP__``.  Returns a mapping ``{dup_idx: source_idx}``
    for postprocessing restoration.

    Args:
        lines: Lines to process.
        threshold: Minimum occurrence count before dedup applies (1 = all).

    Returns:
        Tuple of (processed_lines, change_count, changed_indices,
        dedup_map ``{dup_idx: source_idx}``).
    """
    if threshold <= 0:
        return list(lines), 0, [], {}

    result = list(lines)
    first_by_text: Dict[str, int] = {}
    dedup_map: Dict[int, int] = {}
    changed_indices: List[int] = []
    changes = 0

    for i, line in enumerate(result):
        if not line.strip():
            continue
        head_idx = first_by_text.get(line)
        if head_idx is not None:
            result[i] = DEDUP_PLACEHOLDER
            dedup_map[i] = head_idx
            changed_indices.append(i)
            changes += 1
        else:
            first_by_text[line] = i

    return result, changes, changed_indices, dedup_map


def apply_aggressive_dedup_batch(
    lines: List[str],
) -> Tuple[List[str], int, List[int], Dict[int, int], Dict[int, List[str]]]:
    """Apply aggressive deduplication (number-normalized) to lines.

    Lines that differ only in digit sequences are treated as duplicates.
    The first occurrence is kept (with numbers masked to ``<NUM>``);
    later occurrences become ``__DEDUP__``.

    Args:
        lines: Lines to process (already standard-dedup'd).

    Returns:
        Tuple of (processed_lines, change_count, changed_indices,
        aggr_dedup_map ``{dup_idx: source_idx}``,
        aggr_numbers ``{line_idx: [original_numbers]}``).
    """
    result = list(lines)
    first_by_norm: Dict[str, int] = {}
    aggr_map: Dict[int, int] = {}
    aggr_numbers: Dict[int, List[str]] = {}
    changed_indices: List[int] = []
    changes = 0

    for i, line in enumerate(result):
        if not line.strip() or line == DEDUP_PLACEHOLDER:
            continue
        norm = aggressive_normalize_line(line)
        head_idx = first_by_norm.get(norm)
        if head_idx is not None:
            # Store numbers for this duplicate so post can restore
            _, nums = aggressive_mask_line(line)
            if nums:
                aggr_numbers[i] = nums
            # Mask the head line on first dup encounter if not yet masked
            if head_idx not in aggr_numbers:
                masked_head, head_nums = aggressive_mask_line(result[head_idx])
                if head_nums:
                    aggr_numbers[head_idx] = head_nums
                    if masked_head != result[head_idx]:
                        result[head_idx] = masked_head
                        if head_idx not in changed_indices:
                            changed_indices.append(head_idx)
                            changes += 1
            result[i] = DEDUP_PLACEHOLDER
            aggr_map[i] = head_idx
            changed_indices.append(i)
            changes += 1
        else:
            first_by_norm[norm] = i

    return result, changes, changed_indices, aggr_map, aggr_numbers


def _apply_speaker_replacement_batch(
    lines: List[str],
    characters: List[Dict[str, Any]],
) -> Tuple[List[str], int, List[int]]:
    """Replace speaker names in Speaker: Dialogue lines using character glossary.

    For each line starting with ``OriginalName:`` or ``OriginalName：``,
    replaces the speaker name with its translation from the characters list.

    Args:
        lines: Lines to process.
        characters: Character dicts with ``original_name`` and ``translation``.

    Returns:
        Tuple of (processed_lines, change_count, changed_indices).
    """
    import re as _re

    repl_map: Dict[str, str] = {}
    for char in characters:
        orig = char.get("original_name", "").strip()
        trans = char.get("translation", "").strip()
        if orig and trans and orig != trans:
            repl_map[orig] = trans

    if not repl_map:
        return lines, 0, []

    result = list(lines)
    name_alt = "|".join(
        sorted((_re.escape(n) for n in repl_map), key=len, reverse=True)
    )
    pat = _re.compile(rf"^(\s*)(?P<name>{name_alt})\s*(?P<sep>[:：])")
    changed = 0
    indices: List[int] = []
    for i, ln in enumerate(result):
        m = pat.match(ln)
        if not m:
            continue
        new_name = repl_map.get(m.group("name"), m.group("name"))
        new = f"{m.group(1)}{new_name}{m.group('sep')}" + ln[m.end():]
        if new != ln:
            result[i] = new
            changed += 1
            indices.append(i)
    return result, changed, indices


# ─────────────────────────────────────────────────────────────────────────────
# Unified Preprocessing Pipeline
# ─────────────────────────────────────────────────────────────────────────────


def apply_preprocessing(
    lines: List[str],
    config: Dict[str, Any],
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    """Apply full preprocessing pipeline based on configuration.

    Follows the priority ordering from specs §5.9:
      P10  Deduplication (first)
      P20  Ellipsis Compression
      P30  Symbol Conversion
      P60  PROTECTED Compression
      P70  Custom Placeholders
      P80  Protect Code Patterns
      P90  Aggressive Deduplication (last)

    Args:
        lines: Lines to process.
        config: Preprocessing configuration dict with keys:
            - dedup_enabled: bool
            - dedup_threshold: int
            - aggressive_dedup_enabled: bool
            - ellipsis_enabled: bool
            - symbol_conversion_enabled: bool
            - symbol_src_lang: str
            - symbol_tgt_lang: str
            - prot_compression_enabled: bool
            - protect_code_patterns: List[str]
            - placeholder_rules: List[Dict]
        progress_cb: Optional callback ``(step_name, fraction)`` invoked
            after each preprocessing rule completes. *fraction* ranges
            from 0.0 to 1.0.

    Returns:
        Tuple of (processed_lines, stats_dict) where stats_dict contains:
            - total_changes: int
            - changes_by_rule: Dict[str, int]
            - changed_lines: List[int]
            - tags_by_line: Dict[int, List[str]]  — per-line tag names
            - dedup_map: Dict[int, int]  — {dup_idx: source_idx}
            - aggr_dedup_map: Dict[int, int]  — {dup_idx: source_idx}
            - aggr_numbers: Dict[int, List[str]]  — {line_idx: [numbers]}
    """
    result = list(lines)
    tags_by_line: Dict[int, List[str]] = {}
    stats: Dict[str, Any] = {
        "total_changes": 0,
        "changes_by_rule": {},
        "changed_lines": set(),
        "tags_by_line": tags_by_line,
        "dedup_map": {},
        "aggr_dedup_map": {},
        "aggr_numbers": {},
    }

    def _tag_indices(indices: List[int], tag: str) -> None:
        for i in indices:
            tags_by_line.setdefault(i, []).append(tag)

    def _report(name: str, frac: float) -> None:
        if progress_cb is not None:
            progress_cb(name, frac)

    # P10. Deduplication (FIRST — per specs §5.9)
    _report("Deduplication", 0.0)
    if config.get("dedup_enabled", True):
        threshold = config.get("dedup_threshold", 1)
        if threshold > 0:
            result, count, indices, dedup_map = apply_dedup_batch(
                result, threshold,
            )
            stats["dedup_map"] = dedup_map
            if count:
                stats["changes_by_rule"]["dedup"] = count
                stats["total_changes"] += count
                stats["changed_lines"].update(indices)
                # Tag each dedup'd line for display + direct lookup
                for dup_idx, src_idx in dedup_map.items():
                    tags_by_line.setdefault(dup_idx, []).append("dedup")
                    tags_by_line[dup_idx].append(f"D{src_idx}")

    # P15. Protect Code Patterns (BEFORE symbol conversion so fullwidth
    #      patterns like （圧縮あり） still match the original text)
    _report("Protect Code Patterns", 0.10)
    patterns = config.get("protect_code_patterns", [])
    if patterns:
        result, count, indices, captured = apply_protect_batch(result, patterns)
        if count:
            stats["changes_by_rule"]["protect_code"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            stats["protect_code_captured"] = captured
            _tag_indices(indices, "protect_code")

    # P17. Custom placeholder rules (before symbol conversion)
    _report("Custom Placeholders", 0.15)
    rules = config.get("placeholder_rules", [])
    if rules:
        result, count, indices, captured = apply_placeholder_batch(result, rules)
        if count:
            stats["changes_by_rule"]["placeholder"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            stats["placeholder_captured"] = captured
            _tag_indices(indices, "placeholder")

    # P20. Anchoring (before symbol conversion)
    _report("Anchoring", 0.20)
    anchor_entries = config.get("anchor_entries", [])
    if anchor_entries:
        result, count, indices, anchor_captured = apply_anchor_batch(
            result, anchor_entries,
        )
        if count:
            stats["changes_by_rule"]["anchor"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            stats["anchor_captured"] = anchor_captured
            _tag_indices(indices, "anchor")

    # P30. Symbol conversion (after protection so __PROTECTED__ is safe)
    _report("Symbol Conversion", 0.30)
    if config.get("symbol_conversion_enabled", True):
        src = config.get("symbol_src_lang", "ja")
        tgt = config.get("symbol_tgt_lang", "en")
        result, count, indices = apply_symbol_batch(result, src, tgt)
        if count:
            stats["changes_by_rule"]["symbol_conversion"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            _tag_indices(indices, "symbol_conversion")

    # P36. Ellipsis compression (after symbol + width conversion)
    _report("Ellipsis Compression", 0.40)
    if config.get("ellipsis_enabled", True):
        result, count, indices, ell_counts = apply_ellipsis_batch(result)
        if count:
            stats["changes_by_rule"]["ellipsis"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            stats["ellipsis_counts"] = ell_counts
            _tag_indices(indices, "ellipsis")

    # P40. Speaker Name Replacement
    _report("Speaker Name Replacement", 0.50)
    if config.get("speaker_replacement_enabled", False):
        characters = config.get("characters", [])
        result, count, indices = _apply_speaker_replacement_batch(result, characters)
        if count:
            stats["changes_by_rule"]["speaker"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            _tag_indices(indices, "speaker")

    # P60. PROTECTED Token Compression (after all __PROTECTED__ tokens exist)
    _report("Protected Compression", 0.70)
    if config.get("prot_compression_enabled", True):
        result, count, indices = apply_prot_batch(result)
        if count:
            stats["changes_by_rule"]["prot_compression"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            _tag_indices(indices, "prot_compression")

    # P90. Aggressive Deduplication (LAST — per specs §5.9)
    _report("Aggressive Deduplication", 0.85)
    if config.get("aggressive_dedup_enabled", False):
        result, count, indices, aggr_map, aggr_nums = (
            apply_aggressive_dedup_batch(result)
        )
        stats["aggr_dedup_map"] = aggr_map
        stats["aggr_numbers"] = aggr_nums
        if count:
            stats["changes_by_rule"]["aggressive_dedup"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            # Tag each aggressive-dedup'd line for display + direct lookup
            for dup_idx, src_idx in aggr_map.items():
                tags_by_line.setdefault(dup_idx, []).append("aggressive_dedup")
                tags_by_line[dup_idx].append(f"AD{src_idx}")

    _report("Complete", 1.0)

    # Convert set to sorted list
    stats["changed_lines"] = sorted(stats["changed_lines"])

    return result, stats


# ─────────────────────────────────────────────────────────────────────────────
# Common Patterns Helper
# ─────────────────────────────────────────────────────────────────────────────

# Common protect code patterns for quick insertion
COMMON_PROTECT_PATTERNS: List[Dict[str, str]] = [
    {"pattern": r"<[^>]+>", "description": "HTML/XML tags"},
    {"pattern": r"\\[a-zA-Z]\[[^\]]*\]", "description": "RPG Maker codes"},
    {"pattern": r"\{[^}]+\}", "description": "Curly brace variables"},
    {"pattern": r"\[[^\]]+\]", "description": "Square bracket variables"},
    {"pattern": r"%[sd]", "description": "Printf format strings"},
    {"pattern": r"\$\{[^}]+\}", "description": "Template literals"},
    {"pattern": r"__[A-Z]+__", "description": "Double underscore tokens"},
]


def get_common_patterns() -> List[Dict[str, str]]:
    """Get list of common protect code patterns.

    Returns:
        List of dicts with 'pattern' and 'description' keys.
    """
    return list(COMMON_PROTECT_PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# Mode Registry Bridge (for future integration)
# ─────────────────────────────────────────────────────────────────────────────


def get_available_modes() -> Dict[str, Dict[str, Any]]:
    """Get available preprocessing modes from MODE_REGISTRY.

    Returns:
        Dict mapping mode names to their metadata.
    """
    modes: Dict[str, Dict[str, Any]] = {}

    try:
        from CherryAI.modi import load_modes, MODE_REGISTRY
        from pathlib import Path

        # Get the CherryAI root directory
        root = Path(__file__).parent.parent.parent
        load_modes(root)

        for name, module in MODE_REGISTRY.items():
            modes[name] = {
                "phase": getattr(module, "PHASE", "Both"),
                "priority": getattr(module, "PRIORITY", 100),
                "uses_regex": getattr(module, "USES_REGEX", False),
                "inputs": getattr(module, "INPUTS", []),
            }
    except ImportError as e:
        logger.debug("Could not load MODE_REGISTRY: %s", e)
    except Exception as e:
        logger.warning("Error loading modes: %s", e)

    return modes
