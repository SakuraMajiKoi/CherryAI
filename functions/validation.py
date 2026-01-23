"""
API validation module for CherryAI.

Provides pre-translation and post-translation validation to:
1. Skip lines that should not be sent to the API
2. Validate API responses for quality and accuracy
3. Auto-translate symbol-only lines without API calls
4. Detect and validate Speaker: "Dialogue" format preservation
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .modehelper import ANCHOR_EQUIVS, get_equivs


# Unicode ranges for Japanese character detection
HIRAGANA_RANGE = (0x3040, 0x309F)
KATAKANA_RANGE = (0x30A0, 0x30FF)
KANJI_RANGE_MAIN = (0x4E00, 0x9FFF)
KANJI_RANGE_EXT_A = (0x3400, 0x4DBF)


class SkipReason(Enum):
    """Reasons why a line is skipped from API translation."""
    
    EMPTY = "empty"
    COMMENT = "comment"
    EQUALS_PREFIX = "equals_prefix"
    DEDUP_ONLY = "dedup_only"
    PROT_ONLY = "prot_only"
    NO_JAPANESE = "no_japanese"
    ALREADY_TRANSLATED = "already_translated"
    SYMBOL_ONLY = "symbol_only"


@dataclass
class ValidationResult:
    """Result of validating a single line."""
    
    is_valid: bool
    skip_reason: Optional[SkipReason] = None
    auto_translation: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class BatchValidationResult:
    """Result of validating a batch of lines."""
    
    lines_to_translate: List[Tuple[int, str]]  # (original_index, line)
    skipped_lines: List[Tuple[int, str, SkipReason]]  # (index, line, reason)
    auto_translations: Dict[int, str]  # index -> auto-translated content


# Symbol normalization map: fullwidth → halfwidth
SYMBOL_NORMALIZATION: Dict[str, str] = {
    # Ellipsis and dots
    "…": "...",
    "‥": "..",
    "．": ".",
    # Punctuation
    "。": ".",
    "、": ",",
    "，": ",",
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
    # Brackets
    "（": "(",
    "）": ")",
    "「": '"',
    "」": '"',
    "『": '"',
    "』": '"',
    "【": "[",
    "】": "]",
    "〔": "[",
    "〕": "]",
    "｛": "{",
    "｝": "}",
    "〈": "<",
    "〉": ">",
    "《": "<",
    "》": ">",
    "［": "[",
    "］": "]",
    "＜": "<",
    "＞": ">",
    # Quotes
    "＂": '"',
    """: '"',
    """: '"',
    "„": '"',
    "'": "'",
    "'": "'",
    # Other
    "　": " ",  # Fullwidth space
    "＿": "_",
    "～": "~",
    "ー": "-",
    "－": "-",
    "‐": "-",
    "—": "-",
    "―": "-",
    "＝": "=",
    "＋": "+",
    "＊": "*",
    "／": "/",
    "＼": "\\",
    "＆": "&",
    "＃": "#",
    "＠": "@",
    "％": "%",
}

# Patterns for lines that should be skipped
DEDUP_PATTERN = re.compile(r"^\s*_{1,2}DEDUP_{1,2}\s*$", re.IGNORECASE)
PROT_PATTERN = re.compile(r"^\s*__\s*PROT\s*__\s*$", re.IGNORECASE)
COMMENT_PATTERN = re.compile(r"^\s*#")
EQUALS_PATTERN = re.compile(r"^\s*=")

# Pattern to find __PROT__ placeholders in text (with optional index)
PROT_PLACEHOLDER_PATTERN = re.compile(r"__\s*PROT(?:_\d+)?\s*__", re.IGNORECASE)

# Pattern to find custom placeholders like __NAME__, __CODE__, etc.
CUSTOM_PLACEHOLDER_PATTERN = re.compile(r"__[A-Z][A-Z0-9_]*(?:_\d+)?__")


# ============================================================================
# Placeholder Preservation Validation
# ============================================================================


@dataclass
class PlaceholderValidationResult:
    """Result of placeholder preservation validation."""
    
    is_valid: bool
    missing_placeholders: List[str] = field(default_factory=list)
    extra_placeholders: List[str] = field(default_factory=list)
    mangled_placeholders: List[str] = field(default_factory=list)
    should_retry: bool = False


def extract_placeholders(text: str) -> List[str]:
    """Extract all placeholder tokens from text.
    
    Finds patterns like:
    - __PROT__, __PROT_1__, __PROT_23__
    - __NAME__, __CODE__, __VAR_5__
    
    Args:
        text: Text to search for placeholders.
        
    Returns:
        List of placeholder tokens found (preserves order and duplicates).
    """
    # Find all __PROT__ style placeholders
    prot_matches = PROT_PLACEHOLDER_PATTERN.findall(text)
    
    # Find all __CUSTOM__ style placeholders
    custom_matches = CUSTOM_PLACEHOLDER_PATTERN.findall(text)
    
    # Combine and return (some may overlap, so use set to dedupe then re-find for order)
    all_placeholders = []
    seen = set()
    
    for match in prot_matches + custom_matches:
        normalized = match.upper().replace(" ", "")
        if normalized not in seen:
            seen.add(normalized)
            all_placeholders.append(normalized)
    
    return all_placeholders


def count_placeholder(text: str, placeholder: str) -> int:
    """Count occurrences of a specific placeholder in text.
    
    Handles case-insensitive matching and whitespace variations.
    
    Args:
        text: Text to search.
        placeholder: Placeholder to count (e.g., "__PROT__").
        
    Returns:
        Number of occurrences.
    """
    # Normalize the placeholder for pattern creation
    normalized = placeholder.upper().replace(" ", "")
    
    # Create pattern that allows whitespace variations
    if "_" in normalized[2:-2]:  # Has index like __PROT_1__
        parts = normalized[2:-2].split("_")
        pattern_str = r"__\s*" + r"\s*_\s*".join(parts) + r"\s*__"
    else:
        inner = normalized[2:-2]  # e.g., "PROT" from "__PROT__"
        pattern_str = r"__\s*" + inner + r"\s*__"
    
    pattern = re.compile(pattern_str, re.IGNORECASE)
    return len(pattern.findall(text))


def validate_placeholder_preserved(
    original: str,
    translated: str,
) -> PlaceholderValidationResult:
    """Validate that placeholders in original are preserved in translation.
    
    Checks that:
    1. All placeholders from original appear in translation
    2. No new placeholders were added
    3. Placeholder count matches
    
    Args:
        original: Original line (with placeholders).
        translated: Translated line.
        
    Returns:
        PlaceholderValidationResult with validation details.
    """
    orig_placeholders = extract_placeholders(original)
    trans_placeholders = extract_placeholders(translated)
    
    # If no placeholders in original, nothing to validate
    if not orig_placeholders:
        return PlaceholderValidationResult(is_valid=True)
    
    missing: List[str] = []
    mangled: List[str] = []
    
    # Check each original placeholder is in translation
    for ph in orig_placeholders:
        orig_count = count_placeholder(original, ph)
        trans_count = count_placeholder(translated, ph)
        
        if trans_count == 0:
            missing.append(ph)
        elif trans_count < orig_count:
            mangled.append(f"{ph} (expected {orig_count}, got {trans_count})")
    
    # Check for extra placeholders in translation
    orig_set = set(orig_placeholders)
    trans_set = set(trans_placeholders)
    extra = list(trans_set - orig_set)
    
    is_valid = len(missing) == 0 and len(mangled) == 0
    should_retry = len(missing) > 0  # Missing placeholders warrant retry
    
    return PlaceholderValidationResult(
        is_valid=is_valid,
        missing_placeholders=missing,
        extra_placeholders=extra,
        mangled_placeholders=mangled,
        should_retry=should_retry,
    )


# ============================================================================
# Speaker: "Dialogue" Format Detection
# ============================================================================

# All quote-like characters (opening and closing)
QUOTE_CHARS_OPENING: Set[str] = {
    '"', "'", "「", "『", "\u201c", "\u2018", "（", "(", "＂",
}
QUOTE_CHARS_CLOSING: Set[str] = {
    '"', "'", "」", "』", "\u201d", "\u2019", "）", ")", "＂",
}
QUOTE_CHARS_ALL: Set[str] = QUOTE_CHARS_OPENING | QUOTE_CHARS_CLOSING

# Quote pairs for balanced detection
QUOTE_PAIRS: Dict[str, str] = {
    '"': '"',
    "'": "'",
    "「": "」",
    "『": "』",
    "\u201c": "\u201d",  # Left/right curly double quotes " "
    "\u2018": "\u2019",  # Left/right curly single quotes ' '
    "（": "）",
    "(": ")",
    "＂": "＂",
}

# Colon equivalents
COLON_CHARS: Set[str] = {":", "："}

# Simple escape commands that can appear between colon and quote (pattern: \X)
SIMPLE_COMMANDS_PATTERN = re.compile(r"^\\[a-zA-Z]$")


@dataclass
class SpeakerFormatInfo:
    """Information about detected speaker dialogue format in a line."""
    
    has_speaker_format: bool = False
    speaker_name: str = ""
    colon_char: str = ""
    colon_pos: int = -1
    opening_quote: str = ""
    opening_quote_pos: int = -1
    closing_quote: str = ""
    closing_quote_pos: int = -1
    dialogue_content: str = ""
    is_balanced: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "has_speaker_format": self.has_speaker_format,
            "speaker_name": self.speaker_name,
            "colon_char": self.colon_char,
            "opening_quote": self.opening_quote,
            "closing_quote": self.closing_quote,
            "is_balanced": self.is_balanced,
        }


def detect_speaker_dialogue_format(line: str) -> SpeakerFormatInfo:
    """Detect Speaker: "Dialogue" format in a line.
    
    Detects patterns like:
    - Name: "dialogue"
    - 太郎：「こんにちは」
    - Speaker: 'thought'
    - Name: (aside)
    
    The colon must be followed by a quote character (with optional space or
    simple commands like \\b between them). The quote must be balanced at end.
    
    Args:
        line: The line to analyze
        
    Returns:
        SpeakerFormatInfo with detection results
    """
    result = SpeakerFormatInfo()
    
    if not line or not line.strip():
        return result
    
    # Find the first colon (or fullwidth colon)
    colon_pos = -1
    colon_char = ""
    for i, ch in enumerate(line):
        if ch in COLON_CHARS:
            colon_pos = i
            colon_char = ch
            break
    
    if colon_pos < 0:
        return result
    
    # Speaker name is everything before the colon (trimmed)
    speaker_name = line[:colon_pos].strip()
    if not speaker_name:
        return result
    
    # After colon, find opening quote
    # Skip: spaces, simple commands like \b
    after_colon = line[colon_pos + 1:]
    search_pos = 0
    
    while search_pos < len(after_colon):
        ch = after_colon[search_pos]
        
        # Skip spaces
        if ch.isspace():
            search_pos += 1
            continue
        
        # Skip simple escape commands (e.g., \b, \n but not \c[0])
        if ch == '\\' and search_pos + 1 < len(after_colon):
            next_ch = after_colon[search_pos + 1]
            if next_ch.isalpha():
                # Check if it's a simple command (no bracket follows)
                if search_pos + 2 >= len(after_colon) or after_colon[search_pos + 2] != '[':
                    search_pos += 2
                    continue
        
        # Check for opening quote
        if ch in QUOTE_CHARS_OPENING:
            result.opening_quote = ch
            result.opening_quote_pos = colon_pos + 1 + search_pos
            break
        
        # Non-space, non-command, non-quote character found - not speaker format
        return result
    
    if not result.opening_quote:
        return result
    
    # Find closing quote - must be at end of line (after trimming trailing spaces)
    line_stripped_end = line.rstrip()
    if not line_stripped_end:
        return result
    
    last_char = line_stripped_end[-1]
    
    # Check if last char is a closing quote that matches the opening
    expected_close = QUOTE_PAIRS.get(result.opening_quote, result.opening_quote)
    
    if last_char == expected_close or last_char in QUOTE_CHARS_CLOSING:
        result.closing_quote = last_char
        result.closing_quote_pos = len(line_stripped_end) - 1
        
        # Check balance - opening and closing should match
        result.is_balanced = (result.closing_quote == expected_close)
        
        # Extract dialogue content
        if result.is_balanced:
            content_start = result.opening_quote_pos + 1
            content_end = result.closing_quote_pos
            if content_end > content_start:
                result.dialogue_content = line[content_start:content_end]
    else:
        # No valid closing quote at end
        return result
    
    # Successfully detected speaker format
    result.has_speaker_format = True
    result.speaker_name = speaker_name
    result.colon_char = colon_char
    result.colon_pos = colon_pos
    
    return result


def validate_speaker_format_preserved(
    original: str,
    translated: str,
    strict: bool = True,
) -> Tuple[bool, List[str], List[str]]:
    """Validate that speaker dialogue format is preserved in translation.
    
    Two-tier validation:
    1. Format structure check (colon + balanced quotes)
    2. Content structure check (speaker name present)
    
    Args:
        original: Original line
        translated: Translated line
        strict: If True, require exact format match; if False, allow variations
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    orig_info = detect_speaker_dialogue_format(original)
    trans_info = detect_speaker_dialogue_format(translated)
    
    # If original doesn't have speaker format, nothing to validate
    if not orig_info.has_speaker_format:
        return True, errors, warnings
    
    # Original has speaker format - translation should too
    if not trans_info.has_speaker_format:
        errors.append(
            f"Speaker format lost: Original has '{orig_info.speaker_name}{orig_info.colon_char}"
            f"{orig_info.opening_quote}...{orig_info.closing_quote}' but translation lacks format"
        )
        return False, errors, warnings
    
    # Check balance
    if orig_info.is_balanced and not trans_info.is_balanced:
        errors.append(
            f"Quote imbalance: Original has balanced quotes but translation does not"
        )
        return False, errors, warnings
    
    # Warnings for format variations
    if strict:
        if orig_info.colon_char != trans_info.colon_char:
            warnings.append(
                f"Colon variant changed: '{orig_info.colon_char}' → '{trans_info.colon_char}'"
            )
        if orig_info.opening_quote != trans_info.opening_quote:
            warnings.append(
                f"Opening quote changed: '{orig_info.opening_quote}' → '{trans_info.opening_quote}'"
            )
    
    return True, errors, warnings


