"""Retry Handler for failed translation batches.

This module provides multiple strategies for handling failed translations:
- BATCH: Retry failed lines in smaller batches (default, current behavior)
- CONTEXTUAL: Include surrounding successfully-translated lines as context
- ISOLATED: Translate single lines with minimal prompt
- SKIP: Mark line as failed and continue, report at end

Example:
    >>> handler = RetryHandler(strategy=RetryStrategy.CONTEXTUAL)
    >>> handler.handle_failed_lines(failed_indices, original_lines, translations, translate_fn)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging


class RetryStrategy(Enum):
    """Available retry strategies for failed translations."""
    
    BATCH = "batch"           # Retry in smaller batches with emphasis
    CONTEXTUAL = "contextual" # Include surrounding context
    ISOLATED = "isolated"     # Single line with minimal prompt
    SKIP = "skip"             # Skip and log, continue processing


@dataclass
class RetryConfig:
    """Configuration for retry handling.
    
    Attributes:
        strategy: The retry strategy to use.
        max_retries_per_line: Maximum retries before giving up on a line.
        context_lines: Number of surrounding lines for contextual retry.
        fallback_strategy: Strategy to use after max retries exhausted.
        batch_size_reduction: Factor to reduce batch size for batch retry (0.5 = halve).
        min_batch_size: Minimum batch size for batch retry.
    """
    strategy: RetryStrategy = RetryStrategy.BATCH
    max_retries_per_line: int = 3
    context_lines: int = 2
    fallback_strategy: RetryStrategy = RetryStrategy.SKIP
    batch_size_reduction: float = 0.5
    min_batch_size: int = 1


@dataclass
class RetryResult:
    """Result of a retry attempt.
    
    Attributes:
        line_index: Original index of the line in the batch.
        success: Whether the retry was successful.
        translation: The translated text (or original if failed).
        attempts: Number of retry attempts made.
        strategy_used: The strategy that was used.
        error_message: Error message if failed.
    """
    line_index: int
    success: bool
    translation: str
    attempts: int = 1
    strategy_used: RetryStrategy = RetryStrategy.BATCH
    error_message: Optional[str] = None


@dataclass
class BatchRetryResult:
    """Result of retrying a batch of failed lines.
    
    Attributes:
        successful_count: Number of lines successfully retried.
        failed_count: Number of lines that still failed.
        skipped_count: Number of lines skipped.
        line_results: Individual results for each line.
        total_attempts: Total retry attempts made.
    """
    successful_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    line_results: List[RetryResult] = field(default_factory=list)
    total_attempts: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of retries."""
        total = self.successful_count + self.failed_count + self.skipped_count
        if total == 0:
            return 1.0
        return self.successful_count / total


# Type alias for translate function
TranslateFn = Callable[[List[str], Optional[str]], List[str]]


