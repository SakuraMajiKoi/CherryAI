from __future__ import annotations

"""Analysis module for CherryAI.

Purpose:
- Provide a lightweight, pluggable analysis of the currently loaded input file
  to help users understand structure and potential issues before running Pre/Post.

This module is intentionally minimal and framework-agnostic. It uses centralized
IO helpers from functions.mainhelper and writes analysis logs into the CherryAI
logs directory via the shared logging setup.

Entry point: analyze_file(input_path: Path, logs_dir: Path) -> dict[str, any]
  - Reads the file based on extension (txt/csv/tsv/json/xlsx) using central IO helpers
  - Computes a few basic metrics (line counts, empty lines, unique lines, duplicates)
  - Logs a concise summary to a timestamped analysis log in logs_dir
  - Returns a dictionary summary (for potential future GUI display)

Note: This is a skeleton that can be expanded (e.g., encoding checks, column stats,
JSON schema checks, ellipsis prevalence, protected-code prevalence, etc.).

TODO (analysis enhancements, always consider estimations for script length, time it takes to run the script and what libraries to possibly import. etc.):
- Readability scores — Flesch-Kincaid, SMOG: compute from sentence and syllable counts.
- Lexical diversity — type/token ratio and hapax proportion. Use token counts.
- Word & n-gram frequencies — top N words, bigrams, trigrams. Use lowercasing and stopword filtering.
- Average lengths — mean sentence length and mean word length.
- POS distribution — percent nouns/verbs/adjectives. Optional lightweight tagger (NLTK/spaCy).
- Sentiment (lexicon) — polarity and intensity via VADER or simple sentiment-word lists.
- Formality proxy — contraction count, slang tokens, function-word ratios.
- Readability-complexity proxy — ratio of complex words (≥3 syllables), comma and subordinate conjunction counts.
- Cohesion proxies — pronoun density, transition/connective word counts, TF-IDF similarity between adjacent paragraphs.
- Repetition & fluency issues — repeated n-grams, sentence starts repeated, excessive passive constructions (requires tagger).
- Ambiguity heuristic — words with many WordNet synsets or many POS tags flagged as potentially polysemous.
- Rhetorical/ stylistic flags — all-caps, excessive exclamation/question marks, rhetorical-question detection.
- Vocabulary level mapping — match tokens against CEFR or frequency lists to estimate difficulty.
- Bias/subjectivity detector — combine subjectivity lexicon hits and strong evaluative adjectives.
- Topic coherence (light) — cluster sentence TF-IDF vectors and measure within-cluster similarity.

Implementation notes:
- Prefer plain counts/ratios, simple lexicons, TF-IDF; make POS/WordNet optional behind try/except.
- Add functions incrementally; keep outputs small by default (sample lists disabled via ANALYSIS_INCLUDE_SAMPLES).

"""

import json
import logging
import math
import re
from pathlib import Path
import csv
from typing import Any, Dict, List, Optional, Tuple, Callable
import difflib
from dataclasses import dataclass, field
import os

logger = logging.getLogger(__name__)

# TASK 59.7: Module-level storage for ignored patterns during analysis
# These patterns will be excluded from code pattern detection results
_ignored_patterns: set[str] = set()


def set_ignored_patterns(patterns: List[str]) -> None:
    """Set patterns to ignore during analysis.

    Args:
        patterns: List of pattern strings to ignore.
    """
    global _ignored_patterns
    _ignored_patterns = set(patterns) if patterns else set()
    logger.debug("Set %d ignored patterns for analysis", len(_ignored_patterns))


def get_ignored_patterns() -> List[str]:
    """Get the current list of ignored patterns.

    Returns:
        List of pattern strings currently being ignored.
    """
    return list(_ignored_patterns)


def add_ignored_pattern(pattern: str) -> None:
    """Add a single pattern to the ignore list.

    Args:
        pattern: Pattern string to ignore.
    """
    _ignored_patterns.add(pattern)
    logger.debug("Added ignored pattern: %s", pattern)


def remove_ignored_pattern(pattern: str) -> None:
    """Remove a pattern from the ignore list.

    Args:
        pattern: Pattern string to remove from ignore list.
    """
    _ignored_patterns.discard(pattern)
    logger.debug("Removed ignored pattern: %s", pattern)


def filter_ignored_patterns(code_items: Dict[str, int]) -> Dict[str, int]:
    """Filter out ignored patterns from code items.

    Args:
        code_items: Dictionary of code pattern -> count.

    Returns:
        Filtered dictionary without ignored patterns.
    """
    if not _ignored_patterns:
        return code_items
    return {k: v for k, v in code_items.items() if k not in _ignored_patterns}


# Centralized aggressive dedup normalization from dedup module (fallback if unavailable)
aggressive_normalize_line: Optional[Callable[[str], str]] = None
try:
    from .dedup import aggressive_normalize_line as _aggr_norm_fn
    aggressive_normalize_line = _aggr_norm_fn
except Exception:
    try:
        from CherryAI.functions.dedup import aggressive_normalize_line as _aggr_norm_fn
        aggressive_normalize_line = _aggr_norm_fn
    except Exception:
        aggressive_normalize_line = None

# Robust import strategy similar to other modules
try:
    from .mainhelper import (
        read_text,
        read_table,
        read_json_pairs,
        read_xlsx_pairs,
    )
except Exception:
    from CherryAI.functions.mainhelper import (
        read_text,
        read_table,
        read_json_pairs,
        read_xlsx_pairs,
    )
try:
    from .mainhelper import Manifest, Operation, write_text
except Exception:
    from CherryAI.functions.mainhelper import Manifest, Operation, write_text

# Import glossary detection and extraction functions from new modules
try:
    from .glossaries.name_glossary_functions import (
        detect_speaker,
        extract_names_from_honorifics,
        _normalize_speaker,
        _get_script_type,
        _is_valid_name_candidate,
    )
    from .glossaries.name_glossary_constants import (
        HONORIFIC_RE,
        HONORIFIC_SUFFIXES,
        PRONOUN_LABELS,
        SUFFIX_LABELS,
        RPGM_VAR_RE,
        RPGM_ACTOR_RE,
        HIRAGANA_RANGE,
        KATAKANA_RANGE,
        KANJI_RANGE,
        PLACEHOLDER_NAME_RE,
    )
    from .glossaries.code_glossary_functions import (
        detect_code,
        _normalize_code_segment,
        _find_parenthesis_code,
    )
    from .glossaries.code_glossary_constants import (
        CODE_PATTERNS,
        COLOR_NAMES as _COLOR_NAMES,
    )
except Exception:
    from CherryAI.functions.glossaries.name_glossary_functions import (
        detect_speaker,
        extract_names_from_honorifics,
        _normalize_speaker,
        _get_script_type,
        _is_valid_name_candidate,
    )
    from CherryAI.functions.glossaries.name_glossary_constants import (
        HONORIFIC_RE,
        HONORIFIC_SUFFIXES,
        PRONOUN_LABELS,
        SUFFIX_LABELS,
        RPGM_VAR_RE,
        RPGM_ACTOR_RE,
        HIRAGANA_RANGE,
        KATAKANA_RANGE,
        KANJI_RANGE,
        PLACEHOLDER_NAME_RE,
    )
    from CherryAI.functions.glossaries.code_glossary_functions import (
        detect_code,
        _normalize_code_segment,
        _find_parenthesis_code,
    )
    from CherryAI.functions.glossaries.code_glossary_constants import (
        CODE_PATTERNS,
        COLOR_NAMES as _COLOR_NAMES,
    )

try:
    from .glossary import read_unified_glossary
except Exception:
    from CherryAI.functions.glossary import read_unified_glossary


def _summarize_lines(lines: List[str]) -> Dict[str, Any]:
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
        # Additional deduplication metrics (filled in later by analyze_file)
        "additional_duplicate_lines": 0,
        "total_duplicate_lines": 0,
        "avg_line_length": round(avg_len, 2),
        "max_line_length": max_len,
    }


# ---------------- Tokenization and pricing ---------------- #

# Import pricing from centralized config (TASK 16.4)
from CherryAI.functions.config import (
    DEFAULT_PRICING_MODEL,
    OUTPUT_TOKEN_MULTIPLIER,
    estimate_cost,
    get_model_pricing,
)

_tiktoken_encoder = None  # lazy-loaded encoder
# Toggle controlling whether line/occurrence sample lists are collected and returned.
# Default: False (do not collect samples to reduce noise/size). Set to True to enable.
ANALYSIS_INCLUDE_SAMPLES = False


# ---------------- Estimation config and assets (config/prompt/glossary) ---------------- #

CONFIG_DIRNAME = "config"
CONFIG_FILENAME = "config.txt"
PROMPT_FILENAME = "prompt.txt"
GLOSSARY_FILENAME = "glossary.json"


@dataclass
class EstimationConfig:
    jp_to_en_multiplier: float = 1.2
    lines_per_request: int = 30
    max_input_tokens_per_request: int = 3000
    limiter_modus: str = "LINES"  # LINES | TOKENS | LOWER | HIGHER
    rolling_context_count: int = 3
    aggressive_dedup: bool = False
    # diagnostics
    path: Optional[Path] = None
    created: bool = False


def _get_config_dir() -> Path:
    """Return the CherryAI/config directory (create if missing)."""
    try:
        here = Path(__file__).resolve()
        cfg_dir = here.parent.parent / CONFIG_DIRNAME
    except Exception:
        cfg_dir = Path(CONFIG_DIRNAME)
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


def _parse_config_text(text: str) -> Dict[str, str]:
    kv: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip().lower()] = v.strip()
    return kv


def _write_default_config(path: Path) -> None:
    default_text = (
        "# CherryAI analysis estimation config\n"
        "# Note: The token limit below is intended for the to-be-translated content.\n"
        "#       However, the request limiter uses BOTH the prompt and the (selected) glossary\n"
        "#       alongside content when checking the max tokens per request.\n"
        "# Keys:\n"
        "#   jp_to_en_multiplier = 1.2\n"
        "#   lines_per_request = 30\n"
        "#   max_input_tokens_per_request = 3000\n"
        "#   limiter modus = LINES   # Options: LINES, TOKENS, LOWER, HIGHER\n"
        "#   rolling_context_count = 3\n"
        "#   aggressive_dedup = False\n"
        "jp_to_en_multiplier = 1.2\n"
        "lines_per_request = 30\n"
        "max_input_tokens_per_request = 3000\n"
        "limiter modus = LINES\n"
        "rolling_context_count = 3\n"
        "aggressive_dedup = True\n"
    )
    try:
        write_text(path, default_text)
    except Exception:
        path.write_text(default_text, encoding="utf-8")


def _load_or_create_config() -> EstimationConfig:
    cfg_dir = _get_config_dir()
    cfg_path = cfg_dir / CONFIG_FILENAME
    created = False
    if not cfg_path.exists():
        _write_default_config(cfg_path)
        created = True
    try:
        try:
            cfg_text = read_text(cfg_path)
        except Exception:
            cfg_text = cfg_path.read_text(encoding="utf-8")
        kv = _parse_config_text(cfg_text)
    except Exception:
        kv = {}
    # normalize keys (allow both with and without space)
    def _get(key: str, default: object) -> str:
        v = kv.get(key.lower())
        if v is not None:
            return v
        # alias with underscore/space swap
        alias = key.replace("_", " ")
        v = kv.get(alias.lower())
        if v is not None:
            return v
        alias2 = key.replace(" ", "_")
        v = kv.get(alias2.lower())
        if v is not None:
            return v
        return str(default)

    def _to_int(s: str, d: int) -> int:
        try:
            return int(float(s))
        except Exception:
            return d

    def _to_float(s: str, d: float) -> float:
        try:
            return float(s)
        except Exception:
            return d

    jp2en = _to_float(_get("jp_to_en_multiplier", 1.2), 1.2)
    lpr = max(1, _to_int(_get("lines_per_request", 30), 30))
    mit = max(1, _to_int(_get("max_input_tokens_per_request", 3000), 3000))
    lim = _get("limiter modus", "LINES").strip().upper()
    rc = max(0, _to_int(_get("rolling_context_count", 3), 3))
    # aggressive dedup option (true/false)
    aggr = _get("aggressive_dedup", "False")
    try:
        aggr_bool = str(aggr).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        aggr_bool = False
    if lim not in {"LINES", "TOKENS", "LOWER", "HIGHER"}:
        lim = "LINES"
    return EstimationConfig(
        jp_to_en_multiplier=jp2en,
        lines_per_request=lpr,
        max_input_tokens_per_request=mit,
        limiter_modus=lim,
        rolling_context_count=rc,
        aggressive_dedup=aggr_bool,
        path=cfg_path,
        created=created,
    )


