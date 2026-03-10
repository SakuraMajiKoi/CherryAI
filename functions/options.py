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

from typing import Any, Dict, List, Optional

from .config import get_api_config
from .languages import get_language_names


# =============================================================================
# API PROVIDERS - SINGLE SOURCE OF TRUTH
# =============================================================================

# Static providers whose model lists are NOT fetched from the cloud.
# Local / self-hosted providers keep their hardcoded model defaults.
_STATIC_PROVIDERS: Dict[str, Dict[str, Any]] = {
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

# Cloud providers whose model lists are fetched dynamically via model_registry.
# Provider keys here map to model_registry provider IDs.
_CLOUD_PROVIDER_META: Dict[str, Dict[str, str]] = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "registry_id": "openai",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "registry_id": "google",
    },
    "mistral": {
        "name": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "registry_id": "mistral",
    },
}


def _build_api_providers() -> Dict[str, Dict[str, Any]]:
    """Build the full API_PROVIDERS dict, pulling cloud model lists from the registry.

    Falls back to built-in model lists if the registry is unavailable.
    Integrates with ProviderRegistry when available (V7 Provider Handshake).
    """
    # Try ProviderRegistry first — it knows all registered providers
    try:
        from providers import ProviderRegistry
        pr_providers = ProviderRegistry.all()
    except Exception:
        pr_providers = []

    providers: Dict[str, Dict[str, Any]] = {}

    if pr_providers:
        # ProviderRegistry is available — build from registered providers
        # Map provider names to options.py keys
        _NAME_TO_KEY = {
            "openai": "openai",
            "google": "gemini",
            "mistral": "mistral",
            "anthropic": "anthropic",
            "local": "local",
            "lmstudio": "lmstudio",
            "ollama": "ollama",
        }

        try:
            from .model_registry import get_provider_model_ids
        except Exception:
            get_provider_model_ids = None  # type: ignore[assignment]

        for p in pr_providers:
            key = _NAME_TO_KEY.get(p.name, p.name)

            # Get model list: try model_registry for cloud providers
            # Map options key to registry provider ID
            _KEY_TO_REGISTRY = {
                "openai": "openai", "gemini": "google", "mistral": "mistral",
            }
            rid = _KEY_TO_REGISTRY.get(key)
            models: List[str] = []
            if rid and get_provider_model_ids is not None:
                try:
                    models = get_provider_model_ids(rid)
                except Exception:
                    pass
            if not models:
                # Fallback to hardcoded lists
                if key in _CLOUD_FALLBACK_MODELS:
                    models = _CLOUD_FALLBACK_MODELS[key]
                elif key in _STATIC_PROVIDERS:
                    models = _STATIC_PROVIDERS[key].get("models", [])

            providers[key] = {
                "name": p.display_name,
                "base_url": p.base_url,
                "models": models,
            }
        return providers

    # Legacy fallback: ProviderRegistry not available
    try:
        from .model_registry import (
            get_provider_model_ids,
            PROVIDER_OPENAI,
            PROVIDER_GOOGLE,
            PROVIDER_MISTRAL,
        )
        _registry_map = {
            "openai": PROVIDER_OPENAI,
            "gemini": PROVIDER_GOOGLE,
            "mistral": PROVIDER_MISTRAL,
        }
    except Exception:
        _registry_map = {}

    # Cloud providers — dynamic model lists
    for pkey, meta in _CLOUD_PROVIDER_META.items():
        rid = _registry_map.get(pkey)
        if rid:
            try:
                models = get_provider_model_ids(rid)  # type: ignore[name-defined]
                if not models:
                    raise ValueError("empty")
            except Exception:
                models = _CLOUD_FALLBACK_MODELS.get(pkey, [])
        else:
            models = _CLOUD_FALLBACK_MODELS.get(pkey, [])
        providers[pkey] = {
            "name": meta["name"],
            "base_url": meta["base_url"],
            "models": models,
        }

    # Static providers — unchanged
    providers.update(_STATIC_PROVIDERS)
    return providers


