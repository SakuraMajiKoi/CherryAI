"""Project configuration management for CherryAI.

Handles project-specific settings that can be stored in:
1. Global config (CherryAI.ini [project] section) - defaults for new projects
2. Manifest (project_config field) - per-project overrides
3. Dedicated API profiles (api_profiles.ini) - multiple API configurations

This module centralizes project settings to enable:
- Game summary injection into translation prompts
- Per-project translation styles and preferences
- Multiple API configurations for different purposes (glossary vs translation)
- Manifest-stored settings that travel with the project
"""

from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# Maximum characters for game summary to prevent context overflow
MAX_SUMMARY_CHARS = 2000

# Default project configuration
DEFAULT_PROJECT_CONFIG: Dict[str, Any] = {
    "name": "",
    "summary_file": "",
    "genre": "",
    "tone": "",
    "style_notes": "",
    "source_lang": "",  # Empty = use global
    "target_lang": "",  # Empty = use global
}

# Default API profile configuration
DEFAULT_API_PROFILE: Dict[str, Any] = {
    "provider": "openai",
    "api_key": "",
    "base_url": "",
    "model": "gpt-4o-mini",
    "temperature": 0.3,
    "timeout": 60,
    "retries": 3,
    "rate_limit_requests": 60,
    "chunk_size": 50,
}