class RetryHandler:
    """Handles retry logic for failed translation lines.
    
    Provides multiple strategies for retrying failed translations with
    configurable behavior and fallback options.
    
    Example:
        >>> handler = RetryHandler(RetryConfig(strategy=RetryStrategy.CONTEXTUAL))
        >>> result = handler.handle_failed_lines(
        ...     failed_indices=[2, 5],
        ...     original_lines=["line1", "line2", "line3", "line4", "line5", "line6"],
        ...     translations=["trans1", "trans2", "", "trans4", "trans5", ""],
        ...     translate_fn=my_translate_function
        ... )
    """
    
    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        """Initialize retry handler.
        
        Args:
            config: Configuration for retry behavior. Uses defaults if None.
        """
        self.config = config or RetryConfig()
        self.logger = logging.getLogger("cherryai.retry")
        self._retry_counts: Dict[int, int] = {}  # Track retries per line index
    
    def handle_failed_lines(
        self,
        failed_indices: List[int],
        original_lines: List[str],
        translations: List[str],
        translate_fn: TranslateFn,
        system_prompt: Optional[str] = None,
    ) -> BatchRetryResult:
        """Handle a batch of failed translation lines.
        
        Args:
            failed_indices: Indices of lines that need retry.
            original_lines: All original source lines.
            translations: Current translations (may have empty/failed entries).
            translate_fn: Function to call for translation.
            system_prompt: Optional system prompt for translation.
            
        Returns:
            BatchRetryResult with retry outcomes.
        """
        if not failed_indices:
            return BatchRetryResult()
        
        self.logger.info(
            f"Retrying {len(failed_indices)} failed lines with strategy: {self.config.strategy.value}"
        )
        
        # Dispatch to appropriate strategy
        if self.config.strategy == RetryStrategy.BATCH:
            return self._retry_batch(
                failed_indices, original_lines, translations, translate_fn, system_prompt
            )
        elif self.config.strategy == RetryStrategy.CONTEXTUAL:
            return self._retry_contextual(
                failed_indices, original_lines, translations, translate_fn, system_prompt
            )
        elif self.config.strategy == RetryStrategy.ISOLATED:
            return self._retry_isolated(
                failed_indices, original_lines, translations, translate_fn, system_prompt
            )
        elif self.config.strategy == RetryStrategy.SKIP:
            return self._retry_skip(failed_indices, original_lines, translations)
        else:
            self.logger.warning(f"Unknown strategy: {self.config.strategy}, falling back to BATCH")
            return self._retry_batch(
                failed_indices, original_lines, translations, translate_fn, system_prompt
            )
    
    def _retry_batch(
        self,
        failed_indices: List[int],
        original_lines: List[str],
        translations: List[str],
        translate_fn: TranslateFn,
        system_prompt: Optional[str],
    ) -> BatchRetryResult:
        """Retry failed lines in smaller batches with emphasis prompt.
        
        This is the default strategy that reduces batch size and adds
        an emphasis note to the prompt.
        """
        result = BatchRetryResult()
        
        # Calculate reduced batch size
        current_batch_size = max(
            self.config.min_batch_size,
            int(len(failed_indices) * self.config.batch_size_reduction)
        )
        
        # Group failed indices into batches
        batches = self._chunk_list(failed_indices, current_batch_size)
        
        for batch_indices in batches:
            batch_lines = [original_lines[i] for i in batch_indices]
            
            # Add emphasis to system prompt for retry
            retry_prompt = system_prompt or ""
            retry_prompt += (
                "\n\nIMPORTANT: These lines previously failed translation. "
                "Please ensure accurate translation and preserve all placeholders."
            )
            
            try:
                batch_translations = translate_fn(batch_lines, retry_prompt)
                result.total_attempts += 1
                
                # Map results back to original indices
                for i, (idx, trans) in enumerate(zip(batch_indices, batch_translations)):
                    line_result = RetryResult(
                        line_index=idx,
                        success=bool(trans and trans.strip()),
                        translation=trans if trans else original_lines[idx],
                        attempts=self._get_retry_count(idx) + 1,
                        strategy_used=RetryStrategy.BATCH,
                    )
                    
                    if line_result.success:
                        result.successful_count += 1
                        translations[idx] = trans
                    else:
                        result.failed_count += 1
                        self._increment_retry_count(idx)
                        line_result.error_message = "Empty translation after retry"
                    
                    result.line_results.append(line_result)
                    
            except Exception as e:
                self.logger.error(f"Batch retry failed: {e}")
                result.total_attempts += 1
                
                # Mark all lines in batch as failed
                for idx in batch_indices:
                    result.line_results.append(RetryResult(
                        line_index=idx,
                        success=False,
                        translation=original_lines[idx],
                        attempts=self._get_retry_count(idx) + 1,
                        strategy_used=RetryStrategy.BATCH,
                        error_message=str(e),
                    ))
                    result.failed_count += 1
                    self._increment_retry_count(idx)
        
        return result
    
    def _retry_contextual(
        self,
        failed_indices: List[int],
        original_lines: List[str],
        translations: List[str],
        translate_fn: TranslateFn,
        system_prompt: Optional[str],
    ) -> BatchRetryResult:
        """Retry with surrounding successfully-translated lines as context.
        
        Includes context_lines lines before and after the failed line,
        using already-translated versions for context.
        """
        result = BatchRetryResult()
        
        for idx in failed_indices:
            context_before = []
            context_after = []
            
            # Build context from surrounding lines
            for i in range(max(0, idx - self.config.context_lines), idx):
                if translations[i] and translations[i].strip():
                    context_before.append(f"[CONTEXT] {translations[i]}")
            
            for i in range(idx + 1, min(len(original_lines), idx + self.config.context_lines + 1)):
                if translations[i] and translations[i].strip():
                    context_after.append(f"[CONTEXT] {translations[i]}")
            
            # Build prompt with context
            retry_prompt = system_prompt or ""
            if context_before or context_after:
                retry_prompt += "\n\nContext (already translated):\n"
                if context_before:
                    retry_prompt += "\n".join(context_before) + "\n"
                retry_prompt += "[TRANSLATE THIS LINE]\n"
                if context_after:
                    retry_prompt += "\n".join(context_after)
            
            retry_prompt += "\n\nTranslate only the marked line, not the context."
            
            try:
                # Translate single line with context prompt
                batch_result = translate_fn([original_lines[idx]], retry_prompt)
                result.total_attempts += 1
                
                trans = batch_result[0] if batch_result else ""
                line_result = RetryResult(
                    line_index=idx,
                    success=bool(trans and trans.strip()),
                    translation=trans if trans else original_lines[idx],
                    attempts=self._get_retry_count(idx) + 1,
                    strategy_used=RetryStrategy.CONTEXTUAL,
                )
                
                if line_result.success:
                    result.successful_count += 1
                    translations[idx] = trans
                else:
                    result.failed_count += 1
                    self._increment_retry_count(idx)
                    line_result.error_message = "Empty translation after contextual retry"
                
                result.line_results.append(line_result)
                
            except Exception as e:
                self.logger.error(f"Contextual retry failed for line {idx}: {e}")
                result.total_attempts += 1
                result.line_results.append(RetryResult(
                    line_index=idx,
                    success=False,
                    translation=original_lines[idx],
                    attempts=self._get_retry_count(idx) + 1,
                    strategy_used=RetryStrategy.CONTEXTUAL,
                    error_message=str(e),
                ))
                result.failed_count += 1
                self._increment_retry_count(idx)
        
        return result
    
    def _retry_isolated(
        self,
        failed_indices: List[int],
        original_lines: List[str],
        translations: List[str],
        translate_fn: TranslateFn,
        system_prompt: Optional[str],
    ) -> BatchRetryResult:
        """Retry each line individually with minimal prompt.
        
        Uses a simple, focused prompt for single-line translation.
        Faster and cheaper but may have less quality.
        """
        result = BatchRetryResult()
        
        for idx in failed_indices:
            # Minimal prompt for isolated translation
            minimal_prompt = (
                "Translate this single line. "
                "Preserve all __PROT__ and similar tokens exactly."
            )
            
            try:
                batch_result = translate_fn([original_lines[idx]], minimal_prompt)
                result.total_attempts += 1
                
                trans = batch_result[0] if batch_result else ""
                line_result = RetryResult(
                    line_index=idx,
                    success=bool(trans and trans.strip()),
                    translation=trans if trans else original_lines[idx],
                    attempts=self._get_retry_count(idx) + 1,
                    strategy_used=RetryStrategy.ISOLATED,
                )
                
                if line_result.success:
                    result.successful_count += 1
                    translations[idx] = trans
                else:
                    result.failed_count += 1
                    self._increment_retry_count(idx)
                    line_result.error_message = "Empty translation after isolated retry"
                
                result.line_results.append(line_result)
                
            except Exception as e:
                self.logger.error(f"Isolated retry failed for line {idx}: {e}")
                result.total_attempts += 1
                result.line_results.append(RetryResult(
                    line_index=idx,
                    success=False,
                    translation=original_lines[idx],
                    attempts=self._get_retry_count(idx) + 1,
                    strategy_used=RetryStrategy.ISOLATED,
                    error_message=str(e),
                ))
                result.failed_count += 1
                self._increment_retry_count(idx)
        
        return result
    
    def _retry_skip(
        self,
        failed_indices: List[int],
        original_lines: List[str],
        translations: List[str],
    ) -> BatchRetryResult:
        """Skip failed lines and log them for later review.
        
        Does not attempt to retry - just marks lines as skipped
        and preserves the original text.
        """
        result = BatchRetryResult()
        
        for idx in failed_indices:
            self.logger.warning(f"Skipping failed line {idx}: {original_lines[idx][:50]}...")
            
            result.line_results.append(RetryResult(
                line_index=idx,
                success=False,
                translation=original_lines[idx],  # Keep original
                attempts=0,
                strategy_used=RetryStrategy.SKIP,
                error_message="Line skipped per retry strategy",
            ))
            result.skipped_count += 1
        
        return result
    
    def _chunk_list(self, items: List[Any], chunk_size: int) -> List[List[Any]]:
        """Split a list into chunks of specified size."""
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    
    def _get_retry_count(self, line_index: int) -> int:
        """Get current retry count for a line."""
        return self._retry_counts.get(line_index, 0)
    
    def _increment_retry_count(self, line_index: int) -> None:
        """Increment retry count for a line."""
        self._retry_counts[line_index] = self._retry_counts.get(line_index, 0) + 1
    
    def reset_retry_counts(self) -> None:
        """Reset all retry counts (e.g., for new batch)."""
        self._retry_counts.clear()
    
    def should_continue_retrying(self, line_index: int) -> bool:
        """Check if a line should continue to be retried.
        
        Args:
            line_index: The line index to check.
            
        Returns:
            True if retries should continue, False if max reached.
        """
        return self._get_retry_count(line_index) < self.config.max_retries_per_line
    
    def get_exhausted_lines(self, failed_indices: List[int]) -> List[int]:
        """Get lines that have exhausted their retry attempts.
        
        Args:
            failed_indices: List of failed line indices.
            
        Returns:
            List of indices that have reached max retries.
        """
        return [
            idx for idx in failed_indices 
            if not self.should_continue_retrying(idx)
        ]


