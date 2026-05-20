"""
Standard Post-Process Suite for CherryAI.

Provides comprehensive recovery mechanisms for translations that have
structural issues like missing/mangled placeholders, unbalanced brackets,
and incorrect formatting.

Recovery vs Retry Decision:
- If recovery possible without LLM: Apply fix, log warning, continue
- If recovery impossible: Flag for retry (with emphasis prompt)
- Track recovery rate per session for quality monitoring
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .modehelper import ANCHOR_EQUIVS, get_equivs

try:
    from CherryAI.formats.parser_base import _split_speaker_dialogue
except ImportError:  # pragma: no cover
    from formats.parser_base import _split_speaker_dialogue


# ============================================================================
# Enums and Data Classes
# ============================================================================


class RecoveryType(Enum):
    """Types of recovery operations that can be performed."""
    
    PLACEHOLDER_CASE = "placeholder_case"  # __PROTECTED__ -> __PROTECTED__
    PLACEHOLDER_MANGLED = "placeholder_mangled"  # __PR OT__ -> __PROTECTED__
    PLACEHOLDER_MISSING = "placeholder_missing"  # Placeholder removed by LLM
    PLACEHOLDER_POSITION_SHIFT = "placeholder_position_shift"  # TASK 42.10
    PLACEHOLDER_EXTRA = "placeholder_extra"  # TASK 42.10
    QUOTE_BALANCE = "quote_balance"  # Unbalanced quotes
    BRACKET_BALANCE = "bracket_balance"  # Missing bracket pairs
    WHITESPACE_NORMALIZATION = "whitespace_normalization"  # Errant spacing
    CODE_CHARACTER = "code_character"  # Missing code characters
    CODE_PATTERN = "code_pattern"  # Preserve-action code pattern translated
    BR_TAG = "br_tag"  # Missing <br> tags
    SPEAKER_FORMAT = "speaker_format"  # Speaker: "Dialogue" format


class RecoveryAction(Enum):
    """Action taken for a recovery issue."""
    
    RECOVERED = "recovered"  # Fixed automatically
    NEEDS_RETRY = "needs_retry"  # Cannot fix, needs retry
    SKIPPED = "skipped"  # Not recoverable, kept original


@dataclass
class RecoveryIssue:
    """Describes a single issue found during validation."""
    
    type: RecoveryType
    description: str
    position: int = -1  # Character position where issue was found
    original_text: str = ""
    recovered_text: str = ""
    action: RecoveryAction = RecoveryAction.SKIPPED


@dataclass
class RecoveryResult:
    """Result of recovery attempt for a single line."""
    
    original: str
    recovered: str
    issues: List[RecoveryIssue] = field(default_factory=list)
    fully_recovered: bool = True
    needs_retry: bool = False
    
    @property
    def had_issues(self) -> bool:
        """Check if any issues were found."""
        return len(self.issues) > 0
    
    @property
    def recovery_count(self) -> int:
        """Count of issues that were recovered."""
        return sum(1 for i in self.issues if i.action == RecoveryAction.RECOVERED)


@dataclass
class BatchRecoveryResult:
    """Result of recovery for a batch of lines."""
    
    results: List[RecoveryResult] = field(default_factory=list)
    total_issues: int = 0
    total_recovered: int = 0
    total_needs_retry: int = 0
    
    def add_result(self, result: RecoveryResult) -> None:
        """Add a recovery result to the batch."""
        self.results.append(result)
        self.total_issues += len(result.issues)
        self.total_recovered += result.recovery_count
        if result.needs_retry:
            self.total_needs_retry += 1


@dataclass
class RecoveryStats:
    """Statistics for recovery operations in a session."""
    
    total_lines_processed: int = 0
    lines_with_issues: int = 0
    issues_by_type: Dict[RecoveryType, int] = field(default_factory=dict)
    recovered_by_type: Dict[RecoveryType, int] = field(default_factory=dict)
    retry_recommendations: int = 0
    
    def record_issue(self, issue: RecoveryIssue) -> None:
        """Record an issue in statistics."""
        self.issues_by_type[issue.type] = self.issues_by_type.get(issue.type, 0) + 1
        if issue.action == RecoveryAction.RECOVERED:
            self.recovered_by_type[issue.type] = self.recovered_by_type.get(issue.type, 0) + 1
    
    def get_recovery_rate(self) -> float:
        """Get overall recovery rate as percentage."""
        total = sum(self.issues_by_type.values())
        if total == 0:
            return 100.0
        recovered = sum(self.recovered_by_type.values())
        return (recovered / total) * 100.0


# ============================================================================
# Placeholder Patterns
# ============================================================================


# Standard placeholder pattern: __PROTECTED__, __PROTECTED_1__, __NAME__, etc.
PLACEHOLDER_PATTERN = re.compile(r"__([A-Za-z][A-Za-z0-9]*)(?:_(\d+))?__")

# Pattern for placeholders with internal whitespace (clearly mangled)
WHITESPACE_PLACEHOLDER_PATTERN = re.compile(r"__\s+([A-Za-z][A-Za-z0-9]*)\s*(?:_\s*(\d+))?\s+__")

# Translated placeholder patterns (only match specific known translations)
TRANSLATED_PLACEHOLDER_PATTERNS = [
    # Protection -> PROT
    (re.compile(r"__\s*PROTECTION\s*(?:_\s*(\d+))?\s*__", re.IGNORECASE), "__PROTECTED__"),
    (re.compile(r"__\s*PROTECTED\s*(?:_\s*(\d+))?\s*__", re.IGNORECASE), "__PROTECTED__"),
]

# Known placeholder types (for recovery hinting)
KNOWN_PLACEHOLDERS = {"PROT", "NAME", "CODE", "VAR", "ITEM", "SKILL", "NUM"}

CUSTOM_PLACEHOLDER_TAG_PREFIX = "custom_placeholder"
GENERIC_PLACEHOLDER_TAG_PREFIX = "generic_placeholder"
EDGE_WHITESPACE_TAG_RE = re.compile(
    r"^(?P<kind>indent|trail):u\+(?P<code>[0-9a-fA-F]{4,6})x(?P<count>[1-9][0-9]*)$"
)


def _collect_edge_whitespace(text: str, from_start: bool) -> List[str]:
    """Collect leading or trailing whitespace characters in source order."""
    chars: List[str] = []
    iterator = text if from_start else reversed(text)
    for ch in iterator:
        if not ch.isspace():
            break
        chars.append(ch)
    if not from_start:
        chars.reverse()
    return chars


def _encode_edge_whitespace(kind: str, chars: List[str]) -> List[str]:
    """Encode whitespace runs as canonical manifest tags."""
    if not chars:
        return []

    tags: List[str] = []
    current = chars[0]
    count = 1
    for ch in chars[1:]:
        if ch == current:
            count += 1
            continue
        tags.append(f"{kind}:u+{ord(current):04X}x{count}")
        current = ch
        count = 1
    tags.append(f"{kind}:u+{ord(current):04X}x{count}")
    return tags


def _decode_edge_whitespace_tags(
    line_tags: List[str] | Tuple[str, ...] | Set[str],
) -> Tuple[str, str]:
    """Decode canonical edge-whitespace tags into indent and trail text."""
    indent_parts: List[str] = []
    trail_parts: List[str] = []
    for raw_tag in line_tags:
        tag = str(raw_tag).strip()
        match = EDGE_WHITESPACE_TAG_RE.match(tag)
        if match is None:
            continue
        piece = chr(int(match.group("code"), 16)) * int(match.group("count"))
        if match.group("kind") == "indent":
            indent_parts.append(piece)
        else:
            trail_parts.append(piece)
    return "".join(indent_parts), "".join(trail_parts)


def capture_dialogue_edge_whitespace(
    text: str,
    primary_tag: str = "",
) -> Tuple[str, List[str]]:
    """Strip dialogue-edge whitespace and encode it as manifest tags.

    Any tagged line (non-empty primary_tag) is processed, not just lines
    tagged "dialogue".  Lines with a speaker prefix are always processed
    regardless of tag.  Only completely untagged, speakerless lines are
    skipped so plain text files without parser tags are left unchanged.
    """
    speaker, dialogue = _split_speaker_dialogue(text)
    clean_tag = str(primary_tag).strip()
    if not clean_tag and not speaker:
        return text, []

    target = dialogue if speaker else text
    leading = _collect_edge_whitespace(target, from_start=True)
    trailing = _collect_edge_whitespace(target, from_start=False)
    stripped = target.strip()
    normalized = f"{speaker}: {stripped}" if speaker else stripped

    tags = _encode_edge_whitespace("indent", leading)
    tags.extend(_encode_edge_whitespace("trail", trailing))
    return normalized, tags


def restore_dialogue_edge_whitespace(
    text: str,
    line_tags: List[str] | Tuple[str, ...] | Set[str],
) -> str:
    """Restore tagged dialogue-edge whitespace to final output text."""
    indent, trail = _decode_edge_whitespace_tags(line_tags)
    if not indent and not trail:
        return text

    speaker, dialogue = _split_speaker_dialogue(text)
    if speaker:
        return f"{speaker}: {indent}{dialogue.strip()}{trail}"
    return f"{indent}{text.strip()}{trail}"


def _placeholder_tag_index(tag: str, prefix: str) -> Optional[int]:
    """Return the numeric suffix for a placeholder tag prefix."""
    clean_tag = str(tag).strip()
    if not clean_tag.startswith(prefix):
        return None
    suffix = clean_tag[len(prefix):]
    if not suffix.isdigit():
        return None
    return int(suffix)


def _ordered_placeholder_tags(
    line_tags: List[str] | Tuple[str, ...] | Set[str],
    prefix: str,
) -> List[str]:
    """Return placeholder tags with *prefix* sorted by their numeric suffix."""
    tagged: List[Tuple[int, str]] = []
    for raw_tag in line_tags:
        tag = str(raw_tag).strip()
        tag_idx = _placeholder_tag_index(tag, prefix)
        if tag_idx is None:
            continue
        tagged.append((tag_idx, tag))
    tagged.sort(key=lambda item: item[0])
    return [tag for _idx, tag in tagged]


def _compile_protect_pattern(pattern_entry: Any) -> Optional[re.Pattern[str]]:
    """Compile one generic placeholder pattern entry."""
    if isinstance(pattern_entry, dict):
        pattern_str = str(pattern_entry.get("pattern", ""))
        is_regex = bool(pattern_entry.get("is_regex", True))
    else:
        pattern_str = str(pattern_entry) if pattern_entry is not None else ""
        is_regex = True

    if not pattern_str.strip():
        return None

    try:
        if is_regex:
            return re.compile(pattern_str)
        return re.compile(re.escape(pattern_str))
    except re.error:
        return None


def _collect_protect_matches(
    text: str,
    patterns: List[Dict[str, Any]],
) -> List[Tuple[int, int, str]]:
    """Collect non-overlapping generic placeholder captures left-to-right."""
    all_matches: List[Tuple[int, int, str]] = []
    for pattern_entry in patterns:
        compiled = _compile_protect_pattern(pattern_entry)
        if compiled is None:
            continue
        for match in compiled.finditer(text):
            value = match.group(0)
            if value:
                all_matches.append((match.start(), match.end(), value))

    if not all_matches:
        return []

    all_matches.sort(key=lambda item: item[0])
    filtered: List[Tuple[int, int, str]] = []
    last_end = 0
    for start, end, value in all_matches:
        if start < last_end:
            continue
        filtered.append((start, end, value))
        last_end = end
    return filtered


def capture_generic_placeholder_values(
    text: str,
    line_tags: List[str] | Tuple[str, ...] | Set[str],
    placeholder_lookup: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Recompute generic placeholder captures for one line from tags + lookup."""
    patterns = [
        placeholder_lookup[tag]
        for tag in _ordered_placeholder_tags(line_tags, GENERIC_PLACEHOLDER_TAG_PREFIX)
        if isinstance(placeholder_lookup.get(tag), dict)
    ]
    return [value for _start, _end, value in _collect_protect_matches(str(text), patterns)]


