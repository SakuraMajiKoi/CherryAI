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
from typing import Any, Dict, List, Optional, Tuple

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
) -> Tuple[List[str], int, List[int]]:
    """Apply ellipsis compression to multiple lines.

    Args:
        lines: Lines to process.

    Returns:
        Tuple of (processed_lines, change_count, changed_indices).
    """
    result: List[str] = []
    changed_count = 0
    changed_indices: List[int] = []

    for idx, line in enumerate(lines):
        new_line, changed = apply_ellipsis_compression(line)
        result.append(new_line)
        if changed:
            changed_count += 1
            changed_indices.append(idx)

    return result, changed_count, changed_indices


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

    Args:
        line: Line to process.
        patterns: List of regex patterns (str) or dicts with a ``pattern`` key.

    Returns:
        Tuple of (processed_line, was_changed, captured_values).
    """
    original = line
    captured: List[str] = []

    for entry in patterns:
        # Handle both dict entries and raw strings
        if isinstance(entry, dict):
            pattern_str = entry.get("pattern", "")
        else:
            pattern_str = str(entry) if entry is not None else ""

        if not pattern_str.strip():
            continue
        try:
            pattern = re.compile(pattern_str)
            matches = list(pattern.finditer(line))
            for m in reversed(matches):
                val = m.group(0)
                if val:
                    captured.insert(0, val)
                    line = line[: m.start()] + "__PROTECTED__" + line[m.end() :]
        except re.error as e:
            logger.warning("Invalid protect code pattern %r: %s", pattern_str, e)

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
# Unified Preprocessing Pipeline
# ─────────────────────────────────────────────────────────────────────────────


def apply_preprocessing(
    lines: List[str],
    config: Dict[str, Any],
) -> Tuple[List[str], Dict[str, Any]]:
    """Apply full preprocessing pipeline based on configuration.

    Args:
        lines: Lines to process.
        config: Preprocessing configuration dict with keys:
            - ellipsis_enabled: bool
            - symbol_conversion_enabled: bool
            - symbol_src_lang: str
            - symbol_tgt_lang: str
            - prot_compression_enabled: bool
            - protect_code_patterns: List[str]
            - placeholder_rules: List[Dict]

    Returns:
        Tuple of (processed_lines, stats_dict) where stats_dict contains:
            - total_changes: int
            - changes_by_rule: Dict[str, int]
            - changed_lines: List[int]
    """
    result = list(lines)
    stats: Dict[str, Any] = {
        "total_changes": 0,
        "changes_by_rule": {},
        "changed_lines": set(),
    }

    # 1. Symbol conversion (should happen early)
    if config.get("symbol_conversion_enabled", True):
        src = config.get("symbol_src_lang", "ja")
        tgt = config.get("symbol_tgt_lang", "en")
        result, count, indices = apply_symbol_batch(result, src, tgt)
        if count:
            stats["changes_by_rule"]["symbol_conversion"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)

    # 2. Ellipsis compression
    if config.get("ellipsis_enabled", True):
        result, count, indices = apply_ellipsis_batch(result)
        if count:
            stats["changes_by_rule"]["ellipsis"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)

    # 3. Protect code patterns
    patterns = config.get("protect_code_patterns", [])
    if patterns:
        result, count, indices, captured = apply_protect_batch(result, patterns)
        if count:
            stats["changes_by_rule"]["protect_code"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            stats["protect_code_captured"] = captured

    # 4. Custom placeholder rules
    rules = config.get("placeholder_rules", [])
    if rules:
        result, count, indices, captured = apply_placeholder_batch(result, rules)
        if count:
            stats["changes_by_rule"]["placeholder"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)
            stats["placeholder_captured"] = captured

    # 5. PROTECTED compression (should happen last after PROTECTED tokens are created)
    if config.get("prot_compression_enabled", True):
        result, count, indices = apply_prot_batch(result)
        if count:
            stats["changes_by_rule"]["prot_compression"] = count
            stats["total_changes"] += count
            stats["changed_lines"].update(indices)

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
