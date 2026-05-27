"""Chunker adapter for GUI integration.

This module bridges the GUI estimation step (gui/steps/estimate.py) with the
core chunking functions in functions/chunker.py, functions/chunk_optimizer.py,
and functions/rate_limiter.py.

Purpose:
- Provides clean function signatures for GUI use
- Wraps core chunker functions with fallback implementations
- Integrates chunk optimization and rate limiting for accurate estimates

TASK 16.8: Integrates functions/chunker.py, functions/chunk_optimizer.py,
and functions/rate_limiter.py with GUI Step 5 (Estimation)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------- Imports from functions/chunker.py ---------------- #

_Chunker = None
_ChunkerConfig = None
_ChunkMode = None
_create_chunker = None
_is_tiktoken_available = None

try:
    from CherryAI.functions.chunker import (
        Chunker,
        ChunkerConfig,
        ChunkMode,
        create_chunker,
        is_tiktoken_available as _func_is_tiktoken_available,
    )
    _Chunker = Chunker
    _ChunkerConfig = ChunkerConfig
    _ChunkMode = ChunkMode
    _create_chunker = create_chunker
    _is_tiktoken_available = _func_is_tiktoken_available
except ImportError:
    try:
        from CherryAI.functions.chunker import (
            Chunker,
            ChunkerConfig,
            ChunkMode,
            create_chunker,
            is_tiktoken_available as _func_is_tiktoken_available,
        )
        _Chunker = Chunker
        _ChunkerConfig = ChunkerConfig
        _ChunkMode = ChunkMode
        _create_chunker = create_chunker
        _is_tiktoken_available = _func_is_tiktoken_available
    except ImportError:
        logger.debug("Could not import functions.chunker")


# ---------------- Imports from functions/chunk_optimizer.py ---------------- #

_ChunkOptimizer = None
_OptimizerConfig = None
_BatchResult = None
_ErrorType = None
_OptimizerStats = None

try:
    from CherryAI.functions.chunk_optimizer import (
        ChunkOptimizer,
        OptimizerConfig,
        BatchResult,
        ErrorType,
        OptimizerStats,
    )
    _ChunkOptimizer = ChunkOptimizer
    _OptimizerConfig = OptimizerConfig
    _BatchResult = BatchResult
    _ErrorType = ErrorType
    _OptimizerStats = OptimizerStats
except ImportError:
    try:
        from CherryAI.functions.chunk_optimizer import (
            ChunkOptimizer,
            OptimizerConfig,
            BatchResult,
            ErrorType,
            OptimizerStats,
        )
        _ChunkOptimizer = ChunkOptimizer
        _OptimizerConfig = OptimizerConfig
        _BatchResult = BatchResult
        _ErrorType = ErrorType
        _OptimizerStats = OptimizerStats
    except ImportError:
        logger.debug("Could not import functions.chunk_optimizer")


# ---------------- Imports from functions/rate_limiter.py ---------------- #

_RateLimiter = None
_RateLimiterConfig = None
_ModelRateLimits = None
_DEFAULT_MODEL_LIMITS = None
_RateLimitStats = None
_RateLimitCheckResult = None

try:
    from CherryAI.functions.rate_limiter import (
        RateLimiter,
        RateLimiterConfig,
        ModelRateLimits,
        DEFAULT_MODEL_LIMITS,
        RateLimitStats,
        RateLimitCheckResult,
    )
    _RateLimiter = RateLimiter
    _RateLimiterConfig = RateLimiterConfig
    _ModelRateLimits = ModelRateLimits
    _DEFAULT_MODEL_LIMITS = DEFAULT_MODEL_LIMITS
    _RateLimitStats = RateLimitStats
    _RateLimitCheckResult = RateLimitCheckResult
except ImportError:
    try:
        from CherryAI.functions.rate_limiter import (
            RateLimiter,
            RateLimiterConfig,
            ModelRateLimits,
            DEFAULT_MODEL_LIMITS,
            RateLimitStats,
            RateLimitCheckResult,
        )
        _RateLimiter = RateLimiter
        _RateLimiterConfig = RateLimiterConfig
        _ModelRateLimits = ModelRateLimits
        _DEFAULT_MODEL_LIMITS = DEFAULT_MODEL_LIMITS
        _RateLimitStats = RateLimitStats
        _RateLimitCheckResult = RateLimitCheckResult
    except ImportError:
        logger.debug("Could not import functions.rate_limiter")


# ---------------- Constants ---------------- #

# Default chunk settings
DEFAULT_CHUNK_MODE = "lines"
DEFAULT_MAX_LINES = 50
DEFAULT_MAX_TOKENS = 4000
DEFAULT_MODEL = "gpt-4o"

# Rate limit defaults (fallback)
DEFAULT_RPM = 60  # Requests per minute
DEFAULT_TPM = 40000  # Tokens per minute
DEFAULT_RPD = 0  # Requests per day (0 = unlimited)

# Error rate thresholds for chunk optimization
ERROR_THRESHOLD_WARNING = 0.10  # 10% error rate triggers warning
ERROR_THRESHOLD_REDUCE = 0.20  # 20% error rate triggers chunk reduction


# ---------------- View Classes (GUI-Friendly) ---------------- #


class ChunkModeView(str, Enum):
    """Chunk mode options for GUI display."""

    LINES = "lines"
    TOKENS = "tokens"
    HYBRID = "hybrid"

    @property
    def display_name(self) -> str:
        """Get human-readable name for GUI display."""
        names = {
            "lines": "Line-based",
            "tokens": "Token-based",
            "hybrid": "Hybrid (Lines + Tokens)",
        }
        return names.get(self.value, self.value)

    @property
    def description(self) -> str:
        """Get description for tooltips."""
        descriptions = {
            "lines": "Fixed number of lines per chunk. Simple but may vary in size.",
            "tokens": "Fixed token count per chunk. More accurate for API limits.",
            "hybrid": "Uses whichever limit is reached first. Best of both.",
        }
        return descriptions.get(self.value, "")


@dataclass
class ChunkConfigView:
    """GUI-friendly view of chunker configuration."""

    mode: str = DEFAULT_CHUNK_MODE
    max_lines: int = DEFAULT_MAX_LINES
    max_tokens: int = DEFAULT_MAX_TOKENS
    model: str = DEFAULT_MODEL
    reserve_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "mode": self.mode,
            "max_lines": self.max_lines,
            "max_tokens": self.max_tokens,
            "model": self.model,
            "reserve_tokens": self.reserve_tokens,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChunkConfigView:
        """Create from dictionary."""
        return cls(
            mode=data.get("mode", DEFAULT_CHUNK_MODE),
            max_lines=int(data.get("max_lines", DEFAULT_MAX_LINES)),
            max_tokens=int(data.get("max_tokens", DEFAULT_MAX_TOKENS)),
            model=data.get("model", DEFAULT_MODEL),
            reserve_tokens=int(data.get("reserve_tokens", 0)),
        )


@dataclass
class ChunkResultView:
    """Result of chunking lines for GUI display."""

    chunks: List[List[str]] = field(default_factory=list)
    chunk_count: int = 0
    total_lines: int = 0
    total_tokens: int = 0
    avg_lines_per_chunk: float = 0.0
    avg_tokens_per_chunk: float = 0.0
    max_chunk_tokens: int = 0
    min_chunk_tokens: int = 0
    method: str = "fallback"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "chunk_count": self.chunk_count,
            "total_lines": self.total_lines,
            "total_tokens": self.total_tokens,
            "avg_lines_per_chunk": self.avg_lines_per_chunk,
            "avg_tokens_per_chunk": self.avg_tokens_per_chunk,
            "max_chunk_tokens": self.max_chunk_tokens,
            "min_chunk_tokens": self.min_chunk_tokens,
            "method": self.method,
        }


@dataclass
class RateLimitView:
    """GUI-friendly view of rate limit information."""

    model: str = ""
    rpm: int = DEFAULT_RPM
    tpm: int = DEFAULT_TPM
    rpd: int = DEFAULT_RPD
    tpd: int = 0
    rpm_used: int = 0
    rpd_used: int = 0
    description: str = ""

    @property
    def display_summary(self) -> str:
        """Get summary string for GUI display."""
        parts = []
        if self.rpm > 0:
            parts.append(f"{self.rpm} req/min")
        if self.tpm > 0:
            parts.append(f"{self.tpm:,} tokens/min")
        if self.rpd > 0:
            parts.append(f"{self.rpd:,} req/day")
        return ", ".join(parts) if parts else "No limits"


@dataclass
class TimeEstimateView:
    """GUI-friendly view of time estimation."""

    total_requests: int = 0
    rate_limit_rpm: int = DEFAULT_RPM
    estimated_minutes: float = 0.0
    estimated_seconds: float = 0.0
    formatted: str = ""
    includes_buffer: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "rate_limit_rpm": self.rate_limit_rpm,
            "estimated_minutes": self.estimated_minutes,
            "estimated_seconds": self.estimated_seconds,
            "formatted": self.formatted,
        }


@dataclass
class OptimizerStatsView:
    """GUI-friendly view of chunk optimizer statistics."""

    current_chunk_size: int = DEFAULT_MAX_LINES
    initial_chunk_size: int = DEFAULT_MAX_LINES
    total_batches: int = 0
    successful_batches: int = 0
    failed_batches: int = 0
    error_rate: float = 0.0
    reduction_count: int = 0
    is_at_minimum: bool = False

    @property
    def status_text(self) -> str:
        """Get status text for GUI display."""
        if self.is_at_minimum:
            return "At minimum chunk size"
        if self.error_rate > ERROR_THRESHOLD_REDUCE:
            return f"High error rate ({self.error_rate:.1%}) - reducing chunks"
        if self.error_rate > ERROR_THRESHOLD_WARNING:
            return f"Warning: Error rate {self.error_rate:.1%}"
        return "Optimal"


# ---------------- Token Counting Functions ---------------- #


def count_tokens(text: str, model: str = DEFAULT_MODEL) -> Tuple[int, str]:
    """Count tokens in text using tiktoken if available.

    This wraps functions/chunker.py's Chunker.count_tokens with fallback.

    Args:
        text: Text to count tokens for.
        model: Model name for encoding selection.

    Returns:
        Tuple of (token count, method used).
    """
    if _Chunker is not None and _ChunkerConfig is not None:
        try:
            if _ChunkMode is not None:
                config = _ChunkerConfig(mode=_ChunkMode.TOKENS, model=model)
            else:
                config = _ChunkerConfig(model=model)
            chunker = _Chunker(config)
            count = chunker.count_tokens(text)
            method = getattr(chunker, "last_count_method", "heuristic")
            return count, method
        except Exception as e:
            logger.debug("Chunker count_tokens failed: %s", e)

    # Fallback: heuristic token counting
    return _fallback_count_tokens(text)


def _fallback_count_tokens(text: str) -> Tuple[int, str]:
    """Fallback token counting using heuristics.

    Args:
        text: Text to count tokens for.

    Returns:
        Tuple of (token count, method used).
    """
    if not text:
        return 0, "heuristic/empty"

    # Check for Japanese/CJK characters
    has_cjk = any(
        (0x3040 <= ord(ch) <= 0x30FF) or  # Hiragana/Katakana
        (0x4E00 <= ord(ch) <= 0x9FFF)     # CJK Unified
        for ch in text
    )

    if has_cjk:
        # CJK: approximately 1.5-2 chars per token
        return max(1, len(text) // 2), "heuristic/cjk"
    else:
        # Latin: approximately 4 chars per token
        return max(1, len(text) // 4), "heuristic/latin"


def count_tokens_batch(
    lines: List[str],
    model: str = DEFAULT_MODEL,
) -> Tuple[int, List[int]]:
    """Count tokens for multiple lines.

    Args:
        lines: Lines to count tokens for.
        model: Model name for encoding selection.

    Returns:
        Tuple of (total tokens, per-line token counts).
    """
    if _Chunker is not None and _ChunkerConfig is not None:
        try:
            if _ChunkMode is not None:
                config = _ChunkerConfig(mode=_ChunkMode.TOKENS, model=model)
            else:
                config = _ChunkerConfig(model=model)
            chunker = _Chunker(config)
            total = chunker.count_tokens_batch(lines)
            # Get per-line counts
            per_line = [chunker.count_tokens(line) for line in lines]
            return total, per_line
        except Exception as e:
            logger.debug("Chunker count_tokens_batch failed: %s", e)

    # Fallback
    per_line = []
    total = 0
    for line in lines:
        tokens, _ = _fallback_count_tokens(line)
        per_line.append(tokens)
        total += tokens
    return total, per_line


def is_tiktoken_available() -> bool:
    """Check if tiktoken is available for accurate token counting.

    Returns:
        True if tiktoken is installed, False otherwise.
    """
    if _is_tiktoken_available is not None:
        return _is_tiktoken_available()
    return False


# ---------------- Chunking Functions ---------------- #


def get_chunk_modes() -> List[ChunkModeView]:
    """Get available chunk modes for GUI dropdown.

    Returns:
        List of ChunkModeView enum values.
    """
    return list(ChunkModeView)


def create_chunk_config(
    mode: str = DEFAULT_CHUNK_MODE,
    max_lines: int = DEFAULT_MAX_LINES,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    model: str = DEFAULT_MODEL,
    reserve_tokens: int = 0,
) -> ChunkConfigView:
    """Create a chunk configuration for GUI use.

    Args:
        mode: Chunk mode ("lines", "tokens", "hybrid").
        max_lines: Maximum lines per chunk.
        max_tokens: Maximum tokens per chunk.
        model: Model name for token encoding.
        reserve_tokens: Tokens to reserve for output.

    Returns:
        ChunkConfigView instance.
    """
    return ChunkConfigView(
        mode=mode,
        max_lines=max_lines,
        max_tokens=max_tokens,
        model=model,
        reserve_tokens=reserve_tokens,
    )


def chunk_lines(
    lines: List[str],
    config: Optional[ChunkConfigView] = None,
    mode: str = DEFAULT_CHUNK_MODE,
    max_lines: int = DEFAULT_MAX_LINES,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    model: str = DEFAULT_MODEL,
) -> ChunkResultView:
    """Chunk lines into batches for API requests.

    Args:
        lines: Lines to chunk.
        config: Optional ChunkConfigView. If provided, other params are ignored.
        mode: Chunk mode if config not provided.
        max_lines: Max lines per chunk if config not provided.
        max_tokens: Max tokens per chunk if config not provided.
        model: Model name if config not provided.

    Returns:
        ChunkResultView with chunks and statistics.
    """
    if not lines:
        return ChunkResultView(
            chunks=[],
            chunk_count=0,
            total_lines=0,
            total_tokens=0,
            method="empty",
        )

    # Use config if provided
    if config is not None:
        mode = config.mode
        max_lines = config.max_lines
        max_tokens = config.max_tokens
        model = config.model

    # Try to use core chunker
    if _create_chunker is not None:
        try:
            chunker = _create_chunker(
                mode=mode,
                max_lines=max_lines,
                max_tokens=max_tokens,
                model=model,
            )
            chunks = chunker.chunk_lines(lines)
            total_tokens = chunker.count_tokens_batch(lines)
            method = "chunker"

            # Calculate statistics
            chunk_token_counts = [
                chunker.count_tokens_batch(chunk) for chunk in chunks
            ]
            max_tokens_in_chunk = max(chunk_token_counts) if chunk_token_counts else 0
            min_tokens_in_chunk = min(chunk_token_counts) if chunk_token_counts else 0

            return ChunkResultView(
                chunks=chunks,
                chunk_count=len(chunks),
                total_lines=len(lines),
                total_tokens=total_tokens,
                avg_lines_per_chunk=len(lines) / len(chunks) if chunks else 0,
                avg_tokens_per_chunk=total_tokens / len(chunks) if chunks else 0,
                max_chunk_tokens=max_tokens_in_chunk,
                min_chunk_tokens=min_tokens_in_chunk,
                method=method,
            )
        except Exception as e:
            logger.debug("Chunker failed, using fallback: %s", e)

    # Fallback: simple line-based chunking
    return _fallback_chunk_lines(lines, max_lines)


def _fallback_chunk_lines(
    lines: List[str],
    max_lines: int = DEFAULT_MAX_LINES,
) -> ChunkResultView:
    """Fallback chunking using simple line counts.

    Args:
        lines: Lines to chunk.
        max_lines: Maximum lines per chunk.

    Returns:
        ChunkResultView with chunks and statistics.
    """
    chunks: List[List[str]] = []
    for i in range(0, len(lines), max_lines):
        chunks.append(lines[i:i + max_lines])

    # Calculate token totals
    total_tokens = 0
    chunk_token_counts: List[int] = []
    for chunk in chunks:
        chunk_tokens = 0
        for line in chunk:
            tokens, _ = _fallback_count_tokens(line)
            chunk_tokens += tokens
        chunk_token_counts.append(chunk_tokens)
        total_tokens += chunk_tokens

    return ChunkResultView(
        chunks=chunks,
        chunk_count=len(chunks),
        total_lines=len(lines),
        total_tokens=total_tokens,
        avg_lines_per_chunk=len(lines) / len(chunks) if chunks else 0,
        avg_tokens_per_chunk=total_tokens / len(chunks) if chunks else 0,
        max_chunk_tokens=max(chunk_token_counts) if chunk_token_counts else 0,
        min_chunk_tokens=min(chunk_token_counts) if chunk_token_counts else 0,
        method="fallback/lines",
    )


def estimate_chunks(
    lines: List[str],
    max_lines: int = DEFAULT_MAX_LINES,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    mode: str = DEFAULT_CHUNK_MODE,
    model: str = DEFAULT_MODEL,
) -> int:
    """Estimate how many chunks lines will produce without full chunking.

    Args:
        lines: Lines to estimate for.
        max_lines: Max lines per chunk.
        max_tokens: Max tokens per chunk.
        mode: Chunk mode.
        model: Model name.

    Returns:
        Estimated number of chunks.
    """
    if not lines:
        return 0

    if mode == "lines":
        return math.ceil(len(lines) / max_lines)

    # For token/hybrid modes, need to actually count
    result = chunk_lines(
        lines,
        mode=mode,
        max_lines=max_lines,
        max_tokens=max_tokens,
        model=model,
    )
    return result.chunk_count


# ---------------- Rate Limiting Functions ---------------- #


def get_model_rate_limits(model: str) -> RateLimitView:
    """Get rate limits for a specific model.

    Args:
        model: Model name (e.g., "gemini-2.0-flash", "gpt-4o").

    Returns:
        RateLimitView with rate limit information.
    """
    if _DEFAULT_MODEL_LIMITS is not None:
        # Check for exact match first
        if model in _DEFAULT_MODEL_LIMITS:
            limits = _DEFAULT_MODEL_LIMITS[model]
            return RateLimitView(
                model=model,
                rpm=limits.rpm,
                tpm=limits.tpm,
                rpd=limits.rpd,
                tpd=limits.tpd,
                description=limits.description,
            )

        # Try pattern matching
        model_lower = model.lower()
        for known_model, limits in _DEFAULT_MODEL_LIMITS.items():
            if model_lower.startswith(known_model.lower()):
                return RateLimitView(
                    model=model,
                    rpm=limits.rpm,
                    tpm=limits.tpm,
                    rpd=limits.rpd,
                    tpd=limits.tpd,
                    description=limits.description,
                )

        # Family pattern matching
        if "gemini" in model_lower:
            if "flash-lite" in model_lower:
                return RateLimitView(model=model, rpm=30, tpm=1000000, rpd=1500)
            elif "flash" in model_lower:
                return RateLimitView(model=model, rpm=15, tpm=1000000, rpd=1500)
            elif "pro" in model_lower:
                return RateLimitView(model=model, rpm=5, tpm=250000, rpd=50)

        if "gpt-4" in model_lower:
            if "mini" in model_lower:
                return RateLimitView(model=model, rpm=500, tpm=200000)
            return RateLimitView(model=model, rpm=500, tpm=30000)

        if "gpt-3.5" in model_lower:
            return RateLimitView(model=model, rpm=3500, tpm=200000)

        if "claude" in model_lower:
            return RateLimitView(model=model, rpm=50, tpm=40000)

    # Default fallback
    return RateLimitView(
        model=model,
        rpm=DEFAULT_RPM,
        tpm=DEFAULT_TPM,
        description="Default limits",
    )


def get_all_model_limits() -> Dict[str, RateLimitView]:
    """Get rate limits for all known models.

    Returns:
        Dictionary mapping model names to RateLimitView.
    """
    result: Dict[str, RateLimitView] = {}

    if _DEFAULT_MODEL_LIMITS is not None:
        for model_name, limits in _DEFAULT_MODEL_LIMITS.items():
            result[model_name] = RateLimitView(
                model=model_name,
                rpm=limits.rpm,
                tpm=limits.tpm,
                rpd=limits.rpd,
                tpd=limits.tpd,
                description=limits.description,
            )
    else:
        # Fallback with common models
        common_models = [
            ("gemini-2.0-flash", 15, 1000000, 1500),
            ("gpt-4o", 500, 30000, 0),
            ("gpt-4o-mini", 500, 200000, 0),
            ("claude-3-sonnet", 50, 40000, 0),
        ]
        for model_name, rpm, tpm, rpd in common_models:
            result[model_name] = RateLimitView(
                model=model_name,
                rpm=rpm,
                tpm=tpm,
                rpd=rpd,
            )

    return result


def estimate_rate_limit_time(
    total_requests: int,
    rate_limit_rpm: int = DEFAULT_RPM,
    include_buffer: bool = True,
    buffer_percent: float = 0.1,
    concurrent_requests: int = 1,
    total_output_tokens: int = 0,
    token_speed: int = 50,
) -> TimeEstimateView:
    """Estimate time to complete requests given rate limits (Task 40.7).

    Uses the formula::

        time = max(
            total_requests / concurrent_requests * time_per_request,
            total_output_tokens / token_speed,
            total_requests / rate_limit_rpm * 60,
        )

    Args:
        total_requests: Total number of API requests to make.
        rate_limit_rpm: Requests per minute limit.
        include_buffer: Whether to add safety buffer.
        buffer_percent: Buffer percentage (0.1 = 10%).
        concurrent_requests: Max parallel API calls allowed.
        total_output_tokens: Total output tokens to generate.
        token_speed: Tokens per second for the model (default 50).

    Returns:
        TimeEstimateView with time estimation.
    """
    if total_requests <= 0:
        return TimeEstimateView(
            total_requests=0,
            formatted="0 seconds",
        )

    if rate_limit_rpm <= 0:
        # No rate limit
        return TimeEstimateView(
            total_requests=total_requests,
            rate_limit_rpm=0,
            estimated_minutes=0,
            formatted="No rate limit",
        )

    concurrent = max(concurrent_requests, 1)
    tps = max(token_speed, 1)

    # Three bottleneck calculations (Task 40.7)
    # 1. Concurrent request throughput (avg ~2s per request)
    time_per_request = 2.0  # seconds
    concurrent_seconds = (total_requests / concurrent) * time_per_request

    # 2. Token generation speed
    token_seconds = (
        total_output_tokens / tps if total_output_tokens > 0 else 0.0
    )

    # 3. Rate limit constraint
    rate_limit_seconds = (total_requests / rate_limit_rpm) * 60

    # Take the maximum bottleneck
    seconds = max(concurrent_seconds, token_seconds, rate_limit_seconds)

    # Add buffer if requested
    if include_buffer:
        seconds *= (1 + buffer_percent)

    minutes = seconds / 60

    # Format string
    if minutes >= 60:
        hours = int(minutes // 60)
        remaining_mins = int(minutes % 60)
        formatted = f"{hours}h {remaining_mins}m"
    elif minutes >= 1:
        formatted = f"{int(minutes)}m {int(seconds % 60)}s"
    else:
        formatted = f"{int(seconds)}s"

    return TimeEstimateView(
        total_requests=total_requests,
        rate_limit_rpm=rate_limit_rpm,
        estimated_minutes=minutes,
        estimated_seconds=seconds,
        formatted=formatted,
        includes_buffer=include_buffer,
    )


def estimate_time_for_model(
    total_requests: int,
    model: str,
    include_buffer: bool = True,
) -> TimeEstimateView:
    """Estimate time for a specific model based on its rate limits.

    Args:
        total_requests: Total API requests to make.
        model: Model name to get rate limits for.
        include_buffer: Whether to add safety buffer.

    Returns:
        TimeEstimateView with model-specific time estimate.
    """
    limits = get_model_rate_limits(model)
    return estimate_rate_limit_time(
        total_requests=total_requests,
        rate_limit_rpm=limits.rpm,
        include_buffer=include_buffer,
    )


# ---------------- Chunk Optimizer Functions ---------------- #


def create_optimizer_stats(
    current_size: int = DEFAULT_MAX_LINES,
    initial_size: int = DEFAULT_MAX_LINES,
    total_batches: int = 0,
    successful: int = 0,
    failed: int = 0,
) -> OptimizerStatsView:
    """Create optimizer statistics view.

    Args:
        current_size: Current chunk size.
        initial_size: Initial chunk size.
        total_batches: Total batches processed.
        successful: Successful batch count.
        failed: Failed batch count.

    Returns:
        OptimizerStatsView instance.
    """
    error_rate = failed / total_batches if total_batches > 0 else 0.0
    return OptimizerStatsView(
        current_chunk_size=current_size,
        initial_chunk_size=initial_size,
        total_batches=total_batches,
        successful_batches=successful,
        failed_batches=failed,
        error_rate=error_rate,
        is_at_minimum=current_size <= 5,
    )


def get_adaptive_chunk_size(
    initial_size: int = DEFAULT_MAX_LINES,
    error_rate: float = 0.0,
    min_size: int = 5,
    reduction_factor: float = 0.75,
) -> int:
    """Calculate adaptive chunk size based on error rate.

    This simulates chunk_optimizer.py behavior for GUI preview.

    Args:
        initial_size: Starting chunk size.
        error_rate: Current error rate (0.0-1.0).
        min_size: Minimum chunk size.
        reduction_factor: Factor to reduce by on errors.

    Returns:
        Recommended chunk size.
    """
    if _ChunkOptimizer is not None and _OptimizerConfig is not None:
        try:
            config = _OptimizerConfig(
                initial_chunk_size=initial_size,
                min_chunk_size=min_size,
                reduction_factor=reduction_factor,
            )
            optimizer = _ChunkOptimizer(config)
            return optimizer.get_chunk_size()
        except Exception as e:
            logger.debug("ChunkOptimizer failed: %s", e)

    # Fallback: simple reduction based on error rate
    if error_rate > ERROR_THRESHOLD_REDUCE:
        # Reduce by factor for each 10% above threshold
        reductions = int((error_rate - ERROR_THRESHOLD_WARNING) / 0.10)
        size = initial_size
        for _ in range(reductions):
            size = int(size * reduction_factor)
        return max(min_size, size)

    return initial_size


def get_optimizer_recommendation(
    total_lines: int,
    chunk_size: int = DEFAULT_MAX_LINES,
    estimated_error_rate: float = 0.0,
) -> Dict[str, Any]:
    """Get chunk size recommendation based on project characteristics.

    Args:
        total_lines: Total lines to process.
        chunk_size: Current/planned chunk size.
        estimated_error_rate: Expected error rate.

    Returns:
        Dictionary with recommendation details.
    """
    chunks = math.ceil(total_lines / chunk_size) if chunk_size > 0 else 0
    recommended_size = get_adaptive_chunk_size(
        initial_size=chunk_size,
        error_rate=estimated_error_rate,
    )

    recommendation = {
        "current_chunk_size": chunk_size,
        "recommended_size": recommended_size,
        "estimated_chunks": chunks,
        "size_changed": recommended_size != chunk_size,
        "reason": "",
    }

    if recommended_size < chunk_size:
        recommendation["reason"] = (
            f"Reduced from {chunk_size} to {recommended_size} "
            f"due to {estimated_error_rate:.0%} error rate"
        )
    elif total_lines > 1000 and chunk_size > 25:
        recommendation["reason"] = (
            "Consider smaller chunks for large projects to improve error recovery"
        )
    else:
        recommendation["reason"] = "Current chunk size is optimal"

    return recommendation


# ---------------- Combined Estimation Functions ---------------- #


def estimate_translation_job(
    lines: List[str],
    model: str = DEFAULT_MODEL,
    chunk_size: int = DEFAULT_MAX_LINES,
    output_ratio: float = 1.0,
) -> Dict[str, Any]:
    """Comprehensive estimation for a translation job.

    Combines token counting, chunking, rate limiting, and cost estimation
    into a single result for GUI display.

    Args:
        lines: Lines to translate.
        model: Model to use.
        chunk_size: Lines per chunk.
        output_ratio: Expected output/input token ratio.

    Returns:
        Dictionary with all estimation details.
    """
    if not lines:
        return {
            "status": "empty",
            "total_lines": 0,
            "total_tokens": 0,
            "chunk_count": 0,
            "estimated_time": TimeEstimateView(formatted="0 seconds"),
            "rate_limits": RateLimitView(),
        }

    # Count tokens
    total_tokens, per_line = count_tokens_batch(lines, model=model)
    output_tokens = int(total_tokens * output_ratio)

    # Chunk lines
    chunk_result = chunk_lines(
        lines,
        mode="lines",
        max_lines=chunk_size,
        model=model,
    )

    # Get rate limits
    rate_limits = get_model_rate_limits(model)

    # Estimate time
    time_estimate = estimate_rate_limit_time(
        total_requests=chunk_result.chunk_count,
        rate_limit_rpm=rate_limits.rpm,
    )

    # Get optimizer recommendation
    optimizer_rec = get_optimizer_recommendation(
        total_lines=len(lines),
        chunk_size=chunk_size,
    )

    return {
        "status": "estimated",
        "total_lines": len(lines),
        "total_tokens": total_tokens,
        "output_tokens": output_tokens,
        "chunk_count": chunk_result.chunk_count,
        "chunks": chunk_result.to_dict(),
        "estimated_time": time_estimate.to_dict(),
        "rate_limits": {
            "rpm": rate_limits.rpm,
            "tpm": rate_limits.tpm,
            "rpd": rate_limits.rpd,
            "display": rate_limits.display_summary,
        },
        "optimizer": optimizer_rec,
        "token_method": "tiktoken" if is_tiktoken_available() else "heuristic",
    }


# ---------------- Module Exports ---------------- #

__all__ = [
    # Constants
    "DEFAULT_CHUNK_MODE",
    "DEFAULT_MAX_LINES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "DEFAULT_RPM",
    "DEFAULT_TPM",
    "DEFAULT_RPD",
    "ERROR_THRESHOLD_WARNING",
    "ERROR_THRESHOLD_REDUCE",
    # View Classes
    "ChunkModeView",
    "ChunkConfigView",
    "ChunkResultView",
    "RateLimitView",
    "TimeEstimateView",
    "OptimizerStatsView",
    # Token Functions
    "count_tokens",
    "count_tokens_batch",
    "is_tiktoken_available",
    # Chunking Functions
    "get_chunk_modes",
    "create_chunk_config",
    "chunk_lines",
    "estimate_chunks",
    # Rate Limiting Functions
    "get_model_rate_limits",
    "get_all_model_limits",
    "estimate_rate_limit_time",
    "estimate_time_for_model",
    # Optimizer Functions
    "create_optimizer_stats",
    "get_adaptive_chunk_size",
    "get_optimizer_recommendation",
    # Combined Functions
    "estimate_translation_job",
]
