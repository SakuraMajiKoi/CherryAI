"""Language definitions and utilities for CherryAI.

This module provides a single source of truth for all supported languages,
including language codes, names, native names, and aliases.

Used by both CLI and GUI for consistent language handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Language:
    """Represents a supported language with all metadata.
    
    Attributes:
        code: ISO 639-1 or BCP 47 code (e.g., 'ja', 'zh-CN')
        name: English display name (e.g., 'Japanese')
        native: Native name (e.g., '日本語')
        aliases: Alternative codes/names for lookup
        description: Human-readable description
    """
    code: str
    name: str
    native: str
    aliases: tuple[str, ...]
    description: str = ""
    
    def matches(self, query: str) -> bool:
        """Check if query matches this language (code, name, or alias).
        
        Args:
            query: Search string (case-insensitive)
            
        Returns:
            True if query matches code, name, native name, or any alias.
        """
        q = query.strip().lower()
        if q == self.code.lower():
            return True
        if q == self.name.lower():
            return True
        if q == self.native.lower():
            return True
        return q in (a.lower() for a in self.aliases)


# =============================================================================
# CANONICAL LANGUAGE REGISTRY
# =============================================================================

# All supported languages with full metadata
# This is the single source of truth for language information
LANGUAGES: Dict[str, Language] = {
    "ja": Language(
        code="ja",
        name="Japanese",
        native="日本語",
        aliases=("jp", "jpn", "japanese"),
        description="Japanese - East Asian language with kanji, hiragana, katakana",
    ),
    "en": Language(
        code="en",
        name="English",
        native="English",
        aliases=("eng", "english"),
        description="English - Germanic language, most common target for localization",
    ),
    "zh-CN": Language(
        code="zh-CN",
        name="Chinese (Simplified)",
        native="简体中文",
        aliases=("zh_cn", "chinese", "chinese-simplified", "simplified", "zhs"),
        description="Simplified Chinese - Used in mainland China",
    ),
    "zh-TW": Language(
        code="zh-TW",
        name="Chinese (Traditional)",
        native="繁體中文",
        aliases=("zh_tw", "traditional", "chinese-traditional", "zht"),
        description="Traditional Chinese - Used in Taiwan, Hong Kong",
    ),
    "ko": Language(
        code="ko",
        name="Korean",
        native="한국어",
        aliases=("kor", "korean"),
        description="Korean - East Asian language with hangul script",
    ),
    "es": Language(
        code="es",
        name="Spanish",
        native="Español",
        aliases=("spa", "spanish", "español"),
        description="Spanish - Romance language, second most spoken native language",
    ),
    "fr": Language(
        code="fr",
        name="French",
        native="Français",
        aliases=("fra", "fre", "french", "français"),
        description="French - Romance language spoken in France and worldwide",
    ),
    "de": Language(
        code="de",
        name="German",
        native="Deutsch",
        aliases=("deu", "ger", "german", "deutsch"),
        description="German - West Germanic language spoken in Central Europe",
    ),
    "pt": Language(
        code="pt",
        name="Portuguese",
        native="Português",
        aliases=("por", "portuguese", "português"),
        description="Portuguese - Romance language spoken in Portugal and Brazil",
    ),
    "ru": Language(
        code="ru",
        name="Russian",
        native="Русский",
        aliases=("rus", "russian", "русский"),
        description="Russian - East Slavic language with Cyrillic script",
    ),
    "it": Language(
        code="it",
        name="Italian",
        native="Italiano",
        aliases=("ita", "italian", "italiano"),
        description="Italian - Romance language spoken in Italy",
    ),
    "ar": Language(
        code="ar",
        name="Arabic",
        native="العربية",
        aliases=("ara", "arabic"),
        description="Arabic - Semitic language with right-to-left script",
    ),
    "th": Language(
        code="th",
        name="Thai",
        native="ภาษาไทย",
        aliases=("tha", "thai"),
        description="Thai - Tai language with unique Thai script",
    ),
    "vi": Language(
        code="vi",
        name="Vietnamese",
        native="Tiếng Việt",
        aliases=("vie", "vietnamese"),
        description="Vietnamese - Austroasiatic language with Latin script",
    ),
}


# =============================================================================
# ACCESSOR FUNCTIONS
# =============================================================================

def get_language_names() -> List[str]:
    """Get list of all language display names.
    
    Returns:
        List of language names (e.g., ['Japanese', 'English', ...])
        sorted alphabetically.
    
    Example:
        >>> names = get_language_names()
        >>> 'Japanese' in names
        True
    """
    return sorted(lang.name for lang in LANGUAGES.values())


def get_language_codes() -> List[str]:
    """Get list of all language codes.
    
    Returns:
        List of language codes (e.g., ['ja', 'en', 'zh-CN', ...])
        sorted alphabetically.
    """
    return sorted(LANGUAGES.keys())


def get_language_by_code(code: str) -> Optional[Language]:
    """Get language by its canonical code.
    
    Args:
        code: Language code (e.g., 'ja', 'zh-CN')
        
    Returns:
        Language object if found, None otherwise.
        
    Example:
        >>> lang = get_language_by_code('ja')
        >>> lang.name
        'Japanese'
    """
    return LANGUAGES.get(code)


def get_language_by_name(name: str) -> Optional[Language]:
    """Get language by its English display name.
    
    Args:
        name: Language name (e.g., 'Japanese', case-insensitive)
        
    Returns:
        Language object if found, None otherwise.
        
    Example:
        >>> lang = get_language_by_name('Japanese')
        >>> lang.code
        'ja'
    """
    name_lower = name.strip().lower()
    for lang in LANGUAGES.values():
        if lang.name.lower() == name_lower:
            return lang
    return None


def get_language_by_alias(alias: str) -> Optional[Language]:
    """Get language by any alias, code, or name.
    
    This is the most flexible lookup - it checks:
    1. Canonical code (e.g., 'ja')
    2. English name (e.g., 'Japanese')
    3. Native name (e.g., '日本語')
    4. All aliases (e.g., 'jp', 'jpn', 'japanese')
    
    Args:
        alias: Any identifier for the language (case-insensitive)
        
    Returns:
        Language object if found, None otherwise.
        
    Example:
        >>> get_language_by_alias('jp').code
        'ja'
        >>> get_language_by_alias('Japanese').code
        'ja'
        >>> get_language_by_alias('日本語').code
        'ja'
    """
    # First try direct code lookup (fast path)
    if alias in LANGUAGES:
        return LANGUAGES[alias]
    
    # Normalize and search
    alias_lower = alias.strip().lower()
    
    # Try case-insensitive code match first
    for code, lang in LANGUAGES.items():
        if code.lower() == alias_lower:
            return lang
    
    # Search through all languages
    for lang in LANGUAGES.values():
        if lang.matches(alias):
            return lang
    
    return None


def normalize_language_code(code: str) -> Optional[str]:
    """Normalize any language identifier to canonical code.
    
    Args:
        code: Language code, name, or alias (case-insensitive)
        
    Returns:
        Canonical language code (e.g., 'ja') or None if unknown.
        
    Example:
        >>> normalize_language_code('japanese')
        'ja'
        >>> normalize_language_code('JP')
        'ja'
        >>> normalize_language_code('日本語')
        'ja'
    """
    lang = get_language_by_alias(code)
    return lang.code if lang else None


def get_language_name_from_code(code: str) -> str:
    """Get the display name for a language code.
    
    Args:
        code: Language code or alias
        
    Returns:
        Display name if found, original code if unknown.
        
    Example:
        >>> get_language_name_from_code('ja')
        'Japanese'
        >>> get_language_name_from_code('unknown')
        'unknown'
    """
    lang = get_language_by_alias(code)
    return lang.name if lang else code


def get_language_dict() -> Dict[str, Dict[str, str]]:
    """Get dictionary format for CLI compatibility.
    
    Returns:
        Dictionary mapping code to {name, native, description}.
        
    Example:
        >>> d = get_language_dict()
        >>> d['ja']['name']
        'Japanese'
    """
    return {
        lang.code: {
            "name": lang.name,
            "native": lang.native,
            "description": lang.description,
        }
        for lang in LANGUAGES.values()
    }


def build_language_aliases() -> Dict[str, str]:
    """Build aliases lookup dictionary for CLI compatibility.
    
    Returns:
        Dictionary mapping all aliases to canonical codes.
        
    Example:
        >>> aliases = build_language_aliases()
        >>> aliases['japanese']
        'ja'
        >>> aliases['jp']
        'ja'
    """
    result: Dict[str, str] = {}
    for lang in LANGUAGES.values():
        # Add canonical code
        result[lang.code.lower()] = lang.code
        # Add all aliases
        for alias in lang.aliases:
            result[alias.lower()] = lang.code
    return result


# Pre-built alias lookup for performance
_LANGUAGE_ALIASES: Dict[str, str] = build_language_aliases()


def is_valid_language(identifier: str) -> bool:
    """Check if an identifier is a valid language code, name, or alias.
    
    Args:
        identifier: Any string to check
        
    Returns:
        True if it refers to a supported language.
        
    Example:
        >>> is_valid_language('Japanese')
        True
        >>> is_valid_language('Klingon')
        False
    """
    return get_language_by_alias(identifier) is not None


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Core class
    "Language",
    # Registry
    "LANGUAGES",
    # Accessor functions
    "get_language_names",
    "get_language_codes",
    "get_language_by_code",
    "get_language_by_name",
    "get_language_by_alias",
    "normalize_language_code",
    "get_language_name_from_code",
    "get_language_dict",
    "build_language_aliases",
    "is_valid_language",
]
