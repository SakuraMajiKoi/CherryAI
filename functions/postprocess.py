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


# ============================================================================
# Enums and Data Classes
# ============================================================================


class RecoveryType(Enum):
    """Types of recovery operations that can be performed."""
    
    PLACEHOLDER_CASE = "placeholder_case"  # __prot__ -> __PROT__
    PLACEHOLDER_MANGLED = "placeholder_mangled"  # __PR OT__ -> __PROT__
    PLACEHOLDER_MISSING = "placeholder_missing"  # Placeholder removed by LLM
    PLACEHOLDER_POSITION_SHIFT = "placeholder_position_shift"  # TASK 42.10
    PLACEHOLDER_EXTRA = "placeholder_extra"  # TASK 42.10
    QUOTE_BALANCE = "quote_balance"  # Unbalanced quotes
    BRACKET_BALANCE = "bracket_balance"  # Missing bracket pairs
    WHITESPACE_NORMALIZATION = "whitespace_normalization"  # Errant spacing
    CODE_CHARACTER = "code_character"  # Missing code characters
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


# Standard placeholder pattern: __PROT__, __PROT_1__, __NAME__, etc.
PLACEHOLDER_PATTERN = re.compile(r"__([A-Za-z][A-Za-z0-9]*)(?:_(\d+))?__")

# Pattern for placeholders with internal whitespace (clearly mangled)
WHITESPACE_PLACEHOLDER_PATTERN = re.compile(r"__\s+([A-Za-z][A-Za-z0-9]*)\s*(?:_\s*(\d+))?\s+__")

# Translated placeholder patterns (only match specific known translations)
TRANSLATED_PLACEHOLDER_PATTERNS = [
    # Protection -> PROT
    (re.compile(r"__\s*PROTECTION\s*(?:_\s*(\d+))?\s*__", re.IGNORECASE), "__PROT__"),
    (re.compile(r"__\s*PROTECTED\s*(?:_\s*(\d+))?\s*__", re.IGNORECASE), "__PROT__"),
]

# Known placeholder types (for recovery hinting)
KNOWN_PLACEHOLDERS = {"PROT", "NAME", "CODE", "VAR", "ITEM", "SKILL", "NUM"}


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
    """Fix placeholder case issues (e.g., __prot__ -> __PROT__).
    
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
    """Fix mangled placeholder patterns (e.g., __ PROT __ -> __PROT__).
    
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