def _read_prompt_tokens(cfg_dir: Optional[Path] = None) -> Tuple[int, str]:
    """Return (prompt_token_count, method). If prompt not found, (0, 'none')."""
    dirp = cfg_dir or _get_config_dir()
    p = dirp / PROMPT_FILENAME
    if not p.exists():
        return 0, "none"
    try:
        try:
            content = read_text(p)
        except Exception:
            content = p.read_text(encoding="utf-8")
        tk, method = count_tokens(content)
        return tk, method
    except Exception:
        return 0, "error"


def _build_selected_glossary_block(input_text: str, cfg_dir: Optional[Path] = None) -> Tuple[str, int, List[Dict[str, Any]]]:
    """Return (printable_block, token_count, selected_items). If none selected, returns ("", 0, []).

    Selected items are those whose 'original' occurs in the input_text.
    
    The printable format is:
    Glossary (Input-Output-Note):\n
    original-translation-notes\n
    ...
    """
    read_gloss_fn: Optional[Callable[[], Dict[str, Any]]] = None
    try:
        from .glossary import read_unified_glossary as _read_unified_glossary
        read_gloss_fn = _read_unified_glossary
    except Exception:
        try:
            from CherryAI.functions.glossary import read_unified_glossary as _read_unified_glossary
            read_gloss_fn = _read_unified_glossary
        except Exception:
            read_gloss_fn = None
    
    selected: List[Dict[str, Any]] = []
    
    if read_gloss_fn is not None:
        try:
            entries = read_gloss_fn()
            for original, entry in entries.items():
                # Skip blacklisted tokens
                blacklist_substrs = {"人", "男", "女", "生徒", "入浴", "入浴客", "？", "?", "？？？"}
                skip = False
                for sub in blacklist_substrs:
                    if sub and sub in original:
                        skip = True
                        break
                if skip:
                    continue
                    
                if original in input_text:
                    selected.append({
                        "in": original,
                        "out": entry.translation,
                        "note": entry.notes,
                    })
            
            if selected:
                lines = ["Glossary (Input-Output-Note):"]
                for it in selected:
                    ins = str(it.get("in", ""))
                    outs = str(it.get("out", ""))
                    note = str(it.get("note", ""))
                    lines.append(f"{ins}-{outs}-{note}")
                block = "\n".join(lines)
                tks, _m = count_tokens(block)
                return block, tks, selected
        except Exception as exc:
            logging.debug("Failed to build glossary block from unified: %s", exc)
    
    return "", 0, []


def _load_glossary_index(cfg_dir: Optional[Path] = None) -> Dict[str, Tuple[str, str]]:
    """Return a mapping of glossary 'original' -> (translation, notes).

    Used for enriching speaker rows and building API prompts.
    """
    read_gloss_fn: Optional[Callable[[], Dict[str, Any]]] = None
    try:
        from .glossary import read_unified_glossary as _read_unified_glossary
        read_gloss_fn = _read_unified_glossary
    except Exception:
        try:
            from CherryAI.functions.glossary import read_unified_glossary as _read_unified_glossary
            read_gloss_fn = _read_unified_glossary
        except Exception:
            read_gloss_fn = None
    
    if read_gloss_fn is not None:
        try:
            entries = read_gloss_fn()
            out_map: Dict[str, Tuple[str, str]] = {}
            for original, entry in entries.items():
                out_map[original] = (entry.translation, entry.notes)
            if out_map:
                return out_map
        except Exception as exc:
            logging.debug("Failed to load unified glossary: %s", exc)
    
    return {}


def _try_load_encoder() -> Optional[Any]:
    global _tiktoken_encoder
    if _tiktoken_encoder is not None:
        return _tiktoken_encoder
    try:
        import tiktoken

        _tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
        return _tiktoken_encoder
    except Exception:
        return None


# =============================================================================
# PHASE 59.1: PROJECT-LEVEL LANGUAGE DETECTION
# =============================================================================


def is_hiragana_or_katakana(char: str) -> bool:
    """Check if a character is hiragana or katakana (Japanese kana).

    PHASE 59.1: Used for project-level Japanese/Chinese classification.
    Japanese has unique kana; Chinese does not.

    Args:
        char: Single character to check.

    Returns:
        True if character is hiragana or katakana.
    """
    o = ord(char)
    # Hiragana: U+3040-U+309F
    # Katakana: U+30A0-U+30FF
    return (0x3040 <= o <= 0x309F) or (0x30A0 <= o <= 0x30FF)


def is_cjk_character(char: str) -> bool:
    """Check if a character is CJK unified ideograph (kanji/hanzi).

    Args:
        char: Single character to check.

    Returns:
        True if character is CJK unified ideograph.
    """
    o = ord(char)
    # CJK Unified Ideographs: U+4E00-U+9FFF
    # CJK Unified Ideographs Extension A: U+3400-U+4DBF
    return (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF)


def is_hangul(char: str) -> bool:
    """Check if a character is Korean Hangul.

    Args:
        char: Single character to check.

    Returns:
        True if character is Hangul.
    """
    o = ord(char)
    # Hangul Syllables: U+AC00-U+D7AF
    # Hangul Jamo: U+1100-U+11FF
    return (0xAC00 <= o <= 0xD7AF) or (0x1100 <= o <= 0x11FF)


def classify_cjk_line(line: str) -> Optional[str]:
    """Classify a line as Japanese, Chinese-only, Korean, or None.

    PHASE 59.1: Project-level classification logic.
    - Japanese: Contains ANY hiragana or katakana (regardless of kanji)
    - Chinese-only: Contains CJK but NO hiragana or katakana
    - Korean: Contains Hangul only (handled separately)
    - None: No CJK characters

    Args:
        line: Line of text to classify.

    Returns:
        'japanese', 'chinese_only', 'korean', or None.
    """
    has_kana = False
    has_cjk = False
    has_hangul = False

    for char in line:
        if is_hiragana_or_katakana(char):
            has_kana = True
        elif is_cjk_character(char):
            has_cjk = True
        elif is_hangul(char):
            has_hangul = True

    # Classification priority
    if has_kana:
        return "japanese"
    if has_hangul:
        return "korean"
    if has_cjk:
        return "chinese_only"
    return None


@dataclass
class ProjectLanguageResult:
    """Result of project-level language detection.

    PHASE 59.1: Contains classification details and threshold information.
    """

    dominant_language: str  # "Japanese", "Chinese", "Korean", or "Unknown"
    threshold_applied: bool  # Whether Chinese lines were reclassified
    chinese_percentage: float  # Percentage of CJK lines that are Chinese-only
    japanese_lines: int  # Count of lines with kana
    chinese_only_lines: int  # Count of CJK lines without kana
    korean_lines: int  # Count of Hangul lines
    total_cjk_lines: int  # Total CJK lines analyzed


def detect_project_language(
    lines: List[str],
    threshold: float = 0.30,
) -> ProjectLanguageResult:
    """Detect the dominant language of a project using threshold rule.

    PHASE 59.1: Project-level language detection.
    - Classifies each CJK line as Japanese, Chinese-only, or Korean
    - Applies 30% threshold: if chinese_percentage < 0.30, project is Japanese

    Args:
        lines: List of text lines to analyze.
        threshold: Chinese percentage threshold (default 0.30).

    Returns:
        ProjectLanguageResult with classification details.
    """
    japanese_lines = 0
    chinese_only_lines = 0
    korean_lines = 0

    for line in lines:
        classification = classify_cjk_line(line)
        if classification == "japanese":
            japanese_lines += 1
        elif classification == "chinese_only":
            chinese_only_lines += 1
        elif classification == "korean":
            korean_lines += 1

    total_cjk = japanese_lines + chinese_only_lines
    # Note: Korean is handled separately, not included in CJK threshold

    # Calculate Chinese percentage (excluding Korean)
    if total_cjk > 0:
        chinese_percentage = chinese_only_lines / total_cjk
    else:
        chinese_percentage = 0.0

    # Determine dominant language
    threshold_applied = False
    if total_cjk == 0 and korean_lines == 0:
        dominant_language = "Unknown"
    elif korean_lines > total_cjk:
        dominant_language = "Korean"
    elif chinese_percentage < threshold:
        # Below threshold: project is Japanese (even if some Chinese-only lines exist)
        dominant_language = "Japanese"
        if chinese_only_lines > 0:
            threshold_applied = True
            logger.info(
                "Project classified as Japanese (%.1f%% Chinese-only < %.0f%% threshold)",
                chinese_percentage * 100,
                threshold * 100,
            )
    else:
        # Above threshold: project is Chinese
        dominant_language = "Chinese"

    return ProjectLanguageResult(
        dominant_language=dominant_language,
        threshold_applied=threshold_applied,
        chinese_percentage=chinese_percentage,
        japanese_lines=japanese_lines,
        chinese_only_lines=chinese_only_lines,
        korean_lines=korean_lines,
        total_cjk_lines=total_cjk,
    )


def _has_japanese(text: str) -> bool:
    # Hiragana, Katakana, CJK Unified Ideographs, CJK Ext-A
    for ch in text:
        o = ord(ch)
        if (0x3040 <= o <= 0x30FF) or (0x3400 <= o <= 0x4DBF) or (0x4E00 <= o <= 0x9FFF):
            return True
    return False


def detect_line_script(text: str) -> str:
    """Detect the dominant script of a line.

    Returns one of: 'japanese', 'chinese', 'korean', 'latin', 'mixed',
    or 'unknown' for very short / empty lines.

    Short lines (< 3 non-whitespace chars) return 'unknown' to avoid
    false positives.

    Args:
        text: Line of text to classify.

    Returns:
        Script identifier string.
    """
    stripped = text.strip()
    # Short lines are ambiguous — never skip them
    if len(stripped) < 3:
        return "unknown"

    cjk = 0
    hiragana_katakana = 0
    hangul = 0
    latin = 0
    total = 0

    for ch in stripped:
        o = ord(ch)
        if ch.isspace():
            continue
        total += 1
        if (0x3040 <= o <= 0x30FF):
            hiragana_katakana += 1
        elif (0x3400 <= o <= 0x4DBF) or (0x4E00 <= o <= 0x9FFF):
            cjk += 1
        elif (0xAC00 <= o <= 0xD7AF) or (0x1100 <= o <= 0x11FF):
            hangul += 1
        elif (0x0041 <= o <= 0x005A) or (0x0061 <= o <= 0x007A):
            latin += 1
        elif (0x00C0 <= o <= 0x024F):
            latin += 1

    if total == 0:
        return "unknown"

    jp = hiragana_katakana + cjk
    if hiragana_katakana > 0 and jp / total > 0.3:
        return "japanese"
    if hangul / total > 0.3:
        return "korean"
    if cjk / total > 0.3:
        return "chinese"
    if latin / total > 0.3:
        return "latin"
    return "mixed"


