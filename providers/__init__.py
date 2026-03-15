"""Provider Handshake — Unified LLM Provider Interface.

Defines the formal contract for LLM providers:
- ``ProviderBase`` ABC with mandatory and optional methods
- ``ProviderRegistry`` for discovering and accessing providers
- Shared dataclasses: ``ProviderResponse``, ``TokenUsage``,
  ``ThinkingConfig``, ``CachedInputConfig``, ``BatchConfig``,
  ``TemperatureConfig``
- ``ProviderError`` exception hierarchy
- ``validate_provider()`` for handshake compliance checking
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TokenUsage:
    """Normalised token usage from any provider response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Optional extended fields — populated when provider supports them
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    accepted_prediction_tokens: int = 0
    rejected_prediction_tokens: int = 0


@dataclass
class ProviderResponse:
    """Normalised response from any provider."""

    content: str                           # The response text (JSON string)
    usage: TokenUsage                      # Token counts
    finish_reason: str = "stop"            # "stop", "length", "content_filter"
    raw: Any = None                        # Original response object for debugging
    headers: Dict[str, str] = field(default_factory=dict)  # HTTP response headers


@dataclass
class ThinkingConfig:
    """Thinking/reasoning mode configuration for a model.

    Modes:
        ``""``          – Thinking unavailable for this model.
        ``"builtin"``   – Built-in reasoning (o-series); always on, no params.
        ``"explicit"``  – Explicit thinking budget (Claude); on/off toggle.
        ``"optional"``  – Optional thinking (GPT 4.1); on/off toggle.
        ``"mandatory"`` – Mandatory reasoning (GPT 5); always on, effort
                          level configurable via ``reasoning_effort``.
    """

    available: bool = False
    mode: str = ""                  # "builtin"|"explicit"|"optional"|"mandatory"|""
    mandatory: bool = False         # True when thinking cannot be disabled
    effort_levels: tuple = ()       # e.g. ("low", "medium", "high")
    effort_default: str = ""        # default effort when mandatory
    budget_default: int = 10000     # default thinking token budget
    budget_min: int = 1000
    budget_max: int = 100000

    def build_params(
        self,
        budget: int = 0,
        reasoning_effort: str = "",
    ) -> Dict[str, Any]:
        """Build provider-specific API params for thinking mode.

        For Chat Completions API, OpenAI models use ``reasoning_effort``
        as a top-level parameter.  Claude uses ``thinking`` in
        ``extra_body``.

        Args:
            budget: Token budget for thinking.  Uses ``budget_default``
                when *budget* is 0.
            reasoning_effort: Effort level (``"low"``, ``"medium"``,
                ``"high"``).

        Returns:
            Dict of extra API parameters.  Empty when thinking is
            unavailable or builtin (OpenAI o-series).
        """
        if not self.available:
            return {}
        if self.mode == "builtin":
            return {}  # OpenAI o1/o3: built-in, no extra params
        if self.mode in ("mandatory", "optional"):
            effort = reasoning_effort or self.effort_default or "medium"
            return {"reasoning_effort": effort}
        if self.mode == "explicit":
            effective = budget if budget > 0 else self.budget_default
            return {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": effective,
                },
            }
        return {}


@dataclass
class CachedInputConfig:
    """Prompt caching configuration for a model."""

    supported: bool = False
    min_prefix_tokens: int = 1024
    retention: str = ""             # "" | "in_memory" | "24h"
    cached_price_ratio: float = 0.5

    @staticmethod
    def openai_default() -> CachedInputConfig:
        """Standard OpenAI prompt caching config (gpt-4o+)."""
        return CachedInputConfig(
            supported=True,
            min_prefix_tokens=1024,
            retention="in_memory",
            cached_price_ratio=0.5,
        )

    @staticmethod
    def openai_extended() -> CachedInputConfig:
        """Extended 24h retention for gpt-4.1 / gpt-5 family."""
        return CachedInputConfig(
            supported=True,
            min_prefix_tokens=1024,
            retention="24h",
            cached_price_ratio=0.5,
        )


@dataclass
class BatchConfig:
    """Batch / flex / priority processing config."""

    batch_available: bool = False
    batch_input_price_ratio: float = 0.5
    batch_output_price_ratio: float = 0.5
    flex_available: bool = False
    flex_input_price_ratio: float = 0.0
    flex_output_price_ratio: float = 0.0
    priority_available: bool = False
    priority_input_price_ratio: float = 1.0
    priority_output_price_ratio: float = 1.0


