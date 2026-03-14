"""RPG Maker Parser Script implementation (Phase 53 — Task 53.2).

Implements the :class:`ParserScript` interface for RPG Maker MV/MZ games.
Provides wordwrap defaults, tag rules for Show Text / Show Choices
commands, and forbidden-character definitions.

Note: The ``extract`` and ``inject`` methods delegate to the existing
:class:`RpgMakerMVHandler` / :class:`RpgMakerMZHandler` format handlers
in ``formats/rpgmaker.py`` so that backward compatibility is preserved.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from .parser_base import (
    TagRules,
    ForbiddenChars,
    ParserScript,
    WordwrapConfig,
)


__all__ = [
    "RpgMakerMVParser",
    "RpgMakerMZParser",
]

logger = logging.getLogger("cherryai.formats.parser_rpgmaker")


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

# RPG Maker MV/MZ event command codes
_CODE_SHOW_TEXT = 401       # Show Text (text line within a message)
_CODE_SHOW_TEXT_HEADER = 101  # Show Text header (face, background, position)
_CODE_SHOW_CHOICES = 102    # Show Choices header
_CODE_CHOICE_ITEM = 402     # Individual choice text
_CODE_SHOW_SCROLLING = 405  # Show Scrolling Text line
_CODE_SCRIPT = 355          # Script call (continuation)

# Context marker patterns (regex) for RPG Maker
_SCENE_PATTERN = r"^={3,}|^---\s*(?:Scene|Map)\b"
_DIALOGUE_PATTERN = r"^\\[Nn]\[[^\]]+\]"  # e.g., \N[1] face name indicator
_MENU_PATTERN = r"^\\[Cc]\[\d+\]"  # colour-coded short items
_CHOICE_PATTERN = r"^\d+[\.\)]\s"  # Numbered choice items


# ---------------------------------------------------------------------------
# RPG Maker MV parser
# ---------------------------------------------------------------------------

class RpgMakerMVParser(ParserScript):
    """Parser for RPG Maker MV game files.

    Provides wordwrap defaults (52 chars, 4 lines, ``\\n`` break) and
    context marker rules for Show Text / Show Choices detection.
    """

    @property
    def name(self) -> str:
        return "RPGMakerMV"

    def extract(self, file_path: Path) -> List[str]:
        """Extract translatable lines from an RPG Maker MV JSON file.

        Delegates to the existing format handler for backward compatibility.
        """
        from .rpgmaker import RpgMakerMVHandler
        handler = RpgMakerMVHandler()
        return handler.extract(file_path)

    def inject(self, file_path: Path, lines: List[str]) -> None:
        """Inject translated lines back into an RPG Maker MV JSON file.

        Delegates to the existing format handler for backward compatibility.
        """
        from .rpgmaker import RpgMakerMVHandler
        handler = RpgMakerMVHandler()
        handler.inject(file_path, lines)

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(
            max_line_length=52,
            max_line_number=4,
            wordwrap_command="\\n",
            new_textbox_injection="\\^",
        )

    @property
    def forbidden_chars(self) -> Optional[ForbiddenChars]:
        return ForbiddenChars(
            characters=["\t", "\r"],
            logit_bias={},
            output_action="replace",
        )

    @property
    def tag_rules(self) -> Optional[TagRules]:
        return TagRules(
            scene_pattern=_SCENE_PATTERN,
            dialogue_pattern=_DIALOGUE_PATTERN,
            menu_pattern=_MENU_PATTERN,
            choice_pattern=_CHOICE_PATTERN,
        )

    def can_handle(self, file_path: Path) -> bool:
        """Probe for RPG Maker MV structure (www/data/*.json)."""
        try:
            if file_path.suffix.lower() != ".json":
                return False
            # RPG Maker MV puts data in a www/data folder
            parts = [p.lower() for p in file_path.parts]
            if "www" in parts and "data" in parts:
                return True
            # Also accept if the JSON has RPG Maker structure
            if file_path.exists() and file_path.stat().st_size < 50_000_000:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # RPG Maker data files are arrays with null first element
                if isinstance(data, list) and len(data) > 1 and data[0] is None:
                    return True
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------
# RPG Maker MZ parser
# ---------------------------------------------------------------------------

class RpgMakerMZParser(ParserScript):
    """Parser for RPG Maker MZ game files.

    Very similar to MV with slightly different wordwrap defaults.
    """

    @property
    def name(self) -> str:
        return "RPGMakerMZ"

    def extract(self, file_path: Path) -> List[str]:
        """Extract translatable lines from an RPG Maker MZ JSON file."""
        from .rpgmaker import RpgMakerMZHandler
        handler = RpgMakerMZHandler()
        return handler.extract(file_path)

    def inject(self, file_path: Path, lines: List[str]) -> None:
        """Inject translated lines back into an RPG Maker MZ JSON file."""
        from .rpgmaker import RpgMakerMZHandler
        handler = RpgMakerMZHandler()
        handler.inject(file_path, lines)

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(
            max_line_length=56,
            max_line_number=4,
            wordwrap_command="\\n",
            new_textbox_injection="\\^",
        )

    @property
    def forbidden_chars(self) -> Optional[ForbiddenChars]:
        return ForbiddenChars(
            characters=["\t", "\r"],
            logit_bias={},
            output_action="replace",
        )

    @property
    def tag_rules(self) -> Optional[TagRules]:
        return TagRules(
            scene_pattern=_SCENE_PATTERN,
            dialogue_pattern=_DIALOGUE_PATTERN,
            menu_pattern=_MENU_PATTERN,
            choice_pattern=_CHOICE_PATTERN,
        )

    def can_handle(self, file_path: Path) -> bool:
        """Probe for RPG Maker MZ structure (data/*.json without www)."""
        try:
            if file_path.suffix.lower() != ".json":
                return False
            parts = [p.lower() for p in file_path.parts]
            # MZ uses data/ directly (no www/ parent)
            if "data" in parts and "www" not in parts:
                if file_path.exists() and file_path.stat().st_size < 50_000_000:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and len(data) > 1 and data[0] is None:
                        return True
        except Exception:
            pass
        return False
