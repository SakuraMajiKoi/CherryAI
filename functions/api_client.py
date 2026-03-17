"""API Client for CherryAI.

Handles communication with LLM providers (OpenAI, Gemini via OpenAI compat).
Includes rate limiting, chunking, structured output validation, and error handling.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    # For type checking only; avoids import errors at runtime when package is missing.
    from openai import OpenAI, APIError, RateLimitError, APITimeoutError
    import openai
    from .batch_tracker import BatchJob
else:
    # Try to import openai at runtime; if it's not installed, provide safe fallbacks.
    try:
        import importlib

        openai = importlib.import_module("openai")
    except Exception:
        openai = None  # Handled in __init__

    OpenAI = getattr(openai, "OpenAI", None)
    APIError = getattr(openai, "APIError", Exception)
    RateLimitError = getattr(openai, "RateLimitError", Exception)
    APITimeoutError = getattr(openai, "APITimeoutError", Exception)

from .chunker import Chunker, ChunkerConfig, ChunkMode, create_chunker
from .common_errors import (
    TranslationAbortError,
    classify_api_error,
)
from .config import load_config, get_preset_config, list_preset_names
from .logit_bias import (
    LogitBiasManager,
    LogitBiasConfig,
    parse_ban_tokens_arg,
    create_logit_bias_manager,
    merge_parser_forbidden_chars,
)
from .request_cache import RequestCache, CacheConfig, CacheMode, parse_cache_mode_arg, create_request_cache
from .rate_limiter import RateLimiter, RateLimiterConfig, create_rate_limiter
from .header_rate_limiter import (
    HeaderBasedRateLimiter,
    OPENAI_RATE_LIMIT_CONFIG,
    ProviderRateLimitConfig,
)


@dataclass
class APIConfig:
    """Configuration for API Client."""
    provider: str = "openai"
    api_key: str = ""
    base_url: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.3
    timeout: int = 60
    retries: int = 3
    rate_limit_requests: int = 60  # Requests per minute
    chunk_size: int = 50  # Lines per chunk (for lines/hybrid mode)
    chunk_mode: str = "lines"  # "lines", "tokens", or "hybrid"
    chunk_max_tokens: int = 4000  # Max tokens per chunk (for tokens/hybrid mode)
    source_lang: str = "Japanese"
    target_lang: str = "English"
    thinking_enabled: bool = False  # Enable extended thinking/reasoning mode
    thinking_budget: int = 10000  # Token budget for thinking (Claude models)
    reasoning_effort: str = "medium"  # low/medium/high for optional/mandatory models
    # Logit bias settings
    logit_bias_enabled: bool = False  # Enable token banning
    banned_tokens: str = ""  # Comma-separated tokens/chars to ban
    logit_bias_preset: str = ""  # Preset name (no_em_dash, no_smart_quotes, etc.)
    # Retry strategy settings
    retry_strategy: str = "batch"  # batch, contextual, isolated, skip
    # Cache settings
    cache_enabled: bool = False  # Enable request caching
    cache_mode: str = "model_only"  # strict, model_only, any
    clear_cache: bool = False  # Clear cache before starting
    # Style preset settings
    style_preset: str = ""  # Comma-separated style presets (e.g., fantasy_medieval,archaic_english)
    # Rate limit management settings
    rate_limit_enabled: bool = False  # Enable comprehensive rate limit management
    max_concurrent: int = 3  # Maximum concurrent API requests
    rate_limit_margin: float = 0.1  # Safety margin for rate limits (0.0-0.5)
    # Local LLM settings
    no_api_key: bool = False  # Skip API key validation for local LLMs
    # Batch API settings (TASK 17.1)
    batch_mode: bool = False  # Use async Batch API (50% cheaper)
    # Request mode: normal, batch, flex, or priority
    request_mode: str = "normal"
    # Prompt caching settings (OpenAI)
    prompt_cache_enabled: bool = True  # Enable OpenAI prompt caching (auto for gpt-4o+)
    prompt_cache_retention: str = ""  # "" = default (in_memory), "in_memory", or "24h"
    prompt_cache_key: str = ""  # Semi-unique key to improve cache hit routing

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> APIConfig:
        """Create config from dictionary, ignoring unknown keys."""
        known_keys = cls.__annotations__.keys()
        filtered_data = {k: v for k, v in data.items() if k in known_keys}
        
        # Type conversion for numeric fields
        if "temperature" in filtered_data:
            filtered_data["temperature"] = float(filtered_data["temperature"])
        if "timeout" in filtered_data:
            filtered_data["timeout"] = int(filtered_data["timeout"])
        if "retries" in filtered_data:
            filtered_data["retries"] = int(filtered_data["retries"])
        if "rate_limit_requests" in filtered_data:
            filtered_data["rate_limit_requests"] = int(filtered_data["rate_limit_requests"])
        if "chunk_size" in filtered_data:
            filtered_data["chunk_size"] = int(filtered_data["chunk_size"])
        if "chunk_max_tokens" in filtered_data:
            filtered_data["chunk_max_tokens"] = int(filtered_data["chunk_max_tokens"])
        if "thinking_enabled" in filtered_data:
            val = filtered_data["thinking_enabled"]
            filtered_data["thinking_enabled"] = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        if "thinking_budget" in filtered_data:
            filtered_data["thinking_budget"] = int(filtered_data["thinking_budget"])
        if "logit_bias_enabled" in filtered_data:
            val = filtered_data["logit_bias_enabled"]
            filtered_data["logit_bias_enabled"] = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        # Cache boolean fields
        if "cache_enabled" in filtered_data:
            val = filtered_data["cache_enabled"]
            filtered_data["cache_enabled"] = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        if "clear_cache" in filtered_data:
            val = filtered_data["clear_cache"]
            filtered_data["clear_cache"] = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        # Rate limit fields
        if "rate_limit_enabled" in filtered_data:
            val = filtered_data["rate_limit_enabled"]
            filtered_data["rate_limit_enabled"] = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        if "max_concurrent" in filtered_data:
            filtered_data["max_concurrent"] = int(filtered_data["max_concurrent"])
        if "rate_limit_margin" in filtered_data:
            filtered_data["rate_limit_margin"] = float(filtered_data["rate_limit_margin"])
        # Local LLM fields
        if "no_api_key" in filtered_data:
            val = filtered_data["no_api_key"]
            filtered_data["no_api_key"] = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        # Batch API fields
        if "batch_mode" in filtered_data:
            val = filtered_data["batch_mode"]
            filtered_data["batch_mode"] = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        # Prompt caching fields
        if "prompt_cache_enabled" in filtered_data:
            val = filtered_data["prompt_cache_enabled"]
            filtered_data["prompt_cache_enabled"] = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
        if "prompt_cache_retention" in filtered_data:
            filtered_data["prompt_cache_retention"] = str(filtered_data["prompt_cache_retention"])
        if "prompt_cache_key" in filtered_data:
            filtered_data["prompt_cache_key"] = str(filtered_data["prompt_cache_key"])
            
        return cls(**filtered_data)


def generate_prompt_cache_key(
    project_name: str,
    created_at: str,
) -> str:
    """Generate a prompt_cache_key from manifest metadata.

    Format: ``"{first 5 alpha chars of project_name}-{seconds of created_at}"``
    Example: ``"MyCoo-56"`` for project "My Cool Game" created at
    ``"2025-01-15T12:34:56Z"``.

    Returns an empty string if either input is empty or malformed.
    """
    if not project_name or not created_at:
        return ""
    # Extract first 5 alphabetic characters from project name
    alpha_chars = [c for c in project_name if c.isalpha()]
    prefix = "".join(alpha_chars[:5])
    if not prefix:
        return ""
    # Extract seconds from ISO timestamp (…T…:SS or …:SSZ)
    try:
        # Handle "2025-01-15T12:34:56Z" or "2025-01-15T12:34:56.123Z"
        time_part = created_at.split("T")[-1] if "T" in created_at else ""
        seconds_str = time_part.split(":")[2] if time_part.count(":") >= 2 else ""
        # Strip trailing Z or fractional seconds
        seconds_str = seconds_str.rstrip("Z").split(".")[0]
        seconds = int(seconds_str)
    except (IndexError, ValueError):
        return ""
    return f"{prefix}-{seconds}"


def resolve_prompt_cache_key(
    explicit_key: str,
    project_name: str,
    created_at: str,
) -> str:
    """Resolve the effective prompt cache key.

    Prefers an explicitly configured key. When none is configured,
    derives a stable routing hint from the manifest metadata.
    """
    cache_key = (explicit_key or "").strip()
    if cache_key:
        return cache_key
    return generate_prompt_cache_key(project_name, created_at)


def _normalize_prompt_cache_retention(retention: str) -> str:
    """Normalize retention strings from config or docs aliases."""
    value = (retention or "").strip().lower().replace("-", "_")
    if value in {"", "24h", "in_memory"}:
        return value
    return ""


def supports_prompt_caching_for(
    provider: str,
    model: str,
    *,
    base_url: Optional[str] = None,
) -> bool:
    """Check whether a provider/model combination supports prompt caching."""
    provider_lower = (provider or "").strip().lower()
    if provider_lower != "openai":
        return False
    from CherryAI.functions.local_llm import is_local_url

    if is_local_url(base_url or ""):
        return False

    model_lower = (model or "").strip().lower()
    return any(
        model_lower.startswith(prefix)
        for prefix in APIClient.PROMPT_CACHE_MODEL_PREFIXES
    )


def supports_extended_cache_retention_for(
    provider: str,
    model: str,
    *,
    base_url: Optional[str] = None,
) -> bool:
    """Check whether 24h retention is supported for a provider/model."""
    if not supports_prompt_caching_for(provider, model, base_url=base_url):
        return False

    model_lower = (model or "").strip().lower()
    return any(
        model_lower.startswith(prefix)
        for prefix in APIClient.EXTENDED_CACHE_MODEL_PREFIXES
    )


def build_prompt_cache_params(
    *,
    enabled: bool,
    provider: str,
    model: str,
    retention: str = "",
    explicit_key: str = "",
    project_name: str = "",
    created_at: str = "",
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Build effective prompt cache request parameters.

    This helper centralizes the logic used by both the live request path
    and the Request Preview so they stay identical.
    """
    if not enabled:
        return {}
    if not supports_prompt_caching_for(provider, model, base_url=base_url):
        return {}

    params: Dict[str, Any] = {}
    normalized_retention = _normalize_prompt_cache_retention(retention)
    if (
        normalized_retention == "24h"
        and supports_extended_cache_retention_for(
            provider,
            model,
            base_url=base_url,
        )
    ):
        params["prompt_cache_retention"] = "24h"
    elif normalized_retention == "in_memory":
        params["prompt_cache_retention"] = "in_memory"

    cache_key = resolve_prompt_cache_key(
        explicit_key,
        project_name,
        created_at,
    )
    if cache_key:
        params["prompt_cache_key"] = cache_key

    return params


