"""Mock Translation engine for CherryAI.

Provides deterministic nonsense translation for pipeline testing without
API keys or network connectivity.  Includes deliberate flaw injection
(Phase 56) to validate that postprocessing recovery handles malformed
placeholders, anchor manipulation, code intrusion, and character surgery.

Spec reference: specs.md §5.13 Mock Translation Extended
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("cherryai.mock_translator")

# ============================================================================
# Constants
# ============================================================================

# Limited word lists for mock replacement (English-style nonsense)
MOCK_WORDS: List[str] = [
    "alpha", "bravo", "cherry", "delta", "echo", "foxtrot", "gamma",
    "hotel", "indigo", "juliet", "kilo", "lima", "metro", "nova",
    "oscar", "papa", "quest", "romeo", "sierra", "tango", "ultra",
    "victor", "whiskey", "xray", "yankee", "zulu",
]

# Japanese-specific: katakana syllables for Japanese mock output
MOCK_KATAKANA: List[str] = [
    "アルファ", "ブラボー", "チェリー", "デルタ", "エコー",
    "フォックス", "ガンマ", "ホテル", "インディゴ", "ジュリエット",
    "キロ", "リマ", "メトロ", "ノヴァ", "オスカー",
]

# Placeholder regex: matches __PROT__, __PROT_1__, __DEDUP__, __CUSTOM__, etc.
_PLACEHOLDER_RE = re.compile(r"(__[A-Za-z][A-Za-z0-9]*(?:_\d+)?__)")

# Speaker:dialogue pattern
_SPEAKER_RE = re.compile(r"^(.+?):\s*(.*)$")

# Anchor characters used in CherryAI
ANCHOR_CHARS = set("[]{}()<>「」『』【】")


# ============================================================================
# Flaw Configuration
# ============================================================================


class FlawIntensity(Enum):
    """Intensity level for deliberate flaw injection."""

    MILD = "mild"          # ~10 % of eligible items corrupted
    MODERATE = "moderate"  # ~30 % of eligible items corrupted
    SEVERE = "severe"      # ~60 % of eligible items corrupted


@dataclass
class FlawConfig:
    """Configuration for deliberate flaw injection in mock translation.

    Attributes:
        enabled: Master switch for flaw injection.
        intensity: How aggressively flaws are introduced.
        flaw_line_ratio: Fraction of lines that may receive flaws (0.0-1.0).
        placeholder_malformation: Enable placeholder corruption.
        anchor_manipulation: Enable anchor removal / insertion.
        code_intrusion: Enable random replacement inside code boundaries.
        character_surgery: Enable random character insertion / deletion.
        seed: Random seed for reproducibility (None = non-deterministic).
    """

    enabled: bool = True
    intensity: FlawIntensity = FlawIntensity.MODERATE
    flaw_line_ratio: float = 0.20
    placeholder_malformation: bool = True
    anchor_manipulation: bool = True
    code_intrusion: bool = True
    character_surgery: bool = True
    seed: Optional[int] = None

    @property
    def corruption_probability(self) -> float:
        """Per-item corruption probability derived from intensity."""
        return {
            FlawIntensity.MILD: 0.10,
            FlawIntensity.MODERATE: 0.30,
            FlawIntensity.SEVERE: 0.60,
        }[self.intensity]


@dataclass
class FlawReport:
    """Tracks all flaws deliberately introduced during mock translation.

    Useful for test assertions: the test knows exactly what was broken
    and can verify that recovery fixes it.
    """

    total_lines: int = 0
    flawed_lines: int = 0
    placeholder_malformations: int = 0
    anchor_removals: int = 0
    anchor_insertions: int = 0
    code_intrusions: int = 0
    character_surgeries: int = 0
    details: List[Dict[str, str]] = field(default_factory=list)

    def record(self, line_idx: int, flaw_type: str, before: str, after: str) -> None:
        """Record a single flaw."""
        self.details.append({
            "line": str(line_idx),
            "type": flaw_type,
            "before": before,
            "after": after,
        })


# ============================================================================
# Mock Translation Engine
# ============================================================================


class MockTranslator:
    """Deterministic mock translator with optional flaw injection.

    Standard behaviour:
        - Replaces Japanese text with random English-style words.
        - Replaces non-Japanese text with word-reversed variants.
        - Preserves all ``__PROT__``, ``__DEDUP__``, ``__CUSTOM__`` tokens.
        - Preserves speaker format (``Speaker: "Dialogue"``).

    Flaw testing (Phase 56):
        When ``flaw_config.enabled`` is True the translator deliberately
        corrupts a fraction of lines to stress-test the recovery pipeline.
    """

    def __init__(
        self,
        flaw_config: Optional[FlawConfig] = None,
        delay_per_chunk: float = 0.0,
    ) -> None:
        self.flaw_config = flaw_config or FlawConfig(enabled=False)
        self.delay_per_chunk = delay_per_chunk
        self._rng = random.Random(self.flaw_config.seed)
        self.flaw_report = FlawReport()
        logger.info(
            "MockTranslator initialized (flaws=%s, intensity=%s)",
            self.flaw_config.enabled,
            self.flaw_config.intensity.value if self.flaw_config.enabled else "off",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate_batch(self, lines: List[str]) -> List[str]:
        """Translate a batch of lines with optional flaw injection.

        Args:
            lines: Source lines (may contain placeholders, anchors, code).

        Returns:
            List of mock-translated lines, same length as input.
        """
        if self.delay_per_chunk > 0:
            time.sleep(self.delay_per_chunk)

        self.flaw_report.total_lines += len(lines)
        results: List[str] = []

        for idx, line in enumerate(lines):
            translated = self._translate_line(line)
            if self.flaw_config.enabled and self._should_flaw_line():
                translated = self._apply_flaws(translated, idx)
            results.append(translated)

        return results

    def translate_line(self, line: str) -> str:
        """Translate a single line (convenience wrapper)."""
        return self.translate_batch([line])[0]

    def get_report(self) -> FlawReport:
        """Return the flaw report accumulated so far."""
        return self.flaw_report

    def reset_report(self) -> None:
        """Clear the flaw report."""
        self.flaw_report = FlawReport()

    # ------------------------------------------------------------------
    # Core Translation (Standard Mock)
    # ------------------------------------------------------------------

    def _translate_line(self, line: str) -> str:
        """Produce deterministic mock output for a single line.

        Strategy:
        1. Extract and preserve placeholders.
        2. Detect speaker prefix and preserve it.
        3. Replace text segments with mock words.
        4. Re-insert placeholders in their original positions.
        """
        if not line or not line.strip():
            return line

        # Split line into placeholder tokens and text segments
        parts = _PLACEHOLDER_RE.split(line)
        translated_parts: List[str] = []

        for part in parts:
            if _PLACEHOLDER_RE.fullmatch(part):
                # Preserve placeholder exactly
                translated_parts.append(part)
            else:
                translated_parts.append(self._mock_replace_text(part))

        return "".join(translated_parts)

    def _mock_replace_text(self, text: str) -> str:
        """Replace translatable text with mock words.

        Preserves:
        - Whitespace boundaries
        - Punctuation at word boundaries
        - Speaker prefix (``Name:``)
        - Anchor characters within the text
        """
        if not text.strip():
            return text

        # Check for speaker prefix
        speaker_match = _SPEAKER_RE.match(text)
        if speaker_match:
            speaker = speaker_match.group(1)
            dialogue = speaker_match.group(2)
            return f"{speaker}: {self._mock_replace_segment(dialogue)}"

        return self._mock_replace_segment(text)

    def _mock_replace_segment(self, segment: str) -> str:
        """Replace a text segment word-by-word with mock words.

        Uses a deterministic hash of the original word to pick from
        ``MOCK_WORDS`` so the same input always yields the same output.

        Anchor characters and punctuation are preserved in place.
        """
        if not segment.strip():
            return segment

        # Tokenize: split around anchor/bracket characters individually
        # This ensures 「テスト」 becomes ["「", "テスト", "」"]
        tokens = _tokenize_preserving_anchors(segment)
        result: List[str] = []

        for token in tokens:
            if not token.strip():
                # Preserve whitespace
                result.append(token)
            elif self._is_punctuation_or_anchor(token):
                # Preserve punctuation / anchors
                result.append(token)
            elif _contains_japanese(token):
                # Japanese word → pick from MOCK_WORDS based on hash
                idx = hash(token) % len(MOCK_WORDS)
                result.append(MOCK_WORDS[idx])
            else:
                # Non-Japanese word → simple reversal
                result.append(token[::-1])

        return "".join(result)

    @staticmethod
    def _is_punctuation_or_anchor(token: str) -> bool:
        """Check if a token is purely punctuation or anchor characters."""
        return all(
            c in ANCHOR_CHARS or not c.isalnum()
            for c in token
        )

    # ------------------------------------------------------------------
    # Flaw Injection (Phase 56)
    # ------------------------------------------------------------------

    def _should_flaw_line(self) -> bool:
        """Decide whether to inject flaws into the current line."""
        return self._rng.random() < self.flaw_config.flaw_line_ratio

    def _apply_flaws(self, line: str, line_idx: int) -> str:
        """Apply enabled flaws to a translated line."""
        original = line
        flawed = False

        if self.flaw_config.placeholder_malformation:
            line, changed = self._flaw_placeholder_malformation(line, line_idx)
            if changed:
                flawed = True

        if self.flaw_config.anchor_manipulation:
            line, changed = self._flaw_anchor_manipulation(line, line_idx)
            if changed:
                flawed = True

        if self.flaw_config.code_intrusion:
            line, changed = self._flaw_code_intrusion(line, line_idx)
            if changed:
                flawed = True

        if self.flaw_config.character_surgery:
            line, changed = self._flaw_character_surgery(line, line_idx)
            if changed:
                flawed = True

        if flawed:
            self.flaw_report.flawed_lines += 1
            logger.debug("Flawed line %d: %r -> %r", line_idx, original, line)

        return line

    # -- Task 56.1: Placeholder Malformation --

    def _flaw_placeholder_malformation(
        self, line: str, line_idx: int
    ) -> Tuple[str, bool]:
        """Surgically corrupt placeholder tokens.

        Corruption types:
        - Remove a character from the token name (``__PROT__`` → ``__PRT__``)
        - Add a character into the token name (``__PROT__`` → ``__PROTT__``)
        - Insert a space into the token (``__PROT__`` → ``__PRO T__``)
        """
        placeholders = list(_PLACEHOLDER_RE.finditer(line))
        if not placeholders:
            return line, False

        changed = False
        # Process in reverse to maintain positions
        for match in reversed(placeholders):
            if self._rng.random() > self.flaw_config.corruption_probability:
                continue

            original_ph = match.group(0)
            corrupted = self._corrupt_placeholder(original_ph)
            if corrupted != original_ph:
                before = line
                line = line[:match.start()] + corrupted + line[match.end():]
                self.flaw_report.placeholder_malformations += 1
                self.flaw_report.record(
                    line_idx, "placeholder_malformation", original_ph, corrupted
                )
                changed = True

        return line, changed

    def _corrupt_placeholder(self, placeholder: str) -> str:
        """Apply a random corruption to a single placeholder token."""
        # Extract the inner name (between __ delimiters)
        inner_match = re.match(r"^__(.+)__$", placeholder)
        if not inner_match:
            return placeholder

        inner = inner_match.group(1)
        corruption_type = self._rng.choice(["remove_char", "add_char", "insert_space"])

        if corruption_type == "remove_char" and len(inner) > 1:
            # Remove a random character from the inner name
            pos = self._rng.randint(0, len(inner) - 1)
            inner = inner[:pos] + inner[pos + 1:]
        elif corruption_type == "add_char":
            # Add a random character into the inner name
            pos = self._rng.randint(0, len(inner))
            char = self._rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            inner = inner[:pos] + char + inner[pos:]
        elif corruption_type == "insert_space":
            # Insert a space into the inner name
            pos = self._rng.randint(1, max(1, len(inner) - 1))
            inner = inner[:pos] + " " + inner[pos:]

        return f"__{inner}__"

    # -- Task 56.2: Anchor Manipulation --

    def _flaw_anchor_manipulation(
        self, line: str, line_idx: int
    ) -> Tuple[str, bool]:
        """Remove existing anchors and/or add anchors where they don't belong.

        Operations:
        - Remove an existing anchor character at a random position.
        - Insert an anchor character at a random non-anchor position.
        """
        changed = False

        # Find existing anchor positions
        anchor_positions = [
            i for i, c in enumerate(line) if c in ANCHOR_CHARS
        ]

        # Remove an existing anchor
        if anchor_positions and self._rng.random() < self.flaw_config.corruption_probability:
            pos = self._rng.choice(anchor_positions)
            removed_char = line[pos]
            line = line[:pos] + line[pos + 1:]
            self.flaw_report.anchor_removals += 1
            self.flaw_report.record(
                line_idx, "anchor_removal", removed_char, f"(removed at pos {pos})"
            )
            changed = True

        # Insert a spurious anchor
        if len(line) > 2 and self._rng.random() < self.flaw_config.corruption_probability:
            pos = self._rng.randint(1, len(line) - 1)
            anchor = self._rng.choice(list(ANCHOR_CHARS))
            line = line[:pos] + anchor + line[pos:]
            self.flaw_report.anchor_insertions += 1
            self.flaw_report.record(
                line_idx, "anchor_insertion", f"(inserted {anchor} at pos {pos})", anchor
            )
            changed = True

        return line, changed

    # -- Task 56.3: Code Intrusion and Character Surgery --

    def _flaw_code_intrusion(
        self, line: str, line_idx: int
    ) -> Tuple[str, bool]:
        """Replace words inside code-like boundaries with random words.

        Targets text between angle brackets ``<...>`` or square brackets
        ``[...]`` which typically represent code patterns.
        """
        code_pattern = re.compile(r"(<[^>]+>|\[[^\]]+\])")
        matches = list(code_pattern.finditer(line))
        if not matches:
            return line, False

        changed = False
        for match in reversed(matches):
            if self._rng.random() > self.flaw_config.corruption_probability:
                continue

            original_code = match.group(0)
            bracket_open = original_code[0]
            bracket_close = original_code[-1]
            inner = original_code[1:-1]

            # Replace some words inside the code
            words = inner.split()
            if words:
                replace_idx = self._rng.randint(0, len(words) - 1)
                original_word = words[replace_idx]
                words[replace_idx] = self._rng.choice(MOCK_WORDS)
                corrupted = bracket_open + " ".join(words) + bracket_close
                line = line[:match.start()] + corrupted + line[match.end():]
                self.flaw_report.code_intrusions += 1
                self.flaw_report.record(
                    line_idx, "code_intrusion", original_code, corrupted
                )
                changed = True

        return line, changed

    def _flaw_character_surgery(
        self, line: str, line_idx: int
    ) -> Tuple[str, bool]:
        """Add and remove characters at random positions.

        Operations:
        - Delete a random non-placeholder, non-whitespace character.
        - Insert a random ASCII letter at a random position.
        """
        if len(line) < 3:
            return line, False

        changed = False

        # Identify safe positions (not inside placeholders)
        placeholder_spans: List[Tuple[int, int]] = []
        for m in _PLACEHOLDER_RE.finditer(line):
            placeholder_spans.append((m.start(), m.end()))

        def _in_placeholder(pos: int) -> bool:
            return any(s <= pos < e for s, e in placeholder_spans)

        # Delete a random character
        if self._rng.random() < self.flaw_config.corruption_probability:
            safe_positions = [
                i for i in range(len(line))
                if not _in_placeholder(i) and not line[i].isspace()
            ]
            if safe_positions:
                pos = self._rng.choice(safe_positions)
                removed = line[pos]
                line = line[:pos] + line[pos + 1:]
                self.flaw_report.character_surgeries += 1
                self.flaw_report.record(
                    line_idx, "character_deletion", removed, f"(deleted at pos {pos})"
                )
                changed = True
                # Recompute placeholder spans after deletion
                placeholder_spans = [
                    (m.start(), m.end()) for m in _PLACEHOLDER_RE.finditer(line)
                ]

        # Insert a random character
        if self._rng.random() < self.flaw_config.corruption_probability:
            safe_positions = [
                i for i in range(len(line))
                if not _in_placeholder(i)
            ]
            if safe_positions:
                pos = self._rng.choice(safe_positions)
                char = self._rng.choice("abcdefghijklmnopqrstuvwxyz")
                line = line[:pos] + char + line[pos:]
                self.flaw_report.character_surgeries += 1
                self.flaw_report.record(
                    line_idx, "character_insertion", f"(inserted '{char}' at pos {pos})", char
                )
                changed = True

        return line, changed


# ============================================================================
# Module-level helpers
# ============================================================================


# Regex that splits text around anchor/bracket characters while keeping them
_ANCHOR_SPLIT_RE = re.compile(
    r"([" + re.escape("".join(ANCHOR_CHARS)) + r"]|\s+)"
)


def _tokenize_preserving_anchors(text: str) -> List[str]:
    """Split text into tokens, keeping anchors and whitespace as separate items.

    Example: ``「テスト」 [code]`` → ``["「", "テスト", "」", " ", "[", "code", "]"]``
    """
    parts = _ANCHOR_SPLIT_RE.split(text)
    return [p for p in parts if p]


def _contains_japanese(text: str) -> bool:
    """Return True if text contains any Japanese characters."""
    for ch in text:
        cp = ord(ch)
        if (
            0x3040 <= cp <= 0x309F  # Hiragana
            or 0x30A0 <= cp <= 0x30FF  # Katakana
            or 0x4E00 <= cp <= 0x9FFF  # CJK Unified
            or 0xFF66 <= cp <= 0xFF9D  # Halfwidth katakana
        ):
            return True
    return False


def create_mock_translator(
    enable_flaws: bool = False,
    intensity: str = "moderate",
    seed: Optional[int] = None,
    flaw_line_ratio: float = 0.20,
    delay: float = 0.0,
) -> MockTranslator:
    """Factory function to create a configured MockTranslator.

    Args:
        enable_flaws: Whether to enable deliberate flaw injection.
        intensity: Flaw intensity (``mild``, ``moderate``, ``severe``).
        seed: Random seed for reproducibility.
        flaw_line_ratio: Fraction of lines that may receive flaws.
        delay: Simulated delay per chunk in seconds.

    Returns:
        A configured ``MockTranslator`` instance.
    """
    intensity_enum = FlawIntensity(intensity)
    config = FlawConfig(
        enabled=enable_flaws,
        intensity=intensity_enum,
        flaw_line_ratio=flaw_line_ratio,
        seed=seed,
    )
    return MockTranslator(flaw_config=config, delay_per_chunk=delay)
