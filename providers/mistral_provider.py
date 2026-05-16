"""Mistral AI provider using OpenAI-compatible endpoint."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import (
    CachedInputConfig,
    ProviderRegistry,
    TemperatureConfig,
    ThinkingConfig,
)
from .openai_provider import OpenAICompatProvider

logger = logging.getLogger(__name__)


class MistralProvider(OpenAICompatProvider):
    """Mistral AI via the OpenAI-compatible API."""

    name = "mistral"
    display_name = "Mistral AI"
    requires_api_key = True
    base_url = "https://api.mistral.ai/v1"

    # ---- Pricing delegates to model_registry ----

    def get_input_price(self, model_id: str) -> float:
        info = self._get_model_info(model_id)
        if info and info.input_price is not None:
            return info.input_price
        return 0.0

    def get_output_price(self, model_id: str) -> float:
        info = self._get_model_info(model_id)
        if info and info.output_price is not None:
            return info.output_price
        return 0.0

    # ---- Prompt caching ----

    def get_cached_input_config(self, model_id: str) -> Optional[CachedInputConfig]:
        info = self._get_model_info(model_id)
        if info and not info.structured_output:
            return None
        return CachedInputConfig(
            supported=True,
            min_prefix_tokens=1024,
            retention="in_memory",
            cached_price_ratio=0.1,
        )

    # ---- Thinking: Mistral reasoning models advertise their mode in model_registry ----

    def get_thinking_config(self, model_id: str) -> ThinkingConfig:
        info = self._get_model_info(model_id)
        if info and info.thinking:
            mode = info.thinking_mode or "optional"
            if mode == "mandatory":
                return ThinkingConfig(
                    available=True,
                    mode="mandatory",
                    mandatory=True,
                    effort_levels=("none", "high"),
                    effort_default="high",
                )
            if mode == "explicit":
                return ThinkingConfig(
                    available=True,
                    mode="explicit",
                    budget_default=10000,
                )
            if mode == "builtin":
                return ThinkingConfig(
                    available=True,
                    mode="builtin",
                    mandatory=True,
                )
            return ThinkingConfig(
                available=True,
                mode="optional",
                mandatory=False,
                effort_levels=("none", "high"),
                effort_default="high",
            )
        return ThinkingConfig(available=False)

    # ---- Temperature: 0-1 for Mistral ----

    def get_temperature_config(self, model_id: str) -> TemperatureConfig:
        info = self._get_model_info(model_id)
        if info:
            return TemperatureConfig(
                supported=True,
                min_value=info.temperature_min,
                max_value=info.temperature_max,
            )
        return TemperatureConfig(supported=True, max_value=1.0)

    # ---- Model fetching ----

    def fetch_models(self, api_key: str) -> List[Any]:
        """Delegate to model_registry.fetch_mistral_models."""
        try:
            from functions.model_registry import fetch_mistral_models
            return fetch_mistral_models(api_key)
        except Exception as exc:
            logger.warning("fetch_models failed: %s", exc)
            return []

    # ---- No rate limit probing for Mistral ----

    def probe_rate_limits(
        self, api_key: str, model_id: str,
    ) -> Optional[Dict[str, int]]:
        return None


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

ProviderRegistry.register(MistralProvider())
