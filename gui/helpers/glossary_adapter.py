"""Glossary and project configuration adapter for GUI integration.

This module bridges the GUI information step (gui/steps/information.py) with the
core glossary and configuration functions in:
- functions/glossary.py - Glossary management
- functions/project_config.py - Per-project configuration
- functions/style_presets.py - Style preset management

Purpose:
- Provides clean function signatures for GUI use
- Wraps core functions with fallback implementations
- Aggregates results in GUI-friendly format

TASK 16.7: Integrates glossary modules with GUI Step 3 (Information)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------- Imports from functions/glossary.py ---------------- #

_read_unified_glossary_fn = None
_write_unified_glossary_fn = None
_update_unified_glossary_fn = None
_GlossaryEntry = None
_UNIFIED_HEADER = None

try:
    from CherryAI.functions.glossary import (
        read_unified_glossary,
        write_unified_glossary,
        update_unified_glossary,
        GlossaryEntry,
        UNIFIED_HEADER,
        TYPE_NAME,
        TYPE_LOCATION,
        TYPE_TERM,
        TYPE_CODE,
        GENDER_MALE,
        GENDER_FEMALE,
        GENDER_NEUTRAL,
        GENDER_NONBINARY,
        GENDER_TRANSWOMAN,
        GENDER_TRANSMAN,
        GENDER_UNKNOWN,
    )
    _read_unified_glossary_fn = read_unified_glossary
    _write_unified_glossary_fn = write_unified_glossary
    _update_unified_glossary_fn = update_unified_glossary
    _GlossaryEntry = GlossaryEntry
    _UNIFIED_HEADER = UNIFIED_HEADER
except ImportError:
    try:
        from CherryAI.functions.glossary import (
            read_unified_glossary,
            write_unified_glossary,
            update_unified_glossary,
            GlossaryEntry,
            UNIFIED_HEADER,
            TYPE_NAME,
            TYPE_LOCATION,
            TYPE_TERM,
            TYPE_CODE,
            GENDER_MALE,
            GENDER_FEMALE,
            GENDER_NEUTRAL,
            GENDER_NONBINARY,
            GENDER_TRANSWOMAN,
            GENDER_TRANSMAN,
            GENDER_UNKNOWN,
        )
        _read_unified_glossary_fn = read_unified_glossary
        _write_unified_glossary_fn = write_unified_glossary
        _update_unified_glossary_fn = update_unified_glossary
        _GlossaryEntry = GlossaryEntry
        _UNIFIED_HEADER = UNIFIED_HEADER
    except ImportError:
        logger.debug("Could not import functions.glossary")
        # Define fallback constants
        TYPE_NAME = "Name"
        TYPE_LOCATION = "Location"
        TYPE_TERM = "Term"
        TYPE_CODE = "Code"
        GENDER_MALE = "Male"
        GENDER_FEMALE = "Female"
        GENDER_NEUTRAL = "Neutral"
        GENDER_NONBINARY = "Non-Binary"
        GENDER_TRANSWOMAN = "Transwoman"
        GENDER_TRANSMAN = "Transman"
        GENDER_UNKNOWN = "Unknown"

# ---------------- Imports from functions/project_config.py ---------------- #

_ProjectConfig = None

try:
    from CherryAI.functions.project_config import ProjectConfig, MAX_SUMMARY_CHARS
    _ProjectConfig = ProjectConfig
except ImportError:
    try:
        from CherryAI.functions.project_config import ProjectConfig, MAX_SUMMARY_CHARS
        _ProjectConfig = ProjectConfig
    except ImportError:
        logger.debug("Could not import functions.project_config")
        MAX_SUMMARY_CHARS = 2000

# ---------------- Imports from functions/style_presets.py ---------------- #

_get_style_preset_fn = None
_list_style_presets_fn = None
_list_presets_by_category_fn = None
_StylePreset = None
_StylePresetManager = None
_BUILTIN_PRESETS = None

try:
    from CherryAI.functions.style_presets import (
        get_style_preset,
        list_style_presets,
        list_presets_by_category,
        StylePreset as CoreStylePreset,
        StylePresetManager,
        StyleCategory,
        Formality,
        HonorificHandling,
        BUILTIN_PRESETS,
    )
    _get_style_preset_fn = get_style_preset
    _list_style_presets_fn = list_style_presets
    _list_presets_by_category_fn = list_presets_by_category
    _StylePreset = CoreStylePreset
    _StylePresetManager = StylePresetManager
    _BUILTIN_PRESETS = BUILTIN_PRESETS
except ImportError:
    try:
        from CherryAI.functions.style_presets import (
            get_style_preset,
            list_style_presets,
            list_presets_by_category,
            StylePreset as CoreStylePreset,
            StylePresetManager,
            StyleCategory,
            Formality,
            HonorificHandling,
            BUILTIN_PRESETS,
        )
        _get_style_preset_fn = get_style_preset
        _list_style_presets_fn = list_style_presets
        _list_presets_by_category_fn = list_presets_by_category
        _StylePreset = CoreStylePreset
        _StylePresetManager = StylePresetManager
        _BUILTIN_PRESETS = BUILTIN_PRESETS
    except ImportError:
        logger.debug("Could not import functions.style_presets")


# ---------------- Glossary Entry Wrapper ---------------- #

@dataclass
class GlossaryEntryView:
    """GUI-friendly glossary entry representation.
    
    Wraps the core GlossaryEntry with additional fields for display.
    """
    original: str
    translation: str = ""
    notes: str = ""
    source: str = ""
    entry_type: str = ""
    gender: str = ""
    refers_to_themself_as: str = ""
    referred_to_as: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for display."""
        return {
            "original": self.original,
            "translation": self.translation,
            "notes": self.notes,
            "source": self.source,
            "type": self.entry_type,
            "gender": self.gender,
            "refers_to_themself_as": self.refers_to_themself_as,
            "referred_to_as": self.referred_to_as,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "GlossaryEntryView":
        """Create from dictionary."""
        return cls(
            original=data.get("original", ""),
            translation=data.get("translation", ""),
            notes=data.get("notes", ""),
            source=data.get("source", ""),
            entry_type=data.get("type", data.get("entry_type", "")),
            gender=data.get("gender", ""),
            refers_to_themself_as=data.get("refers_to_themself_as", ""),
            referred_to_as=data.get("referred_to_as", ""),
        )


# ---------------- Style Preset Wrapper ---------------- #

@dataclass
class StylePresetView:
    """GUI-friendly style preset representation.
    
    Simplified view of the core StylePreset for dropdown display.
    """
    name: str
    display_name: str
    description: str
    category: str
    formality: str = "neutral"
    honorifics: str = "localize"
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "formality": self.formality,
            "honorifics": self.honorifics,
        }