@dataclass
class TemperatureConfig:
    """Temperature parameter configuration for a model."""

    supported: bool = True
    min_value: float = 0.0
    max_value: float = 2.0
    default: float = 0.3


# ---------------------------------------------------------------------------
# Provider error hierarchy
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base error for all provider failures."""

    def __init__(
        self,
        message: str,
        *,
        is_fatal: bool = False,
        error_code: str = "UNKNOWN",
    ) -> None:
        super().__init__(message)
        self.is_fatal = is_fatal
        self.error_code = error_code


class AuthenticationError(ProviderError):
    """API key invalid or expired."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, is_fatal=True, error_code="AUTH_INVALID")


class ModelNotFoundError(ProviderError):
    """Requested model does not exist."""

    def __init__(self, message: str = "Model not found") -> None:
        super().__init__(message, is_fatal=True, error_code="MODEL_NOT_FOUND")


class RateLimitedError(ProviderError):
    """Rate limit exceeded — retryable."""

    def __init__(self, message: str = "Rate limited") -> None:
        super().__init__(message, is_fatal=False, error_code="RATE_LIMITED")


class QuotaExceededError(ProviderError):
    """Billing quota exhausted."""

    def __init__(self, message: str = "Quota exceeded") -> None:
        super().__init__(message, is_fatal=True, error_code="QUOTA_EXCEEDED")


class ContentFilteredError(ProviderError):
    """Content policy violation."""

    def __init__(self, message: str = "Content filtered") -> None:
        super().__init__(message, is_fatal=True, error_code="CONTENT_FILTERED")


class ProviderConnectionError(ProviderError):
    """Network / connectivity issue — retryable."""

    def __init__(self, message: str = "Connection error") -> None:
        super().__init__(message, is_fatal=False, error_code="CONNECTION_ERROR")


