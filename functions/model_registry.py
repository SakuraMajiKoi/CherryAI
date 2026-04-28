"""Model Registry for CherryAI.

Fetches, stores, and retrieves up-to-date model information for supported
cloud providers: OpenAI, Google Gemini, and Mistral.

Data is persisted to ``user/API.ini`` under provider-specific sections so the
app can work offline (using the last-fetched or built-in fallback data).

Architecture
------------
- ``ModelInfo``          - dataclass for a single model's metadata & pricing
- ``FALLBACK_MODELS``    - curated fallback data (accurate as of Feb 2026)
- ``fetch_models()``     - fetch fresh data from provider APIs / pricing pages
- ``save_to_ini()``      - persist model data to API.ini
- ``load_from_ini()``    - load model data from API.ini
- ``get_model_pricing()``- return MODEL_PRICING-compatible dict
- ``get_provider_models()`` - return list of model IDs for a provider
- ``get_all_models()``   - return all ModelInfo objects (loaded or fetched)
- ``refresh_models()``   - high-level: fetch + save + return

INI Structure (added to existing user/API.ini)
-----------------------------------------------
[model_registry]
version = 1
last_refreshed =             ; ISO-8601 timestamp of last successful refresh

[model_registry_openai]
last_updated = <ISO>
data = <JSON dict of model_id → ModelInfo dict>

[model_registry_google]
last_updated = <ISO>
data = <JSON dict …>

[model_registry_mistral]
last_updated = <ISO>
data = <JSON dict …>
"""

from __future__ import annotations

import configparser
import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGISTRY_VERSION = 1
DEFAULT_REFRESH_HOURS = 24       # cache is considered stale after 24 hours
DEFAULT_COST_CAP = 25.0

# Provider IDs - canonical names used throughout the module
PROVIDER_OPENAI = "openai"
PROVIDER_GOOGLE = "google"
PROVIDER_MISTRAL = "mistral"

ALL_PROVIDERS = [PROVIDER_OPENAI, PROVIDER_GOOGLE, PROVIDER_MISTRAL]

# Provider base URLs
OPENAI_BASE_URL = "https://api.openai.com/v1"
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"

# Public pricing page URLs (no auth required)
OPENAI_PRICING_URL = "https://developers.openai.com/api/docs/pricing"
GOOGLE_PRICING_URL = "https://ai.google.dev/pricing"

# Provider API endpoints for model lists
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
GOOGLE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MISTRAL_MODELS_URL = "https://api.mistral.ai/v1/models"

_HTTP_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# ModelInfo dataclass
# ---------------------------------------------------------------------------

