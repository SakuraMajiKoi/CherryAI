"""Estimation engine for CherryAI (TASK 17.9).

Computes token estimates, cost predictions, and manages inference options
that determine how the translation pipeline will run. Provides live price
preview based on selected model/preset and configurable pipeline toggles.

Uses MODEL_PRICING from functions/config.py as the price source, with
graceful fallback to defaults when model is unknown.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Average tokens-per-line for Japanese source text (empirical)
DEFAULT_TOKENS_PER_LINE: float = 25.0

# Output multiplier (JP → EN typical expansion)
DEFAULT_OUTPUT_MULTIPLIER: float = 1.2

# Overhead tokens per API call (system prompt + framing)
DEFAULT_PROMPT_OVERHEAD: int = 500

# Default chunk size in lines
DEFAULT_CHUNK_SIZE: int = 50

# Batch API discount factor (50% cheaper)
BATCH_DISCOUNT: float = 0.5

# Task type multipliers for additional API calls
TASK_MULTIPLIERS: Dict[str, float] = {
    "translation": 1.0,
    "summary": 0.05,       # ~5% of main translation cost
    "glossary": 0.03,      # ~3% of main translation cost
    "editing": 1.0,        # Full pass per editing round
    "tlc": 0.8,            # Slightly less than full pass
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class InferenceOptions:
    """Configurable options that control the translation pipeline.

    Each option affects cost and workflow. The estimation engine uses
    these to compute an itemized cost breakdown.
    """

    # Core translation
    translation_enabled: bool = True
    chunk_max_lines: int = 50
    chunk_max_tokens: int = 4000
    rolling_context: bool = True
    batch_api: bool = False
    use_local_model: bool = False

    # Summary
    summary_enabled: bool = False
    summary_size: int = 200    # Target summary tokens
    summary_request_size: int = 2000  # Max source tokens per summary request

    # Glossary
    glossary_enabled: bool = False
    glossary_full: bool = False  # False = uncertain-only, True = full
    glossary_fraction: float = 0.3  # Fraction of lines sent for glossary (~30%)

    # Editing & TLC
    editing_passes: int = 0
    tlc_passes: int = 0

    # Deduplication
    dedup_enabled: bool = False
    dedup_ratio: float = 0.0  # Expected dedup reduction (0.0-1.0)

    # Quote stripping
    strip_quotes: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InferenceOptions:
        """Create from dictionary, ignoring unknown keys."""
        known = cls.__annotations__.keys()
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class CostLineItem:
    """A single line item in the cost estimate breakdown."""

    task: str           # e.g., "translation", "editing_pass_1"
    description: str    # Human-readable description
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)


@dataclass
class CostEstimate:
    """Complete cost estimate with itemized breakdown."""

    model: str = ""
    total_lines: int = 0
    effective_lines: int = 0  # After dedup
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    batch_discount_applied: bool = False
    line_items: List[CostLineItem] = field(default_factory=list)
    options: Optional[InferenceOptions] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "model": self.model,
            "total_lines": self.total_lines,
            "effective_lines": self.effective_lines,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "batch_discount_applied": self.batch_discount_applied,
            "line_items": [item.to_dict() for item in self.line_items],
        }


# ---------------------------------------------------------------------------
# Core estimation functions
# ---------------------------------------------------------------------------

def estimate_tokens_for_lines(
    line_count: int,
    tokens_per_line: float = DEFAULT_TOKENS_PER_LINE,
    output_multiplier: float = DEFAULT_OUTPUT_MULTIPLIER,
) -> Dict[str, int]:
    """Estimate input and output token counts for a batch of lines.

    Args:
        line_count: Number of source lines.
        tokens_per_line: Average tokens per source line.
        output_multiplier: Ratio of output tokens to input tokens.

    Returns:
        Dict with 'input_tokens' and 'output_tokens'.
    """
    input_tokens = int(math.ceil(line_count * tokens_per_line))
    output_tokens = int(math.ceil(input_tokens * output_multiplier))
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def estimate_chunks(
    line_count: int,
    chunk_max_lines: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """Estimate number of API chunks needed.

    Args:
        line_count: Total lines to translate.
        chunk_max_lines: Max lines per chunk.

    Returns:
        Number of chunks (at least 1 if line_count > 0).
    """
    if line_count <= 0:
        return 0
    return max(1, math.ceil(line_count / max(1, chunk_max_lines)))


def compute_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_m: float,
    output_price_per_m: float,
    batch_mode: bool = False,
) -> Dict[str, float]:
    """Compute cost in USD for given token counts and pricing.

    Args:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        input_price_per_m: Price per 1M input tokens.
        output_price_per_m: Price per 1M output tokens.
        batch_mode: Apply 50% batch discount.

    Returns:
        Dict with 'input_cost', 'output_cost', 'total_cost'.
    """
    discount = BATCH_DISCOUNT if batch_mode else 1.0
    in_cost = (input_tokens / 1_000_000) * input_price_per_m * discount
    out_cost = (output_tokens / 1_000_000) * output_price_per_m * discount
    total = in_cost + out_cost
    return {
        "input_cost": round(in_cost, 6),
        "output_cost": round(out_cost, 6),
        "total_cost": round(total, 6),
    }


def build_estimate(
    total_lines: int,
    model: str = "",
    options: Optional[InferenceOptions] = None,
    pricing: Optional[Dict[str, float]] = None,
    tokens_per_line: float = DEFAULT_TOKENS_PER_LINE,
    output_multiplier: float = DEFAULT_OUTPUT_MULTIPLIER,
    prompt_overhead: int = DEFAULT_PROMPT_OVERHEAD,
) -> CostEstimate:
    """Build a complete itemized cost estimate.

    Args:
        total_lines: Number of source lines to translate.
        model: Model ID for pricing lookup.
        options: Inference options controlling pipeline features.
        pricing: Optional explicit pricing dict with 'input' and 'output'
            (per 1M tokens). If None, attempts to look up from config.
        tokens_per_line: Average tokens per source line.
        output_multiplier: Output/input token ratio.
        prompt_overhead: Per-chunk overhead tokens (system prompt).

    Returns:
        CostEstimate with itemized line items.
    """
    if options is None:
        options = InferenceOptions()

    # Resolve pricing
    if pricing is None:
        pricing = _get_pricing(model)
    input_price = pricing.get("input", 0.0)
    output_price = pricing.get("output", 0.0)

    # Apply dedup reduction
    effective_lines = total_lines
    if options.dedup_enabled and options.dedup_ratio > 0:
        effective_lines = max(1, int(total_lines * (1.0 - options.dedup_ratio)))

    estimate = CostEstimate(
        model=model,
        total_lines=total_lines,
        effective_lines=effective_lines,
        batch_discount_applied=options.batch_api,
        options=options,
        line_items=[],
    )

    # --- Translation ---
    if options.translation_enabled:
        n_chunks = estimate_chunks(effective_lines, options.chunk_max_lines)
        toks = estimate_tokens_for_lines(
            effective_lines, tokens_per_line, output_multiplier
        )
        # Add prompt overhead per chunk
        total_input = toks["input_tokens"] + (n_chunks * prompt_overhead)
        total_output = toks["output_tokens"]
        cost = compute_cost(
            total_input, total_output,
            input_price, output_price,
            batch_mode=options.batch_api,
        )
        item = CostLineItem(
            task="translation",
            description=f"Translation ({effective_lines} lines, {n_chunks} chunks)",
            input_tokens=total_input,
            output_tokens=total_output,
            **cost,
        )
        estimate.line_items.append(item)

    # --- Summary ---
    if options.summary_enabled:
        # Summary uses a fraction of lines
        summary_input = int(total_lines * tokens_per_line * 0.5)  # ~50% of text
        summary_output = options.summary_size
        cost = compute_cost(
            summary_input, summary_output, input_price, output_price
        )
        item = CostLineItem(
            task="summary",
            description="Game Summary generation",
            input_tokens=summary_input,
            output_tokens=summary_output,
            **cost,
        )
        estimate.line_items.append(item)

    # --- Glossary ---
    if options.glossary_enabled:
        frac = 1.0 if options.glossary_full else options.glossary_fraction
        glossary_lines = max(1, int(effective_lines * frac))
        toks = estimate_tokens_for_lines(
            glossary_lines, tokens_per_line, 0.5  # glossary output is compact
        )
        cost = compute_cost(
            toks["input_tokens"], toks["output_tokens"],
            input_price, output_price,
        )
        mode_label = "full" if options.glossary_full else "uncertain-only"
        item = CostLineItem(
            task="glossary",
            description=f"Glossary ({mode_label}, ~{glossary_lines} lines)",
            input_tokens=toks["input_tokens"],
            output_tokens=toks["output_tokens"],
            **cost,
        )
        estimate.line_items.append(item)

    # --- Editing passes ---
    for i in range(options.editing_passes):
        toks = estimate_tokens_for_lines(
            effective_lines, tokens_per_line, output_multiplier
        )
        n_chunks = estimate_chunks(effective_lines, options.chunk_max_lines)
        total_input = toks["input_tokens"] + (n_chunks * prompt_overhead)
        total_output = toks["output_tokens"]
        cost = compute_cost(
            total_input, total_output, input_price, output_price
        )
        item = CostLineItem(
            task=f"editing_pass_{i + 1}",
            description=f"Editing pass {i + 1}",
            input_tokens=total_input,
            output_tokens=total_output,
            **cost,
        )
        estimate.line_items.append(item)

    # --- TLC passes ---
    for i in range(options.tlc_passes):
        toks = estimate_tokens_for_lines(
            effective_lines, tokens_per_line, output_multiplier * 0.8
        )
        n_chunks = estimate_chunks(effective_lines, options.chunk_max_lines)
        total_input = toks["input_tokens"] + (n_chunks * prompt_overhead)
        total_output = toks["output_tokens"]
        cost = compute_cost(
            total_input, total_output, input_price, output_price
        )
        item = CostLineItem(
            task=f"tlc_pass_{i + 1}",
            description=f"TLC pass {i + 1}",
            input_tokens=total_input,
            output_tokens=total_output,
            **cost,
        )
        estimate.line_items.append(item)

    # --- Aggregate totals ---
    for item in estimate.line_items:
        estimate.total_input_tokens += item.input_tokens
        estimate.total_output_tokens += item.output_tokens
        estimate.total_cost += item.total_cost

    estimate.total_cost = round(estimate.total_cost, 6)

    return estimate


# ---------------------------------------------------------------------------
# Pricing helper
# ---------------------------------------------------------------------------

def _get_pricing(model: str) -> Dict[str, float]:
    """Resolve pricing for a model from config, with fallback.

    Returns:
        Dict with 'input' and 'output' keys (price per 1M tokens).
    """
    try:
        from .config import get_model_pricing
        info = get_model_pricing(model)
        return {"input": info.get("input", 0.0), "output": info.get("output", 0.0)}
    except Exception:
        return {"input": 0.15, "output": 0.60}  # Cheap default fallback


def compare_models(
    total_lines: int,
    models: Optional[List[str]] = None,
    options: Optional[InferenceOptions] = None,
) -> List[Dict[str, Any]]:
    """Compare cost estimates across multiple models.

    Args:
        total_lines: Number of lines to estimate for.
        models: List of model IDs. If None, uses all known models.
        options: Inference options to apply uniformly.

    Returns:
        List of dicts with 'model', 'display_name', 'total_cost',
        'input_tokens', 'output_tokens', sorted by total_cost ascending.
    """
    if models is None:
        try:
            from .config import get_model_names
            models = get_model_names()
        except Exception:
            models = []

    results: List[Dict[str, Any]] = []
    for model_id in models:
        est = build_estimate(total_lines, model=model_id, options=options)
        try:
            from .config import get_model_display_name
            display = get_model_display_name(model_id)
        except Exception:
            display = model_id
        results.append({
            "model": model_id,
            "display_name": display,
            "total_cost": est.total_cost,
            "input_tokens": est.total_input_tokens,
            "output_tokens": est.total_output_tokens,
        })

    results.sort(key=lambda r: r["total_cost"])
    return results


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_options(path: Path, options: InferenceOptions) -> None:
    """Save inference options to a JSON file.

    Args:
        path: File path to write.
        options: Options to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(options.to_dict(), indent=2), encoding="utf-8")
    logger.debug("Saved inference options to %s", path)


def load_options(path: Path) -> InferenceOptions:
    """Load inference options from a JSON file.

    Args:
        path: File path to read.

    Returns:
        Loaded options, or defaults if file missing/invalid.
    """
    if not path.exists():
        return InferenceOptions()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return InferenceOptions.from_dict(data)
    except Exception as exc:
        logger.warning("Failed to load options from %s: %s", path, exc)
        return InferenceOptions()
