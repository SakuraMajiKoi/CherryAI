"""CherryAI INI Configuration Manager.

Provides centralized INI file path resolution and typed access to configuration values.
The INI file (CherryAI.ini) must be located next to the main CherryAI.py script.

This module is the single source of truth for:
- INI file path resolution (relative to main module)
- Typed access to configuration values with fallbacks
- Manifest defaults section handling
- Default paths for manifests and other directories
- User defaults management (TASK 31.2)
- Initial defaults from config/defaults.ini

TASK 21.1: Created as part of Manifest 3.0 Foundation
TASK 31.2: Added user_defaults and initial_defaults support
"""

from __future__ import annotations

import configparser
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Type aliases for clarity
ConfigValue = Union[str, int, float, bool, None]

# Cache for loaded INI data
_ini_cache: Optional[configparser.ConfigParser] = None
_ini_path_cache: Optional[Path] = None
_defaults_cache: Optional[configparser.ConfigParser] = None


def get_ini_path() -> Path:
    """Get the path to CherryAI.ini relative to the main module.

    The INI file is always located next to CherryAI.py (or future .exe).
    This ensures consistent path resolution regardless of working directory.

    Returns:
        Path to CherryAI.ini file.

    Example:
        >>> ini_path = get_ini_path()
        >>> ini_path.name
        'CherryAI.ini'
    """
    global _ini_path_cache

    if _ini_path_cache is not None:
        return _ini_path_cache

    # Try to find CherryAI.py location
    try:
        # First, try importing the CherryAI module to get its path
        import sys

        # Check for CherryAI module in various forms
        for module_name in ("CherryAI", "CherryAI.CherryAI"):
            if module_name in sys.modules:
                module = sys.modules[module_name]
                if hasattr(module, "__file__") and module.__file__:
                    module_path = Path(module.__file__).resolve()
                    _ini_path_cache = module_path.parent / "CherryAI.ini"
                    return _ini_path_cache

        # Fallback: resolve relative to this file (functions/ is one level below root)
        this_file = Path(__file__).resolve()
        package_root = this_file.parent.parent  # functions/ -> CherryAI/
        _ini_path_cache = package_root / "CherryAI.ini"
        return _ini_path_cache

    except Exception as e:
        logger.warning("Failed to resolve INI path via module: %s", e)
        # Ultimate fallback
        _ini_path_cache = Path(__file__).resolve().parent.parent / "CherryAI.ini"
        return _ini_path_cache


def get_app_dir() -> Path:
    """Get the application root directory.

    Returns:
        Path to the CherryAI application directory.
    """
    return get_ini_path().parent


def get_manifest_dir() -> Path:
    """Get the default manifest directory.

    Returns:
        Path to {app_dir}/manifests (created if not exists).
    """
    manifest_dir = get_app_dir() / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return manifest_dir


def _load_ini() -> configparser.ConfigParser:
    """Load and cache the INI file.

    Returns:
        ConfigParser with loaded INI data.
    """
    global _ini_cache

    if _ini_cache is not None:
        return _ini_cache

    _ini_cache = configparser.ConfigParser()
    ini_path = get_ini_path()

    try:
        if ini_path.exists():
            _ini_cache.read(ini_path, encoding="utf-8")
            logger.debug("Loaded INI from: %s", ini_path)
        else:
            logger.warning("INI file not found: %s", ini_path)
    except Exception as e:
        logger.error("Failed to load INI file: %s", e)

    return _ini_cache


def reload_ini() -> None:
    """Force reload of the INI file (clears cache)."""
    global _ini_cache
    _ini_cache = None
    _load_ini()


def get_default(
    section: str,
    key: str,
    fallback: ConfigValue = None,
    value_type: type = str,
) -> ConfigValue:
    """Get a configuration value with type conversion.

    Args:
        section: INI section name (e.g., 'manifest_defaults', 'api').
        key: Configuration key within the section.
        fallback: Default value if key not found.
        value_type: Expected type (str, int, float, bool).

    Returns:
        Configuration value converted to specified type, or fallback.

    Example:
        >>> get_default('manifest_defaults', 'deduplication', True, bool)
        True
        >>> get_default('api', 'temperature', 0.3, float)
        0.3
    """
    config = _load_ini()

    try:
        if not config.has_section(section):
            return fallback

        if not config.has_option(section, key):
            return fallback

        raw_value = config.get(section, key)

        # Type conversion
        if value_type == bool:
            return raw_value.lower() in ("true", "yes", "1", "on")
        elif value_type == int:
            return int(raw_value)
        elif value_type == float:
            return float(raw_value)
        else:
            return raw_value

    except (ValueError, TypeError) as e:
        logger.warning(
            "Type conversion failed for [%s]%s=%r: %s. Using fallback: %r",
            section,
            key,
            raw_value,
            e,
            fallback,
        )
        return fallback