def capture_custom_placeholder_records(
    text: str,
    line_tags: List[str] | Tuple[str, ...] | Set[str],
    placeholder_lookup: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Recompute custom placeholder records for one line from tags + lookup."""
    remaining_text = str(text)
    records: List[Dict[str, Any]] = []

    for tag in _ordered_placeholder_tags(line_tags, CUSTOM_PLACEHOLDER_TAG_PREFIX):
        lookup_entry = placeholder_lookup.get(tag)
        if not isinstance(lookup_entry, dict):
            continue
        token = str(lookup_entry.get("token", "__CUST__")).strip() or "__CUST__"
        remaining_text, captured = _capture_custom_placeholder_rule(
            remaining_text,
            str(lookup_entry.get("pattern", "")),
            token,
            bool(lookup_entry.get("is_regex", True)),
        )
        if not captured:
            continue

        record: Dict[str, Any] = {
            "tag": tag,
            "token": token,
            "values": captured,
        }
        if lookup_entry.get("recover_everywhere", False):
            record["recover_everywhere"] = True
        records.append(record)

    return records


def _capture_custom_placeholder_rule(
    text: str,
    pattern: str,
    token: str,
    is_regex: bool,
) -> Tuple[str, List[str]]:
    """Apply one placeholder rule and return rewritten text plus captured values."""
    if not pattern:
        return text, []

    result = text
    captured: List[str] = []
    try:
        if is_regex:
            compiled = re.compile(pattern)
            matches = list(compiled.finditer(result))
            for match in reversed(matches):
                value = match.group(0)
                if not value:
                    continue
                captured.insert(0, value)
                result = result[:match.start()] + token + result[match.end():]
        else:
            while pattern in result:
                pos = result.find(pattern)
                if pos < 0:
                    break
                captured.append(pattern)
                result = result[:pos] + token + result[pos + len(pattern):]
    except re.error:
        return text, []

    return result, captured


def capture_custom_placeholder_values(
    text: str,
    rules: List[Dict[str, Any]],
) -> List[str]:
    """Recompute custom placeholder captures from the original line text."""
    result = str(text)
    records = capture_custom_placeholder_records(
        result,
        [f"{CUSTOM_PLACEHOLDER_TAG_PREFIX}{idx}" for idx in range(1, len(rules) + 1)],
        {
            f"{CUSTOM_PLACEHOLDER_TAG_PREFIX}{idx}": {
                "pattern": rule.get("pattern", ""),
                "token": rule.get("token", "__CUST__"),
                "is_regex": rule.get("is_regex", True),
            }
            for idx, rule in enumerate(rules, start=1)
        },
    )
    captured: List[str] = []
    for record in records:
        captured.extend([str(value) for value in record.get("values", [])])
    return captured


def capture_ellipsis_counts(text: str) -> List[int]:
    """Recompute ellipsis compression counts from the original line text."""
    try:
        from CherryAI.modi.standard_mode import compress_ellipsis_line

        _compressed, counts = compress_ellipsis_line(str(text))
        return counts
    except Exception:
        return []


# ============================================================================
# Bracket/Quote Definitions
# ============================================================================


# Bracket pairs (opening -> closing)
BRACKET_PAIRS: Dict[str, str] = {
    "[": "]",
    "{": "}",
    "<": ">",
    "(": ")",
    "「": "」",
    "『": "』",
    "【": "】",
    "〔": "〕",
    "《": "》",
    "〈": "〉",
    "［": "］",
    "｛": "｝",
    "＜": "＞",
    "（": "）",
}

# Quote pairs for balanced detection (symmetric quotes only)
# Note: Japanese brackets like 「」 are in BRACKET_PAIRS, not here
QUOTE_PAIRS: Dict[str, str] = {
    '"': '"',  # ASCII double quote (same open/close)
    "'": "'",  # ASCII single quote (same open/close)
    "\u201c": "\u201d",  # Left/right curly double quotes " "
    "\u2018": "\u2019",  # Left/right curly single quotes ' '
    "＂": "＂",  # Fullwidth double quote (same open/close)
}

# ---------------------------------------------------------------------------
# Equivalence maps derived from ANCHOR_EQUIVS (modehelper)
# ---------------------------------------------------------------------------

# Build bracket equivalence from ANCHOR_EQUIVS: maps fullwidth → canonical
BRACKET_EQUIV: Dict[str, str] = {}
for _canon, _equivs in ANCHOR_EQUIVS.items():
    for _ch in _equivs:
        if _ch in BRACKET_PAIRS or any(
            _ch == v for v in BRACKET_PAIRS.values()
        ):
            if _ch != _canon:
                BRACKET_EQUIV[_ch] = _canon
BRACKET_EQUIV.update({
    "【": "[",
    "】": "]",
})

# Build quote equivalence from ANCHOR_EQUIVS: maps fullwidth → canonical
QUOTE_EQUIV: Dict[str, str] = {}
for _canon, _equivs in ANCHOR_EQUIVS.items():
    for _ch in _equivs:
        if _ch in QUOTE_PAIRS or any(
            _ch == v for v in QUOTE_PAIRS.values()
        ):
            if _ch != _canon:
                QUOTE_EQUIV[_ch] = _canon

# Unified canonical map for ALL bracket/quote characters
_CANON_MAP: Dict[str, str] = {}
for _canon, _equivs in ANCHOR_EQUIVS.items():
    for _ch in _equivs:
        _CANON_MAP[_ch] = _canon
_CANON_MAP.update({
    "【": "[",
    "】": "]",
})

# Reverse bracket map: closing → opening
_CLOSING_TO_OPENING: Dict[str, str] = {v: k for k, v in BRACKET_PAIRS.items()}

# Characters that can serve as positional anchors for recovery
_RECOVERY_ANCHOR_CHARS: Set[str] = set(
    list(".,!?;:。、！？；：")
    + list("()[]<>{}（）「」『』【】〔〕《》〈〉［］｛｝＜＞")
    + ['"', "'", "＂", "\u201c", "\u201d", "\u2018", "\u2019"]
)


def _normalize_bracket(ch: str) -> str:
    """Return the canonical (halfwidth) form of a bracket character.

    Uses ANCHOR_EQUIVS to find the canonical form.  Characters not
    in any equivalence group are returned unchanged.
    """
    return _CANON_MAP.get(ch, ch)


# All opening characters
OPENING_CHARS: Set[str] = set(BRACKET_PAIRS.keys()) | set(QUOTE_PAIRS.keys())

# All closing characters
CLOSING_CHARS: Set[str] = set(BRACKET_PAIRS.values()) | set(QUOTE_PAIRS.values())


# ============================================================================
# Recovery Functions
# ============================================================================


def normalize_placeholder(text: str, preserve_case: bool = False) -> str:
    """Normalize placeholder to standard format: __NAME__ or __NAME_N__.
    
    Args:
        text: The placeholder text to normalize.
        preserve_case: If True, preserve original case; if False, uppercase.
        
    Returns:
        Normalized placeholder string.
    """
    # Remove all spaces
    cleaned = text.replace(" ", "")
    
    # Ensure double underscores at start and end
    if not cleaned.startswith("__"):
        cleaned = "__" + cleaned.lstrip("_")
    if not cleaned.endswith("__"):
        cleaned = cleaned.rstrip("_") + "__"
    
    # Uppercase if not preserving case
    if not preserve_case:
        cleaned = cleaned.upper()
    
    return cleaned


def extract_placeholders_ordered(text: str) -> List[Tuple[str, int, int]]:
    """Extract all placeholders from text with their positions.
    
    Returns:
        List of (placeholder, start, end) tuples sorted by position.
    """
    results: List[Tuple[str, int, int]] = []
    
    # Find standard placeholders (case-insensitive search, but we normalize)
    for match in PLACEHOLDER_PATTERN.finditer(text):
        ph = match.group(0).upper()
        results.append((ph, match.start(), match.end()))
    
    # Sort by position
    results.sort(key=lambda x: x[1])
    return results


def recover_placeholder_case(text: str, original_placeholders: List[str]) -> Tuple[str, List[RecoveryIssue]]:
    """Fix placeholder case issues (e.g., __PROTECTED__ -> __PROTECTED__).
    
    Args:
        text: The translated text to fix.
        original_placeholders: List of original placeholders (uppercase).
        
    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    issues: List[RecoveryIssue] = []
    result = text
    
    # Pattern to find any placeholder-like pattern (case insensitive)
    # Must match __WORD__ or __WORD_N__ format
    pattern = re.compile(r"__([a-zA-Z][a-zA-Z0-9]*)(?:_(\d+))?__")
    
    # Find all matches and collect replacements
    replacements = []
    for match in pattern.finditer(text):
        found = match.group(0)
        normalized = found.upper()
        
        # Check if this matches an original placeholder but with wrong case
        if normalized in original_placeholders and found != normalized:
            replacements.append((match.start(), match.end(), found, normalized))
    
    # Apply replacements in reverse order to maintain positions
    for start, end, found, normalized in reversed(replacements):
        issue = RecoveryIssue(
            type=RecoveryType.PLACEHOLDER_CASE,
            description=f"Placeholder case corrected: {found} -> {normalized}",
            position=start,
            original_text=found,
            recovered_text=normalized,
            action=RecoveryAction.RECOVERED,
        )
        issues.append(issue)
        result = result[:start] + normalized + result[end:]
    
    # Reverse issues to maintain original order
    issues.reverse()
    
    return result, issues


def recover_mangled_placeholders(text: str, original_placeholders: List[str]) -> Tuple[str, List[RecoveryIssue]]:
    """Fix mangled placeholder patterns (e.g., __ PROTECTED __ -> __PROTECTED__).
    
    Only fixes placeholders with internal whitespace that clearly match
    known original placeholders.
    
    Args:
        text: The translated text to fix.
        original_placeholders: List of original placeholders.
        
    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    issues: List[RecoveryIssue] = []
    result = text
    
    # Only fix placeholders with internal whitespace
    replacements = []
    for match in WHITESPACE_PLACEHOLDER_PATTERN.finditer(text):
        found = match.group(0)
        normalized = normalize_placeholder(found)
        
        # Only fix if it matches a known original placeholder
        if normalized in original_placeholders and found != normalized:
            replacements.append((match.start(), match.end(), found, normalized))
    
    # Apply replacements in reverse order
    for start, end, found, normalized in reversed(replacements):
        issue = RecoveryIssue(
            type=RecoveryType.PLACEHOLDER_MANGLED,
            description=f"Mangled placeholder fixed: {found} -> {normalized}",
            position=start,
            original_text=found,
            recovered_text=normalized,
            action=RecoveryAction.RECOVERED,
        )
        issues.append(issue)
        result = result[:start] + normalized + result[end:]
    
    issues.reverse()
    return result, issues


def recover_missing_placeholders(
    text: str,
    original: str,
    original_placeholders: List[str],
) -> Tuple[str, List[RecoveryIssue]]:
    """Attempt to recover missing placeholders by inserting at likely positions.
    
    This is a best-effort recovery - if we can't find a good insertion point,
    we mark it as needing retry.
    
    Args:
        text: The translated text.
        original: The original text (before translation).
        original_placeholders: List of original placeholders.
        
    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    issues: List[RecoveryIssue] = []
    result = text
    
    # Get placeholders currently in the translated text
    current_placeholders = [p for p, _, _ in extract_placeholders_ordered(result)]
    
    # Find missing placeholders
    missing = []
    for ph in original_placeholders:
        count_orig = original_placeholders.count(ph)
        count_trans = current_placeholders.count(ph)
        for _ in range(count_orig - count_trans):
            missing.append(ph)
    
    if not missing:
        return result, issues
    
    # Try to recover each missing placeholder
    for ph in missing:
        # Find position of placeholder in original
        ph_pattern = re.compile(re.escape(ph), re.IGNORECASE)
        orig_match = ph_pattern.search(original)
        
        if orig_match:
            # Calculate relative position in original
            rel_pos = orig_match.start() / len(original) if len(original) > 0 else 0.5
            
            # Find insertion point in translated text
            insert_at = int(rel_pos * len(result))
            
            # Try to insert at word boundary
            while insert_at > 0 and insert_at < len(result) and result[insert_at - 1].isalnum():
                insert_at += 1
            
            # Insert the placeholder
            result = result[:insert_at] + " " + ph + " " + result[insert_at:]
            
            issue = RecoveryIssue(
                type=RecoveryType.PLACEHOLDER_MISSING,
                description=f"Missing placeholder inserted at position {insert_at}: {ph}",
                position=insert_at,
                original_text="",
                recovered_text=ph,
                action=RecoveryAction.RECOVERED,
            )
            issues.append(issue)
        else:
            # Can't determine good position - flag for retry
            issue = RecoveryIssue(
                type=RecoveryType.PLACEHOLDER_MISSING,
                description=f"Missing placeholder could not be recovered: {ph}",
                position=-1,
                original_text="",
                recovered_text=ph,
                action=RecoveryAction.NEEDS_RETRY,
            )
            issues.append(issue)
    
    return result, issues


def check_bracket_balance(text: str) -> List[Tuple[str, int]]:
    """Check for unbalanced brackets in text.
    
    Returns:
        List of (bracket, position) for unmatched brackets.
    """
    return _find_unmatched_brackets(text)


def _get_recoverable_bracket_pair_id(ch: str) -> Optional[str]:
    """Return the canonical opening bracket for a recoverable bracket char.

    Bracket-quote hybrids such as ``「」`` are excluded here because they are
    handled by quote recovery.
    """
    if ch in BRACKET_PAIRS:
        opening = ch
    elif ch in _CLOSING_TO_OPENING:
        opening = _CLOSING_TO_OPENING[ch]
    else:
        return None

    pair_id = _normalize_bracket(opening)
    if pair_id in QUOTE_PAIRS or pair_id in QUOTE_PAIRS.values():
        return None
    return pair_id


def _extract_recoverable_brackets(
    text: str,
) -> List[Tuple[str, str, str, int]]:
    """Extract recoverable brackets as ``(pair_id, role, actual, position)``."""
    extracted: List[Tuple[str, str, str, int]] = []
    all_brackets = set(BRACKET_PAIRS.keys()) | set(BRACKET_PAIRS.values())

    for i, ch in enumerate(text):
        if ch not in all_brackets:
            continue
        pair_id = _get_recoverable_bracket_pair_id(ch)
        if pair_id is None:
            continue
        role = "open" if ch in BRACKET_PAIRS else "close"
        extracted.append((pair_id, role, ch, i))

    return extracted


def _find_unmatched_brackets(text: str) -> List[Tuple[str, int]]:
    """Return unmatched recoverable brackets using stack-based pairing."""
    stack: List[Tuple[str, str, int]] = []
    unmatched: List[Tuple[str, int]] = []

    for pair_id, role, actual, pos in _extract_recoverable_brackets(text):
        if role == "open":
            stack.append((pair_id, actual, pos))
            continue

        if stack and stack[-1][0] == pair_id:
            stack.pop()
        else:
            unmatched.append((actual, pos))

    unmatched.extend((actual, pos) for _, actual, pos in stack)
    return unmatched


def _has_balanced_brackets(text: str) -> bool:
    """Return True when recoverable brackets in *text* are properly balanced."""
    return not _find_unmatched_brackets(text)


def recover_bracket_balance(
    text: str,
    original: str,
) -> Tuple[str, List[RecoveryIssue]]:
    """Fix unbalanced brackets using anchor-relative positioning.

    Recovery is only attempted when *original* has balanced recoverable
    brackets and *text* is currently unbalanced. This prevents rare,
    intentionally unbalanced source lines from triggering bracket repair.

    When recovery does run, missing brackets are re-inserted only when a
    reliable anchor (adjacent punctuation, line start, or line end) can be
    found in the translated text. If no anchor is available the line is
    flagged for review instead of guessing a position.

    Args:
        text: The translated text.
        original: The original text.

    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    issues: List[RecoveryIssue] = []
    result = text

    # Only recover lines whose source bracket structure is sound.
    if not _has_balanced_brackets(original):
        return result, issues

    # Skip balanced translations even if they changed bracket style.
    if _has_balanced_brackets(result):
        return result, issues

    orig_seq = _extract_recoverable_brackets(original)
    trans_seq = _extract_recoverable_brackets(result)

    from collections import Counter
    orig_counts: Dict[Tuple[str, str], int] = Counter(
        (pair_id, role) for pair_id, role, _, _ in orig_seq
    )
    trans_counts: Dict[Tuple[str, str], int] = Counter(
        (pair_id, role) for pair_id, role, _, _ in trans_seq
    )

    extra_positions: List[Tuple[int, str]] = []
    for bracket_ch, pos in _find_unmatched_brackets(result):
        pair_id = _get_recoverable_bracket_pair_id(bracket_ch)
        if pair_id is None:
            continue
        role = "open" if bracket_ch in BRACKET_PAIRS else "close"
        key = (pair_id, role)
        if trans_counts.get(key, 0) <= orig_counts.get(key, 0):
            continue
        trans_counts[key] -= 1
        extra_positions.append((pos, bracket_ch))

    for pos, bracket_ch in sorted(extra_positions, reverse=True):
        result = result[:pos] + result[pos + 1:]
        issues.append(RecoveryIssue(
            type=RecoveryType.BRACKET_BALANCE,
            description=f"Extra unmatched bracket '{bracket_ch}' removed",
            position=pos,
            original_text=bracket_ch,
            recovered_text="",
            action=RecoveryAction.RECOVERED,
        ))

    if extra_positions:
        trans_seq = _extract_recoverable_brackets(result)
        trans_counts = Counter((pair_id, role) for pair_id, role, _, _ in trans_seq)

    # For each recoverable bracket type that is under-represented in text,
    # use the source positions as anchor hints.
    for (pair_id, role), orig_count in sorted(orig_counts.items()):
        trans_count = trans_counts.get((pair_id, role), 0)
        if trans_count >= orig_count:
            continue

        orig_of_type = [
            pos for p, r, _, pos in orig_seq
            if p == pair_id and r == role
        ]
        missing_positions = orig_of_type[trans_count:]
        bracket_ch = pair_id if role == "open" else BRACKET_PAIRS[pair_id]

        for orig_pos in missing_positions:
            inserted = _try_anchor_bracket_insert(
                result, original, orig_pos, bracket_ch,
                is_opening=(role == "open"),
            )
            if inserted is not None:
                result, desc = inserted
                issues.append(RecoveryIssue(
                    type=RecoveryType.BRACKET_BALANCE,
                    description=desc,
                    position=-1,
                    original_text="",
                    recovered_text=bracket_ch,
                    action=RecoveryAction.RECOVERED,
                ))
            else:
                issues.append(RecoveryIssue(
                    type=RecoveryType.BRACKET_BALANCE,
                    description=(
                        f"Missing bracket '{bracket_ch}' could not "
                        f"be placed (no anchor found)"
                    ),
                    position=-1,
                    original_text="",
                    recovered_text=bracket_ch,
                    action=RecoveryAction.NEEDS_RETRY,
                ))

    # Final balance check — report any remaining imbalance
    unmatched = check_bracket_balance(result)
    if unmatched:
        for bracket, pos in unmatched:
            issues.append(RecoveryIssue(
                type=RecoveryType.BRACKET_BALANCE,
                description=(
                    f"Unbalanced bracket at position {pos}: "
                    f"'{bracket}'"
                ),
                position=pos,
                original_text=bracket,
                recovered_text="",
                action=RecoveryAction.NEEDS_RETRY,
            ))

    return result, issues


def _find_anchor_near(
    text: str,
    pos: int,
    direction: str,
    skip_chars: Optional[Set[str]] = None,
) -> Optional[Tuple[str, int]]:
    """Find nearest punctuation anchor from *pos* in *direction*.

    Args:
        text: The text to search.
        pos: Starting position (exclusive — search begins at pos±1).
        direction: ``"left"`` (search backwards) or ``"right"``.
        skip_chars: Characters to skip (e.g. the bracket itself).

    Returns:
        ``(anchor_char, anchor_pos)`` or ``None``.
    """
    skip = skip_chars or set()
    if direction == "left":
        for i in range(pos - 1, -1, -1):
            ch = text[i]
            if ch in skip or ch.isspace():
                continue
            if ch in _RECOVERY_ANCHOR_CHARS:
                return ch, i
            # Non-anchor, non-space character blocks further search
            return None
    else:
        for i in range(pos + 1, len(text)):
            ch = text[i]
            if ch in skip or ch.isspace():
                continue
            if ch in _RECOVERY_ANCHOR_CHARS:
                return ch, i
            return None
    return None


def _try_anchor_bracket_insert(
    result: str,
    original: str,
    orig_pos: int,
    bracket_ch: str,
    is_opening: bool,
) -> Optional[Tuple[str, str]]:
    """Try to insert *bracket_ch* into *result* using anchor-relative logic.

    Returns ``(new_result, description)`` on success, ``None`` if no
    anchor could be found.
    """
    all_brackets = set(BRACKET_PAIRS.keys()) | set(BRACKET_PAIRS.values())
    orig_len = len(original)

    # --- Line-start / line-end anchors ---
    if is_opening:
        # Check if bracket is at or near start of original
        leading = original[:orig_pos].lstrip()
        if not leading:
            return (
                bracket_ch + result,
                f"Missing opening '{bracket_ch}' inserted at line start",
            )
    else:
        trailing = original[orig_pos + 1:].rstrip()
        if not trailing:
            return (
                result + bracket_ch,
                f"Missing closing '{bracket_ch}' inserted at line end",
            )

    # --- Character-anchor search ---
    # For opening bracket: look LEFT for a punctuation anchor
    # For closing bracket: look RIGHT for a punctuation anchor
    primary = "left" if is_opening else "right"
    secondary = "right" if is_opening else "left"

    for direction in (primary, secondary):
        anchor_info = _find_anchor_near(
            original, orig_pos, direction, skip_chars=all_brackets,
        )
        if anchor_info is None:
            continue
        anchor_found, _ = anchor_info

        # Canonicalise the anchor char so get_equivs returns all variants
        canon_anchor = _CANON_MAP.get(anchor_found, anchor_found)

        # Find anchor (or equivalent) in the translated text
        for equiv in get_equivs(canon_anchor):
            # Use rfind for "right" side insertion stability
            if direction == primary and is_opening:
                # Bracket is left of anchor → insert AFTER anchor
                pos = result.find(equiv)
                if pos >= 0:
                    insert_at = pos + len(equiv)
                    new = result[:insert_at] + bracket_ch + result[insert_at:]
                    return (
                        new,
                        f"Missing '{bracket_ch}' inserted after anchor "
                        f"'{equiv}'",
                    )
            elif direction == primary and not is_opening:
                # Bracket is right of anchor → insert BEFORE anchor
                pos = result.rfind(equiv)
                if pos >= 0:
                    new = result[:pos] + bracket_ch + result[pos:]
                    return (
                        new,
                        f"Missing '{bracket_ch}' inserted before anchor "
                        f"'{equiv}'",
                    )
            elif direction == secondary and is_opening:
                # Fallback: bracket before some anchor on the right
                pos = result.find(equiv)
                if pos >= 0:
                    new = result[:pos] + bracket_ch + result[pos:]
                    return (
                        new,
                        f"Missing '{bracket_ch}' inserted before anchor "
                        f"'{equiv}' (secondary)",
                    )
            else:
                # Fallback: closing bracket after some anchor on the left
                pos = result.rfind(equiv)
                if pos >= 0:
                    insert_at = pos + len(equiv)
                    new = result[:insert_at] + bracket_ch + result[insert_at:]
                    return (
                        new,
                        f"Missing '{bracket_ch}' inserted after anchor "
                        f"'{equiv}' (secondary)",
                    )

    return None


def check_quote_balance(text: str) -> List[Tuple[str, int]]:
    """Check for unbalanced quotes in text.
    
    Returns:
        List of (quote, position) for unmatched quotes.
    """
    # Track quote state (for each quote type)
    quote_state: Dict[str, Optional[int]] = {}  # quote_char -> opening_position or None
    unmatched: List[Tuple[str, int]] = []
    
    # Build reverse mapping for closing quotes
    closing_to_opening: Dict[str, str] = {}
    for open_ch, close_ch in QUOTE_PAIRS.items():
        if open_ch != close_ch:
            closing_to_opening[close_ch] = open_ch
    
    for i, ch in enumerate(text):
        if ch in QUOTE_PAIRS:
            closing = QUOTE_PAIRS[ch]
            
            if ch == closing:
                # Same character for open/close (e.g., " or ')
                if ch in quote_state and quote_state[ch] is not None:
                    # This is a closing quote
                    quote_state[ch] = None
                else:
                    # This is an opening quote
                    quote_state[ch] = i
            else:
                # Different open/close characters - this is an opening quote
                if ch in quote_state and quote_state[ch] is not None:
                    # Previous opening was never closed
                    opening_pos = quote_state[ch]
                    if opening_pos is not None:
                        unmatched.append((ch, opening_pos))
                quote_state[ch] = i
        elif ch in closing_to_opening:
            # This is a closing quote with a different opening character
            expected_open = closing_to_opening[ch]
            if expected_open in quote_state and quote_state[expected_open] is not None:
                quote_state[expected_open] = None
            else:
                # Closing quote without matching opening
                unmatched.append((ch, i))
    
    # Check for unclosed quotes
    for ch, pos in quote_state.items():
        if pos is not None:
            unmatched.append((ch, pos))
    
    return unmatched


def recover_quote_balance(
    text: str,
    original: str,
) -> Tuple[str, List[RecoveryIssue]]:
    """Fix unbalanced quotes using anchor-relative positioning.

    Uses ANCHOR_EQUIVS to treat fullwidth/halfwidth and JP/EN quote
    variants as equivalent.  Missing closing quotes are inserted at
    line end; missing opening quotes at line start (dialogue start).
    Interior missing quotes use anchor-relative logic or are flagged
    for review.

    Args:
        text: The translated text.
        original: The original text.

    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    issues: List[RecoveryIssue] = []
    result = text

    all_quote_chars = set(QUOTE_PAIRS.keys()) | set(QUOTE_PAIRS.values())
    # Also include bracket-pair quotes (「」 etc.) that are quote-equivalent
    bracket_quote_chars: Set[str] = set()
    for canon, equivs in ANCHOR_EQUIVS.items():
        if canon in QUOTE_PAIRS or canon in QUOTE_PAIRS.values():
            bracket_quote_chars.update(equivs)
    combined = all_quote_chars | bracket_quote_chars

    # Extract quotes with canonical forms and open/close roles
    def _extract_quotes(s: str) -> List[Tuple[str, str, str, int]]:
        """Return (canonical, role, actual_char, position)."""
        out: List[Tuple[str, str, str, int]] = []
        same_char_state: Dict[str, bool] = {}
        for i, ch in enumerate(s):
            if ch not in combined:
                continue
            canon = _CANON_MAP.get(ch, ch)
            # Check if this char is a clear opening bracket-quote
            if ch in BRACKET_PAIRS and ch in bracket_quote_chars:
                out.append((canon, "open", ch, i))
            elif ch in _CLOSING_TO_OPENING and ch in bracket_quote_chars:
                out.append((canon, "close", ch, i))
            elif ch in QUOTE_PAIRS:
                closing = QUOTE_PAIRS[ch]
                if ch == closing:
                    # Same char open/close — track alternating state
                    is_open = not same_char_state.get(canon, False)
                    same_char_state[canon] = is_open
                    role = "open" if is_open else "close"
                    out.append((canon, role, ch, i))
                else:
                    out.append((canon, "open", ch, i))
            elif any(ch == v for v in QUOTE_PAIRS.values()):
                out.append((canon, "close", ch, i))
        return out

    orig_quotes = _extract_quotes(original)
    trans_quotes = _extract_quotes(result)

    # Count by (canonical, role)
    from collections import Counter
    orig_counts: Dict[Tuple[str, str], int] = Counter(
        (canon, role) for canon, role, _, _ in orig_quotes
    )
    trans_counts: Dict[Tuple[str, str], int] = Counter(
        (canon, role) for canon, role, _, _ in trans_quotes
    )

    # Already balanced according to equivalences → nothing to do
    if not any(
        trans_counts.get(k, 0) < v for k, v in orig_counts.items()
    ):
        return result, issues

    for (canon_ch, role), orig_count in sorted(orig_counts.items()):
        trans_count = trans_counts.get((canon_ch, role), 0)
        if trans_count >= orig_count:
            continue

        orig_of_type = [
            (ch, pos) for c, r, ch, pos in orig_quotes
            if c == canon_ch and r == role
        ]
        missing = orig_of_type[trans_count:]

        for _, orig_pos in missing:
            # Closing quote → easy: append at line end
            if role == "close":
                # Use canonical form (halfwidth)
                close_ch = canon_ch
                # If the canonical quote char has a distinct opening form,
                # use the correct closing char
                if canon_ch in QUOTE_PAIRS and QUOTE_PAIRS[canon_ch] != canon_ch:
                    close_ch = QUOTE_PAIRS[canon_ch]
                result = result.rstrip() + close_ch
                issues.append(RecoveryIssue(
                    type=RecoveryType.QUOTE_BALANCE,
                    description=(
                        f"Missing closing quote '{close_ch}' "
                        f"inserted at line end"
                    ),
                    position=len(result) - 1,
                    original_text="",
                    recovered_text=close_ch,
                    action=RecoveryAction.RECOVERED,
                ))
                continue

            # Opening quote → try line start first
            leading = original[:orig_pos].lstrip()
            if not leading:
                result = canon_ch + result
                issues.append(RecoveryIssue(
                    type=RecoveryType.QUOTE_BALANCE,
                    description=(
                        f"Missing opening quote '{canon_ch}' "
                        f"inserted at line start"
                    ),
                    position=0,
                    original_text="",
                    recovered_text=canon_ch,
                    action=RecoveryAction.RECOVERED,
                ))
                continue

            # Interior opening quote → try anchor-relative
            all_brackets = set(BRACKET_PAIRS.keys()) | set(
                BRACKET_PAIRS.values()
            )
            anchor_info = _find_anchor_near(
                original, orig_pos, "left",
                skip_chars=all_brackets | combined,
            )
            placed = False
            if anchor_info:
                anchor_ch, _ = anchor_info
                for equiv in get_equivs(anchor_ch):
                    pos = result.find(equiv)
                    if pos >= 0:
                        insert_at = pos + len(equiv)
                        result = (
                            result[:insert_at]
                            + canon_ch
                            + result[insert_at:]
                        )
                        issues.append(RecoveryIssue(
                            type=RecoveryType.QUOTE_BALANCE,
                            description=(
                                f"Missing opening quote '{canon_ch}' "
                                f"inserted after anchor '{equiv}'"
                            ),
                            position=insert_at,
                            original_text="",
                            recovered_text=canon_ch,
                            action=RecoveryAction.RECOVERED,
                        ))
                        placed = True
                        break

            if not placed:
                issues.append(RecoveryIssue(
                    type=RecoveryType.QUOTE_BALANCE,
                    description=(
                        f"Missing opening quote '{canon_ch}' could "
                        f"not be auto-placed (no anchor)"
                    ),
                    position=-1,
                    original_text="",
                    recovered_text=canon_ch,
                    action=RecoveryAction.NEEDS_RETRY,
                ))

    return result, issues


def detect_position_shift(
    text: str,
    original: str,
    original_placeholders: List[str],
) -> List[RecoveryIssue]:
    """Detect placeholders that are present but at a different relative position.

    TASK 42.10: Flags placeholders whose relative position shifted
    significantly (>30% of line length) compared to the original.

    Args:
        text: The translated text.
        original: The original text (before translation).
        original_placeholders: List of original placeholders.

    Returns:
        List of RecoveryIssue for each shifted placeholder.
    """
    issues: List[RecoveryIssue] = []
    if not original_placeholders or not text or not original:
        return issues

    orig_positions = extract_placeholders_ordered(original)
    trans_positions = extract_placeholders_ordered(text)

    orig_len = max(len(original), 1)
    trans_len = max(len(text), 1)

    # Match by placeholder name (first occurrence of each)
    matched_orig: Dict[str, float] = {}
    for ph, start, _ in orig_positions:
        if ph not in matched_orig:
            matched_orig[ph] = start / orig_len

    for ph, start, _ in trans_positions:
        if ph in matched_orig:
            orig_rel = matched_orig[ph]
            trans_rel = start / trans_len
            shift = abs(orig_rel - trans_rel)
            if shift > 0.30:
                issues.append(RecoveryIssue(
                    type=RecoveryType.PLACEHOLDER_POSITION_SHIFT,
                    description=(
                        f"Placeholder {ph} shifted from ~{orig_rel:.0%} "
                        f"to ~{trans_rel:.0%} ({shift:.0%} shift)"
                    ),
                    position=start,
                    original_text=ph,
                    recovered_text=ph,
                    action=RecoveryAction.SKIPPED,
                ))
    return issues


def detect_extra_tokens(
    text: str,
    original_placeholders: List[str],
) -> List[RecoveryIssue]:
    """Detect extra placeholders not present in the original.

    TASK 42.10: Flags placeholders in the translation that appear
    more times than in the original, indicating potential duplication.

    Args:
        text: The translated text.
        original_placeholders: List of original placeholders.

    Returns:
        List of RecoveryIssue for each extra token.
    """
    issues: List[RecoveryIssue] = []
    if not text:
        return issues

    trans_phs = [p for p, _, _ in extract_placeholders_ordered(text)]

    from collections import Counter
    orig_counts = Counter(original_placeholders)
    trans_counts = Counter(trans_phs)

    for ph, count in trans_counts.items():
        expected = orig_counts.get(ph, 0)
        if count > expected:
            extra = count - expected
            issues.append(RecoveryIssue(
                type=RecoveryType.PLACEHOLDER_EXTRA,
                description=(
                    f"Extra token: {ph} appears {count} times "
                    f"(expected {expected}, {extra} extra)"
                ),
                position=-1,
                original_text=ph,
                recovered_text="",
                action=RecoveryAction.NEEDS_RETRY,
            ))
    return issues


# ============================================================================
# Code Pattern Recovery
# ============================================================================


def recover_code_patterns(
    text: str,
    original: str,
    code_patterns: List[Dict[str, Any]],
) -> Tuple[str, List[RecoveryIssue]]:
    """Recover preserve-action code patterns translated by the LLM.

    For each code pattern with ``action='preserve'``, use its regex to
    find all occurrences in *original*.  For each original occurrence,
    search for it in *text*.  If missing, scan *text* with a broad regex
    that matches any content wrapped in the same delimiters (e.g.
    ``{...}``, ``[...]``, ``<...>``) and identify candidates that do
    NOT appear in *original* — these are likely translated versions.
    Replace the first unmatched candidate with the original pattern.

    Args:
        text: The translated text.
        original: The original (preprocessed) text.
        code_patterns: Code pattern dicts from the manifest.

    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    from CherryAI.functions.glossaries.code_glossary_functions import (
        _extract_all_balanced_code,
        generate_regex_pattern,
    )

    def _filter_nested(matches: List[re.Match[str]], haystack: str) -> List[re.Match[str]]:
        segments = _extract_all_balanced_code(haystack)
        filtered: List[re.Match[str]] = []
        for match in matches:
            start, end = match.span()
            nested = any(
                seg_start <= start and end <= seg_end
                and (seg_start, seg_end) != (start, end)
                for seg_start, seg_end, _seg_text in segments
            )
            if not nested:
                filtered.append(match)
        return filtered

    issues: List[RecoveryIssue] = []
    result = text

    for cp in code_patterns:
        if not isinstance(cp, dict):
            continue
        action = cp.get("action", "preserve")
        if action != "preserve":
            continue
        pat = cp.get("pattern", "")
        raw_type = cp.get("raw_type", "UNKNOWN")
        if not pat:
            continue

        regex_str = generate_regex_pattern(pat, raw_type)
        try:
            regex = re.compile(regex_str)
        except re.error:
            continue

        orig_matches = _filter_nested(list(regex.finditer(original)), original)
        if not orig_matches:
            continue

        # Check each original match instance in the translated text
        for orig_match in orig_matches:
            orig_instance = orig_match.group(0)
            if orig_instance in result:
                continue  # This instance is preserved — good

            # Pattern is missing in translation.  Try to find a
            # translated substitute: look for content wrapped in the
            # same delimiters that does NOT exist in original.
            candidate_found = False
            delimiters = _detect_delimiters(pat)
            if delimiters:
                open_d, close_d = delimiters
                # Build regex to find anything in those delimiters
                open_esc = re.escape(open_d)
                close_esc = re.escape(close_d)
                if len(open_d) == 1 and len(close_d) == 1:
                    broad_pat = re.compile(
                        open_esc + r"[^" + close_esc + r"]+" + close_esc
                    )
                else:
                    broad_pat = re.compile(open_esc + r"[\s\S]+?" + close_esc)
                for m in broad_pat.finditer(result):
                    candidate = m.group(0)
                    # Skip if candidate exists in original (it belongs)
                    if candidate in original:
                        continue
                    # Skip if candidate matches a known code pattern
                    # occurrence (don't clobber a different valid pattern)
                    if regex.fullmatch(candidate):
                        continue
                    # This candidate is likely the translated version
                    result = (
                        result[:m.start()]
                        + orig_instance
                        + result[m.end():]
                    )
                    issues.append(RecoveryIssue(
                        type=RecoveryType.CODE_PATTERN,
                        description=(
                            f"Code pattern '{orig_instance}' recovered "
                            f"from translated '{candidate}'"
                        ),
                        position=m.start(),
                        original_text=candidate,
                        recovered_text=orig_instance,
                        action=RecoveryAction.RECOVERED,
                    ))
                    candidate_found = True
                    break

            if not candidate_found:
                issues.append(RecoveryIssue(
                    type=RecoveryType.CODE_PATTERN,
                    description=(
                        f"Code pattern '{orig_instance}' missing "
                        f"and could not be recovered"
                    ),
                    position=-1,
                    original_text=orig_instance,
                    recovered_text="",
                    action=RecoveryAction.NEEDS_RETRY,
                ))

    return result, issues


def _detect_delimiters(pattern: str) -> Optional[Tuple[str, str]]:
    """Detect the outermost delimiter pair of a code pattern.

    Returns:
        Tuple of (opening, closing) delimiter or ``None``.
    """
    _DELIMITER_PAIRS = {
        "{": "}", "[": "]", "<": ">", "(": ")",
        "{": "}", "\uff5b": "\uff5d",
        "\uff3b": "\uff3d", "\uff08": "\uff09",
        "\uff1c": "\uff1e", "\u300a": "\u300b",
        "\u3008": "\u3009", "\u3010": "\u3011",
    }
    if not pattern:
        return None
    first = pattern[0]
    if first in _DELIMITER_PAIRS:
        closer = _DELIMITER_PAIRS[first]
        doubled_open = first * 2
        doubled_close = closer * 2
        if pattern.startswith(doubled_open) and pattern.endswith(doubled_close):
            return doubled_open, doubled_close
        return first, closer
    last = pattern[-1]
    # Try reverse lookup for closing-first patterns
    for opener, closer in _DELIMITER_PAIRS.items():
        if last == closer and opener in pattern:
            return opener, closer
    return None


# ============================================================================
# Main Recovery Functions
# ============================================================================


def recover_line(
    original: str,
    translated: str,
    enable_placeholder_recovery: bool = True,
    enable_bracket_recovery: bool = True,
    enable_quote_recovery: bool = True,
    enable_whitespace_normalization: bool = True,
    code_patterns: Optional[List[Dict[str, Any]]] = None,
) -> RecoveryResult:
    """Apply all recovery operations to a single translated line.
    
    Args:
        original: The original line (pre-translation).
        translated: The translated line.
        enable_placeholder_recovery: Enable placeholder-related recovery.
        enable_bracket_recovery: Enable bracket balancing.
        enable_quote_recovery: Enable quote balancing.
        enable_whitespace_normalization: Deprecated compatibility flag.
        code_patterns: Code pattern dicts for preserve-action recovery.
        
    Returns:
        RecoveryResult with recovered text and issue details.
    """
    result = RecoveryResult(original=translated, recovered=translated)
    all_issues: List[RecoveryIssue] = []
    current_text = translated
    
    # Extract original placeholders for reference
    original_placeholders = [p for p, _, _ in extract_placeholders_ordered(original)]
    
    if enable_placeholder_recovery and original_placeholders:
        # 1. Fix placeholder case
        current_text, issues = recover_placeholder_case(current_text, original_placeholders)
        all_issues.extend(issues)
        
        # 2. Fix mangled placeholders
        current_text, issues = recover_mangled_placeholders(current_text, original_placeholders)
        all_issues.extend(issues)
        
        # 3. Attempt to recover missing placeholders
        current_text, issues = recover_missing_placeholders(
            current_text, original, original_placeholders
        )
        all_issues.extend(issues)

        # TASK 42.10: Detect position-shifted placeholders
        shift_issues = detect_position_shift(
            current_text, original, original_placeholders,
        )
        all_issues.extend(shift_issues)

        # TASK 42.10: Detect extra tokens
        extra_issues = detect_extra_tokens(current_text, original_placeholders)
        all_issues.extend(extra_issues)

    # 3b. Recover preserve-action code patterns translated by the LLM
    if code_patterns:
        current_text, issues = recover_code_patterns(
            current_text, original, code_patterns,
        )
        all_issues.extend(issues)
    
    if enable_bracket_recovery:
        # 4. Fix bracket balance
        current_text, issues = recover_bracket_balance(current_text, original)
        all_issues.extend(issues)
    
    if enable_quote_recovery:
        # 5. Fix quote balance
        current_text, issues = recover_quote_balance(current_text, original)
        all_issues.extend(issues)
    
    # Determine if fully recovered
    result.recovered = current_text
    result.issues = all_issues
    result.needs_retry = any(i.action == RecoveryAction.NEEDS_RETRY for i in all_issues)
    result.fully_recovered = not result.needs_retry
    
    return result


def recover_batch(
    originals: List[str],
    translations: List[str],
    enable_placeholder_recovery: bool = True,
    enable_bracket_recovery: bool = True,
    enable_quote_recovery: bool = True,
    enable_whitespace_normalization: bool = True,
    code_patterns: Optional[List[Dict[str, Any]]] = None,
) -> BatchRecoveryResult:
    """Apply recovery operations to a batch of translated lines.
    
    Args:
        originals: List of original lines.
        translations: List of translated lines.
        enable_placeholder_recovery: Enable placeholder-related recovery.
        enable_bracket_recovery: Enable bracket balancing.
        enable_quote_recovery: Enable quote balancing.
        enable_whitespace_normalization: Deprecated compatibility flag.
        code_patterns: Code pattern dicts for preserve-action recovery.
        
    Returns:
        BatchRecoveryResult with all results.
    """
    batch_result = BatchRecoveryResult()
    
    # Ensure same length
    min_len = min(len(originals), len(translations))
    
    for i in range(min_len):
        result = recover_line(
            original=originals[i],
            translated=translations[i],
            enable_placeholder_recovery=enable_placeholder_recovery,
            enable_bracket_recovery=enable_bracket_recovery,
            enable_quote_recovery=enable_quote_recovery,
            enable_whitespace_normalization=enable_whitespace_normalization,
            code_patterns=code_patterns,
        )
        batch_result.add_result(result)
    
    return batch_result


# ============================================================================
# PostProcess Manager
# ============================================================================


class PostProcessManager:
    """Manager for post-process recovery operations.
    
    Tracks statistics and provides centralized recovery control.
    """
    
    def __init__(
        self,
        enable_placeholder_recovery: bool = True,
        enable_bracket_recovery: bool = True,
        enable_quote_recovery: bool = True,
        enable_whitespace_normalization: bool = True,
        auto_retry_on_failure: bool = False,
        code_patterns: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize the post-process manager.
        
        Args:
            enable_placeholder_recovery: Enable placeholder-related recovery.
            enable_bracket_recovery: Enable bracket balancing.
            enable_quote_recovery: Enable quote balancing.
            enable_whitespace_normalization: Deprecated compatibility flag.
            auto_retry_on_failure: Automatically flag unrecoverable issues for retry.
            code_patterns: Code pattern dicts for preserve-action recovery.
        """
        self.enable_placeholder_recovery = enable_placeholder_recovery
        self.enable_bracket_recovery = enable_bracket_recovery
        self.enable_quote_recovery = enable_quote_recovery
        self.enable_whitespace_normalization = enable_whitespace_normalization
        self.auto_retry_on_failure = auto_retry_on_failure
        self.code_patterns = code_patterns
        self.stats = RecoveryStats()
    
    def process_line(self, original: str, translated: str) -> RecoveryResult:
        """Process a single line for recovery.
        
        Args:
            original: Original line.
            translated: Translated line.
            
        Returns:
            RecoveryResult with recovered text and issues.
        """
        result = recover_line(
            original=original,
            translated=translated,
            enable_placeholder_recovery=self.enable_placeholder_recovery,
            enable_bracket_recovery=self.enable_bracket_recovery,
            enable_quote_recovery=self.enable_quote_recovery,
            enable_whitespace_normalization=self.enable_whitespace_normalization,
            code_patterns=self.code_patterns,
        )
        
        # Update statistics
        self.stats.total_lines_processed += 1
        if result.had_issues:
            self.stats.lines_with_issues += 1
        for issue in result.issues:
            self.stats.record_issue(issue)
        if result.needs_retry:
            self.stats.retry_recommendations += 1
        
        return result
    
    def process_batch(
        self,
        originals: List[str],
        translations: List[str],
    ) -> BatchRecoveryResult:
        """Process a batch of lines for recovery.
        
        Args:
            originals: List of original lines.
            translations: List of translated lines.
            
        Returns:
            BatchRecoveryResult with all results.
        """
        batch_result = BatchRecoveryResult()
        
        min_len = min(len(originals), len(translations))
        for i in range(min_len):
            result = self.process_line(originals[i], translations[i])
            batch_result.add_result(result)
        
        return batch_result
    
    def get_stats(self) -> RecoveryStats:
        """Get current recovery statistics.
        
        Returns:
            RecoveryStats instance with current statistics.
        """
        return self.stats
    
    def reset_stats(self) -> None:
        """Reset recovery statistics."""
        self.stats = RecoveryStats()
    
    def get_recovery_summary(self) -> Dict[str, Any]:
        """Get a summary of recovery operations.

        TASK 42.10: Includes all recovery type data for manifest persistence.

        Returns:
            Dictionary with summary information.
        """
        return {
            "total_processed": self.stats.total_lines_processed,
            "lines_with_issues": self.stats.lines_with_issues,
            "recovery_rate": self.stats.get_recovery_rate(),
            "retry_recommendations": self.stats.retry_recommendations,
            "issues_by_type": {
                t.value: c for t, c in self.stats.issues_by_type.items()
            },
            "recovered_by_type": {
                t.value: c for t, c in self.stats.recovered_by_type.items()
            },
        }

    def save_to_manifest(self, manifest: Any) -> None:
        """Save recovery analysis results to manifest for persistence.

        TASK 42.10: Stores the summary under manifest.mappings['recovery_analysis'].

        Args:
            manifest: Manifest object with a .mappings dict.
        """
        try:
            if hasattr(manifest, "mappings") and isinstance(manifest.mappings, dict):
                manifest.mappings["recovery_analysis"] = self.get_recovery_summary()
        except Exception:
            logging.debug("Failed to save recovery analysis to manifest")


# ============================================================================
# Factory Functions
# ============================================================================


def create_postprocess_manager(
    enable_placeholder_recovery: bool = True,
    enable_bracket_recovery: bool = True,
    enable_quote_recovery: bool = True,
    enable_whitespace_normalization: bool = True,
    auto_retry_on_failure: bool = False,
    code_patterns: Optional[List[Dict[str, Any]]] = None,
) -> PostProcessManager:
    """Create a PostProcessManager with specified settings.
    
    Args:
        enable_placeholder_recovery: Enable placeholder-related recovery.
        enable_bracket_recovery: Enable bracket balancing.
        enable_quote_recovery: Enable quote balancing.
        enable_whitespace_normalization: Deprecated compatibility flag.
        auto_retry_on_failure: Automatically flag unrecoverable issues for retry.
        code_patterns: Code pattern dicts for preserve-action recovery.
        
    Returns:
        Configured PostProcessManager instance.
    """
    return PostProcessManager(
        enable_placeholder_recovery=enable_placeholder_recovery,
        enable_bracket_recovery=enable_bracket_recovery,
        enable_quote_recovery=enable_quote_recovery,
        enable_whitespace_normalization=enable_whitespace_normalization,
        auto_retry_on_failure=auto_retry_on_failure,
        code_patterns=code_patterns,
    )


def postprocess_manifest(manifest: Any) -> None:
    """Apply postprocessing to manifest lines using default settings.

    The function is deliberately defensive: it skips work when lines are
    missing and tolerates partial manifest implementations used in tests.
    """
    lines = getattr(manifest, "lines", None)
    if not lines:
        return

    originals: List[str] = []
    translations: List[str] = []
    for line in lines:
        originals.append(
            getattr(line, "source", None)
            or getattr(line, "text", "")
            or ""
        )
        translations.append(
            getattr(line, "target", None)
            or getattr(line, "translation", "")
            or ""
        )

    manager = create_postprocess_manager()
    batch_result = manager.process_batch(originals, translations)

    postprocessed_lines = []
    for line, result in zip(lines, batch_result.results):
        recovered = result.recovered
        postprocessed_lines.append(recovered)

        if hasattr(line, "target"):
            line.target = recovered
        elif hasattr(line, "translation"):
            line.translation = recovered
        else:
            setattr(line, "translation", recovered)

        setattr(line, "postprocess_issues", result.issues)

    try:
        manifest.postprocessed_lines = postprocessed_lines
    except Exception:
        setattr(manifest, "postprocessed_lines", postprocessed_lines)

    try:
        manager.save_to_manifest(manifest)
    except Exception:
        pass

    summary = manager.get_recovery_summary()
    try:
        manifest.postprocess_summary = summary
    except Exception:
        setattr(manifest, "postprocess_summary", summary)


def get_recovery_type_description(recovery_type: RecoveryType) -> str:
    """Get a human-readable description of a recovery type.
    
    Args:
        recovery_type: The RecoveryType to describe.
        
    Returns:
        Human-readable description string.
    """
    descriptions = {
        RecoveryType.PLACEHOLDER_CASE: "Fix placeholder case (e.g., __PROTECTED__ → __PROTECTED__)",
        RecoveryType.PLACEHOLDER_MANGLED: "Fix mangled placeholders (e.g., __PR OT__ → __PROTECTED__)",
        RecoveryType.PLACEHOLDER_MISSING: "Recover missing placeholders",
        RecoveryType.PLACEHOLDER_POSITION_SHIFT: "Placeholder position shifted significantly",
        RecoveryType.PLACEHOLDER_EXTRA: "Extra placeholder tokens detected",
        RecoveryType.QUOTE_BALANCE: "Balance unmatched quotes",
        RecoveryType.BRACKET_BALANCE: "Balance unmatched brackets",
        RecoveryType.WHITESPACE_NORMALIZATION: "Fix errant whitespace in placeholders",
        RecoveryType.CODE_CHARACTER: "Recover missing code characters",
        RecoveryType.BR_TAG: "Recover missing <br> tags",
        RecoveryType.SPEAKER_FORMAT: "Fix Speaker: \"Dialogue\" format",
    }
    return descriptions.get(recovery_type, str(recovery_type))


def list_recovery_types() -> List[Dict[str, str]]:
    """List all recovery types with descriptions.
    
    Returns:
        List of dictionaries with 'type' and 'description' keys.
    """
    return [
        {"type": rt.value, "description": get_recovery_type_description(rt)}
        for rt in RecoveryType
    ]


def replace_forbidden_chars(
    text: str,
    characters: List[str],
    action: str = "replace",
    replacement: str = "",
) -> Tuple[str, List[str]]:
    """Replace or flag forbidden characters in translated output (TASK 53.5).

    Args:
        text: Translated text to clean.
        characters: List of forbidden character strings.
        action: ``"replace"`` to auto-remove or ``"flag"`` to report only.
        replacement: Replacement string when *action* is ``"replace"``.

    Returns:
        Tuple of (cleaned_text, list_of_issues).  When *action* is
        ``"flag"`` the text is returned unchanged and issues list the
        offending characters found.
    """
    issues: List[str] = []

    if not characters or not text:
        return text, issues

    if action == "flag":
        for ch in characters:
            if ch in text:
                issues.append(
                    f"Forbidden character {repr(ch)} found in output"
                )
        return text, issues

    # action == "replace" (default)
    cleaned = text
    for ch in characters:
        if ch in cleaned:
            issues.append(
                f"Replaced forbidden character {repr(ch)}"
            )
            cleaned = cleaned.replace(ch, replacement)
    return cleaned, issues
