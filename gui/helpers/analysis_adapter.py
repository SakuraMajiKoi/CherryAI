"""Analysis adapter for GUI integration.

This module bridges the GUI analysis step (gui/steps/analysis.py) with the
core analysis functions in functions/analysis.py and functions/glossaries/.

Purpose:
- Provides clean function signatures for GUI use
- Wraps core analysis functions with fallback implementations
- Aggregates results in GUI-friendly format

TASK 16.6: Integrates functions/analysis.py with GUI Step 2
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------- Imports from functions/analysis.py ---------------- #

# Core analysis functions
_summarize_lines_fn = None
_count_tokens_fn = None
_analyze_file_fn = None

# Glossary detection functions
_detect_code_fn = None
_detect_speaker_fn = None

try:
    from CherryAI.functions.analysis import _summarize_lines, count_tokens as _func_count_tokens, analyze_file
    _summarize_lines_fn = _summarize_lines
    _count_tokens_fn = _func_count_tokens
    _analyze_file_fn = analyze_file
except ImportError:
    try:
        from CherryAI.functions.analysis import _summarize_lines, count_tokens as _func_count_tokens, analyze_file
        _summarize_lines_fn = _summarize_lines
        _count_tokens_fn = _func_count_tokens
        _analyze_file_fn = analyze_file
    except ImportError:
        logger.debug("Could not import functions.analysis")

try:
    from CherryAI.functions.glossaries.code_glossary_functions import detect_code
    _detect_code_fn = detect_code
except ImportError:
    try:
        from CherryAI.functions.glossaries.code_glossary_functions import detect_code
        _detect_code_fn = detect_code
    except ImportError:
        logger.debug("Could not import code_glossary_functions.detect_code")

try:
    from CherryAI.functions.glossaries.name_glossary_functions import detect_speaker
    _detect_speaker_fn = detect_speaker
except ImportError:
    try:
        from CherryAI.functions.glossaries.name_glossary_functions import detect_speaker
        _detect_speaker_fn = detect_speaker
    except ImportError:
        logger.debug("Could not import name_glossary_functions.detect_speaker")


# ---------------- Language Detection ---------------- #

# Unicode ranges for language detection
HIRAGANA_RANGE = (0x3040, 0x309F)
KATAKANA_RANGE = (0x30A0, 0x30FF)
CJK_COMMON_RANGE = (0x4E00, 0x9FFF)
HANGUL_RANGE = (0xAC00, 0xD7AF)


def detect_language(text: str) -> Optional[str]:
    """Detect primary language of text based on character distribution.

    Args:
        text: Text to analyze.

    Returns:
        Language name or None if undetermined.
        One of: "Japanese", "Chinese", "Korean", "English/Latin", "Mixed"
    """
    if not text:
        return None

    # Count character types
    japanese = 0.0
    chinese = 0.0
    korean = 0.0
    latin = 0.0

    for char in text:
        code = ord(char)
        # Hiragana/Katakana - definite Japanese
        if HIRAGANA_RANGE[0] <= code <= HIRAGANA_RANGE[1]:
            japanese += 1
        elif KATAKANA_RANGE[0] <= code <= KATAKANA_RANGE[1]:
            japanese += 1
        # CJK common (used by Japanese, Chinese)
        elif CJK_COMMON_RANGE[0] <= code <= CJK_COMMON_RANGE[1]:
            # Could be Japanese or Chinese - weight towards Chinese
            japanese += 0.3
            chinese += 0.7
        # Korean Hangul
        elif HANGUL_RANGE[0] <= code <= HANGUL_RANGE[1]:
            korean += 1
        # Latin letters
        elif code < 128 and char.isalpha():
            latin += 1

    total = japanese + chinese + korean + latin
    if total == 0:
        return None

    # Determine primary language by threshold
    if japanese / total > 0.3:
        return "Japanese"
    elif chinese / total > 0.5:
        return "Chinese"
    elif korean / total > 0.3:
        return "Korean"
    elif latin / total > 0.5:
        return "English/Latin"
    return "Mixed"


def detect_language_batch(
    lines: List[str],
) -> Tuple[Dict[str, int], Dict[str, float]]:
    """Detect language distribution across multiple lines.

    Args:
        lines: Lines to analyze.

    Returns:
        Tuple of (language counts, language percentages)
    """
    counts: Dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lang = detect_language(stripped)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1

    total = sum(counts.values())
    percentages: Dict[str, float] = {}
    if total > 0:
        for lang, count in counts.items():
            percentages[lang] = round(count / total * 100, 2)

    return counts, percentages


# ---------------- Code Pattern Detection ---------------- #

# Fallback regex patterns for code detection (used if detect_code not available)
_RPG_MAKER_VAR_RE = re.compile(r"\\[VN]\[\d+\]", re.IGNORECASE)
_RPG_MAKER_FMT_RE = re.compile(r"\\[CFS]\[\d+\]", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_COLOR_CODE_RE = re.compile(r"#[0-9A-Fa-f]{6}")
_RUBY_TEXT_RE = re.compile(r"[一-龯]+[《（][ぁ-ん]+[》）]")
_LINE_BREAK_RE = re.compile(r"<br>|\\n", re.IGNORECASE)


def detect_code_patterns(text: str) -> List[str]:
    """Detect code patterns in text.

    Uses functions.glossaries.code_glossary_functions.detect_code for structure
    detection, supplemented with regex patterns for GUI-specific categories.

    Args:
        text: Text to analyze.

    Returns:
        List of detected pattern type names.
    """
    patterns: List[str] = []

    if _detect_code_fn is not None:
        # Use the proper code detection from glossary functions
        try:
            result = _detect_code_fn(text)
            if result.get("has_code"):
                codes_by_type = result.get("codes_by_type", {})
                for code_type, codes in codes_by_type.items():
                    if code_type == "LINEBREAK":
                        patterns.append("Line Breaks")
                    elif code_type in ("VARIABLENAME", "VARIABLENUMBER", "VISIBLEVARIABLE"):
                        patterns.append("RPG Maker Variables")
                    elif code_type == "COLOR":
                        patterns.append("Color Codes")
                    elif code_type == "FONT":
                        patterns.append("Font Formatting")
                    elif code_type == "RUBY":
                        patterns.append("Ruby/Furigana")
                    elif code_type == "UNKNOWN":
                        # Check for HTML-like tags and other patterns
                        for code in codes:
                            if code.startswith("<") and code.endswith(">"):
                                if "HTML/XML Tags" not in patterns:
                                    patterns.append("HTML/XML Tags")
                                # Check for line breaks like <br>
                                if code.lower() in ("<br>", "<br/>", "<br />"):
                                    if "Line Breaks" not in patterns:
                                        patterns.append("Line Breaks")
        except Exception as e:
            logger.debug("detect_code failed: %s", e)

    # Always apply supplementary regex patterns for GUI-expected categories
    # that the core detect_code may not catch
    if _RPG_MAKER_VAR_RE.search(text) and "RPG Maker Variables" not in patterns:
        patterns.append("RPG Maker Variables")

    if _RPG_MAKER_FMT_RE.search(text) and "RPG Maker Formatting" not in patterns:
        patterns.append("RPG Maker Formatting")

    if _HTML_TAG_RE.search(text) and "HTML/XML Tags" not in patterns:
        patterns.append("HTML/XML Tags")

    if _LINE_BREAK_RE.search(text) and "Line Breaks" not in patterns:
        patterns.append("Line Breaks")

    if _COLOR_CODE_RE.search(text) and "Color Codes" not in patterns:
        patterns.append("Color Codes")

    if _RUBY_TEXT_RE.search(text):
        patterns.append("Ruby/Furigana")

    return patterns


def detect_code_patterns_batch(
    lines: List[str],
) -> Tuple[Dict[str, int], Set[int]]:
    """Detect code patterns across multiple lines.

    Args:
        lines: Lines to analyze.

    Returns:
        Tuple of (pattern type counts, set of line indices with code)
    """
    counts: Dict[str, int] = {}
    lines_with_code: Set[int] = set()

    for idx, line in enumerate(lines):
        patterns = detect_code_patterns(line)
        if patterns:
            lines_with_code.add(idx)
            for pattern_type in patterns:
                counts[pattern_type] = counts.get(pattern_type, 0) + 1

    return counts, lines_with_code


# Import normalization function lazily
_normalize_code_fn = None

try:
    from CherryAI.functions.glossaries.code_glossary_functions import (
        _normalize_code_segment,
        classify_code_type,
    )
    _normalize_code_fn = _normalize_code_segment
except ImportError:
    logger.debug("Could not import _normalize_code_segment")


# Friendly type name mapping for code types
_CODE_TYPE_FRIENDLY: Dict[str, str] = {
    "LINEBREAK": "Line Break",
    "VARIABLENAME": "Variable Name",
    "VARIABLENUMBER": "Variable Number",
    "VISIBLEVARIABLE": "Visible Variable",
    "COLOR": "Color Code",
    "FONT": "Font Formatting",
    "RUBY": "Ruby/Furigana",
    "UNKNOWN": "Unknown",
}


def _friendly_code_type(raw_type: str) -> str:
    """Convert internal code type to user-friendly name.

    Args:
        raw_type: Internal type constant (e.g., 'VARIABLENAME').

    Returns:
        Friendly display name.
    """
    return _CODE_TYPE_FRIENDLY.get(raw_type, raw_type)


def detect_individual_codes_batch(
    lines: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Detect individual code patterns with counts, types, and sample lines.

    Instead of grouping by type category, this returns each unique normalized
    code pattern with its occurrence count, type classification, and a sample
    line for context.

    Args:
        lines: Lines to analyze.

    Returns:
        Dict mapping normalized_code -> {
            'count': int,
            'type': str (friendly name),
            'raw_type': str (internal type constant),
        }
    """
    codes: Dict[str, Dict[str, Any]] = {}

    if _detect_code_fn is None:
        # Fallback: use regex-based detection with no normalization
        for line in lines:
            patterns = detect_code_patterns(line)
            for pat in patterns:
                if pat not in codes:
                    codes[pat] = {
                        "count": 0,
                        "type": pat,
                        "raw_type": "UNKNOWN",
                    }
                codes[pat]["count"] += 1
        return codes

    normalize = _normalize_code_fn if _normalize_code_fn is not None else (lambda x: x)

    for line in lines:
        try:
            result = _detect_code_fn(line)
            if not result.get("has_code"):
                continue
            for _start, _end, raw_code, raw_type in result.get("spans", []):
                normalized = normalize(raw_code)
                if normalized not in codes:
                    codes[normalized] = {
                        "count": 0,
                        "type": _friendly_code_type(raw_type),
                        "raw_type": raw_type,
                    }
                codes[normalized]["count"] += 1
        except Exception as e:
            logger.debug("detect_code failed for line: %s", e)

    return codes