class ProviderTimeoutError(ProviderError):
    """Request timed out — retryable."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message, is_fatal=False, error_code="TIMEOUT")


# ---------------------------------------------------------------------------
# Provider ABC
# ---------------------------------------------------------------------------

class ProviderBase(ABC):
    """Abstract base class for all LLM providers.

    Mandatory components are abstract methods.  Optional components have
    default no-op implementations that providers may override.
    """

    name: str = ""                          # e.g., "openai"
    display_name: str = ""                  # e.g., "OpenAI"
    requires_api_key: bool = True           # MP1
    base_url: str = ""                      # MP4

    # --- Mandatory provider-level (MP2, MP3, MP5, MP6) ---

    @abstractmethod
    def send_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float],
        response_format: Optional[Dict[str, Any]],
        *,
        api_key: str = "",
        timeout: int = 60,
        **kwargs: Any,
    ) -> ProviderResponse:
        """MP5: Send a chat completion request.

        Args:
            messages: Chat messages (system + user).
            model: Model ID string.
            temperature: Sampling temperature (``None`` to omit).
            response_format: JSON mode / schema dict.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
            **kwargs: Extra provider-specific params (``extra_body``, etc.).

        Returns:
            ``ProviderResponse`` with content, usage, and finish reason.

        Raises:
            ProviderError: On any API failure.
        """
        ...

    @abstractmethod
    def parse_response(self, raw_response: Any) -> ProviderResponse:
        """MP6: Parse raw API response to ``ProviderResponse``."""
        ...

    @abstractmethod
    def get_input_price(self, model_id: str) -> float:
        """MP2: USD per 1M input tokens."""
        ...

    @abstractmethod
    def get_output_price(self, model_id: str) -> float:
        """MP3: USD per 1M output tokens."""
        ...

    # --- Mandatory model-level (MM1, MM2, MM3) ---

    @abstractmethod
    def supports_structured_output(self, model_id: str) -> bool:
        """MM1: Can this model return structured JSON?"""
        ...

    @abstractmethod
    def get_model_name(self, model_id: str) -> str:
        """MM2: Human-readable model name."""
        ...

    @abstractmethod
    def get_thinking_config(self, model_id: str) -> ThinkingConfig:
        """MM3: Thinking/reasoning support."""
        ...

    # --- Optional provider-level (defaults) ---

    def get_cached_input_config(self, model_id: str) -> Optional[CachedInputConfig]:
        """OP1: Prompt caching config.  ``None`` when unsupported."""
        return None

    def get_batch_config(self, model_id: str) -> Optional[BatchConfig]:
        """OP2: Batch / flex / priority config."""
        return None

    def fetch_models(self, api_key: str) -> List[Any]:
        """OP3: Fetch available models from provider API."""
        return []

    def probe_rate_limits(
        self, api_key: str, model_id: str,
    ) -> Optional[Dict[str, int]]:
        """OP4: Probe rate limit headers with a minimal request."""
        return None

    def classify_error(self, error: Exception) -> Optional[Any]:
        """OP5: Provider-specific error classification.

        Returns ``None`` to fall back to the default classifier.
        """
        return None

    # --- Optional model-level (defaults) ---

    def get_temperature_config(self, model_id: str) -> TemperatureConfig:
        """OM1: Temperature parameter support and range."""
        return TemperatureConfig()

    def get_context_window(self, model_id: str) -> int:
        """OM2: Maximum context window in tokens."""
        return 128000

    # --- Convenience helpers ---

    def get_response_format(self, model_id: str) -> Dict[str, Any]:
        """Build the ``response_format`` dict for a model.

        Default is ``{"type": "json_object"}`` — local providers
        override this to use ``json_schema`` with a strict schema.
        """
        return {"type": "json_object"}


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------

class ProviderRegistry:
    """Global registry of available LLM providers."""

    _providers: Dict[str, ProviderBase] = {}

    @classmethod
    def register(cls, provider: ProviderBase) -> None:
        """Register a provider instance.

        Args:
            provider: An instance of a ``ProviderBase`` subclass.
        """
        if not provider.name:
            raise ValueError("Provider must have a non-empty 'name'")
        cls._providers[provider.name] = provider
        logger.debug("Registered provider: %s", provider.name)

    @classmethod
    def get(cls, name: str) -> Optional[ProviderBase]:
        """Look up a provider by its canonical name.

        Args:
            name: Provider key (e.g., ``"openai"``).

        Returns:
            The provider instance, or ``None`` if not registered.
        """
        return cls._providers.get(name)

    @classmethod
    def list_providers(cls) -> List[str]:
        """Return sorted list of registered provider names."""
        return sorted(cls._providers.keys())

    @classmethod
    def all(cls) -> List[ProviderBase]:
        """Return all registered provider instances."""
        return list(cls._providers.values())

    @classmethod
    def clear(cls) -> None:
        """Remove all registered providers (for testing)."""
        cls._providers.clear()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_MANDATORY_METHODS = [
    "send_request",
    "parse_response",
    "get_input_price",
    "get_output_price",
    "supports_structured_output",
    "get_model_name",
    "get_thinking_config",
]


def validate_provider(provider: ProviderBase) -> List[str]:
    """Check that a provider satisfies all mandatory components.

    Args:
        provider: The provider to validate.

    Returns:
        List of error messages. Empty list means the provider is valid.
    """
    errors: List[str] = []

    if not provider.name:
        errors.append("Provider 'name' must be non-empty")
    if not provider.display_name:
        errors.append("Provider 'display_name' must be non-empty")
    if not provider.base_url:
        errors.append("Provider 'base_url' must be non-empty")
    if not isinstance(provider.requires_api_key, bool):
        errors.append("Provider 'requires_api_key' must be bool")

    for method_name in _MANDATORY_METHODS:
        method = getattr(provider, method_name, None)
        if method is None:
            errors.append(f"Missing mandatory method: {method_name}")
        elif not callable(method):
            errors.append(f"'{method_name}' is not callable")

    return errors


# ---------------------------------------------------------------------------
# Auto-registration of built-in providers
# ---------------------------------------------------------------------------

def _load_providers() -> None:
    """Import and register all built-in provider modules.

    Called once at module load time.  Each provider module is expected
    to call ``ProviderRegistry.register(...)`` at import.
    """
    # Lazy imports to avoid circular dependency issues
    try:
        from . import openai_provider  # noqa: F401
    except Exception:
        logger.debug("Could not load openai_provider")
    try:
        from . import google_provider  # noqa: F401
    except Exception:
        logger.debug("Could not load google_provider")
    try:
        from . import mistral_provider  # noqa: F401
    except Exception:
        logger.debug("Could not load mistral_provider")
    try:
        from . import anthropic_provider  # noqa: F401
    except Exception:
        logger.debug("Could not load anthropic_provider")
    try:
        from . import local_provider  # noqa: F401
    except Exception:
        logger.debug("Could not load local_provider")


_load_providers()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Dataclasses
    "TokenUsage",
    "ProviderResponse",
    "ThinkingConfig",
    "CachedInputConfig",
    "BatchConfig",
    "TemperatureConfig",
    # Errors
    "ProviderError",
    "AuthenticationError",
    "ModelNotFoundError",
    "RateLimitedError",
    "QuotaExceededError",
    "ContentFilteredError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    # ABC & registry
    "ProviderBase",
    "ProviderRegistry",
    "validate_provider",
]
