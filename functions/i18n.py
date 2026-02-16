"""Internationalization (i18n) module for CherryAI (TASK 17.10).

Provides a simple translation system that:
- Loads language files (JSON key→value maps) from user/lang/
- Exposes a t(key) function that returns the localized string
- Falls back to English for missing keys in other languages
- Supports placeholder interpolation via str.format()

Usage:
    from CherryAI.functions.i18n import t, set_language, get_language

    label_text = t("step.input.title")                     # "Input & Extract"
    msg = t("status.lines_loaded", count=42)               # "Loaded 42 lines"
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LANGUAGE = "en"

# Language display names (code → human-readable)
LANGUAGE_NAMES: Dict[str, str] = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "ja": "日本語",
    "zh": "中文",
    "ko": "한국어",
    "pt": "Português",
    "ru": "Русский",
    "it": "Italiano",
}

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_current_language: str = DEFAULT_LANGUAGE
_strings: Dict[str, str] = {}          # Active language strings
_fallback_strings: Dict[str, str] = {} # English fallback
_lang_dir: Optional[Path] = None       # Resolved lang directory


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init(root: Optional[Path] = None, language: str = DEFAULT_LANGUAGE) -> None:
    """Initialize the i18n system.

    Args:
        root: Project root directory. If None, auto-detects.
        language: Language code to load (e.g., 'en', 'de').
    """
    global _lang_dir
    if root is not None:
        _lang_dir = root / "user" / "lang"
    elif _lang_dir is None:
        _lang_dir = _detect_lang_dir()

    _load_fallback()
    set_language(language)


def t(key: str, **kwargs: Any) -> str:
    """Translate a key to the current language.

    Args:
        key: Dot-separated translation key (e.g., 'step.input.title').
        **kwargs: Format arguments for interpolation.

    Returns:
        Localized string, or the key itself if not found in any language.
    """
    # Try current language first, then fallback to English
    text = _strings.get(key) or _fallback_strings.get(key) or key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass  # Return unformatted if interpolation fails

    return text


def set_language(code: str) -> None:
    """Switch the active language.

    Args:
        code: Language code (e.g., 'en', 'de').
    """
    global _current_language, _strings
    _current_language = code
    if code == DEFAULT_LANGUAGE:
        _strings = _fallback_strings.copy()
    else:
        _strings = _load_language_file(code)
    logger.info("Language set to: %s", code)


def get_language() -> str:
    """Return the current language code."""
    return _current_language


def get_available_languages() -> List[Dict[str, str]]:
    """List available languages found in user/lang/.

    Returns:
        List of dicts with 'code' and 'name' keys, sorted by name.
    """
    if _lang_dir is None or not _lang_dir.exists():
        return [{"code": "en", "name": "English"}]

    langs: List[Dict[str, str]] = []
    for f in sorted(_lang_dir.glob("*.json")):
        code = f.stem
        name = LANGUAGE_NAMES.get(code, code)
        langs.append({"code": code, "name": name})

    if not langs:
        langs.append({"code": "en", "name": "English"})

    return langs


def get_language_name(code: str) -> str:
    """Get human-readable name for a language code.

    Args:
        code: Language code (e.g., 'de').

    Returns:
        Human-readable name (e.g., 'Deutsch'), or the code if unknown.
    """
    return LANGUAGE_NAMES.get(code, code)


def has_key(key: str) -> bool:
    """Check if a translation key exists in any loaded language."""
    return key in _strings or key in _fallback_strings


def translation_count() -> int:
    """Return number of keys in the current language."""
    return len(_strings)


def missing_keys() -> List[str]:
    """Return English keys not present in the current language.

    Useful for finding untranslated strings.
    """
    if _current_language == DEFAULT_LANGUAGE:
        return []
    return sorted(k for k in _fallback_strings if k not in _strings)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_lang_dir() -> Path:
    """Auto-detect the lang directory relative to this module."""
    here = Path(__file__).resolve().parent  # functions/
    return here.parent / "user" / "lang"


def _load_fallback() -> None:
    """Load English strings as the fallback language."""
    global _fallback_strings
    _fallback_strings = _load_language_file(DEFAULT_LANGUAGE)


def _load_language_file(code: str) -> Dict[str, str]:
    """Load a language JSON file and return its key→value map.

    Args:
        code: Language code (e.g., 'en', 'de').

    Returns:
        Dictionary of translation strings, or empty dict if file missing.
    """
    if _lang_dir is None:
        return {}

    path = _lang_dir / f"{code}.json"
    if not path.exists():
        if code != DEFAULT_LANGUAGE:
            logger.debug("Language file not found: %s", path)
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("Language file %s is not a JSON object", path)
            return {}
        # Flatten nested dicts if present
        return _flatten_dict(data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load language file %s: %s", path, exc)
        return {}


def _flatten_dict(
    data: Dict[str, Any],
    prefix: str = "",
    sep: str = ".",
) -> Dict[str, str]:
    """Flatten a nested dict into dot-separated keys.

    Example:
        {"step": {"input": {"title": "Input"}}}
        → {"step.input.title": "Input"}
    """
    result: Dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}{sep}{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_dict(value, full_key, sep))
        else:
            result[full_key] = str(value)
    return result