def normalize_placeholder_whitespace(text: str) -> Tuple[str, List[RecoveryIssue]]:
    """Fix errant spacing around placeholders.
    
    Args:
        text: The text to fix.
        
    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    issues: List[RecoveryIssue] = []
    result = text
    
    # Pattern for placeholders with extra internal whitespace
    pattern = re.compile(r"__\s+([A-Za-z][A-Za-z0-9_]*)\s*(?:_\s*(\d+))?\s+__")
    
    offset = 0
    for match in pattern.finditer(text):
        found = match.group(0)
        normalized = normalize_placeholder(found)
        
        if found != normalized:
            issue = RecoveryIssue(
                type=RecoveryType.WHITESPACE_NORMALIZATION,
                description=f"Whitespace normalized in placeholder: {found} -> {normalized}",
                position=match.start() + offset,
                original_text=found,
                recovered_text=normalized,
                action=RecoveryAction.RECOVERED,
            )
            issues.append(issue)
            
            start = match.start() + offset
            end = match.end() + offset
            result = result[:start] + normalized + result[end:]
            offset += len(normalized) - len(found)
    
    return result, issues


def check_bracket_balance(text: str) -> List[Tuple[str, int]]:
    """Check for unbalanced brackets in text.
    
    Returns:
        List of (bracket, position) for unmatched brackets.
    """
    stack: List[Tuple[str, int]] = []
    unmatched: List[Tuple[str, int]] = []
    
    for i, ch in enumerate(text):
        if ch in BRACKET_PAIRS:
            # Opening bracket
            stack.append((ch, i))
        elif ch in BRACKET_PAIRS.values():
            # Closing bracket - find matching opening
            expected_open = None
            for open_ch, close_ch in BRACKET_PAIRS.items():
                if close_ch == ch:
                    expected_open = open_ch
                    break
            
            if stack and stack[-1][0] == expected_open:
                stack.pop()
            else:
                unmatched.append((ch, i))
    
    # Any remaining in stack are unmatched opening brackets
    unmatched.extend(stack)
    return unmatched


def recover_bracket_balance(
    text: str,
    original: str,
) -> Tuple[str, List[RecoveryIssue]]:
    """Attempt to fix unbalanced brackets by comparing with original.
    
    Args:
        text: The translated text.
        original: The original text.
        
    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    issues: List[RecoveryIssue] = []
    result = text
    
    # Get bracket sequences from both
    orig_brackets = [(ch, i) for i, ch in enumerate(original) if ch in OPENING_CHARS or ch in CLOSING_CHARS]
    trans_brackets = [(ch, i) for i, ch in enumerate(text) if ch in OPENING_CHARS or ch in CLOSING_CHARS]
    
    # Check for missing brackets
    orig_bracket_chars = [b[0] for b in orig_brackets]
    trans_bracket_chars = [b[0] for b in trans_brackets]
    
    # Count brackets by type
    for bracket in set(orig_bracket_chars):
        orig_count = orig_bracket_chars.count(bracket)
        trans_count = trans_bracket_chars.count(bracket)
        
        if trans_count < orig_count:
            # Missing brackets - try to insert
            for _ in range(orig_count - trans_count):
                # Find where in original this bracket appears
                for i, (ch, pos) in enumerate(orig_brackets):
                    if ch == bracket:
                        # Calculate relative position
                        rel_pos = pos / len(original) if len(original) > 0 else 0.5
                        insert_at = int(rel_pos * len(result))
                        
                        # Insert bracket
                        result = result[:insert_at] + bracket + result[insert_at:]
                        
                        issue = RecoveryIssue(
                            type=RecoveryType.BRACKET_BALANCE,
                            description=f"Missing bracket inserted: '{bracket}' at position {insert_at}",
                            position=insert_at,
                            original_text="",
                            recovered_text=bracket,
                            action=RecoveryAction.RECOVERED,
                        )
                        issues.append(issue)
                        break
    
    # Check if brackets are now balanced
    unmatched = check_bracket_balance(result)
    if unmatched:
        # Still unbalanced - may need retry
        for bracket, pos in unmatched:
            issue = RecoveryIssue(
                type=RecoveryType.BRACKET_BALANCE,
                description=f"Unbalanced bracket at position {pos}: '{bracket}'",
                position=pos,
                original_text=bracket,
                recovered_text="",
                action=RecoveryAction.NEEDS_RETRY,
            )
            issues.append(issue)
    
    return result, issues


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
    """Attempt to fix unbalanced quotes by comparing with original.
    
    Args:
        text: The translated text.
        original: The original text.
        
    Returns:
        Tuple of (fixed_text, list of issues found).
    """
    issues: List[RecoveryIssue] = []
    result = text
    
    # Get quote info from original
    orig_unmatched = check_quote_balance(original)
    trans_unmatched = check_quote_balance(text)
    
    if not trans_unmatched:
        return result, issues  # Already balanced
    
    # Count quotes by type in both
    orig_quotes = [ch for ch in original if ch in QUOTE_PAIRS or ch in QUOTE_PAIRS.values()]
    trans_quotes = [ch for ch in text if ch in QUOTE_PAIRS or ch in QUOTE_PAIRS.values()]
    
    # Look for missing quotes
    for quote in set(orig_quotes):
        orig_count = orig_quotes.count(quote)
        trans_count = trans_quotes.count(quote)
        
        if trans_count < orig_count:
            # Missing quotes
            missing_count = orig_count - trans_count
            
            # Try to add missing quote at end or start based on type
            if quote in QUOTE_PAIRS.values() and quote not in QUOTE_PAIRS:
                # Closing quote - add at end
                result = result.rstrip() + quote
                issue = RecoveryIssue(
                    type=RecoveryType.QUOTE_BALANCE,
                    description=f"Missing closing quote added at end: '{quote}'",
                    position=len(result) - 1,
                    original_text="",
                    recovered_text=quote,
                    action=RecoveryAction.RECOVERED,
                )
                issues.append(issue)
            elif quote in QUOTE_PAIRS and quote not in QUOTE_PAIRS.values():
                # Opening quote - harder to place, flag for retry
                issue = RecoveryIssue(
                    type=RecoveryType.QUOTE_BALANCE,
                    description=f"Missing opening quote could not be auto-placed: '{quote}'",
                    position=-1,
                    original_text="",
                    recovered_text=quote,
                    action=RecoveryAction.NEEDS_RETRY,
                )
                issues.append(issue)
    
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
# Main Recovery Functions
# ============================================================================