def _normalize_for_dedup(line: str) -> str:
    """Delegate to centralized dedup.aggressive_normalize_line when available.

    Fallback mirrors previous local normalization if the helper is unavailable.
    """
    if aggressive_normalize_line is not None:
        try:
            return aggressive_normalize_line(line)
        except Exception:
            pass
    if not line:
        return ""
    s = str(line)
    s = re.sub(r"<[^>]+?>", "", s)
    s = re.sub(r"[（\(]\s*[0-9０-９]+\s*[）\)]", " <NUM> ", s)
    s = re.sub(r"[0-9０-９]+", " <NUM> ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def calculate_aggressive_dedup_projection(
    lines: List[str],
) -> Dict[str, Any]:
    """Calculate projected line count after aggressive deduplication.

    Args:
        lines: List of text lines to analyze.

    Returns:
        Dictionary with keys:
            - original_count: Total number of lines
            - unique_count: Number of unique lines after normalization
            - reduction_percent: Percentage reduction (0-100)
            - display_text: Formatted display string
    """
    if not lines:
        return {
            "original_count": 0,
            "unique_count": 0,
            "reduction_percent": 0.0,
            "display_text": "Aggressive Dedup: 0 lines → 0 unique (0% reduction)",
        }

    original_count = len(lines)
    normalized_set: set[str] = set()
    for line in lines:
        normalized = _normalize_for_dedup(line)
        if normalized:
            normalized_set.add(normalized)

    unique_count = len(normalized_set)
    if original_count > 0:
        reduction_percent = ((original_count - unique_count) / original_count) * 100
    else:
        reduction_percent = 0.0

    display_text = (
        f"Aggressive Dedup: {original_count:,} lines → "
        f"{unique_count:,} unique ({reduction_percent:.1f}% reduction)"
    )

    return {
        "original_count": original_count,
        "unique_count": unique_count,
        "reduction_percent": round(reduction_percent, 1),
        "display_text": display_text,
    }


def count_tokens(text: str) -> Tuple[int, str]:
    """Return (token_count, method) using tiktoken if available; otherwise heuristic.

    Heuristic: if Japanese present, tokens ≈ len(text)/1.7; else ≈ len(text)/4.
    """
    enc = _try_load_encoder()
    if enc is not None:
        try:
            return len(enc.encode(text)), "tiktoken/cl100k_base"
        except Exception:
            pass
    if not text:
        return 0, "heuristic/empty"
    if _has_japanese(text):
        return math.ceil(len(text) / 1.7), "heuristic/jp"
    return math.ceil(len(text) / 4), "heuristic/latin"


# Note: estimate_cost is now imported from config.py (TASK 16.4)
# The function signature is compatible: estimate_cost(input_tokens, output_tokens, model=None)
# For backward compatibility, calls without model parameter use DEFAULT_PRICING_MODEL ("gpt-4o-mini")


# ---------------- End imported constants and helpers (from glossaries/*) ---------------- #


# ============================================================================
# Context Marker Detection (Phase 50)
# ============================================================================

# Patterns for detecting numbered/bulleted choice items
_CHOICE_RE = re.compile(
    r"^\s*(?:"
    r"\d+[.)]\s"           # 1. / 1) numbered lists
    r"|[・●■□◆▶►▸→]\s?"    # Bullet-like markers (CJK/Unicode)
    r"|[-*]\s"             # Markdown-style bullets
    r"|[①②③④⑤⑥⑦⑧⑨⑩]"    # Circled numbers
    r")",
)

# Short-line threshold for menu detection (chars)
_MENU_MAX_LEN = 60