# Minimal hardcoded fallback model lists for cloud providers,
# used when the registry module itself cannot be imported.
_CLOUD_FALLBACK_MODELS: Dict[str, List[str]] = {
    "openai": [
        "gpt-4.1", "gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano",
        "gpt-5-mini", "o3", "o4-mini",
        "gpt-5", "gpt-5.1", "gpt-5.2", "gpt-5-nano",
    ],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
    "mistral": ["mistral-large-latest", "mistral-small-latest", "ministral-8b-latest"],
}


# Module-level cache — rebuilt lazily on first access.
_API_PROVIDERS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _get_api_providers() -> Dict[str, Dict[str, Any]]:
    global _API_PROVIDERS_CACHE
    if _API_PROVIDERS_CACHE is None:
        _API_PROVIDERS_CACHE = _build_api_providers()
    return _API_PROVIDERS_CACHE


def reload_api_providers() -> None:
    """Force the API_PROVIDERS cache to rebuild on next access.

    Call this after ``model_registry.refresh_models()`` so that provider
    model lists immediately reflect the newly-fetched data.
    """
    global _API_PROVIDERS_CACHE
    _API_PROVIDERS_CACHE = None


class _APIProvidersProxy(dict):
    """Transparent proxy so ``from options import API_PROVIDERS`` stays valid."""

    def _sync(self) -> None:
        fresh = _get_api_providers()
        self.clear()
        self.update(fresh)

    def __contains__(self, key: object) -> bool:
        self._sync(); return super().__contains__(key)

    def __getitem__(self, key: Any) -> Any:
        self._sync(); return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:  # type: ignore[override]
        self._sync(); return super().get(key, default)

    def keys(self) -> Any:
        self._sync(); return super().keys()

    def values(self) -> Any:
        self._sync(); return super().values()

    def items(self) -> Any:
        self._sync(); return super().items()

    def __iter__(self) -> Any:
        self._sync(); return super().__iter__()

    def __len__(self) -> int:
        self._sync(); return super().__len__()


# Public constant — backward-compatible, dynamically populated
API_PROVIDERS: Dict[str, Dict[str, Any]] = _APIProvidersProxy()


def get_api_urls() -> Dict[str, str]:
    """Get mapping of provider keys to base URLs.

    Returns:
        Dict mapping provider key to base URL string.
        Compatible with CLI.py KNOWN_API_URLS format.
    """
    return {key: info["base_url"] for key, info in _get_api_providers().items()}


def get_provider_models(provider: str) -> List[str]:
    """Get list of models for a specific provider.

    Args:
        provider: Provider key (e.g., 'openai', 'gemini', 'mistral').

    Returns:
        List of model IDs for the provider.  Empty list if not found.
    """
    providers = _get_api_providers()
    if provider in providers:
        return providers[provider].get("models", [])
    return []


def get_all_provider_models() -> Dict[str, List[str]]:
    """Get mapping of all providers to their models.

    Returns:
        Dict mapping provider key to list of model IDs.
        Compatible with CLI.py KNOWN_MODELS format.
    """
    return {key: info["models"] for key, info in _get_api_providers().items()}


def get_provider_names() -> List[str]:
    """Get list of all provider keys.

    Returns:
        List of provider key strings.
    """
    return list(_get_api_providers().keys())


def get_provider_display_name(provider: str) -> str:
    """Get display name for a provider.

    Args:
        provider: Provider key (e.g., 'openai').

    Returns:
        Human-readable provider name, or the key if not found.
    """
    # Try ProviderRegistry first
    try:
        from providers import ProviderRegistry
        p = ProviderRegistry.get(provider)
        if p:
            return p.display_name
    except Exception:
        pass
    providers = _get_api_providers()
    if provider in providers:
        return providers[provider].get("name", provider)
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