def get_str(section: str, key: str, fallback: str = "") -> str:
    """Get a string configuration value.

    Args:
        section: INI section name.
        key: Configuration key.
        fallback: Default value if key not found.

    Returns:
        String configuration value.
    """
    result = get_default(section, key, fallback, str)
    return result if isinstance(result, str) else fallback


def get_int(section: str, key: str, fallback: int = 0) -> int:
    """Get an integer configuration value.

    Args:
        section: INI section name.
        key: Configuration key.
        fallback: Default value if key not found.

    Returns:
        Integer configuration value.
    """
    result = get_default(section, key, fallback, int)
    return result if isinstance(result, int) else fallback


def get_float(section: str, key: str, fallback: float = 0.0) -> float:
    """Get a float configuration value.

    Args:
        section: INI section name.
        key: Configuration key.
        fallback: Default value if key not found.

    Returns:
        Float configuration value.
    """
    result = get_default(section, key, fallback, float)
    return result if isinstance(result, (int, float)) else fallback


def get_bool(section: str, key: str, fallback: bool = False) -> bool:
    """Get a boolean configuration value.

    Args:
        section: INI section name.
        key: Configuration key.
        fallback: Default value if key not found.

    Returns:
        Boolean configuration value.
    """
    result = get_default(section, key, fallback, bool)
    return result if isinstance(result, bool) else fallback


def get_list(section: str, key: str, fallback: Optional[List[str]] = None) -> List[str]:
    """Get a comma-separated list configuration value.

    Args:
        section: INI section name.
        key: Configuration key.
        fallback: Default value if key not found.

    Returns:
        List of strings (split by comma, whitespace stripped).
    """
    if fallback is None:
        fallback = []

    raw_value = get_str(section, key, "")
    if not raw_value:
        return fallback

    return [item.strip() for item in raw_value.split(",") if item.strip()]


def set_default(section: str, key: str, value: ConfigValue) -> bool:
    """Set a configuration value and save to INI.

    Creates the section if it doesn't exist.

    Args:
        section: INI section name.
        key: Configuration key.
        value: Value to set (will be converted to string).

    Returns:
        True if successful, False otherwise.

    Example:
        >>> set_default('manifest_defaults', 'deduplication', True)
        True
    """
    config = _load_ini()
    ini_path = get_ini_path()

    try:
        # Create section if needed
        if not config.has_section(section):
            config.add_section(section)

        # Convert value to string
        if isinstance(value, bool):
            str_value = "true" if value else "false"
        elif value is None:
            str_value = ""
        else:
            str_value = str(value)

        config.set(section, key, str_value)

        # Save to file
        with open(ini_path, "w", encoding="utf-8") as f:
            config.write(f)

        logger.debug("Set [%s]%s = %s", section, key, str_value)
        return True

    except Exception as e:
        logger.error("Failed to set config [%s]%s: %s", section, key, e)
        return False


def get_section(section: str) -> Dict[str, str]:
    """Get all key-value pairs from a section.

    Args:
        section: INI section name.

    Returns:
        Dictionary of key-value pairs (empty dict if section not found).
    """
    config = _load_ini()

    if not config.has_section(section):
        return {}

    return dict(config.items(section))


def has_section(section: str) -> bool:
    """Check if a section exists in the INI file.

    Args:
        section: Section name to check.

    Returns:
        True if section exists.
    """
    config = _load_ini()
    return config.has_section(section)


def has_option(section: str, key: str) -> bool:
    """Check if an option exists in the INI file.

    Args:
        section: Section name.
        key: Option key.

    Returns:
        True if option exists.
    """
    config = _load_ini()
    return config.has_option(section, key)


def remove_section(section: str) -> bool:
    """Remove an entire section from the INI file.

    Args:
        section: Section name to remove.

    Returns:
        True if the section existed and was removed.
    """
    config = _load_ini()
    if not config.has_section(section):
        return False
    config.remove_section(section)
    _save_ini(config)
    return True