def should_retry_for_speaker_format(
    original: str,
    translated: str,
) -> bool:
    """Determine if translation should be retried due to speaker format loss.
    
    This is the Tier 1 check - automatic retranslation trigger.
    
    Args:
        original: Original line
        translated: Translated line
        
    Returns:
        True if retranslation is recommended
    """
    orig_info = detect_speaker_dialogue_format(original)
    
    # No speaker format in original - no retry needed
    if not orig_info.has_speaker_format:
        return False
    
    trans_info = detect_speaker_dialogue_format(translated)
    
    # Speaker format lost completely
    if not trans_info.has_speaker_format:
        return True
    
    # Quote balance lost
    if orig_info.is_balanced and not trans_info.is_balanced:
        return True
    
    return False


def has_japanese(text: str) -> bool:
    """Check if text contains any Japanese characters (hiragana, katakana, kanji)."""
    for ch in text:
        code = ord(ch)
        if (HIRAGANA_RANGE[0] <= code <= HIRAGANA_RANGE[1] or
            KATAKANA_RANGE[0] <= code <= KATAKANA_RANGE[1] or
            KANJI_RANGE_MAIN[0] <= code <= KANJI_RANGE_MAIN[1] or
            KANJI_RANGE_EXT_A[0] <= code <= KANJI_RANGE_EXT_A[1]):
            return True
    return False


