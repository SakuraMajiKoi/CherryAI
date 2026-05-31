"""Local LLM provider implementations (LM Studio, Ollama, generic local).

Local providers use the OpenAI-compatible API format with ``json_schema``
response format instead of ``json_object``.  They require no API key and
all pricing is $0.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import (
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
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Translation JSON schema used by all local providers
# ---------------------------------------------------------------------------

_LOCAL_RESPONSE_FORMAT: Dict[str, Any] = {
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


class LocalProvider(ProviderBase):
    """Generic local LLM provider (OpenAI-compatible on localhost)."""

    name = "local"
    display_name = "Local/Custom"
    requires_api_key = False
    base_url = "http://localhost:1234/v1"

    # ---- send_request ----

    def send_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float],
        response_format: Optional[Dict[str, Any]],
        *,
        api_key: str = "",
        timeout: int = 120,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send request to local LLM server via OpenAI SDK."""
        try:
            import importlib
            openai_mod = importlib.import_module("openai")
            OpenAI = openai_mod.OpenAI  # type: ignore[attr-defined]
        except Exception as exc:
            raise ProviderError(
                f"openai package not available: {exc}", is_fatal=True,
            ) from exc

        # Local providers use a placeholder API key
        effective_key = api_key or "lm-studio"
        base = kwargs.pop("base_url", None) or self.base_url

        client = OpenAI(
            api_key=effective_key,
            base_url=base,
            timeout=timeout,
            max_retries=0,
        )

        # Prefer the caller's schema.  Translation supplies the default
        # translation array schema; utility/editor requests may require a
        # different strict shape or plain text.
        fmt = response_format or _LOCAL_RESPONSE_FORMAT

        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if fmt is not None:
            params["response_format"] = fmt

        if temperature is not None:
            params["temperature"] = temperature

        params.update(kwargs)

        try:
            from typing import cast
            response = cast(Any, client).chat.completions.create(**params)
        except Exception as exc:
            self._raise_provider_error(exc)

        return self.parse_response(response)

    # ---- parse_response ----

    def parse_response(self, raw_response: Any) -> ProviderResponse:
        """Extract content and basic usage from local LLM response."""
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

        return ProviderResponse(
            content=content,
            usage=usage,
            finish_reason=finish_reason,
            raw=raw_response,
        )

    # ---- Pricing: always free ----

    def get_input_price(self, model_id: str) -> float:
        return 0.0

    def get_output_price(self, model_id: str) -> float:
        return 0.0

    # ---- Structured output: supported via json_schema ----

    def supports_structured_output(self, model_id: str) -> bool:
        return True

    # ---- Model name ----

    def get_model_name(self, model_id: str) -> str:
        return model_id

    # ---- Thinking: not available for local ----

    def get_thinking_config(self, model_id: str) -> ThinkingConfig:
        return ThinkingConfig(available=False)

    # ---- Response format override: json_schema ----

    def get_response_format(self, model_id: str) -> Dict[str, Any]:
        """Local providers always use the full json_schema format."""
        return dict(_LOCAL_RESPONSE_FORMAT)

    # ---- Temperature: varies by backend, allow by default ----

    def get_temperature_config(self, model_id: str) -> TemperatureConfig:
        return TemperatureConfig(supported=True)

    # ---- No caching support ----

    def get_cached_input_config(self, model_id: str) -> None:
        return None

    # ---- Fetch models from local /v1/models ----

    def fetch_models(self, api_key: str) -> List[Any]:
        """Query /v1/models on the local server."""
        try:
            import importlib
            openai_mod = importlib.import_module("openai")
            OpenAI = openai_mod.OpenAI  # type: ignore[attr-defined]
            client = OpenAI(
                api_key=api_key or "lm-studio",
                base_url=self.base_url,
                timeout=5,
                max_retries=0,
            )
            resp = client.models.list()
            return [m.id for m in resp.data] if resp.data else []
        except Exception as exc:
            logger.debug("fetch_models from %s failed: %s", self.base_url, exc)
            return []

    # ---- Error handling ----

    def _raise_provider_error(self, exc: Exception) -> None:
        """Convert exceptions to provider errors — mostly connection issues."""
        raw = str(exc)
        raw_lower = raw.lower()
        err_type = type(exc).__name__

        if err_type == "APIConnectionError" or "connection" in raw_lower:
            raise ProviderConnectionError(raw) from exc
        if err_type == "APITimeoutError" or "timeout" in raw_lower:
            raise ProviderTimeoutError(raw) from exc

        raise ProviderError(raw, is_fatal=False) from exc


# ---------------------------------------------------------------------------
# LM Studio subclass
# ---------------------------------------------------------------------------

class LMStudioProvider(LocalProvider):
    """LM Studio on localhost:1234."""

    name = "lmstudio"
    display_name = "LM Studio"
    base_url = "http://localhost:1234/v1"


# ---------------------------------------------------------------------------
# Ollama subclass
# ---------------------------------------------------------------------------

class OllamaProvider(LocalProvider):
    """Ollama on localhost:11434."""

    name = "ollama"
    display_name = "Ollama"
    base_url = "http://localhost:11434/v1"


class KoboldCPPProvider(LocalProvider):
    """KoboldCPP OpenAI-compatible endpoint."""

    name = "koboldcpp"
    display_name = "KoboldCPP"
    base_url = "http://localhost:5001/v1"


# ---------------------------------------------------------------------------
# Register all local providers
# ---------------------------------------------------------------------------

ProviderRegistry.register(LocalProvider())
ProviderRegistry.register(LMStudioProvider())
ProviderRegistry.register(OllamaProvider())
ProviderRegistry.register(KoboldCPPProvider())
