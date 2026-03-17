"""Parser Script base interface for CherryAI (Phase 53).

Parser Scripts are game-engine-specific or format-specific scripts that
handle extraction, injection, and optionally provide wordwrap settings,
forbidden characters, and tag rules.

Usage::

    from formats.parser_base import ParserScript, WordwrapConfig

    class MyParser(ParserScript):
        @property
        def name(self) -> str:
            return "MyEngine"

        def extract(self, file_path):
            ...

        def inject(self, file_path, lines):
            ...
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


__all__ = [
    "ParserScript",
    "WordwrapConfig",
    "ForbiddenChars",
    "TagRules",
    "ContextMarkerRules",  # backward-compatible alias
    "ExtractedLine",
    "SpeakerInfo",
    "ParserError",
]

# Re-export handshake types for convenience
from .handshake import ExtractedLine, ParserError, SpeakerInfo

# Regex matching "Speaker: dialogue" or "Speaker： dialogue" (half/fullwidth colon)
_SPEAKER_DIALOGUE_RE = re.compile(r"^(.+?)(?:：|: )(.+)$", re.DOTALL)


def _split_speaker_dialogue(text: str) -> Tuple[str, str]:
    """Split ``'Speaker: dialogue'`` into ``(speaker, dialogue)``.

    Recognises both half-width ``: `` and fullwidth ``： `` separators.
    Returns ``("", text)`` when no separator is found.
    """
    m = _SPEAKER_DIALOGUE_RE.match(text)
    if m:
        return m.group(1), m.group(2)
    return "", text


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WordwrapConfig:
    """Engine-specific wordwrap configuration provided by a parser.

    Attributes:
        max_line_length: Maximum characters (or pixels) per visual line.
        max_line_number: Maximum visual lines per text box.
        wordwrap_command: Line-break command for the engine (e.g. ``\\n``).
        new_textbox_injection: Command to start a new text box on overflow.
    """

    max_line_length: int = 48
    max_line_number: int = 4
    wordwrap_command: str = "\\n"
    new_textbox_injection: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "max_line_length": self.max_line_length,
            "max_line_number": self.max_line_number,
            "wordwrap_command": self.wordwrap_command,
            "new_textbox_injection": self.new_textbox_injection,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WordwrapConfig":
        """Deserialise from dictionary."""
        return cls(
            max_line_length=int(data.get("max_line_length", 48)),
            max_line_number=int(data.get("max_line_number", 4)),
            wordwrap_command=str(data.get("wordwrap_command", "\\n")),
            new_textbox_injection=str(data.get("new_textbox_injection", "")),
        )


@dataclass
class ForbiddenChars:
    """Characters that must not appear in translated output.

    Attributes:
        characters: Set of forbidden characters.
        logit_bias: Token-ID → bias mapping for API requests.
        output_action: ``"replace"`` (auto-fix) or ``"flag"`` (manual review).
    """

    characters: List[str] = field(default_factory=list)
    logit_bias: Dict[str, float] = field(default_factory=dict)
    output_action: str = "flag"  # "replace" | "flag"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "characters": self.characters,
            "logit_bias": self.logit_bias,
            "output_action": self.output_action,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForbiddenChars":
        """Deserialise from dictionary."""
        return cls(
            characters=list(data.get("characters", [])),
            logit_bias=dict(data.get("logit_bias", {})),
            output_action=str(data.get("output_action", "flag")),
        )


@dataclass
class TagRules:
    """Engine-specific patterns for detecting per-line tags.

    Attributes:
        scene_pattern: Regex for scene/file boundaries.
        dialogue_pattern: Regex for dialogue sections.
        menu_pattern: Regex for menu sections.
        choice_pattern: Regex for choice sections.
    """

    scene_pattern: str = ""
    dialogue_pattern: str = ""
    menu_pattern: str = ""
    choice_pattern: str = ""

    def compiled(self) -> Dict[str, Optional[re.Pattern]]:
        """Return compiled regex patterns (None for empty strings)."""
        result: Dict[str, Optional[re.Pattern]] = {}
        for key in ("scene_pattern", "dialogue_pattern",
                     "menu_pattern", "choice_pattern"):
            raw = getattr(self, key)
            result[key] = re.compile(raw) if raw else None
        return result

    def to_dict(self) -> Dict[str, str]:
        """Serialise to dictionary."""
        return {
            "scene_pattern": self.scene_pattern,
            "dialogue_pattern": self.dialogue_pattern,
            "menu_pattern": self.menu_pattern,
            "choice_pattern": self.choice_pattern,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TagRules":
        """Deserialise from dictionary."""
        return cls(
            scene_pattern=str(data.get("scene_pattern", "")),
            dialogue_pattern=str(data.get("dialogue_pattern", "")),
            menu_pattern=str(data.get("menu_pattern", "")),
            choice_pattern=str(data.get("choice_pattern", "")),
        )


# Backward-compatible alias
ContextMarkerRules = TagRules


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class ParserScript(ABC):
    """Abstract base class for game-engine parser scripts.

    Subclasses must implement:
    - :attr:`name`: unique parser identifier string.
    - :meth:`extract`: read translatable lines from a source file.
    - :meth:`inject`: write translated lines back into a file copy.

    Subclasses may override:
    - :attr:`wordwrap_config`: engine-specific wrapping defaults.
    - :attr:`forbidden_chars`: characters to ban during translation.
    - :attr:`tag_rules`: patterns for tag detection.
    - :meth:`can_handle`: probe whether a file belongs to this engine.
    """

    # ------------------------------------------------------------------
    # Mandatory
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique parser identifier (e.g. ``"RPGMakerMV"``)."""
        ...

    @abstractmethod
    def extract(self, file_path: Path) -> List[str]:
        """Extract translatable lines from *file_path*.

        Args:
            file_path: Path to the source file.

        Returns:
            List of translatable text lines.
        """
        ...

    @abstractmethod
    def inject(self, file_path: Path, lines: List[str]) -> None:
        """Inject *lines* back into a copy/target of *file_path*.

        Args:
            file_path: Path to the target file.
            lines: Translated lines to inject.
        """
        ...

    # ------------------------------------------------------------------
    # Optional — override to provide engine-specific configuration
    # ------------------------------------------------------------------

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        """Engine-specific wordwrap settings, or ``None``."""
        return None

    @property
    def forbidden_chars(self) -> Optional[ForbiddenChars]:
        """Forbidden characters for this engine, or ``None``."""
        return None

    @property
    def tag_rules(self) -> Optional[TagRules]:
        """Tag detection patterns, or ``None``."""
        return None

    # Backward-compatible alias
    @property
    def context_marker_rules(self) -> Optional[TagRules]:
        """Deprecated alias for :attr:`tag_rules`."""
        return self.tag_rules

    @property
    def display_name(self) -> str:
        """Human-readable name for the parser (shown in the GUI).

        Defaults to :attr:`name`.  Override for a friendlier label.
        """
        return self.name

    @property
    def tooltip(self) -> str:
        """Short description shown as a tooltip in the GUI.

        Defaults to an empty string.  Override to provide parser info.
        """
        return ""

    def can_handle(self, file_path: Path) -> bool:
        """Probe whether *file_path* is handled by this parser.

        Default implementation returns ``False``.  Override to add
        auto-detection logic.

        Args:
            file_path: Path to the file to probe.

        Returns:
            ``True`` if this parser can handle the file.
        """
        return False

    # ------------------------------------------------------------------
    # Optional — tagged extraction (Parser Handshake O4/O8 extensions)
    # ------------------------------------------------------------------

    def extract_tagged(self, file_path: Path) -> Optional[List["ExtractedLine"]]:
        """Extract translatable lines with per-line tags and speaker info.

        Override to provide richer extraction metadata.  When present the
        pipeline uses this instead of plain :meth:`extract`.

        Returns:
            List of :class:`ExtractedLine`, or ``None`` to fall back to
            :meth:`extract`.
        """
        return None

    def detect_speakers(
        self, lines: List[str],
    ) -> Optional[List["SpeakerInfo"]]:
        """Detect speakers from extracted lines (O4).

        Override when the parser can reliably identify speakers.  When
        provided the generic regex-based speaker detector is skipped.

        Returns:
            List of :class:`SpeakerInfo`, or ``None``.
        """
        return None

    def wordwrap_for_tag(
        self, tag: str,
    ) -> Optional[WordwrapConfig]:
        """Return a tag-specific wordwrap config.

        Override when different extraction types (e.g. dialogue vs menu)
        require different wrapping settings.

        Args:
            tag: The extraction tag (e.g. ``"dialogue"``, ``"menu"``).

        Returns:
            Tag-specific :class:`WordwrapConfig`, or ``None`` to use the
            default :attr:`wordwrap_config`.
        """
        return None

    def wordwrap(
        self, line: str, config: Optional[WordwrapConfig] = None,
    ) -> Optional[List[str]]:
        """Custom wordwrap function (O6).

        Override to replace the built-in ``pretty_wrap`` with
        engine-specific wrapping logic.

        Args:
            line: Text to wrap.
            config: Wrapping settings (uses :attr:`wordwrap_config` when
                ``None``).

        Returns:
            Wrapped lines, or ``None`` to fall back to the built-in.
        """
        return None

    def pretty_wrap(
        self, text: str, width: int, break_char: str = "\n",
        max_lines: Optional[int] = None,
    ) -> Optional[str]:
        """Custom pretty-wrap replacement hook.

        Override to provide an engine-specific wrap function that the
        Wordwrap step calls *instead of* ``functions.wordwrap.pretty_wrap``
        for lines belonging to this parser.  Return ``None`` to fall back
        to the built-in ``pretty_wrap`` (default behaviour).

        Unlike :meth:`wordwrap` (O6), which replaces the *entire* per-line
        pipeline, this hook only replaces the core text-wrapping algorithm
        while keeping speaker handling, ignore-pattern stripping, and
        statistics tracking intact.

        Args:
            text: Visible text to wrap (speaker prefix already stripped
                when ``SpeakerMode == IGNORE``).
            width: Maximum visible characters per line.
            break_char: Character sequence to insert at line breaks.
            max_lines: Maximum number of output lines (``None`` = unlimited).

        Returns:
            Wrapped text with *break_char* separators, or ``None`` to use
            the built-in algorithm.
        """
        return None

    def detect_encoding(self, file_path: Path) -> Optional[str]:
        """Detect file encoding (O3).

        Override to provide engine-specific encoding detection.

        Returns:
            Encoding string, or ``None`` to use the global heuristic.
        """
        return None

    def inject_to(
        self,
        source_path: Path,
        output_path: Path,
        lines: List[str],
        *,
        orig_lines: Optional[List[str]] = None,
    ) -> List[int]:
        """Standard injection handshake: inject translated *lines* into *output_path*.

        Implements the standardized injection process with Speaker:Dialogue
        awareness.  When ``extract_tagged`` is available, each extracted
        line carries a *speaker* field.  Lines with a non-empty speaker are
        split into a **speaker part** and a **dialogue part** which are
        replaced independently in the file content:

        * The speaker name is replaced **only on its first occurrence** for
          consecutive lines with the same speaker.  Subsequent dialogue
          lines that share the speaker skip the speaker replacement.
        * The dialogue part is searched and replaced separately (no leading
          or trailing spaces unless present in the original).

        Lines without a speaker (narration, menu, variable) are handled as
        a plain find-and-replace on the full text.

        **4-step process:**

        0. Load ``\\Original`` into memory.
        1. Use :meth:`extract_tagged` (or :meth:`extract`) on the original
           to get per-line keys and speaker metadata.
        2. For each position, split Speaker:Dialogue when applicable and
           sequentially find-and-replace speaker and dialogue independently.
        3. Save the result to *output_path*.

        When *orig_lines* is provided the method uses those as the
        authority for what was stored in the manifest and verifies them
        against extracted keys.  When ``None``, the extracted keys are
        used directly (legacy compatibility).

        Args:
            source_path: Path to the original source file.
            output_path: Path to write the injected output.
            lines: Translated lines in extraction order.
            orig_lines: Original text for each position (from manifest
                ``orig`` field).  When ``None``, falls back to extracted
                keys.

        Returns:
            List of indices that failed to match (empty on full success).
        """
        enc = self.detect_encoding(source_path) or "utf-8"
        try:
            with open(source_path, "r", encoding=enc) as fh:
                content = fh.read()
        except Exception as exc:
            raise ParserError(
                f"Failed to read {source_path}: {exc}",
                parser_name=self.name,
                component="inject_to",
            ) from exc

        # Step 1: Extract keys with tagged metadata when available
        tagged = self.extract_tagged(source_path)
        if tagged is not None:
            search_keys = orig_lines if orig_lines is not None else [
                el.text for el in tagged
            ]
            speakers = [el.speaker for el in tagged]
        else:
            search_keys = (
                orig_lines if orig_lines is not None
                else self.extract(source_path)
            )
            speakers = [""] * len(search_keys)

        # Step 2: Sequential search-and-replace with speaker awareness
        failures: List[int] = []
        last_replaced_speaker: Optional[str] = None

        for i, (search, translated) in enumerate(zip(search_keys, lines)):
            if search == translated:
                # No change — but still track speaker for skip logic
                if i < len(speakers) and speakers[i]:
                    last_replaced_speaker = _split_speaker_dialogue(search)[0]
                continue

            speaker = speakers[i] if i < len(speakers) else ""

            if speaker:
                # --- Speaker:Dialogue line ---
                orig_sp, orig_dlg = _split_speaker_dialogue(search)
                trans_sp, trans_dlg = _split_speaker_dialogue(translated)

                # Replace speaker name only on first occurrence for this
                # speaker (consecutive same-speaker dialogue lines skip).
                if orig_sp and orig_sp != last_replaced_speaker:
                    if trans_sp and trans_sp != orig_sp:
                        pos = content.find(orig_sp)
                        if pos >= 0:
                            content = (
                                content[:pos]
                                + trans_sp
                                + content[pos + len(orig_sp):]
                            )
                    last_replaced_speaker = orig_sp

                # Replace dialogue text (no leading/trailing space changes)
                if orig_dlg and trans_dlg != orig_dlg:
                    pos = content.find(orig_dlg)
                    if pos >= 0:
                        content = (
                            content[:pos]
                            + trans_dlg
                            + content[pos + len(orig_dlg):]
                        )
                    else:
                        failures.append(i)
                        logger.warning(
                            "inject_to [%s]: dialogue not found at "
                            "position %d: %r",
                            self.name, i,
                            orig_dlg[:80] if orig_dlg else "",
                        )
            else:
                # --- Plain line (no speaker) ---
                last_replaced_speaker = None
                pos = content.find(search)
                if pos >= 0:
                    content = (
                        content[:pos]
                        + translated
                        + content[pos + len(search):]
                    )
                else:
                    failures.append(i)
                    logger.warning(
                        "inject_to [%s]: failed to find text at "
                        "position %d: %r",
                        self.name, i, search[:80] if search else "",
                    )

        # Step 3: Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(output_path, "w", encoding=enc) as fh:
                fh.write(content)
        except Exception as exc:
            raise ParserError(
                f"Failed to write {output_path}: {exc}",
                parser_name=self.name,
                component="inject_to",
            ) from exc

        return failures

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def info(self) -> Dict[str, Any]:
        """Return a summary of the parser's capabilities."""
        return {
            "name": self.name,
            "has_wordwrap": self.wordwrap_config is not None,
            "has_forbidden_chars": self.forbidden_chars is not None,
            "has_tag_rules": self.tag_rules is not None,
            "has_tagged_extraction": (
                type(self).extract_tagged is not ParserScript.extract_tagged
            ),
            "has_speaker_detection": (
                type(self).detect_speakers is not ParserScript.detect_speakers
            ),
            "has_custom_wordwrap": (
                type(self).wordwrap is not ParserScript.wordwrap
            ),
            "has_custom_pretty_wrap": (
                type(self).pretty_wrap is not ParserScript.pretty_wrap
            ),
            "has_encoding_detection": (
                type(self).detect_encoding is not ParserScript.detect_encoding
            ),
        }