# =============================================================================
# Manifest Defaults Section Helpers
# =============================================================================


def get_manifest_default(key: str, fallback: ConfigValue = None) -> ConfigValue:
    """Get a manifest default value from [manifest_defaults] section.

    Convenience wrapper for manifest-specific defaults.

    Args:
        key: Configuration key.
        fallback: Default value if key not found.

    Returns:
        Configuration value (type determined by fallback).
    """
    # Infer type from fallback
    if isinstance(fallback, bool):
        return get_bool("manifest_defaults", key, fallback)
    elif isinstance(fallback, int):
        return get_int("manifest_defaults", key, fallback)
    elif isinstance(fallback, float):
        return get_float("manifest_defaults", key, fallback)
    else:
        return get_str("manifest_defaults", key, str(fallback) if fallback else "")


def get_all_manifest_defaults() -> Dict[str, Any]:
    """Get all manifest defaults as a typed dictionary.

    Reads all values from [manifest_defaults] section and converts
    to appropriate types based on known schema.

    Returns:
        Dictionary with all manifest default values.
    """
    raw = get_section("manifest_defaults")
    if not raw:
        return _get_builtin_manifest_defaults()

    # Known type mappings for manifest defaults
    bool_keys = {
        "deduplication",
        "ellipsis_compression",
        "symbol_conversion",
        "speaker_name_replacement",
        "code_spacing_rules",
        "validation_placeholder_preservation",
        "validation_anchor_preservation",
        "validation_japanese_character_detection",
        "validation_speaker_format",
        "validation_quote_balance",
        "validation_empty_translation",
        "request_enable_caching",
        "request_line_by_line_mode",
        "request_thinking",
        "post_placeholder_recovery",
        "post_bracket_balance_recovery",
        "post_quote_balance_recovery",
        "post_whitespace_normalization",
        "post_restore_code_characters",
        "post_restore_linebreaks",
        "post_enable_symbol_conversion",
        "post_fullwidth_to_halfwidth",
        "wordwrap_prevent_orphans",
        "wordwrap_prefer_punctuation_breaks",
        "output_preserve_folder_structure",
        "output_overwrite_existing_files",
        "output_export_manifest_file",
        "output_export_processing_logs",
        "output_export_glossary_entries",
    }

    int_keys = {
        "deduplication_threshold",
        "qa_max_japanese_chars",
        "qa_max_line_length",
        "request_lines_per_chunk",
        "request_max_retries",
        "request_thinking_budget",
        "wordwrap_width",
        "wordwrap_max_lines",
    }

    float_keys = {
        "request_temperature",
    }

    result: Dict[str, Any] = {}
    for key, raw_value in raw.items():
        if key in bool_keys:
            result[key] = raw_value.lower() in ("true", "yes", "1", "on")
        elif key in int_keys:
            try:
                result[key] = int(raw_value)
            except ValueError:
                result[key] = 0
        elif key in float_keys:
            try:
                result[key] = float(raw_value)
            except ValueError:
                result[key] = 0.0
        else:
            result[key] = raw_value

    return result


