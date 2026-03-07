"""CherryAI INI Configuration Manager.

Provides centralized INI file path resolution and typed access to configuration values.
The INI file (CherryAI.ini) is located in the user/ subfolder of the application root.

This module is the single source of truth for:
- INI file path resolution (user/ subfolder next to CherryAI.py)
- Typed access to configuration values with fallbacks
- Manifest defaults section handling
- Default paths for manifests and other directories
- User defaults management (TASK 31.2)
- Factory defaults (embedded in _FACTORY_DEFAULTS_INI_TEXT — no config/ folder)
- Style/Tone preset management via [style]/[tone] INI sections
- Long-text defaults via [defaults] INI section

INI LOCATION: user/CherryAI.ini
  - Migrated automatically from root CherryAI.ini on first run.

FACTORY DEFAULTS: All factory defaults are embedded in _FACTORY_DEFAULTS_INI_TEXT.
  config/defaults.ini no longer exists; get_initial_default() reads from the constant.

TASK 21.1: Created as part of Manifest 3.0 Foundation
TASK 31.2: Added user_defaults and initial_defaults support
TASK STYLE: Style/Tone presets unified in INI [style]/[tone] sections
SESSION 25: Removed config/ folder — all defaults embedded in this module.
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

# =============================================================================
# FACTORY DEFAULTS — embedded so config/defaults.ini is no longer needed.
# These are the shipping defaults for every setting. User overrides live in
# user/CherryAI.ini [user_defaults].  Conditional-prompt defaults are in the
# [conditional_prompts] section; they are seeded into [prompts] on first run.
# =============================================================================
_FACTORY_DEFAULTS_INI_TEXT: str = """
[manifest_defaults]
project_name = Project1
title = Title1
genre = fictional, nonfictional
source_language = Japanese
target_language = English
summary = [Summary of the Content]
style_preset = neutral
tone_preset = natural
deduplication = true
deduplication_threshold = 1
ellipsis_compression = true
symbol_conversion = true
speaker_name_replacement = false
code_spacing_rules = true
validation_placeholder_preservation = true
validation_anchor_preservation = true
validation_japanese_character_detection = true
validation_speaker_format = true
validation_quote_balance = true
validation_empty_translation = true
character_whitelist =
character_blacklist =
word_blacklist =
autofix_map =
qa_rerun_policy = FailedOnly
qa_max_japanese_chars = 4
qa_max_line_length = 0
request_temperature = 0.2
request_lines_per_chunk = 30
request_retry_strategy = Batch
request_max_retries = 3
request_enable_caching = true
request_line_by_line_mode = false
request_thinking = false
request_thinking_budget = 1000
post_placeholder_recovery = true
post_bracket_balance_recovery = true
post_quote_balance_recovery = true
post_whitespace_normalization = true
post_restore_code_characters = true
post_restore_linebreaks = true
post_enable_symbol_conversion = true
post_fullwidth_to_halfwidth = true
post_failure_handling = flag
wordwrap_mode = Manual
wordwrap_width = 48
wordwrap_break_char =
wordwrap_max_lines = 4
wordwrap_prevent_orphans = true
wordwrap_prefer_punctuation_breaks = true
wordwrap_speaker_handling = Sameline
wordwrap_ignore_patterns = Angle,Square,Curly,En
wordwrap_typography = Western
output_preserve_folder_structure = true
output_pair_mode = translated_only
output_file_naming = subfolder
output_text_option = translated
output_overwrite_existing_files = false
output_backup = Timestamp
output_backup_extension = .bk
output_export_manifest_file = false
output_export_processing_logs = false
output_export_glossary_entries = false

[api]
provider = openai
api_key =
base_url =
model = gpt-4o-mini
temperature = 0.3
timeout = 60
retries = 3
rate_limit_requests = 60
chunk_size = 50
source_lang = Japanese
target_lang = English
content_warning_enabled = true
retry_strategy = batch
cache_enabled = true

[session]
autosave = true
interval = 60
theme = light
load_last = true
last_manifest = 

[caching]
enabled = true
dir = Cache
age = 0
size = 0
mode = strict
aggressive_dedup = false

[log]
level = Error
location = log/
debug = false
api_log = true

[limit]
banned = \u2014, \u2013
warnings = true
output = 4096
safe = true

[fileio]
encoding = auto
lines = auto
preservebom = true
backup = true

[prompts]
edit = Review and improve the translation while maintaining accuracy and natural flow. Fix any grammar issues, awkward phrasing, or inconsistencies. Preserve the original meaning and tone.
tlc = Perform a Translation/Localization Check (TLC) on the translation. Verify accuracy against the source text, check for natural {target_lang} expression, ensure consistency in terminology and style, and flag any issues or suggest improvements.