# ---------------- Glossary Functions ---------------- #

def load_glossary() -> Dict[str, GlossaryEntryView]:
    """Load unified glossary entries.
    
    Returns:
        Dict mapping original text to GlossaryEntryView.
    """
    if _read_unified_glossary_fn is None:
        logger.warning("Glossary functions not available")
        return {}
    
    try:
        entries = _read_unified_glossary_fn()
        result: Dict[str, GlossaryEntryView] = {}
        for key, entry in entries.items():
            result[key] = GlossaryEntryView(
                original=entry.original,
                translation=entry.translation,
                notes=entry.notes,
                source=entry.source,
                entry_type=entry.entry_type,
                gender=entry.gender,
                refers_to_themself_as=entry.refers_to_themself_as,
                referred_to_as=entry.referred_to_as,
            )
        return result
    except Exception as e:
        logger.error("Failed to load glossary: %s", e)
        return {}


def save_glossary(entries: Dict[str, GlossaryEntryView]) -> bool:
    """Save glossary entries.
    
    Args:
        entries: Dict mapping original text to GlossaryEntryView.
        
    Returns:
        True if saved successfully.
    """
    if _write_unified_glossary_fn is None or _GlossaryEntry is None:
        logger.warning("Glossary functions not available")
        return False
    
    try:
        # Convert to core format
        core_entries: Dict[str, Any] = {}
        for key, view in entries.items():
            core_entries[key] = _GlossaryEntry(
                original=view.original,
                translation=view.translation,
                notes=view.notes,
                source=view.source,
                entry_type=view.entry_type,
                gender=view.gender,
                refers_to_themself_as=view.refers_to_themself_as,
                referred_to_as=view.referred_to_as,
            )
        _write_unified_glossary_fn(core_entries)
        return True
    except Exception as e:
        logger.error("Failed to save glossary: %s", e)
        return False