def _get_builtin_manifest_defaults() -> Dict[str, Any]:
    """Get hardcoded default manifest values.

    Used as fallback when INI file is missing or incomplete.

    Returns:
        Dictionary with all default manifest values.
    """
    return {
        # Project Information
        "project_name": "Project1",
        "title": "Title1",
        "genre": "fictional, nonfictional",
        "source_language": "Japanese",
        "target_language": "English",
        "summary": "[Summary of the Content]",
        "style_preset": "neutral",
        "tone_preset": "natural",
        # Preprocessing
        "deduplication": True,
        "deduplication_threshold": 1,
        "ellipsis_compression": True,
        "symbol_conversion": True,
        "speaker_name_replacement": False,
        "code_spacing_rules": True,
        # Validation Rules
        "validation_placeholder_preservation": True,
        "validation_anchor_preservation": True,
        "validation_japanese_character_detection": True,
        "validation_speaker_format": True,
        "validation_quote_balance": True,
        "validation_empty_translation": True,
        # QA Options
        "qa_rerun_policy": "FailedOnly",
        "qa_max_japanese_chars": 4,
        "qa_max_line_length": 0,
        # Request Options
        "request_temperature": 0.2,
        "request_lines_per_chunk": 30,
        "request_retry_strategy": "Batch",
        "request_max_retries": 3,
        "request_enable_caching": True,
        "request_line_by_line_mode": False,
        "request_thinking": False,
        "request_thinking_budget": 1000,
        # Post Processing
        "post_placeholder_recovery": True,
        "post_bracket_balance_recovery": True,
        "post_quote_balance_recovery": True,
        "post_whitespace_normalization": True,
        "post_restore_code_characters": True,
        "post_restore_linebreaks": True,
        "post_enable_symbol_conversion": True,
        "post_fullwidth_to_halfwidth": True,
        "post_failure_handling": "FlagForReview",
        # Wordwrap Settings
        "wordwrap_mode": "Manual",
        "wordwrap_width": 48,
        "wordwrap_break_char": "",
        "wordwrap_max_lines": 4,
        "wordwrap_prevent_orphans": True,
        "wordwrap_prefer_punctuation_breaks": True,
        "wordwrap_speaker_handling": "Sameline",
        "wordwrap_ignore_patterns": "Angle,Square,Curly,En",
        "wordwrap_typography": "Western",
        # Output Format
        "output_preserve_folder_structure": True,
        "output_pair_mode": "translated_only",
        "output_file_naming": "PutInSubfolder",
        "output_text_option": "translated",
        "output_overwrite_existing_files": False,
        "output_backup": "Timestamp",
        "output_backup_extension": ".bk",
        "output_export_manifest_file": False,
        "output_export_processing_logs": False,
        "output_export_glossary_entries": False,
    }


def clear_cache() -> None:
    """Clear all cached data (useful for testing)."""
    global _ini_cache, _ini_path_cache, _defaults_cache
    _ini_cache = None
    _ini_path_cache = None
    _defaults_cache = None


# =============================================================================
# Recent/Session Management (TASK 21.4)
# =============================================================================


def get_last_manifest() -> Optional[Path]:
    """Get the path to the last used manifest from INI.

    Reads [recent] last_manifest from INI file.

    Returns:
        Path to last manifest if it exists, None otherwise.

    Example:
        >>> path = get_last_manifest()
        >>> if path and path.exists():
        ...     load_manifest(path)
    """
    path_str = get_str("recent", "last_manifest", "")
    if not path_str:
        return None

    path = Path(path_str)

    # Return the path even if it doesn't exist - caller should check
    return path if path_str else None


def set_last_manifest(manifest_path: Optional[Path]) -> bool:
    """Set the last used manifest path in INI.

    Stores as absolute path in [recent] last_manifest.

    Args:
        manifest_path: Path to manifest, or None to clear.

    Returns:
        True if successful.

    Example:
        >>> set_last_manifest(Path("manifests/my_project.cherryproj"))
        True
    """
    if manifest_path is None:
        return set_default("recent", "last_manifest", "")

    # Store as absolute path
    abs_path = manifest_path.resolve()
    return set_default("recent", "last_manifest", str(abs_path))


def get_recent_manifests(max_count: int = 10) -> List[Path]:
    """Get list of recently used manifests from INI.

    Reads [recent] manifest_history as comma-separated paths.

    Args:
        max_count: Maximum number of recent manifests to return.

    Returns:
        List of manifest paths (most recent first), filtered to existing files.
    """
    raw = get_str("recent", "manifest_history", "")
    if not raw:
        return []

    paths = []
    for path_str in raw.split("|"):
        path_str = path_str.strip()
        if path_str:
            path = Path(path_str)
            if path.exists() and path not in paths:
                paths.append(path)
                if len(paths) >= max_count:
                    break

    return paths


def add_to_recent_manifests(manifest_path: Path) -> bool:
    """Add a manifest to the recent manifests list.

    Moves the path to the front if already in list.
    Limits list to 10 most recent.

    Args:
        manifest_path: Manifest path to add.

    Returns:
        True if successful.
    """
    abs_path = manifest_path.resolve()

    # Get current list
    current = get_recent_manifests(max_count=20)

    # Remove if already present
    current = [p for p in current if p.resolve() != abs_path]

    # Add to front
    current.insert(0, abs_path)

    # Limit to 10
    current = current[:10]

    # Save
    history_str = "|".join(str(p) for p in current)
    return set_default("recent", "manifest_history", history_str)