def count_japanese(text: str) -> int:
    """Count the number of Japanese characters in text."""
    count = 0
    for ch in text:
        code = ord(ch)
        if (HIRAGANA_RANGE[0] <= code <= HIRAGANA_RANGE[1] or
            KATAKANA_RANGE[0] <= code <= KATAKANA_RANGE[1] or
            KANJI_RANGE_MAIN[0] <= code <= KANJI_RANGE_MAIN[1] or
            KANJI_RANGE_EXT_A[0] <= code <= KANJI_RANGE_EXT_A[1]):
            count += 1
    return count


def is_symbol_only(text: str) -> bool:
    """Check if text contains only symbols, whitespace, and ASCII punctuation.
    
    No Japanese characters, no alphabetic characters, no digits.
    """
    if not text.strip():
        return False
    for ch in text:
        code = ord(ch)
        # Skip if Japanese
        if (HIRAGANA_RANGE[0] <= code <= HIRAGANA_RANGE[1] or
            KATAKANA_RANGE[0] <= code <= KATAKANA_RANGE[1] or
            KANJI_RANGE_MAIN[0] <= code <= KANJI_RANGE_MAIN[1] or
            KANJI_RANGE_EXT_A[0] <= code <= KANJI_RANGE_EXT_A[1]):
            return False
        # Skip if alphabetic
        if ch.isalpha():
            return False
        # Skip if digit (allow as symbol-only can have numbers in patterns)
        # Actually, pure number lines should also be auto-translated
    return True


def normalize_symbols(text: str) -> str:
    """Normalize fullwidth symbols to halfwidth equivalents."""
    result = []
    for ch in text:
        if ch in SYMBOL_NORMALIZATION:
            result.append(SYMBOL_NORMALIZATION[ch])
        else:
            result.append(ch)
    return "".join(result)


def validate_line_pre(
    line: str,
    existing_translation: Optional[str] = None,
    skip_comments: bool = True,
    skip_equals: bool = True,
) -> ValidationResult:
    """Validate a line before sending to API.
    
    Determines if the line should be:
    - Skipped entirely (with reason)
    - Auto-translated (symbol normalization only)
    - Sent to API for translation
    
    Args:
        line: The preprocessed line to validate
        existing_translation: If the line already has a translation
        skip_comments: Skip lines starting with #
        skip_equals: Skip lines starting with =
    
    Returns:
        ValidationResult with skip_reason or auto_translation if applicable
    """
    stripped = line.strip()
    
    # 1. Empty lines
    if not stripped:
        return ValidationResult(
            is_valid=False,
            skip_reason=SkipReason.EMPTY,
        )
    
    # 2. Comment lines (start with #)
    if skip_comments and COMMENT_PATTERN.match(line):
        return ValidationResult(
            is_valid=False,
            skip_reason=SkipReason.COMMENT,
        )
    
    # 3. Lines starting with =
    if skip_equals and EQUALS_PATTERN.match(line):
        return ValidationResult(
            is_valid=False,
            skip_reason=SkipReason.EQUALS_PREFIX,
        )
    
    # 4. Lines containing only __DEDUP__ placeholder
    if DEDUP_PATTERN.match(stripped):
        return ValidationResult(
            is_valid=False,
            skip_reason=SkipReason.DEDUP_ONLY,
        )
    
    # 5. Lines containing only __PROT__ placeholder
    if PROT_PATTERN.match(stripped):
        return ValidationResult(
            is_valid=False,
            skip_reason=SkipReason.PROT_ONLY,
        )
    
    # 6. Already translated lines
    if existing_translation and existing_translation.strip():
        return ValidationResult(
            is_valid=False,
            skip_reason=SkipReason.ALREADY_TRANSLATED,
        )
    
    # 7. Lines without Japanese characters
    if not has_japanese(line):
        # Check if symbol-only → auto-translate
        if is_symbol_only(line):
            normalized = normalize_symbols(line)
            return ValidationResult(
                is_valid=False,
                skip_reason=SkipReason.SYMBOL_ONLY,
                auto_translation=normalized,
            )
        # Otherwise, just skip (no Japanese, but has other content like English)
        return ValidationResult(
            is_valid=False,
            skip_reason=SkipReason.NO_JAPANESE,
        )
    
    # Line is valid for translation
    return ValidationResult(is_valid=True)