def recover_line(
    original: str,
    translated: str,
    enable_placeholder_recovery: bool = True,
    enable_bracket_recovery: bool = True,
    enable_quote_recovery: bool = True,
    enable_whitespace_normalization: bool = True,
) -> RecoveryResult:
    """Apply all recovery operations to a single translated line.
    
    Args:
        original: The original line (pre-translation).
        translated: The translated line.
        enable_placeholder_recovery: Enable placeholder-related recovery.
        enable_bracket_recovery: Enable bracket balancing.
        enable_quote_recovery: Enable quote balancing.
        enable_whitespace_normalization: Enable whitespace fixes.
        
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
        
        # 3. Normalize whitespace in placeholders
        if enable_whitespace_normalization:
            current_text, issues = normalize_placeholder_whitespace(current_text)
            all_issues.extend(issues)
        
        # 4. Attempt to recover missing placeholders
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
    
    if enable_bracket_recovery:
        # 5. Fix bracket balance
        current_text, issues = recover_bracket_balance(current_text, original)
        all_issues.extend(issues)
    
    if enable_quote_recovery:
        # 6. Fix quote balance
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
) -> BatchRecoveryResult:
    """Apply recovery operations to a batch of translated lines.
    
    Args:
        originals: List of original lines.
        translations: List of translated lines.
        enable_placeholder_recovery: Enable placeholder-related recovery.
        enable_bracket_recovery: Enable bracket balancing.
        enable_quote_recovery: Enable quote balancing.
        enable_whitespace_normalization: Enable whitespace fixes.
        
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
    ):
        """Initialize the post-process manager.
        
        Args:
            enable_placeholder_recovery: Enable placeholder-related recovery.
            enable_bracket_recovery: Enable bracket balancing.
            enable_quote_recovery: Enable quote balancing.
            enable_whitespace_normalization: Enable whitespace fixes.
            auto_retry_on_failure: Automatically flag unrecoverable issues for retry.
        """
        self.enable_placeholder_recovery = enable_placeholder_recovery
        self.enable_bracket_recovery = enable_bracket_recovery
        self.enable_quote_recovery = enable_quote_recovery
        self.enable_whitespace_normalization = enable_whitespace_normalization
        self.auto_retry_on_failure = auto_retry_on_failure
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
) -> PostProcessManager:
    """Create a PostProcessManager with specified settings.
    
    Args:
        enable_placeholder_recovery: Enable placeholder-related recovery.
        enable_bracket_recovery: Enable bracket balancing.
        enable_quote_recovery: Enable quote balancing.
        enable_whitespace_normalization: Enable whitespace fixes.
        auto_retry_on_failure: Automatically flag unrecoverable issues for retry.
        
    Returns:
        Configured PostProcessManager instance.
    """
    return PostProcessManager(
        enable_placeholder_recovery=enable_placeholder_recovery,
        enable_bracket_recovery=enable_bracket_recovery,
        enable_quote_recovery=enable_quote_recovery,
        enable_whitespace_normalization=enable_whitespace_normalization,
        auto_retry_on_failure=auto_retry_on_failure,
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
        RecoveryType.PLACEHOLDER_CASE: "Fix placeholder case (e.g., __prot__ → __PROT__)",
        RecoveryType.PLACEHOLDER_MANGLED: "Fix mangled placeholders (e.g., __PR OT__ → __PROT__)",
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
