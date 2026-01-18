"""Preset management for text fields (TASK 30.1).

This module provides save/load/delete operations for named presets.
Presets are stored in JSON files under user/presets/ folder.

Supported preset types:
- style_presets.json - Style presets (translation style)
- tone_presets.json - Tone presets (writing tone)
- prompt_presets.json - Prompt presets (system prompts)

Each preset is stored as:
{
    "name": "My Preset",
    "content": "The actual text content..."
}
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)

# Preset folder location
PRESETS_DIR = Path("user/presets")


@dataclass
class Preset:
    """A single preset entry.

    Attributes:
        name: The display name of the preset
        content: The text content of the preset
    """

    name: str
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Preset:
        """Create from dictionary.

        Args:
            data: Dictionary with 'name' and 'content' keys

        Returns:
            Preset instance
        """
        return cls(
            name=data.get("name", ""),
            content=data.get("content", ""),
        )


@dataclass
class PresetFile:
    """Collection of presets stored in a file.

    Attributes:
        presets: List of Preset objects
    """

    presets: list[Preset] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "presets": [p.to_dict() for p in self.presets],
        }

    @classmethod
    def from_dict(cls, data: dict) -> PresetFile:
        """Create from dictionary.

        Args:
            data: Dictionary with 'presets' key

        Returns:
            PresetFile instance
        """
        presets_data = data.get("presets", [])
        presets = [Preset.from_dict(p) for p in presets_data]
        return cls(presets=presets)

    def get_preset(self, name: str) -> Preset | None:
        """Get a preset by name.

        Args:
            name: The preset name to find

        Returns:
            Preset if found, None otherwise
        """
        for preset in self.presets:
            if preset.name == name:
                return preset
        return None

    def add_preset(self, preset: Preset) -> bool:
        """Add or update a preset.

        If a preset with the same name exists, it is updated.
        Otherwise, a new preset is added.

        Args:
            preset: The preset to add or update

        Returns:
            True if preset was added (new), False if updated (existing)
        """
        for i, existing in enumerate(self.presets):
            if existing.name == preset.name:
                self.presets[i] = preset
                return False
        self.presets.append(preset)
        return True

    def delete_preset(self, name: str) -> bool:
        """Delete a preset by name.

        Args:
            name: The preset name to delete

        Returns:
            True if deleted, False if not found
        """
        for i, preset in enumerate(self.presets):
            if preset.name == name:
                del self.presets[i]
                return True
        return False

    def get_names(self) -> list[str]:
        """Get list of all preset names.

        Returns:
            List of preset names in order
        """
        return [p.name for p in self.presets]


class PresetManager:
    """Manager for preset save/load/delete operations (TASK 30.1).

    This class provides a singleton interface for managing presets.
    Presets are stored in JSON files under user/presets/ folder.

    Supported preset types:
    - style - Style presets for translation style
    - tone - Tone presets for writing tone
    - prompt - Prompt presets for system prompts

    Usage:
        manager = PresetManager.get_instance()
        manager.save_preset("style", "My Style", "Natural, flowing translation")
        content = manager.load_preset("style", "My Style")
        manager.delete_preset("style", "My Style")
    """

    _instance: ClassVar[PresetManager | None] = None

    # Preset type to file mapping
    PRESET_FILES: ClassVar[dict[str, str]] = {
        "style": "style_presets.json",
        "tone": "tone_presets.json",
        "prompt": "prompt_presets.json",
    }

    def __init__(self) -> None:
        """Initialize the preset manager."""
        self._presets_dir = PRESETS_DIR
        self._cache: dict[str, PresetFile] = {}
        self._ensure_presets_dir()

    @classmethod
    def get_instance(cls) -> PresetManager:
        """Get or create the singleton instance.

        Returns:
            The singleton PresetManager instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    def _ensure_presets_dir(self) -> None:
        """Ensure the presets directory exists."""
        self._presets_dir.mkdir(parents=True, exist_ok=True)

    def _get_preset_path(self, preset_type: str) -> Path:
        """Get the file path for a preset type.

        Args:
            preset_type: The preset type (style, tone, prompt)

        Returns:
            Path to the preset file

        Raises:
            ValueError: If preset type is not supported
        """
        if preset_type not in self.PRESET_FILES:
            raise ValueError(
                f"Unknown preset type: {preset_type}. "
                f"Supported types: {list(self.PRESET_FILES.keys())}"
            )
        return self._presets_dir / self.PRESET_FILES[preset_type]

    def _load_preset_file(self, preset_type: str) -> PresetFile:
        """Load presets from file.

        Args:
            preset_type: The preset type to load

        Returns:
            PresetFile with loaded presets (empty if file not found)
        """
        # Check cache first
        if preset_type in self._cache:
            return self._cache[preset_type]

        path = self._get_preset_path(preset_type)
        if not path.exists():
            # Return default presets for each type
            preset_file = self._get_default_presets(preset_type)
            self._cache[preset_type] = preset_file
            return preset_file

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            preset_file = PresetFile.from_dict(data)
            self._cache[preset_type] = preset_file
            return preset_file
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load preset file %s: %s", path, e)
            preset_file = self._get_default_presets(preset_type)
            self._cache[preset_type] = preset_file
            return preset_file

    def _save_preset_file(self, preset_type: str, preset_file: PresetFile) -> bool:
        """Save presets to file.

        Args:
            preset_type: The preset type to save
            preset_file: The PresetFile to save

        Returns:
            True if saved successfully, False otherwise
        """
        path = self._get_preset_path(preset_type)
        try:
            self._ensure_presets_dir()
            with path.open("w", encoding="utf-8") as f:
                json.dump(preset_file.to_dict(), f, indent=2, ensure_ascii=False)
            self._cache[preset_type] = preset_file
            logger.debug("Saved preset file: %s", path)
            return True
        except OSError as e:
            logger.warning("Failed to save preset file %s: %s", path, e)
            return False

    def _get_default_presets(self, preset_type: str) -> PresetFile:
        """Get default presets for a preset type.

        Args:
            preset_type: The preset type

        Returns:
            PresetFile with default presets
        """
        defaults: dict[str, list[Preset]] = {
            "style": [
                Preset("Natural", "Natural, flowing translation"),
                Preset("Literal", "Literal, word-for-word translation"),
                Preset("Localizing", "Localized adaptation for target audience"),
                Preset("Formal", "Formal, academic translation style"),
                Preset("Casual", "Casual, conversational translation"),
            ],
            "tone": [
                Preset("Neutral", "Neutral, balanced tone"),
                Preset("Casual", "Casual, friendly tone"),
                Preset("Formal", "Formal, professional tone"),
                Preset("Dramatic", "Dramatic, expressive tone"),
                Preset("Comedic", "Light, humorous tone"),
            ],
            "prompt": [
                Preset(
                    "Default",
                    "Translate the following text accurately while preserving "
                    "the original meaning and nuance.",
                ),
            ],
        }
        presets = defaults.get(preset_type, [])
        return PresetFile(presets=presets)

    def get_presets(self, preset_type: str) -> list[Preset]:
        """Get all presets of a given type.

        Args:
            preset_type: The preset type (style, tone, prompt)

        Returns:
            List of Preset objects
        """
        preset_file = self._load_preset_file(preset_type)
        return list(preset_file.presets)

    def get_preset_names(self, preset_type: str) -> list[str]:
        """Get all preset names of a given type.

        Args:
            preset_type: The preset type (style, tone, prompt)

        Returns:
            List of preset names
        """
        preset_file = self._load_preset_file(preset_type)
        return preset_file.get_names()

    def load_preset(self, preset_type: str, name: str) -> str | None:
        """Load content of a preset by name.

        Args:
            preset_type: The preset type (style, tone, prompt)
            name: The preset name to load

        Returns:
            The preset content, or None if not found
        """
        preset_file = self._load_preset_file(preset_type)
        preset = preset_file.get_preset(name)
        if preset:
            logger.debug("Loaded preset '%s' from %s", name, preset_type)
            return preset.content
        logger.debug("Preset '%s' not found in %s", name, preset_type)
        return None

    def save_preset(self, preset_type: str, name: str, content: str) -> bool:
        """Save a preset.

        If a preset with the same name exists, it is updated.
        Otherwise, a new preset is created.

        Escape handling: Use \\ before " and only remove \\ before " when loading.

        Args:
            preset_type: The preset type (style, tone, prompt)
            name: The preset name
            content: The preset content

        Returns:
            True if saved successfully, False otherwise
        """
        if not name or not name.strip():
            logger.warning("Cannot save preset with empty name")
            return False

        preset_file = self._load_preset_file(preset_type)
        preset = Preset(name=name.strip(), content=content)
        is_new = preset_file.add_preset(preset)

        if self._save_preset_file(preset_type, preset_file):
            action = "Created new" if is_new else "Updated"
            logger.debug("%s preset '%s' in %s", action, name, preset_type)
            return True
        return False

    def delete_preset(self, preset_type: str, name: str) -> bool:
        """Delete a preset by name.

        Args:
            preset_type: The preset type (style, tone, prompt)
            name: The preset name to delete

        Returns:
            True if deleted successfully, False if not found or failed
        """
        preset_file = self._load_preset_file(preset_type)
        if not preset_file.delete_preset(name):
            logger.debug("Preset '%s' not found in %s for deletion", name, preset_type)
            return False

        if self._save_preset_file(preset_type, preset_file):
            logger.debug("Deleted preset '%s' from %s", name, preset_type)
            return True
        return False

    def preset_exists(self, preset_type: str, name: str) -> bool:
        """Check if a preset exists.

        Args:
            preset_type: The preset type (style, tone, prompt)
            name: The preset name to check

        Returns:
            True if preset exists, False otherwise
        """
        preset_file = self._load_preset_file(preset_type)
        return preset_file.get_preset(name) is not None

    def clear_cache(self) -> None:
        """Clear the preset cache (for testing)."""
        self._cache.clear()

    def set_presets_dir(self, path: Path) -> None:
        """Set the presets directory (for testing).

        Args:
            path: The new presets directory path
        """
        self._presets_dir = path
        self._cache.clear()
        self._ensure_presets_dir()