def validate_batch_pre(
    lines: List[str],
    existing_translations: Optional[List[Optional[str]]] = None,
    skip_comments: bool = True,
    skip_equals: bool = True,
) -> BatchValidationResult:
    """Validate a batch of lines before sending to API.
    
    Separates lines into:
    - lines_to_translate: Lines that need API translation
    - skipped_lines: Lines to skip with their reasons
    - auto_translations: Lines with auto-generated translations
    
    Args:
        lines: List of preprocessed lines
        existing_translations: Optional list of existing translations (parallel to lines)
        skip_comments: Skip lines starting with #
        skip_equals: Skip lines starting with =
    
    Returns:
        BatchValidationResult with categorized lines
    """
    if existing_translations is None:
        existing_translations = [None] * len(lines)
    
    lines_to_translate: List[Tuple[int, str]] = []
    skipped_lines: List[Tuple[int, str, SkipReason]] = []
    auto_translations: Dict[int, str] = {}
    
    for i, line in enumerate(lines):
        existing = existing_translations[i] if i < len(existing_translations) else None
        result = validate_line_pre(
            line,
            existing_translation=existing,
            skip_comments=skip_comments,
            skip_equals=skip_equals,
        )
        
        if result.is_valid:
            lines_to_translate.append((i, line))
        elif result.auto_translation is not None:
            auto_translations[i] = result.auto_translation
            # Use skip_reason if provided, otherwise default to ALREADY_TRANSLATED
            reason = result.skip_reason if result.skip_reason else SkipReason.ALREADY_TRANSLATED
            skipped_lines.append((i, line, reason))
        elif result.skip_reason is not None:
            skipped_lines.append((i, line, result.skip_reason))
    
    return BatchValidationResult(
        lines_to_translate=lines_to_translate,
        skipped_lines=skipped_lines,
        auto_translations=auto_translations,
    )


def extract_anchors(text: str) -> Set[str]:
    """Extract anchor characters from text, normalized to canonical forms.
    
    Uses ANCHOR_EQUIVS to identify equivalent characters.
    Returns a set of canonical anchor characters found.
    """
    anchors: Set[str] = set()
    for canonical, equivalents in ANCHOR_EQUIVS.items():
        for equiv in equivalents:
            if equiv in text:
                anchors.add(canonical)
                break
    return anchors


def count_anchor_occurrences(text: str, anchor: str) -> int:
    """Count occurrences of an anchor character and its equivalents in text."""
    count = 0
    for equiv in get_equivs(anchor):
        count += text.count(equiv)
    return count