[conditional_prompts]
dialogue = # Content Type: Dialogue\\nThese lines are character dialogue. Pay attention to the speaker names, maintain consistent voice and tone for each character, and preserve emotional nuances in the conversation.
menu = # Content Type: Menu\\nThese lines are menu items from a game UI. Translate each item concisely and clearly. Preserve formatting, order, and any shortcut indicators. Keep translations brief and action-oriented.
choice = # Content Type: Choices\\nThese lines are player choices or options. Translate each choice concisely and distinctly so the player can differentiate between options. Preserve numbering or bullet formatting.
unknown = # Content Type: Mixed\\nThese lines may contain dialogue, menu items, or choices. Translate each line appropriately based on its apparent purpose. Maintain formatting and keep menu/choice items concise.
"""


def _get_app_root() -> Path:
    """Resolve the application root directory (contains CherryAI.py).

    Returns:
        Absolute Path of the CherryAI package directory.
    """
    import sys

    for module_name in ("CherryAI", "CherryAI.CherryAI"):
        if module_name in sys.modules:
            module = sys.modules[module_name]
            if hasattr(module, "__file__") and module.__file__:
                return Path(module.__file__).resolve().parent

    # Fallback: this file lives in functions/, parent is the app root.
    return Path(__file__).resolve().parent.parent


def get_ini_path() -> Path:
    """Get the path to user/CherryAI.ini.

    The INI file lives in the ``user/`` subfolder of the application root.
    On the first call, if the legacy root-level CherryAI.ini exists and
    user/CherryAI.ini does not, the file is migrated automatically.

    Returns:
        Path to user/CherryAI.ini.

    Example:
        >>> ini_path = get_ini_path()
        >>> ini_path.parts[-2:]
        ('user', 'CherryAI.ini')
    """
    global _ini_path_cache

    if _ini_path_cache is not None:
        return _ini_path_cache

    try:
        app_root = _get_app_root()
        user_ini = app_root / "user" / "CherryAI.ini"
        legacy_ini = app_root / "CherryAI.ini"

        # Auto-migrate legacy INI to user/ on first run.
        if legacy_ini.exists() and not user_ini.exists():
            user_ini.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(legacy_ini, user_ini)
            logger.info("Migrated CherryAI.ini: %s -> %s", legacy_ini, user_ini)
            try:
                legacy_ini.unlink()
            except Exception as exc:
                logger.warning("Could not remove legacy INI: %s", exc)

        # Ensure user/ directory exists.
        user_ini.parent.mkdir(parents=True, exist_ok=True)

        _ini_path_cache = user_ini
        return _ini_path_cache

    except Exception as exc:
        logger.warning("Failed to resolve INI path: %s", exc)
        _ini_path_cache = Path(__file__).resolve().parent.parent / "user" / "CherryAI.ini"
        return _ini_path_cache


def get_app_dir() -> Path:
    """Get the application root directory (parent of user/).

    Returns:
        Path to the CherryAI application root directory.
    """
    return get_ini_path().parent.parent


def get_user_dir() -> Path:
    """Get the user data directory (user/).

    Returns:
        Path to the user/ directory, created if missing.
    """
    user_dir = get_ini_path().parent
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_manifest_dir() -> Path:
    """Get the default manifest directory.

    Returns:
        Path to {app_dir}/manifests (created if not exists).
    """
    manifest_dir = get_app_dir() / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return manifest_dir


def ensure_app_dirs() -> None:
    """Create all required application directories under the CherryAI root.

    Phase 62: Called on every _load_ini() invocation so directories always
    exist after the first application access. Safe to call multiple times
    (uses exist_ok=True).

    Directories created:
        user/       – INI files, glossaries, API config
        Projects/   – Per-project manifest folders
        logs/       – Translation and QA log files
        cache/      – Cached translation data
    """
    root = get_app_dir()
    for dir_name in ("user", "Projects", "logs", "cache"):
        (root / dir_name).mkdir(parents=True, exist_ok=True)


# Sections that must always exist in CherryAI.ini.
# If any are absent when the file is read, they are added to the in-memory
# config immediately *and* the file is re-saved so that subsequent reads
# (including fresh ``reload_ini()`` calls) also see them.  This prevents
# test helpers or any partial-save operation from silently stripping sections.
_REQUIRED_SECTIONS: tuple[str, ...] = (
    "session",            # renamed from 'recent'; stores last_manifest, load_last
    "ui",                 # window geometry and state
    "confirmations",      # suppressed confirmation dialog keys
    "defaults",           # merged defaults (was manifest_defaults + defaults)
    "style",              # named style presets
    "tone",               # named tone presets
    "system_instructions",  # named system instructions presets (was JSON file)
    "caching",            # request cache settings
    "limit",              # safety / output-limit settings
    "prompts",            # edit/TLC prompt settings
    "log",                # logging settings
    "fileio",             # file I/O settings
    "security",           # password / encryption settings
)

# Legacy section migrations applied once on first load.
# Keys: old section name → new section name (None = discard/remove).
_LEGACY_SECTION_RENAMES: Dict[str, Optional[str]] = {
    "recent": "session",
    "manifest_defaults": "defaults",
    "api": None,           # moved to API.ini
    "api_presets": None,   # moved to API.ini
    "project": None,       # per-project → manifest files
    "translation": None,   # per-project → manifest files
    "rolling_context": None,   # per-project → manifest files
    "partial_translation": None,  # per-project → manifest files
    "safety": None,        # renamed to 'limit'
}


def _ensure_required_sections(config: configparser.ConfigParser) -> bool:
    """Add any missing required sections to *config*.

    Args:
        config: In-memory ConfigParser to patch.

    Returns:
        ``True`` if at least one section was added (caller should save).
    """
    added = False
    for section in _REQUIRED_SECTIONS:
        if not config.has_section(section):
            config.add_section(section)
            logger.debug("Initialized missing INI section [%s]", section)
            added = True
    return added


def _migrate_legacy_sections(config: configparser.ConfigParser) -> bool:
    """Apply one-time legacy section renames and discards.

    - ``[recent]``          → ``[session]``          (keys copied)
    - ``[manifest_defaults]`` → ``[defaults]``         (keys merged into)
    - ``api``, ``api_presets``, ``project``, ``translation``,
      ``rolling_context``, ``partial_translation``, ``safety`` → removed
    - Within ``[session]`` (formerly ``[recent]``): key
      ``restore_on_launch`` is renamed to ``load_last``.

    Args:
        config: In-memory ConfigParser to patch in place.

    Returns:
        ``True`` if any change was made (caller should save).
    """
    changed = False
    for old_section, new_section in _LEGACY_SECTION_RENAMES.items():
        if not config.has_section(old_section):
            continue
        if new_section is not None:
            # Ensure destination exists.
            if not config.has_section(new_section):
                config.add_section(new_section)
            # Copy keys that are not already present in the destination.
            for key, value in config.items(old_section):
                if not config.has_option(new_section, key):
                    config.set(new_section, key, value)
        # Remove old section.
        config.remove_section(old_section)
        logger.info("Migrated INI section [%s] → [%s]", old_section, new_section)
        changed = True

    # Rename 'restore_on_launch' key to 'load_last' within [session].
    if config.has_section("session") and config.has_option("session", "restore_on_launch"):
        val = config.get("session", "restore_on_launch")
        if not config.has_option("session", "load_last"):
            config.set("session", "load_last", val)
        config.remove_option("session", "restore_on_launch")
        logger.info("Migrated [session] restore_on_launch → load_last")
        changed = True

    # Remove legacy key 'last_input' from [session] (superceded by last_manifest).
    if config.has_section("session") and config.has_option("session", "last_input"):
        config.remove_option("session", "last_input")
        changed = True

    return changed


def _load_ini() -> configparser.ConfigParser:
    """Load and cache the INI file.

    Returns:
        ConfigParser with loaded INI data.

    Note:
        ``optionxform = str`` is set so that key names are stored verbatim
        (case-preserved).  This is required for preset names like ``Natural``
        in the ``[style]`` and ``[tone]`` sections.

        All sections listed in ``_REQUIRED_SECTIONS`` are guaranteed to exist
        in the returned config.  If any were missing from the file on disk,
        they are added in-memory **and** the file is re-written so that the
        next cold load also sees them.
    """
    global _ini_cache

    if _ini_cache is not None:
        return _ini_cache

    # Ensure required application directories always exist.
    ensure_app_dirs()

    _ini_cache = configparser.ConfigParser()
    # Preserve option-name case (required for preset names such as "Natural").
    _ini_cache.optionxform = str  # type: ignore[method-assign]
    ini_path = get_ini_path()

    try:
        if ini_path.exists():
            _ini_cache.read(ini_path, encoding="utf-8")
            logger.debug("Loaded INI from: %s", ini_path)
        else:
            logger.warning("INI file not found: %s", ini_path)
    except Exception as e:
        logger.error("Failed to load INI file: %s", e)

    # Apply one-time migrations (old section names → new names).
    dirty = _migrate_legacy_sections(_ini_cache)

    # Guarantee required sections exist; persist if any were missing.
    sections_added = _ensure_required_sections(_ini_cache)

    # Seed empty sections from factory defaults (embedded in _FACTORY_DEFAULTS_INI_TEXT).
    populated = _populate_from_defaults(_ini_cache)

    # Seed built-in Python-constant data into [style], [tone],
    # [system_instructions], and [defaults] long-text keys.
    seeded = _seed_builtin_sections(_ini_cache)

    # Fix any corrupted / mis-assigned built-in preset values.
    migrated = _migrate_preset_values(_ini_cache)

    if sections_added or dirty or populated or seeded or migrated:
        _save_ini(_ini_cache)

    return _ini_cache


# Sections in config/defaults.ini that populate CherryAI.ini sections directly.
# Key = section name in defaults.ini → Value = target section in CherryAI.ini.
# Sections matching by identical name are included implicitly.
_DEFAULTS_POPULATE_MAP: Dict[str, str] = {
    "session": "session",
    "caching": "caching",
    "log": "log",
    "limit": "limit",
    "fileio": "fileio",
    "prompts": "prompts",
}


def _populate_from_defaults(config: configparser.ConfigParser) -> bool:
    """Seed empty CherryAI.ini sections from ``_FACTORY_DEFAULTS_INI_TEXT``.

    For every section listed in ``_DEFAULTS_POPULATE_MAP``, if the
    corresponding CherryAI.ini section exists but contains **no keys** yet,
    all key/value pairs from the factory defaults string are written into it.

    The special ``[conditional_prompts]`` section in the factory defaults is
    written into the ``[prompts]`` section of CherryAI.ini under the same
    keys (``dialogue``, ``menu``, ``choice``, ``unknown``).

    Args:
        config: In-memory ConfigParser for CherryAI.ini.

    Returns:
        ``True`` if any key was written (caller should save).
    """
    defaults = _load_defaults_ini()
    changed = False

    # Populate standard sections.
    for src_section, dst_section in _DEFAULTS_POPULATE_MAP.items():
        if not defaults.has_section(src_section):
            continue
        if not config.has_section(dst_section):
            config.add_section(dst_section)
        # Only populate if the target section currently has no user-set keys.
        if len(config.options(dst_section)) == 0:
            for key, value in defaults.items(src_section):
                config.set(dst_section, key, value)
                logger.debug(
                    "Populated [%s].%s from defaults.ini", dst_section, key
                )
            changed = True
            logger.info(
                "Seeded [%s] from defaults.ini [%s]", dst_section, src_section
            )

    # Populate conditional prompts into [prompts] section.
    _COND_KEYS = ("dialogue", "menu", "choice", "unknown")
    if defaults.has_section("conditional_prompts"):
        if not config.has_section("prompts"):
            config.add_section("prompts")
        for key in _COND_KEYS:
            if defaults.has_option("conditional_prompts", key) and not config.has_option(
                "prompts", key
            ):
                value = defaults.get("conditional_prompts", key)
                # Unescape literal \n in INI value to real newline.
                value = value.replace("\\n", "\n")
                config.set("prompts", key, value)
                logger.debug("Populated [prompts].%s from defaults.ini", key)
                changed = True

    return changed


def _seed_builtin_sections(config: configparser.ConfigParser) -> bool:
    """Seed built-in defaults for [style], [tone], [system_instructions], and [defaults].

    Unlike ``_populate_from_defaults`` (which reads from the embedded factory
    defaults INI text), this function seeds rich Python-constant data that is
    not stored in the factory INI text:

    * ``[style]``              — all ``_BUILTIN_STYLE_DEFAULTS`` preset texts (per-key)
    * ``[tone]``               — all ``_BUILTIN_TONE_DEFAULTS`` preset texts (per-key)
    * ``[system_instructions]`` — the built-in ``Default`` system instruction
    * ``[defaults]``           — ``default_style``, ``default_tone``, ``Summary``,
                                  ``SystemInstruction`` (stores preset name, not full text)

    Individual keys are only written when absent; existing user values are
    never overwritten.  Style/tone built-in preset keys are seeded per-key
    so that user-added presets are preserved even when built-in entries are
    missing.

    Args:
        config: In-memory ConfigParser for CherryAI.ini.

    Returns:
        ``True`` if any key was written (caller should save the file).
    """
    changed = False

    # ── [style] preset texts — seed each builtin key individually ────────
    if not config.has_section("style"):
        config.add_section("style")
    for name, text in _BUILTIN_STYLE_DEFAULTS.items():
        if not config.has_option("style", name):
            config.set("style", name, text)
            changed = True
            logger.debug("Seeded [style].%s with built-in text", name)

    # ── [tone] preset texts — seed each builtin key individually ─────────
    if not config.has_section("tone"):
        config.add_section("tone")
    for name, text in _BUILTIN_TONE_DEFAULTS.items():
        if not config.has_option("tone", name):
            config.set("tone", name, text)
            changed = True
            logger.debug("Seeded [tone].%s with built-in text", name)

    # ── [system_instructions] Default key ───────────────────────────────
    if not config.has_section("system_instructions"):
        config.add_section("system_instructions")
    if not config.has_option("system_instructions", "Default"):
        config.set("system_instructions", "Default", _BUILTIN_SYSTEM_INSTRUCTION)
        changed = True
        logger.info("Seeded [system_instructions].Default with built-in text")

    # ── [defaults] long-text and named-default keys ──────────────────────
    # ``SystemInstruction`` stores a *preset name* (e.g. 'Default'), not the
    # full text.  This mirrors how default_style / default_tone work.
    if not config.has_section("defaults"):
        config.add_section("defaults")

    _defaults_seeds: Dict[str, str] = {
        "default_style": "Natural",
        "default_tone": "Neutral",
        "Summary": _BUILTIN_SUMMARY_DEFAULT,
        "SystemInstruction": "Default",  # preset name reference, not full text
    }
    for key, value in _defaults_seeds.items():
        if not config.has_option("defaults", key):
            config.set("defaults", key, value)
            changed = True
            logger.debug("Seeded [defaults].%s = %r", key, value)

    # Migration: if [defaults].SystemInstruction is the full text (i.e. it
    # contains newlines), replace it with the preset name reference.
    if config.has_option("defaults", "SystemInstruction"):
        si_val = config.get("defaults", "SystemInstruction")
        if "\n" in si_val or len(si_val) > 120:
            config.set("defaults", "SystemInstruction", "Default")
            changed = True
            logger.info(
                "Migrated [defaults].SystemInstruction: full text → preset name 'Default'"
            )

    # ── [session] missing keys ───────────────────────────────────────────
    if not config.has_option("session", "last_manifest"):
        config.set("session", "last_manifest", "")
        changed = True
        logger.debug("Seeded [session].last_manifest (empty placeholder)")

    if changed:
        logger.info("Built-in section seeding complete (at least one key written)")
    return changed


def _migrate_preset_values(config: configparser.ConfigParser) -> bool:
    """Fix corrupted or mis-assigned built-in preset values in [style] and [tone].

    Detects when a built-in preset name (e.g. ``Dramatic``) has been stored
    with the text of a *different* built-in preset (e.g. the ``Neutral`` text)
    and restores the correct built-in text.  User-customised values — those
    that are not equal to any other builtin's text — are preserved.

    Args:
        config: In-memory ConfigParser for CherryAI.ini.

    Returns:
        ``True`` if any value was corrected.
    """
    changed = False
    sections: Dict[str, Dict[str, str]] = {
        "style": _BUILTIN_STYLE_DEFAULTS,
        "tone": _BUILTIN_TONE_DEFAULTS,
    }
    for section, builtins in sections.items():
        if not config.has_section(section):
            continue
        all_builtin_texts = set(builtins.values())
        for name, correct_text in builtins.items():
            if not config.has_option(section, name):
                continue
            stored = config.get(section, name)
            if stored == correct_text:
                continue  # Correct — leave it alone.
            # If stored value is exactly another builtin's text, it was
            # mis-assigned during a previous seeding run — fix it.
            other_builtin_texts = all_builtin_texts - {correct_text}
            if stored in other_builtin_texts:
                config.set(section, name, correct_text)
                changed = True
                logger.info(
                    "Fixed mis-assigned [%s].%s (was another preset's text)",
                    section, name,
                )
    return changed


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


def _save_ini(config: configparser.ConfigParser) -> None:
    """Write the config to the INI file on disk.

    Args:
        config: ConfigParser instance to persist.
    """
    ini_path = get_ini_path()
    try:
        ini_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ini_path, "w", encoding="utf-8") as fh:
            config.write(fh)
    except Exception as exc:
        logger.error("Failed to write INI file %s: %s", ini_path, exc)


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
    """Get a manifest default value from [defaults] section.

    Convenience wrapper for manifest-specific defaults.
    The section was previously named ``manifest_defaults``; it is now
    ``defaults`` which also holds style/tone/system-instruction defaults.

    Args:
        key: Configuration key.
        fallback: Default value if key not found.

    Returns:
        Configuration value (type determined by fallback).
    """
    # Infer type from fallback
    if isinstance(fallback, bool):
        return get_bool("defaults", key, fallback)
    elif isinstance(fallback, int):
        return get_int("defaults", key, fallback)
    elif isinstance(fallback, float):
        return get_float("defaults", key, fallback)
    else:
        return get_str("defaults", key, str(fallback) if fallback else "")


def get_all_manifest_defaults() -> Dict[str, Any]:
    """Get all manifest defaults as a typed dictionary.

    Reads all values from [manifest_defaults] section and converts
    to appropriate types based on known schema.

    Note: The [defaults] section also contains non-manifest keys such as
    ``default_style``, ``default_tone``, ``Summary``, and
    ``SystemInstruction``.  These are excluded from the result so that
    manifest tooling only sees manifest-relevant keys.

    Returns:
        Dictionary with all manifest default values.
    """
    # Keys in [defaults] that are NOT manifest settings.
    _non_manifest = frozenset({"default_style", "default_tone", "Summary", "SystemInstruction"})
    raw = {k: v for k, v in get_section("defaults").items() if k not in _non_manifest}
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
        "post_failure_handling": "flag",
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
        "output_file_naming": "subfolder",
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

    Reads [session] last_manifest from INI file.

    Returns:
        Path to last manifest if it exists, None otherwise.
    """
    path_str = get_str("session", "last_manifest", "")
    if not path_str:
        return None
    return Path(path_str)


