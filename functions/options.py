"""API provider definitions and option helpers for CherryAI.

Single source of truth for API_PROVIDERS configuration.
Safe dependency chain: options.py → config.py → languages.py → stdlib only

NOTE: The options dialog UI moved to gui/dialogs/global_options.py (GlobalOptionsDialog).
This module now only provides:
- API_PROVIDERS constant (canonical provider definitions)
- Provider helper functions
- get_api_settings_summary()
"""

from __future__ import annotations

from typing import Any, Dict, List

from .config import get_api_config
from .languages import get_language_names


# =============================================================================
# API PROVIDERS - SINGLE SOURCE OF TRUTH
# =============================================================================

# Supported API providers with their default base URLs and models
# This is the canonical definition - import from here, don't duplicate!
API_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    },
    "local": {
        "name": "Local/Custom",
        "base_url": "http://localhost:11434/v1",
        "models": ["local-model", "custom"],
    },
    "ollama": {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3", "mistral", "codellama"],
    },
    "lmstudio": {
        "name": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "models": ["local-model"],
    },
}


def get_api_urls() -> Dict[str, str]:
    """Get mapping of provider keys to base URLs.

    Returns:
        Dict mapping provider key to base URL string.
        Compatible with CLI.py KNOWN_API_URLS format.
    """
    return {key: info["base_url"] for key, info in API_PROVIDERS.items()}


def get_provider_models(provider: str) -> List[str]:
    """Get list of models for a specific provider.

    Args:
        provider: Provider key (e.g., 'openai', 'gemini').

    Returns:
        List of model names for the provider, or empty list if not found.
    """
    if provider in API_PROVIDERS:
        return API_PROVIDERS[provider].get("models", [])
    return []


def get_all_provider_models() -> Dict[str, List[str]]:
    """Get mapping of all providers to their models.

    Returns:
        Dict mapping provider key to list of model names.
        Compatible with CLI.py KNOWN_MODELS format.
    """
    return {key: info["models"] for key, info in API_PROVIDERS.items()}


def get_provider_names() -> List[str]:
    """Get list of all provider keys.

    Returns:
        List of provider key strings.
    """
    return list(API_PROVIDERS.keys())


def get_provider_display_name(provider: str) -> str:
    """Get display name for a provider.

    Args:
        provider: Provider key (e.g., 'openai').

    Returns:
        Human-readable provider name, or the key if not found.
    """
    if provider in API_PROVIDERS:
        return API_PROVIDERS[provider].get("name", provider)
    return provider

# Supported languages for translation
# Imported from languages.py - single source of truth
SUPPORTED_LANGUAGES: List[str] = get_language_names()


# NOTE: OptionsDialog class and open_options_dialog were deprecated and removed.
# The GUI now uses gui/dialogs/global_options.py → GlobalOptionsDialog.
# This module now only provides API_PROVIDERS and helper functions.


def get_api_settings_summary() -> str:
    """Get a brief summary of current API settings for display.

    Returns:
        String summarizing provider, model, and key status.
    """
    config = get_api_config()
    provider = config.get("provider", "openai")
    model = config.get("model", "unknown")
    has_key = bool(config.get("api_key", "").strip())
    key_status = "configured" if has_key else "NOT SET"
    return f"{provider}/{model} (Key: {key_status})"
