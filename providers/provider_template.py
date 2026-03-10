"""Provider Template — Skeleton for adding a new LLM provider.

How to use
----------
1. Copy this file → ``providers/my_provider.py``
2. Rename ``TemplateProvider`` and fill in every ``# TODO`` section.
3. Register at the bottom of the file with ``ProviderRegistry.register(...)``.
4. Add a lazy import in ``providers/__init__.py``'s ``_load_providers()``.
5. Run ``validate_provider(MyProvider())`` to confirm compliance.

For OpenAI-compatible APIs
--------------------------
If the remote API speaks the OpenAI chat-completions format, inherit
``OpenAICompatProvider`` from ``openai_provider.py`` instead of
``ProviderBase``.  Override only the base URL, pricing, and any
provider-specific quirks.  See ``google_provider.py`` or
``mistral_provider.py`` for examples.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import (
    ProviderBase,
    ProviderRegistry,
    ProviderResponse,
    TemperatureConfig,
    ThinkingConfig,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class TemplateProvider(ProviderBase):
    """Skeleton provider — replace every ``# TODO`` before use."""

    # --- Provider-level attributes (MP1–MP4) ---
    name = "template"                       # TODO: unique slug (lowercase)
    display_name = "Template Provider"      # TODO: human-readable name
    base_url = "https://api.example.com/v1" # TODO: API base URL
    requires_api_key = True                 # TODO: False for local providers

    # =================================================================
    # Mandatory provider-level methods (MP5, MP6)
    # =================================================================

    def send_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response_format: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send a chat-completion request and return the result.

        TODO: Implement using the provider's SDK or HTTP client.
        """
        raise NotImplementedError("Implement send_request")

    def parse_response(self, raw_response: Any) -> ProviderResponse:
        """Parse a raw SDK response into a ProviderResponse.

        TODO: Extract content, token usage, and finish reason.
        """
        raise NotImplementedError("Implement parse_response")

    # =================================================================
    # Mandatory pricing methods (MP2, MP3)
    # =================================================================

    def get_input_price(self, model_id: str) -> float:
        """USD per 1 M input tokens.

        TODO: Return model-specific pricing or ``0.0`` for free tiers.
        """
        return 0.0

    def get_output_price(self, model_id: str) -> float:
        """USD per 1 M output tokens.

        TODO: Return model-specific pricing or ``0.0`` for free tiers.
        """
        return 0.0

    # =================================================================
    # Mandatory model-level methods (MM1, MM2, MM3)
    # =================================================================

    def supports_structured_output(self, model_id: str) -> bool:
        """Can this model return structured JSON?

        TODO: Return True if the model supports ``response_format``
        with ``json_object`` or ``json_schema``.
        """
        return True

    def get_model_name(self, model_id: str) -> str:
        """Human-readable model name.

        TODO: Look up a display name or return the raw model_id.
        """
        return model_id

    def get_thinking_config(self, model_id: str) -> ThinkingConfig:
        """Thinking / reasoning support.

        TODO: Return ``ThinkingConfig(available=True, mode="explicit")``
        for models that support extended thinking, or the default
        ``ThinkingConfig()`` (available=False) otherwise.
        """
        return ThinkingConfig()

    # =================================================================
    # Optional overrides — uncomment and customise as needed
    # =================================================================

    # def get_temperature_config(self, model_id: str) -> TemperatureConfig:
    #     """Override temperature range — e.g. Mistral max 1.0."""
    #     return TemperatureConfig(supported=True, max_value=1.0)

    # def get_context_window(self, model_id: str) -> int:
    #     return 128_000

    # def get_response_format(self, model_id: str) -> Dict[str, Any]:
    #     """Override for providers that need json_schema instead of json_object."""
    #     return {"type": "json_object"}

    # def classify_error(self, error: Exception) -> Optional[Any]:
    #     """Map SDK exceptions to ProviderError subtypes."""
    #     return None

    # def fetch_models(self, api_key: str) -> List[Any]:
    #     """Live-fetch available models from the provider API."""
    #     return []


# ---------------------------------------------------------------------------
# Registration — instantiate and register with the global registry.
# Uncomment the line below after implementation is complete.
# ---------------------------------------------------------------------------

# ProviderRegistry.register(TemplateProvider())