def validate_line_post(
    original: str,
    translated: str,
    max_japanese_chars: int = 4,
    check_anchors: bool = True,
    check_speaker_format: bool = True,
) -> ValidationResult:
    """Validate a translated line.
    
    Checks:
    1. Translated line doesn't have too many Japanese characters (max 4)
    2. Important anchor characters are preserved
    3. Speaker: "Dialogue" format is preserved (if present in original)
    
    Args:
        original: The original (preprocessed) line
        translated: The translated line from API
        max_japanese_chars: Maximum allowed Japanese characters in translation
        check_anchors: Whether to check for anchor preservation
        check_speaker_format: Whether to check speaker dialogue format preservation
    
    Returns:
        ValidationResult with errors and warnings
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    # 1. Check Japanese character count in translation
    jp_count = count_japanese(translated)
    if jp_count > max_japanese_chars:
        errors.append(
            f"Translation contains {jp_count} Japanese characters "
            f"(max allowed: {max_japanese_chars})"
        )
    elif jp_count > 0:
        warnings.append(f"Translation contains {jp_count} Japanese character(s)")
    
    # 2. Check anchor preservation
    if check_anchors:
        orig_anchors = extract_anchors(original)
        trans_anchors = extract_anchors(translated)
        
        # Check for missing anchors
        missing = orig_anchors - trans_anchors
        if missing:
            for anchor in missing:
                orig_count = count_anchor_occurrences(original, anchor)
                trans_count = count_anchor_occurrences(translated, anchor)
                if orig_count > trans_count:
                    warnings.append(
                        f"Anchor '{anchor}' appears {orig_count} time(s) in original "
                        f"but only {trans_count} time(s) in translation"
                    )
    
    # 3. Check speaker format preservation
    if check_speaker_format:
        format_valid, format_errors, format_warnings = validate_speaker_format_preserved(
            original, translated, strict=False
        )
        errors.extend(format_errors)
        warnings.extend(format_warnings)
    
    is_valid = len(errors) == 0
    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
    )


def validate_batch_post(
    originals: List[str],
    translations: List[str],
    max_japanese_chars: int = 4,
    check_anchors: bool = True,
    check_speaker_format: bool = True,
) -> List[ValidationResult]:
    """Validate a batch of translated lines.
    
    Args:
        originals: Original (preprocessed) lines
        translations: Translated lines from API
        max_japanese_chars: Maximum allowed Japanese characters per translation
        check_anchors: Whether to check for anchor preservation
        check_speaker_format: Whether to check speaker dialogue format preservation
    
    Returns:
        List of ValidationResult for each line pair
    """
    results: List[ValidationResult] = []
    
    for orig, trans in zip(originals, translations):
        result = validate_line_post(
            orig,
            trans,
            max_japanese_chars=max_japanese_chars,
            check_anchors=check_anchors,
            check_speaker_format=check_speaker_format,
        )
        results.append(result)
    
    return results


def reassemble_translations(
    original_count: int,
    api_translations: List[str],
    lines_to_translate: List[Tuple[int, str]],
    auto_translations: Dict[int, str],
    skipped_lines: List[Tuple[int, str, SkipReason]],
    preserve_skipped: bool = True,
) -> List[str]:
    """Reassemble translations into the original order.
    
    Takes API translations for sent lines and combines them with:
    - Auto-translations for symbol-only lines
    - Original content for skipped lines (optionally)
    
    Args:
        original_count: Total number of original lines
        api_translations: Translations received from API
        lines_to_translate: (index, line) pairs that were sent to API
        auto_translations: index -> auto-translated content
        skipped_lines: (index, line, reason) for skipped lines
        preserve_skipped: If True, skipped lines keep original content
    
    Returns:
        List of translations in original order
    """
    result: List[str] = [""] * original_count
    
    # Fill in API translations
    for (idx, _), translation in zip(lines_to_translate, api_translations):
        result[idx] = translation
    
    # Fill in auto-translations
    for idx, auto_trans in auto_translations.items():
        result[idx] = auto_trans
    
    # Fill in skipped lines (preserve original or leave empty)
    if preserve_skipped:
        for idx, line, reason in skipped_lines:
            if idx not in auto_translations:
                # For comments and special lines, preserve original
                if reason in (SkipReason.COMMENT, SkipReason.EQUALS_PREFIX,
                              SkipReason.DEDUP_ONLY, SkipReason.PROT_ONLY):
                    result[idx] = line
                # For empty lines, keep empty
                elif reason == SkipReason.EMPTY:
                    result[idx] = ""
                # For already translated or no Japanese, preserve original
                else:
                    result[idx] = line
    
    return result


# ============================================================================
# Repetition Detection
# ============================================================================


@dataclass
class RepetitionDetectionResult:
    """Result of detecting repetition in text."""
    
    has_repetition: bool = False
    repetition_type: Optional[str] = None  # "single_char", "multi_char", "trailing"
    repeated_pattern: Optional[str] = None
    repetition_count: int = 0
    details: str = ""
    should_retry: bool = False


# Default thresholds for repetition detection
DEFAULT_SINGLE_CHAR_THRESHOLD = 20  # Same char > 20 times
DEFAULT_MULTI_CHAR_THRESHOLD = 10   # Same pattern > 10 times
DEFAULT_TRAILING_THRESHOLD = 15      # Pattern at end > 15 times


def detect_single_char_repetition(
    text: str,
    threshold: int = DEFAULT_SINGLE_CHAR_THRESHOLD,
) -> Optional[Tuple[str, int]]:
    """Detect if a single character is repeated excessively.
    
    Args:
        text: Text to check for repetition.
        threshold: Minimum consecutive repetitions to trigger detection.
        
    Returns:
        Tuple of (repeated_char, count) if detected, None otherwise.
    """
    if not text:
        return None
    
    # Pattern: any single character repeated threshold+ times
    pattern = re.compile(r'(.)\1{' + str(threshold - 1) + r',}')
    match = pattern.search(text)
    
    if match:
        repeated_char = match.group(1)
        count = len(match.group(0))
        return repeated_char, count
    
    return None


def detect_multi_char_repetition(
    text: str,
    threshold: int = DEFAULT_MULTI_CHAR_THRESHOLD,
    min_pattern_len: int = 2,
    max_pattern_len: int = 10,
) -> Optional[Tuple[str, int]]:
    """Detect if a multi-character pattern is repeated excessively.
    
    Args:
        text: Text to check for repetition.
        threshold: Minimum consecutive repetitions to trigger detection.
        min_pattern_len: Minimum length of the repeated pattern.
        max_pattern_len: Maximum length of the repeated pattern.
        
    Returns:
        Tuple of (repeated_pattern, count) if detected, None otherwise.
    """
    if not text or len(text) < min_pattern_len * threshold:
        return None
    
    # Pattern: any sequence of min-max chars repeated threshold+ times
    pattern = re.compile(
        r'(.{' + str(min_pattern_len) + r',' + str(max_pattern_len) + r'})\1{' 
        + str(threshold - 1) + r',}'
    )
    match = pattern.search(text)
    
    if match:
        repeated_pattern = match.group(1)
        total_len = len(match.group(0))
        count = total_len // len(repeated_pattern)
        return repeated_pattern, count
    
    return None


def detect_trailing_repetition(
    text: str,
    threshold: int = DEFAULT_TRAILING_THRESHOLD,
) -> Optional[Tuple[str, int]]:
    """Detect if text ends with an excessively repeated pattern.
    
    This catches cases where the model "runs away" at the end of output.
    
    Args:
        text: Text to check for trailing repetition.
        threshold: Minimum repetitions at end to trigger detection.
        
    Returns:
        Tuple of (repeated_pattern, count) if detected, None otherwise.
    """
    if not text:
        return None
    
    text = text.rstrip()  # Strip trailing whitespace first
    
    # Check for single character trailing repetition
    pattern = re.compile(r'(.)\1{' + str(threshold - 1) + r',}$')
    match = pattern.search(text)
    if match:
        return match.group(1), len(match.group(0))
    
    # Check for multi-character trailing repetition (2-5 chars)
    pattern = re.compile(r'(.{2,5})\1{' + str(threshold - 1) + r',}$')
    match = pattern.search(text)
    if match:
        repeated_pattern = match.group(1)
        total_len = len(match.group(0))
        count = total_len // len(repeated_pattern)
        return repeated_pattern, count
    
    return None


def detect_repetition(
    text: str,
    single_char_threshold: int = DEFAULT_SINGLE_CHAR_THRESHOLD,
    multi_char_threshold: int = DEFAULT_MULTI_CHAR_THRESHOLD,
    trailing_threshold: int = DEFAULT_TRAILING_THRESHOLD,
) -> RepetitionDetectionResult:
    """Comprehensive repetition detection for LLM output.
    
    Detects three types of problematic repetition:
    1. Single character repetition (e.g., "ああああああああああ...")
    2. Multi-character pattern repetition (e.g., "hello hello hello...")
    3. Trailing repetition (pattern repeats at end of text)
    
    Args:
        text: Text to check for repetition.
        single_char_threshold: Threshold for single char detection.
        multi_char_threshold: Threshold for multi-char pattern detection.
        trailing_threshold: Threshold for trailing repetition detection.
        
    Returns:
        RepetitionDetectionResult with detection details.
    """
    result = RepetitionDetectionResult()
    
    if not text:
        return result
    
    # Check single character repetition (highest priority - most severe)
    single_result = detect_single_char_repetition(text, single_char_threshold)
    if single_result:
        char, count = single_result
        result.has_repetition = True
        result.repetition_type = "single_char"
        result.repeated_pattern = char
        result.repetition_count = count
        result.details = f"Character '{char}' repeated {count} times consecutively"
        result.should_retry = True
        return result
    
    # Check multi-character pattern repetition
    multi_result = detect_multi_char_repetition(text, multi_char_threshold)
    if multi_result:
        pattern, count = multi_result
        result.has_repetition = True
        result.repetition_type = "multi_char"
        result.repeated_pattern = pattern
        result.repetition_count = count
        result.details = f"Pattern '{pattern}' repeated {count} times consecutively"
        result.should_retry = True
        return result
    
    # Check trailing repetition
    trailing_result = detect_trailing_repetition(text, trailing_threshold)
    if trailing_result:
        pattern, count = trailing_result
        result.has_repetition = True
        result.repetition_type = "trailing"
        result.repeated_pattern = pattern
        result.repetition_count = count
        result.details = f"Trailing pattern '{pattern}' repeated {count} times at end"
        result.should_retry = True
        return result
    
    return result


def detect_batch_repetition(
    translations: List[str],
    single_char_threshold: int = DEFAULT_SINGLE_CHAR_THRESHOLD,
    multi_char_threshold: int = DEFAULT_MULTI_CHAR_THRESHOLD,
    trailing_threshold: int = DEFAULT_TRAILING_THRESHOLD,
) -> Dict[int, RepetitionDetectionResult]:
    """Check a batch of translations for repetition issues.
    
    Args:
        translations: List of translated lines to check.
        single_char_threshold: Threshold for single char detection.
        multi_char_threshold: Threshold for multi-char pattern detection.
        trailing_threshold: Threshold for trailing repetition detection.
        
    Returns:
        Dict mapping line index to RepetitionDetectionResult for lines with issues.
    """
    results: Dict[int, RepetitionDetectionResult] = {}
    
    for i, text in enumerate(translations):
        result = detect_repetition(
            text,
            single_char_threshold,
            multi_char_threshold,
            trailing_threshold,
        )
        if result.has_repetition:
            results[i] = result
    
    return results


# ============================================================================
# Comprehensive Translation Validation
# ============================================================================


class RetryReason(Enum):
    """Reasons why a translation should be retried."""
    
    EMPTY_TRANSLATION = "empty_translation"
    PLACEHOLDER_MISSING = "placeholder_missing"
    SPEAKER_FORMAT_LOST = "speaker_format_lost"
    TOO_MANY_JAPANESE = "too_many_japanese"
    LINE_COUNT_MISMATCH = "line_count_mismatch"
    REPETITION_DETECTED = "repetition_detected"


@dataclass
class TranslationValidationResult:
    """Comprehensive validation result for a single line translation."""
    
    line_index: int
    is_valid: bool
    should_retry: bool
    retry_reasons: List[RetryReason] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    placeholder_result: Optional[PlaceholderValidationResult] = None


@dataclass
class BatchTranslationValidationResult:
    """Comprehensive validation result for a batch of translations."""
    
    is_valid: bool
    total_lines: int
    valid_count: int
    retry_count: int
    line_results: List[TranslationValidationResult] = field(default_factory=list)
    lines_to_retry: List[int] = field(default_factory=list)  # Indices that need retry
    
    @property
    def success_rate(self) -> float:
        """Calculate the success rate."""
        if self.total_lines == 0:
            return 1.0
        return self.valid_count / self.total_lines


def validate_translation_comprehensive(
    original: str,
    translated: str,
    line_index: int = 0,
    max_japanese_chars: int = 4,
    check_placeholders: bool = True,
    check_speaker_format: bool = True,
    check_anchors: bool = True,
    check_repetition: bool = True,
) -> TranslationValidationResult:
    """Perform comprehensive validation on a translated line.
    
    Combines all validation checks:
    1. Empty translation check
    2. Placeholder preservation
    3. Speaker format preservation
    4. Japanese character limit
    5. Anchor preservation
    6. Repetition detection (infinite loops, runaway patterns)
    
    Args:
        original: Original (preprocessed) line.
        translated: Translated line from API.
        line_index: Index of this line in the batch.
        max_japanese_chars: Maximum allowed Japanese characters.
        check_placeholders: Whether to check placeholder preservation.
        check_speaker_format: Whether to check speaker format.
        check_anchors: Whether to check anchor preservation.
        check_repetition: Whether to check for repetitive patterns.
        
    Returns:
        TranslationValidationResult with all validation details.
    """
    errors: List[str] = []
    warnings: List[str] = []
    retry_reasons: List[RetryReason] = []
    placeholder_result: Optional[PlaceholderValidationResult] = None
    
    # 1. Empty translation check
    if not translated or not translated.strip():
        if original and original.strip():
            errors.append("Translation is empty but original has content")
            retry_reasons.append(RetryReason.EMPTY_TRANSLATION)
    
    # 2. Placeholder preservation
    if check_placeholders:
        placeholder_result = validate_placeholder_preserved(original, translated)
        if not placeholder_result.is_valid:
            if placeholder_result.missing_placeholders:
                errors.append(
                    f"Missing placeholders: {', '.join(placeholder_result.missing_placeholders)}"
                )
                retry_reasons.append(RetryReason.PLACEHOLDER_MISSING)
            if placeholder_result.mangled_placeholders:
                warnings.append(
                    f"Mangled placeholders: {', '.join(placeholder_result.mangled_placeholders)}"
                )
    
    # 3. Speaker format preservation
    if check_speaker_format:
        if should_retry_for_speaker_format(original, translated):
            errors.append("Speaker dialogue format lost in translation")
            retry_reasons.append(RetryReason.SPEAKER_FORMAT_LOST)
    
    # 4. Japanese character limit
    jp_count = count_japanese(translated)
    if jp_count > max_japanese_chars:
        errors.append(
            f"Translation contains {jp_count} Japanese characters "
            f"(max allowed: {max_japanese_chars})"
        )
        retry_reasons.append(RetryReason.TOO_MANY_JAPANESE)
    elif jp_count > 0:
        warnings.append(f"Translation contains {jp_count} Japanese character(s)")
    
    # 5. Anchor preservation
    if check_anchors:
        orig_anchors = extract_anchors(original)
        trans_anchors = extract_anchors(translated)
        missing_anchors = orig_anchors - trans_anchors
        if missing_anchors:
            for anchor in missing_anchors:
                orig_count = count_anchor_occurrences(original, anchor)
                trans_count = count_anchor_occurrences(translated, anchor)
                if orig_count > trans_count:
                    warnings.append(
                        f"Anchor '{anchor}' appears {orig_count} time(s) in original "
                        f"but only {trans_count} time(s) in translation"
                    )
    
    # 6. Repetition detection
    if check_repetition:
        repetition_result = detect_repetition(translated)
        if repetition_result.has_repetition:
            errors.append(f"Repetition detected: {repetition_result.details}")
            retry_reasons.append(RetryReason.REPETITION_DETECTED)
    
    is_valid = len(errors) == 0
    should_retry = len(retry_reasons) > 0
    
    return TranslationValidationResult(
        line_index=line_index,
        is_valid=is_valid,
        should_retry=should_retry,
        retry_reasons=retry_reasons,
        errors=errors,
        warnings=warnings,
        placeholder_result=placeholder_result,
    )


def validate_batch_comprehensive(
    originals: List[str],
    translations: List[str],
    max_japanese_chars: int = 4,
    check_placeholders: bool = True,
    check_speaker_format: bool = True,
    check_anchors: bool = True,
    check_repetition: bool = True,
) -> BatchTranslationValidationResult:
    """Validate a batch of translations comprehensively.
    
    Returns per-line validation results with retry recommendations.
    
    Args:
        originals: Original (preprocessed) lines.
        translations: Translated lines from API.
        max_japanese_chars: Maximum allowed Japanese characters.
        check_placeholders: Whether to check placeholder preservation.
        check_speaker_format: Whether to check speaker format.
        check_anchors: Whether to check anchor preservation.
        check_repetition: Whether to check for repetitive patterns.
        
    Returns:
        BatchTranslationValidationResult with all line results.
    """
    # Handle line count mismatch
    if len(originals) != len(translations):
        # Return a result indicating the batch needs full retry
        return BatchTranslationValidationResult(
            is_valid=False,
            total_lines=len(originals),
            valid_count=0,
            retry_count=len(originals),
            line_results=[],
            lines_to_retry=list(range(len(originals))),
        )
    
    line_results: List[TranslationValidationResult] = []
    lines_to_retry: List[int] = []
    valid_count = 0
    
    for i, (orig, trans) in enumerate(zip(originals, translations)):
        result = validate_translation_comprehensive(
            original=orig,
            translated=trans,
            line_index=i,
            max_japanese_chars=max_japanese_chars,
            check_placeholders=check_placeholders,
            check_speaker_format=check_speaker_format,
            check_anchors=check_anchors,
            check_repetition=check_repetition,
        )
        line_results.append(result)
        
        if result.is_valid:
            valid_count += 1
        if result.should_retry:
            lines_to_retry.append(i)
    
    is_valid = len(lines_to_retry) == 0
    
    return BatchTranslationValidationResult(
        is_valid=is_valid,
        total_lines=len(originals),
        valid_count=valid_count,
        retry_count=len(lines_to_retry),
        line_results=line_results,
        lines_to_retry=lines_to_retry,
    )


# ============================================================================
# Character/Word Validation (TASK 36.2)
# ============================================================================


class ValidationSeverity(Enum):
    """Severity of a validation finding.
    
    TASK 36.2: Yellow = autofix available and valid, Red = no autofix.
    """
    
    WARNING = "warning"  # Yellow - autofix available
    ERROR = "error"      # Red - no autofix available


@dataclass
class CharacterWordFinding:
    """A single character/word validation finding.
    
    TASK 36.2: Structured finding for character/word validation.
    """
    
    idx: int                    # Line index
    field: str                  # Which field (tl, post, wordwr, final)
    offending_token: str        # The offending character or word
    token_type: str             # "character" or "word"
    position: int               # Position in the text (character offset)
    suggestion: Optional[str]   # Suggested replacement (from autofix map)
    severity: ValidationSeverity  # WARNING (autofix available) or ERROR


@dataclass
class CharacterWordValidationResult:
    """Result of character/word validation for a batch of lines.
    
    TASK 36.2: Batch validation result with findings and counts.
    """
    
    findings: List[CharacterWordFinding] = field(default_factory=list)
    total_lines_scanned: int = 0
    lines_with_issues: int = 0
    warning_count: int = 0
    error_count: int = 0
    
    @property
    def has_issues(self) -> bool:
        """Check if any issues were found."""
        return len(self.findings) > 0
    
    @property
    def total_issues(self) -> int:
        """Get total number of issues."""
        return len(self.findings)


def _build_distinct_char_set(texts: List[str]) -> Set[str]:
    """Build a set of distinct characters from all texts.
    
    TASK 36.2: First pass of the two-pass algorithm.
    
    Args:
        texts: List of text strings to analyze.
        
    Returns:
        Set of distinct characters found.
    """
    char_set: Set[str] = set()
    for text in texts:
        char_set.update(text)
    return char_set


def _find_offending_characters(
    distinct_chars: Set[str],
    whitelist: str,
    blacklist: str,
) -> Set[str]:
    """Find characters that violate whitelist/blacklist rules.
    
    TASK 36.2: Identify offending characters from the distinct set.
    
    Logic:
    - If whitelist is non-empty: character must be in whitelist
    - If blacklist is non-empty: character must NOT be in blacklist
    - Both can be active simultaneously
    
    Args:
        distinct_chars: Set of distinct characters from texts.
        whitelist: Allowed characters (empty = all allowed).
        blacklist: Forbidden characters.
        
    Returns:
        Set of offending characters.
    """
    offending: Set[str] = set()
    
    whitelist_set = set(whitelist) if whitelist else None
    blacklist_set = set(blacklist) if blacklist else set()
    
    for char in distinct_chars:
        # Check whitelist (if non-empty, char must be in it)
        if whitelist_set is not None and char not in whitelist_set:
            offending.add(char)
            continue
        
        # Check blacklist (char must NOT be in it)
        if char in blacklist_set:
            offending.add(char)
    
    return offending


def _compile_word_patterns(word_blacklist: List[str]) -> List[re.Pattern]:
    """Compile regex patterns for word blacklist matching.
    
    TASK 36.2: Case-insensitive, whole word matching.
    
    Args:
        word_blacklist: List of forbidden words/phrases.
        
    Returns:
        List of compiled regex patterns.
    """
    patterns: List[re.Pattern] = []
    for word in word_blacklist:
        if not word:
            continue
        # Escape special regex characters and create whole-word pattern
        escaped = re.escape(word)
        # Use word boundaries for whole word matching
        pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
        patterns.append(pattern)
    return patterns


def validate_character_word(
    lines: List[Dict[str, Any]],
    whitelist: str = "",
    blacklist: str = "",
    word_blacklist: Optional[List[str]] = None,
    autofix_map: Optional[Dict[str, str]] = None,
    fields_to_check: Optional[List[str]] = None,
) -> CharacterWordValidationResult:
    """Validate lines for forbidden characters and words.
    
    TASK 36.2: High-performance scanner using two-pass algorithm:
    1. First pass: build distinct character set from all texts
    2. Compare distinct set against whitelist/blacklist
    3. Second pass: scan only for offending characters and forbidden words
    
    Args:
        lines: List of line dictionaries with fields like 'tl', 'post', 'wordwr', 'final'.
        whitelist: Allowed characters (empty = all allowed).
        blacklist: Forbidden characters.
        word_blacklist: List of forbidden words/phrases (case-insensitive, whole word).
        autofix_map: Dict mapping offending chars to replacement chars.
        fields_to_check: Which fields to check (default: ['tl', 'post', 'wordwr', 'final']).
        
    Returns:
        CharacterWordValidationResult with all findings.
    """
    if word_blacklist is None:
        word_blacklist = []
    if autofix_map is None:
        autofix_map = {}
    if fields_to_check is None:
        fields_to_check = ["tl", "post", "wordwr", "final"]
    
    # Fast exit: nothing to check
    if not whitelist and not blacklist and not word_blacklist:
        return CharacterWordValidationResult(total_lines_scanned=len(lines))
    
    # Determine what types of checks we need
    check_chars = bool(whitelist or blacklist)
    check_words = bool(word_blacklist)
    
    # Collect all texts to scan
    texts_by_location: List[Tuple[int, str, str]] = []  # (idx, field, text)
    for line in lines:
        idx = line.get("idx", 0)
        for field_name in fields_to_check:
            text = line.get(field_name)
            if text:
                texts_by_location.append((idx, field_name, text))
    
    if not texts_by_location:
        return CharacterWordValidationResult(total_lines_scanned=len(lines))
    
    findings: List[CharacterWordFinding] = []
    lines_with_issues: Set[int] = set()
    
    # Character validation (two-pass algorithm)
    if check_chars:
        # First pass: build distinct character set
        all_texts = [text for _, _, text in texts_by_location]
        distinct_chars = _build_distinct_char_set(all_texts)
        
        # Find offending characters
        offending_chars = _find_offending_characters(distinct_chars, whitelist, blacklist)
        
        if offending_chars:
            # Second pass: scan for offending characters
            for idx, field_name, text in texts_by_location:
                for pos, char in enumerate(text):
                    if char in offending_chars:
                        suggestion = autofix_map.get(char)
                        
                        # Determine severity
                        if suggestion:
                            # Check if the replacement is valid
                            whitelist_set = set(whitelist) if whitelist else None
                            blacklist_set = set(blacklist) if blacklist else set()
                            
                            replacement_valid = True
                            if whitelist_set and suggestion not in whitelist_set:
                                replacement_valid = False
                            if suggestion in blacklist_set:
                                replacement_valid = False
                            
                            severity = (ValidationSeverity.WARNING if replacement_valid 
                                       else ValidationSeverity.ERROR)
                        else:
                            severity = ValidationSeverity.ERROR
                        
                        findings.append(CharacterWordFinding(
                            idx=idx,
                            field=field_name,
                            offending_token=char,
                            token_type="character",
                            position=pos,
                            suggestion=suggestion,
                            severity=severity,
                        ))
                        lines_with_issues.add(idx)
    
    # Word validation
    if check_words:
        word_patterns = _compile_word_patterns(word_blacklist)
        
        for idx, field_name, text in texts_by_location:
            for pattern in word_patterns:
                for match in pattern.finditer(text):
                    offending_word = match.group()
                    
                    # Words don't have autofix
                    findings.append(CharacterWordFinding(
                        idx=idx,
                        field=field_name,
                        offending_token=offending_word,
                        token_type="word",
                        position=match.start(),
                        suggestion=None,
                        severity=ValidationSeverity.ERROR,
                    ))
                    lines_with_issues.add(idx)
    
    # Calculate counts
    warning_count = sum(1 for f in findings if f.severity == ValidationSeverity.WARNING)
    error_count = sum(1 for f in findings if f.severity == ValidationSeverity.ERROR)
    
    return CharacterWordValidationResult(
        findings=findings,
        total_lines_scanned=len(lines),
        lines_with_issues=len(lines_with_issues),
        warning_count=warning_count,
        error_count=error_count,
    )


def apply_autofix(
    text: str,
    autofix_map: Dict[str, str],
    whitelist: str = "",
    blacklist: str = "",
) -> Tuple[str, int]:
    """Apply autofix replacements to text.
    
    TASK 36.2: Apply character replacements from autofix map.
    Only applies fixes where the replacement is valid under whitelist/blacklist rules.
    
    Args:
        text: Text to fix.
        autofix_map: Dict mapping offending chars to replacement chars.
        whitelist: Allowed characters (for validating replacements).
        blacklist: Forbidden characters (for validating replacements).
        
    Returns:
        Tuple of (fixed_text, number_of_replacements_made).
    """
    if not autofix_map:
        return text, 0
    
    whitelist_set = set(whitelist) if whitelist else None
    blacklist_set = set(blacklist) if blacklist else set()
    
    result_chars: List[str] = []
    replacements_made = 0
    
    for char in text:
        if char in autofix_map:
            replacement = autofix_map[char]
            
            # Check if replacement is valid
            replacement_valid = True
            if whitelist_set and replacement not in whitelist_set:
                replacement_valid = False
            if replacement in blacklist_set:
                replacement_valid = False
            
            if replacement_valid:
                result_chars.append(replacement)
                replacements_made += 1
            else:
                result_chars.append(char)  # Keep original if replacement invalid
        else:
            result_chars.append(char)
    
    return "".join(result_chars), replacements_made


def apply_autofix_to_lines(
    lines: List[Dict[str, Any]],
    autofix_map: Dict[str, str],
    whitelist: str = "",
    blacklist: str = "",
    fields_to_fix: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Apply autofix to multiple lines.
    
    TASK 36.2: Apply character replacements to line dictionaries.
    
    Args:
        lines: List of line dictionaries.
        autofix_map: Dict mapping offending chars to replacement chars.
        whitelist: Allowed characters.
        blacklist: Forbidden characters.
        fields_to_fix: Which fields to fix (default: ['tl', 'post', 'wordwr', 'final']).
        
    Returns:
        Tuple of (fixed_lines, total_replacements_made).
    """
    if fields_to_fix is None:
        fields_to_fix = ["tl", "post", "wordwr", "final"]
    
    total_replacements = 0
    
    for line in lines:
        for field_name in fields_to_fix:
            text = line.get(field_name)
            if text:
                fixed_text, count = apply_autofix(
                    text, autofix_map, whitelist, blacklist
                )
                if count > 0:
                    line[field_name] = fixed_text
                    total_replacements += count
    
    return lines, total_replacements


