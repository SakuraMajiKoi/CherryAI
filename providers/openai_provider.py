"""OpenAI reference provider implementation.

This is the canonical provider.  Other providers that speak the
OpenAI-compatible format can inherit from ``OpenAICompatProvider``
and override only what differs.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from . import (
    BatchConfig,
    CachedInputConfig,
    ProviderBase,
    ProviderConnectionError,
    ProviderError,
    ProviderRegistry,
    ProviderResponse,
    ProviderTimeoutError,
    TemperatureConfig,
    ThinkingConfig,
    TokenUsage,
    validate_provider,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model pattern constants (mirrored from api_client.py for provider isolation)
# ---------------------------------------------------------------------------

# Reasoning models have built-in thinking — no extra params needed.
_OPENAI_REASONING_PREFIXES = ("o1", "o3", "o4")

# GPT-5 family has configurable reasoning.effort but does NOT accept
# the ``temperature`` parameter.
_GPT5_PREFIXES = ("gpt-5",)

# GPT-4.1 family supports optional reasoning.effort (on/off).
_GPT41_PREFIXES = ("gpt-4.1",)

# Models supporting automatic OpenAI prompt caching.
_PROMPT_CACHE_PREFIXES = ("gpt-4o", "gpt-4.1", "gpt-5", "o1", "o3", "chatgpt-4o")

# Models supporting extended 24h cache retention.
_EXTENDED_CACHE_PREFIXES = ("gpt-4.1", "gpt-5")


def _is_reasoning_model(model_id: str) -> bool:
    """Check whether *model_id* is an OpenAI reasoning model (o-series)."""
    ml = model_id.lower()
    return any(ml.startswith(p) for p in _OPENAI_REASONING_PREFIXES)


def _is_gpt5_family(model_id: str) -> bool:
    """Check whether *model_id* belongs to the GPT-5 family."""
    return model_id.lower().startswith("gpt-5")


def _is_gpt41_family(model_id: str) -> bool:
    """Check whether *model_id* belongs to the GPT-4.1 family."""
    return model_id.lower().startswith("gpt-4.1")


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------

class OpenAIProvider(ProviderBase):
    """Reference implementation for the OpenAI API.

    Delegates to the existing ``model_registry`` for pricing / model data
    and uses the ``openai`` SDK for requests.
    """

    name = "openai"
    display_name = "OpenAI"
    requires_api_key = True
    base_url = "https://api.openai.com/v1"

    # ---- MP5: send_request ----

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
        """Send a chat completion request via the OpenAI SDK."""
        try:
            import importlib
            openai_mod = importlib.import_module("openai")
            OpenAI = openai_mod.OpenAI  # type: ignore[attr-defined]
        except Exception as exc:
            raise ProviderError(
                f"openai package not available: {exc}", is_fatal=True,
            ) from exc

        effective_key = api_key or "sk-placeholder"
        base = kwargs.pop("base_url", None) or self.base_url

        client = OpenAI(
            api_key=effective_key,
            base_url=base,
            timeout=timeout,
            max_retries=0,
        )

        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # Temperature: GPT-5 family and o-series reasoning models do not
        # accept a temperature parameter.
        temp_cfg = self.get_temperature_config(model)
        if temp_cfg.supported and temperature is not None:
            params["temperature"] = temperature

        if response_format is not None:
            params["response_format"] = response_format

        # Merge any extra kwargs (e.g. extra_body, max_tokens, logit_bias)
        params.update(kwargs)

        try:
            from typing import cast
            response = cast(Any, client).chat.completions.create(**params)
        except Exception as exc:
            self._raise_provider_error(exc)

        return self.parse_response(response)

    # ---- MP6: parse_response ----

    def parse_response(self, raw_response: Any) -> ProviderResponse:
        """Extract content, usage, and finish_reason from an OpenAI response."""
        content = ""
        if raw_response.choices:
            content = raw_response.choices[0].message.content or ""

        finish_reason = "stop"
        if raw_response.choices:
            finish_reason = raw_response.choices[0].finish_reason or "stop"

        usage = TokenUsage()
        if raw_response.usage:
            u = raw_response.usage
            usage.prompt_tokens = getattr(u, "prompt_tokens", 0) or 0
            usage.completion_tokens = getattr(u, "completion_tokens", 0) or 0
            usage.total_tokens = getattr(u, "total_tokens", 0) or 0

            ptd = getattr(u, "prompt_tokens_details", None)
            if ptd is not None:
                usage.cached_tokens = getattr(ptd, "cached_tokens", 0) or 0

            ctd = getattr(u, "completion_tokens_details", None)
            if ctd is not None:
                usage.reasoning_tokens = (
                    getattr(ctd, "reasoning_tokens", 0) or 0
                )
                usage.accepted_prediction_tokens = (
                    getattr(ctd, "accepted_prediction_tokens", 0) or 0
                )
                usage.rejected_prediction_tokens = (
                    getattr(ctd, "rejected_prediction_tokens", 0) or 0
                )

        return ProviderResponse(
            content=content,
            usage=usage,
            finish_reason=finish_reason,
            raw=raw_response,
        )

    # ---- MP2 / MP3: pricing ----

    def get_input_price(self, model_id: str) -> float:
        """USD per 1M input tokens.  Delegates to model_registry."""
        info = self._get_model_info(model_id)
        if info and info.input_price is not None:
            return info.input_price
        return 0.0

    def get_output_price(self, model_id: str) -> float:
        """USD per 1M output tokens.  Delegates to model_registry."""
        info = self._get_model_info(model_id)
        if info and info.output_price is not None:
            return info.output_price
        return 0.0

    # ---- MM1: structured output ----

    def supports_structured_output(self, model_id: str) -> bool:
        """All modern OpenAI models support JSON structured output."""
        info = self._get_model_info(model_id)
        if info:
            return info.structured_output
        # Default: True for all gpt-4+, o-series, gpt-5 models
        ml = model_id.lower()
        return any(ml.startswith(p) for p in (
            "gpt-4", "gpt-5", "o1", "o3", "o4", "chatgpt",
        ))

    # ---- MM2: model name ----

    def get_model_name(self, model_id: str) -> str:
        info = self._get_model_info(model_id)
        if info:
            return info.display_name
        return model_id

    # ---- MM3: thinking config ----

    def get_thinking_config(self, model_id: str) -> ThinkingConfig:
        """Return thinking/reasoning mode config for an OpenAI model.

        - o-series: builtin reasoning (always on, no params).
        - GPT-5: mandatory reasoning with configurable effort.
        - GPT-4.1: optional reasoning (on/off, effort configurable).
        - Others: thinking unavailable.
        """
        ml = model_id.lower()
        if _is_reasoning_model(ml):
            return ThinkingConfig(available=True, mode="builtin", mandatory=True)
        if _is_gpt5_family(ml):
            return ThinkingConfig(
                available=True,
                mode="mandatory",
                mandatory=True,
                effort_levels=("low", "medium", "high"),
                effort_default="medium",
            )
        if _is_gpt41_family(ml):
            return ThinkingConfig(
                available=True,
                mode="optional",
                mandatory=False,
                effort_levels=("low", "medium", "high"),
                effort_default="medium",
            )
        return ThinkingConfig(available=False)

    # ---- OP1: prompt caching ----

    def get_cached_input_config(self, model_id: str) -> Optional[CachedInputConfig]:
        ml = model_id.lower()
        if not any(ml.startswith(p) for p in _PROMPT_CACHE_PREFIXES):
            return None
        if any(ml.startswith(p) for p in _EXTENDED_CACHE_PREFIXES):
            return CachedInputConfig.openai_extended()
        return CachedInputConfig.openai_default()

    # ---- OP2: batch config ----

    def get_batch_config(self, model_id: str) -> Optional[BatchConfig]:
        info = self._get_model_info(model_id)
        if info and info.batch_mode:
            return BatchConfig(
                batch_available=True,
                batch_input_price_ratio=0.5,
                batch_output_price_ratio=0.5,
                flex_available=info.flex_input_price is not None,
                flex_input_price_ratio=(
                    (info.flex_input_price / info.input_price)
                    if info.flex_input_price and info.input_price
                    else 0.0
                ),
                flex_output_price_ratio=(
                    (info.flex_output_price / info.output_price)
                    if info.flex_output_price and info.output_price
                    else 0.0
                ),
            )
        return None

    # ---- OP3: fetch models ----

    def fetch_models(self, api_key: str) -> List[Any]:
        """Delegate to model_registry.fetch_openai_models."""
        try:
            from functions.model_registry import fetch_openai_models
            return fetch_openai_models(api_key)
        except Exception as exc:
            logger.warning("fetch_models failed: %s", exc)
            return []

    # ---- OP4: rate limit probing ----

    def probe_rate_limits(
        self, api_key: str, model_id: str,
    ) -> Optional[Dict[str, int]]:
        """Delegate to model_registry.probe_openai_rate_limits."""
        try:
            from functions.model_registry import probe_openai_rate_limits
            return probe_openai_rate_limits(api_key, model_id)
        except Exception as exc:
            logger.warning("probe_rate_limits failed: %s", exc)
            return None

    # ---- OP5: error classification ----

    def classify_error(self, error: Exception) -> Optional[Any]:
        """Delegate to common_errors.classify_api_error."""
        try:
            from functions.common_errors import classify_api_error
            return classify_api_error(error)
        except Exception:
            return None

    # ---- OM1: temperature ----

    def get_temperature_config(self, model_id: str) -> TemperatureConfig:
        ml = model_id.lower()
        # GPT-5 family does not support temperature
        if _is_gpt5_family(ml):
            return TemperatureConfig(supported=False)
        # O-series reasoning models have restricted temperature
        if _is_reasoning_model(ml):
            return TemperatureConfig(supported=False)
        # All other OpenAI models: standard 0-2 range
        info = self._get_model_info(model_id)
        if info:
            return TemperatureConfig(
                supported=True,
                min_value=info.temperature_min,
                max_value=info.temperature_max,
            )
        return TemperatureConfig(supported=True)

    # ---- OM2: context window ----

    def get_context_window(self, model_id: str) -> int:
        info = self._get_model_info(model_id)
        if info and info.context_window:
            return info.context_window
        return 128000

    # ---- Helpers ----

    def _get_model_info(self, model_id: str) -> Optional[Any]:
        """Look up ModelInfo from the model registry."""
        try:
            from functions.model_registry import get_model_info
            return get_model_info(model_id)
        except Exception:
            return None

    def _raise_provider_error(self, exc: Exception) -> None:
        """Convert an OpenAI SDK exception to a ProviderError."""
        from . import (
            AuthenticationError as AuthErr,
            ModelNotFoundError,
            RateLimitedError,
            QuotaExceededError,
            ContentFilteredError,
        )

        err_type = type(exc).__name__
        raw = str(exc)
        raw_lower = raw.lower()

        if err_type == "AuthenticationError" or "401" in raw:
            raise AuthErr(raw) from exc
        if err_type == "NotFoundError" or "404" in raw:
            raise ModelNotFoundError(raw) from exc
        if err_type == "RateLimitError" or "429" in raw:
            if "quota" in raw_lower or "billing" in raw_lower:
                raise QuotaExceededError(raw) from exc
            raise RateLimitedError(raw) from exc
        if err_type == "APITimeoutError" or "timeout" in raw_lower:
            raise ProviderTimeoutError(raw) from exc
        if err_type == "APIConnectionError" or "connection" in raw_lower:
            raise ProviderConnectionError(raw) from exc
        if ("content" in raw_lower and "policy" in raw_lower) or "flagged" in raw_lower:
            raise ContentFilteredError(raw) from exc

        raise ProviderError(raw, is_fatal=False) from exc


# ---------------------------------------------------------------------------
# OpenAI-Compatible Base
# ---------------------------------------------------------------------------

class OpenAICompatProvider(OpenAIProvider):
    """Base for providers using the OpenAI-compatible ``/v1/chat/completions``.

    Inherits ``send_request()`` and ``parse_response()`` unchanged.
    Subclasses override ``name``, ``display_name``, ``base_url``, pricing
    lookups, and model fetching.
    """

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
        """Same as OpenAI but with this provider's base_url."""
        kwargs.setdefault("base_url", self.base_url)
        return super().send_request(
            messages, model, temperature, response_format,
            api_key=api_key, timeout=timeout, **kwargs,
        )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

ProviderRegistry.register(OpenAIProvider())