# ---------------- Speaker Detection ---------------- #

def detect_speaker_in_line(line: str) -> Optional[str]:
    """Detect speaker name in a line.

    Uses functions.glossaries.name_glossary_functions.detect_speaker if available,
    otherwise falls back to basic colon-based detection.

    Args:
        line: Line to analyze.

    Returns:
        Speaker name or None.
    """
    if _detect_speaker_fn is not None:
        try:
            speaker = _detect_speaker_fn(line)
            if speaker:
                return speaker
        except Exception as e:
            logger.debug("detect_speaker failed, using fallback: %s", e)

    # Fallback: basic colon detection
    if ": " in line or "：" in line:
        parts = line.replace("：", ": ").split(": ", 1)
        if len(parts) == 2 and len(parts[0]) < 30:
            speaker = parts[0].strip()
            if speaker:
                return speaker

    return None


def detect_speakers_batch(lines: List[str]) -> Dict[str, int]:
    """Detect and count speakers across multiple lines.

    Args:
        lines: Lines to analyze.

    Returns:
        Dict mapping speaker name to occurrence count.
    """
    speakers: Dict[str, int] = {}

    for line in lines:
        speaker = detect_speaker_in_line(line)
        if speaker:
            speakers[speaker] = speakers.get(speaker, 0) + 1

    return speakers