# Sections that form the static (cacheable) prefix per §5.2
_STATIC_PROMPT_SECTIONS = frozenset({
    "language", "system_instructions", "io_examples", "style", "tone",
    "protagonist", "summary", "genre", "pov", "context_type",
})


def check_static_prompt_cache_status(
    token_breakdown: Dict[str, int],
    *,
    words_per_token: float = 0.75,
) -> tuple[str, str]:
    """Evaluate whether the static prompt prefix is large enough for caching.

    OpenAI caches prompt prefixes ≥ 1024 tokens in 128-token increments.
    This checks the *static* portion (slots 1-7b) of the prompt.

    Args:
        token_breakdown: Section-name → word-count mapping from
            ``build_full_system_prompt``.
        words_per_token: Estimated words-per-token ratio.  Default 0.75
            (≈ 1.33 tokens per word) is conservative for English.

    Returns:
        Tuple of ``(status, message)`` where *status* is one of:
        - ``"ok"`` — ≥ 1280 estimated tokens (2× 128-token boundary above 1024)
        - ``"suggest"`` — 1024–1279 tokens (borderline; may not cache reliably)
        - ``"warn"`` — < 1024 tokens (below caching threshold)
    """
    static_words = sum(
        count for section, count in token_breakdown.items()
        if section in _STATIC_PROMPT_SECTIONS
    )
    estimated_tokens = int(static_words / words_per_token) if words_per_token else 0

    if estimated_tokens >= 1280:
        return ("ok", f"Static prompt ~{estimated_tokens} tokens — caching active.")
    if estimated_tokens >= 1024:
        return (
            "suggest",
            f"Static prompt ~{estimated_tokens} tokens — borderline. "
            f"Adding more system instructions may improve cache reliability.",
        )
    return (
        "warn",
        f"Static prompt ~{estimated_tokens} tokens — below 1024 minimum. "
        f"Prompt caching will NOT activate.",
    )



class TranslationError(Exception):
    """Custom exception for translation failures."""
    pass


# Content warning terms that may trigger API refusal/ban
EXPLICIT_CONTENT_TERMS = [
    "erotic", "explicit", "sexual", "violent", "18+", "adult content",
    "pornographic", "nsfw", "hentai", "rape", "incest",
]