def set_last_manifest(manifest_path: Optional[Path]) -> bool:
    """Set the last used manifest path in INI.

    Stores as absolute path in [session] last_manifest.

    Args:
        manifest_path: Path to manifest, or None to clear.

    Returns:
        True if successful.
    """
    if manifest_path is None:
        return set_default("session", "last_manifest", "")
    abs_path = manifest_path.resolve()
    return set_default("session", "last_manifest", str(abs_path))


def get_recent_manifests(max_count: int = 10) -> List[Path]:
    """Get list of recently used manifests from INI.

    Reads [session] manifest_history as pipe-separated paths.

    Args:
        max_count: Maximum number of recent manifests to return.

    Returns:
        List of manifest paths (most recent first), filtered to existing files.
    """
    raw = get_str("session", "manifest_history", "")
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

    Args:
        manifest_path: Manifest path to add.

    Returns:
        True if successful.
    """
    abs_path = manifest_path.resolve()
    current = get_recent_manifests(max_count=20)
    current = [p for p in current if p.resolve() != abs_path]
    current.insert(0, abs_path)
    current = current[:10]
    history_str = "|".join(str(p) for p in current)
    return set_default("session", "manifest_history", history_str)


def get_restore_on_launch() -> bool:
    """Check if 'Load last project' is enabled.

    Reads [session] load_last from INI.

    Returns:
        True if restore is enabled (default True).
    """
    return get_bool("session", "load_last", True)


def set_restore_on_launch(enabled: bool) -> bool:
    """Set whether to load last project on launch.

    Args:
        enabled: True to enable loading last project on launch.

    Returns:
        True if successful.
    """
    return set_default("session", "load_last", enabled)


def get_last_input_dir() -> Optional[Path]:
    """Get the last used input directory from INI.

    Reads [session] last_input_dir.

    Returns:
        Path to last input directory if it exists, None otherwise.
    """
    path_str = get_str("session", "last_input_dir", "")
    if not path_str:
        return None
    path = Path(path_str)
    if path.exists() and path.is_dir():
        return path
    return None


def set_last_input_dir(dir_path: Optional[Path]) -> bool:
    """Set the last used input directory in INI.

    Args:
        dir_path: Path to directory, or None to clear.

    Returns:
        True if successful.
    """
    if dir_path is None:
        return set_default("session", "last_input_dir", "")
    abs_path = dir_path.resolve()
    return set_default("session", "last_input_dir", str(abs_path))


# =============================================================================
# User Defaults Management (TASK 31.2)
# =============================================================================


def get_defaults_path() -> Optional[Path]:
    """Return ``None`` — factory defaults are now embedded in ``_FACTORY_DEFAULTS_INI_TEXT``.

    .. deprecated::
        config/defaults.ini no longer exists.  All factory defaults are embedded
        in the ``_FACTORY_DEFAULTS_INI_TEXT`` constant in this module.

    Returns:
        ``None`` (kept for backward-compatibility only).
    """
    return None


def _load_defaults_ini() -> configparser.ConfigParser:
    """Load and cache the factory defaults from the embedded INI text.

    The defaults are no longer read from ``config/defaults.ini``; they live in
    the ``_FACTORY_DEFAULTS_INI_TEXT`` string constant in this module.

    Returns:
        ConfigParser populated with factory defaults.
    """
    global _defaults_cache

    if _defaults_cache is not None:
        return _defaults_cache

    _defaults_cache = configparser.ConfigParser()
    try:
        _defaults_cache.read_string(_FACTORY_DEFAULTS_INI_TEXT)
        logger.debug("Loaded factory defaults from embedded constant")
    except Exception as e:
        logger.error("Failed to parse embedded factory defaults: %s", e)

    return _defaults_cache


def get_initial_default(
    section: str,
    key: str,
    fallback: ConfigValue = None,
    value_type: type = str,
) -> ConfigValue:
    """Get an initial default value from the embedded factory defaults.

    Factory defaults are stored in ``_FACTORY_DEFAULTS_INI_TEXT``.
    Previously read from ``config/defaults.ini`` (removed in Session 25).

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
    """Get all initial defaults for a section from the embedded factory defaults.

    Previously read from ``config/defaults.ini`` (removed in Session 25).

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


# =============================================================================
# Preset Management: [style] and [tone] INI sections
# =============================================================================

# Built-in fallback text for default style/tone presets used when the
# [defaults] section of the INI file is absent or incomplete.
_BUILTIN_STYLE_DEFAULTS: Dict[str, str] = {
    "Literal": (
        "Translate as literally as possible. Preserve the original sentence "
        "structure, word order, and phrasing. Prioritize accuracy over "
        "natural flow in the target language."
    ),
    "Natural": (
        "Translate naturally and fluently. Adapt sentence structure and "
        "phrasing to feel native in the target language while preserving "
        "the original meaning. Prioritize readability."
    ),
    "Creative": (
        "Translate with creative liberty. Adapt idioms, humor, and cultural "
        "references for the target audience. You may rephrase freely to "
        "capture the spirit of the original rather than the exact words."
    ),
    "Formal": (
        "Use a formal, professional register. Choose polished vocabulary "
        "and structured phrasing. Avoid colloquialisms, contractions, and slang."
    ),
    "Casual": (
        "Use an informal, conversational tone. Employ natural contractions, "
        "colloquial expressions, and relaxed phrasing as spoken language."
    ),
    "Technical": (
        "Use precise, technical language. Maintain exact terminology and "
        "avoid ambiguity. Prefer established translations for domain-specific terms."
    ),
    "Literary": (
        "Translate with literary finesse. Use rich vocabulary, varied "
        "sentence rhythm, and artistic phrasing. Preserve poetic devices "
        "and narrative voice."
    ),
}

_BUILTIN_TONE_DEFAULTS: Dict[str, str] = {
    "Neutral": (
        "Maintain a balanced, neutral tone throughout the translation. "
        "Do not add emotional emphasis or dramatic flair beyond what is "
        "present in the source."
    ),
    "Serious": (
        "Convey a grave, solemn atmosphere. Use measured, weighty phrasing "
        "appropriate for serious subject matter."
    ),
    "Humorous": (
        "Preserve and enhance comedic timing and humor. Adapt jokes and "
        "wordplay for the target language while keeping the light-hearted spirit."
    ),
    "Dramatic": (
        "Emphasize dramatic tension and intensity. Use impactful phrasing, "
        "strong verbs, and theatrical delivery to heighten emotional moments."
    ),
    "Lighthearted": (
        "Keep the mood cheerful and upbeat. Use bright, positive language "
        "and breezy phrasing that feels warm and inviting."
    ),
    "Dark": (
        "Convey a grim, ominous atmosphere. Use foreboding language, "
        "heavy imagery, and tense phrasing appropriate for dark themes."
    ),
    "Romantic": (
        "Use warm, emotionally resonant language. Convey tenderness, "
        "affection, and intimacy through gentle phrasing and evocative word choices."
    ),
    "Action": (
        "Use punchy, fast-paced language. Keep sentences short and energetic. "
        "Emphasize motion, impact, and urgency to match action sequences."
    ),
}

_BUILTIN_SYSTEM_INSTRUCTION = (
    "You are an expert translator and localizer.\n"
    "You will be translating any content provided. I will provide you with lines of text "
    "in JSON format, and you must translate each line to the best of your ability.\n"
    "\n"
    "Guidelines:\n"
    "- Do not combine, add, or remove any lines. The number of lines should ALWAYS remain "
    "the same as the original.\n"
    "- Avoid overly literal translations that may seem awkward or confusing; focus on "
    "conveying the intended meaning and spirit.\n"
    "- Use consistent translations for recurring terms, character names, and important "
    "plot elements.\n"
    "- Preserve the emotional undertones and atmosphere, whether comedic, dramatic, "
    "romantic, or suspenseful.\n"
    "- '# Glossary' lists terms including locations and the names, nicknames, and genders "
    "of the game characters. Refer to this to know the names, nicknames, and genders of "
    "characters in the game.\n"
    "- ALWAYS read the translation history BEFORE to figure out the best context for your "
    "translation. This will help you make less mistakes with genders and subjects.\n"
    "- Translate all text to English no exceptions. Double check that everything is "
    "translated.\n"
    "- Avoid using romaji or including any Japanese text in your response.\n"
    "- Always translate the speaker in the line to English.\n"
    "- Maintain any spacing or newlines such as '\\n' or '\\\\n' in the translation.\n"
    "- Never include any notes, explanations, disclaimers, or anything similar in your "
    "response.\n"
    "\n"
    "Output Examples\n"
    "\n"
    "Input (with protected placeholders):\n"
    "{\n"
    '    "Line1": "\u300c\u97f3\u697d\u304c__PROTECTED_0__\u6d41\u308c\u3066\u3044\u307e\u3059\u300d",\n'
    '    "Line2": "\u300c\u305d\u3057\u3066__PROTECTED_1__\u52b9\u679c\u97f3\u3082\u9cf4\u308a\u307e\u3059"\n'
    "}\n"
    "Output (placeholders preserved exactly):\n"
    "{\n"
    '    "Line1": "\\"The music __PROTECTED_0__ is playing.\\"",\n'
    '    "Line2": "\\"And the __PROTECTED_1__ sound effect is also playing.\\""\n'
    "}\n"
    "\n"
    "Input:\n"
    "{\n"
    '    "Line1": "Defense Member E: ...",\n'
    '    "Line2": "Kurone: ...\\\\i[100]",\n'
    '    "Line3": "Kurone: \u3042\u306e\u3055",\n'
    '    "Line4": "Kurone: \\\\v[0]\u304c\u304a\u524d\u306b\u624b\u3092\u713c\u3044\u3066\u308b\u307f\u305f\u3044\u3060\u3063\u305f\u3088",\n'
    '    "Line5": "Kurone: \u4ed6\u306f\u3069\u3046\u3067\u3082\u826f\u3044\u3051\u3069\u3001\\\\n\\"\\\\c[10]\u79c1\u306e\u6a19\u7684\\\\c\\"\u306b\u4f59\u8a08\u306a\u4e8b \u3057\u306a\u3044\u3067\u304f\u308c\u306a\u3044\uff1f",\n'
    '    "Line6": "Kurone: \u6bba\u3059\u3088",\n'
    '    "Line7": "Defense Member E: \u3072\u3063...!\u3082...\u7533\u3057\u8a33\u3054\u30b6\u3044\u307e\u30bb\u3093",\n'
    '    "Line8": "Defense Member E: \\\\SE[\u30e9\u30a4\u30bf\u30fc]\u30af\u30ed\u30cd\u69d8\u306b\u6c38\u4e45\u30cb\u670d\u5f93\u3057\u307e\u30b9\u304b\u3089...\\\\n\\\\c[18]\u3069\u30a6\u304b\u304a\u8a31\u30b7\u3092"\n'
    "}\n"
    "Output:\n"
    "{\n"
    '    "Line1": "Defense Member E: ...",\n'
    '    "Line2": "Kurone: ...\\\\i[100]",\n'
    '    "Line3": "Kurone: Hey.",\n'
    '    "Line4": "Kurone: It seems like \\\\v[0] is having a hard time with you.",\n'
    '    "Line5": "Kurone: I don\'t care about the others,\\\\nbut could you not interfere with \\"\\\\c[10]my target\\\\c\\"?",\n'
    '    "Line6": "Kurone: I\'ll kill you.",\n'
    '    "Line7": "Defense Member E: Eek...! I-\'m so sorry.",\n'
    '    "Line8": "Defense Member E: \\\\SE[\u30e9\u30a4\u30bf\u30fc]I will serve you forever, Kurone-sama...\\\\n\\\\c[18]please forgive me."\n'
    "}"
)

_BUILTIN_SUMMARY_DEFAULT = (
    "Write a short summary of the work here. Mentioning protagonist(s) "
    "and Point of View is not necessary and will be automatically provided."
)


def _get_preset_default(section: str, name: str) -> str:
    """Get the factory-default text for a named style or tone preset.

    First checks the [defaults] section of CherryAI.ini using the key
    ``Style<Name>`` or ``Tone<Name>``, then falls back to built-in constants.

    Args:
        section: ``'style'`` or ``'tone'``.
        name: Preset name (e.g. ``'Natural'``, ``'Neutral'``).

    Returns:
        Default prompt text string.
    """
    cap = section.capitalize()
    ini_key = f"{cap}{name}"
    ini_val = get_str("defaults", ini_key, "")
    if ini_val:
        return ini_val
    if section == "style":
        return _BUILTIN_STYLE_DEFAULTS.get(name, "")
    if section == "tone":
        return _BUILTIN_TONE_DEFAULTS.get(name, "")
    return ""


def get_preset_text(section: str, name: str) -> str:
    """Get the prompt text for a named preset from its INI section.

    Looks up ``name`` in ``[section]`` of CherryAI.ini.  Falls back to the
    factory default from ``[defaults]`` or built-in constants.

    Args:
        section: INI section name — ``'style'`` or ``'tone'``.
        name: Preset display name (case-sensitive).

    Returns:
        Prompt text for the preset.

    Example:
        >>> get_preset_text('style', 'Natural')
        'Translate naturally and fluently...'
    """
    user_val = get_str(section, name, "")
    if user_val:
        return user_val
    return _get_preset_default(section, name)


def set_preset_text(section: str, name: str, text: str) -> bool:
    """Save a preset's prompt text to its INI section.

    Args:
        section: ``'style'`` or ``'tone'``.
        name: Preset display name.
        text: Prompt text to store.

    Returns:
        True on success.

    Example:
        >>> set_preset_text('style', 'MyStyle', 'Very creative...')
        True
    """
    return set_default(section, name, text)


def delete_preset(section: str, name: str) -> bool:
    """Remove a user-defined preset from its INI section.

    Factory-default names (e.g. ``Natural``, ``Neutral``) can be deleted
    from the user INI section; the factory default will then be used again.

    Args:
        section: ``'style'`` or ``'tone'``.
        name: Preset name to delete.

    Returns:
        True if the option existed and was removed.
    """
    config = _load_ini()
    if not config.has_section(section):
        return False
    if not config.has_option(section, name):
        return False
    config.remove_option(section, name)
    _save_ini(config)
    return True


def get_all_presets(section: str) -> Dict[str, str]:
    """Get all available presets for a section, merging defaults and user overrides.

    Factory defaults are listed first (for missing user entries), then any
    user-added extras.  User INI values override factory defaults for the
    same name.

    Args:
        section: ``'style'`` or ``'tone'``.

    Returns:
        Ordered dict: name -> prompt text.  ``'Custom'`` key is included last
        with an empty string.

    Example:
        >>> presets = get_all_presets('style')
        >>> 'Natural' in presets
        True
    """
    if section == "style":
        base: Dict[str, str] = dict(_BUILTIN_STYLE_DEFAULTS)
    elif section == "tone":
        base = dict(_BUILTIN_TONE_DEFAULTS)
    else:
        base = {}

    # Check [defaults] overrides for each built-in name
    for name in list(base.keys()):
        cap = section.capitalize()
        ini_key = f"{cap}{name}"
        ini_val = get_str("defaults", ini_key, "")
        if ini_val:
            base[name] = ini_val

    # Merge [style] / [tone] user overrides
    user_entries = get_section(section)
    for name, text in user_entries.items():
        # Key case is preserved (optionxform = str) so use name directly.
        base[name] = text

    # Build ordered result: sorted alphabetical, Custom last
    result: Dict[str, str] = {}
    for name in sorted(base):
        if name.lower() != "custom":
            result[name] = base[name]
    result["Custom"] = ""
    return result


# =============================================================================
# Long-text defaults management: [defaults] section
# =============================================================================


def get_default_text(key: str, fallback: str = "") -> str:
    """Get a long-text default value from the [defaults] section.

    Suitable for multi-line values (system instructions, summary, etc.).
    Falls back to built-in constants if not found in INI.

    For the ``'SystemInstruction'`` key the stored value is treated as a
    *preset name* (e.g. ``'Default'``) rather than the literal text.  The
    actual text is resolved via :func:`get_si_preset`.  If the stored value
    is multi-line (legacy full-text), it is returned directly for backward
    compatibility.

    Args:
        key: Key in [defaults] section (e.g. ``'SystemInstruction'``).
        fallback: Value returned if key absent in INI and no built-in exists.

    Returns:
        Text value.

    Example:
        >>> get_default_text('SystemInstruction')
        'You are an expert translator...'
    """
    val = get_str("defaults", key, "")
    if key == "SystemInstruction":
        if val:
            # Short value with no newlines = a preset name reference.
            if "\n" not in val and len(val) <= 120:
                resolved = get_si_preset(val)
                return resolved if resolved else _BUILTIN_SYSTEM_INSTRUCTION
            # Multi-line = legacy full text stored directly; return as-is.
            return val
        return _BUILTIN_SYSTEM_INSTRUCTION
    if val:
        return val
    # Built-in constants for other keys.
    if key == "Summary":
        return _BUILTIN_SUMMARY_DEFAULT
    return fallback


def set_default_text(key: str, value: str) -> bool:
    """Save a long-text default value to the [defaults] section.

    Args:
        key: Key in [defaults] section.
        value: Text to store.

    Returns:
        True on success.
    """
    return set_default("defaults", key, value)


def restore_preset_defaults(section: str) -> bool:
    """Remove all user overrides from a preset section to restore factory defaults.

    Args:
        section: ``'style'`` or ``'tone'``.

    Returns:
        True on success.
    """
    return remove_section(section)


# =============================================================================
# Default tone / style helpers  [defaults] section
# =============================================================================


def get_default_style() -> str:
    """Get the default style preset name from [defaults].

    Returns:
        Preset name string (default ``'Natural'``).
    """
    return get_str("defaults", "default_style", "Natural")


def set_default_style(name: str) -> bool:
    """Set the default style preset name in [defaults].

    Args:
        name: Preset name to use as default.

    Returns:
        True on success.
    """
    return set_default("defaults", "default_style", name)


def get_default_tone() -> str:
    """Get the default tone preset name from [defaults].

    Returns:
        Preset name string (default ``'Neutral'``).
    """
    return get_str("defaults", "default_tone", "Neutral")


def set_default_tone(name: str) -> bool:
    """Set the default tone preset name in [defaults].

    Args:
        name: Preset name to use as default.

    Returns:
        True on success.
    """
    return set_default("defaults", "default_tone", name)


# =============================================================================
# System Instructions Presets  [system_instructions] section
# =============================================================================


def get_si_preset(name: str) -> str:
    """Get a System Instructions preset from [system_instructions].

    Falls back to the built-in default content for the ``'Default'`` preset.

    Args:
        name: Preset name (case-sensitive).

    Returns:
        Preset text, or empty string if not found.
    """
    val = get_str("system_instructions", name, "")
    if val:
        return val
    if name == "Default":
        return _BUILTIN_SYSTEM_INSTRUCTION
    return ""


def set_si_preset(name: str, text: str) -> bool:
    """Save a System Instructions preset to [system_instructions].

    Args:
        name: Preset name.
        text: System instruction text.

    Returns:
        True on success.
    """
    return set_default("system_instructions", name, text)


def delete_si_preset(name: str) -> bool:
    """Remove a user SI preset (cannot delete 'Default').

    Args:
        name: Preset name to remove.

    Returns:
        True if it existed and was removed.
    """
    if name == "Default":
        return False
    config = _load_ini()
    if not config.has_section("system_instructions"):
        return False
    if not config.has_option("system_instructions", name):
        return False
    config.remove_option("system_instructions", name)
    _save_ini(config)
    return True


def get_all_si_presets() -> Dict[str, str]:
    """Get all System Instructions presets merged with built-in defaults.

    Returns:
        Ordered dict: ``Custom`` first, then ``Default``, then user presets
        alphabetically.
    """
    merged: Dict[str, str] = {"Default": _BUILTIN_SYSTEM_INSTRUCTION}
    user_entries = get_section("system_instructions")
    for name, text in user_entries.items():
        if text:
            merged[name] = text

    result: Dict[str, str] = {"Custom": ""}
    if "Default" in merged:
        result["Default"] = merged["Default"]
    for name in sorted(merged):
        if name.lower() != "custom" and name != "Default":
            result[name] = merged[name]
    return result


def migrate_si_presets_from_json(json_path: Path) -> bool:
    """Import System Instructions presets from a legacy JSON file.

    Reads the JSON, writes each entry to [system_instructions], and
    optionally renames the file to ``*.migrated`` when done.

    Args:
        json_path: Path to the legacy JSON presets file.

    Returns:
        True if migration succeeded (or file did not exist).
    """
    import json

    if not json_path.exists():
        return True
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        for name, text in data.items():
            if name and isinstance(text, str) and name.lower() != "custom":
                set_si_preset(name, text)
        # Mark as migrated so future runs skip it.
        migrated_path = json_path.with_suffix(".json.migrated")
        json_path.rename(migrated_path)
        logger.info("Migrated SI presets from %s \u2192 INI", json_path)
        return True
    except Exception as exc:
        logger.warning("SI presets JSON migration failed: %s", exc)
        return False


# =============================================================================
# Global Options section helpers (caching / limit / prompts / log / fileio)
# These thin wrappers give callers a typed API for the new INI sections.
# =============================================================================


def get_caching_setting(key: str, fallback: Any = None) -> Any:
    """Read a value from the [caching] section."""
    if isinstance(fallback, bool):
        return get_bool("caching", key, fallback)
    if isinstance(fallback, int):
        return get_int("caching", key, fallback)
    return get_str("caching", key, str(fallback) if fallback is not None else "")


def set_caching_setting(key: str, value: Any) -> bool:
    """Write a value to the [caching] section."""
    return set_default("caching", key, value)


def get_limit_setting(key: str, fallback: Any = None) -> Any:
    """Read a value from the [limit] section (was 'safety')."""
    if isinstance(fallback, bool):
        return get_bool("limit", key, fallback)
    if isinstance(fallback, int):
        return get_int("limit", key, fallback)
    return get_str("limit", key, str(fallback) if fallback is not None else "")


def set_limit_setting(key: str, value: Any) -> bool:
    """Write a value to the [limit] section."""
    return set_default("limit", key, value)


def get_prompts_setting(key: str, fallback: Any = None) -> Any:
    """Read a value from the [prompts] section."""
    if isinstance(fallback, bool):
        return get_bool("prompts", key, fallback)
    if isinstance(fallback, int):
        return get_int("prompts", key, fallback)
    return get_str("prompts", key, str(fallback) if fallback is not None else "")


def set_prompts_setting(key: str, value: Any) -> bool:
    """Write a value to the [prompts] section."""
    return set_default("prompts", key, value)


def get_log_setting(key: str, fallback: Any = None) -> Any:
    """Read a value from the [log] section."""
    if isinstance(fallback, bool):
        return get_bool("log", key, fallback)
    if isinstance(fallback, int):
        return get_int("log", key, fallback)
    return get_str("log", key, str(fallback) if fallback is not None else "")


def set_log_setting(key: str, value: Any) -> bool:
    """Write a value to the [log] section."""
    return set_default("log", key, value)


def get_fileio_setting(key: str, fallback: Any = None) -> Any:
    """Read a value from the [fileio] section."""
    if isinstance(fallback, bool):
        return get_bool("fileio", key, fallback)
    if isinstance(fallback, int):
        return get_int("fileio", key, fallback)
    return get_str("fileio", key, str(fallback) if fallback is not None else "")


def set_fileio_setting(key: str, value: Any) -> bool:
    """Write a value to the [fileio] section."""
    return set_default("fileio", key, value)


def get_security_setting(key: str, fallback: Any = None) -> Any:
    """Read a value from the [security] section."""
    if isinstance(fallback, bool):
        return get_bool("security", key, fallback)
    return get_str("security", key, str(fallback) if fallback is not None else "")


def set_security_setting(key: str, value: Any) -> bool:
    """Write a value to the [security] section."""
    return set_default("security", key, value)


def get_session_setting(key: str, fallback: Any = None) -> Any:
    """Read a value from the [session] section."""
    if isinstance(fallback, bool):
        return get_bool("session", key, fallback)
    if isinstance(fallback, int):
        return get_int("session", key, fallback)
    return get_str("session", key, str(fallback) if fallback is not None else "")


def set_session_setting(key: str, value: Any) -> bool:
    """Write a value to the [session] section."""
    return set_default("session", key, value)


# ---------------------------------------------------------------------------
# Conditional Prompt helpers (Dialogue / Menu / Choice / Unknown)
# ---------------------------------------------------------------------------

#: Factory-default prompts used when nothing is stored in CherryAI.ini.
_CONDITIONAL_PROMPT_DEFAULTS: Dict[str, str] = {
    "dialogue": (
        "# Content Type: Dialogue\n"
        "These lines are character dialogue. "
        "Pay attention to the speaker names, maintain consistent voice and tone "
        "for each character, and preserve emotional nuances in the conversation."
    ),
    "menu": (
        "# Content Type: Menu\n"
        "These lines are menu items from a game UI. "
        "Translate each item concisely and clearly. Preserve formatting, order, "
        "and any shortcut indicators. Keep translations brief and action-oriented."
    ),
    "choice": (
        "# Content Type: Choices\n"
        "These lines are player choices or options. "
        "Translate each choice concisely and distinctly so the player can "
        "differentiate between options. Preserve numbering or bullet formatting."
    ),
    "unknown": (
        "# Content Type: Mixed\n"
        "These lines may contain dialogue, menu items, or choices. "
        "Translate each line appropriately based on its apparent purpose. "
        "Maintain formatting and keep menu/choice items concise."
    ),
}


def get_conditional_prompt(context_type: str, fallback: str = "") -> str:
    """Return the configurable context-type prompt from ``[prompts]``.

    Falls back to the factory default if no override is stored.

    Args:
        context_type: One of ``"dialogue"``, ``"menu"``, ``"choice"``,
            ``"unknown"``.
        fallback: Value returned when context_type is unrecognised **and**
            no factory default exists.

    Returns:
        Prompt text (may be empty string if context_type is unknown).
    """
    factory = _CONDITIONAL_PROMPT_DEFAULTS.get(context_type, fallback)
    stored = get_str("prompts", context_type, "")
    return stored if stored else factory


def set_conditional_prompt(context_type: str, value: str) -> bool:
    """Persist a context-type prompt override to ``[prompts]``.

    Args:
        context_type: One of ``"dialogue"``, ``"menu"``, ``"choice"``,
            ``"unknown"``.
        value: New prompt text.  Pass empty string to revert to factory default.

    Returns:
        ``True`` if the value was saved successfully.
    """
    return set_default("prompts", context_type, value)