def _is_choice_item(line: str) -> bool:
    """Return ``True`` if *line* looks like a numbered or bulleted choice.

    Heuristic: starts with a number/bullet pattern AND is reasonably short
    (to avoid matching numbered paragraphs).

    Args:
        line: Raw line text.

    Returns:
        True if the line matches a choice-item pattern.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    return bool(_CHOICE_RE.match(stripped))


def _is_menu_item(line: str) -> bool:
    """Return ``True`` if *line* looks like a short menu item.

    Menu items are typically short, self-contained strings without speaker
    prefixes.  Examples: "New Game", "Settings", "はい", "いいえ".

    Args:
        line: Raw line text.

    Returns:
        True if the line looks like a menu item.
    """
    stripped = line.strip()
    if not stripped:
        return False
    # Too long for a menu item
    if len(stripped) > _MENU_MAX_LEN:
        return False
    # Has a speaker prefix → likely dialogue, not menu
    if detect_speaker(stripped):
        return False
    # Multi-sentence lines are not menu items
    if stripped.count("。") > 1 or stripped.count(". ") > 1:
        return False
    return True


def _is_dialogue_line(line: str) -> bool:
    """Return ``True`` if *line* has a speaker:dialogue pattern.

    Relies on the established ``detect_speaker`` function from glossary.

    Args:
        line: Raw line text.

    Returns:
        True if a Speaker: Dialogue pattern is detected.
    """
    return detect_speaker(line.strip()) is not None


def detect_context_markers(
    lines: List[str],
    min_run: int = 3,
) -> List[Optional[str]]:
    """Detect context marker annotations for a list of raw lines.

    Scans *lines* for contiguous runs of menu items, choice items, or
    dialogue lines.  A run of ``min_run`` or more consecutive matching
    lines earns a marker annotation; shorter runs are left as ``None``
    (treated as "unknown").

    This function does **not** produce file_end markers — those come from
    the file-loading layer or from Parser Scripts.

    Args:
        lines: Raw text lines (orig or prepro).
        min_run: Minimum consecutive lines to trigger a marker annotation.

    Returns:
        List of marker strings or ``None`` per line, same length as *lines*.
        Possible values: ``"dialogue"``, ``"menu"``, ``"choice"``, ``None``.
    """
    n = len(lines)
    markers: List[Optional[str]] = [None] * n

    if n == 0:
        return markers

    # Classify each line independently
    raw_types: List[Optional[str]] = [None] * n
    for i, line in enumerate(lines):
        text = line.strip()
        if not text:
            # Empty lines don't belong to any category
            continue
        if _is_choice_item(text):
            raw_types[i] = "choice"
        elif _is_dialogue_line(text):
            raw_types[i] = "dialogue"
        elif _is_menu_item(text):
            raw_types[i] = "menu"

    # Identify contiguous runs and apply min_run threshold
    i = 0
    while i < n:
        kind = raw_types[i]
        if kind is None:
            i += 1
            continue

        # Scan the run of the same kind
        j = i
        while j < n and raw_types[j] == kind:
            j += 1

        run_len = j - i
        if run_len >= min_run:
            for k in range(i, j):
                markers[k] = kind

        i = j

    return markers


def get_active_context_type(
    context_markers: List[Optional[str]],
    index: int,
) -> str:
    """Return the active context type at *index* by scanning backwards.

    Context markers apply from their position until the next marker.  If no
    marker precedes *index*, the result is ``"unknown"``.

    Args:
        context_markers: Per-line marker list (from :func:`detect_context_markers`
            or from LineEntry.context_marker values).
        index: The line index to query.

    Returns:
        Active context type: ``"dialogue"``, ``"menu"``, ``"choice"``, or
        ``"unknown"``.
    """
    for i in range(index, -1, -1):
        marker = context_markers[i]
        if marker is not None:
            return marker
    return "unknown"


def analyze_file(input_path: Path, logs_dir: Path) -> Dict[str, Any]:
    """Analyze the given file and write a concise summary into logs_dir.

    Returns a dict summary for potential UI display.
    """
    input_path = Path(input_path)
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "input": str(input_path),
        "kind": input_path.suffix.lower(),
    }

    code_total = 0
    lines_with_code = 0
    speakers: Dict[str, int] = {}
    # honorific counts are attached to speakers via speaker_suffix_counts
    # (speaker_normalized -> suffix -> count)
    rpgm_vars: Dict[str, int] = {}
    rpgm_actors: Dict[str, int] = {}
    code_items: Dict[str, int] = {}
    total_tokens = 0
    token_method = ""
    lines: List[str] = []
    
    # Per-speaker pronoun and suffix tracking for gender/style inference
    # speaker_pronoun_counts: speaker -> pronoun_token -> count
    speaker_pronoun_counts: Dict[str, Dict[str, int]] = {}
    # speaker_suffix_counts: speaker -> suffix -> count
    speaker_suffix_counts: Dict[str, Dict[str, int]] = {}
    # speaker_lines: mapping from speaker to their line indices (for later analysis)
    speaker_lines: Dict[str, List[int]] = {}

    try:
        suffix = input_path.suffix.lower()
        if suffix in (".txt",):
            text = read_text(input_path)
            lines = text.splitlines()
        elif suffix in (".csv", ".tsv"):
            rows, delim = read_table(input_path)
            lines = [row[0] if row else "" for row in rows]
            summary["delimiter"] = "," if delim == "," else "\t"
        elif suffix in (".json",):
            pairs = read_json_pairs(input_path)
            lines = [p[0] for p in pairs]
        elif suffix in (".xlsx",):
            pairs_xlsx = read_xlsx_pairs(input_path)
            if pairs_xlsx is None:
                summary["error"] = "openpyxl not installed or failed to read xlsx"
                lines = []
            else:
                lines = [p[0] for p in pairs_xlsx]
        else:
            summary["error"] = f"Unsupported file type: {input_path.suffix}"
            lines = []
    except Exception as exc:
        summary["error"] = f"Analysis failed: {exc}"
        lines = []

    # Base line metrics
    summary.update(_summarize_lines(lines))

    # Load glossary index early so honorific detection can require matches against
    # glossary 'in' entries (honorifics must be attached to a speaker defined in glossary)
    gloss_map = _load_glossary_index()
    gloss_in_keys = set(gloss_map.keys())

    # Code & speaker metrics + tokenization
    sample_code_lines: List[int] = []
    per_line_tokens: List[int] = []
    for idx, line in enumerate(lines):
        cd = detect_code(line)
        if cd["has_code"]:
            lines_with_code += 1
            code_total += cd["count"]
            if len(sample_code_lines) < 5:
                sample_code_lines.append(idx + 1)
            # New detect_code returns actual code segments in spans: (start, end, code, type)
            for start, end, code_seg, code_type in cd["spans"]:
                if code_seg:
                    code_items[code_seg] = code_items.get(code_seg, 0) + 1
        sp = detect_speaker(line)
        if sp:
            # Normalize speaker name and skip generic/blacklisted names
            norm = _normalize_speaker(sp)
            if norm:
                speakers[norm] = speakers.get(norm, 0) + 1
                # Track which line indices belong to this speaker
                if norm not in speaker_lines:
                    speaker_lines[norm] = []
                speaker_lines[norm].append(idx)
        # RPG Maker variable / actor placeholders (case-sensitive \V[...] and \N[...])
        for m in RPGM_VAR_RE.finditer(line):
            var_id = m.group(1)
            var_key = f"V[{var_id}]"
            rpgm_vars[var_key] = rpgm_vars.get(var_key, 0) + 1
        for m in RPGM_ACTOR_RE.finditer(line):
            actor_id = m.group(1)
            actor_key = f"N[{actor_id}]"
            rpgm_actors[actor_key] = rpgm_actors.get(actor_key, 0) + 1
        # Honorific name detection: only count honorifics that are attached to a
        # speaker entry present in the glossary 'in' keys (i.e., exact match like
        # '花子ちゃん' in glossary). This prevents free-floating honorific mentions
        # from being counted.
        for m in HONORIFIC_RE.finditer(line):
            base = m.group(1).strip()
            suffix = m.group(2)
            if not base or not suffix:
                continue
            matched_full = f"{base}{suffix}"
            # Accept either the full form (base+suffix) or the base-only form
            # being present in the glossary 'in' keys. If the glossary contains
            # the speaker name without the suffix, treat occurrences of the
            # suffixed form as belonging to that speaker.
            try:
                target_key: Optional[str] = None
                if matched_full in gloss_in_keys:
                    target_key = matched_full
                elif base in gloss_in_keys:
                    target_key = base
                if target_key:
                    norm_s = _normalize_speaker(target_key)
                    if norm_s:
                        if norm_s not in speaker_suffix_counts:
                            speaker_suffix_counts[norm_s] = {}
                        speaker_suffix_counts[norm_s][suffix] = speaker_suffix_counts[norm_s].get(suffix, 0) + 1
            except Exception:
                # best-effort: skip any problems here
                pass
        # Token counting per line (populate per_line_tokens and total_tokens)
        try:
            tk, method = count_tokens(line)
        except Exception:
            tk, method = 0, "error"
        per_line_tokens.append(tk)
        total_tokens += tk
        if not token_method:
            token_method = method
    
    # Extended speaker detection: extract names from honorific usage in text
    # This catches speakers who are referred to by others but don't use "Name:" format
    honorific_names = extract_names_from_honorifics(lines)
    
    # Merge honorific-detected names into speakers dict
    # Only add if they meet frequency threshold (appear at least 3 times)
    HONORIFIC_NAME_MIN_FREQ = 3
    for name, count in honorific_names.items():
        if count >= HONORIFIC_NAME_MIN_FREQ:
            # Normalize the name (same pipeline as colon-detected speakers)
            norm = _normalize_speaker(name)
            if norm:
                # Add to speakers if new, or increment if already exists
                if norm not in speakers:
                    speakers[norm] = count
                    logging.debug("Detected name via honorific: %s (count=%d)", norm, count)
                else:
                    # Name already detected via colon - just log it was also found via honorific
                    logging.debug("Name %s found via honorific (%d times) - already in speakers", norm, count)
    
    # Second pass: analyze each speaker's lines for pronoun usage
    # Build regex patterns for each pronoun
    # Japanese pronouns need broad matching because they appear in many contexts.
    # Strategy: Match pronoun NOT followed by kanji/katakana (but hiragana particles are OK)
    # This excludes compounds like 俺たち、俺様 but includes 俺は、俺の、俺だ etc.
    pronoun_patterns = {}
    for pronoun_token in PRONOUN_LABELS.keys():
        # Match pronoun NOT followed by kanji or katakana
        # Negative lookahead: NOT followed by kanji (一-龯) or katakana (ァ-ン)
        # This allows hiragana particles (は、の、だ etc.) to follow
        pattern = re.compile(
            re.escape(pronoun_token) + r"(?![一-龯ァ-ン])"
        )
        pronoun_patterns[pronoun_token] = pattern
    
    # Count pronouns in each speaker's dialogue lines
    for speaker, line_indices in speaker_lines.items():
        pronoun_counts: Dict[str, int] = {}
        for idx in line_indices:
            if idx >= len(lines):
                continue
            ln = lines[idx]
            # Count pronouns using regex with negative lookahead for word boundaries
            for pronoun_token, pattern in pronoun_patterns.items():
                matches = pattern.findall(ln)
                count = len(matches)
                if count > 0:
                    pronoun_counts[pronoun_token] = pronoun_counts.get(pronoun_token, 0) + count
        if pronoun_counts:
            speaker_pronoun_counts[speaker] = pronoun_counts
    
    # Count honorifics attached to each speaker's name across ALL lines
    # (not just in their dialogue - we want to know how others refer to them)
    for line in lines:
        for m in HONORIFIC_RE.finditer(line):
            base_token = m.group(1)
            suffix = m.group(2)
            if not base_token or not suffix:
                continue
            
            # Normalize the base token to match against known speakers
            norm_base = _normalize_speaker(base_token)
            if not norm_base:
                continue
            
            # If this normalized base matches a known speaker, count the honorific
            if norm_base in speakers:
                if norm_base not in speaker_suffix_counts:
                    speaker_suffix_counts[norm_base] = {}
                speaker_suffix_counts[norm_base][suffix] = speaker_suffix_counts[norm_base].get(suffix, 0) + 1
    
    # Load estimation config (auto-creates if missing) and assets
    cfg = _load_or_create_config()
    jp_to_en_multiplier = cfg.jp_to_en_multiplier or OUTPUT_TOKEN_MULTIPLIER
    est_output_tokens = math.ceil(total_tokens * jp_to_en_multiplier)
    price = estimate_cost(total_tokens, est_output_tokens)

    # Build glossary (selected only) and prompt tokens
    input_text_full = "\n".join(lines)
    glossary_block, glossary_tokens, selected_gloss = _build_selected_glossary_block(input_text_full)
    prompt_tokens, prompt_method = _read_prompt_tokens()

    # Requests estimation per limiter modus (token limit applies to content only)
    overhead_tokens = prompt_tokens + glossary_tokens  # used for cost, not for limits
    effective_budget = max(1, cfg.max_input_tokens_per_request)
    reqs_by_tokens = max(1, math.ceil(total_tokens / effective_budget))
    reqs_by_lines = max(1, math.ceil(len(lines) / max(1, cfg.lines_per_request)))
    if cfg.limiter_modus == "TOKENS":
        est_reqs = reqs_by_tokens
    elif cfg.limiter_modus == "LINES":
        est_reqs = reqs_by_lines
    elif cfg.limiter_modus == "LOWER":
        est_reqs = max(reqs_by_lines, reqs_by_tokens)
    else:  # HIGHER
        est_reqs = min(reqs_by_lines, reqs_by_tokens)

    # Build chunking for per-request assets (glossary/prompt/rolling context) cost estimation
    def _chunk_by_lines(n: int) -> List[Tuple[int, int]]:
        size = max(1, n)
        chunks: List[Tuple[int, int]] = []
        i = 0
        L = len(lines)
        while i < L:
            j = min(L, i + size)
            chunks.append((i, j))
            i = j
        return chunks

    def _chunk_by_tokens(budget: int) -> List[Tuple[int, int]]:
        budget = max(1, budget)
        chunks: List[Tuple[int, int]] = []
        i = 0
        L = len(lines)
        while i < L:
            used = 0
            j = i
            # ensure at least one line per chunk
            while j < L and (used + per_line_tokens[j] <= budget or j == i):
                used += per_line_tokens[j]
                j += 1
            chunks.append((i, j))
            i = j
        return chunks

    if cfg.limiter_modus == "TOKENS":
        chunks = _chunk_by_tokens(cfg.max_input_tokens_per_request)
    elif cfg.limiter_modus == "LINES":
        chunks = _chunk_by_lines(cfg.lines_per_request)
    elif cfg.limiter_modus == "LOWER":
        # use the stricter plan (more chunks)
        chunks_t = _chunk_by_tokens(cfg.max_input_tokens_per_request)
        chunks_l = _chunk_by_lines(cfg.lines_per_request)
        chunks = chunks_t if len(chunks_t) >= len(chunks_l) else chunks_l
    else:  # HIGHER
        chunks_t = _chunk_by_tokens(cfg.max_input_tokens_per_request)
        chunks_l = _chunk_by_lines(cfg.lines_per_request)
        chunks = chunks_t if len(chunks_t) <= len(chunks_l) else chunks_l

    est_reqs = max(1, len(chunks))

    # Per-request glossary tokens (select only entries present in each chunk)
    total_glossary_tokens_all_reqs = 0
    first_request_glossary_block = ""
    for c_idx, (a, b) in enumerate(chunks):
        chunk_text = "\n".join(lines[a:b])
        block, tks, items = _build_selected_glossary_block(chunk_text)
        total_glossary_tokens_all_reqs += tks
        if c_idx == 0:
            first_request_glossary_block = block

    # Rolling context tokens (previous N lines included as input, not translated)
    rc = max(0, cfg.rolling_context_count)
    total_rc_tokens = 0
    if rc > 0:
        for idx, (a, _b) in enumerate(chunks):
            if idx == 0:
                continue
            # prev chunk end index
            prev_end = chunks[idx - 1][1]
            start_rc = max(chunks[idx - 1][0], prev_end - rc)
            if start_rc < prev_end:
                # sum token counts for those lines
                total_rc_tokens += sum(per_line_tokens[start_rc:prev_end])

    # Prompt tokens per request
    total_prompt_tokens_all_reqs = prompt_tokens * est_reqs

    # Total billed input tokens (content + per-request prompt + per-request glossary + rolling context)
    billed_input_tokens_total = total_tokens + total_prompt_tokens_all_reqs + total_glossary_tokens_all_reqs + total_rc_tokens

    # --- Duplicate-based savings estimate ---------------------------------
    # Compute tokens that are from duplicate occurrences (tokens that could be
    # removed if exact duplicate lines are de-duplicated prior to translation).
    # Simple (exact-line) deduplication: baseline fast heuristic
    dedup_total_tokens = 0
    seen_lines = set()
    for ln, tk in zip(lines, per_line_tokens):
        if ln not in seen_lines:
            seen_lines.add(ln)
            dedup_total_tokens += tk
    duplicate_tokens_total = max(0, total_tokens - dedup_total_tokens)
    duplicate_lines_total = max(0, summary.get("duplicate_lines", 0))

    # Prepare baseline dedup counts (simple dedup)
    dedup_line_count = len(seen_lines)
    reqs_by_tokens_after = max(1, math.ceil(dedup_total_tokens / max(1, cfg.max_input_tokens_per_request)))
    reqs_by_lines_after = max(1, math.ceil(dedup_line_count / max(1, cfg.lines_per_request)))
    if cfg.limiter_modus == "TOKENS":
        est_reqs_after = reqs_by_tokens_after
    elif cfg.limiter_modus == "LINES":
        est_reqs_after = reqs_by_lines_after
    elif cfg.limiter_modus == "LOWER":
        est_reqs_after = max(reqs_by_lines_after, reqs_by_tokens_after)
    else:
        est_reqs_after = min(reqs_by_lines_after, reqs_by_tokens_after)

    # Scale per-request assets proportionally to change in estimated requests (baseline)
    if est_reqs and est_reqs > 0:
        glossary_tokens_after = round(total_glossary_tokens_all_reqs * est_reqs_after / est_reqs)
        rc_tokens_after = round(total_rc_tokens * est_reqs_after / est_reqs)
    else:
        glossary_tokens_after = 0
        rc_tokens_after = 0
    prompt_tokens_after = prompt_tokens * est_reqs_after

    billed_input_tokens_after = dedup_total_tokens + prompt_tokens_after + glossary_tokens_after + rc_tokens_after
    est_output_tokens_after = math.ceil(dedup_total_tokens * jp_to_en_multiplier)
    cost_after = estimate_cost(billed_input_tokens_after, est_output_tokens_after)

    # Aggressive dedup (optional additional step): normalize then dedup; compute separate estimate and log it
    aggressive_result: Optional[Dict[str, Any]] = None
    if cfg.aggressive_dedup:
        # Build a mapping of normalized string -> token count (count tokens on
        # the normalized string itself for a more accurate aggressive dedup estimate).
        norm_token_counts: Dict[str, int] = {}
        norm_token_method = ""
        for ln in lines:
            norm = _normalize_for_dedup(ln)
            # Treat empty normalized strings as their own bucket
            if norm not in norm_token_counts:
                tk, method2 = count_tokens(norm)
                norm_token_counts[norm] = tk
                if not norm_token_method:
                    norm_token_method = method2
        aggr_dedup_total_tokens = sum(norm_token_counts.values())
        aggr_dedup_line_count = len(norm_token_counts)
        aggr_duplicate_tokens_total = max(0, total_tokens - aggr_dedup_total_tokens)

        # Estimate requests after aggressive dedup
        aggr_reqs_by_tokens_after = max(1, math.ceil(aggr_dedup_total_tokens / max(1, cfg.max_input_tokens_per_request)))
        aggr_reqs_by_lines_after = max(1, math.ceil(aggr_dedup_line_count / max(1, cfg.lines_per_request)))
        if cfg.limiter_modus == "TOKENS":
            aggr_est_reqs_after = aggr_reqs_by_tokens_after
        elif cfg.limiter_modus == "LINES":
            aggr_est_reqs_after = aggr_reqs_by_lines_after
        elif cfg.limiter_modus == "LOWER":
            aggr_est_reqs_after = max(aggr_reqs_by_lines_after, aggr_reqs_by_tokens_after)
        else:
            aggr_est_reqs_after = min(aggr_reqs_by_lines_after, aggr_reqs_by_tokens_after)

        if est_reqs and est_reqs > 0:
            aggr_glossary_tokens_after = round(total_glossary_tokens_all_reqs * aggr_est_reqs_after / est_reqs)
            aggr_rc_tokens_after = round(total_rc_tokens * aggr_est_reqs_after / est_reqs)
        else:
            aggr_glossary_tokens_after = 0
            aggr_rc_tokens_after = 0
        aggr_prompt_tokens_after = prompt_tokens * aggr_est_reqs_after

        aggr_billed_input_tokens_after = aggr_dedup_total_tokens + aggr_prompt_tokens_after + aggr_glossary_tokens_after + aggr_rc_tokens_after
        aggr_est_output_tokens_after = math.ceil(aggr_dedup_total_tokens * jp_to_en_multiplier)
        aggr_cost_after = estimate_cost(aggr_billed_input_tokens_after, aggr_est_output_tokens_after)

        aggressive_result = {
            "dedup_content_input_tokens": aggr_dedup_total_tokens,
            "dedup_token_method": norm_token_method or "unknown",
            "duplicate_tokens_total": aggr_duplicate_tokens_total,
            "dedup_line_count": aggr_dedup_line_count,
            "estimated_requests_after_dedup": aggr_est_reqs_after,
            "billed_input_tokens_after_dedup": aggr_billed_input_tokens_after,
            "estimated_output_tokens_after_dedup": aggr_est_output_tokens_after,
            "estimated_cost_after_dedup_usd": aggr_cost_after,
        }

    # Estimate requests after deduplication (using same limiter rules but with
    # deduplicated content and deduplicated line counts). This is a heuristic
    # estimate to show potential savings; it assumes prompt/glossary scale with
    # number of requests.
    dedup_line_count = len(seen_lines)
    reqs_by_tokens_after = max(1, math.ceil(dedup_total_tokens / max(1, cfg.max_input_tokens_per_request)))
    reqs_by_lines_after = max(1, math.ceil(dedup_line_count / max(1, cfg.lines_per_request)))
    if cfg.limiter_modus == "TOKENS":
        est_reqs_after = reqs_by_tokens_after
    elif cfg.limiter_modus == "LINES":
        est_reqs_after = reqs_by_lines_after
    elif cfg.limiter_modus == "LOWER":
        est_reqs_after = max(reqs_by_lines_after, reqs_by_tokens_after)
    else:
        est_reqs_after = min(reqs_by_lines_after, reqs_by_tokens_after)

    # Scale per-request assets proportionally to change in estimated requests
    if est_reqs and est_reqs > 0:
        glossary_tokens_after = round(total_glossary_tokens_all_reqs * est_reqs_after / est_reqs)
        rc_tokens_after = round(total_rc_tokens * est_reqs_after / est_reqs)
    else:
        glossary_tokens_after = 0
        rc_tokens_after = 0
    prompt_tokens_after = prompt_tokens * est_reqs_after

    billed_input_tokens_after = dedup_total_tokens + prompt_tokens_after + glossary_tokens_after + rc_tokens_after
    est_output_tokens_after = math.ceil(dedup_total_tokens * jp_to_en_multiplier)
    cost_after = estimate_cost(billed_input_tokens_after, est_output_tokens_after)

    # Savings
    # Ensure original baseline cost uses billed input tokens (content + per-request assets)
    original_cost = estimate_cost(billed_input_tokens_total, est_output_tokens)
    original_total_usd = original_cost.get("total_usd", 0.0)
    after_total_usd = cost_after.get("total_usd", 0.0)
    savings_usd = round(max(0.0, original_total_usd - after_total_usd), 4)
    savings_pct = round((savings_usd / original_total_usd) * 100, 2) if original_total_usd > 0 else 0.0
    # If aggressive dedup ran, compute its savings too and attach into aggressive_result
    if aggressive_result is not None:
        try:
            aggr_total_usd = aggr_cost_after.get("total_usd", 0.0) if isinstance(aggr_cost_after, dict) else aggr_cost_after.get("total_usd", 0.0)
        except Exception:
            aggr_total_usd = 0.0
        aggr_savings_usd = round(max(0.0, original_total_usd - aggr_total_usd), 4) if original_total_usd > 0 else 0.0
        aggr_savings_pct = round((aggr_savings_usd / original_total_usd) * 100, 2) if original_total_usd > 0 else 0.0
        aggressive_result.update({
            "savings_usd": aggr_savings_usd,
            "savings_percent": aggr_savings_pct,
        })
    # Populate additional duplicate-line metrics into the top-level summary
    try:
        baseline_dup_lines = int(summary.get("duplicate_lines", 0)) if isinstance(summary, dict) else 0
    except Exception:
        baseline_dup_lines = 0
    if aggressive_result is not None:
        aggr_dedup_line_count_val = int(aggressive_result.get("dedup_line_count", 0))
        total_dup_after_aggr = max(0, len(lines) - aggr_dedup_line_count_val)
        additional_dup_lines = max(0, total_dup_after_aggr - baseline_dup_lines)
    else:
        total_dup_after_aggr = baseline_dup_lines
        additional_dup_lines = 0
    # Write back into the existing summary dict (these keys were created as placeholders)
    try:
        summary["additional_duplicate_lines"] = additional_dup_lines
        summary["total_duplicate_lines"] = total_dup_after_aggr
    except Exception:
        pass
    # -----------------------------------------------------------------------

    # Language analysis (vocabulary variety and bad habits)
    try:
        lang = analyze_language(lines)
    except Exception:
        lang = {}

    summary.update(
        {
            "code": {
                "lines_with_code": lines_with_code,
                "code_segment_count": code_total,
                "sample_lines": sample_code_lines,
            },
            "speakers": {
                # Keep only aggregate speaker counts in the main summary.
                "count_lines_with_speaker": sum(speakers.values()),
                "unique_speakers": len(speakers),
                "top": sorted(speakers.items(), key=lambda x: x[1], reverse=True),  # All speakers, not just top 10
                # honorifics attached to speakers (from speaker_suffix_counts)
                "honorific_total": sum(
                    sum(d.values()) for d in speaker_suffix_counts.values()
                ),
                "honorific_unique": sum(len(d) for d in speaker_suffix_counts.values()),
                # honorific_top is list of ((speaker, suffix), count)
                "honorific_top": sorted(
                    [((sp, sfx), cnt) for sp, d in speaker_suffix_counts.items() for sfx, cnt in d.items()],
                    key=lambda x: x[1],
                    reverse=True,
                )[:10],
                "rpgm_variables_total": sum(rpgm_vars.values()),
                "rpgm_variables_unique": len(rpgm_vars),
                "rpgm_variables_top": sorted(rpgm_vars.items(), key=lambda x: x[1], reverse=True)[:10],
                "rpgm_actors_total": sum(rpgm_actors.values()),
                "rpgm_actors_unique": len(rpgm_actors),
                "rpgm_actors_top": sorted(rpgm_actors.items(), key=lambda x: x[1], reverse=True)[:10],
            },
            "tokens": {
                "method": token_method or "unknown",
                "content_input_tokens": total_tokens,
                "estimated_output_tokens": est_output_tokens,
                "pricing_usd": estimate_cost(billed_input_tokens_total, est_output_tokens),
                "jp_to_en_multiplier": jp_to_en_multiplier,
                "prompt_tokens_per_request": prompt_tokens,
                "prompt_token_method": prompt_method,
                "input_tokens_total": billed_input_tokens_total,
                "glossary_tokens_total_all_requests": total_glossary_tokens_all_reqs,
                "rolling_context_tokens_total": total_rc_tokens,
                "duplicate_savings": {
                    "duplicate_lines_total": duplicate_lines_total,
                    "duplicate_tokens_total": duplicate_tokens_total,
                    "dedup_content_input_tokens": dedup_total_tokens,
                    "estimated_requests_after_dedup": est_reqs_after,
                    "billed_input_tokens_after_dedup": billed_input_tokens_after,
                    "estimated_output_tokens_after_dedup": est_output_tokens_after,
                    "estimated_cost_after_dedup_usd": cost_after,
                    "savings_usd": savings_usd,
                    "savings_percent": savings_pct,
                    "aggressive": aggressive_result,
                },
            },
            "batch_estimate": {
                "lines_per_request": cfg.lines_per_request,
                "max_input_tokens_per_request": cfg.max_input_tokens_per_request,
                "limiter_modus": cfg.limiter_modus,
                "prompt_tokens_per_request": prompt_tokens,
                "glossary_tokens_per_request_avg": (total_glossary_tokens_all_reqs / est_reqs) if est_reqs else 0,
                "rolling_context_lines": cfg.rolling_context_count,
                "estimated_requests": est_reqs,
                "reqs_by_lines": reqs_by_lines,
                "reqs_by_tokens": reqs_by_tokens,
                "notes": "Token limit applies to content only. Prompt/glossary/rolling-context are billed per request but do not reduce the token limit.",
            },
            "glossary": {
                "selected_unique_total": len(selected_gloss),
                "print_block_first_request": first_request_glossary_block,
            },
            "config": {
                "path": str(cfg.path) if cfg.path else None,
                "created": cfg.created,
                "prompt_path": str((_get_config_dir() / PROMPT_FILENAME).resolve()),
                "glossary_path": str((_get_config_dir() / GLOSSARY_FILENAME).resolve()),
            },
            "language": lang,
        }
    )
    # --- Prepare sanitized summary for logging/written logs (remove file paths)
    def _scrub_paths(obj: Any) -> Any:
        """Return a copy of obj with any path-like strings redacted or shortened.

        Keys containing 'path' are replaced with their basename. Any string that
        looks like an absolute path on Windows (e.g. C:\\...) or Unix (/...) is
        replaced with its basename to avoid leaking file paths in logs.
        """
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if isinstance(k, str) and "path" in k.lower():
                    # redact path-like keys
                    try:
                        out[k] = os.path.basename(str(v)) if v else None
                    except Exception:
                        out[k] = None
                else:
                    out[k] = _scrub_paths(v)
            return out
        if isinstance(obj, list):
            return [_scrub_paths(x) for x in obj]
        if isinstance(obj, str):
            # Windows absolute path (C:\...), or Unix (/...)
            if re.match(r"^[A-Za-z]:\\|^/", obj):
                try:
                    return os.path.basename(obj)
                except Exception:
                    return "<path>"
            return obj
        return obj

    sanitized = _scrub_paths(summary)

    # Log a concise summary (sanitized)
    try:
        logging.info("Analysis for %s: %s", input_path.name, json.dumps(sanitized, ensure_ascii=False))
    except Exception:
        # fallback to non-json logging
        logging.info("Analysis for %s: summary written", input_path.name)

    # Also write a standalone analysis log file for easy review (sanitized)
    try:
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = logs_dir / f"{input_path.stem}.analysis.{stamp}.log"
        out.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # Best-effort; do not raise
        pass

    # Write compact speakers and code log (CSV-like, single-line entries)
    try:
        from datetime import datetime, timezone as _tz

        sp_stamp = stamp if 'stamp' in locals() else datetime.now(_tz.utc).strftime("%Y%m%dT%H%M%SZ")
        sp_out = logs_dir / f"{input_path.stem}.speakers.{sp_stamp}.log"

        # Prepare speaker rows with glossary enrichment (only for speaker names)
        gloss_map = _load_glossary_index()
        sorted_counts = sorted(speakers.items(), key=lambda x: x[1], reverse=True)
        
        # Import speaker validation from glossary module
        try:
            from .glossary import _is_valid_speaker_entry
        except Exception:
            from CherryAI.functions.glossary import _is_valid_speaker_entry
        
        # Build sorted honorific list from speaker_suffix_counts: entries are ((speaker, suffix), count)
        honor_list = [((sp, sfx), cnt) for sp, d in speaker_suffix_counts.items() for sfx, cnt in d.items()]
        sorted_honorific = sorted(honor_list, key=lambda x: x[1], reverse=True)
        sorted_rpgm_vars = sorted(rpgm_vars.items(), key=lambda x: x[1], reverse=True)
        sorted_rpgm_actors = sorted(rpgm_actors.items(), key=lambda x: x[1], reverse=True)

        lines_out: List[str] = []
        lines_out.append("Speakers")
        lines_out.append("name,count,glossary_hit,out,note")
        for name, cnt in sorted_counts:
            # Skip invalid speakers (same validation as glossary)
            if not _is_valid_speaker_entry(name, cnt):
                continue
            
            # Exact match on glossary 'in' key only when name is detected as speaker
            if name in gloss_map:
                out_tr, note = gloss_map[name]
                row = [name, str(cnt), "true", out_tr or "", note or ""]
            else:
                row = [name, str(cnt), "false", "", ""]
            
            # Infer gender/style if glossary note is empty
            if not row[4]:  # note column is empty
                inference_parts: List[str] = []
                # Find top 2 pronouns for this speaker
                if name in speaker_pronoun_counts:
                    pronoun_items = sorted(speaker_pronoun_counts[name].items(), key=lambda x: x[1], reverse=True)[:2]
                    for pron, pron_count in pronoun_items:
                        # Romanize the pronoun
                        try:
                            from .glossary import romanize_pronoun, PRONOUN_GENDER
                        except Exception:
                            from CherryAI.functions.glossary import romanize_pronoun, PRONOUN_GENDER
                        
                        romanized = romanize_pronoun(pron)
                        gender = PRONOUN_GENDER.get(romanized, "unknown")
                        inference_parts.append(f"{romanized}:{gender}:{pron_count}")
                
                # Find top 2 suffixes for this speaker
                if name in speaker_suffix_counts:
                    suffix_items = sorted(speaker_suffix_counts[name].items(), key=lambda x: x[1], reverse=True)[:2]
                    for sfx, sfx_count in suffix_items:
                        # Romanize the honorific
                        try:
                            from .glossary import romanize_honorific, HONORIFIC_GENDER
                        except Exception:
                            from CherryAI.functions.glossary import romanize_honorific, HONORIFIC_GENDER
                        
                        romanized = romanize_honorific(sfx)
                        gender = HONORIFIC_GENDER.get(romanized, "unknown")
                        inference_parts.append(f"{romanized}:{gender}:{sfx_count}")
                
                if inference_parts:
                    row[4] = " | ".join(inference_parts)
            
            # CSV-escape minimal: quote fields containing commas/quotes/newlines
            def _csv_field(v: str) -> str:
                if any(ch in v for ch in [',', '"', '\n', '\r']):
                    return '"' + v.replace('"', '""') + '"'
                return v

            lines_out.append(",".join(_csv_field(x) for x in row))

        # Honorific names (base + suffix) - romanized
        lines_out.append("")
        lines_out.append("Honorifics")
        lines_out.append("base_name,suffix,count")
        for hs_key, cnt in sorted_honorific:
            # key may be a tuple (base, suffix)
            if isinstance(hs_key, (list, tuple)) and len(hs_key) == 2:
                base, suffix = hs_key
            else:
                base, suffix = str(hs_key), ""
            
            # Romanize the suffix
            try:
                from .glossary import romanize_honorific
            except Exception:
                from CherryAI.functions.glossary import romanize_honorific
            
            sfx_romanized = romanize_honorific(suffix)
            
            # minimal CSV-escape
            def _esc_field(x: str) -> str:
                if any(ch in x for ch in [',', '"', '\n', '\r']):
                    return '"' + x.replace('"', '""') + '"'
                return x
            lines_out.append(f"{_esc_field(base)},{_esc_field(sfx_romanized)},{cnt}")

        # RPG Maker variables
        lines_out.append("")
        lines_out.append("RPGMVariables")
        lines_out.append("variable,count")
        for v_name, cnt in sorted_rpgm_vars:
            vv = v_name
            if any(ch in vv for ch in [',', '"', '\n', '\r']):
                vv = '"' + vv.replace('"', '""') + '"'
            lines_out.append(f"{vv},{cnt}")

        # RPG Maker actors
        lines_out.append("")
        lines_out.append("RPGMActors")
        lines_out.append("actor,count")
        for actor_name, cnt in sorted_rpgm_actors:
            aa = actor_name
            if any(ch in aa for ch in [',', '"', '\n', '\r']):
                aa = '"' + aa.replace('"', '""') + '"'
            lines_out.append(f"{aa},{cnt}")

        # Prepare code rows (normalized aggregation for similarity)
        lines_out.append("")
        lines_out.append("Code")
        lines_out.append("code,count")
        norm_counts: Dict[str, int] = {}
        for seg, c in code_items.items():
            norm = _normalize_code_segment(seg)
            norm_counts[norm] = norm_counts.get(norm, 0) + int(c)
        for code_str, cnt in sorted(norm_counts.items(), key=lambda x: x[1], reverse=True):
            # CSV-escape as above
            cs = code_str
            if cs is None:
                cs = ""
            if any(ch in cs for ch in [',', '"', '\n', '\r']):
                cs = '"' + cs.replace('"', '""') + '"'
            lines_out.append(f"{cs},{cnt}")

        sp_out.write_text("\r\n".join(lines_out), encoding="utf-8")
    except Exception:
        pass

    # Add pronoun and honorific data to summary for glossary update
    summary["speaker_pronoun_counts"] = speaker_pronoun_counts
    summary["speaker_suffix_counts"] = speaker_suffix_counts
    # TASK 59.7: Filter out ignored patterns from code_items
    summary["code_items"] = filter_ignored_patterns(code_items)

    # Create or update a manifest to persist original lines as part of analysis
    try:
        man_path = create_or_update_manifest(input_path, logs_dir)
        summary["manifest_path"] = str(man_path)
    except Exception as _exc:
        summary["manifest_error"] = str(_exc)

    return summary


# ---------------- Manifest creation/update helpers ---------------- #

SIMILARITY_THRESHOLD = 0.10  # 10%


def _align_lines(old: List[str], new: List[str]) -> List[Tuple[Optional[int], Optional[int]]]:
    """Return alignment pairs of indices (old_idx, new_idx) using difflib.

    When a line is inserted/deleted, one side will be None. Matches are 1:1.
    """
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    mapping: List[Tuple[Optional[int], Optional[int]]] = []
    a_i = b_i = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mapping.append((i1 + k, j1 + k))
            a_i, b_i = i2, j2
        elif tag == "replace":
            # fall back to pairwise until one side exhausts
            span = min(i2 - i1, j2 - j1)
            for k in range(span):
                mapping.append((i1 + k, j1 + k))
            for k in range(span, i2 - i1):
                mapping.append((i1 + k, None))
            for k in range(span, j2 - j1):
                mapping.append((None, j1 + k))
            a_i, b_i = i2, j2
        elif tag == "delete":
            for k in range(i1, i2):
                mapping.append((k, None))
            a_i = i2
        elif tag == "insert":
            for k in range(j1, j2):
                mapping.append((None, k))
            b_i = j2
    return mapping


def create_or_update_manifest(input_path: Path, logs_dir: Path, manifest_path: Optional[Path] = None) -> Path:
    """Create a new manifest recording original lines, or update an existing one if provided.

    - Writes original_lines and pre_lines (identical at this stage) into mappings
    - If manifest_path exists, tries to align existing lines to new lines; if >=10% match
      is achieved, updates the manifest with moved/inserted lines accordingly.
    - Returns the path to the written manifest JSON.
    """
    input_path = Path(input_path)
    logs_dir = Path(logs_dir)
    if input_path.suffix.lower() in (".csv", ".tsv"):
        rows, _ = read_table(input_path)
        new_lines = [row[0] if row else "" for row in rows]
    elif input_path.suffix.lower() == ".json":
        pairs = read_json_pairs(input_path)
        new_lines = [p[0] for p in pairs]
    elif input_path.suffix.lower() == ".xlsx":
        pairs = read_xlsx_pairs(input_path) or []
        new_lines = [p[0] for p in pairs]
    else:
        new_lines = read_text(input_path).splitlines()

    # Load existing manifest only if explicit manifest_path is provided (i.e., via Load Manifest)
    existing = None
    if manifest_path and Path(manifest_path).exists():
        try:
            data = json.loads(read_text(Path(manifest_path)))
            existing = Manifest.from_dict(data)
        except Exception:
            existing = None

    # Determine manifests directory within the project
    # Prefer colocated CherryAI/manifests relative to this module
    try:
        here = Path(__file__).resolve()
        manifests_dir = here.parent.parent / "manifests"
    except Exception:
        manifests_dir = Path("manifests")
    manifests_dir.mkdir(parents=True, exist_ok=True)

    if existing is None:
        # Create fresh manifest with originals; always write into manifests folder
        man = Manifest(
            summary=f"Analysis-init for {input_path.name}",
            metadata={"created_utc": "", "version": "1.0", "input_file": str(input_path)},
            operations=[],
        )
        man.mappings["original_lines"] = list(new_lines)
        man.mappings["pre_lines"] = list(new_lines)
        man.mappings["enabled_operations"] = []
        # Target path: manifests/<stem>.CherryAI.json (ignore provided path for new)
        man_path = manifests_dir / f"{input_path.stem}.CherryAI.json"
        write_text(man_path, json.dumps(man.to_pretty_dict(), ensure_ascii=False, indent=2))
        return man_path

    # Update existing manifest if enough similarity
    old_lines = existing.mappings.get("original_lines") or []
    if not isinstance(old_lines, list):
        old_lines = []
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    ratio = sm.quick_ratio()
    # Allow update if either condition holds: similarity >=10% OR at least 10k lines match exactly
    try:
        matching_blocks = sm.get_matching_blocks()
        matched_lines = sum(bsize for (_a, _b, bsize) in matching_blocks)
    except Exception:
        matched_lines = 0
    allow_update = (ratio >= SIMILARITY_THRESHOLD) or (matched_lines >= 10_000)
    if not allow_update:
        # Not allowed to update; write a fresh manifest into manifests folder
        man = Manifest(
            summary=f"Analysis-init for {input_path.name}",
            metadata={"created_utc": "", "version": "1.0", "input_file": str(input_path)},
            operations=existing.operations,
        )
        man.mappings = dict(existing.mappings)
        man.mappings["original_lines"] = list(new_lines)
        man.mappings["pre_lines"] = list(new_lines)
        out_path = manifests_dir / f"{input_path.stem}.CherryAI.json"
        write_text(out_path, json.dumps(man.to_pretty_dict(), ensure_ascii=False, indent=2))
        return out_path

    # Similar enough: align and update original and overwrite lines preserving order
    alignment = _align_lines(old_lines, new_lines)
    updated_originals: List[str] = []
    old_overwrites = existing.mappings.get("overwrite_lines") or []
    if not isinstance(old_overwrites, list):
        old_overwrites = []
    updated_overwrites: List[str] = []
    for old_idx, new_idx in alignment:
        if new_idx is not None:
            updated_originals.append(new_lines[new_idx])
            if old_idx is not None and 0 <= old_idx < len(old_overwrites):
                updated_overwrites.append(old_overwrites[old_idx])
            else:
                updated_overwrites.append("")
        elif old_idx is not None:
            # deleted in new version; skip or keep placeholder
            continue
    existing.mappings["original_lines"] = list(updated_originals)
    existing.mappings["pre_lines"] = list(updated_originals)
    # Carry overwrite lines forward aligned to new structure
    if updated_overwrites:
        existing.mappings["overwrite_lines"] = list(updated_overwrites)
    assert manifest_path is not None
    out_path = Path(manifest_path)
    write_text(out_path, json.dumps(existing.to_pretty_dict(), ensure_ascii=False, indent=2))
    return out_path


# ---------------- Language analysis (vocabulary + habits) ---------------- #

_WORD_RE = re.compile(r"[A-Za-z]+")
_COMMA_AND_RE = re.compile(r",\s+and\b", re.IGNORECASE)
_HYPHEN_WORD_RE = re.compile(r"\b[A-Za-z]+-[A-Za-z]+\b")


def _is_sfx_word(w: str) -> bool:
    """Heuristic for SFX-like tokens.

    - Repeating same character: len>=3 and all chars identical (e.g., "zzz", "!!!!!")
    - Only consonants: letters only, at least 2 letters, contains no AEIOU (case-insensitive)
    """
    if not w:
        return False
    lw = w.lower()
    if len(lw) >= 3 and all(ch == lw[0] for ch in lw):
        return True
    # consonants-only heuristic
    if lw.isalpha() and len(lw) >= 2 and not any(v in lw for v in "aeiou"):
        return True
    return False


def analyze_language(lines: List[str]) -> Dict[str, Any]:
    """Return language metrics: vocabulary variety and selected bad habits.

    Output keys:
    - words: { total, unique_total, unique_non_sfx, sfx_total, sfx_unique, top_words, top_sfx }
    - bad_habits:
        - comma_and: { count, sample_lines }
        - hyphenated: { count, unique_forms, top_forms, sample_lines }
    """
    total_words = 0
    freq: Dict[str, int] = {}
    sfx_freq: Dict[str, int] = {}

    # Collect words and classify SFX
    for ln in lines:
        for m in _WORD_RE.finditer(ln):
            w = m.group(0).lower()
            total_words += 1
            if _is_sfx_word(w):
                sfx_freq[w] = sfx_freq.get(w, 0) + 1
            else:
                freq[w] = freq.get(w, 0) + 1

    # Build word stats
    top_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:20]
    top_sfx = sorted(sfx_freq.items(), key=lambda x: x[1], reverse=True)[:20]
    words_section = {
        "total": total_words,
        "unique_total": len(freq) + len(sfx_freq),
        "unique_non_sfx": len(freq),
        "sfx_total": sum(sfx_freq.values()),
        "sfx_unique": len(sfx_freq),
        "top_words": top_words,
        "top_sfx": top_sfx,
    }

    # Comma usage
    total_commas = 0
    per_line_commas: List[Tuple[int, int]] = []  # (line_no, count)
    for i, ln in enumerate(lines, start=1):
        c = ln.count(",")
        if c:
            total_commas += c
            if ANALYSIS_INCLUDE_SAMPLES and len(per_line_commas) < 50:
                per_line_commas.append((i, c))

    # Bad habit: ", and"
    comma_and_count = 0
    comma_and_lines: List[int] = []
    for i, ln in enumerate(lines, start=1):
        matches = list(_COMMA_AND_RE.finditer(ln))
        if matches:
            comma_and_count += len(matches)
            if ANALYSIS_INCLUDE_SAMPLES and len(comma_and_lines) < 20:
                comma_and_lines.append(i)

    # Bad habit: hyphenated words
    hyphen_count = 0
    hyphen_forms: Dict[str, int] = {}
    hyphen_lines: List[int] = []
    for i, ln in enumerate(lines, start=1):
        matches = list(_HYPHEN_WORD_RE.finditer(ln))
        if matches:
            hyphen_count += len(matches)
            if ANALYSIS_INCLUDE_SAMPLES and len(hyphen_lines) < 20:
                hyphen_lines.append(i)
            for m in matches:
                form = m.group(0).lower()
                hyphen_forms[form] = hyphen_forms.get(form, 0) + 1

    top_hyphen = sorted(hyphen_forms.items(), key=lambda x: x[1], reverse=True)[:20]

    habits_section = {
        "comma_and": {"count": comma_and_count, "sample_lines": comma_and_lines},
        "hyphenated": {
            "count": hyphen_count,
            "unique_forms": len(hyphen_forms),
            "top_forms": top_hyphen,
            "sample_lines": hyphen_lines,
        },
    }

    # Sentence length analysis (split on . ? ! and measure words)
    sentence_end_re = re.compile(r"[\.\?!]+")
    sentence_word_counts: List[int] = []
    sentence_samples: List[Tuple[int, str, int]] = []  # (line_no, sentence, word_count)
    for i, ln in enumerate(lines, start=1):
        parts = [p.strip() for p in sentence_end_re.split(ln) if p.strip()]
        for s in parts:
            wc = len(_WORD_RE.findall(s))
            sentence_word_counts.append(wc)
            if ANALYSIS_INCLUDE_SAMPLES and wc and len(sentence_samples) < 20:
                sentence_samples.append((i, s if len(s) <= 200 else s[:197] + "...", wc))

    import statistics as _st
    if sentence_word_counts:
        sent_avg = round(_st.mean(sentence_word_counts), 2)
        sent_median = _st.median(sentence_word_counts)
        sent_max = max(sentence_word_counts)
    else:
        sent_avg = sent_median = sent_max = 0

    sentence_section = {
        "total_sentences": len(sentence_word_counts),
        "avg_words": sent_avg,
        "median_words": sent_median,
        "max_words": sent_max,
        "samples": sentence_samples,
    }

    # Combine language analysis
    lang = {
        "words": words_section,
        "bad_habits": habits_section,
        "commas": {"total_commas": total_commas, "per_line": per_line_commas},
        "sentences": sentence_section,
    }
    return lang


# ============================================================================
# Point of View Inference (Phase 54)
# ============================================================================

# -- Pronoun pattern database (Task 54.1) ------------------------------------
# Each entry maps a language key to a dict of POV → list of patterns.
# Patterns are compiled once and cached via _get_pov_patterns().

_RAW_POV_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "japanese": {
        "1st": [
            r"私", r"僕", r"俺", r"わたし", r"ぼく", r"おれ",
            r"あたし", r"我", r"わし", r"拙者", r"某",
            r"ウチ", r"うち", r"オレ", r"ボク", r"ワタシ",
            r"アタシ", r"オイラ",
        ],
        "2nd": [
            r"あなた", r"君", r"きみ", r"お前", r"おまえ",
            r"てめえ", r"貴方", r"貴様", r"そなた", r"キミ",
            r"アンタ", r"あんた", r"オマエ",
        ],
    },
    "english": {
        "1st": [
            r"\bI\b", r"\bmy\b", r"\bmine\b", r"\bme\b",
            r"\bmyself\b", r"\bwe\b", r"\bour\b", r"\bours\b",
        ],
        "2nd": [
            r"\byou\b", r"\byour\b", r"\byours\b", r"\byourself\b",
        ],
    },
    "chinese": {
        "1st": [r"我", r"咱", r"余", r"吾"],
        "2nd": [r"你", r"您", r"汝"],
    },
    "korean": {
        "1st": [r"나", r"저", r"제"],
        "2nd": [r"너", r"당신", r"그대"],
    },
}

# Compiled cache
_COMPILED_POV: Dict[str, Dict[str, List[re.Pattern]]] = {}


def _get_pov_patterns(
    language: str,
) -> Dict[str, List[re.Pattern]]:
    """Return compiled POV regex patterns for *language*.

    Args:
        language: Language key (lowercase).  Falls back to ``"japanese"``
            when the key is not found.

    Returns:
        Dict mapping ``"1st"`` / ``"2nd"`` to lists of compiled patterns.
    """
    lang_key = language.lower()
    if lang_key not in _RAW_POV_PATTERNS:
        lang_key = "japanese"  # default

    if lang_key not in _COMPILED_POV:
        # English patterns use word boundaries and need case-insensitive
        flags = re.IGNORECASE if lang_key == "english" else 0
        compiled: Dict[str, List[re.Pattern]] = {}
        for pov, pats in _RAW_POV_PATTERNS[lang_key].items():
            compiled[pov] = [re.compile(p, flags) for p in pats]
        _COMPILED_POV[lang_key] = compiled

    return _COMPILED_POV[lang_key]


# -- POV detection algorithm (Task 54.2) -------------------------------------

@dataclass
class POVResult:
    """Result of point-of-view inference.

    Attributes:
        pov: Detected perspective (``"1st"``, ``"2nd"``, ``"3rd"``,
            ``"mixed"``, or ``"unknown"``).
        confidence: ``"high"`` when the dominant POV accounts for
            >60 % of pronoun matches; ``"low"`` otherwise.
        counts: Per-POV match counts.
        total_narrative_lines: Number of lines analysed.
    """

    pov: str = "unknown"
    confidence: str = "low"
    counts: Dict[str, int] = field(default_factory=dict)
    total_narrative_lines: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "pov": self.pov,
            "confidence": self.confidence,
            "counts": dict(self.counts),
            "total_narrative_lines": self.total_narrative_lines,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "POVResult":
        """Deserialise from dictionary."""
        return cls(
            pov=str(data.get("pov", "unknown")),
            confidence=str(data.get("confidence", "low")),
            counts=dict(data.get("counts", {})),
            total_narrative_lines=int(data.get("total_narrative_lines", 0)),
        )


def detect_pov(
    lines: List[str],
    language: str = "japanese",
    protagonist_name: str = "",
    context_markers: Optional[List[Optional[str]]] = None,
) -> POVResult:
    """Infer the narrative point of view from non-dialogue lines.

    Filters out dialogue (speaker prefix) and menu/choice lines, then
    counts pronoun occurrences for 1st and 2nd person.  3rd person is
    inferred when the protagonist name appears frequently and
    1st/2nd counts are low.

    Args:
        lines: Raw text lines.
        language: Source language key (``"japanese"``, ``"english"``, etc.).
        protagonist_name: Protagonist name from Character Notes (used for
            3rd-person detection).  Empty string disables 3rd-person probe.
        context_markers: Optional per-line marker list from
            :func:`detect_context_markers`.

    Returns:
        :class:`POVResult` with detected perspective and confidence.
    """
    patterns = _get_pov_patterns(language)

    counts: Dict[str, int] = {"1st": 0, "2nd": 0, "3rd": 0}
    narrative_lines = 0

    for idx, line in enumerate(lines):
        text = line.strip()
        if not text:
            continue

        # Skip dialogue lines (speaker prefix)
        if detect_speaker(text) is not None:
            continue

        # Skip menu / choice lines via context markers
        if context_markers and idx < len(context_markers):
            marker = context_markers[idx]
            if marker in ("menu", "choice"):
                continue

        narrative_lines += 1

        # 1st / 2nd person pattern matching
        for pov, pats in patterns.items():
            for pat in pats:
                counts[pov] += len(pat.findall(text))

        # 3rd person: protagonist name frequency
        if protagonist_name and protagonist_name in text:
            counts["3rd"] += text.count(protagonist_name)

    total = counts["1st"] + counts["2nd"] + counts["3rd"]

    if total == 0 or narrative_lines == 0:
        return POVResult(
            pov="unknown",
            confidence="low",
            counts=counts,
            total_narrative_lines=narrative_lines,
        )

    # Determine dominant POV
    dominant_pov = max(counts, key=lambda k: counts[k])
    dominant_ratio = counts[dominant_pov] / total

    # Secondary POV check
    secondary = sorted(counts, key=lambda k: counts[k], reverse=True)
    secondary_pov = secondary[1] if len(secondary) > 1 else None
    secondary_ratio = counts[secondary_pov] / total if secondary_pov else 0.0

    # Mixed POV: dominant < 60 % and secondary >= 20 %
    if dominant_ratio < 0.6 and secondary_ratio >= 0.2:
        pov = "mixed"
        confidence = "low"
    else:
        pov = dominant_pov
        confidence = "high" if dominant_ratio > 0.6 else "low"

    return POVResult(
        pov=pov,
        confidence=confidence,
        counts=counts,
        total_narrative_lines=narrative_lines,
    )


# ============================================================================
# File Type Classification (Typing)
# ============================================================================


def classify_file_type(lines: List[str]) -> str:
    """Classify a file's content type based on speaker detection ratio.

    Uses ``detect_speaker`` to count how many lines have a speaker prefix,
    then classifies:

    - ``"dialogue"`` — more than 10% of lines have speakers detected.
    - ``"menu?"``    — 10% or fewer but at least 2 lines have speakers.
    - ``"menu"``     — no speakers detected at all.

    Args:
        lines: The raw text lines from a single file.

    Returns:
        One of ``"dialogue"``, ``"menu?"``, or ``"menu"``.
    """
    if not lines:
        return "menu"

    speaker_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and detect_speaker(stripped) is not None:
            speaker_count += 1

    total = len(lines)
    if total == 0:
        return "menu"

    ratio = speaker_count / total
    if ratio > 0.10:
        return "dialogue"
    elif speaker_count >= 2:
        return "menu?"
    else:
        return "menu"


def resolve_chunk_type(
    line_indices: List[int],
    lines: List[Dict[str, Any]],
    filedir: List[Any],
) -> str:
    """Resolve the context type for a chunk of line indices.

    Priority:
    1. Per-line ``tag`` values — majority wins.
    2. ``filedir`` entry ``type`` for the files containing the lines.
    3. ``"unknown"`` fallback.

    Args:
        line_indices: Global 0-based line indices in this chunk.
        lines: Full manifest ``lines`` list (dicts with ``idx``, ``tag``, …).
        filedir: List of ``FileDirEntry`` objects from the manifest.

    Returns:
        One of ``"dialogue"``, ``"menu"``, ``"choice"``, ``"menu?"``,
        ``"mixed"``, or ``"unknown"``.
    """
    if not line_indices:
        return "unknown"

    # Build idx→tag map for requested indices
    idx_set = set(line_indices)
    tag_counts: Dict[str, int] = {}
    for line_data in lines:
        idx = line_data.get("idx", -1)
        if idx in idx_set:
            tag = line_data.get("tag", "")
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # 1. Tags take priority
    if tag_counts:
        winner = max(tag_counts, key=tag_counts.get)  # type: ignore[arg-type]
        return winner

    # 2. Filedir type
    type_set: set = set()
    for idx in line_indices:
        for entry in filedir:
            if entry.contains_idx(idx) and entry.type:
                type_set.add(entry.type)
                break

    if len(type_set) == 1:
        return type_set.pop()
    if len(type_set) > 1:
        return "mixed"

    # 3. Fallback
    return "unknown"


# ============================================================================
# Protagonist Detection (Task 75)
# ============================================================================


def get_protagonists_from_characters(
    characters: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return characters marked as Protagonist.

    Scans the ``notes`` field for the word "Protagonist" (case-insensitive).

    Args:
        characters: Character dicts from the manifest (``original_name``,
            ``translation``, ``notes``).

    Returns:
        Subset of *characters* that are tagged as protagonist.
    """
    result: List[Dict[str, Any]] = []
    for ch in characters:
        notes = str(ch.get("notes", "")).lower()
        if "protagonist" in notes:
            result.append(ch)
    return result


