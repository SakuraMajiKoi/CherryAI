"""Adaptive chunk sizing for translation batches.

Automatically adjusts chunk size based on error rates during translation.
Reduces chunk size when errors are frequent, resets when stable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ErrorType(Enum):
    """Types of errors tracked for chunk optimization."""
    EMPTY_RESPONSE = "empty_response"      # API returned empty or no content
    RETRY_NEEDED = "retry_needed"          # Batch required full retry
    TIMEOUT = "timeout"                     # API request timed out
    VALIDATION_FAILED = "validation_failed" # Post-validation failed
    RATE_LIMIT = "rate_limit"              # Rate limit hit


@dataclass
class OptimizerConfig:
    """Configuration for chunk size optimizer.
    
    Attributes:
        error_threshold: Error rate (0.0-1.0) that triggers reduction.
        min_requests_before_adjust: Minimum requests before evaluating.
        reduction_factor: Factor to multiply chunk size by on reduction (0.5-0.99).
        min_chunk_size: Minimum chunk size floor.
        success_streak_to_reset: Consecutive successes needed to reset.
        initial_chunk_size: Starting chunk size.
        max_chunk_size: Maximum chunk size (for reset).
    """
    error_threshold: float = 0.20  # 20% error rate triggers reduction
    min_requests_before_adjust: int = 7
    reduction_factor: float = 0.75  # Reduce by 25%
    min_chunk_size: int = 10
    success_streak_to_reset: int = 10
    initial_chunk_size: int = 50
    max_chunk_size: int = 200


@dataclass
class BatchResult:
    """Result of a single batch translation.
    
    Attributes:
        success: Whether the batch succeeded without issues.
        error_type: Type of error if any.
        chunk_size: Chunk size used for this batch.
        lines_translated: Number of lines successfully translated.
        retries_used: Number of retries used for this batch.
    """
    success: bool
    error_type: Optional[ErrorType] = None
    chunk_size: int = 0
    lines_translated: int = 0
    retries_used: int = 0


@dataclass 
class OptimizerStats:
    """Statistics for the optimizer session.
    
    Attributes:
        total_batches: Total number of batches processed.
        successful_batches: Number of fully successful batches.
        failed_batches: Number of batches with errors.
        total_errors: Total error count.
        errors_by_type: Count of each error type.
        adjustments_made: Number of chunk size reductions.
        current_chunk_size: Current effective chunk size.
        success_streak: Current consecutive successes.
        history: List of batch results.
    """
    total_batches: int = 0
    successful_batches: int = 0
    failed_batches: int = 0
    total_errors: int = 0
    errors_by_type: dict = field(default_factory=dict)
    adjustments_made: int = 0
    current_chunk_size: int = 50
    success_streak: int = 0
    history: List[BatchResult] = field(default_factory=list)


class ChunkOptimizer:
    """Adaptively adjusts chunk size based on error rates.
    
    The optimizer tracks batch results and automatically reduces chunk size
    when the error rate exceeds a threshold. It also resets to the initial
    size after a streak of successful batches.
    
    Example usage:
        optimizer = ChunkOptimizer(OptimizerConfig(initial_chunk_size=50))
        
        for batch in batches:
            chunk_size = optimizer.get_chunk_size()
            result = translate_batch(batch[:chunk_size])
            optimizer.record_batch(BatchResult(success=result.ok))
    """

    def __init__(self, config: Optional[OptimizerConfig] = None) -> None:
        """Initialize the chunk optimizer.
        
        Args:
            config: Optimizer configuration. Uses defaults if not provided.
        """
        self.config = config or OptimizerConfig()
        self.logger = logging.getLogger(__name__)
        self._stats = OptimizerStats(
            current_chunk_size=self.config.initial_chunk_size
        )

    def get_chunk_size(self) -> int:
        """Get the current recommended chunk size.
        
        Returns:
            Current chunk size to use.
        """
        return self._stats.current_chunk_size

    def record_batch(self, result: BatchResult) -> None:
        """Record the result of a batch translation.
        
        This updates statistics and may trigger chunk size adjustments.
        
        Args:
            result: Result of the batch translation.
        """
        self._stats.total_batches += 1
        self._stats.history.append(result)
        
        if result.success:
            self._stats.successful_batches += 1
            self._stats.success_streak += 1
            self._check_reset()
        else:
            self._stats.failed_batches += 1
            self._stats.total_errors += 1
            self._stats.success_streak = 0
            
            if result.error_type:
                error_key = result.error_type.value
                self._stats.errors_by_type[error_key] = \
                    self._stats.errors_by_type.get(error_key, 0) + 1
            
            self._check_adjustment()

    def record_success(self) -> None:
        """Record a successful batch (convenience method)."""
        self.record_batch(BatchResult(success=True))

    def record_error(self, error_type: ErrorType) -> None:
        """Record a failed batch with specific error type.
        
        Args:
            error_type: The type of error that occurred.
        """
        self.record_batch(BatchResult(success=False, error_type=error_type))

    def _check_adjustment(self) -> None:
        """Check if chunk size should be reduced based on error rate."""
        if self._stats.total_batches < self.config.min_requests_before_adjust:
            return  # Not enough data yet
        
        error_rate = self._stats.total_errors / self._stats.total_batches
        
        if error_rate >= self.config.error_threshold:
            self._reduce_chunk_size()

    def _reduce_chunk_size(self) -> None:
        """Reduce chunk size by the configured factor."""
        old_size = self._stats.current_chunk_size
        new_size = int(old_size * self.config.reduction_factor)
        
        # Apply minimum floor
        new_size = max(new_size, self.config.min_chunk_size)
        
        if new_size < old_size:
            self._stats.current_chunk_size = new_size
            self._stats.adjustments_made += 1
            self.logger.info(
                f"Chunk size reduced: {old_size} → {new_size} "
                f"(error rate: {self._stats.total_errors}/{self._stats.total_batches})"
            )

    def _check_reset(self) -> None:
        """Check if chunk size should be reset after success streak."""
        if self._stats.success_streak >= self.config.success_streak_to_reset:
            self._reset_chunk_size()

    def _reset_chunk_size(self) -> None:
        """Reset chunk size to initial value after sustained success."""
        old_size = self._stats.current_chunk_size
        initial = self.config.initial_chunk_size
        
        if old_size < initial:
            self._stats.current_chunk_size = initial
            self._stats.success_streak = 0  # Reset streak counter
            self.logger.info(
                f"Chunk size reset: {old_size} → {initial} "
                f"(success streak: {self.config.success_streak_to_reset})"
            )

    def get_stats(self) -> OptimizerStats:
        """Get current optimizer statistics.
        
        Returns:
            Copy of current statistics.
        """
        return OptimizerStats(
            total_batches=self._stats.total_batches,
            successful_batches=self._stats.successful_batches,
            failed_batches=self._stats.failed_batches,
            total_errors=self._stats.total_errors,
            errors_by_type=dict(self._stats.errors_by_type),
            adjustments_made=self._stats.adjustments_made,
            current_chunk_size=self._stats.current_chunk_size,
            success_streak=self._stats.success_streak,
            history=list(self._stats.history),
        )

    def get_error_rate(self) -> float:
        """Get current error rate.
        
        Returns:
            Error rate (0.0-1.0), or 0.0 if no batches processed.
        """
        if self._stats.total_batches == 0:
            return 0.0
        return self._stats.total_errors / self._stats.total_batches

    def get_success_rate(self) -> float:
        """Get current success rate.
        
        Returns:
            Success rate (0.0-1.0), or 1.0 if no batches processed.
        """
        if self._stats.total_batches == 0:
            return 1.0
        return self._stats.successful_batches / self._stats.total_batches

    def reset(self) -> None:
        """Reset optimizer to initial state."""
        self._stats = OptimizerStats(
            current_chunk_size=self.config.initial_chunk_size
        )
        self.logger.debug("Optimizer reset to initial state")

    def should_adjust(self) -> bool:
        """Check if conditions are met for potential adjustment.
        
        Returns:
            True if enough data collected and error rate is high.
        """
        if self._stats.total_batches < self.config.min_requests_before_adjust:
            return False
        return self.get_error_rate() >= self.config.error_threshold

    def get_summary(self) -> str:
        """Get a human-readable summary of optimizer state.
        
        Returns:
            Summary string.
        """
        stats = self._stats
        lines = [
            f"Chunk Size: {stats.current_chunk_size}",
            f"Batches: {stats.total_batches} ({stats.successful_batches} ok, {stats.failed_batches} failed)",
            f"Error Rate: {self.get_error_rate():.1%}",
            f"Success Streak: {stats.success_streak}",
            f"Adjustments: {stats.adjustments_made}",
        ]
        return " | ".join(lines)


def create_optimizer(
    initial_chunk_size: int = 50,
    error_threshold: float = 0.20,
    min_chunk_size: int = 10,
    reduction_factor: float = 0.75,
    success_streak_to_reset: int = 10,
    min_requests_before_adjust: int = 7,
) -> ChunkOptimizer:
    """Factory function to create a ChunkOptimizer with simplified arguments.
    
    Args:
        initial_chunk_size: Starting chunk size.
        error_threshold: Error rate (0.0-1.0) that triggers reduction.
        min_chunk_size: Minimum chunk size floor.
        reduction_factor: Factor to multiply chunk size by on reduction.
        success_streak_to_reset: Consecutive successes needed to reset.
        min_requests_before_adjust: Minimum requests before evaluating error rate.
        
    Returns:
        Configured ChunkOptimizer instance.
    """
    config = OptimizerConfig(
        initial_chunk_size=initial_chunk_size,
        error_threshold=error_threshold,
        min_chunk_size=min_chunk_size,
        reduction_factor=reduction_factor,
        success_streak_to_reset=success_streak_to_reset,
        min_requests_before_adjust=min_requests_before_adjust,
    )
    return ChunkOptimizer(config)