# ---------------- Line Statistics ---------------- #

def summarize_lines(lines: List[str]) -> Dict[str, Any]:
    """Compute basic line statistics.

    Uses functions.analysis._summarize_lines if available,
    otherwise uses local implementation.

    Args:
        lines: Lines to analyze.

    Returns:
        Dict with statistics (total_lines, empty_lines, unique_lines, etc.)
    """
    if _summarize_lines_fn is not None:
        try:
            return _summarize_lines_fn(lines)
        except Exception as e:
            logger.debug("_summarize_lines failed, using fallback: %s", e)

    # Fallback implementation
    total = len(lines)
    empty = sum(1 for x in lines if not x.strip())
    unique = len(set(lines))
    dupes = total - unique
    avg_len = (sum(len(x) for x in lines) / total) if total else 0.0
    max_len = max((len(x) for x in lines), default=0)

    return {
        "total_lines": total,
        "empty_lines": empty,
        "unique_lines": unique,
        "duplicate_lines": dupes,
        "avg_line_length": round(avg_len, 2),
        "max_line_length": max_len,
    }


def count_duplicates(lines: List[str], limit: int = 20) -> Dict[str, int]:
    """Count and return top duplicate lines.

    Args:
        lines: Lines to analyze.
        limit: Maximum number of duplicates to return.

    Returns:
        Dict mapping line text to count (for lines appearing more than once).
    """
    line_counts: Dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        line_counts[stripped] = line_counts.get(stripped, 0) + 1

    # Filter to duplicates only, sort by count
    duplicates = {
        line: count for line, count in line_counts.items()
        if count > 1
    }
    sorted_dups = sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:limit]

    return dict(sorted_dups)