def get_protagonists_from_code_database(
    code_patterns: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return code patterns marked as nameable protagonist variables.

    A code pattern is considered a protagonist variable when its ``notes``
    (or ``action``) field contains "protagonist" or its type is "name"
    and notes contain "protagonist".

    Args:
        code_patterns: Code pattern dicts from the manifest.

    Returns:
        Subset of *code_patterns* that are tagged as protagonist.
    """
    result: List[Dict[str, Any]] = []
    for cp in code_patterns:
        notes = str(cp.get("notes", "")).lower()
        if "protagonist" in notes:
            result.append(cp)
    return result


def run_pov_with_protagonists(
    lines: List[str],
    language: str,
    characters: List[Dict[str, Any]],
    code_patterns: Optional[List[Dict[str, Any]]] = None,
    context_markers: Optional[List[Optional[str]]] = None,
) -> POVResult:
    """Run POV inference using all known protagonist names.

    Combines protagonist names from character glossary and code database,
    then calls :func:`detect_pov` for each name and merges results.
    When no protagonist is configured, runs without a protagonist name
    (only detects 1st/2nd person).

    Args:
        lines: Raw text lines.
        language: Source language key.
        characters: Character list from manifest.
        code_patterns: Code patterns from manifest (optional).
        context_markers: Per-line context markers (optional).

    Returns:
        :class:`POVResult` with detected perspective and confidence.
    """
    protagonist_names: List[str] = []

    # Gather protagonist names from characters
    for ch in get_protagonists_from_characters(characters):
        name = ch.get("original_name", "").strip()
        if name:
            protagonist_names.append(name)

    # Gather protagonist names from code patterns
    if code_patterns:
        for cp in get_protagonists_from_code_database(code_patterns):
            pattern = cp.get("pattern", "").strip()
            if pattern:
                protagonist_names.append(pattern)

    if not protagonist_names:
        # No protagonist — only 1st/2nd detection
        return detect_pov(lines, language, "", context_markers)

    # Run detection for each protagonist and merge counts
    merged_counts: Dict[str, int] = {"1st": 0, "2nd": 0, "3rd": 0}
    narrative_lines = 0

    for name in protagonist_names:
        result = detect_pov(lines, language, name, context_markers)
        for k in ("1st", "2nd", "3rd"):
            merged_counts[k] += result.counts.get(k, 0)
        narrative_lines = max(narrative_lines, result.total_narrative_lines)

    # Deduplicate 1st/2nd counts (they're the same across runs)
    if len(protagonist_names) > 1:
        # 1st/2nd counts are counted identically each run, so divide
        merged_counts["1st"] = merged_counts["1st"] // len(protagonist_names)
        merged_counts["2nd"] = merged_counts["2nd"] // len(protagonist_names)

    total = sum(merged_counts.values())
    if total == 0 or narrative_lines == 0:
        return POVResult(
            pov="unknown",
            confidence="low",
            counts=merged_counts,
            total_narrative_lines=narrative_lines,
        )

    dominant_pov = max(merged_counts, key=lambda k: merged_counts[k])
    dominant_ratio = merged_counts[dominant_pov] / total

    secondary = sorted(merged_counts, key=lambda k: merged_counts[k], reverse=True)
    secondary_pov = secondary[1] if len(secondary) > 1 else None
    secondary_ratio = merged_counts[secondary_pov] / total if secondary_pov else 0.0

    if dominant_ratio < 0.6 and secondary_ratio >= 0.2:
        pov_val = "mixed"
        confidence = "low"
    else:
        pov_val = dominant_pov
        confidence = "high" if dominant_ratio > 0.6 else "low"

    return POVResult(
        pov=pov_val,
        confidence=confidence,
        counts=merged_counts,
        total_narrative_lines=narrative_lines,
    )


def format_protagonist_prompt(
    characters: List[Dict[str, Any]],
    code_patterns: Optional[List[Dict[str, Any]]] = None,
    pov_result: Optional["POVResult"] = None,
) -> str:
    """Build the Protagonist + Narration prompt section.

    Format::

        Protagonist: {Original} - {Translation} ({Details})
        Narration: {1st/2nd/3rd/Mixed} View

    Multiple protagonists are comma-separated.

    Args:
        characters: Character list from manifest.
        code_patterns: Code patterns from manifest (optional).
        pov_result: POV detection result (optional).

    Returns:
        Formatted prompt string, or empty string if no protagonist.
    """
    protag_parts: List[str] = []

    for ch in get_protagonists_from_characters(characters):
        original = ch.get("original_name", "")
        translation = ch.get("translation", "") or ch.get("name", "")
        notes = ch.get("notes", "")
        # Strip "Protagonist" from notes to avoid redundancy
        detail_parts = [
            p.strip() for p in notes.split(",")
            if p.strip().lower() != "protagonist"
        ]
        details = ", ".join(detail_parts) if detail_parts else ""
        if original:
            part = f"{original}"
            if translation:
                part += f" - {translation}"
            if details:
                part += f" ({details})"
            protag_parts.append(part)

    if code_patterns:
        for cp in get_protagonists_from_code_database(code_patterns):
            pattern = cp.get("pattern", "")
            notes = cp.get("notes", "")
            detail_parts = [
                p.strip() for p in notes.split(",")
                if p.strip().lower() != "protagonist"
            ]
            details = ", ".join(detail_parts) if detail_parts else ""
            if pattern:
                part = f"{pattern}"
                if details:
                    part += f" ({details})"
                protag_parts.append(part)

    if not protag_parts and not pov_result:
        return ""

    lines_out: List[str] = []
    if protag_parts:
        lines_out.append(f"Protagonist: {', '.join(protag_parts)}")

    if pov_result:
        pov_label = {
            "1st": "1st Person",
            "2nd": "2nd Person",
            "3rd": "3rd Person",
            "mixed": "Mixed",
            "unknown": "Unknown",
        }.get(pov_result.pov, pov_result.pov)

        if pov_result.confidence == "high":
            lines_out.append(f"Narration: {pov_label} View")
        elif not protag_parts:
            # Without protagonist, low confidence but still show inference
            lines_out.append(f"Narration: ? - Likely 3rd Person")
        else:
            lines_out.append(f"Narration: {pov_label} View")

    return "\n".join(lines_out)


# ---------------- Glossary delegates ---------------- #

def update_glossaries_from_analysis(
    input_path: Path,
    logs_dir: Path,
    confidence_threshold: float = 75.0,
    update_mode: str = "Add"
) -> Dict[str, Any]:
    """Delegate to the centralized glossary builder that writes headers and comments.

    Args:
        input_path: Path to input file to analyze
        logs_dir: Path to logs directory
        confidence_threshold: Minimum confidence (0-100%) for gender assignment (default 75%)
        update_mode: Glossary update mode - "Add", "Update", "Overwrite", or "New" (default "Add")
            - Add: Only add new entries (preserve existing)
            - Update: Add new + fill empty fields in existing
            - Overwrite: Add new + replace all fields in existing
            - New: Archive existing glossary and create fresh one

    Returns a dict with paths to the updated glossaries and analysis summary.
    """
    # Import the concrete implementations directly from the glossaries package
    # This avoids relying on wrapper re-exports in `glossary.py`, which can
    # behave differently depending on how the script is launched (VS Code vs
    # double-click). Import lazily to keep startup cheap.
    try:
        from .glossaries.name_glossary_functions import update_speakers_in_glossary
        from .glossaries.code_glossary_functions import update_code_in_glossary
    except Exception:  # pragma: no cover - fallback absolute imports
        from CherryAI.functions.glossaries.name_glossary_functions import update_speakers_in_glossary
        from CherryAI.functions.glossaries.code_glossary_functions import update_code_in_glossary
    
    # Read input file for comprehensive gender detection
    # (explicit markers like "性別：女性" and honorifics from others like "リリィちゃん")
    input_path = Path(input_path)
    try:
        full_text = input_path.read_text(encoding="utf-8")
        lines = full_text.splitlines()
    except Exception:
        full_text = ""
        lines = []
    
    # Run full analysis to get pronoun/honorific data
    summary = analyze_file(input_path, logs_dir)
    
    # Extract data from analysis summary
    # Speaker counts are in summary["speakers"]["top"] as list of (name, count) tuples
    speakers_top = summary.get("speakers", {}).get("top", [])
    speakers_count = dict(speakers_top) if speakers_top else {}
    speaker_pronoun_counts = summary.get("speaker_pronoun_counts", {})
    speaker_suffix_counts = summary.get("speaker_suffix_counts", {})
    
    # Code items are now directly in summary (dict of code -> count)
    code_counts = summary.get("code_items", {})
    
    # Update glossaries with enriched data
    if speakers_count:
        sp_path = update_speakers_in_glossary(
            speakers_count,
            speaker_pronoun_counts,
            speaker_suffix_counts,
            confidence_threshold=confidence_threshold,
            update_mode=update_mode,
            full_text=full_text,
            lines=lines,
        )
        summary["speakers_glossary_path"] = str(sp_path)
        logging.info("Updated speaker glossary: %s (%d speakers)", sp_path, len(speakers_count))
    
    if code_counts:
        code_path = update_code_in_glossary(code_counts, update_mode=update_mode)
        summary["code_glossary_path"] = str(code_path)
        logging.info("Updated code glossary: %s (%d codes)", code_path, len(code_counts))
    
    return summary