@dataclass
class ProjectConfig:
    """Project-level configuration that can be stored in manifest.
    
    Attributes:
        name: Project/game name
        summary_file: Path to game summary file (relative to config dir)
        genre: Game genre (fantasy, sci-fi, romance, etc.)
        tone: Writing tone (comedic, dramatic, dark, etc.)
        style_notes: Additional translation style instructions
        source_lang: Source language (empty = use global)
        target_lang: Target language (empty = use global)
        api_profile: Name of API profile to use for translation
        glossary_api_profile: Name of API profile to use for glossary enrichment
        custom_settings: Dict for additional per-project settings
        
        # Extended fields for Session 16
        chunk_size: Lines per batch (0 = use global)
        temperature: LLM generation temperature (-1 = use global)
        model: Model name override (empty = use global)
        preset: Preset name override (empty = use global)
        glossary_enabled: Whether to use glossary in prompts
        game_summary_enabled: Whether to include game summary
        translation_style_enabled: Whether to include translation style guide
        dedup_enabled: Whether to enable deduplication
        thinking_enabled: Whether to enable thinking mode
        thinking_budget: Token budget for thinking mode
        speaker_format: Speaker format (empty = auto-detect)
        preserve_codes: Whether to preserve code markers
        max_retries: Maximum retry attempts (0 = use global)
    """
    name: str = ""
    summary_file: str = ""
    genre: str = ""
    tone: str = ""
    style_notes: str = ""
    source_lang: str = ""
    target_lang: str = ""
    api_profile: str = "default"
    glossary_api_profile: str = ""  # Empty = use same as translation
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Extended fields for Session 16
    chunk_size: int = 0  # 0 = use global
    temperature: float = -1.0  # -1 = use global
    model: str = ""
    preset: str = ""
    glossary_enabled: bool = True
    game_summary_enabled: bool = True
    translation_style_enabled: bool = True
    dedup_enabled: bool = True
    thinking_enabled: bool = False
    thinking_budget: int = 10000
    speaker_format: str = ""
    preserve_codes: bool = True
    max_retries: int = 0  # 0 = use global
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for manifest storage."""
        return {
            "name": self.name,
            "summary_file": self.summary_file,
            "genre": self.genre,
            "tone": self.tone,
            "style_notes": self.style_notes,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "api_profile": self.api_profile,
            "glossary_api_profile": self.glossary_api_profile,
            "custom_settings": self.custom_settings,
            # Extended fields
            "chunk_size": self.chunk_size,
            "temperature": self.temperature,
            "model": self.model,
            "preset": self.preset,
            "glossary_enabled": self.glossary_enabled,
            "game_summary_enabled": self.game_summary_enabled,
            "translation_style_enabled": self.translation_style_enabled,
            "dedup_enabled": self.dedup_enabled,
            "thinking_enabled": self.thinking_enabled,
            "thinking_budget": self.thinking_budget,
            "speaker_format": self.speaker_format,
            "preserve_codes": self.preserve_codes,
            "max_retries": self.max_retries,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        """Create from dictionary (e.g., from manifest)."""
        # Handle boolean conversion for string values
        def parse_bool(value, default: bool = True) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return default
        
        return cls(
            name=data.get("name", ""),
            summary_file=data.get("summary_file", ""),
            genre=data.get("genre", ""),
            tone=data.get("tone", ""),
            style_notes=data.get("style_notes", ""),
            source_lang=data.get("source_lang", ""),
            target_lang=data.get("target_lang", ""),
            api_profile=data.get("api_profile", "default"),
            glossary_api_profile=data.get("glossary_api_profile", ""),
            custom_settings=data.get("custom_settings", {}),
            # Extended fields
            chunk_size=int(data.get("chunk_size", 0)),
            temperature=float(data.get("temperature", -1.0)),
            model=data.get("model", ""),
            preset=data.get("preset", ""),
            glossary_enabled=parse_bool(data.get("glossary_enabled", True)),
            game_summary_enabled=parse_bool(data.get("game_summary_enabled", True)),
            translation_style_enabled=parse_bool(data.get("translation_style_enabled", True)),
            dedup_enabled=parse_bool(data.get("dedup_enabled", True)),
            thinking_enabled=parse_bool(data.get("thinking_enabled", False), False),
            thinking_budget=int(data.get("thinking_budget", 10000)),
            speaker_format=data.get("speaker_format", ""),
            preserve_codes=parse_bool(data.get("preserve_codes", True)),
            max_retries=int(data.get("max_retries", 0)),
        )
    
    def get_api_overrides(self) -> Dict[str, Any]:
        """Get settings suitable for API client override.
        
        Returns only settings that should override API configuration.
        Non-default values are included.
        
        Returns:
            Dictionary of API override settings.
        """
        overrides: Dict[str, Any] = {}
        
        if self.model:
            overrides["model"] = self.model
        if self.preset:
            overrides["preset"] = self.preset
        if self.temperature >= 0:  # -1 means use global
            overrides["temperature"] = self.temperature
        if self.chunk_size > 0:  # 0 means use global
            overrides["chunk_size"] = self.chunk_size
        if self.thinking_enabled:
            overrides["thinking_enabled"] = True
            overrides["thinking_budget"] = self.thinking_budget
        if self.max_retries > 0:  # 0 means use global
            overrides["retries"] = self.max_retries
        
        return overrides
    
    def merge_with(self, other: "ProjectConfig") -> "ProjectConfig":
        """Merge this config with another, preferring other's non-default values.
        
        Args:
            other: Config to merge with.
            
        Returns:
            New merged config.
        """
        # Start with self's values
        result = ProjectConfig.from_dict(self.to_dict())
        
        # Override with other's non-default/non-empty values
        if other.name:
            result.name = other.name
        if other.summary_file:
            result.summary_file = other.summary_file
        if other.genre:
            result.genre = other.genre
        if other.tone:
            result.tone = other.tone
        if other.style_notes:
            result.style_notes = other.style_notes
        if other.source_lang:
            result.source_lang = other.source_lang
        if other.target_lang:
            result.target_lang = other.target_lang
        if other.api_profile != "default":
            result.api_profile = other.api_profile
        if other.glossary_api_profile:
            result.glossary_api_profile = other.glossary_api_profile
        if other.custom_settings:
            result.custom_settings.update(other.custom_settings)
        # Extended fields
        if other.chunk_size > 0:
            result.chunk_size = other.chunk_size
        if other.temperature >= 0:
            result.temperature = other.temperature
        if other.model:
            result.model = other.model
        if other.preset:
            result.preset = other.preset
        if not other.glossary_enabled:
            result.glossary_enabled = False
        if not other.game_summary_enabled:
            result.game_summary_enabled = False
        if not other.translation_style_enabled:
            result.translation_style_enabled = False
        if not other.dedup_enabled:
            result.dedup_enabled = False
        if other.thinking_enabled:
            result.thinking_enabled = True
            result.thinking_budget = other.thinking_budget
        if other.speaker_format:
            result.speaker_format = other.speaker_format
        if not other.preserve_codes:
            result.preserve_codes = False
        if other.max_retries > 0:
            result.max_retries = other.max_retries
        
        return result


@dataclass
class APIProfile:
    """API configuration profile for translation or glossary enrichment.

    Multiple profiles can be stored in api_profiles.ini to allow:
    - Different models for different purposes (fast/cheap for glossary, powerful for translation)
    - Different API keys for different providers
    - Separate rate limits per purpose

    TASK 17.3: Added display_name for human-readable labelling and
    system_prompt_tweak for per-profile prompt adjustments.
    """

    name: str
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    timeout: int = 60
    retries: int = 3
    rate_limit_requests: int = 60
    chunk_size: int = 50
    display_name: str = ""
    system_prompt_tweak: str = ""

    @property
    def label(self) -> str:
        """Human-readable label (display_name if set, otherwise name)."""
        return self.display_name or self.name

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for INI storage."""
        return {
            "provider": self.provider,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": str(self.temperature),
            "timeout": str(self.timeout),
            "retries": str(self.retries),
            "rate_limit_requests": str(self.rate_limit_requests),
            "chunk_size": str(self.chunk_size),
            "display_name": self.display_name,
            "system_prompt_tweak": self.system_prompt_tweak,
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "APIProfile":
        """Create from dictionary."""
        return cls(
            name=name,
            provider=data.get("provider", "openai"),
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", ""),
            model=data.get("model", "gpt-4o-mini"),
            temperature=float(data.get("temperature", 0.3)),
            timeout=int(data.get("timeout", 60)),
            retries=int(data.get("retries", 3)),
            rate_limit_requests=int(data.get("rate_limit_requests", 60)),
            chunk_size=int(data.get("chunk_size", 50)),
            display_name=data.get("display_name", ""),
            system_prompt_tweak=data.get("system_prompt_tweak", ""),
        )


def _get_project_root() -> Path:
    """Get the CherryAI project root directory."""
    return Path(__file__).resolve().parent.parent


def _get_api_profiles_path() -> Path:
    """Get the path to api_profiles.ini."""
    return _get_project_root() / "api_profiles.ini"


def load_game_summary(
    summary_file: str = "",
    max_chars: int = MAX_SUMMARY_CHARS,
) -> str:
    """Load game summary from file.
    
    Args:
        summary_file: Path to summary file (relative to project root, or absolute)
        max_chars: Maximum characters to load (truncates if exceeded)
        
    Returns:
        Summary text with comments stripped, or empty string if file not found.
    """
    if not summary_file:
        return ""
    
    summary_path = Path(summary_file)
    
    # If not absolute, treat as relative to project root
    if not summary_path.is_absolute():
        project_root = _get_project_root()
        summary_path = project_root / summary_file
    
    if not summary_path.exists():
        logging.debug(f"Game summary file not found: {summary_path}")
        return ""
    
    try:
        raw_text = summary_path.read_text(encoding="utf-8")
    except Exception as e:
        logging.warning(f"Failed to read game summary: {e}")
        return ""
    
    # Strip comment lines (lines starting with # followed by space or end of line)
    # Preserve markdown headers like ## TITLE
    lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        # Only skip if line starts with "# " (comment) but not "## " (markdown header)
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue
        # Skip bare "#" lines
        if stripped == "#":
            continue
        lines.append(line)
    
    summary = "\n".join(lines).strip()
    
    # Remove template placeholders (lines with just [placeholder text])
    cleaned_lines = []
    for line in summary.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            # Check if it's a placeholder like [Title goes here]
            inner = stripped[1:-1].strip().lower()
            if any(word in inner for word in ["goes here", "description", "summary", "notes"]):
                continue
        cleaned_lines.append(line)
    
    summary = "\n".join(cleaned_lines).strip()
    
    # Truncate if too long
    if len(summary) > max_chars:
        summary = summary[:max_chars] + "\n[Summary truncated...]"
        logging.info(f"Game summary truncated to {max_chars} characters")
    
    return summary


def format_summary_for_prompt(summary: str, project_config: Optional[ProjectConfig] = None) -> str:
    """Format game summary for injection into system prompt.
    
    Args:
        summary: Raw summary text
        project_config: Optional project configuration for additional context
        
    Returns:
        Formatted summary block ready for prompt injection.
    """
    if not summary:
        return ""
    
    parts = ["# Game Context"]
    
    # Add project name and genre if available
    if project_config:
        if project_config.name:
            parts.append(f"**Game:** {project_config.name}")
        if project_config.genre:
            parts.append(f"**Genre:** {project_config.genre}")
        if project_config.tone:
            parts.append(f"**Tone:** {project_config.tone}")
    
    parts.append("")
    parts.append(summary)
    
    # Add style notes if available
    if project_config and project_config.style_notes:
        parts.append("")
        parts.append("**Style Notes:**")
        parts.append(project_config.style_notes)
    
    return "\n".join(parts)


def load_project_config_from_ini(config_file: Optional[Path] = None) -> ProjectConfig:
    """Load project configuration from CherryAI.ini [project] section.
    
    Args:
        config_file: Path to INI file. If None, uses default.
        
    Returns:
        ProjectConfig with values from INI or defaults.
    """
    if config_file is None:
        config_file = _get_project_root() / "CherryAI.ini"
    
    config = configparser.ConfigParser()
    try:
        if config_file.exists():
            config.read(config_file, encoding="utf-8")
    except Exception as e:
        logging.warning(f"Failed to read project config: {e}")
        return ProjectConfig()
    
    if not config.has_section("project"):
        return ProjectConfig()
    
    section = dict(config["project"])
    return ProjectConfig.from_dict(section)


def save_project_config_to_ini(
    project_config: ProjectConfig,
    config_file: Optional[Path] = None,
) -> None:
    """Save project configuration to CherryAI.ini [project] section.
    
    Args:
        project_config: Configuration to save
        config_file: Path to INI file. If None, uses default.
    """
    if config_file is None:
        config_file = _get_project_root() / "CherryAI.ini"
    
    config = configparser.ConfigParser()
    try:
        if config_file.exists():
            config.read(config_file, encoding="utf-8")
    except Exception:
        pass
    
    if not config.has_section("project"):
        config.add_section("project")
    
    data = project_config.to_dict()
    for key, value in data.items():
        if key == "custom_settings":
            continue  # Skip complex nested dict for INI
        config.set("project", key, str(value))
    
    try:
        with config_file.open("w", encoding="utf-8") as f:
            config.write(f)
    except Exception as e:
        logging.error(f"Failed to save project config: {e}")


def load_api_profiles() -> Dict[str, APIProfile]:
    """Load all API profiles from ``user/API.ini`` (Phase 62).

    Returns:
        Dict mapping profile name to APIProfile.
    """
    from . import api_config as _api_cfg

    # Read profiles from API.ini
    profiles: Dict[str, APIProfile] = {}
    for name in ("translation", "glossary"):
        data = _api_cfg.get_all_profile_settings(name)
        if data:
            profiles[name] = APIProfile.from_dict(name, data)
        else:
            profiles[name] = APIProfile(name=name)

    return profiles


def save_api_profile(profile: APIProfile) -> None:
    """Save an API profile to ``user/API.ini`` (Phase 62).

    Non-secret fields are written to the matching section in API.ini.
    The ``api_key`` field is intentionally excluded here — use
    ``api_config.set_api_key()`` to store keys with encryption.

    Args:
        profile: API profile to save (uses ``profile.name`` as section name).
    """
    from . import api_config as _api_cfg

    data = profile.to_dict()
    for key, value in data.items():
        if key == "api_key":
            continue  # handled by encrypted set_api_key()
        _api_cfg.set_profile_setting(profile.name, key, str(value))


def get_api_profile(
    profile_name: str = "default",
    fallback_to_main_config: bool = True,
) -> Optional[APIProfile]:
    """Get a specific API profile from ``user/API.ini`` (Phase 62).

    Args:
        profile_name: Section name, e.g. ``"translation"`` or ``"glossary"``.
        fallback_to_main_config: If True and profile section is empty, build
            an APIProfile from the CherryAI.ini ``[api]`` section.

    Returns:
        APIProfile, or None if not found and fallback disabled.
    """
    from . import api_config as _api_cfg

    data = _api_cfg.get_all_profile_settings(profile_name)
    if data:
        return APIProfile.from_dict(profile_name, data)

    if fallback_to_main_config:
        from .config import load_config
        config = load_config()
        api_section = config.get("api", {})
        return APIProfile.from_dict(profile_name, api_section)

    return None


def delete_api_profile(profile_name: str) -> bool:
    """Delete an API profile section from ``user/API.ini`` (Phase 62).

    Args:
        profile_name: Section name to delete (e.g. ``"translation"``).

    Returns:
        True if the section existed and was removed, False otherwise.
    """
    from . import api_config as _api_cfg
    import configparser as _cp

    path = _api_cfg.get_api_ini_path()
    cfg = _cp.ConfigParser()
    cfg.optionxform = str
    if path.exists():
        cfg.read(str(path), encoding="utf-8")
    if not cfg.has_section(profile_name):
        return False
    cfg.remove_section(profile_name)
    with path.open("w", encoding="utf-8") as fh:
        cfg.write(fh)
    return True


# =============================================================================
# TASK 17.3: Named API Profile Utilities
# =============================================================================


def list_api_profile_names() -> List[str]:
    """List all available API profile names from api_profiles.ini.

    Returns:
        Sorted list of profile section names.
    """
    profiles = load_api_profiles()
    return sorted(profiles.keys())


def rename_api_profile(old_name: str, new_name: str) -> bool:
    """Rename an API profile (copy to new name then delete old).

    Args:
        old_name: Current profile section name.
        new_name: Desired profile section name.

    Returns:
        True if renamed successfully; False if old_name not found or
        new_name already exists.
    """
    if old_name == new_name:
        return True

    profiles = load_api_profiles()

    if old_name not in profiles:
        logging.warning("Cannot rename profile '%s': not found", old_name)
        return False

    if new_name in profiles:
        logging.warning(
            "Cannot rename to '%s': profile already exists", new_name,
        )
        return False

    profile = profiles[old_name]
    profile.name = new_name
    save_api_profile(profile)
    delete_api_profile(old_name)
    return True


def duplicate_api_profile(
    source_name: str,
    new_name: str,
    new_display_name: str = "",
) -> Optional[APIProfile]:
    """Duplicate an existing API profile under a new name.

    Args:
        source_name: Profile to copy from.
        new_name: Section name for the duplicate.
        new_display_name: Optional display_name for the copy.

    Returns:
        The newly created APIProfile, or None on failure.
    """
    profiles = load_api_profiles()

    if source_name not in profiles:
        logging.warning(
            "Cannot duplicate profile '%s': not found", source_name,
        )
        return None

    if new_name in profiles:
        logging.warning(
            "Cannot duplicate to '%s': profile already exists", new_name,
        )
        return None

    source = profiles[source_name]
    data = source.to_dict()
    copy = APIProfile.from_dict(new_name, data)
    if new_display_name:
        copy.display_name = new_display_name
    save_api_profile(copy)
    return copy


def get_profile_display_map() -> Dict[str, str]:
    """Return a mapping of profile name → display label.

    Uses the profile's ``label`` property (display_name if set, else name).

    Returns:
        Ordered dict {section_name: label} for all profiles.
    """
    profiles = load_api_profiles()
    return {name: p.label for name, p in sorted(profiles.items())}