def add_glossary_entry(
    original: str,
    translation: str = "",
    notes: str = "",
    entry_type: str = TYPE_NAME,
    gender: str = GENDER_UNKNOWN,
    source: str = "GUI",
) -> bool:
    """Add or update a single glossary entry.
    
    Args:
        original: Original text (key).
        translation: Translation text.
        notes: Optional notes.
        entry_type: Entry type (Name, Location, Term, Code).
        gender: Gender for names.
        source: Source of the entry.
        
    Returns:
        True if added successfully.
    """
    if _update_unified_glossary_fn is None or _GlossaryEntry is None:
        logger.warning("Glossary functions not available")
        return False
    
    try:
        entry = _GlossaryEntry(
            original=original,
            translation=translation,
            notes=notes,
            source=source,
            entry_type=entry_type,
            gender=gender,
        )
        _update_unified_glossary_fn([entry])
        return True
    except Exception as e:
        logger.error("Failed to add glossary entry: %s", e)
        return False


def get_glossary_entries_by_type(
    entry_type: str,
) -> List[GlossaryEntryView]:
    """Get glossary entries filtered by type.
    
    Args:
        entry_type: Entry type to filter by (Name, Location, Term, Code).
        
    Returns:
        List of matching entries.
    """
    entries = load_glossary()
    return [e for e in entries.values() if e.entry_type == entry_type]


def get_glossary_names() -> List[GlossaryEntryView]:
    """Get all name entries from glossary.
    
    Returns:
        List of name entries.
    """
    return get_glossary_entries_by_type(TYPE_NAME)


def get_glossary_stats() -> Dict[str, int]:
    """Get statistics about the glossary.
    
    Returns:
        Dict with counts by type.
    """
    entries = load_glossary()
    stats: Dict[str, int] = {
        "total": len(entries),
        "names": 0,
        "locations": 0,
        "terms": 0,
        "codes": 0,
        "with_translation": 0,
    }
    
    for entry in entries.values():
        if entry.entry_type == TYPE_NAME:
            stats["names"] += 1
        elif entry.entry_type == TYPE_LOCATION:
            stats["locations"] += 1
        elif entry.entry_type == TYPE_TERM:
            stats["terms"] += 1
        elif entry.entry_type == TYPE_CODE:
            stats["codes"] += 1
        if entry.translation:
            stats["with_translation"] += 1
    
    return stats


def search_glossary(query: str, limit: int = 50) -> List[GlossaryEntryView]:
    """Search glossary entries by original text.
    
    Args:
        query: Search query.
        limit: Maximum results to return.
        
    Returns:
        List of matching entries.
    """
    entries = load_glossary()
    query_lower = query.lower()
    
    results: List[GlossaryEntryView] = []
    for entry in entries.values():
        if query_lower in entry.original.lower():
            results.append(entry)
            if len(results) >= limit:
                break
        elif query_lower in entry.translation.lower():
            results.append(entry)
            if len(results) >= limit:
                break
    
    return results


# ---------------- Style Preset Functions ---------------- #