# ---------------- Token Counting ---------------- #

def count_tokens(text: str) -> Tuple[int, str]:
    """Count tokens in text using tiktoken if available.

    Args:
        text: Text to count tokens for.

    Returns:
        Tuple of (token count, method used).
    """
    if _count_tokens_fn is not None:
        try:
            return _count_tokens_fn(text)
        except Exception as e:
            logger.debug("count_tokens failed, using fallback: %s", e)

    # Fallback: heuristic token counting
    if not text:
        return 0, "heuristic/empty"

    # Check for Japanese characters
    has_jp = any(
        (0x3040 <= ord(ch) <= 0x30FF) or (0x4E00 <= ord(ch) <= 0x9FFF)
        for ch in text
    )

    if has_jp:
        # Japanese: ~1.7 chars per token
        return max(1, len(text) // 2), "heuristic/jp"
    else:
        # Latin: ~4 chars per token
        return max(1, len(text) // 4), "heuristic/latin"


def count_tokens_batch(lines: List[str]) -> Tuple[int, List[int]]:
    """Count tokens for multiple lines.

    Args:
        lines: Lines to count tokens for.

    Returns:
        Tuple of (total tokens, per-line token counts).
    """
    per_line: List[int] = []
    total = 0

    for line in lines:
        tokens, _ = count_tokens(line)
        per_line.append(tokens)
        total += tokens

    return total, per_line


# ---------------- Full Analysis ---------------- #

def analyze_lines(
    lines: List[str],
    include_speakers: bool = True,
    include_code_patterns: bool = True,
    include_language: bool = True,
    include_tokens: bool = False,
) -> Dict[str, Any]:
    """Perform comprehensive analysis on lines.

    This is the main entry point for GUI analysis, combining all detection
    functions into a single result dictionary.

    Args:
        lines: Lines to analyze.
        include_speakers: Whether to detect speakers.
        include_code_patterns: Whether to detect code patterns.
        include_language: Whether to detect language.
        include_tokens: Whether to count tokens (slower).

    Returns:
        Dict with analysis results including:
        - summary: Basic line statistics
        - duplicates: Top duplicate lines
        - languages: Language distribution (if enabled)
        - speakers: Speaker counts (if enabled)
        - code_patterns: Code pattern counts (if enabled)
        - tokens: Token information (if enabled)
    """
    results: Dict[str, Any] = {}

    # Basic statistics
    results["summary"] = summarize_lines(lines)

    # Duplicates
    results["duplicates"] = count_duplicates(lines)
    results["duplicate_count"] = sum(results["duplicates"].values()) - len(results["duplicates"])

    # Language detection
    if include_language:
        lang_counts, lang_pcts = detect_language_batch(lines)
        results["languages"] = lang_counts
        results["language_percentages"] = lang_pcts

    # Speaker detection
    if include_speakers:
        results["speakers"] = detect_speakers_batch(lines)

    # Code pattern detection
    if include_code_patterns:
        code_counts, lines_with_code = detect_code_patterns_batch(lines)
        results["code_patterns"] = code_counts
        results["lines_with_code"] = len(lines_with_code)
        # Individual code patterns with full details
        results["individual_codes"] = detect_individual_codes_batch(lines)

    # Token counting
    if include_tokens:
        total_tokens, per_line_tokens = count_tokens_batch(lines)
        results["tokens"] = {
            "total": total_tokens,
            "per_line": per_line_tokens,
            "average": round(total_tokens / max(1, len(lines)), 2),
        }

    return results


# ---------------- Public API ---------------- #

__all__ = [
    # Language detection
    "detect_language",
    "detect_language_batch",
    # Code pattern detection
    "detect_code_patterns",
    "detect_code_patterns_batch",
    "detect_individual_codes_batch",
    # Speaker detection
    "detect_speaker_in_line",
    "detect_speakers_batch",
    # Line statistics
    "summarize_lines",
    "count_duplicates",
    # Token counting
    "count_tokens",
    "count_tokens_batch",
    # Full analysis
    "analyze_lines",
    # Unicode ranges (for testing/extension)
    "HIRAGANA_RANGE",
    "KATAKANA_RANGE",
    "CJK_COMMON_RANGE",
    "HANGUL_RANGE",
]
