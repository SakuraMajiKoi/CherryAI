"""CherryAI GUI v2 Estimation Step - Backward Compatibility Redirect.

This module re-exports everything from costs.py for backward compatibility.
The step was renamed from Estimation to Costs in Phase 40 (Task 40.1).
"""

# Re-export everything from costs.py
from CherryAI.gui.steps.costs import (  # noqa: F401
    CostsStep,
    ComparisonResult,
    EstimationResult,
    EstimationStep,
    count_tokens,
    estimate_cost,
    estimate_rate_limit_time,
    DEFAULT_MODEL,
    OUTPUT_MULTIPLIER,
    _format_time,
)

# Re-export config constants that were previously accessible via estimate.py
from CherryAI.functions.config import (  # noqa: F401
    MODEL_PRICING,
    DEFAULT_PRICING_MODEL,
    OUTPUT_TOKEN_MULTIPLIER,
)

# Re-export manifest field helpers for backward compatibility
from CherryAI.functions.manifest_fields import (  # noqa: F401
    save_int_field,
    load_int_field,
)

__all__ = [
    "CostsStep",
    "ComparisonResult",
    "EstimationResult",
    "EstimationStep",
    "count_tokens",
    "estimate_cost",
    "estimate_rate_limit_time",
    "DEFAULT_MODEL",
    "OUTPUT_MULTIPLIER",
    "MODEL_PRICING",
    "DEFAULT_PRICING_MODEL",
    "OUTPUT_TOKEN_MULTIPLIER",
]
