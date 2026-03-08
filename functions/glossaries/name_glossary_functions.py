"""Name and speaker glossary functions for CherryAI.

This module contains all functions for:
- Speaker detection from dialogue
- Name extraction from honorifics
- Name validation and normalization
- Gender inference from pronouns and honorifics
- Explicit gender detection from status cards and narrative
- Romanization of Japanese names
- Glossary updates for speakers/names
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import constants from name_glossary_constants
from .name_glossary_constants import (
    HIRAGANA_RANGE,
    KATAKANA_RANGE,
    KANJI_RANGE,
    HONORIFIC_RE,
    HONORIFIC_ROMANIZATION,
    HONORIFIC_GENDER,
    PLACEHOLDER_NAME_RE,
    PRONOUN_ROMANIZATION,
    PRONOUN_GENDER,
    MIN_SPEAKER_OCCURRENCES,
    MAX_SPEAKER_LENGTH,
    DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
    EXPLICIT_GENDER_PATTERNS,
    EXPLICIT_GENDER_VALUES,
    REFERRED_BY_OTHERS_WEIGHT,
    STRONG_GENDER_HONORIFICS,
)

# NOTE: Avoid importing heavyweight glossary module at import time to prevent
# circular imports. Any references to GlossaryEntry or unified-glossary I/O
# are imported lazily inside the functions that need them.


# ---------------- Speaker detection helpers ---------------- #

# CJK Unicode ranges for length-limit heuristic
_CJK_RANGES = (
    (0x3000, 0x9FFF),    # CJK Unified, Hiragana, Katakana, symbols
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0xFF00, 0xFFEF),    # Fullwidth Forms
    (0x20000, 0x2FA1F),  # CJK Extension B-F
)

_BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}", "<": ">",
                  "（": "）", "［": "］", "｛": "｝", "＜": "＞",
                  "〈": "〉", "【": "】", "〔": "〕", "「": "」", "『": "』"}

# Max distance (in characters) from line start to the colon separator.
SPEAKER_MAX_LEN_LATIN = 30
SPEAKER_MAX_LEN_CJK = 20


def _is_cjk_char(ch: str) -> bool:
    """Return True if *ch* falls inside a CJK Unicode range."""
    cp = ord(ch)
    for lo, hi in _CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def _has_balanced_brackets(text: str) -> bool:
    """Return True when all opening brackets in *text* are properly closed.

    Handles nested and multiple bracket types. Pairs checked:
    ``( ) [ ] { } < >`` and their fullwidth/CJK equivalents.
    """
    stack: List[str] = []
    closing_map = {v: k for k, v in _BRACKET_PAIRS.items()}
    openers = set(_BRACKET_PAIRS.keys())
    closers = set(_BRACKET_PAIRS.values())

    for ch in text:
        if ch in openers:
            stack.append(ch)
        elif ch in closers:
            expected_opener = closing_map[ch]
            if not stack or stack[-1] != expected_opener:
                return False
            stack.pop()
    return len(stack) == 0


def _speaker_length_ok(name: str) -> bool:
    """Return True if the speaker candidate respects length limits.

    Latin-dominant names: max 30 characters.
    CJK-dominant names: max 20 characters.
    """
    cjk_count = sum(1 for ch in name if _is_cjk_char(ch))
    is_cjk_dominant = cjk_count > len(name) / 2
    limit = SPEAKER_MAX_LEN_CJK if is_cjk_dominant else SPEAKER_MAX_LEN_LATIN
    return len(name) <= limit


# ---------------- Speaker detection ---------------- #


def detect_speaker(line: str) -> Optional[str]:
    """Return speaker name if a leading ``NAME:`` or ``NAME：`` pattern is detected.

    Validation rules applied after regex match:
    1. **Balanced brackets** — all ``( ) [ ] { } < >`` (and fullwidth/CJK
       equivalents) in the name must be properly paired.
    2. **No newline before colon** — the colon must appear on the first
       physical line; if ``\\n`` precedes it the match is rejected.
    3. **Length limit** — the name portion must be ≤ 30 chars for Latin-
       dominant text and ≤ 20 chars for CJK-dominant text.

    Args:
        line: The line to check for speaker pattern.

    Returns:
        The speaker name if detected, None otherwise.
    """
    # Rule 2: colon must be on the first physical line
    first_line = line.split("\n", 1)[0]

    m = re.match(r"^\s*(?P<name>[^\s:：][^:：]{0,100}?)\s*[:：]", first_line)
    if not m:
        return None

    name = m.group("name").strip()

    # Rule 1: balanced brackets
    if not _has_balanced_brackets(name):
        return None

    # Rule 3: length limit
    if not _speaker_length_ok(name):
        return None

    return name


# ---------------- Script type detection ---------------- #


def _get_script_type(text: str) -> Optional[str]:
    """Return the script type of text: 'hiragana', 'katakana', 'kanji', or None if mixed/invalid.
    
    A valid name uses ONE script type only (not a mix). ASCII/Latin chars cause rejection.
    
    Args:
        text: The text to analyze
        
    Returns:
        'hiragana', 'katakana', 'kanji', or None
    """
    if not text:
        return None
    
    has_hiragana = False
    has_katakana = False
    has_kanji = False
    has_ascii_alpha = False
    japanese_char_count = 0
    
    for ch in text:
        o = ord(ch)
        if HIRAGANA_RANGE[0] <= o <= HIRAGANA_RANGE[1]:
            has_hiragana = True
            japanese_char_count += 1
        elif KATAKANA_RANGE[0] <= o <= KATAKANA_RANGE[1]:
            has_katakana = True
            japanese_char_count += 1
        elif KANJI_RANGE[0] <= o <= KANJI_RANGE[1]:
            has_kanji = True
            japanese_char_count += 1
        elif (0x41 <= o <= 0x5A) or (0x61 <= o <= 0x7A):  # A-Z, a-z
            has_ascii_alpha = True
    
    # Must have at least one Japanese character
    if japanese_char_count == 0:
        return None
    
    # Reject if contains ASCII letters (mixed with Japanese)
    if has_ascii_alpha:
        return None
    
    # Must use only ONE Japanese script type
    script_count = sum([has_hiragana, has_katakana, has_kanji])
    if script_count != 1:
        return None  # Mixed scripts
    
    if has_hiragana:
        return "hiragana"
    elif has_katakana:
        return "katakana"
    elif has_kanji:
        return "kanji"
    return None


# ---------------- Name validation ---------------- #


def _is_valid_name_candidate(base_token: str) -> bool:
    r"""Validate if base_token (before honorific) is a plausible name.
    
    Criteria:
    - One script type only (hiragana, katakana, or kanji - no mixing)
    - Kanji names: 2-4 characters
    - Hiragana/Katakana names: 2-6 characters (more flexible for given names)
    - No symbols except in placeholder patterns like [n1], \N[1], {name}
    - Placeholder patterns are always valid (for variable name coding)
    
    Args:
        base_token: The name candidate to validate
        
    Returns:
        True if valid name candidate, False otherwise
    """
    if not base_token:
        return False
    
    # Check for placeholder patterns first (always valid)
    if PLACEHOLDER_NAME_RE.match(base_token):
        return True
    
    # Check for disallowed symbols (except placeholder patterns already checked)
    # Allow Japanese characters and basic punctuation that might be part of names
    # Disallow: <, >, [, ], {, }, (, ), \, ", ', etc.
    disallowed_symbols = "<>[]{}()\"\\'`"
    if any(sym in base_token for sym in disallowed_symbols):
        return False
    
    # Get script type (must be pure: one type only)
    script_type = _get_script_type(base_token)
    if script_type is None:
        return False  # Mixed scripts or no Japanese
    
    # Count Japanese characters only (ignore ASCII/symbols for length check)
    jp_char_count = 0
    for ch in base_token:
        o = ord(ch)
        if (HIRAGANA_RANGE[0] <= o <= HIRAGANA_RANGE[1] or
            KATAKANA_RANGE[0] <= o <= KATAKANA_RANGE[1] or
            KANJI_RANGE[0] <= o <= KANJI_RANGE[1]):
            jp_char_count += 1
    
    # Length validation based on script type
    if script_type == "kanji":
        # Kanji names: typically 2-4 characters (family + given name)
        if not (2 <= jp_char_count <= 4):
            return False
    else:  # hiragana or katakana
        # Hiragana/Katakana names: 2-6 characters (more flexible)
        if not (2 <= jp_char_count <= 6):
            return False
    
    return True


# ---------------- Name extraction ---------------- #


def extract_names_from_honorifics(lines: List[str]) -> Dict[str, int]:
    """Extract name candidates from text by finding tokens preceding honorifics.
    
    Scans all lines for honorific patterns (e.g., 花子さん, ジョンくん) and extracts
    the base name if it meets validation criteria (pure script, appropriate length, etc.).
    
    Args:
        lines: List of text lines to scan
        
    Returns:
        Dict mapping normalized name -> occurrence count (only validated names)
    """
    name_counts: Dict[str, int] = {}
    
    for line in lines:
        for match in HONORIFIC_RE.finditer(line):
            base_token = match.group(1)
            
            # Normalize first to strip leading/trailing punctuation (「朝霧 → 朝霧)
            normalized = _normalize_speaker(base_token)
            if not normalized:
                continue
            
            # Validate the normalized name
            if _is_valid_name_candidate(normalized):
                name_counts[normalized] = name_counts.get(normalized, 0) + 1
    
    return name_counts


# ---------------- Speaker normalization ---------------- #


def _normalize_speaker(name: str) -> Optional[str]:
    """Normalize speaker name:

    - Strip ASCII digits and fullwidth digits (e.g., 1 and １).
    - Trim whitespace.
    - Exclude generic/blacklisted names (currently Japanese: 人, 男, 女).
    - Return None when name is empty or blacklisted.
    
    Args:
        name: The raw speaker name to normalize
        
    Returns:
        Normalized name or None if invalid
    """
    if not name:
        return None

    # Strip leading quotation marks (Japanese/English), ellipses, commas, and spaces
    # Common patterns: 「静葉, 「……夢乃, 、夢乃, ……太刀野, etc.
    leading_punct = "「『\"（(［[【……、，, \t"
    trailing_punct = "」』\"）)］]】、，, \t"
    
    while name and name[0] in leading_punct:
        name = name[1:]
    
    # Strip trailing quotation marks and punctuation
    while name and name[-1] in trailing_punct:
        name = name[:-1]

    # Collapse common enclosing punctuation and trim
    name = name.strip().strip('"'"'"'""''()[]{}<>')

    # If the name is entirely question marks (fullwidth or ascii), drop it
    if re.fullmatch(r"[\?？]{1,}", name):
        return None

    # If bracketed variant like [Name1] or （Name2） exists, normalize inner part
    br_match = re.match(r"^[\[（\(](.*?)[\]）\)]$", name)
    if br_match:
        inner = br_match.group(1).strip()
        # remove ASCII and fullwidth digits
        inner = re.sub(r"[0-9０-９]", "", inner)
        inner = inner.strip()
        if not inner:
            return None
        name = f"[{inner}]"

    # Remove remaining digits anywhere
    name = re.sub(r"[0-9０-９]", "", name).strip()
    if not name:
        return None

    # Blacklist substrings: if any appears anywhere in the name, drop it.
    # Include fullwidth question mark and common Japanese terms that indicate
    # non-speaker tokens (examples requested by user).
    blacklist_substrs = {"人", "男", "女", "？？？", "その", "……", "旦那"}
    for sub in blacklist_substrs:
        if sub and sub in name:
            return None

    # Collapse trailing single-letter suffixes (halfwidth or fullwidth capitals)
    # e.g. "Man A" or "太郎Ａ" -> "Man" / "太郎"
    name = re.sub(r"[\s\-\_]*[A-ZＡ-Ｚ]$", "", name)

    # Collapse repeated whitespace
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return None
    return name


# ---------------- Romanization ---------------- #


def romanize_pronoun(jp_pronoun: str) -> str:
    """Convert Japanese pronoun to romanized form.
    
    Args:
        jp_pronoun: Japanese pronoun text
        
    Returns:
        Romanized pronoun (Hepburn style) or original if not in table
    """
    from typing import cast
    return cast(str, PRONOUN_ROMANIZATION.get(jp_pronoun, jp_pronoun))


def romanize_honorific(jp_honorific: str) -> str:
    """Convert Japanese honorific to romanized form.
    
    Args:
        jp_honorific: Japanese honorific text
        
    Returns:
        Romanized honorific (Hepburn style) or original if not in table
    """
    from typing import cast
    return cast(str, HONORIFIC_ROMANIZATION.get(jp_honorific, jp_honorific))


# ---------------- Explicit gender detection ---------------- #


def detect_explicit_gender(
    name: str,
    text: str,
) -> Tuple[Optional[str], float, str]:
    """Detect explicit gender declarations for a character in text.
    
    Searches for explicit patterns like:
    - Status cards: "名前：リリィ、性別：女性" (Name: Lily, Gender: Female)
    - Transformation: "リリィは女性になった" (Lily became female)
    
    Args:
        name: The character name to search for
        text: Full text content to search through
        
    Returns:
        Tuple of (gender, confidence, source):
        - gender: "Male", "Female", or None if not found
        - confidence: 100.0 if explicit match found, 0.0 otherwise
        - source: Pattern type that matched (e.g., "status_card") or ""
    """
    from ..glossary import GENDER_MALE, GENDER_FEMALE
    
    # Escape name for regex safety
    escaped_name = re.escape(name)
    
    for pattern, source_type in EXPLICIT_GENDER_PATTERNS.items():
        # Substitute the name into patterns that reference it
        if ".+?" in pattern:
            # Pattern with name capture group - search for any match then filter
            regex = re.compile(pattern, re.IGNORECASE)
            for match in regex.finditer(text):
                matched_name = match.group(1) if (match.lastindex or 0) >= 1 else None
                matched_gender = match.group(2) if (match.lastindex or 0) >= 2 else None
                
                if matched_name and name in matched_name:
                    if matched_gender:
                        gender_value = EXPLICIT_GENDER_VALUES.get(matched_gender)
                        if gender_value == "female":
                            logging.info(
                                "Explicit gender found for %s: Female (%s)",
                                name, source_type
                            )
                            return GENDER_FEMALE, 100.0, source_type
                        elif gender_value == "male":
                            logging.info(
                                "Explicit gender found for %s: Male (%s)",
                                name, source_type
                            )
                            return GENDER_MALE, 100.0, source_type
    
    return None, 0.0, ""


def detect_honorific_gender_from_others(
    name: str,
    lines: List[str],
    speaker_counts: Dict[str, int],
) -> Tuple[Optional[str], float]:
    """Detect gender from how OTHER characters refer to this character.
    
    When other characters refer to someone as "リリィちゃん" (Lily-chan),
    the feminine honorific ちゃん strongly suggests female gender.
    This is weighted more heavily than self-pronouns because external
    perception is more reliable for characters with unusual speech patterns
    (e.g., transformed characters using old speech habits).
    
    Args:
        name: The character name to search for
        lines: Lines of dialogue to search
        speaker_counts: Dict of speaker -> occurrence count (to identify other speakers)
        
    Returns:
        Tuple of (gender, weighted_confidence):
        - gender: "Male", "Female", or None if inconclusive
        - weighted_confidence: Confidence score (0-100), weighted by REFERRED_BY_OTHERS_WEIGHT
    """
    from ..glossary import GENDER_MALE, GENDER_FEMALE
    
    male_score = 0.0
    female_score = 0.0
    
    # Pattern to find name+honorific combinations (e.g., リリィちゃん)
    for honorific, gender in STRONG_GENDER_HONORIFICS.items():
        pattern = re.escape(name) + re.escape(honorific)
        regex = re.compile(pattern)
        
        for line in lines:
            # Check if this line is spoken by someone OTHER than the target
            speaker = detect_speaker(line)
            if speaker and speaker != name:
                # Count honorific usage by others
                matches = regex.findall(line)
                if matches:
                    count = len(matches)
                    if gender == "female":
                        female_score += count * REFERRED_BY_OTHERS_WEIGHT
                    elif gender == "male":
                        male_score += count * REFERRED_BY_OTHERS_WEIGHT
    
    # Calculate confidence
    total = male_score + female_score
    if total == 0:
        return None, 0.0
    
    if female_score > male_score:
        confidence = (female_score / total) * 100.0
        return GENDER_FEMALE, confidence
    elif male_score > female_score:
        confidence = (male_score / total) * 100.0
        return GENDER_MALE, confidence
    else:
        return None, 50.0


# ---------------- Gender inference ---------------- #


def infer_gender_from_context(
    pronouns: Dict[str, int],
    honorifics: Dict[str, int],
    confidence_threshold: float = DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
) -> Tuple[str, float, str, str]:
    """Infer gender from pronouns and honorifics with confidence scoring.
    
    Args:
        pronouns: Dict mapping romanized pronoun to occurrence count (e.g., {"watashi": 100, "ore": 50})
        honorifics: Dict mapping romanized honorific to occurrence count (e.g., {"san": 200, "chan": 30})
        confidence_threshold: Minimum confidence (0-100%) to return male/female
        
    Returns:
        Tuple of (gender, confidence_pct, refers_to_themself_as, referred_to_as)
        - gender: "Male", "Female", or "Unknown"
        - confidence_pct: Confidence percentage (0-100)
        - refers_to_themself_as: Comma-separated romanized pronouns
        - referred_to_as: Comma-separated romanized honorifics
    """
    # Import gender constants lazily to avoid circular import
    from ..glossary import GENDER_MALE, GENDER_FEMALE, GENDER_UNKNOWN

    # Count male/female/unknown indicators weighted by occurrence count
    male_count = 0
    female_count = 0
    unknown_count = 0
    
    # Analyze pronouns (weighted by count)
    for pronoun, count in pronouns.items():
        gender = PRONOUN_GENDER.get(pronoun, "unknown")
        if gender == "male":
            male_count += count
        elif gender == "female":
            female_count += count
        else:
            unknown_count += count
    
    # Analyze honorifics (weighted by count)
    for honorific, count in honorifics.items():
        gender = HONORIFIC_GENDER.get(honorific, "unknown")
        if gender == "male":
            male_count += count
        elif gender == "female":
            female_count += count
        else:
            unknown_count += count
    
    # Calculate confidence (only from male/female, exclude unknown)
    total_gendered = male_count + female_count
    if total_gendered == 0:
        # No gendered indicators
        confidence = 0.0
        inferred_gender = GENDER_UNKNOWN
    else:
        # Confidence is the percentage of the dominant gender
        if male_count > female_count:
            confidence = (male_count / total_gendered) * 100.0
            inferred_gender = GENDER_MALE if confidence >= confidence_threshold else GENDER_UNKNOWN
        elif female_count > male_count:
            confidence = (female_count / total_gendered) * 100.0
            inferred_gender = GENDER_FEMALE if confidence >= confidence_threshold else GENDER_UNKNOWN
        else:
            # Equal male/female counts = conflict
            confidence = 50.0
            inferred_gender = GENDER_UNKNOWN
    
    # Format pronoun/honorific strings (sorted by count descending)
    refers_to = ",".join(
        f"{p}:{c}" for p, c in sorted(pronouns.items(), key=lambda x: x[1], reverse=True)
    ) if pronouns else ""
    referred_to = ",".join(
        f"{h}:{c}" for h, c in sorted(honorifics.items(), key=lambda x: x[1], reverse=True)
    ) if honorifics else ""
    
    logging.debug(
        "Gender inference: male=%d female=%d unknown=%d -> %s (%.1f%%)",
        male_count, female_count, unknown_count, inferred_gender, confidence
    )
    
    return inferred_gender, confidence, refers_to, referred_to


def infer_gender_comprehensive(
    name: str,
    pronouns: Dict[str, int],
    honorifics: Dict[str, int],
    full_text: str = "",
    lines: Optional[List[str]] = None,
    speaker_counts: Optional[Dict[str, int]] = None,
    confidence_threshold: float = DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
) -> Tuple[str, float, str, str, str]:
    """Comprehensive gender inference combining all available signals.
    
    Priority order (highest to lowest):
    1. Explicit gender markers (status cards, narrative declarations) -> 100% confidence
    2. Honorifics used BY OTHERS (weighted 3x) -> high confidence
    3. Self-pronouns and self-honorifics -> normal weighting
    
    This handles edge cases like:
    - Characters who use male pronouns but are canonically female (e.g., transformed characters)
    - Characters with conflicting signals from different sources
    
    Args:
        name: The character name to analyze
        pronouns: Dict mapping romanized pronoun to occurrence count
        honorifics: Dict mapping romanized honorific to occurrence count
        full_text: Full text content for explicit gender detection
        lines: List of dialogue lines for honorific-by-others detection
        speaker_counts: Dict of speaker -> occurrence count
        confidence_threshold: Minimum confidence to return male/female
        
    Returns:
        Tuple of (gender, confidence_pct, refers_to_themself_as, referred_to_as, source):
        - gender: "Male", "Female", or "Unknown"
        - confidence_pct: Confidence percentage (0-100)
        - refers_to_themself_as: Comma-separated romanized pronouns
        - referred_to_as: Comma-separated romanized honorifics
        - source: What determined the gender ("explicit", "others_honorific", "pronouns", "unknown")
    """
    from ..glossary import GENDER_UNKNOWN
    
    # Format pronoun/honorific strings (always include regardless of result)
    refers_to = ",".join(
        f"{p}:{c}" for p, c in sorted(pronouns.items(), key=lambda x: x[1], reverse=True)
    ) if pronouns else ""
    referred_to = ",".join(
        f"{h}:{c}" for h, c in sorted(honorifics.items(), key=lambda x: x[1], reverse=True)
    ) if honorifics else ""
    
    # 1. Try explicit gender detection first (highest priority)
    if full_text:
        explicit_gender, explicit_conf, explicit_source = detect_explicit_gender(name, full_text)
        if explicit_gender:
            logging.info(
                "Gender for %s determined by explicit marker (%s): %s",
                name, explicit_source, explicit_gender
            )
            return explicit_gender, explicit_conf, refers_to, referred_to, "explicit"
    
    # 2. Try honorifics used by others (high weight)
    if lines and speaker_counts:
        others_gender, others_conf = detect_honorific_gender_from_others(
            name, lines, speaker_counts
        )
        if others_gender and others_conf >= confidence_threshold:
            logging.info(
                "Gender for %s determined by others' honorifics: %s (%.1f%%)",
                name, others_gender, others_conf
            )
            return others_gender, others_conf, refers_to, referred_to, "others_honorific"
    
    # 3. Fall back to standard pronoun/honorific analysis
    basic_gender, basic_conf, _, _ = infer_gender_from_context(
        pronouns, honorifics, confidence_threshold
    )
    
    if basic_gender != GENDER_UNKNOWN:
        source = "pronouns"
    else:
        source = "unknown"
    
    return basic_gender, basic_conf, refers_to, referred_to, source


# ---------------- Speaker validation ---------------- #


def _is_valid_speaker_entry(name: str, count: int) -> bool:
    """Validate if a speaker entry should be included in the glossary.
    
    Filters out low-quality entries based on:
    - Minimum occurrence threshold (must appear at least 2 times)
    - Maximum length (names shouldn't be full sentences)
    - Linebreak codes (literal \\n or actual newlines indicate bad detection)
    - Unbalanced parentheses (incomplete expressions)
    
    Args:
        name: The speaker name to validate
        count: Number of times this speaker appears in the text
        
    Returns:
        True if the entry is valid and should be included, False otherwise
    """
    if not name or not name.strip():
        return False
    
    # Minimum occurrence threshold
    if count < MIN_SPEAKER_OCCURRENCES:
        return False
    
    # Length check - filter out full sentences mistaken for speakers
    if len(name) > MAX_SPEAKER_LENGTH:
        return False
    
    # Check for linebreak codes (literal backslash-n or actual newline)
    if "\\n" in name or "\n" in name or "\\r" in name or "\r" in name:
        return False
    
    # Check for unbalanced parentheses (both ASCII and fullwidth)
    paren_balance = name.count("(") - name.count(")")
    fullwidth_balance = name.count("（") - name.count("）")
    if paren_balance != 0 or fullwidth_balance != 0:
        return False
    
    # Check for unbalanced brackets (common in code/formatting)
    bracket_balance = name.count("[") - name.count("]")
    brace_balance = name.count("{") - name.count("}")
    angle_balance = name.count("<") - name.count(">")
    if bracket_balance != 0 or brace_balance != 0 or angle_balance != 0:
        return False
    
    return True


# ---------------- Glossary update functions ---------------- #


def update_speakers_in_glossary(
    speakers_count: Dict[str, int],
    speaker_pronoun_counts: Optional[Dict[str, Dict[str, int]]] = None,
    speaker_suffix_counts: Optional[Dict[str, Dict[str, int]]] = None,
    additional_data: Optional[Dict[str, Dict[str, str]]] = None,
    confidence_threshold: float = DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
    update_mode: str = "Add",  # Use literal string to avoid circular import at module load time
    full_text: str = "",  # Full text content for explicit gender detection
    lines: Optional[List[str]] = None,  # All lines for honorific-from-others detection
    speaker_threshold: int = 0,
) -> Path:
    """Update unified glossary with speaker entries from analysis.
    
    Args:
        speakers_count: Dict mapping speaker name to occurrence count
        speaker_pronoun_counts: Optional dict mapping speaker -> pronoun -> count
        speaker_suffix_counts: Optional dict mapping speaker -> honorific -> count
        additional_data: Optional dict mapping speaker name to additional fields
                        (e.g., from API enrichment with 'romaji', 'gender', 'note')
        confidence_threshold: Minimum confidence (0-100%) to auto-assign gender
        update_mode: One of UPDATE_MODE_ADD, UPDATE_MODE_UPDATE, UPDATE_MODE_OVERWRITE, or UPDATE_MODE_NEW
            - ADD: Only add new entries (preserve existing)
            - UPDATE: Add new + fill empty fields in existing
            - OVERWRITE: Add new + replace all fields in existing
            - NEW: Archive existing glossary and create fresh one
        full_text: Full text content for explicit gender marker detection
                   (e.g., "名前：リリィ、性別：女性" status cards)
        lines: All lines from the file for honorific-from-others detection
               (e.g., when others call someone リリィちゃん)
        speaker_threshold: Minimum occurrence count to include in glossary
                          (0 = no filtering, uses MIN_SPEAKER_OCCURRENCES only).
        
    Returns:
        Path to updated unified glossary
    """
    # Lazy-import heavy glossary symbols to avoid circular imports at module import time
    from ..glossary import (
        TYPE_NAME,
        UPDATE_MODE_ADD,
        GlossaryEntry,
        read_unified_glossary,
        update_unified_glossary,
    )

    existing = read_unified_glossary()
    new_entries: List[GlossaryEntry] = []
    
    # Filter and create entries for valid speakers
    for name, count in speakers_count.items():
        if not _is_valid_speaker_entry(name, count):
            logging.debug("Filtered invalid speaker entry: %s (count=%d)", name, count)
            continue

        if speaker_threshold > 0 and count < speaker_threshold:
            logging.debug(
                "Speaker below threshold: %s (count=%d, threshold=%d)",
                name, count, speaker_threshold,
            )
            continue
        
        # For ADD mode: skip if already exists (preserve user edits)
        # For UPDATE/OVERWRITE modes: process all entries
        if update_mode == UPDATE_MODE_ADD and name in existing:
            continue
        
        # Get additional data if available (from API enrichment)
        extra = additional_data.get(name, {}) if additional_data else {}
        
        # Process pronouns and honorifics for gender inference
        pronouns_jp = speaker_pronoun_counts.get(name, {}) if speaker_pronoun_counts else {}
        honorifics_jp = speaker_suffix_counts.get(name, {}) if speaker_suffix_counts else {}
        
        # Romanize pronouns and honorifics with counts
        # IMPORTANT: Accumulate counts when multiple Japanese variants map to same romanized form
        # (e.g., 俺:2506 + おれ:1 -> ore:2507, not ore:1)
        pronouns_romanized: Dict[str, int] = {}
        for jp_token, count_val in pronouns_jp.items():
            rom = romanize_pronoun(jp_token)
            pronouns_romanized[rom] = pronouns_romanized.get(rom, 0) + count_val
        
        honorifics_romanized: Dict[str, int] = {}
        for jp_token, count_val in honorifics_jp.items():
            rom = romanize_honorific(jp_token)
            honorifics_romanized[rom] = honorifics_romanized.get(rom, 0) + count_val
        
        # Use comprehensive gender inference (explicit markers > honorifics from others > self-pronouns)
        inferred_gender, confidence, refers_to_formatted, referred_to_formatted, _source = infer_gender_comprehensive(
            name=name,
            full_text=full_text,
            lines=lines or [],
            speaker_counts=speakers_count,
            pronouns=pronouns_romanized,
            honorifics=honorifics_romanized,
            confidence_threshold=confidence_threshold,
        )
        
        # Use API gender if available, otherwise use inferred
        final_gender = extra.get("gender", "") or inferred_gender

        # Task 75: Auto-romanize kana names when no translation exists
        translation = extra.get("romaji", "")
        if not translation:
            try:
                from ..romanization import romanize_if_japanese
                translation = romanize_if_japanese(name)
                if translation == name:
                    translation = ""  # No kana found, don't duplicate
            except ImportError:
                pass

        entry = GlossaryEntry(
            original=name,
            translation=translation,
            notes=extra.get("note", ""),
            source="",
            entry_type=TYPE_NAME,
            gender=final_gender,
            refers_to_themself_as=refers_to_formatted,
            referred_to_as=referred_to_formatted,
        )
        new_entries.append(entry)
    
    # Sort by frequency (highest first)
    new_entries.sort(key=lambda e: speakers_count.get(e.original, 0), reverse=True)
    
    from typing import cast
    from pathlib import Path as _Path
    return cast(_Path, update_unified_glossary(new_entries, update_mode=update_mode))
