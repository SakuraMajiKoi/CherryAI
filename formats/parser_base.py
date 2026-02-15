"""Parser Script base interface for CherryAI (Phase 53).

Parser Scripts are game-engine-specific or format-specific scripts that
handle extraction, injection, and optionally provide wordwrap settings,
forbidden characters, and context marker rules.

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

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


__all__ = [
    "ParserScript",
    "WordwrapConfig",
    "ForbiddenChars",
    "ContextMarkerRules",
]


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
class ContextMarkerRules:
    """Engine-specific patterns for detecting context markers.

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
    def from_dict(cls, data: Dict[str, Any]) -> "ContextMarkerRules":
        """Deserialise from dictionary."""
        return cls(
            scene_pattern=str(data.get("scene_pattern", "")),
            dialogue_pattern=str(data.get("dialogue_pattern", "")),
            menu_pattern=str(data.get("menu_pattern", "")),
            choice_pattern=str(data.get("choice_pattern", "")),
        )


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
    - :attr:`context_marker_rules`: patterns for context detection.
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
    def context_marker_rules(self) -> Optional[ContextMarkerRules]:
        """Context marker detection patterns, or ``None``."""
        return None

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
    # Convenience
    # ------------------------------------------------------------------

    def info(self) -> Dict[str, Any]:
        """Return a summary of the parser's capabilities."""
        return {
            "name": self.name,
            "has_wordwrap": self.wordwrap_config is not None,
            "has_forbidden_chars": self.forbidden_chars is not None,
            "has_context_markers": self.context_marker_rules is not None,
        }