def get_restore_on_launch() -> bool:
    """Check if session restore on launch is enabled.

    Reads [recent] restore_on_launch from INI.

    Returns:
        True if restore is enabled (default True).
    """
    return get_bool("recent", "restore_on_launch", True)


def set_restore_on_launch(enabled: bool) -> bool:
    """Set whether to restore last manifest on launch.

    Args:
        enabled: True to enable restore on launch.

    Returns:
        True if successful.
    """
    return set_default("recent", "restore_on_launch", enabled)


def get_last_input_dir() -> Optional[Path]:
    """Get the last used input directory from INI.

    PHASE 58.12: Reads [recent] last_input_dir from INI file.

    Returns:
        Path to last input directory if it exists, None otherwise.
    """
    path_str = get_str("recent", "last_input_dir", "")
    if not path_str:
        return None
    
    path = Path(path_str)
    # Return only if directory exists
    if path.exists() and path.is_dir():
        return path
    return None


def set_last_input_dir(dir_path: Optional[Path]) -> bool:
    """Set the last used input directory in INI.

    PHASE 58.12: Stores as absolute path in [recent] last_input_dir.

    Args:
        dir_path: Path to directory, or None to clear.

    Returns:
        True if successful.
    """
    if dir_path is None:
        return set_default("recent", "last_input_dir", "")
    
    # Store as absolute path
    abs_path = dir_path.resolve()
    return set_default("recent", "last_input_dir", str(abs_path))


# =============================================================================
# User Defaults Management (TASK 31.2)
# =============================================================================


def get_defaults_path() -> Path:
    """Get the path to config/defaults.ini (initial defaults).

    Returns:
        Path to defaults.ini file.
    """
    return get_app_dir() / "config" / "defaults.ini"


def _load_defaults_ini() -> configparser.ConfigParser:
    """Load and cache the initial defaults INI file.

    Returns:
        ConfigParser with loaded defaults data.
    """
    global _defaults_cache

    if _defaults_cache is not None:
        return _defaults_cache

    _defaults_cache = configparser.ConfigParser()
    defaults_path = get_defaults_path()

    try:
        if defaults_path.exists():
            _defaults_cache.read(defaults_path, encoding="utf-8")
            logger.debug("Loaded defaults from: %s", defaults_path)
        else:
            logger.warning("Defaults file not found: %s", defaults_path)
    except Exception as e:
        logger.error("Failed to load defaults file: %s", e)

    return _defaults_cache


def get_initial_default(
    section: str,
    key: str,
    fallback: ConfigValue = None,
    value_type: type = str,
) -> ConfigValue:
    """Get an initial default value from config/defaults.ini.

    Args:
        section: INI section name.
        key: Configuration key within the section.
        fallback: Default value if key not found.
        value_type: Expected type (str, int, float, bool).

    Returns:
        Configuration value converted to specified type, or fallback.

    Example:
        >>> get_initial_default('manifest_defaults', 'deduplication', True, bool)
        True
    """
    config = _load_defaults_ini()

    try:
        if not config.has_section(section):
            return fallback

        if not config.has_option(section, key):
            return fallback

        raw_value = config.get(section, key)

        # Type conversion
        if value_type == bool:
            return raw_value.lower() in ("true", "yes", "1", "on")
        elif value_type == int:
            return int(raw_value)
        elif value_type == float:
            return float(raw_value)
        else:
            return raw_value

    except (ValueError, TypeError) as e:
        logger.warning(
            "Type conversion failed for initial default [%s]%s: %s",
            section,
            key,
            e,
        )
        return fallback


def get_user_default(
    section: str,
    key: str,
    fallback: ConfigValue = None,
    value_type: type = str,
) -> ConfigValue:
    """Get a user default value from [user_defaults] section in CherryAI.ini.

    User defaults override initial defaults when set.

    Args:
        section: Original section name (used to construct prefixed key).
        key: Configuration key.
        fallback: Default value if not found.
        value_type: Expected type.

    Returns:
        User default value, or fallback if not set.

    Example:
        >>> get_user_default('manifest_defaults', 'deduplication', True, bool)
        True  # If user has saved this as default
    """
    # User defaults are stored with section prefix: "section.key"
    prefixed_key = f"{section}.{key}"
    return get_default("user_defaults", prefixed_key, fallback, value_type)