@dataclass
class ModelInfo:
    """Complete metadata for a single LLM model.

    Pricing fields are in USD per 1,000,000 tokens (same unit as provider
    pricing pages).  ``None`` means the feature/tier is unavailable.
    """

    # Identity
    model_id: str                        # canonical API name, e.g. "gpt-4o"
    display_name: str                    # human-readable, e.g. "GPT-4o"
    provider: str                        # "openai" | "google" | "mistral"
    url: str                             # API base URL for this provider

    # Pricing (USD / 1M tokens, None = not available / free)
    input_price: Optional[float] = None          # standard input
    cached_input_price: Optional[float] = None   # cached / context-cache input
    output_price: Optional[float] = None         # standard output
    batch_input_price: Optional[float] = None    # batch mode input
    batch_output_price: Optional[float] = None   # batch mode output
    flex_input_price: Optional[float] = None     # flex processing input
    flex_output_price: Optional[float] = None    # flex processing output
    priority_input_price: Optional[float] = None   # priority processing input
    priority_output_price: Optional[float] = None  # priority processing output

    # Rate limits
    rpm_free: Optional[int] = None       # requests per minute (free tier)
    rpm_tier1: Optional[int] = None      # requests per minute (paid tier 1)
    rpd_free: Optional[int] = None       # requests per day (free tier)
    rpd_tier1: Optional[int] = None      # requests per day (paid tier 1)
    tpm_free: Optional[int] = None       # input tokens per minute (free tier)
    tpm_tier1: Optional[int] = None      # input tokens per minute (paid tier 1)
    max_concurrent: Optional[int] = None   # app-internal parallel slots (not API-imposed)

    # Capabilities
    structured_output: bool = False      # supports JSON schema / structured output
    batch_mode: bool = False             # asynchronous batch API available
    thinking: bool = False               # extended thinking / reasoning mode
    thinking_mode: str = ""              # "optional"|"mandatory"|"builtin"|""
    logit_bias: bool = False             # supports logit_bias parameter
    temperature_min: float = 0.0
    temperature_max: float = 2.0
    context_window: Optional[int] = None # max context window in tokens

    # Misc
    token_speed: int = 100               # rough estimate of output tokens/sec
    notes: str = ""                      # free-form notes

    # Source tracking
    fetched_at: str = ""                 # ISO timestamp when this was fetched

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return asdict(self)

    def _derived_concurrent(self) -> int:
        """Derive a concurrent request limit from RPM when max_concurrent is unset.

        Uses whichever RPM field is available (tier1 preferred, then free).
        Formula: ``min(rpm / 30, 50)`` — assumes ~2s per request on average,
        capped at 50 to be conservative.  Returns 5 if no RPM data.
        """
        rpm = self.rpm_tier1 or self.rpm_free
        if rpm and rpm > 0:
            return max(1, min(rpm // 30, 50))
        return 5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        """Deserialize from a dict, ignoring unknown keys."""
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def to_pricing_entry(self) -> Dict[str, Any]:
        """Return a ``MODEL_PRICING``-compatible dict entry.

        The legacy format used by ``functions/config.py``:
        ``{"name": …, "input": …, "output": …, "concurrent": …, "token_speed": …}``
        """
        return {
            "name": self.display_name,
            "input": self.input_price or 0.0,
            "cached_input": self.cached_input_price,
            "output": self.output_price or 0.0,
            "batch_input": self.batch_input_price,
            "batch_output": self.batch_output_price,
            "flex_input": self.flex_input_price,
            "flex_output": self.flex_output_price,
            "priority_input": self.priority_input_price,
            "priority_output": self.priority_output_price,
            "batch_mode": self.batch_mode,
            "concurrent": self.max_concurrent or self._derived_concurrent(),
            "token_speed": self.token_speed,
            "rpm_free": self.rpm_free,
            "rpm_tier1": self.rpm_tier1,
            "rpd_free": self.rpd_free,
            "structured_output": self.structured_output,
            "thinking": self.thinking,
            "thinking_mode": self.thinking_mode,
            "logit_bias": self.logit_bias,
            "temperature_min": self.temperature_min,
            "temperature_max": self.temperature_max,
            "context_window": self.context_window,
            "provider": self.provider,
            "url": self.url,
        }


@dataclass(frozen=True)
class ModelCostStatus:
    """Resolved cost-cap state for a model.

    ``output_price`` is the governing price for request and probe eligibility.
    ``price_known`` distinguishes an actual free model (``0.0``) from an
    unknown price (``None``).
    """

    model_id: str
    output_price: Optional[float]
    cost_cap: Optional[float]
    price_known: bool
    above_cost_cap: bool
    blocked: bool
    block_reason: str = ""


def _pricing_unknown_updates() -> Dict[str, Optional[float]]:
    """Return field updates that mark all pricing data as unknown."""
    return {
        "input_price": None,
        "cached_input_price": None,
        "output_price": None,
        "batch_input_price": None,
        "batch_output_price": None,
        "flex_input_price": None,
        "flex_output_price": None,
        "priority_input_price": None,
        "priority_output_price": None,
    }


def with_unknown_pricing(model: ModelInfo, *, fetched_at: Optional[str] = None) -> ModelInfo:
    """Return a copy of *model* with all pricing fields cleared.

    This is used during refresh when model discovery succeeds but pricing
    documentation cannot be confirmed. Clearing the values prevents CherryAI
    from treating stale fallback prices as current documented prices.
    """
    updates: Dict[str, Any] = _pricing_unknown_updates()
    if fetched_at is not None:
        updates["fetched_at"] = fetched_at
    return ModelInfo(**{**model.to_dict(), **updates})


def is_price_known(price: Optional[float]) -> bool:
    """Return True when *price* is documented.

    ``0.0`` is considered known and represents a free tier, while ``None``
    means the price is unknown or unavailable.
    """
    return price is not None


def get_model_cost_status(model: ModelInfo, cost_cap: Optional[float] = None) -> ModelCostStatus:
    """Resolve whether *model* is blocked by unknown pricing or the cost cap.

    Args:
        model: Model metadata to evaluate.
        cost_cap: Maximum allowed output price in USD / 1M tokens. ``None``
            disables the cap check while still blocking unknown prices.

    Returns:
        A :class:`ModelCostStatus` describing the model's price state.
    """
    output_price = model.output_price
    price_known = is_price_known(output_price)
    above_cost_cap = False
    blocked = False
    block_reason = ""

    if not price_known:
        blocked = True
        block_reason = "unknown_price"
    elif cost_cap is not None and output_price is not None and output_price > cost_cap:
        above_cost_cap = True
        blocked = True
        block_reason = "above_cost_cap"

    return ModelCostStatus(
        model_id=model.model_id,
        output_price=output_price,
        cost_cap=cost_cap,
        price_known=price_known,
        above_cost_cap=above_cost_cap,
        blocked=blocked,
        block_reason=block_reason,
    )


def get_model_cost_status_by_id(
    model_id: str,
    cost_cap: Optional[float] = None,
    path: Optional[Path] = None,
) -> ModelCostStatus:
    """Resolve cost-cap state for the model identified by *model_id*.

    Missing registry entries are treated as having unknown pricing so callers
    fail closed instead of implicitly allowing undocumented models.
    """
    model = get_model_info(model_id, path=path)
    if model is None:
        return ModelCostStatus(
            model_id=model_id,
            output_price=None,
            cost_cap=cost_cap,
            price_known=False,
            above_cost_cap=False,
            blocked=True,
            block_reason="unknown_price",
        )
    return get_model_cost_status(model, cost_cap=cost_cap)


def is_model_allowed_for_requests(
    model_id: str,
    cost_cap: Optional[float] = None,
    path: Optional[Path] = None,
) -> bool:
    """Return True when the model is allowed under current price rules.

    Unknown models return ``False`` so request call sites can fail closed.
    """
    status = get_model_cost_status_by_id(model_id, cost_cap=cost_cap, path=path)
    return not status.blocked


def get_configured_cost_cap(default: float = DEFAULT_COST_CAP) -> float:
    """Return the persisted global cost cap from ``CherryAI.ini``.

    Falls back to ``default`` when the INI manager is unavailable or the value
    cannot be parsed.
    """
    try:
        from CherryAI.functions import ini_manager

        value = ini_manager.get_effective_default(
            "api",
            "cost_cap",
            default,
            float,
        )
        return float(value)
    except Exception:
        return default


def describe_model_cost_status(status: ModelCostStatus) -> str:
    """Return a user-facing explanation for a model cost status."""
    if not status.price_known:
        return (
            f"Requests for model '{status.model_id}' are blocked because its "
            "output price is unknown."
        )

    if status.above_cost_cap:
        output_price = status.output_price or 0.0
        cost_cap = status.cost_cap if status.cost_cap is not None else DEFAULT_COST_CAP
        return (
            f"Requests for model '{status.model_id}' are blocked because its "
            f"output price (${output_price:.2f}/1M) exceeds the cost cap "
            f"(${cost_cap:.2f}/1M)."
        )

    return (
        f"Model '{status.model_id}' is allowed at ${status.output_price or 0.0:.2f}/1M."
    )


# ---------------------------------------------------------------------------
# Fallback (built-in) model data — accurate as of February 2026
# ---------------------------------------------------------------------------

def _ts() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# Helper to create ModelInfo with fetched_at already set to the build-time value
def _mi(**kwargs: Any) -> ModelInfo:
    if "fetched_at" not in kwargs:
        kwargs["fetched_at"] = "2026-02-23T00:00:00+00:00"  # static fallback date
    return ModelInfo(**kwargs)


FALLBACK_MODELS: Dict[str, List[ModelInfo]] = {
    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    PROVIDER_OPENAI: [
        _mi(
            model_id="gpt-4.1",
            display_name="GPT-4.1",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=2.00,
            cached_input_price=0.50,
            output_price=8.00,
            batch_input_price=1.00,
            batch_output_price=4.00,
            batch_mode=True,
            rpm_free=500,
            rpm_tier1=10000,
            rpd_free=200,
            tpm_tier1=1_000_000,
            max_concurrent=5,
            structured_output=True,
            thinking=True,
            thinking_mode="optional",
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_047_576,
            token_speed=80,
        ),
        _mi(
            model_id="gpt-4.1-mini",
            display_name="GPT-4.1 Mini",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=0.40,
            cached_input_price=0.10,
            output_price=1.60,
            batch_input_price=0.20,
            batch_output_price=0.80,
            batch_mode=True,
            rpm_free=500,
            rpm_tier1=10000,
            rpd_free=200,
            tpm_tier1=1_000_000,
            max_concurrent=10,
            structured_output=True,
            thinking=True,
            thinking_mode="optional",
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_047_576,
            token_speed=120,
        ),
        _mi(
            model_id="gpt-4.1-nano",
            display_name="GPT-4.1 Nano",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=0.10,
            cached_input_price=0.025,
            output_price=0.40,
            batch_input_price=0.05,
            batch_output_price=0.20,
            batch_mode=True,
            rpm_free=500,
            rpm_tier1=30000,
            rpd_free=200,
            tpm_tier1=1_000_000,
            max_concurrent=10,
            structured_output=True,
            thinking=True,
            thinking_mode="optional",
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_047_576,
            token_speed=150,
        ),
        _mi(
            model_id="gpt-4o",
            display_name="GPT-4o",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=2.50,
            cached_input_price=1.25,
            output_price=10.00,
            batch_input_price=1.25,
            batch_output_price=5.00,
            flex_input_price=1.25,
            flex_output_price=5.00,
            priority_input_price=4.25,
            priority_output_price=17.00,
            batch_mode=True,
            rpm_free=500,
            rpm_tier1=10000,
            rpd_free=200,
            tpm_tier1=800_000,
            max_concurrent=5,
            structured_output=True,
            thinking=False,
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=128_000,
            token_speed=80,
        ),
        _mi(
            model_id="gpt-4o-mini",
            display_name="GPT-4o Mini",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=0.15,
            cached_input_price=0.075,
            output_price=0.60,
            batch_input_price=0.075,
            batch_output_price=0.30,
            flex_input_price=0.075,
            flex_output_price=0.30,
            priority_input_price=0.25,
            priority_output_price=1.00,
            batch_mode=True,
            rpm_free=500,
            rpm_tier1=30000,
            rpd_free=200,
            tpm_tier1=150_000_000,
            max_concurrent=10,
            structured_output=True,
            thinking=False,
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=128_000,
            token_speed=120,
        ),
        _mi(
            model_id="o4-mini",
            display_name="o4-mini (Reasoning)",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=1.10,
            cached_input_price=0.275,
            output_price=4.40,
            batch_input_price=0.55,
            batch_output_price=2.20,
            flex_input_price=0.55,
            flex_output_price=2.20,
            priority_input_price=2.00,
            priority_output_price=8.00,
            batch_mode=True,
            rpm_free=500,
            rpm_tier1=10000,
            rpd_free=200,
            tpm_tier1=1_000_000,
            max_concurrent=5,
            structured_output=True,
            thinking=True,
            thinking_mode="builtin",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=200_000,
            token_speed=60,
            notes="Reasoning model — thinking tokens billed as output",
        ),
        _mi(
            model_id="o3",
            display_name="o3 (Reasoning)",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=2.00,
            cached_input_price=0.50,
            output_price=8.00,
            batch_input_price=1.00,
            batch_output_price=4.00,
            flex_input_price=1.00,
            flex_output_price=4.00,
            priority_input_price=3.50,
            priority_output_price=14.00,
            batch_mode=True,
            rpm_free=500,
            rpm_tier1=10000,
            rpd_free=200,
            tpm_tier1=1_000_000,
            max_concurrent=3,
            structured_output=True,
            thinking=True,
            thinking_mode="builtin",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=200_000,
            token_speed=50,
            notes="Reasoning model — thinking tokens billed as output",
        ),
        _mi(
            model_id="gpt-5-mini",
            display_name="GPT-5 Mini",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=0.25,
            cached_input_price=0.025,
            output_price=2.00,
            batch_input_price=0.125,
            batch_output_price=1.00,
            flex_input_price=0.125,
            flex_output_price=1.00,
            priority_input_price=0.45,
            priority_output_price=3.60,
            batch_mode=True,
            rpm_free=500,
            rpm_tier1=30000,
            rpd_free=200,
            max_concurrent=10,
            structured_output=True,
            thinking=True,
            thinking_mode="mandatory",
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=400_000,
            token_speed=130,
        ),
        _mi(
            model_id="gpt-5",
            display_name="GPT-5",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=1.25,
            cached_input_price=0.125,
            output_price=10.00,
            batch_input_price=0.625,
            batch_output_price=5.00,
            flex_input_price=0.625,
            flex_output_price=5.00,
            priority_input_price=2.50,
            priority_output_price=20.00,
            batch_mode=True,
            rpm_free=None,
            rpm_tier1=500,
            rpd_free=None,
            tpm_tier1=500_000,
            max_concurrent=5,
            structured_output=True,
            thinking=True,
            thinking_mode="mandatory",
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=400_000,
            token_speed=70,
            notes="Reasoning model with configurable effort",
        ),
        _mi(
            model_id="gpt-5.1",
            display_name="GPT-5.1",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=1.25,
            cached_input_price=0.125,
            output_price=10.00,
            batch_input_price=0.625,
            batch_output_price=5.00,
            flex_input_price=0.625,
            flex_output_price=5.00,
            priority_input_price=2.50,
            priority_output_price=20.00,
            batch_mode=True,
            rpm_free=None,
            rpm_tier1=500,
            rpd_free=None,
            tpm_tier1=500_000,
            max_concurrent=5,
            structured_output=True,
            thinking=True,
            thinking_mode="mandatory",
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=400_000,
            token_speed=70,
            notes="Flagship model with configurable reasoning effort",
        ),
        _mi(
            model_id="gpt-5.2",
            display_name="GPT-5.2",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=1.75,
            cached_input_price=0.175,
            output_price=14.00,
            batch_input_price=0.875,
            batch_output_price=7.00,
            flex_input_price=0.875,
            flex_output_price=7.00,
            priority_input_price=3.50,
            priority_output_price=28.00,
            batch_mode=True,
            rpm_free=None,
            rpm_tier1=500,
            rpd_free=None,
            tpm_tier1=500_000,
            max_concurrent=5,
            structured_output=True,
            thinking=True,
            thinking_mode="mandatory",
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=400_000,
            token_speed=70,
            notes="Best model for coding and agentic tasks",
        ),
        _mi(
            model_id="gpt-5-nano",
            display_name="GPT-5 Nano",
            provider=PROVIDER_OPENAI,
            url=OPENAI_BASE_URL,
            input_price=0.05,
            cached_input_price=0.005,
            output_price=0.40,
            batch_input_price=0.025,
            batch_output_price=0.20,
            flex_input_price=0.025,
            flex_output_price=0.20,
            priority_input_price=None,
            priority_output_price=None,
            batch_mode=True,
            rpm_free=None,
            rpm_tier1=500,
            rpd_free=None,
            tpm_tier1=200_000,
            max_concurrent=10,
            structured_output=True,
            thinking=True,
            thinking_mode="mandatory",
            logit_bias=True,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=400_000,
            token_speed=180,
            notes="Fastest, most cost-efficient GPT-5 variant",
        ),
    ],

    # ------------------------------------------------------------------
    # Google Gemini
    # ------------------------------------------------------------------
    PROVIDER_GOOGLE: [
        _mi(
            model_id="gemini-3.1-pro-preview",
            display_name="Gemini 3.1 Pro Preview",
            provider=PROVIDER_GOOGLE,
            url=GOOGLE_BASE_URL,
            input_price=2.00,       # paid, <= 200k tokens
            cached_input_price=0.20,
            output_price=12.00,     # includes thinking tokens
            batch_input_price=2.00,
            batch_output_price=12.00,
            batch_mode=True,
            rpm_free=None,          # no free tier
            rpm_tier1=150,
            rpd_free=None,
            rpd_tier1=None,
            max_concurrent=3,
            structured_output=True,
            thinking=True,
            thinking_mode="explicit",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_048_576,
            token_speed=60,
            notes="Preview model; paid tier only",
        ),
        _mi(
            model_id="gemini-3-flash-preview",
            display_name="Gemini 3 Flash Preview",
            provider=PROVIDER_GOOGLE,
            url=GOOGLE_BASE_URL,
            input_price=0.50,       # paid tier (text/image/video)
            cached_input_price=0.05,
            output_price=3.00,
            batch_input_price=0.50,
            batch_output_price=3.00,
            batch_mode=True,
            rpm_free=15,
            rpm_tier1=4000,
            rpd_free=1000,
            rpd_tier1=None,
            max_concurrent=5,
            structured_output=True,
            thinking=True,
            thinking_mode="explicit",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_048_576,
            token_speed=200,
            notes="Free tier available",
        ),
        _mi(
            model_id="gemini-2.5-pro",
            display_name="Gemini 2.5 Pro",
            provider=PROVIDER_GOOGLE,
            url=GOOGLE_BASE_URL,
            input_price=1.25,       # <= 200k tokens
            cached_input_price=0.125,
            output_price=10.00,     # includes thinking tokens; <= 200k
            batch_input_price=1.25,
            batch_output_price=10.00,
            batch_mode=True,
            rpm_free=5,
            rpm_tier1=150,
            rpd_free=25,
            rpd_tier1=None,
            tpm_free=250_000,
            tpm_tier1=1_000_000,
            max_concurrent=3,
            structured_output=True,
            thinking=True,
            thinking_mode="explicit",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_048_576,
            token_speed=60,
            notes="Thinking tokens included in output price",
        ),
        _mi(
            model_id="gemini-2.5-flash",
            display_name="Gemini 2.5 Flash",
            provider=PROVIDER_GOOGLE,
            url=GOOGLE_BASE_URL,
            input_price=0.30,       # paid; text/image/video
            cached_input_price=0.03,
            output_price=2.50,      # includes thinking tokens
            batch_input_price=0.30,
            batch_output_price=2.50,
            batch_mode=True,
            rpm_free=15,
            rpm_tier1=4000,
            rpd_free=1000,
            rpd_tier1=None,
            tpm_free=250_000,
            tpm_tier1=4_000_000,
            max_concurrent=10,
            structured_output=True,
            thinking=True,
            thinking_mode="explicit",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_048_576,
            token_speed=150,
            notes="1M token context window; thinking budgets supported",
        ),
        _mi(
            model_id="gemini-2.5-flash-lite",
            display_name="Gemini 2.5 Flash-Lite",
            provider=PROVIDER_GOOGLE,
            url=GOOGLE_BASE_URL,
            input_price=0.10,
            cached_input_price=0.01,
            output_price=0.40,
            batch_input_price=0.10,
            batch_output_price=0.40,
            batch_mode=True,
            rpm_free=15,
            rpm_tier1=4000,
            rpd_free=500,
            max_concurrent=10,
            structured_output=True,
            thinking=True,
            thinking_mode="explicit",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_048_576,
            token_speed=200,
            notes="Smallest & most cost-effective Gemini 2.5 model",
        ),
        _mi(
            model_id="gemini-2.0-flash",
            display_name="Gemini 2.0 Flash",
            provider=PROVIDER_GOOGLE,
            url=GOOGLE_BASE_URL,
            input_price=0.10,       # text/image/video
            cached_input_price=0.025,
            output_price=0.40,
            batch_input_price=0.10,
            batch_output_price=0.40,
            batch_mode=True,
            rpm_free=15,
            rpm_tier1=2000,
            rpd_free=200,
            rpd_tier1=None,
            tpm_free=1_000_000,
            tpm_tier1=4_000_000,
            max_concurrent=10,
            structured_output=True,
            thinking=False,
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_048_576,
            token_speed=200,
            notes="1M token context window; built for agents",
        ),
        _mi(
            model_id="gemini-2.0-flash-lite",
            display_name="Gemini 2.0 Flash-Lite",
            provider=PROVIDER_GOOGLE,
            url=GOOGLE_BASE_URL,
            input_price=0.075,
            cached_input_price=None,
            output_price=0.30,
            batch_input_price=None,
            batch_output_price=None,
            batch_mode=False,
            rpm_free=30,
            rpm_tier1=4000,
            rpd_free=1500,
            tpm_free=1_000_000,
            tpm_tier1=4_000_000,
            max_concurrent=10,
            structured_output=True,
            thinking=False,
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=2.0,
            context_window=1_048_576,
            token_speed=200,
            notes="Smallest & most cost-effective Gemini 2.0; no context caching",
        ),
    ],

    # ------------------------------------------------------------------
    # Mistral
    # ------------------------------------------------------------------
    PROVIDER_MISTRAL: [
        _mi(
            model_id="mistral-large-latest",
            display_name="Mistral Large 3",
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
            input_price=2.00,
            cached_input_price=None,
            output_price=6.00,
            batch_input_price=None,
            batch_output_price=None,
            batch_mode=False,
            rpm_free=1,
            rpm_tier1=2000,
            rpd_free=None,
            tpm_free=500_000,
            max_concurrent=5,
            structured_output=True,
            thinking=False,
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=131_072,
            token_speed=80,
            notes="Mistral's flagship open-weight large model",
        ),
        _mi(
            model_id="mistral-medium-latest",
            display_name="Mistral Medium 3.1",
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
            input_price=0.40,
            cached_input_price=None,
            output_price=2.00,
            batch_mode=False,
            rpm_free=1,
            rpm_tier1=2000,
            tpm_free=500_000,
            max_concurrent=5,
            structured_output=True,
            thinking=False,
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=131_072,
            token_speed=100,
            notes="Multimodal frontier model released Aug 2025",
        ),
        _mi(
            model_id="mistral-small-latest",
            display_name="Mistral Small 3.2",
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
            input_price=0.10,
            cached_input_price=None,
            output_price=0.30,
            batch_mode=False,
            rpm_free=1,
            rpm_tier1=2000,
            tpm_free=500_000,
            max_concurrent=10,
            structured_output=True,
            thinking=False,
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=32_768,
            token_speed=150,
            notes="Updated small model released June 2025",
        ),
        _mi(
            model_id="magistral-medium-latest",
            display_name="Magistral Medium 1.2",
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
            input_price=2.00,
            cached_input_price=None,
            output_price=5.00,
            batch_mode=False,
            rpm_free=1,
            rpm_tier1=500,
            tpm_free=500_000,
            max_concurrent=3,
            structured_output=True,
            thinking=True,
            thinking_mode="explicit",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=131_072,
            token_speed=60,
            notes="Reasoning model with thinking budgets",
        ),
        _mi(
            model_id="magistral-small-latest",
            display_name="Magistral Small 1.2",
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
            input_price=0.50,
            cached_input_price=None,
            output_price=2.00,
            batch_mode=False,
            rpm_free=1,
            rpm_tier1=1000,
            tpm_free=500_000,
            max_concurrent=5,
            structured_output=True,
            thinking=True,
            thinking_mode="explicit",
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=131_072,
            token_speed=100,
            notes="Small reasoning model with thinking budgets",
        ),
        _mi(
            model_id="codestral-latest",
            display_name="Codestral",
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
            input_price=0.30,
            cached_input_price=None,
            output_price=0.90,
            batch_mode=False,
            rpm_free=1,
            rpm_tier1=2000,
            tpm_free=500_000,
            max_concurrent=5,
            structured_output=True,
            thinking=False,
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=262_144,
            token_speed=120,
            notes="Cutting-edge code completion model",
        ),
        _mi(
            model_id="ministral-8b-latest",
            display_name="Ministral 3 8B",
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
            input_price=0.10,
            cached_input_price=None,
            output_price=0.10,
            batch_mode=False,
            rpm_free=1,
            rpm_tier1=2000,
            tpm_free=500_000,
            max_concurrent=10,
            structured_output=True,
            thinking=False,
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=131_072,
            token_speed=150,
            notes="Powerful edge model with vision capabilities",
        ),
        _mi(
            model_id="ministral-3b-latest",
            display_name="Ministral 3 3B",
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
            input_price=0.04,
            cached_input_price=None,
            output_price=0.04,
            batch_mode=False,
            rpm_free=1,
            rpm_tier1=2000,
            tpm_free=500_000,
            max_concurrent=10,
            structured_output=True,
            thinking=False,
            logit_bias=False,
            temperature_min=0.0,
            temperature_max=1.0,
            context_window=131_072,
            token_speed=200,
            notes="Tiny and efficient edge model; best-in-class for size",
        ),
    ],
}


# ---------------------------------------------------------------------------
# INI helpers
# ---------------------------------------------------------------------------

def _get_api_ini_path() -> Path:
    """Return the canonical path to user/API.ini."""
    here = Path(__file__).resolve()
    root = here.parent.parent            # CherryAI root
    user_dir = root / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "API.ini"


def _load_ini(path: Optional[Path] = None) -> configparser.ConfigParser:
    """Load API.ini without disturbing existing sections."""
    cfg = configparser.ConfigParser()
    cfg.optionxform = str   # preserve case
    p = path or _get_api_ini_path()
    if p.exists():
        cfg.read(str(p), encoding="utf-8")
    return cfg


def _save_ini(cfg: configparser.ConfigParser, path: Optional[Path] = None) -> None:
    p = path or _get_api_ini_path()
    with open(str(p), "w", encoding="utf-8") as fh:
        cfg.write(fh)


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def save_to_ini(
    provider: str,
    models: List[ModelInfo],
    path: Optional[Path] = None,
) -> None:
    """Persist a provider's model list to API.ini.

    Each model is stored as a separate key (``model.<id>``) with its JSON
    value on a single line so the INI file is human-readable without
    needing to parse one enormous blob.

    Args:
        provider: Provider ID (``PROVIDER_OPENAI`` etc.).
        models:   List of ``ModelInfo`` objects to save.
        path:     Override path to API.ini.
    """
    cfg = _load_ini(path)
    section = f"model_registry_{provider}"
    if not cfg.has_section("model_registry"):
        cfg.add_section("model_registry")
    # Recreate section to remove stale model keys
    if cfg.has_section(section):
        cfg.remove_section(section)
    cfg.add_section(section)

    cfg.set(section, "last_updated", _ts())
    for m in models:
        key = f"model.{m.model_id}"
        cfg.set(section, key, json.dumps(m.to_dict(), ensure_ascii=False))

    cfg.set("model_registry", "version", str(REGISTRY_VERSION))
    _save_ini(cfg, path)
    logger.info("model_registry: saved %d models for %s", len(models), provider)


def load_from_ini(
    provider: str,
    path: Optional[Path] = None,
) -> Tuple[List[ModelInfo], Optional[str]]:
    """Load a provider's models from API.ini.

    Reads individual ``model.<id>`` keys (current format).  Falls back to
    the legacy single ``data`` JSON blob for backward compatibility.

    Returns:
        Tuple ``(models, last_updated)`` where ``last_updated`` is an ISO
        timestamp string (or ``None`` if section is absent / empty).
    """
    cfg = _load_ini(path)
    section = f"model_registry_{provider}"
    if not cfg.has_section(section):
        return [], None

    last_updated = cfg.get(section, "last_updated", fallback=None)

    # --- New per-model key format ---
    models: List[ModelInfo] = []
    for key, raw in cfg.items(section):
        if not key.startswith("model."):
            continue
        try:
            models.append(ModelInfo.from_dict(json.loads(raw)))
        except Exception as exc:
            logger.warning("model_registry: bad model key %s: %s", key, exc)

    if models:
        return models, last_updated

    # --- Legacy single-blob fallback ---
    raw_blob = cfg.get(section, "data", fallback="").strip()
    if not raw_blob:
        return [], last_updated
    try:
        data: Dict[str, Any] = json.loads(raw_blob)
        models = [ModelInfo.from_dict(v) for v in data.values()]
        return models, last_updated
    except Exception as exc:
        logger.warning("model_registry: failed to decode %s from INI: %s",
                       provider, exc)
        return [], last_updated


def _is_stale(last_updated: Optional[str], hours: float = DEFAULT_REFRESH_HOURS) -> bool:
    """Return True if *last_updated* is older than *hours* or missing."""
    if not last_updated:
        return True
    try:
        dt = datetime.fromisoformat(last_updated)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - dt).total_seconds()
        return age > hours * 3600
    except Exception:
        return True


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    """Fetch *url* via HTTP GET and return the response body as a string.

    Raises ``urllib.error.URLError`` on failure.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CherryAI/1.0 (model registry fetcher)",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        charset = "utf-8"
        ct = resp.headers.get("Content-Type", "")
        m = re.search(r"charset=([\w-]+)", ct)
        if m:
            charset = m.group(1)
        return resp.read().decode(charset, errors="replace")


def _http_post_json(
    url: str,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """HTTP POST with JSON body; return (parsed_response, response_headers).

    Returns a tuple of (response body as dict, response headers as dict).
    Raises ``urllib.error.URLError`` / ``json.JSONDecodeError`` on failure.
    """
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "User-Agent": "CherryAI/1.0 (model registry fetcher)",
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        return json.loads(raw), resp_headers


def probe_openai_rate_limits(
    api_key: str,
    model_id: str,
    model_info: Optional[ModelInfo] = None,
    cost_cap: Optional[float] = None,
) -> Optional[Dict[str, int]]:
    """Probe a single OpenAI model for rate limits via response headers.

    Makes a minimal chat completion request (1 output token) and reads
    ``x-ratelimit-limit-requests`` (RPM) and ``x-ratelimit-limit-tokens``
    (TPM) from the response headers.

    Args:
        api_key: OpenAI API key.
        model_id: Model ID to probe (e.g. ``"gpt-4.1-nano"``).

    Returns:
        Dict with ``rpm`` and ``tpm`` keys, or ``None`` on failure.
    """
    effective_cost_cap = (
        get_configured_cost_cap() if cost_cap is None else cost_cap
    )
    status = (
        get_model_cost_status(model_info, cost_cap=effective_cost_cap)
        if model_info is not None
        else get_model_cost_status_by_id(
            model_id,
            cost_cap=effective_cost_cap,
        )
    )
    if status.blocked:
        logger.info(
            "probe_rate_limits(%s): skipped: %s",
            model_id,
            describe_model_cost_status(status),
        )
        return None

    try:
        _, headers = _http_post_json(
            f"{OPENAI_BASE_URL}/chat/completions",
            body={
                "model": model_id,
                "messages": [{"role": "user", "content": "hi"}],
                "max_completion_tokens": 1,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        result: Dict[str, int] = {}
        rpm_raw = headers.get("x-ratelimit-limit-requests")
        tpm_raw = headers.get("x-ratelimit-limit-tokens")
        if rpm_raw:
            result["rpm"] = int(rpm_raw)
        if tpm_raw:
            result["tpm"] = int(tpm_raw)
        if result:
            logger.info(
                "probe_rate_limits(%s): rpm=%s tpm=%s",
                model_id, result.get("rpm"), result.get("tpm"),
            )
            return result
    except Exception as exc:
        logger.warning("probe_rate_limits(%s): failed: %s", model_id, exc)
    return None


def fetch_openai_model_limits(
    api_key: str,
) -> Dict[str, Dict[str, int]]:
    """Fetch per-model rate limits from the OpenAI model_limits endpoint.

    Calls ``GET /v1/fine_tuning/model_limits`` and extracts RPM / TPM
    values for each model returned.

    The results are also persisted to ``API.ini`` via
    :func:`functions.api_config.set_rate_limit`.

    Args:
        api_key: OpenAI API key.

    Returns:
        Dict mapping ``model_id → {"rpm": int, "tpm": int}``.
        Empty dict on failure.
    """
    url = "https://api.openai.com/v1/fine_tuning/model_limits"
    result: Dict[str, Dict[str, int]] = {}
    try:
        raw = _http_get(url, headers={"Authorization": f"Bearer {api_key}"})
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("fetch_openai_model_limits: request failed: %s", exc)
        return result

    items = data.get("data", [])
    if not isinstance(items, list):
        logger.warning("fetch_openai_model_limits: unexpected response shape")
        return result

    for item in items:
        model_id = item.get("model", "")
        if not model_id:
            continue
        limits = item.get("limits", item)
        rpm = (
            limits.get("max_requests_per_minute")
            or limits.get("rpm")
            or item.get("max_requests_per_minute")
            or 0
        )
        tpm = (
            limits.get("max_tokens_per_minute")
            or limits.get("tpm")
            or item.get("max_tokens_per_minute")
            or 0
        )
        if rpm or tpm:
            result[model_id] = {"rpm": int(rpm), "tpm": int(tpm)}

    # Persist to API.ini
    if result:
        try:
            from functions.api_config import set_rate_limit
            for mid, lims in result.items():
                set_rate_limit(mid, rpm=lims["rpm"], tpm=lims["tpm"])
            logger.info(
                "fetch_openai_model_limits: stored limits for %d models",
                len(result),
            )
        except Exception as exc:
            logger.warning(
                "fetch_openai_model_limits: failed to persist: %s", exc,
            )

    return result


# ---------------------------------------------------------------------------
# Provider-specific fetchers
# ---------------------------------------------------------------------------

# --- OpenAI ---

def _parse_openai_pricing(html: str) -> Dict[str, Dict[str, Optional[float]]]:
    """Extract text-token pricing from the OpenAI pricing page HTML.

    Returns dict: model_id → {input, cached_input, output, batch_input, batch_output}

    The page table has columns: Model | Batch(in) | Flex(cached) | Standard(out)
    and a second pass is needed for batch output (which the page omits) —
    we derive batch_output = standard_output × 0.5.
    """
    pricing: Dict[str, Dict[str, Optional[float]]] = {}
    # Pattern: table row with model name and dollar amounts
    # Format from fetched page: "| gpt-4.1 | $2.00 | $0.50 | $8.00 |"
    row_re = re.compile(
        r"\|\s*(gpt-\S+|o\d\S*)\s*\|\s*\$([\d.]+)\s*\|\s*(?:\$([\d.]+)|-)?\s*\|\s*\$([\d.]+)\s*\|",
        re.IGNORECASE,
    )
    for m in row_re.finditer(html):
        model_id = m.group(1).strip()
        try:
            inp = float(m.group(2))
        except (TypeError, ValueError):
            inp = 0.0
        try:
            cached = float(m.group(3)) if m.group(3) else None
        except (TypeError, ValueError):
            cached = None
        try:
            out = float(m.group(4))
        except (TypeError, ValueError):
            out = 0.0
        pricing[model_id] = {
            "input": inp,
            "cached_input": cached,
            "output": out,
            "batch_input": round(inp * 0.5, 6) if inp else None,
            "batch_output": round(out * 0.5, 6) if out else None,
        }
    return pricing


def fetch_openai_models(
    api_key: str,
    probe_limits: bool = False,
) -> List[ModelInfo]:
    """Fetch available OpenAI models via the /v1/models API.

    Also attempts to enrich with live pricing from the pricing page.
    When *probe_limits* is ``True``, a minimal chat completion request is
    sent to each structured-output model to read the actual RPM/TPM from
    the ``x-ratelimit-*`` response headers.

    Args:
        api_key:      OpenAI API key.
        probe_limits: If ``True``, probe each model for rate limits
                      (costs ~0.01 cent per model probed).

    Returns:
        List of ``ModelInfo`` objects.  Falls back to ``FALLBACK_MODELS`` if
        the API call fails.
    """
    # --- Fetch model list ---
    try:
        raw = _http_get(
            OPENAI_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        api_data: Dict[str, Any] = json.loads(raw)
        api_model_ids: List[str] = sorted(
            {m["id"] for m in api_data.get("data", [])
             if isinstance(m, dict) and "id" in m}
        )
    except Exception as exc:
        logger.warning("fetch_openai_models: API call failed (%s); using fallback", exc)
        return list(FALLBACK_MODELS[PROVIDER_OPENAI])

    # --- Fetch pricing ---
    pricing_map: Dict[str, Dict[str, Optional[float]]] = {}
    pricing_available = False
    try:
        pricing_html = _http_get(OPENAI_PRICING_URL)
        pricing_map = _parse_openai_pricing(pricing_html)
        pricing_available = bool(pricing_map)
        logger.info("fetch_openai_models: parsed %d pricing entries", len(pricing_map))
    except Exception as exc:
        logger.warning("fetch_openai_models: pricing fetch failed (%s); using embedded", exc)

    # --- Build ModelInfo list ---
    # Start with fallback as a base for all known models with full metadata
    fallback_by_id = {m.model_id: m for m in FALLBACK_MODELS[PROVIDER_OPENAI]}
    now = _ts()
    result: List[ModelInfo] = []
    # Include models that appear both in the API list AND the fallback/pricing
    # (we only want text generation models relevant to translation)
    _text_prefixes = ("gpt-4", "gpt-3.5", "gpt-5", "o1", "o3", "o4")
    for mid in api_model_ids:
        if not any(mid.startswith(p) for p in _text_prefixes):
            continue
        base = fallback_by_id.get(mid)
        if base is None:
            # New model not in fallback — create a skeleton
            base = ModelInfo(
                model_id=mid,
                display_name=mid.replace("-", " ").title(),
                provider=PROVIDER_OPENAI,
                url=OPENAI_BASE_URL,
            )
        # Apply live pricing if available
        if mid in pricing_map:
            p = pricing_map[mid]
            base = ModelInfo(
                **{
                    **base.to_dict(),
                    "input_price": p.get("input"),
                    "cached_input_price": p.get("cached_input"),
                    "output_price": p.get("output"),
                    "batch_input_price": p.get("batch_input"),
                    "batch_output_price": p.get("batch_output"),
                    "fetched_at": now,
                }
            )
        else:
            base = with_unknown_pricing(base, fetched_at=now)
        result.append(base)

    if not result:
        return list(FALLBACK_MODELS[PROVIDER_OPENAI])

    # Also add fallback models NOT returned by the API (legacy / known future)
    present = {m.model_id for m in result}
    for fb in FALLBACK_MODELS[PROVIDER_OPENAI]:
        if fb.model_id not in present:
            result.append(
                with_unknown_pricing(fb, fetched_at=now)
                if not pricing_available or fb.model_id not in pricing_map
                else ModelInfo(**{**fb.to_dict(), "fetched_at": now})
            )

    # Only keep models that support structured output
    result = [m for m in result if m.structured_output]

    # --- Probe rate limits from response headers ---
    if probe_limits and api_key:
        cost_cap = get_configured_cost_cap()
        for i, m in enumerate(result):
            limits = probe_openai_rate_limits(
                api_key,
                m.model_id,
                model_info=m,
                cost_cap=cost_cap,
            )
            if limits:
                updates: Dict[str, Any] = {}
                if "rpm" in limits:
                    updates["rpm_tier1"] = limits["rpm"]
                if "tpm" in limits:
                    updates["tpm_tier1"] = limits["tpm"]
                if updates:
                    result[i] = ModelInfo(**{**m.to_dict(), **updates})

    logger.info("fetch_openai_models: %d models (structured_output only)", len(result))
    return result


# --- Google Gemini ---

def _parse_google_pricing(html: str) -> Dict[str, Dict[str, Optional[float]]]:
    """Extract text-token pricing for Gemini models from the pricing page.

    We look for section headings with the model ID in back-ticks then
    the first Standard pricing row for input and output.
    Pattern: `gemini-X.Y-modelname` … $N.NN … $N.NN
    """
    pricing: Dict[str, Dict[str, Optional[float]]] = {}
    # Match model ID + first two dollar amounts in the same paragraph/section
    # Example: `gemini-2.5-flash` … $0.30 … $2.50
    section_re = re.compile(
        r"`(gemini-[\w.:-]+)`.*?"
        r"\$\s*([\d.]+)[^\n]*?\n"   # first price (input or skip row)
        r"(?:.*?\$\s*([\d.]+))?",
        re.DOTALL,
    )
    for m in section_re.finditer(html):
        model_id = m.group(1).strip()
        if not model_id:
            continue
        try:
            inp = float(m.group(2))
        except (TypeError, ValueError):
            inp = 0.0
        try:
            out = float(m.group(3)) if m.group(3) else None
        except (TypeError, ValueError):
            out = None
        if model_id not in pricing:
            pricing[model_id] = {
                "input": inp,
                "output": out,
                "cached_input": None,
                "batch_input": inp * 0.5 if inp else None,
                "batch_output": out * 0.5 if out else None,
            }
    return pricing


def fetch_google_models(api_key: str) -> List[ModelInfo]:
    """Fetch Google Gemini model list via the v1beta models API.

    Also attempts to parse live pricing from the pricing page.
    Falls back to ``FALLBACK_MODELS[PROVIDER_GOOGLE]`` on failure.
    """
    # --- Fetch model list ---
    try:
        raw = _http_get(
            f"{GOOGLE_MODELS_URL}?pageSize=100&key={api_key}",
        )
        api_data: Dict[str, Any] = json.loads(raw)
        api_models: List[Dict[str, Any]] = api_data.get("models", [])
    except Exception as exc:
        logger.warning("fetch_google_models: API call failed (%s); using fallback", exc)
        return list(FALLBACK_MODELS[PROVIDER_GOOGLE])

    # --- Fetch pricing ---
    pricing_map: Dict[str, Dict[str, Optional[float]]] = {}
    pricing_available = False
    try:
        pricing_html = _http_get(GOOGLE_PRICING_URL)
        pricing_map = _parse_google_pricing(pricing_html)
        pricing_available = bool(pricing_map)
        logger.info("fetch_google_models: parsed %d pricing entries", len(pricing_map))
    except Exception as exc:
        logger.warning("fetch_google_models: pricing fetch failed (%s)", exc)

    fallback_by_id = {m.model_id: m for m in FALLBACK_MODELS[PROVIDER_GOOGLE]}
    now = _ts()
    result: List[ModelInfo] = []

    for model_obj in api_models:
        name_full = model_obj.get("name", "")   # e.g. "models/gemini-2.0-flash"
        base_id = model_obj.get("baseModelId", "")
        # Extract the bare ID
        mid = base_id or name_full.replace("models/", "")
        if not mid.startswith("gemini"):
            continue

        display = model_obj.get("displayName", mid)
        temp_max = model_obj.get("maxTemperature") or 2.0
        thinking = model_obj.get("thinking", False)
        ctx = model_obj.get("inputTokenLimit")

        base = fallback_by_id.get(mid) or ModelInfo(
            model_id=mid,
            display_name=display,
            provider=PROVIDER_GOOGLE,
            url=GOOGLE_BASE_URL,
        )

        # Merge live data
        updates: Dict[str, Any] = {
            "display_name": display,
            "thinking": thinking,
            "temperature_max": float(temp_max),
            "fetched_at": now,
        }
        if ctx:
            updates["context_window"] = int(ctx)

        # Pricing
        if mid in pricing_map:
            p = pricing_map[mid]
            updates.update({
                "input_price": p.get("input"),
                "output_price": p.get("output"),
                "cached_input_price": p.get("cached_input"),
                "batch_input_price": p.get("batch_input"),
                "batch_output_price": p.get("batch_output"),
            })
        else:
            updates.update(_pricing_unknown_updates())

        result.append(ModelInfo(**{**base.to_dict(), **updates}))

    if not result:
        return list(FALLBACK_MODELS[PROVIDER_GOOGLE])

    # Add fallback models not returned by API
    present = {m.model_id for m in result}
    for fb in FALLBACK_MODELS[PROVIDER_GOOGLE]:
        if fb.model_id not in present:
            result.append(
                with_unknown_pricing(fb, fetched_at=now)
                if not pricing_available or fb.model_id not in pricing_map
                else ModelInfo(**{**fb.to_dict(), "fetched_at": now})
            )

    # Only keep models that support structured output
    result = [m for m in result if m.structured_output]

    logger.info("fetch_google_models: %d models (structured_output only)", len(result))
    return result


# --- Mistral ---

def fetch_mistral_models(api_key: str) -> List[ModelInfo]:
    """Fetch Mistral model list from the /v1/models API.

    Pricing is taken from fallback (Mistral's pricing page is JS-rendered
    and cannot be scraped reliably without a headless browser).
    Falls back to ``FALLBACK_MODELS[PROVIDER_MISTRAL]`` on failure.
    """
    try:
        raw = _http_get(
            MISTRAL_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        api_data: Dict[str, Any] = json.loads(raw)
        api_models: List[Dict[str, Any]] = api_data.get("data", [])
    except Exception as exc:
        logger.warning("fetch_mistral_models: API call failed (%s); using fallback", exc)
        return list(FALLBACK_MODELS[PROVIDER_MISTRAL])

    fallback_by_id = {m.model_id: m for m in FALLBACK_MODELS[PROVIDER_MISTRAL]}
    now = _ts()
    result: List[ModelInfo] = []

    for model_obj in api_models:
        mid = model_obj.get("id", "")
        if not mid:
            continue
        # Skip alias "latest" models that are duplicated (keep the ones with
        # explicit version dates too if present)
        base = fallback_by_id.get(mid) or ModelInfo(
            model_id=mid,
            display_name=model_obj.get("name", mid),
            provider=PROVIDER_MISTRAL,
            url=MISTRAL_BASE_URL,
        )
        result.append(with_unknown_pricing(base, fetched_at=now))

    if not result:
        return list(FALLBACK_MODELS[PROVIDER_MISTRAL])

    # Only keep models that support structured output
    result = [m for m in result if m.structured_output]

    logger.info("fetch_mistral_models: %d models (structured_output only)", len(result))
    return result


# ---------------------------------------------------------------------------
# High-level public API
# ---------------------------------------------------------------------------

def refresh_models(
    api_keys: Optional[Dict[str, str]] = None,
    path: Optional[Path] = None,
    providers: Optional[List[str]] = None,
    probe_limits: bool = False,
) -> Dict[str, List[ModelInfo]]:
    """Fetch fresh model data for all (or specified) providers and save to INI.

    Args:
        api_keys:     Dict mapping provider → API key.  If a key is absent/empty,
                      only the pricing-page fetch is attempted; the model list
                      falls back to built-in data.
        path:         Override path for API.ini.
        providers:    Subset of providers to refresh, default = all three.
        probe_limits: If ``True``, probe each OpenAI model for actual rate
                      limits via response headers (costs ~0.01 cent per model).

    Returns:
        Dict mapping provider → list of ModelInfo.
    """
    if api_keys is None:
        api_keys = {}
    if providers is None:
        providers = list(ALL_PROVIDERS)

    result: Dict[str, List[ModelInfo]] = {}

    for provider in providers:
        key = api_keys.get(provider, "").strip()
        try:
            if provider == PROVIDER_OPENAI:
                models = (
                    fetch_openai_models(key, probe_limits=probe_limits)
                    if key
                    else list(FALLBACK_MODELS[PROVIDER_OPENAI])
                )
            elif provider == PROVIDER_GOOGLE:
                models = fetch_google_models(key) if key else list(FALLBACK_MODELS[PROVIDER_GOOGLE])
            elif provider == PROVIDER_MISTRAL:
                models = fetch_mistral_models(key) if key else list(FALLBACK_MODELS[PROVIDER_MISTRAL])
            else:
                logger.warning("refresh_models: unknown provider '%s', skipping", provider)
                continue
        except Exception as exc:
            logger.error("refresh_models: provider %s failed: %s; using fallback", provider, exc)
            models = list(FALLBACK_MODELS.get(provider, []))

        save_to_ini(provider, models, path)
        result[provider] = models

    # After saving all models, fetch rate limits from OpenAI model_limits
    # endpoint and store them in API.ini.
    openai_key = api_keys.get(PROVIDER_OPENAI, "").strip()
    if openai_key and PROVIDER_OPENAI in providers:
        try:
            fetch_openai_model_limits(openai_key)
        except Exception as exc:
            logger.warning(
                "refresh_models: fetch_openai_model_limits failed: %s", exc,
            )

    return result


def get_all_models(
    path: Optional[Path] = None,
    providers: Optional[List[str]] = None,
    max_age_hours: float = DEFAULT_REFRESH_HOURS,
) -> Dict[str, List[ModelInfo]]:
    """Return model data for all providers, loading from INI when fresh.

    If INI data is stale (exceeds *max_age_hours*) the fallback data is
    returned but **no network request is made at this point** — call
    ``refresh_models()`` explicitly to update.

    Args:
        path:          Override path for API.ini.
        providers:     Subset of providers to include.
        max_age_hours: How old cached data can be before falling back.

    Returns:
        Dict mapping provider → list of ModelInfo.
    """
    if providers is None:
        providers = list(ALL_PROVIDERS)
    result: Dict[str, List[ModelInfo]] = {}
    for provider in providers:
        models, last_updated = load_from_ini(provider, path)
        if not models or _is_stale(last_updated, max_age_hours):
            models = list(FALLBACK_MODELS.get(provider, []))
        result[provider] = models
    return result


def get_all_models_flat(
    path: Optional[Path] = None,
    max_age_hours: float = DEFAULT_REFRESH_HOURS,
) -> List[ModelInfo]:
    """Return a flat list of all models across all providers."""
    all_models: List[ModelInfo] = []
    for models in get_all_models(path=path, max_age_hours=max_age_hours).values():
        all_models.extend(models)
    return all_models


def get_provider_models(
    provider: str,
    path: Optional[Path] = None,
    max_age_hours: float = DEFAULT_REFRESH_HOURS,
) -> List[ModelInfo]:
    """Return model list for a specific provider."""
    models, last_updated = load_from_ini(provider, path)
    if not models or _is_stale(last_updated, max_age_hours):
        return list(FALLBACK_MODELS.get(provider, []))
    return models


def get_model_info(
    model_id: str,
    path: Optional[Path] = None,
) -> Optional[ModelInfo]:
    """Look up a single model by ID across all providers.

    Returns ``None`` if not found.
    """
    for provider in ALL_PROVIDERS:
        models, _ = load_from_ini(provider, path)
        if not models:
            models = FALLBACK_MODELS.get(provider, [])
        for m in models:
            if m.model_id == model_id:
                return m
    # Try fallback
    for provider_models in FALLBACK_MODELS.values():
        for m in provider_models:
            if m.model_id == model_id:
                return m
    return None


def get_pricing_dict(
    path: Optional[Path] = None,
    max_age_hours: float = DEFAULT_REFRESH_HOURS,
) -> Dict[str, Dict[str, Any]]:
    """Return a ``MODEL_PRICING``-compatible dict for all known models.

    This dict is backward-compatible with the legacy ``MODEL_PRICING``
    constant in ``functions/config.py`` and can be used as a drop-in
    replacement.
    """
    result: Dict[str, Dict[str, Any]] = {}
    for models in get_all_models(path=path, max_age_hours=max_age_hours).values():
        for m in models:
            result[m.model_id] = m.to_pricing_entry()
    return result


def get_provider_model_ids(
    provider: str,
    path: Optional[Path] = None,
) -> List[str]:
    """Return list of model IDs for a provider (for dropdown population)."""
    return [m.model_id for m in get_provider_models(provider, path)]


def get_all_provider_urls() -> Dict[str, str]:
    """Return dict of provider → base URL (used by API_PROVIDERS compat)."""
    return {
        PROVIDER_OPENAI: OPENAI_BASE_URL,
        PROVIDER_GOOGLE: GOOGLE_BASE_URL,
        PROVIDER_MISTRAL: MISTRAL_BASE_URL,
    }


def get_last_refresh_time(
    provider: str,
    path: Optional[Path] = None,
) -> Optional[str]:
    """Return the ISO timestamp of the last successful refresh, or None."""
    _, last_updated = load_from_ini(provider, path)
    return last_updated


def is_data_fresh(
    provider: str,
    path: Optional[Path] = None,
    max_age_hours: float = DEFAULT_REFRESH_HOURS,
) -> bool:
    """Return True if the stored data for *provider* is younger than *max_age_hours*."""
    _, last_updated = load_from_ini(provider, path)
    return bool(last_updated) and not _is_stale(last_updated, max_age_hours)


def get_registry_summary(path: Optional[Path] = None) -> Dict[str, Any]:
    """Return a lightweight summary of what's in the registry.

    Useful for the "Refresh Models" button in the UI to show users what
    data is currently cached and when it was fetched.
    """
    summary: Dict[str, Any] = {}
    for provider in ALL_PROVIDERS:
        models, last_updated = load_from_ini(provider, path)
        if not models:
            models = FALLBACK_MODELS.get(provider, [])
        summary[provider] = {
            "count": len(models),
            "last_updated": last_updated,
            "is_fresh": is_data_fresh(provider, path),
            "models": [m.model_id for m in models],
        }
    return summary
