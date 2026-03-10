"""Anthropic (Claude) provider via OpenAI-compatible endpoint."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import (
    ProviderRegistry,
    ProviderResponse,
    TemperatureConfig,
    ThinkingConfig,
    TokenUsage,
)
from .openai_provider import OpenAICompatProvider

logger = logging.getLogger(__name__)

# Claude models with explicit thinking support
_CLAUDE_THINKING_MODELS = (
    "claude-sonnet-4",
    "claude-opus-4",
    "claude-haiku-4",
    "claude-3-7-sonnet",
    "claude-sonnet-4-5",
    "claude-opus-4-5",
    "claude-opus-4-1",
    "claude-haiku-4-5",
)

# Default pricing for Claude (per 1M tokens) when not in model_registry
_CLAUDE_DEFAULT_INPUT_PRICE = 1.0
_CLAUDE_DEFAULT_OUTPUT_PRICE = 2.0


def _is_claude_thinking_model(model_id: str) -> bool:
    """Check whether *model_id* is a Claude model that supports thinking."""
    ml = model_id.lower()
    return any(ml.startswith(p) for p in _CLAUDE_THINKING_MODELS)


class AnthropicProvider(OpenAICompatProvider):
    """Anthropic Claude via the OpenAI-compatible proxy."""

    name = "anthropic"
    display_name = "Anthropic Claude"
    requires_api_key = True
    base_url = "https://api.anthropic.com/v1"

    # ---- send_request: inject thinking via extra_body ----

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
        """Send request with Claude thinking support.

        When thinking is enabled for a Claude model, injects ``extra_body``
        with thinking params and inflates ``max_tokens`` to accommodate the
        thinking budget.
        """
        thinking_enabled = kwargs.pop("thinking_enabled", False)
        thinking_budget = kwargs.pop("thinking_budget", 10000)

        if thinking_enabled and _is_claude_thinking_model(model):
            extra = kwargs.get("extra_body", {})
            extra["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
            kwargs["extra_body"] = extra

            # Inflate max_tokens to accommodate thinking budget + output
            current_max = kwargs.get("max_tokens", 4096)
            kwargs["max_tokens"] = max(current_max, thinking_budget + 4096)

        return super().send_request(
            messages, model, temperature, response_format,
            api_key=api_key, timeout=timeout, **kwargs,
        )

    # ---- Pricing ----

    def get_input_price(self, model_id: str) -> float:
        info = self._get_model_info(model_id)
        if info and info.input_price is not None:
            return info.input_price
        return _CLAUDE_DEFAULT_INPUT_PRICE

    def get_output_price(self, model_id: str) -> float:
        info = self._get_model_info(model_id)
        if info and info.output_price is not None:
            return info.output_price
        return _CLAUDE_DEFAULT_OUTPUT_PRICE

    # ---- Structured output: via json_object ----

    def supports_structured_output(self, model_id: str) -> bool:
        return True

    # ---- Thinking config: explicit mode for Claude ----

    def get_thinking_config(self, model_id: str) -> ThinkingConfig:
        if _is_claude_thinking_model(model_id):
            return ThinkingConfig(
                available=True,
                mode="explicit",
                budget_default=10000,
            )
        return ThinkingConfig(available=False)

    # ---- Temperature: 0-1 for Claude ----

    def get_temperature_config(self, model_id: str) -> TemperatureConfig:
        return TemperatureConfig(supported=True, min_value=0.0, max_value=1.0)

    # ---- No prompt caching for Claude ----

    def get_cached_input_config(self, model_id: str) -> None:
        return None

    # ---- Model fetching: no API for listing ----

    def fetch_models(self, api_key: str) -> List[Any]:
        """Claude has no /v1/models endpoint; return empty."""
        return []

    # ---- No rate limit probing ----

    def probe_rate_limits(
        self, api_key: str, model_id: str,
    ) -> Optional[Dict[str, int]]:
        return None


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

ProviderRegistry.register(AnthropicProvider())