def create_retry_handler(
    strategy: str = "batch",
    max_retries: int = 3,
    context_lines: int = 2,
) -> RetryHandler:
    """Factory function to create a retry handler.
    
    Args:
        strategy: Strategy name: "batch", "contextual", "isolated", "skip"
        max_retries: Maximum retries per line.
        context_lines: Context lines for contextual strategy.
        
    Returns:
        Configured RetryHandler instance.
    """
    strategy_map = {
        "batch": RetryStrategy.BATCH,
        "contextual": RetryStrategy.CONTEXTUAL,
        "isolated": RetryStrategy.ISOLATED,
        "skip": RetryStrategy.SKIP,
    }
    
    retry_strategy = strategy_map.get(strategy.lower(), RetryStrategy.BATCH)
    
    config = RetryConfig(
        strategy=retry_strategy,
        max_retries_per_line=max_retries,
        context_lines=context_lines,
    )
    
    return RetryHandler(config)


def parse_retry_strategy_arg(arg: str) -> RetryStrategy:
    """Parse a retry strategy from CLI argument.
    
    Args:
        arg: Strategy name from command line.
        
    Returns:
        RetryStrategy enum value.
        
    Raises:
        ValueError: If strategy name is not recognized.
    """
    arg_lower = arg.lower().strip()
    strategy_map = {
        "batch": RetryStrategy.BATCH,
        "contextual": RetryStrategy.CONTEXTUAL,
        "context": RetryStrategy.CONTEXTUAL,  # Alias
        "isolated": RetryStrategy.ISOLATED,
        "single": RetryStrategy.ISOLATED,  # Alias
        "skip": RetryStrategy.SKIP,
        "none": RetryStrategy.SKIP,  # Alias
    }
    
    if arg_lower in strategy_map:
        return strategy_map[arg_lower]
    
    valid = ", ".join(sorted(set(strategy_map.keys())))
    raise ValueError(f"Unknown retry strategy '{arg}'. Valid options: {valid}")


def list_retry_strategies() -> List[str]:
    """List available retry strategy names.
    
    Returns:
        List of strategy names that can be used.
    """
    return [s.value for s in RetryStrategy]


def get_strategy_description(strategy: RetryStrategy) -> str:
    """Get a description of a retry strategy.
    
    Args:
        strategy: The strategy to describe.
        
    Returns:
        Human-readable description.
    """
    descriptions = {
        RetryStrategy.BATCH: (
            "Retry failed lines in smaller batches with emphasis prompt. "
            "Default behavior, balances quality and cost."
        ),
        RetryStrategy.CONTEXTUAL: (
            "Include surrounding successfully-translated lines as context. "
            "May improve quality for context-dependent text."
        ),
        RetryStrategy.ISOLATED: (
            "Translate single lines with minimal prompt. "
            "Faster and cheaper but may have less quality."
        ),
        RetryStrategy.SKIP: (
            "Skip failed lines and continue. "
            "Preserves original text, logs failures for review."
        ),
    }
    return descriptions.get(strategy, "Unknown strategy")
