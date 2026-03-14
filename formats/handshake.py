"""Parser Handshake — Unified I/O Parser Interface.

Defines the formal contract that every file-format parser must satisfy.
Contains mandatory/optional component validation, shared dataclasses,
and error types for parser compliance.

Mandatory components (M1-M3):
    - M1: extract(path, encoding) → list[str]
    - M2: inject(path, lines, encoding)
    - M3: format_id + extensions  OR  can_handle(path) → bool

Optional components (O1-O8):
    - O1: decrypt(path) → path
    - O2: encrypt(path) → path
    - O3: detect_encoding(path) → str  OR  encoding: str
    - O4: detect_speakers(lines) → list[SpeakerInfo]
    - O5: wordwrap_config: WordwrapConfig
    - O6: wordwrap(line, config) → list[str]
    - O7: forbidden_chars: ForbiddenChars
    - O8: tag_rules: TagRules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


__all__ = [
    "ExtractedLine",
    "ParserError",
    "SpeakerInfo",
    "validate_parser",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SpeakerInfo:
    """Speaker detected by a parser during extraction.

    Attributes:
        name: Speaker name as detected (empty string for narration).
        line_idx: Index into the extracted lines where this speaker appears.
    """

    name: str
    line_idx: int


@dataclass
class ExtractedLine:
    """A single line extracted by a parser with optional metadata.

    Returned by ``extract_tagged()`` to provide per-line tag and speaker
    information alongside the translatable text.

    Attributes:
        text: The translatable text content.
        tag: Parser-specific tag (e.g. ``"dialogue"``, ``"menu"``,
            ``"variable"``).  Empty string when untagged.
        speaker: Speaker name for dialogue lines.  Empty for non-dialogue.
        context: Free-form context hint for the translator (optional).
    """

    text: str
    tag: str = ""
    speaker: str = ""
    context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        d: Dict[str, Any] = {"text": self.text}
        if self.tag:
            d["tag"] = self.tag
        if self.speaker:
            d["speaker"] = self.speaker
        if self.context:
            d["context"] = self.context
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractedLine":
        """Deserialise from dictionary."""
        return cls(
            text=str(data.get("text", "")),
            tag=str(data.get("tag", "")),
            speaker=str(data.get("speaker", "")),
            context=str(data.get("context", "")),
        )


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class ParserError(Exception):
    """Raised when a mandatory parser component fails.

    Attributes:
        parser_name: Name of the parser that raised the error.
        component: Which component failed (e.g. ``"extract"``, ``"inject"``).
        detail: Human-readable detail message.
    """

    def __init__(
        self,
        message: str,
        *,
        parser_name: str = "",
        component: str = "",
    ) -> None:
        self.parser_name = parser_name
        self.component = component
        super().__init__(message)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_parser(parser: Any) -> List[str]:
    """Validate that *parser* satisfies the mandatory handshake contract.

    Checks:
        - M1: ``extract`` callable exists.
        - M2: ``inject`` callable exists.
        - M3: Non-empty ``format_id`` + ``extensions``, **or**
               ``can_handle`` callable defined (and not the no-op default).

    Args:
        parser: A ``FormatHandler`` or ``ParserScript`` instance.

    Returns:
        List of error messages.  Empty list means the parser is valid.
    """
    errors: List[str] = []

    # M1 — extract
    extract_fn = getattr(parser, "extract", None)
    if not callable(extract_fn):
        errors.append("M1: missing callable 'extract'")

    # M2 — inject
    inject_fn = getattr(parser, "inject", None)
    if not callable(inject_fn):
        errors.append("M2: missing callable 'inject'")

    # M3 — identification
    format_id = getattr(parser, "format_id", None)
    extensions = getattr(parser, "extensions", None)
    can_handle_fn = getattr(parser, "can_handle", None)

    has_format_id = bool(format_id)
    has_extensions = bool(extensions)

    # can_handle is valid only when it's not the base ParserScript default
    has_can_handle = False
    if callable(can_handle_fn):
        # Check if can_handle is overridden (not the default returning False)
        from .parser_base import ParserScript
        if isinstance(parser, ParserScript):
            # It's overridden if the method differs from the base class default
            if type(parser).can_handle is not ParserScript.can_handle:
                has_can_handle = True
        else:
            has_can_handle = True

    if not (has_format_id and has_extensions) and not has_can_handle:
        errors.append(
            "M3: must provide (format_id + extensions) or override can_handle()"
        )

    return errors