def get_findings_summary(result: CharacterWordValidationResult) -> str:
    """Get a human-readable summary of validation findings.
    
    TASK 36.2: Format findings for display.
    
    Args:
        result: Validation result.
        
    Returns:
        Summary string.
    """
    if not result.has_issues:
        return f"✓ No issues found in {result.total_lines_scanned} lines"
    
    parts = []
    parts.append(f"Found {result.total_issues} issue(s) in {result.lines_with_issues} line(s)")
    
    if result.warning_count > 0:
        parts.append(f"  ⚠ {result.warning_count} warning(s) (autofix available)")
    if result.error_count > 0:
        parts.append(f"  ✗ {result.error_count} error(s) (no autofix)")
    
    return "\n".join(parts)


def group_findings_by_line(
    findings: List[CharacterWordFinding],
) -> Dict[int, List[CharacterWordFinding]]:
    """Group findings by line index.
    
    Args:
        findings: List of findings.
        
    Returns:
        Dict mapping line index to list of findings.
    """
    grouped: Dict[int, List[CharacterWordFinding]] = {}
    for finding in findings:
        if finding.idx not in grouped:
            grouped[finding.idx] = []
        grouped[finding.idx].append(finding)
    return grouped


def group_findings_by_token(
    findings: List[CharacterWordFinding],
) -> Dict[str, List[CharacterWordFinding]]:
    """Group findings by offending token.
    
    Args:
        findings: List of findings.
        
    Returns:
        Dict mapping offending token to list of findings.
    """
    grouped: Dict[str, List[CharacterWordFinding]] = {}
    for finding in findings:
        if finding.offending_token not in grouped:
            grouped[finding.offending_token] = []
        grouped[finding.offending_token].append(finding)
    return grouped