class APIClient:
    """Client for interacting with LLM APIs."""

    def __init__(
        self, 
        enable_api_log: bool = False, 
        api_log_path: Optional[str] = None,
        content_warning_enabled: bool = True,
        persistent_log: bool = True,
    ) -> None:
        """Initialize the API client.
        
        Args:
            enable_api_log: If True, log all API requests and responses to file.
            api_log_path: Custom path for API log file. If None, uses logs/api_log.txt.
            content_warning_enabled: If True, warn when explicit content detected.
            persistent_log: If True, create timestamped log files instead of overwriting.
        """
        if openai is None:
            logging.error("OpenAI package not installed. Please run dependency check.")
            raise ImportError("openai package is required for API Client")

        self.logger = logging.getLogger("cherryai.api")
        self.config = self._load_api_config()
        self.client: Optional[OpenAI] = None
        self._request_timestamps: List[float] = []
        
        # API logging
        self.enable_api_log = enable_api_log
        self.api_log_path = api_log_path
        self.persistent_log = persistent_log
        self._api_log_entries: List[Dict[str, Any]] = []
        self._chunk_counter = 0
        self._session_log_path: Optional[Path] = None  # Resolved at write time
        
        # Statistics tracking
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_cached_tokens = 0
        self._total_reasoning_tokens = 0
        self._skipped_lines: Dict[str, int] = {"dedup": 0, "symbols": 0, "no_source": 0}
        self._initial_chunk_count = 0
        self._final_chunk_count = 0
        self._content_warnings: List[str] = []

        # Manifest-derived prompt cache context used for auto-generated
        # prompt_cache_key routing hints.
        self._prompt_cache_project_name: str = ""
        self._prompt_cache_created_at: str = ""
        
        # Content warning
        self.content_warning_enabled = content_warning_enabled

        # Structured API log store (API Log Window)
        from .api_log import get_api_log_store
        self._api_log_store = get_api_log_store()

        # Step log path for per-project translation.log (Phase 48)
        self._step_log_path: Optional[Path] = None
        
        # Logit bias manager (initialized lazily when needed)
        self._logit_bias_manager: Optional[LogitBiasManager] = None
        
        # Request cache (initialized lazily when needed)
        self._request_cache: Optional[RequestCache] = None
        
        # Rate limiter (initialized lazily when needed)
        self._rate_limiter: Optional[RateLimiter] = None

        # Header-based rate limiter (per-model, response-header driven)
        self._header_rate_limiter: Optional[HeaderBasedRateLimiter] = None

        # Resolve provider from ProviderRegistry (V6 Provider Handshake)
        self._provider = None
        try:
            from providers import ProviderRegistry
            self._provider = ProviderRegistry.get(self.config.provider)
        except Exception:
            pass  # Fallback to legacy branching if registry unavailable
        
        self._init_client()
        
        # Initialize logit bias if enabled in config
        if self.config.logit_bias_enabled or self.config.banned_tokens or self.config.logit_bias_preset:
            self.configure_logit_bias(
                enabled=True,
                banned_tokens=self.config.banned_tokens,
                preset=self.config.logit_bias_preset,
            )
        
        # Initialize cache if enabled in config
        if self.config.cache_enabled:
            self.configure_cache(
                enabled=True,
                mode=self.config.cache_mode,
                clear_cache=self.config.clear_cache,
            )
        
        # Initialize rate limiter if enabled in config
        if self.config.rate_limit_enabled:
            self.configure_rate_limiter(
                enabled=True,
                max_concurrent=self.config.max_concurrent,
                safety_margin=self.config.rate_limit_margin,
            )

        # Always initialise the header-based rate limiter with stored limits
        self._init_header_rate_limiter()

    def _load_api_config(self) -> APIConfig:
        """Load configuration from CherryAI.ini."""
        full_config = load_config()
        api_section = full_config.get("api", {})
        return APIConfig.from_dict(api_section)

    def _init_client(self) -> None:
        """Initialize the OpenAI client.
        
        For local LLMs that don't require API keys, use --no-api-key flag
        or set api_key to "dummy" to bypass key validation.
        """
        # For local LLMs, allow dummy/empty keys
        api_key = self.config.api_key
        if not api_key:
            # Use provider handshake if available
            if self._provider and not self._provider.requires_api_key:
                api_key = "lm-studio"
                self.logger.info("Using no-API-key mode for local LLM")
            elif (self.config.no_api_key
                    or self.config.provider.lower() in self.LOCAL_PROVIDERS):
                # Legacy fallback
                api_key = "lm-studio"
                self.logger.info("Using no-API-key mode for local LLM")
            else:
                self.logger.warning("No API key found in configuration.")
                return

        self.client = OpenAI(
            api_key=api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=0  # We handle retries manually
        )
        self.logger.info(f"API Client initialized for {self.config.provider} ({self.config.model})")

    def _init_header_rate_limiter(self) -> None:
        """Initialise the header-based rate limiter with stored limits.

        Reads per-model RPM/TPM values from ``API.ini`` (via
        :func:`functions.api_config.get_rate_limit`) and seeds the
        limiter so enforcement starts immediately, before any response
        headers are received.
        """
        self._header_rate_limiter = HeaderBasedRateLimiter(
            OPENAI_RATE_LIMIT_CONFIG,
        )
        try:
            from functions.api_config import get_rate_limit
            limits = get_rate_limit(self.config.model)
            if limits and (limits.get("rpm") or limits.get("tpm")):
                self._header_rate_limiter.set_model_limits(
                    self.config.model,
                    rpm=limits.get("rpm", 0),
                    tpm=limits.get("tpm", 0),
                )
                self.logger.info(
                    "Header rate limiter: loaded %s limits (rpm=%d, tpm=%d)",
                    self.config.model,
                    limits.get("rpm", 0),
                    limits.get("tpm", 0),
                )
        except Exception as exc:
            self.logger.debug(
                "Header rate limiter: no stored limits found: %s", exc,
            )
    
    def apply_preset(self, preset_name: str) -> bool:
        """Apply an API preset to the client configuration.
        
        This updates the client's configuration with values from the preset,
        then reinitializes the client connection.
        
        Args:
            preset_name: Name of the preset to apply.
            
        Returns:
            True if preset was applied successfully, False otherwise.
        """
        preset = get_preset_config(preset_name)
        if preset is None:
            self.logger.warning(f"Preset not found: {preset_name}")
            return False
        
        # Update config with preset values
        if "base_url" in preset:
            self.config.base_url = preset["base_url"]
        if "model" in preset:
            self.config.model = preset["model"]
        if "temperature" in preset:
            self.config.temperature = preset["temperature"]
        if "timeout" in preset:
            self.config.timeout = preset["timeout"]
        if "rate_limit_requests" in preset:
            self.config.rate_limit_requests = preset["rate_limit_requests"]
        
        # Reinitialize client with new settings
        self._init_client()
        self.logger.info(f"Applied preset: {preset_name} (model: {self.config.model})")
        return True
    
    @staticmethod
    def get_available_presets() -> List[str]:
        """Get list of available preset names.
        
        Returns:
            List of preset names that can be used with apply_preset().
        """
        from typing import cast
        return cast(List[str], list_preset_names())

    # Models that support extended thinking/reasoning mode
    THINKING_MODELS = [
        # Claude models with extended thinking support
        "claude-sonnet-4",
        "claude-opus-4",
        "claude-haiku-4",
        "claude-3-7-sonnet",
        # Aliases and versioned names
        "claude-sonnet-4-5",
        "claude-opus-4-5",
        "claude-opus-4-1",
        "claude-haiku-4-5",
        # OpenAI reasoning models (built-in, no special param needed)
        "o1",
        "o1-mini",
        "o1-preview",
        "o3",
        "o3-mini",
        "o4-mini",
        # GPT 4.1 family (optional reasoning)
        "gpt-4.1",
        # GPT 5 family (mandatory reasoning)
        "gpt-5",
    ]
    
    # Providers that are local and don't require API keys
    LOCAL_PROVIDERS = ("local", "lmstudio", "ollama")

    # Models supporting OpenAI prompt caching (automatic, gpt-4o and newer).
    # Prefix-matched against the configured model name (case-insensitive).
    PROMPT_CACHE_MODEL_PREFIXES = (
        "gpt-4o",
        "gpt-4.1",
        "gpt-5",
        "o1",
        "o3",
        "chatgpt-4o",
    )

    # Models supporting extended 24h prompt cache retention.
    # Prefix-matched against the configured model name (case-insensitive).
    EXTENDED_CACHE_MODEL_PREFIXES = (
        "gpt-4.1",
        "gpt-5",
    )

    def is_local_provider(self) -> bool:
        """Check if the current provider is a local LLM server.

        Returns:
            True if using a local provider (LM Studio, Ollama, etc.).
        """
        if self.config.provider.lower() in self.LOCAL_PROVIDERS:
            return True
        from CherryAI.functions.local_llm import is_local_url
        return is_local_url(self.config.base_url or "")

    def supports_thinking_mode(self) -> bool:
        """Check if the current model supports extended thinking mode.
        
        Returns:
            True if the model supports thinking mode, False otherwise.
        """
        model_lower = self.config.model.lower()
        for pattern in self.THINKING_MODELS:
            if pattern in model_lower:
                return True
        return False
    
    def is_openai_reasoning_model(self) -> bool:
        """Check if the current model is an OpenAI reasoning model.
        
        Includes o-series (built-in), GPT-4.1 (optional), and GPT-5
        (mandatory) models.
        
        Returns:
            True if model is an OpenAI reasoning model.
        """
        model_lower = self.config.model.lower()
        return any(
            model_lower.startswith(p)
            for p in ("o1", "o3", "o4", "gpt-4.1", "gpt-5")
        )
    
    def is_claude_thinking_model(self) -> bool:
        """Check if the current model is a Claude model with thinking support.
        
        Returns:
            True if model is a Claude model with extended thinking.
        """
        model_lower = self.config.model.lower()
        # Claude models (not o1/o3)
        if "claude" in model_lower:
            # Check if it's a model version that supports thinking
            return any(p in model_lower for p in [
                "sonnet-4", "opus-4", "haiku-4", "3-7-sonnet",
                "sonnet-4-5", "opus-4-5", "opus-4-1", "haiku-4-5",
            ])
        return False

    def supports_prompt_caching(self) -> bool:
        """Check if the current model supports OpenAI prompt caching.

        Prompt caching is automatic for gpt-4o and newer models when the
        provider is OpenAI (not local).  Gemini uses a different caching
        mechanism and is not supported here.

        Returns:
            True if the model supports prompt caching.
        """
        return supports_prompt_caching_for(
            self.config.provider,
            self.config.model,
            base_url=self.config.base_url,
        )

    def supports_extended_cache_retention(self) -> bool:
        """Check if the current model supports 24h extended cache retention.

        Extended retention keeps cached prefixes for up to 24 hours instead
        of the default 5-10 minute in-memory window.

        Returns:
            True if the model supports extended cache retention.
        """
        return supports_extended_cache_retention_for(
            self.config.provider,
            self.config.model,
            base_url=self.config.base_url,
        )

    def set_prompt_cache_context(
        self,
        *,
        project_name: str,
        created_at: str,
    ) -> str:
        """Set manifest context used to auto-generate prompt cache keys."""
        self._prompt_cache_project_name = project_name or ""
        self._prompt_cache_created_at = created_at or ""
        return resolve_prompt_cache_key(
            self.config.prompt_cache_key,
            self._prompt_cache_project_name,
            self._prompt_cache_created_at,
        )

    def get_prompt_cache_params(self) -> Dict[str, Any]:
        """Build prompt caching parameters for the API request.

        Returns a dict of keyword arguments to merge into the
        ``chat.completions.create()`` call.  Empty dict when prompt
        caching is disabled or not supported by the model.

        Returns:
            Dict with ``prompt_cache_retention`` key when applicable.
        """
        project_name = getattr(self, "_prompt_cache_project_name", "")
        created_at = getattr(self, "_prompt_cache_created_at", "")
        return build_prompt_cache_params(
            enabled=self.config.prompt_cache_enabled,
            provider=self.config.provider,
            model=self.config.model,
            retention=self.config.prompt_cache_retention,
            explicit_key=self.config.prompt_cache_key,
            project_name=project_name,
            created_at=created_at,
            base_url=self.config.base_url,
        )

    def get_thinking_params(self) -> Dict[str, Any]:
        """Get thinking mode parameters for the current model.

        Uses the provider's ``ThinkingConfig`` when available, falling back
        to legacy hardcoded logic.  For mandatory-mode models the params are
        always returned regardless of ``thinking_enabled``.

        Returns:
            Dictionary of extra parameters to add to API request.
            Empty dict if thinking is disabled or model doesn't support it.
        """
        # --- provider-based path (preferred) ---
        if self._provider:
            think_cfg = self._provider.get_thinking_config(self.config.model)
            if think_cfg.available:
                # Mandatory models always send reasoning params
                if not think_cfg.mandatory and not self.config.thinking_enabled:
                    return {}
                params = think_cfg.build_params(
                    budget=self.config.thinking_budget,
                    reasoning_effort=self.config.reasoning_effort,
                )
                if params:
                    self.logger.debug(
                        "Thinking params for %s (mode=%s): %s",
                        self.config.model, think_cfg.mode, params,
                    )
                return params
            # Provider says unavailable
            return {}

        # --- legacy fallback (no provider) ---
        if not self.config.thinking_enabled:
            return {}

        if not self.supports_thinking_mode():
            self.logger.debug(
                "Model %s does not support thinking mode",
                self.config.model,
            )
            return {}

        # OpenAI reasoning models: built-in, no extra params
        if self.is_openai_reasoning_model():
            self.logger.debug("OpenAI reasoning model - using built-in reasoning")
            return {}

        # Claude models: explicit thinking parameter
        if self.is_claude_thinking_model():
            self.logger.debug(
                "Enabling Claude thinking mode (budget: %s)",
                self.config.thinking_budget,
            )
            return {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": self.config.thinking_budget,
                },
            }

        return {}

    def configure_logit_bias(
        self,
        enabled: bool = True,
        banned_tokens: Optional[str] = None,
        preset: Optional[str] = None,
    ) -> bool:
        """Configure logit bias settings for token banning/discouraging.
        
        Args:
            enabled: Whether logit bias is enabled.
            banned_tokens: Comma-separated tokens/aliases to ban (e.g., "em_dash,smart_quotes").
            preset: Name of preset to apply (e.g., "no_fancy_punctuation").
            
        Returns:
            True if configuration was successful, False if tiktoken unavailable.
        """
        if not enabled:
            self._logit_bias_manager = None
            self.config.logit_bias_enabled = False
            return True
        
        # Create configuration from parameters or existing config
        config = LogitBiasConfig(
            enabled=enabled,
            banned_chars=parse_ban_tokens_arg(banned_tokens or self.config.banned_tokens),
            preset=preset or self.config.logit_bias_preset,
            model=self.config.model,
        )
        
        try:
            self._logit_bias_manager = create_logit_bias_manager(
                enabled=config.enabled,
                banned_chars=config.banned_chars,
                preset=config.preset,
                model=config.model,
            )
            if self._logit_bias_manager and self._logit_bias_manager.is_available():
                self.config.logit_bias_enabled = True
                summary = self._logit_bias_manager.get_summary()
                self.logger.info(f"Logit bias configured: {summary}")
                return True
            else:
                self.logger.warning("Logit bias manager not available (tiktoken may not be installed)")
                self.config.logit_bias_enabled = False
                return False
        except Exception as e:
            self.logger.error(f"Failed to configure logit bias: {e}")
            self.config.logit_bias_enabled = False
            return False
    
    def get_logit_bias_params(self) -> Dict[str, int]:
        """Get logit bias dictionary for API call.
        
        Returns:
            Dictionary mapping token IDs to bias values, or empty dict if disabled.
        """
        if not self.config.logit_bias_enabled or not self._logit_bias_manager:
            return {}
        
        if not self._logit_bias_manager.is_available():
            return {}
        
        from typing import cast, Dict as _Dict
        return cast(_Dict[str, int], self._logit_bias_manager.get_logit_bias())
    
    def get_logit_bias_summary(self) -> Optional[str]:
        """Get a human-readable summary of logit bias configuration.
        
        Returns:
            Summary string or None if not configured.
        """
        if not self._logit_bias_manager:
            return None
        from typing import Optional as _Optional, cast
        return cast(_Optional[str], self._logit_bias_manager.get_summary())

    def apply_parser_forbidden_chars(self, parser_name: str) -> bool:
        """Merge parser-defined forbidden characters into logit bias (TASK 53.5).

        Looks up the named parser in the parser registry.  If it defines
        :attr:`forbidden_chars`, those characters are merged into the
        current logit bias configuration.

        Args:
            parser_name: Name of the parser (e.g. ``"RPGMakerMV"``).

        Returns:
            ``True`` if chars were merged, ``False`` otherwise.
        """
        try:
            from CherryAI.formats import get_parser_registry
        except ImportError:
            return False

        parser = get_parser_registry().get(parser_name)
        if parser is None or parser.forbidden_chars is None:
            return False

        fc = parser.forbidden_chars
        base = LogitBiasConfig(
            enabled=self.config.logit_bias_enabled,
            banned_chars=list(
                parse_ban_tokens_arg(self.config.banned_tokens)
            ),
            model=self.config.model,
        )
        merged = merge_parser_forbidden_chars(
            fc.characters, fc.logit_bias, base,
        )

        self._logit_bias_manager = create_logit_bias_manager(
            enabled=merged.enabled,
            banned_chars=merged.banned_chars,
            discouraged_chars=merged.discouraged_chars,
            discourage_strength=merged.discourage_strength,
            model=merged.model,
        )
        self.config.logit_bias_enabled = merged.enabled
        self.logger.info(
            "Parser '%s' forbidden chars merged into logit bias", parser_name,
        )
        return True
    
    def configure_cache(
        self,
        enabled: bool = True,
        mode: Optional[str] = None,
        cache_dir: Optional[str] = None,
        ttl_days: int = 30,
        max_entries: int = 10000,
        clear_cache: bool = False,
    ) -> bool:
        """Configure request caching.
        
        Args:
            enabled: Whether caching is enabled.
            mode: Cache mode string ("strict", "model_only", "any").
            cache_dir: Directory for cache files.
            ttl_days: Time-to-live for entries in days.
            max_entries: Maximum cache entries.
            clear_cache: If True, clear existing cache.
            
        Returns:
            True if configuration was successful.
        """
        if not enabled:
            self._request_cache = None
            self.config.cache_enabled = False
            return True
        
        # Parse cache mode
        cache_mode = parse_cache_mode_arg(mode or self.config.cache_mode)
        
        # Create config
        config = CacheConfig(
            enabled=enabled,
            mode=cache_mode,
            cache_dir=cache_dir or "cache",
            ttl_days=ttl_days,
            max_entries=max_entries,
        )
        
        try:
            self._request_cache = create_request_cache(
                enabled=config.enabled,
                mode=config.mode.value,
                cache_dir=config.cache_dir,
                ttl_days=config.ttl_days,
                max_entries=config.max_entries,
            )
            if self._request_cache:
                self.config.cache_enabled = True
                self.logger.info(f"Request cache enabled (mode: {cache_mode.value})")
                
                if clear_cache:
                    self._request_cache.clear()
                    self.logger.info("Cache cleared")
                
                return True
            else:
                self.config.cache_enabled = False
                return False
        except Exception as e:
            self.logger.error(f"Failed to configure cache: {e}")
            self.config.cache_enabled = False
            return False
    
    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats or None if cache not enabled.
        """
        if not self._request_cache or not self.config.cache_enabled:
            return None
        
        stats = self._request_cache.get_stats()
        from typing import cast, Dict as _Dict, Any as _Any
        return cast(_Dict[str, _Any], stats.to_dict())

    def configure_rate_limiter(
        self,
        enabled: bool = True,
        max_concurrent: int = 3,
        safety_margin: float = 0.1,
        auto_wait: bool = True,
        storage_path: Optional[str] = None,
    ) -> bool:
        """Configure rate limit management.
        
        Args:
            enabled: Whether rate limiting is enabled.
            max_concurrent: Maximum concurrent API requests.
            safety_margin: Safety margin for rate limits (0.0-0.5).
            auto_wait: Automatically wait when rate limited.
            storage_path: Path for persistent usage storage.
            
        Returns:
            True if configuration was successful.
        """
        if not enabled:
            self._rate_limiter = None
            self.config.rate_limit_enabled = False
            return True
        
        # Validate safety margin
        safety_margin = max(0.0, min(0.5, safety_margin))
        
        try:
            self._rate_limiter = create_rate_limiter(
                storage_path=storage_path or "user/rate_limits.json",
                safety_margin=safety_margin,
                auto_wait=auto_wait,
                max_concurrent=max_concurrent,
            )
            
            self.config.rate_limit_enabled = True
            self.config.max_concurrent = max_concurrent
            self.config.rate_limit_margin = safety_margin
            
            self.logger.info(f"Rate limiter enabled (max_concurrent: {max_concurrent}, margin: {safety_margin})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to configure rate limiter: {e}")
            self.config.rate_limit_enabled = False
            return False
    
    def get_rate_limit_stats(self, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get rate limit statistics.
        
        Args:
            model: Model to get stats for (defaults to current config model).
            
        Returns:
            Dictionary with rate limit stats or None if not enabled.
        """
        if not self._rate_limiter or not self.config.rate_limit_enabled:
            return None
        
        target_model = model or self.config.model
        stats = self._rate_limiter.get_stats(target_model)
        
        return {
            "model": stats.model,
            "rpm_used": stats.rpm_used,
            "rpm_limit": stats.rpm_limit,
            "rpm_remaining": stats.rpm_remaining,
            "tpm_used": stats.tpm_used,
            "tpm_limit": stats.tpm_limit,
            "tpm_remaining": stats.tpm_remaining,
            "rpd_used": stats.rpd_used,
            "rpd_limit": stats.rpd_limit,
            "rpd_remaining": stats.rpd_remaining,
            "next_reset_rpm": stats.next_reset_rpm,
            "next_reset_rpd": stats.next_reset_rpd,
        }
    
    def estimate_batch_capacity(
        self,
        lines: int,
        avg_tokens_per_line: int = 50,
        chunk_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Estimate if there's capacity to translate a batch.
        
        Args:
            lines: Number of lines to translate.
            avg_tokens_per_line: Average tokens per line.
            chunk_size: Lines per chunk (defaults to config).
            
        Returns:
            Dictionary with capacity analysis.
        """
        if not self._rate_limiter or not self.config.rate_limit_enabled:
            # Without rate limiter, assume unlimited capacity
            return {
                "model": self.config.model,
                "lines": lines,
                "can_complete_now": True,
                "rate_limiter_enabled": False,
            }
        
        from typing import cast, Dict as _Dict, Any as _Any
        return cast(_Dict[str, _Any], self._rate_limiter.estimate_capacity(
            model=self.config.model,
            lines=lines,
            avg_tokens_per_line=avg_tokens_per_line,
            chunk_size=chunk_size or self.config.chunk_size,
        ))

    def _wait_for_rate_limit(self, estimated_tokens: int = 0) -> None:
        """Enforce rate limiting (requests per minute).

        Priority order:
        1. Header-based rate limiter (per-model, response-header driven).
        2. Advanced sliding-window rate limiter (if enabled).
        3. Simple timestamp-based fallback.

        Args:
            estimated_tokens: Estimated tokens for the request.
        """
        # 1. Header-based rate limiter — always active when initialised
        if self._header_rate_limiter is not None:
            self._header_rate_limiter.pre_request(
                self.config.model,
                estimated_tokens,
            )
            # Do NOT return — still record in the old rate limiter (if present)
            # so that capacity estimates remain accurate.

        # 2. Advanced rate limiter (sliding window)
        if self._rate_limiter and self.config.rate_limit_enabled:
            result = self._rate_limiter.check_rate_limit(
                model=self.config.model,
                estimated_tokens=estimated_tokens,
            )
            
            if not result.allowed and result.wait_time > 0:
                self.logger.info(f"Rate limit: waiting {result.wait_time:.1f}s ({result.reason})")
                time.sleep(result.wait_time)
                result = self._rate_limiter.check_rate_limit(
                    model=self.config.model,
                    estimated_tokens=estimated_tokens,
                )
            
            if not result.allowed and result.wait_time > 0:
                self.logger.warning(f"Rate limit denied: waiting {result.wait_time:.1f}s ({result.reason})")
                time.sleep(result.wait_time)
            
            self._rate_limiter.record_request(
                model=self.config.model,
                input_tokens=estimated_tokens,
            )
            return
        
        # 3. Fallback: simple timestamp-based rate limiting
        now = time.time()
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60]

        if len(self._request_timestamps) >= self.config.rate_limit_requests:
            oldest = self._request_timestamps[0]
            wait_time = 60 - (now - oldest) + 1
            if wait_time > 0:
                self.logger.info(f"Rate limit reached. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                now = time.time()
                self._request_timestamps = [t for t in self._request_timestamps if now - t < 60]

        self._request_timestamps.append(now)

    def check_content_warning(self, text: str) -> Optional[str]:
        """Check if text contains explicit content terms that may trigger API issues.
        
        Args:
            text: Text to check for explicit content terms
            
        Returns:
            Warning message if explicit content detected, None otherwise
        """
        if not self.content_warning_enabled:
            return None
        
        text_lower = text.lower()
        found_terms = [term for term in EXPLICIT_CONTENT_TERMS if term in text_lower]
        
        if found_terms:
            warning = (
                f"⚠️ CONTENT WARNING: Input contains potentially explicit terms: {', '.join(found_terms[:3])}...\n"
                "   Some API providers (OpenAI, Anthropic) may refuse or ban accounts for explicit content.\n"
                "   Consider using Gemini, local models, or providers with fewer content restrictions."
            )
            self._content_warnings.append(warning)
            return warning
        return None

    def write_log_header(self, filename: str, total_lines: int, chunk_count: int, missing_sections: Optional[List[str]] = None) -> None:
        """Write the API log header with statistics.
        
        Args:
            filename: Name of the file being translated
            total_lines: Total lines in the file
            chunk_count: Number of chunks to process
            missing_sections: List of sections not included (Glossary, Rolling Context, etc.)
        """
        if not self.enable_api_log:
            return
        
        self._initial_chunk_count = chunk_count
        
        from pathlib import Path
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine log path - use timestamped file for persistent logging
        if self.api_log_path:
            log_path = Path(self.api_log_path)
        elif self.persistent_log:
            # Create timestamped log file: api_log_YYYYMMDD_HHMMSS.txt
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            log_path = logs_dir / f"api_log_{timestamp}.txt"
        else:
            # Legacy mode: overwrite single file
            log_path = logs_dir / "api_log.txt"
        
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._session_log_path = log_path
        
        # Estimate cost per MILLION tokens (industry standard)
        model = self.config.model.lower()
        if "gpt-4o" in model:
            cost_per_m_input = 2.50
            cost_per_m_output = 10.00
            cost_note = ""
        elif "gpt-4" in model:
            cost_per_m_input = 30.00
            cost_per_m_output = 60.00
            cost_note = ""
        elif "gpt-3.5" in model:
            cost_per_m_input = 0.50
            cost_per_m_output = 1.50
            cost_note = ""
        elif "gemini" in model:
            cost_per_m_input = 0.0
            cost_per_m_output = 0.0
            cost_note = " (FREE TIER)"
        else:
            cost_per_m_input = 1.00
            cost_per_m_output = 2.00
            cost_note = " (estimated)"
        
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"API Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"File: {filename}\n")
            f.write(f"Log File: {log_path.name}\n")
            f.write(f"{'='*80}\n\n")
            f.write(f"[TRANSLATION STATISTICS]\n")
            f.write(f"  Total Lines: {total_lines}\n")
            f.write(f"  Total Chunks: {chunk_count}\n")
            f.write(f"  Model: {self.config.model}\n")
            f.write(f"  Structured Output: JSON mode enabled\n")
            f.write(f"  Cost: ${cost_per_m_input:.2f}/1M input, ${cost_per_m_output:.2f}/1M output{cost_note}\n")
            
            # Skipped lines tracking
            f.write(f"\n[SKIPPED LINES]\n")
            f.write(f"  DEDUP markers: {self._skipped_lines.get('dedup', 0)}\n")
            f.write(f"  Symbols only: {self._skipped_lines.get('symbols', 0)}\n")
            f.write(f"  No source lang: {self._skipped_lines.get('no_source', 0)}\n")
            
            # Missing sections (Glossary, Rolling Context, etc.)
            if missing_sections:
                f.write(f"\n[MISSING SECTIONS]\n")
                for section in missing_sections:
                    f.write(f"  - {section}\n")
            
            if self._content_warnings:
                f.write(f"\n[CONTENT WARNINGS]\n")
                for warning in self._content_warnings:
                    f.write(f"  {warning}\n")
            f.write("\n")

        # Phase 48: Also write a per-project step log header if configured
        try:
            if self._step_log_path:
                from .mainhelper import write_step_log_header
                header = {
                    "CherryAI Translation Log": "",
                    "Project": filename,
                    "Started": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "Model": self.config.model,
                    "Provider": self.config.provider,
                    "Lines/Chunk": str(self.config.chunk_size),
                    "Total Lines": str(total_lines),
                    "Retry Strategy": self.config.retry_strategy,
                    "Max Retries": str(self.config.retries),
                }
                write_step_log_header(self._step_log_path, header)
        except Exception:
            pass

    def _format_system_prompt_for_log(self, content: str) -> str:
        """Format system prompt content for readable log output.
        
        Expands escaped newlines and formats sections with proper indentation.
        
        Args:
            content: The raw system prompt string with escaped newlines
            
        Returns:
            Formatted string with proper line breaks and indentation
        """
        # Replace escaped newlines with actual newlines
        formatted = content.replace("\\n", "\n")
        
        # Add visual separators for major sections
        section_markers = [
            "# Game Context",
            "# Glossary",
            "# Game Characters", 
            "# Special Handling Instructions",
            "**Guidelines:**",
            "**Output Examples**",
            "Game Content:",
        ]
        
        for marker in section_markers:
            if marker in formatted:
                formatted = formatted.replace(marker, f"\n{'-'*40}\n{marker}")
        
        return formatted

    def _format_lines_for_log(self, lines_json: str) -> str:
        """Format the lines JSON for readable log output.
        
        Parses the JSON and displays each line on its own row.
        
        Args:
            lines_json: JSON string containing {"lines": [...]}
            
        Returns:
            Formatted string with each line numbered
        """
        try:
            data = json.loads(lines_json)
            lines = data.get("lines", [])
            if not lines:
                return lines_json
            
            result = ["INPUT LINES:"]
            for i, line in enumerate(lines, 1):
                # Truncate very long lines for readability
                display_line = line if len(line) <= 120 else line[:117] + "..."
                result.append(f"  [{i:3d}] {display_line}")
            return "\n".join(result)
        except (json.JSONDecodeError, TypeError):
            return lines_json

    def _format_translations_for_log(self, content: str) -> str:
        """Format translation response for readable log output.
        
        Parses the JSON response and displays each translation on its own row.
        
        Args:
            content: JSON string containing {"translations": [...]}
            
        Returns:
            Formatted string with each translation numbered
        """
        try:
            data = json.loads(content)
            translations = data.get("translations", [])
            if not translations:
                return content
            
            result = ["OUTPUT TRANSLATIONS:"]
            for i, line in enumerate(translations, 1):
                # Truncate very long lines for readability  
                display_line = line if len(line) <= 120 else line[:117] + "..."
                result.append(f"  [{i:3d}] {display_line}")
            return "\n".join(result)
        except (json.JSONDecodeError, TypeError):
            return content

    def _log_api_call(self, request_data: Dict[str, Any], response_data: Dict[str, Any]) -> None:
        """Log an API request-response pair to the log file.
        
        Formats output for human readability:
        - System prompts have proper line breaks
        - Each input/output line is on its own row
        - Sections are visually separated
        
        Args:
            request_data: The request sent to the API (messages, model, etc.)
            response_data: The response received from the API
        """
        if not self.enable_api_log:
            return
            
        self._chunk_counter += 1
        entry = {
            "chunk_number": self._chunk_counter,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "request": request_data,
            "response": response_data,
        }
        self._api_log_entries.append(entry)
        
        # Use session log path if available, otherwise fall back to default
        from pathlib import Path
        if self._session_log_path:
            log_path = self._session_log_path
        elif self.api_log_path:
            log_path = Path(self.api_log_path)
        else:
            log_path = Path(__file__).parent.parent / "logs" / "api_log.txt"
        
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Track token usage
        usage = response_data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens

        # Track cached tokens from prompt caching
        prompt_details = usage.get("prompt_tokens_details", {})
        if isinstance(prompt_details, dict):
            cached_tokens = prompt_details.get("cached_tokens", 0) or 0
        else:
            cached_tokens = 0
        self._total_cached_tokens += cached_tokens

        # Track completion token breakdown (reasoning, predictions)
        comp_details = usage.get("completion_tokens_details", {})
        if isinstance(comp_details, dict):
            reasoning_tokens = comp_details.get("reasoning_tokens", 0) or 0
            accepted_pred = comp_details.get(
                "accepted_prediction_tokens", 0,
            ) or 0
            rejected_pred = comp_details.get(
                "rejected_prediction_tokens", 0,
            ) or 0
        else:
            reasoning_tokens = accepted_pred = rejected_pred = 0
        self._total_reasoning_tokens += reasoning_tokens
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"CHUNK #{self._chunk_counter} - {entry['timestamp']}")
            f.write(f" | Tokens: {prompt_tokens} in / {completion_tokens} out")
            if cached_tokens:
                f.write(f" | Cached: {cached_tokens}")
            if reasoning_tokens:
                f.write(f" | Reasoning: {reasoning_tokens}")
            f.write(f" | Running Total: {self._total_prompt_tokens + self._total_completion_tokens}\n")
            f.write(f"{'='*80}\n\n")
            
            # --- REQUEST SECTION (LOG-ONLY formatting, not sent to API) ---
            f.write("--- REQUEST ---\n")
            f.write(f"Model: {request_data.get('model', 'unknown')}\n")
            f.write(f"Temperature: {request_data.get('temperature', 'unknown')}\n\n")
            
            # Format messages for readability (LOG-ONLY)
            messages = request_data.get("messages", [])
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                
                if role == "system":
                    f.write(f"[SYSTEM PROMPT]\n")
                    f.write(f"{'-'*40}\n")
                    formatted_prompt = self._format_system_prompt_for_log(content)
                    f.write(formatted_prompt)
                    f.write(f"\n{'-'*40}\n\n")
                    
                elif role == "user":
                    f.write(f"[USER MESSAGE]\n")
                    formatted_lines = self._format_lines_for_log(content)
                    f.write(formatted_lines)
                    f.write("\n\n")
            
            # --- RESPONSE SECTION ---
            f.write("--- RESPONSE ---\n")
            
            content = response_data.get("content", "")
            if content:
                formatted_translations = self._format_translations_for_log(content)
                f.write(formatted_translations)
                f.write("\n\n")
            
            # Usage stats
            if usage:
                f.write(f"[USAGE]\n")
                f.write(f"  Prompt Tokens: {prompt_tokens}\n")
                if cached_tokens:
                    f.write(f"  Cached Tokens: {cached_tokens}\n")
                f.write(f"  Completion Tokens: {completion_tokens}\n")
                if reasoning_tokens:
                    f.write(f"  Reasoning Tokens: {reasoning_tokens}\n")
                if accepted_pred:
                    f.write(
                        f"  Accepted Prediction Tokens: {accepted_pred}\n",
                    )
                if rejected_pred:
                    f.write(
                        f"  Rejected Prediction Tokens: {rejected_pred}\n",
                    )
                f.write(f"  Total Tokens: {usage.get('total_tokens', 0)}\n")
            
            finish_reason = response_data.get("finish_reason", "")
            if finish_reason:
                f.write(f"  Finish Reason: {finish_reason}\n")
            
            f.write("\n")

        # Phase 48: Per-chunk summary to step log
        try:
            if self._step_log_path:
                from .mainhelper import append_step_log_entry
                entry_lines = [
                    f"--- Chunk {self._chunk_counter}/{self._initial_chunk_count} ---",
                    f"  Status: PASS",
                    f"  Input Tokens: {prompt_tokens}",
                    f"  Output Tokens: {completion_tokens}",
                ]
                if cached_tokens:
                    entry_lines.append(f"  Cached Tokens: {cached_tokens}")
                if reasoning_tokens:
                    entry_lines.append(
                        f"  Reasoning Tokens: {reasoning_tokens}",
                    )
                entry_lines.append("")
                append_step_log_entry(self._step_log_path, "\n".join(entry_lines))
        except Exception:
            pass

    def get_api_log(self) -> List[Dict[str, Any]]:
        """Get all logged API calls.
        
        Returns:
            List of request-response pairs logged during this session.
        """
        return self._api_log_entries.copy()

    def write_log_footer(self) -> None:
        """Write the API log footer with final statistics."""
        if not self.enable_api_log:
            return
        
        from pathlib import Path
        # Use session log path if available, otherwise fall back to default
        if self._session_log_path:
            log_path = self._session_log_path
        elif self.api_log_path:
            log_path = Path(self.api_log_path)
        else:
            log_path = Path(__file__).parent.parent / "logs" / "api_log.txt"
        
        if not log_path.exists():
            return
        
        # Calculate cost
        model = self.config.model.lower()
        if "gpt-4o" in model:
            cost_per_m_input, cost_per_m_output = 2.50, 10.00
        elif "gpt-4" in model:
            cost_per_m_input, cost_per_m_output = 30.00, 60.00
        elif "gpt-3.5" in model:
            cost_per_m_input, cost_per_m_output = 0.50, 1.50
        elif "gemini" in model:
            cost_per_m_input, cost_per_m_output = 0.0, 0.0
        else:
            cost_per_m_input, cost_per_m_output = 1.00, 2.00
        
        input_cost = (self._total_prompt_tokens / 1_000_000) * cost_per_m_input
        output_cost = (self._total_completion_tokens / 1_000_000) * cost_per_m_output
        total_cost = input_cost + output_cost
        # Prompt caching saves up to 50% on cached input tokens
        cached_savings = (self._total_cached_tokens / 1_000_000) * cost_per_m_input * 0.5
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"TRANSLATION COMPLETE - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n\n")
            f.write(f"[FINAL STATISTICS]\n")
            f.write(f"  Chunks Processed: {self._chunk_counter}/{self._initial_chunk_count}\n")
            f.write(f"  Total Prompt Tokens: {self._total_prompt_tokens:,}\n")
            if self._total_cached_tokens:
                f.write(f"  Cached Prompt Tokens: {self._total_cached_tokens:,}\n")
                cache_pct = (
                    self._total_cached_tokens / self._total_prompt_tokens * 100
                    if self._total_prompt_tokens else 0
                )
                f.write(f"  Cache Hit Rate: {cache_pct:.1f}%\n")
            f.write(f"  Total Completion Tokens: {self._total_completion_tokens:,}\n")
            if self._total_reasoning_tokens:
                f.write(
                    f"  Reasoning Tokens: {self._total_reasoning_tokens:,}\n",
                )
            f.write(f"  Total Tokens: {self._total_prompt_tokens + self._total_completion_tokens:,}\n")
            if "gemini" in model:
                f.write(f"  Estimated Cost: FREE (Gemini free tier)\n")
            else:
                f.write(f"  Estimated Cost: ${total_cost:.4f}\n")
                if cached_savings > 0:
                    f.write(f"  Cache Savings: ~${cached_savings:.4f}\n")
            f.write("\n")
        
        # Update summary file
        self._update_log_summary(log_path, total_cost)

        # Phase 48: Also write per-project step log footer
        try:
            if self._step_log_path:
                from .mainhelper import write_step_log_footer
                footer: Dict[str, str] = {
                    "Translation Summary": "",
                    "Completed": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "Chunks Processed": f"{self._chunk_counter}/{self._initial_chunk_count}",
                    "Total Tokens": (
                        f"{self._total_prompt_tokens + self._total_completion_tokens:,} "
                        f"(Input: {self._total_prompt_tokens:,}, "
                        f"Output: {self._total_completion_tokens:,})"
                    ),
                    "Estimated Cost": f"${total_cost:.4f} USD",
                }
                if self._total_cached_tokens:
                    cache_pct = (
                        self._total_cached_tokens / self._total_prompt_tokens * 100
                        if self._total_prompt_tokens else 0
                    )
                    footer["Cached Tokens"] = (
                        f"{self._total_cached_tokens:,} ({cache_pct:.1f}%)"
                    )
                    if cached_savings > 0:
                        footer["Cache Savings"] = f"~${cached_savings:.4f} USD"
                if self._total_reasoning_tokens:
                    footer["Reasoning Tokens"] = (
                        f"{self._total_reasoning_tokens:,}"
                    )
                write_step_log_footer(self._step_log_path, footer)
        except Exception:
            pass

    def _update_log_summary(self, log_path: Path, total_cost: float) -> None:
        """Update the API log summary CSV with session statistics.
        
        Args:
            log_path: Path to the session log file
            total_cost: Total estimated cost for this session
        """
        import csv
        from pathlib import Path
        
        summary_path = log_path.parent / "api_log_summary.csv"
        
        # Check if summary file exists to determine if we need headers
        write_header = not summary_path.exists()
        
        # Prepare row data
        row = {
            "date": time.strftime("%Y-%m-%d"),
            "time": time.strftime("%H:%M:%S"),
            "log_file": log_path.name,
            "model": self.config.model,
            "chunks": self._chunk_counter,
            "prompt_tokens": self._total_prompt_tokens,
            "completion_tokens": self._total_completion_tokens,
            "cached_tokens": self._total_cached_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "cost": f"{total_cost:.4f}",
        }
        
        try:
            with open(summary_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
            self.logger.debug(f"Updated API log summary: {summary_path}")
        except Exception as exc:
            self.logger.warning(f"Failed to update API log summary: {exc}")

    def _create_chunker(self) -> Chunker:
        """Create a Chunker based on current configuration.
        
        Returns:
            Configured Chunker instance.
        """
        try:
            mode = ChunkMode(self.config.chunk_mode.lower())
        except ValueError:
            self.logger.warning(
                f"Invalid chunk_mode '{self.config.chunk_mode}', using 'lines'"
            )
            mode = ChunkMode.LINES
        
        config = ChunkerConfig(
            mode=mode,
            max_lines=self.config.chunk_size,
            max_tokens=self.config.chunk_max_tokens,
            model=self.config.model,
            reserve_tokens=0,  # Reserve handled separately if needed
        )
        return Chunker(config)

    def translate_batch(self, lines: List[str], system_prompt: Optional[str] = None) -> List[str]:
        """Translate a list of lines using the configured API.

        Handles chunking, validation, and retries. Supports three chunking modes:
        - lines: Chunk by line count (default)
        - tokens: Chunk by token count using tiktoken
        - hybrid: Use whichever limit is reached first

        When ``self.config.model`` is ``"mock"``, translation is routed to
        :class:`~functions.mock_translator.MockTranslator` instead of a live
        API, enabling full pipeline testing without network or API keys.
        """
        if not lines:
            return []

        # Route to mock translator when model is "mock"
        if self.config.model == "mock":
            return self._mock_translate(lines, system_prompt=system_prompt)

        if not self.client:
            raise TranslationError("API Client not initialized (missing API key?)")
        
        # Check cache first if enabled
        if self._request_cache and self.config.cache_enabled:
            cached = self._request_cache.get(
                lines,
                model=self.config.model,
                temperature=self.config.temperature,
                prompt=system_prompt,
            )
            if cached is not None:
                self.logger.info(f"Cache hit: {len(lines)} lines retrieved from cache")
                from typing import cast
                return cast(List[str], cached)

        results: List[str] = []
        
        # Use the configurable chunker
        chunker = self._create_chunker()
        chunks = chunker.chunk_lines(lines)
        
        total_chunks = len(chunks)
        mode_info = f" (mode={self.config.chunk_mode})" if self.config.chunk_mode != "lines" else ""
        self.logger.info(f"Starting translation: {len(lines)} lines in {total_chunks} chunks{mode_info}")

        for i, chunk in enumerate(chunks):
            chunk_info = chunker.get_chunk_info(chunk)
            self.logger.info(
                f"Processing chunk {i+1}/{total_chunks} "
                f"({chunk_info['line_count']} lines, ~{chunk_info['token_count']} tokens)"
            )
            translated_chunk = self._translate_chunk_with_retry(chunk, system_prompt)
            results.extend(translated_chunk)
        
        # Store in cache if enabled
        if self._request_cache and self.config.cache_enabled and len(results) == len(lines):
            self._request_cache.store(
                lines,
                results,
                model=self.config.model,
                temperature=self.config.temperature,
                prompt=system_prompt,
            )
            self.logger.debug(f"Cached {len(lines)} lines")

        return results

    def _mock_translate(self, lines: List[str], system_prompt: Optional[str] = None) -> List[str]:
        """Route translation to MockTranslator for offline pipeline testing.

        Uses the ``mock_translator`` module to produce deterministic nonsense
        output with optional deliberate flaw injection (Phase 56).

        When a *system_prompt* is provided the context type embedded in it
        (``"# Content Type: …"``) is detected so that mock output can be
        adjusted accordingly (e.g. shorter labels for Menu/Choice content).
        """
        from .mock_translator import create_mock_translator

        # Detect context_type from system_prompt if available.
        context_type: Optional[str] = None
        if system_prompt:
            import re as _re
            _m = _re.search(r"# Content Type:\s*(\S+)", system_prompt, _re.IGNORECASE)
            if _m:
                context_type = _m.group(1).strip(".,;").lower()
                self.logger.info("Mock translation context_type: %s", context_type)

        self.logger.info("Using Mock Translation for %d lines (context=%s)", len(lines), context_type or "unknown")
        translator = create_mock_translator(
            enable_flaws=True,
            intensity="moderate",
            seed=42,
            context_type=context_type,
        )
        return translator.translate_batch(lines)

    def translate_line_by_line(
        self,
        lines: List[str],
        context_lines: int = 1,
        minimal_prompt: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[str]:
        """Translate lines one at a time with minimal prompt.
        
        This mode is useful for:
        - Debugging translation issues on specific lines
        - Files with highly varied content
        - Maximum control over individual translations
        - Testing different models with identical inputs
        
        Args:
            lines: List of lines to translate.
            context_lines: Number of adjacent lines to include as read-only context (0-3).
            minimal_prompt: If True, use minimal prompt without glossary/summary.
            progress_callback: Optional callback(current, total) for progress updates.
            
        Returns:
            List of translated lines.
        """
        if not self.client:
            raise TranslationError("API Client not initialized (missing API key?)")
        
        if not lines:
            return []
        
        results: List[str] = []
        total = len(lines)
        
        self.logger.info(f"Starting line-by-line translation: {total} lines")
        
        for i, line in enumerate(lines):
            if progress_callback:
                progress_callback(i + 1, total)
            
            # Skip empty lines
            if not line.strip():
                results.append(line)
                continue
            
            # Build context (previous and next lines)
            context_before = lines[max(0, i - context_lines):i] if context_lines > 0 else []
            context_after = lines[i + 1:i + 1 + context_lines] if context_lines > 0 else []
            
            # Translate single line
            translated = self._translate_single_line(
                line=line,
                context_before=context_before,
                context_after=context_after,
                minimal_prompt=minimal_prompt,
                line_index=i,
            )
            results.append(translated)
        
        self.logger.info(f"Line-by-line translation complete: {total} lines")
        return results
    
    def _translate_single_line(
        self,
        line: str,
        context_before: List[str],
        context_after: List[str],
        minimal_prompt: bool,
        line_index: int,
    ) -> str:
        """Translate a single line with optional context.
        
        Args:
            line: The line to translate.
            context_before: Previous lines for context (read-only).
            context_after: Following lines for context (read-only).
            minimal_prompt: If True, use minimal system prompt.
            line_index: Line index for logging.
            
        Returns:
            Translated line.
        """
        # Build prompt
        if minimal_prompt:
            system_prompt = (
                f"Translate the following text from {self.config.source_lang} to {self.config.target_lang}.\n"
                "Preserve all placeholders (like __PROTECTED__, __CODE__) exactly.\n"
                "Output only the translation, no explanations or markdown."
            )
        else:
            system_prompt = (
                f"You are a professional translator translating from {self.config.source_lang} to {self.config.target_lang}.\n"
                "Preserve all special tokens like __PROTECTED__ exactly.\n"
                "Output only the translation, no explanations."
            )
        
        # Build user message with context
        user_parts = []
        
        if context_before:
            context_text = "\n".join(f"  {l}" for l in context_before)
            user_parts.append(f"[Previous lines for context - do not translate these:]\n{context_text}\n")
        
        user_parts.append(f"[Translate this line:]\n{line}")
        
        if context_after:
            context_text = "\n".join(f"  {l}" for l in context_after)
            user_parts.append(f"\n[Following lines for context - do not translate these:]\n{context_text}")
        
        user_content = "\n".join(user_parts)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        cache_params = self.get_prompt_cache_params()
        
        # Execute with retry
        attempt = 0
        max_retries = self.config.retries
        last_error: Optional[Exception] = None
        
        # Estimate tokens for rate limiting
        estimated_tokens = (len(line) + sum(len(l) for l in context_before) + sum(len(l) for l in context_after)) // 4 + 10
        
        while attempt < max_retries:
            try:
                self._wait_for_rate_limit(estimated_tokens=estimated_tokens)
                
                if self.client is None:
                    raise TranslationError("API client not initialized")
                
                from typing import Any, cast
                client_any = cast(Any, self.client)
                request_params: Dict[str, Any] = {
                    "model": self.config.model,
                    "messages": cast(Any, messages),
                    "temperature": self.config.temperature,
                }
                if cache_params:
                    request_params.update(cache_params)
                response = client_any.chat.completions.create(**request_params)
                
                content = response.choices[0].message.content
                if not content:
                    raise TranslationError(f"Empty response for line {line_index}")
                
                # Clean up response (remove markdown, extra whitespace)
                from typing import cast
                content_str = cast(str, content)
                result = content_str.strip()
                
                # Remove common markdown artifacts
                if result.startswith("```") and result.endswith("```"):
                    result = result[3:-3].strip()
                if result.startswith('"') and result.endswith('"'):
                    result = result[1:-1]
                
                # Log if enabled
                if self.enable_api_log:
                    request_data = {
                        "model": self.config.model,
                        "temperature": self.config.temperature,
                        "mode": "line_by_line",
                        "line_index": line_index,
                        "messages": messages,
                        "prompt_cache_params": cache_params if cache_params else None,
                    }
                    response_data = {
                        "content": result,
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        } if response.usage else None,
                    }
                    self._log_api_call(request_data, response_data)

                # Structured API log for API Log Window
                try:
                    from .api_log import (
                        LogCategory, LogStatus, LogEntrySent, LogEntryReceived,
                    )
                    sent_entry = LogEntrySent(
                        model=self.config.model,
                        provider=self.config.provider,
                        temperature=self.config.temperature,
                        system_prompt=system_prompt,
                        user_content=user_content,
                        line_count=1,
                        extra={
                            "mode": "line_by_line",
                            "line_index": line_index,
                            **cache_params,
                        },
                    )
                    _usage_lbl = response.usage
                    _ptd_lbl = getattr(_usage_lbl, "prompt_tokens_details", None) if _usage_lbl else None
                    _ctd_lbl = getattr(_usage_lbl, "completion_tokens_details", None) if _usage_lbl else None
                    recv_entry = LogEntryReceived(
                        content=result,
                        prompt_tokens=_usage_lbl.prompt_tokens if _usage_lbl else 0,
                        completion_tokens=_usage_lbl.completion_tokens if _usage_lbl else 0,
                        total_tokens=getattr(_usage_lbl, "total_tokens", 0) if _usage_lbl else 0,
                        cached_tokens=(getattr(_ptd_lbl, "cached_tokens", 0) or 0) if _ptd_lbl else 0,
                        reasoning_tokens=(getattr(_ctd_lbl, "reasoning_tokens", 0) or 0) if _ctd_lbl else 0,
                    )
                    self._api_log_store.log_pair(
                        LogCategory.MAIN_TRANSLATION, sent_entry, recv_entry,
                        LogStatus.SUCCESS,
                    )
                except Exception:
                    pass

                return result
                
            except (RateLimitError, APITimeoutError) as e:
                attempt += 1
                last_error = e
                wait_time = min(2 ** attempt, 60)
                self.logger.warning(f"Line {line_index} retry {attempt}: {e}. Waiting {wait_time}s...")
                time.sleep(wait_time)
            except Exception as e:
                attempt += 1
                last_error = e
                if attempt >= max_retries:
                    break
                time.sleep(1)
        
        # Log failure to structured API log
        try:
            from .api_log import (
                LogCategory, LogStatus, LogEntrySent, LogEntryReceived,
            )
            sent_entry = LogEntrySent(
                model=self.config.model,
                provider=self.config.provider,
                temperature=self.config.temperature,
                system_prompt=system_prompt,
                user_content=user_content,
                line_count=1,
                extra={
                    "mode": "line_by_line",
                    "line_index": line_index,
                    **cache_params,
                },
            )
            recv_entry = LogEntryReceived(
                error_message=str(last_error) if last_error is not None else "",
            )
            self._api_log_store.log_pair(
                LogCategory.MAIN_TRANSLATION, sent_entry, recv_entry,
                LogStatus.FAILED,
            )
        except Exception:
            pass

        self.logger.error(f"Failed to translate line {line_index} after {max_retries} attempts: {last_error}")
        # Return original line on failure
        return line

    def _translate_chunk_with_retry(self, chunk: List[str], system_prompt: Optional[str]) -> List[str]:
        """Translate a single chunk with retry logic.

        Fatal errors (auth, model not found, etc.) raise
        :class:`TranslationAbortError` immediately without retrying.
        Retryable errors (rate limit, timeout, server error) use
        exponential backoff up to *max_retries* attempts.
        """
        import random
        attempt = 0
        last_error: Exception | None = None
        max_retries = max(self.config.retries, 5)

        # Token estimation per spec:
        # estimated_tokens = sent_request_token_count + (input_line_token_count * 1.5)
        input_line_tokens = sum(len(line) // 4 + 1 for line in chunk)
        # Approximate system prompt tokens (sent_request overhead)
        sent_request_tokens = input_line_tokens + 200  # ~200 tok for system prompt
        estimated_tokens = int(sent_request_tokens + input_line_tokens * 1.5)

        while attempt < max_retries:
            try:
                self._wait_for_rate_limit(estimated_tokens=estimated_tokens)
                return self._translate_chunk(chunk, system_prompt)
            except TranslationAbortError:
                # Already classified and fatal — propagate immediately
                raise
            except (RateLimitError, APITimeoutError, APIError, TranslationError) as e:
                classified = classify_api_error(e)
                if classified.is_fatal:
                    raise TranslationAbortError(classified) from e
                attempt += 1
                last_error = e
                base_wait = 3 ** attempt
                jitter = random.uniform(0, base_wait * 0.2)
                wait_time = min(base_wait + jitter, 120)
                self.logger.warning(
                    "Translation failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt, max_retries, e, wait_time,
                )
                time.sleep(wait_time)
            except Exception as e:
                classified = classify_api_error(e)
                if classified.is_fatal:
                    raise TranslationAbortError(classified) from e
                self.logger.error("Unexpected error during translation: %s", e)
                raise TranslationError(f"Unexpected error: {e}") from e

        # All retries exhausted — classify the last error for the user
        if last_error is not None:
            classified = classify_api_error(last_error)
            raise TranslationAbortError(classified)
        raise TranslationError(
            f"Failed to translate chunk after {max_retries} attempts.",
        )

    def _translate_chunk(self, chunk: List[str], system_prompt: Optional[str]) -> List[str]:
        """Perform the actual API call for a chunk."""
        if not self.client:
             raise TranslationError("Client not initialized")

        # Check for content warnings
        chunk_text = "\n".join(chunk)
        warning = self.check_content_warning(chunk_text)
        if warning:
            self.logger.warning(warning)

        # Construct the prompt
        # We use JSON mode to ensure structured output
        user_content = json.dumps({"lines": chunk}, ensure_ascii=False)

        # JSON format instructions are always appended
        json_instructions = (
            "Output must be a valid JSON object with a single key "
            "'translations' containing an array of strings.\n"
            "The array must have exactly the same number of elements "
            "as the input 'lines' array.\n"
            "Preserve all special tokens like __PROTECTED__ exactly.\n"
            "Do not translate proper names if you are unsure, or "
            "follow the glossary if provided."
        )

        if system_prompt and system_prompt.strip():
            # Full system prompt assembled by the caller (translate step)
            # already contains Language, System Instructions, Style, Tone,
            # Summary, Genre, Conditional Prompts, Glossary, Rolling Context.
            final_system_prompt = (
                f"{system_prompt.strip()}\n\n"
                f"# Output Format\n{json_instructions}"
            )
        else:
            # Fallback: no caller prompt — use a minimal default
            final_system_prompt = (
                f"You are a professional translator translating from "
                f"{self.config.source_lang} to {self.config.target_lang}.\n"
                f"{json_instructions}"
            )

        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": user_content}
        ]

        # Build API call parameters
        #
        # Local providers (LM Studio, Ollama) may not support
        # {"type": "json_object"}.  LM Studio requires
        # {"type": "json_schema", "json_schema": {...}} instead.
        # We detect the provider and choose the right format.
        if self._provider:
            response_fmt: Dict[str, Any] = self._provider.get_response_format(
                self.config.model
            )
        elif self.is_local_provider():
            response_fmt: Dict[str, Any] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "translation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "translations": {
                                "type": "array",
                                "items": {"type": "string"},
                            }
                        },
                        "required": ["translations"],
                        "additionalProperties": False,
                    },
                },
            }
        else:
            response_fmt = {"type": "json_object"}

        api_params: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "response_format": response_fmt,
        }

        # Temperature: use provider to check if model supports it
        if self._provider:
            temp_cfg = self._provider.get_temperature_config(self.config.model)
            if temp_cfg.supported:
                api_params["temperature"] = self.config.temperature
        else:
            api_params["temperature"] = self.config.temperature
        
        # Add thinking mode parameters if enabled
        thinking_params = self.get_thinking_params()
        if thinking_params:
            if "reasoning_effort" in thinking_params:
                # OpenAI Chat Completions: top-level parameter
                api_params["reasoning_effort"] = thinking_params["reasoning_effort"]
            elif "thinking" in thinking_params:
                # Claude via OpenAI SDK: extra_body for thinking budget
                api_params["extra_body"] = thinking_params
                budget = thinking_params["thinking"].get("budget_tokens", 10000)
                api_params["max_tokens"] = budget + 4000
            self.logger.debug("Thinking params for %s: %s", self.config.model, thinking_params)

        # Add logit bias parameters if enabled
        logit_bias = self.get_logit_bias_params()
        if logit_bias:
            api_params["logit_bias"] = logit_bias
            self.logger.debug(f"Logit bias enabled with {len(logit_bias)} token biases")

        # Add prompt caching parameters for supported OpenAI models
        cache_params = self.get_prompt_cache_params()
        if cache_params:
            api_params.update(cache_params)
            self.logger.debug(f"Prompt caching: {cache_params}")

        try:
            if self.client is None:
                raise TranslationError("API client not initialized")
            from typing import Any, cast
            client_any = cast(Any, self.client)
            raw_resp = client_any.chat.completions.with_raw_response.create(
                **api_params,
            )
            response = raw_resp.parse()
            resp_headers = {
                k.lower(): v for k, v in raw_resp.headers.items()
            }
            # Feed response headers into the header-based rate limiter
            if self._header_rate_limiter is not None:
                self._header_rate_limiter.update_from_headers(
                    self.config.model, resp_headers,
                )
        except TranslationError:
            raise
        except TranslationAbortError:
            raise
        except Exception as e:
            # Try provider-level classification first, fall back to legacy
            classified = None
            if self._provider:
                classified = self._provider.classify_error(e)
            if classified is None:
                classified = classify_api_error(e)
            if classified.is_fatal:
                raise TranslationAbortError(classified) from e
            raise TranslationError(f"OpenAI API call failed: {str(e)}") from e

        content = response.choices[0].message.content
        if not content:
            raise TranslationError("API returned empty response")
        
        # Log API call if enabled
        if self.enable_api_log:
            request_data = {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "messages": messages,
                "thinking_enabled": bool(thinking_params),
                "logit_bias_enabled": bool(logit_bias),
                "logit_bias_count": len(logit_bias) if logit_bias else 0,
                "prompt_cache_params": cache_params if cache_params else None,
            }
            # Extract prompt_tokens_details for cached token tracking
            usage_dict: Dict[str, Any] = {}
            if response.usage:
                usage_dict = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                ptd = getattr(response.usage, "prompt_tokens_details", None)
                if ptd is not None:
                    usage_dict["prompt_tokens_details"] = {
                        "cached_tokens": getattr(ptd, "cached_tokens", 0) or 0,
                    }
            response_data = {
                "content": content,
                "finish_reason": response.choices[0].finish_reason if response.choices else None,
                "usage": usage_dict if usage_dict else None,
            }
            self._log_api_call(request_data, response_data)

        # Structured API log for API Log Window
        try:
            from .api_log import (
                LogCategory, LogStatus, LogEntrySent, LogEntryReceived,
            )
            sent_entry = LogEntrySent(
                model=self.config.model,
                provider=self.config.provider,
                temperature=self.config.temperature,
                system_prompt=final_system_prompt,
                user_content=user_content,
                chunk_index=self._chunk_counter,
                total_chunks=self._initial_chunk_count,
                line_count=len(chunk),
                extra=cache_params.copy(),
            )
            _usage = response.usage
            _ptd = getattr(_usage, "prompt_tokens_details", None) if _usage else None
            _ctd = getattr(_usage, "completion_tokens_details", None) if _usage else None
            recv_entry = LogEntryReceived(
                content=content,
                prompt_tokens=_usage.prompt_tokens if _usage else 0,
                completion_tokens=_usage.completion_tokens if _usage else 0,
                total_tokens=_usage.total_tokens if _usage else 0,
                cached_tokens=(getattr(_ptd, "cached_tokens", 0) or 0) if _ptd else 0,
                reasoning_tokens=(getattr(_ctd, "reasoning_tokens", 0) or 0) if _ctd else 0,
                finish_reason=response.choices[0].finish_reason or "" if response.choices else "",
            )
            self._api_log_store.log_pair(
                LogCategory.MAIN_TRANSLATION, sent_entry, recv_entry,
                LogStatus.SUCCESS,
            )
        except Exception:
            pass

        # Parse JSON output
        try:
            data = json.loads(content)
            translations = data.get("translations")
        except json.JSONDecodeError:
            # Non-structured output is fatal — model cannot produce JSON
            classified = classify_api_error(
                TranslationError("API returned invalid JSON"),
            )
            raise TranslationAbortError(classified)
        
        if not isinstance(translations, list):
            classified = classify_api_error(
                TranslationError(
                    "API returned JSON but 'translations' is not a list",
                ),
            )
            raise TranslationAbortError(classified)

        # Validation
        if len(translations) != len(chunk):
            raise TranslationError(f"Line count mismatch: Input {len(chunk)}, Output {len(translations)}")

        # Check for refusal or empty lines (basic heuristic)
        for i, (original, translated) in enumerate(zip(chunk, translations)):
            if not translated.strip() and original.strip():
                # Allow empty translation only if original was empty (though chunking usually handles non-empty)
                # But here we assume input chunk might have empty lines? 
                # Actually, usually we filter empty lines before sending, but let's be safe.
                pass 
            
            # Check for common refusal patterns
            if "I cannot translate" in translated or "I am unable to translate" in translated:
                 raise TranslationError(f"API refused to translate line {i}: {translated}")

        return translations

    # ------------------------------------------------------------------
    # Batch API methods (TASK 17.1)
    # ------------------------------------------------------------------

    def submit_batch_translation(
        self,
        chunks: List[List[str]],
        system_prompt: Optional[str] = None,
        manifest_path: str = "",
    ) -> "BatchJob":
        """Submit translation chunks as an async Batch API job.

        Args:
            chunks: List of line-lists (same format as ``translate_batch``).
            system_prompt: Optional additional system prompt.
            manifest_path: Path to the manifest file for tracking.

        Returns:
            A :class:`BatchJob` tracking object.

        Raises:
            TranslationError: If the batch cannot be submitted.
        """
        from .batch_tracker import build_batch_jsonl, submit_batch, BatchJob

        if not self.client:
            raise TranslationError("API client not initialized")

        jsonl = build_batch_jsonl(
            chunks=chunks,
            model=self.config.model,
            source_lang=self.config.source_lang,
            target_lang=self.config.target_lang,
            system_prompt=system_prompt,
            temperature=self.config.temperature,
        )

        chunk_ids = [f"chunk_{i:04d}" for i in range(len(chunks))]

        try:
            job = submit_batch(
                client=self.client,
                jsonl_content=jsonl,
                model=self.config.model,
                manifest_path=manifest_path,
                chunk_ids=chunk_ids,
            )
        except Exception as exc:
            raise TranslationError(f"Batch submission failed: {exc}") from exc

        self.logger.info(
            "Batch %s submitted (%d chunks, model=%s)",
            job.batch_id,
            len(chunks),
            self.config.model,
        )
        return job

    def check_batch_status(self, batch_id: str) -> "BatchJob":
        """Poll the provider for the latest batch status.

        Returns:
            Updated :class:`BatchJob`.
        """
        from .batch_tracker import poll_batch_status

        if not self.client:
            raise TranslationError("API client not initialized")
        return poll_batch_status(self.client, batch_id)

    def retrieve_batch_translations(
        self,
        batch_id: str,
        total_chunks: int,
    ) -> Optional[Dict[int, List[str]]]:
        """Download and parse results for a completed batch.

        Args:
            batch_id: The batch ID to retrieve.
            total_chunks: Expected number of chunks.

        Returns:
            Mapping ``{chunk_index: [translated_lines]}``,
            or ``None`` if results are not available yet.
        """
        from .batch_tracker import retrieve_batch_results, parse_batch_results

        if not self.client:
            raise TranslationError("API client not initialized")

        raw = retrieve_batch_results(self.client, batch_id)
        if raw is None:
            return None

        return parse_batch_results(raw, total_chunks)

    def cancel_batch_job(self, batch_id: str) -> "BatchJob":
        """Cancel an in-progress batch.

        Returns:
            Updated :class:`BatchJob`.
        """
        from .batch_tracker import cancel_batch

        if not self.client:
            raise TranslationError("API client not initialized")
        return cancel_batch(self.client, batch_id)

    def get_models(self) -> List[str]:
        """Fetch available models from the API."""
        if not self.client:
            return []
        try:
            models = self.client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            self.logger.error(f"Failed to fetch models: {e}")
            return []