def get_style_presets() -> List[StylePresetView]:
    """Get all available style presets.
    
    Returns:
        List of StylePresetView objects.
    """
    if _list_style_presets_fn is None or _BUILTIN_PRESETS is None:
        # Fallback: return basic presets
        return [
            StylePresetView(
                name="natural",
                display_name="Natural",
                description="Fluent translation adapted to target language",
                category="time_period",
                formality="neutral",
            ),
            StylePresetView(
                name="literal",
                display_name="Literal",
                description="Word-for-word translation",
                category="time_period",
                formality="neutral",
            ),
            StylePresetView(
                name="casual",
                display_name="Casual",
                description="Informal, conversational language",
                category="time_period",
                formality="casual",
            ),
            StylePresetView(
                name="formal",
                display_name="Formal",
                description="Professional, formal language",
                category="time_period",
                formality="formal",
            ),
        ]
    
    try:
        result: List[StylePresetView] = []
        for name in _list_style_presets_fn():
            preset = _BUILTIN_PRESETS.get(name)
            if preset:
                result.append(StylePresetView(
                    name=preset.name,
                    display_name=preset.display_name,
                    description=preset.description,
                    category=preset.category.value,
                    formality=preset.formality.value,
                    honorifics=preset.honorifics.value,
                ))
        return result
    except Exception as e:
        logger.error("Failed to get style presets: %s", e)
        return []


def get_style_preset_names() -> List[str]:
    """Get list of style preset names for dropdown.
    
    Returns:
        List of preset names.
    """
    if _list_style_presets_fn is None:
        return ["natural", "literal", "casual", "formal"]
    
    try:
        return _list_style_presets_fn()
    except Exception as e:
        logger.error("Failed to get preset names: %s", e)
        return ["natural"]


def get_style_preset_by_name(name: str) -> Optional[StylePresetView]:
    """Get a specific style preset by name.
    
    Args:
        name: Preset name.
        
    Returns:
        StylePresetView or None if not found.
    """
    if _get_style_preset_fn is None:
        return None
    
    try:
        preset = _get_style_preset_fn(name)
        if preset:
            return StylePresetView(
                name=preset.name,
                display_name=preset.display_name,
                description=preset.description,
                category=preset.category.value,
                formality=preset.formality.value,
                honorifics=preset.honorifics.value,
            )
        return None
    except Exception as e:
        logger.error("Failed to get preset %s: %s", name, e)
        return None


def get_style_preset_prompt(name: str) -> str:
    """Get the prompt text for a style preset.
    
    Args:
        name: Preset name.
        
    Returns:
        Formatted prompt text or empty string.
    """
    if _get_style_preset_fn is None:
        return ""
    
    try:
        preset = _get_style_preset_fn(name)
        if preset:
            return preset.to_prompt_text()
        return ""
    except Exception as e:
        logger.error("Failed to get prompt for preset %s: %s", name, e)
        return ""


def get_presets_by_category() -> Dict[str, List[StylePresetView]]:
    """Get style presets organized by category.
    
    Returns:
        Dict mapping category name to list of presets.
    """
    if _list_presets_by_category_fn is None or _BUILTIN_PRESETS is None:
        return {"General": get_style_presets()}
    
    try:
        result: Dict[str, List[StylePresetView]] = {}
        category_names = _list_presets_by_category_fn()
        
        for category, preset_names in category_names.items():
            presets: List[StylePresetView] = []
            for name in preset_names:
                preset = _BUILTIN_PRESETS.get(name)
                if preset:
                    presets.append(StylePresetView(
                        name=preset.name,
                        display_name=preset.display_name,
                        description=preset.description,
                        category=preset.category.value,
                        formality=preset.formality.value,
                        honorifics=preset.honorifics.value,
                    ))
            if presets:
                # Capitalize category name for display
                display_category = category.replace("_", " ").title()
                result[display_category] = presets
        
        return result
    except Exception as e:
        logger.error("Failed to get presets by category: %s", e)
        return {}


# ---------------- Project Config Functions ---------------- #