def set_user_default(section: str, key: str, value: ConfigValue) -> bool:
    """Set a user default value in [user_defaults] section.

    Args:
        section: Original section name (used to construct prefixed key).
        key: Configuration key.
        value: Value to set.

    Returns:
        True if successful.

    Example:
        >>> set_user_default('manifest_defaults', 'deduplication', False)
        True
    """
    # Store with section prefix
    prefixed_key = f"{section}.{key}"
    return set_default("user_defaults", prefixed_key, value)


def has_user_default(section: str, key: str) -> bool:
    """Check if a user default exists.

    Args:
        section: Original section name.
        key: Configuration key.

    Returns:
        True if user has set this default.
    """
    prefixed_key = f"{section}.{key}"
    return has_option("user_defaults", prefixed_key)


def get_effective_default(
    section: str,
    key: str,
    fallback: ConfigValue = None,
    value_type: type = str,
) -> ConfigValue:
    """Get the effective default value (user default if set, else initial default).

    This is the primary function for retrieving defaults with proper override chain:
    1. User defaults (from [user_defaults] in CherryAI.ini)
    2. Initial defaults (from config/defaults.ini)
    3. Fallback value

    Args:
        section: INI section name.
        key: Configuration key.
        fallback: Default value if neither user nor initial default exists.
        value_type: Expected type.

    Returns:
        Effective default value.

    Example:
        >>> get_effective_default('manifest_defaults', 'deduplication', True, bool)
        False  # If user saved False as default
    """
    # Check user defaults first
    if has_user_default(section, key):
        return get_user_default(section, key, fallback, value_type)

    # Fall back to initial defaults
    return get_initial_default(section, key, fallback, value_type)


def save_as_user_defaults(section: str, values: Dict[str, Any]) -> bool:
    """Save multiple values as user defaults for a section.

    Args:
        section: Original section name.
        values: Dictionary of key-value pairs to save.

    Returns:
        True if all saves successful.

    Example:
        >>> save_as_user_defaults('manifest_defaults', {
        ...     'deduplication': True,
        ...     'deduplication_threshold': 2,
        ... })
        True
    """
    success = True
    for key, value in values.items():
        if not set_user_default(section, key, value):
            success = False
    return success


def get_all_user_defaults(section: str) -> Dict[str, str]:
    """Get all user defaults for a section.

    Args:
        section: Original section name.

    Returns:
        Dictionary of user defaults for the section.
    """
    all_user_defaults = get_section("user_defaults")
    prefix = f"{section}."

    result = {}
    for key, value in all_user_defaults.items():
        if key.startswith(prefix):
            actual_key = key[len(prefix):]
            result[actual_key] = value

    return result


def clear_user_defaults(section: Optional[str] = None) -> bool:
    """Clear user defaults (all or for a specific section).

    Args:
        section: If provided, only clear defaults for this section.
                 If None, clear all user defaults.

    Returns:
        True if successful.
    """
    config = _load_ini()
    ini_path = get_ini_path()

    try:
        if not config.has_section("user_defaults"):
            return True  # Nothing to clear

        if section is None:
            # Clear all user defaults
            config.remove_section("user_defaults")
        else:
            # Clear only defaults for specific section
            prefix = f"{section}."
            keys_to_remove = [
                key for key in config.options("user_defaults")
                if key.startswith(prefix)
            ]
            for key in keys_to_remove:
                config.remove_option("user_defaults", key)

        # Save to file
        with open(ini_path, "w", encoding="utf-8") as f:
            config.write(f)

        return True

    except Exception as e:
        logger.error("Failed to clear user defaults: %s", e)
        return False


def restore_initial_defaults(section: Optional[str] = None) -> bool:
    """Restore initial defaults by clearing user defaults.

    This removes user customizations and reverts to initial defaults
    from config/defaults.ini.

    Args:
        section: If provided, only restore for this section.
                 If None, restore all sections.

    Returns:
        True if successful.
    """
    return clear_user_defaults(section)


def get_all_initial_defaults(section: str) -> Dict[str, str]:
    """Get all initial defaults for a section from config/defaults.ini.

    Args:
        section: Section name.

    Returns:
        Dictionary of initial defaults for the section.
    """
    config = _load_defaults_ini()

    if not config.has_section(section):
        return {}

    return dict(config.items(section))


def reload_defaults_cache() -> None:
    """Force reload of the defaults.ini file (clears cache)."""
    global _defaults_cache
    _defaults_cache = None
    _load_defaults_ini()