def create_project_config(
    name: str = "",
    summary_file: str = "config/game_summary.txt",
    genre: str = "",
    tone: str = "",
    style_notes: str = "",
    source_lang: str = "",
    target_lang: str = "",
) -> Dict[str, Any]:
    """Create a project configuration dictionary.
    
    Args:
        name: Project name.
        summary_file: Path to summary file.
        genre: Game genre.
        tone: Writing tone.
        style_notes: Additional style instructions.
        source_lang: Source language.
        target_lang: Target language.
        
    Returns:
        Project config dictionary.
    """
    if _ProjectConfig is not None:
        config = _ProjectConfig(
            name=name,
            summary_file=summary_file,
            genre=genre,
            tone=tone,
            style_notes=style_notes,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        return config.to_dict()
    
    # Fallback if core module not available
    return {
        "name": name,
        "summary_file": summary_file,
        "genre": genre,
        "tone": tone,
        "style_notes": style_notes,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }


def load_project_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Load and validate project configuration.
    
    Args:
        data: Raw config dictionary (from manifest).
        
    Returns:
        Validated project config dictionary.
    """
    if _ProjectConfig is not None:
        try:
            config = _ProjectConfig.from_dict(data)
            return config.to_dict()
        except Exception as e:
            logger.error("Failed to load project config: %s", e)
    
    # Fallback: return data with defaults
    defaults = create_project_config()
    defaults.update(data)
    return defaults


def get_project_api_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get API override settings from project config.
    
    Args:
        config: Project config dictionary.
        
    Returns:
        Dict of API overrides (model, temperature, etc.)
    """
    if _ProjectConfig is not None:
        try:
            pc = _ProjectConfig.from_dict(config)
            return pc.get_api_overrides()
        except Exception as e:
            logger.error("Failed to get API overrides: %s", e)
    
    # Fallback: extract relevant fields manually
    overrides: Dict[str, Any] = {}
    if config.get("model"):
        overrides["model"] = config["model"]
    if config.get("temperature", -1) >= 0:
        overrides["temperature"] = config["temperature"]
    if config.get("chunk_size", 0) > 0:
        overrides["chunk_size"] = config["chunk_size"]
    return overrides


# ---------------- Character/Name Integration ---------------- #

def get_characters_from_glossary() -> List[Dict[str, str]]:
    """Get character entries from glossary.
    
    Returns:
        List of character dictionaries with name, gender, etc.
    """
    names = get_glossary_names()
    characters: List[Dict[str, str]] = []
    
    for entry in names:
        characters.append({
            "name": entry.translation or entry.original,
            "original_name": entry.original,
            "gender": entry.gender,
            "role": entry.notes,
            "speaking_style": entry.refers_to_themself_as,
            "referred_to_as": entry.referred_to_as,
        })
    
    return characters


def sync_characters_to_glossary(
    characters: List[Dict[str, str]],
    source: str = "GUI",
) -> int:
    """Sync character list to glossary.
    
    Args:
        characters: List of character dictionaries.
        source: Source identifier.
        
    Returns:
        Number of entries updated.
    """
    count = 0
    for char in characters:
        original = char.get("original_name", "")
        if not original:
            original = char.get("name", "")
        if not original:
            continue
        
        success = add_glossary_entry(
            original=original,
            translation=char.get("name", ""),
            notes=char.get("role", ""),
            entry_type=TYPE_NAME,
            gender=char.get("gender", GENDER_UNKNOWN),
            source=source,
        )
        if success:
            count += 1
    
    return count


# ---------------- Public API ---------------- #

__all__ = [
    # Data classes
    "GlossaryEntryView",
    "StylePresetView",
    # Constants
    "TYPE_NAME",
    "TYPE_LOCATION",
    "TYPE_TERM",
    "TYPE_CODE",
    "GENDER_MALE",
    "GENDER_FEMALE",
    "GENDER_NEUTRAL",
    "GENDER_UNKNOWN",
    "MAX_SUMMARY_CHARS",
    # Glossary functions
    "load_glossary",
    "save_glossary",
    "add_glossary_entry",
    "get_glossary_entries_by_type",
    "get_glossary_names",
    "get_glossary_stats",
    "search_glossary",
    # Style preset functions
    "get_style_presets",
    "get_style_preset_names",
    "get_style_preset_by_name",
    "get_style_preset_prompt",
    "get_presets_by_category",
    # Project config functions
    "create_project_config",
    "load_project_config",
    "get_project_api_overrides",
    # Character functions
    "get_characters_from_glossary",
    "sync_characters_to_glossary",
]
