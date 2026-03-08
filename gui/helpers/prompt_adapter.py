"""Prompt builder adapter for GUI integration.

This module bridges the GUI translation step (gui/steps/translate.py) with the
core prompt functions in functions/prompt_builder.py, functions/conditional_prompts.py,
and functions/retry_handler.py.

Purpose:
- Provides clean function signatures for GUI use
- Wraps core prompt functions with fallback implementations
- Integrates retry handling for failed translations
- Exposes conditional prompts for configuration

TASK 16.9: Integrates functions/prompt_builder.py, functions/conditional_prompts.py,
and functions/retry_handler.py with GUI Step 6 (Translation)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------- Imports from functions/prompt_builder.py ---------------- #

_PromptBuilder = None
_RequestBatch = None
_RollingContextConfig = None
_StrippedQuoteInfo = None
_QuoteStrippingResult = None
_strip_speaker_quotes = None
_restore_speaker_quotes = None
_load_translation_style = None
_format_style_for_prompt = None
_format_rolling_context = None
_load_game_summary = None
_format_summary_for_prompt = None
_MAX_STYLE_CHARS = 2000

try:
    from CherryAI.functions.prompt_builder import (
        PromptBuilder,
        RequestBatch,
        RollingContextConfig,
        StrippedQuoteInfo,
        QuoteStrippingResult,
        strip_speaker_quotes,
        restore_speaker_quotes,
        load_translation_style,
        format_style_for_prompt,
        format_rolling_context,
        load_game_summary,
        format_summary_for_prompt,
        MAX_STYLE_CHARS,
    )
    _PromptBuilder = PromptBuilder
    _RequestBatch = RequestBatch
    _RollingContextConfig = RollingContextConfig
    _StrippedQuoteInfo = StrippedQuoteInfo
    _QuoteStrippingResult = QuoteStrippingResult
    _strip_speaker_quotes = strip_speaker_quotes
    _restore_speaker_quotes = restore_speaker_quotes
    _load_translation_style = load_translation_style
    _format_style_for_prompt = format_style_for_prompt
    _format_rolling_context = format_rolling_context
    _load_game_summary = load_game_summary
    _format_summary_for_prompt = format_summary_for_prompt
    _MAX_STYLE_CHARS = MAX_STYLE_CHARS
except ImportError:
    try:
        from CherryAI.functions.prompt_builder import (
            PromptBuilder,
            RequestBatch,
            RollingContextConfig,
            StrippedQuoteInfo,
            QuoteStrippingResult,
            strip_speaker_quotes,
            restore_speaker_quotes,
            load_translation_style,
            format_style_for_prompt,
            format_rolling_context,
            load_game_summary,
            format_summary_for_prompt,
            MAX_STYLE_CHARS,
        )
        _PromptBuilder = PromptBuilder
        _RequestBatch = RequestBatch
        _RollingContextConfig = RollingContextConfig
        _StrippedQuoteInfo = StrippedQuoteInfo
        _QuoteStrippingResult = QuoteStrippingResult
        _strip_speaker_quotes = strip_speaker_quotes
        _restore_speaker_quotes = restore_speaker_quotes
        _load_translation_style = load_translation_style
        _format_style_for_prompt = format_style_for_prompt
        _format_rolling_context = format_rolling_context
        _load_game_summary = load_game_summary
        _format_summary_for_prompt = format_summary_for_prompt
        _MAX_STYLE_CHARS = MAX_STYLE_CHARS
    except ImportError:
        logger.debug("Could not import functions.prompt_builder")


# ---------------- Imports from functions/conditional_prompts.py ---------------- #

_ConditionalPrompt = None
_ConditionalPromptManager = None
_BUILTIN_CONDITIONS = None

try:
    from CherryAI.functions.conditional_prompts import (
        ConditionalPrompt,
        ConditionalPromptManager,
        BUILTIN_CONDITIONS,
    )
    _ConditionalPrompt = ConditionalPrompt
    _ConditionalPromptManager = ConditionalPromptManager
    _BUILTIN_CONDITIONS = BUILTIN_CONDITIONS
except ImportError:
    try:
        from CherryAI.functions.conditional_prompts import (
            ConditionalPrompt,
            ConditionalPromptManager,
            BUILTIN_CONDITIONS,
        )
        _ConditionalPrompt = ConditionalPrompt
        _ConditionalPromptManager = ConditionalPromptManager
        _BUILTIN_CONDITIONS = BUILTIN_CONDITIONS
    except ImportError:
        logger.debug("Could not import functions.conditional_prompts")


# ---------------- Imports from functions/retry_handler.py ---------------- #

_RetryStrategy = None
_RetryConfig = None
_RetryResult = None
_BatchRetryResult = None
_RetryHandler = None
_create_retry_handler = None
_list_retry_strategies = None
_get_strategy_description = None

try:
    from CherryAI.functions.retry_handler import (
        RetryStrategy,
        RetryConfig,
        RetryResult,
        BatchRetryResult,
        RetryHandler,
        create_retry_handler,
        list_retry_strategies,
        get_strategy_description,
    )
    _RetryStrategy = RetryStrategy
    _RetryConfig = RetryConfig
    _RetryResult = RetryResult
    _BatchRetryResult = BatchRetryResult
    _RetryHandler = RetryHandler
    _create_retry_handler = create_retry_handler
    _list_retry_strategies = list_retry_strategies
    _get_strategy_description = get_strategy_description
except ImportError:
    try:
        from CherryAI.functions.retry_handler import (
            RetryStrategy,
            RetryConfig,
            RetryResult,
            BatchRetryResult,
            RetryHandler,
            create_retry_handler,
            list_retry_strategies,
            get_strategy_description,
        )
        _RetryStrategy = RetryStrategy
        _RetryConfig = RetryConfig
        _RetryResult = RetryResult
        _BatchRetryResult = BatchRetryResult
        _RetryHandler = RetryHandler
        _create_retry_handler = create_retry_handler
        _list_retry_strategies = list_retry_strategies
        _get_strategy_description = get_strategy_description
    except ImportError:
        logger.debug("Could not import functions.retry_handler")


# ---------------- Imports from functions/analysis.py (Task 75) ---------------- #

_format_protagonist_prompt = None
_POVResult = None

try:
    from CherryAI.functions.analysis import format_protagonist_prompt, POVResult

    _format_protagonist_prompt = format_protagonist_prompt
    _POVResult = POVResult
except ImportError:
    try:
        from functions.analysis import format_protagonist_prompt, POVResult

        _format_protagonist_prompt = format_protagonist_prompt
        _POVResult = POVResult
    except ImportError:
        logger.debug("Could not import functions.analysis protagonist helpers")


# ---------------- Constants ---------------- #

# Default prompt settings
DEFAULT_ROLLING_CONTEXT_LINES = 3
DEFAULT_MAX_BATCH_SIZE = 50
DEFAULT_MIN_BATCH_SIZE = 10
DEFAULT_MAX_STYLE_CHARS = 2000

# Retry strategy defaults
DEFAULT_RETRY_STRATEGY = "batch"
DEFAULT_MAX_RETRIES = 3
DEFAULT_CONTEXT_LINES = 2


# ---------------- View Classes (GUI-Friendly) ---------------- #


class RetryStrategyView(str, Enum):
    """Retry strategy options for GUI display."""

    BATCH = "batch"
    CONTEXTUAL = "contextual"
    ISOLATED = "isolated"
    SKIP = "skip"

    @property
    def display_name(self) -> str:
        """Get human-readable name for GUI display."""
        names = {
            "batch": "Batch (retry whole chunk)",
            "contextual": "Contextual (retry with context)",
            "isolated": "Isolated (retry line-by-line)",
            "skip": "Skip (mark failed and continue)",
        }
        return names.get(self.value, self.value)

    @property
    def description(self) -> str:
        """Get description for tooltips."""
        descriptions = {
            "batch": (
                "Retry failed lines in smaller batches with emphasis prompt. "
                "Default behavior, balances quality and cost."
            ),
            "contextual": (
                "Include surrounding successfully-translated lines as context. "
                "May improve quality for context-dependent text."
            ),
            "isolated": (
                "Translate single lines with minimal prompt. "
                "Faster and cheaper but may have less quality."
            ),
            "skip": (
                "Skip failed lines and continue. "
                "Preserves original text, logs failures for review."
            ),
        }
        return descriptions.get(self.value, "")


@dataclass
class ConditionalPromptView:
    """GUI-friendly view of a conditional prompt."""

    name: str
    description: str
    patterns: List[str]
    instruction: str
    priority: int
    enabled: bool
    category: str

    @property
    def display_patterns(self) -> str:
        """Get patterns as a formatted string."""
        return ", ".join(self.patterns[:3])
        if len(self.patterns) > 3:
            return f"{', '.join(self.patterns[:3])}..."
        return ", ".join(self.patterns)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "description": self.description,
            "patterns": self.patterns,
            "instruction": self.instruction,
            "priority": self.priority,
            "enabled": self.enabled,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConditionalPromptView":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            patterns=data.get("patterns", []),
            instruction=data.get("instruction", ""),
            priority=int(data.get("priority", 50)),
            enabled=bool(data.get("enabled", True)),
            category=data.get("category", "general"),
        )


@dataclass
class PromptPreviewView:
    """GUI-friendly view of prompt preview."""

    system_prompt: str
    game_summary: str
    glossary_section: str
    style_section: str
    conditional_section: str
    total_tokens: int
    breakdown: Dict[str, int]

    @property
    def has_content(self) -> bool:
        """Check if prompt has meaningful content."""
        return bool(self.system_prompt.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "system_prompt": self.system_prompt,
            "game_summary": self.game_summary,
            "glossary_section": self.glossary_section,
            "style_section": self.style_section,
            "conditional_section": self.conditional_section,
            "total_tokens": self.total_tokens,
            "breakdown": self.breakdown,
        }


@dataclass
class RollingContextView:
    """GUI-friendly view of rolling context configuration."""

    enabled: bool = True
    lines_before: int = DEFAULT_ROLLING_CONTEXT_LINES
    lines_between: int = 0
    lines_after: int = 0
    scene_markers: List[str] = field(default_factory=lambda: ["=====", "-----", "***"])
    use_translated: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "lines_before": self.lines_before,
            "lines_between": self.lines_between,
            "lines_after": self.lines_after,
            "scene_markers": self.scene_markers,
            "use_translated": self.use_translated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RollingContextView":
        """Create from dictionary."""
        return cls(
            enabled=bool(data.get("enabled", True)),
            lines_before=int(data.get("lines_before", DEFAULT_ROLLING_CONTEXT_LINES)),
            lines_between=int(data.get("lines_between", 0)),
            lines_after=int(data.get("lines_after", 0)),
            scene_markers=data.get("scene_markers", ["=====", "-----", "***"]),
            use_translated=bool(data.get("use_translated", True)),
        )


@dataclass
class RetryConfigView:
    """GUI-friendly view of retry configuration."""

    strategy: str = DEFAULT_RETRY_STRATEGY
    max_retries: int = DEFAULT_MAX_RETRIES
    context_lines: int = DEFAULT_CONTEXT_LINES

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy": self.strategy,
            "max_retries": self.max_retries,
            "context_lines": self.context_lines,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryConfigView":
        """Create from dictionary."""
        return cls(
            strategy=data.get("strategy", DEFAULT_RETRY_STRATEGY),
            max_retries=int(data.get("max_retries", DEFAULT_MAX_RETRIES)),
            context_lines=int(data.get("context_lines", DEFAULT_CONTEXT_LINES)),
        )


@dataclass
class RetryResultView:
    """GUI-friendly view of retry result."""

    line_index: int
    success: bool
    translation: str
    attempts: int
    strategy_used: str
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "line_index": self.line_index,
            "success": self.success,
            "translation": self.translation,
            "attempts": self.attempts,
            "strategy_used": self.strategy_used,
            "error_message": self.error_message,
        }


@dataclass
class BatchRetryResultView:
    """GUI-friendly view of batch retry results."""

    successful_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    total_attempts: int = 0
    line_results: List[RetryResultView] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total lines processed."""
        return self.successful_count + self.failed_count + self.skipped_count

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_processed == 0:
            return 0.0
        return self.successful_count / self.total_processed * 100


# ---------------- Translation Style Functions ---------------- #


def get_translation_style(
    style_file: str = "",
    config_dir: Optional[Path] = None,
) -> Tuple[str, str]:
    """Load translation style from file.

    Args:
        style_file: Path to style file (relative or absolute).
        config_dir: Base config directory.

    Returns:
        Tuple of (style_text, method) where method is "core" or "fallback".
    """
    if _load_translation_style is not None:
        try:
            style = _load_translation_style(style_file, config_dir)
            return (style, "core")
        except Exception as e:
            logger.debug(f"Core load_translation_style failed: {e}")

    # Fallback implementation
    try:
        if config_dir:
            path = config_dir / style_file
        else:
            path = Path(style_file)
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            # Truncate if too long
            if len(content) > DEFAULT_MAX_STYLE_CHARS:
                content = content[:DEFAULT_MAX_STYLE_CHARS] + "..."
            return (content, "fallback")
    except Exception as e:
        logger.debug(f"Fallback style load failed: {e}")

    return ("", "fallback")


def format_style_section(style: str) -> str:
    """Format translation style for prompt.

    Args:
        style: Raw style text.

    Returns:
        Formatted style section for system prompt.
    """
    if _format_style_for_prompt is not None:
        try:
            return _format_style_for_prompt(style)
        except Exception as e:
            logger.debug(f"Core format_style_for_prompt failed: {e}")

    # Fallback
    if not style or not style.strip():
        return ""
    return f"\n\n# Translation Style Guidelines\n{style.strip()}"


def get_game_summary(
    summary_file: str = "",
) -> Tuple[str, str]:
    """Load game summary from file.

    Args:
        summary_file: Path to summary file.

    Returns:
        Tuple of (summary_text, method) where method is "core" or "fallback".
    """
    if _load_game_summary is not None:
        try:
            summary = _load_game_summary(summary_file)
            return (summary, "core")
        except Exception as e:
            logger.debug(f"Core load_game_summary failed: {e}")

    # Fallback
    try:
        path = Path(summary_file)
        if path.exists():
            return (path.read_text(encoding="utf-8").strip(), "fallback")
    except Exception as e:
        logger.debug(f"Fallback summary load failed: {e}")

    return ("", "fallback")


# ---------------- Quote Stripping Functions ---------------- #


def strip_quotes_from_lines(
    lines: List[str],
    start_index: int = 0,
) -> Tuple[List[str], List[Dict[str, Any]], str]:
    """Strip quotes from speaker lines to save tokens.

    Args:
        lines: Lines to process.
        start_index: Starting line index for mapping.

    Returns:
        Tuple of (stripped_lines, quote_info, method).
    """
    if _strip_speaker_quotes is not None:
        try:
            result = _strip_speaker_quotes(lines, start_index)
            # Convert to simple dict format for GUI
            info = []
            for qi in result.quote_info:
                info.append({
                    "line_index": qi.line_index,
                    "speaker_name": qi.speaker_name,
                    "colon_char": qi.colon_char,
                    "opening_quote": qi.opening_quote,
                    "closing_quote": qi.closing_quote,
                })
            return (result.stripped_lines, info, "core")
        except Exception as e:
            logger.debug(f"Core strip_speaker_quotes failed: {e}")

    # Fallback: no stripping
    return (lines[:], [], "fallback")


def restore_quotes_to_lines(
    translated_lines: List[str],
    quote_info: List[Dict[str, Any]],
    base_index: int = 0,
) -> Tuple[List[str], str]:
    """Restore quotes to translated lines.

    Args:
        translated_lines: Lines after translation.
        quote_info: Quote info from stripping.
        base_index: Base line index.

    Returns:
        Tuple of (restored_lines, method).
    """
    if not quote_info:
        return (translated_lines[:], "no-op")

    if _restore_speaker_quotes is not None and _StrippedQuoteInfo is not None:
        try:
            # Convert back to StrippedQuoteInfo objects
            info_objs = []
            for qi in quote_info:
                info_objs.append(_StrippedQuoteInfo(
                    line_index=qi["line_index"],
                    speaker_name=qi["speaker_name"],
                    colon_char=qi["colon_char"],
                    opening_quote=qi["opening_quote"],
                    closing_quote=qi["closing_quote"],
                ))
            restored = _restore_speaker_quotes(translated_lines, info_objs, base_index)
            return (restored, "core")
        except Exception as e:
            logger.debug(f"Core restore_speaker_quotes failed: {e}")

    # Fallback: return as-is
    return (translated_lines[:], "fallback")


# ---------------- Conditional Prompt Functions ---------------- #


def get_builtin_conditions() -> Tuple[List[ConditionalPromptView], str]:
    """Get list of built-in conditional prompts.

    Returns:
        Tuple of (conditions, method).
    """
    if _BUILTIN_CONDITIONS is not None:
        try:
            views = []
            for cond in _BUILTIN_CONDITIONS:
                views.append(ConditionalPromptView(
                    name=cond.name,
                    description=cond.description,
                    patterns=cond.patterns[:],
                    instruction=cond.instruction,
                    priority=cond.priority,
                    enabled=cond.enabled,
                    category=cond.category,
                ))
            return (views, "core")
        except Exception as e:
            logger.debug(f"Core get_builtin_conditions failed: {e}")

    # Fallback: return common patterns
    fallback = [
        ConditionalPromptView(
            name="protected_tokens",
            description="Protection tokens (__PROTECTED_N__)",
            patterns=[r"__PROTECTED_\d+__"],
            instruction="Preserve __PROTECTED_N__ tokens exactly.",
            priority=100,
            enabled=True,
            category="code",
        ),
        ConditionalPromptView(
            name="dedup_tokens",
            description="Deduplication tokens (__DEDUP_N__)",
            patterns=[r"__DEDUP_\d+__"],
            instruction="Preserve __DEDUP_N__ tokens exactly.",
            priority=95,
            enabled=True,
            category="code",
        ),
        ConditionalPromptView(
            name="brackets",
            description="Square brackets with content",
            patterns=[r"\[[^\]]+\]"],
            instruction="Preserve brackets and content exactly.",
            priority=80,
            enabled=True,
            category="code",
        ),
    ]
    return (fallback, "fallback")


def evaluate_conditions_for_batch(
    lines: List[str],
    config_dir: Optional[Path] = None,
) -> Tuple[List[Tuple[ConditionalPromptView, Set[str]]], str]:
    """Evaluate which conditions match a batch of lines.

    Args:
        lines: Lines to evaluate.
        config_dir: Config directory for loading conditions.

    Returns:
        Tuple of (matches, method) where matches is list of (condition, patterns).
    """
    if _ConditionalPromptManager is not None:
        try:
            manager = _ConditionalPromptManager(config_dir)
            raw_matches = manager.evaluate_batch(lines)
            # Convert to view objects
            matches = []
            for cond, patterns in raw_matches:
                view = ConditionalPromptView(
                    name=cond.name,
                    description=cond.description,
                    patterns=cond.patterns[:],
                    instruction=cond.instruction,
                    priority=cond.priority,
                    enabled=cond.enabled,
                    category=cond.category,
                )
                matches.append((view, patterns))
            return (matches, "core")
        except Exception as e:
            logger.debug(f"Core evaluate_conditions failed: {e}")

    # Fallback: simple pattern matching
    batch_text = "\n".join(lines)
    matches = []
    builtin, _ = get_builtin_conditions()
    for builtin_view in builtin:
        if not builtin_view.enabled:
            continue
        matched_patterns: Set[str] = set()
        for pattern in builtin_view.patterns:
            try:
                if re.search(pattern, batch_text):
                    matched_patterns.add(pattern)
            except re.error:
                continue
        if matched_patterns:
            matches.append((builtin_view, matched_patterns))
    return (matches, "fallback")


def build_conditional_instructions(
    lines: List[str],
    config_dir: Optional[Path] = None,
) -> Tuple[str, str]:
    """Build conditional instruction block for a batch.

    Args:
        lines: Lines to analyze.
        config_dir: Config directory.

    Returns:
        Tuple of (instruction_block, method).
    """
    if _ConditionalPromptManager is not None:
        try:
            manager = _ConditionalPromptManager(config_dir)
            block = manager.build_conditional_instructions(lines)
            return (block, "core")
        except Exception as e:
            logger.debug(f"Core build_conditional_instructions failed: {e}")

    # Fallback: simple format
    matches, _ = evaluate_conditions_for_batch(lines, config_dir)
    if not matches:
        return ("", "fallback")

    parts = ["# Special Handling Instructions\n"]
    for cond, patterns in matches:
        examples = ", ".join(sorted(patterns)[:2])
        parts.append(f"- **{cond.name}**: {cond.instruction} (e.g., {examples})\n")

    return ("".join(parts), "fallback")


# ---------------- Retry Handler Functions ---------------- #


def get_retry_strategies() -> Tuple[List[RetryStrategyView], str]:
    """Get list of available retry strategies.

    Returns:
        Tuple of (strategies, method).
    """
    if _list_retry_strategies is not None:
        try:
            names = _list_retry_strategies()
            views = [RetryStrategyView(name) for name in names if name in RetryStrategyView.__members__.values()]
            return (list(RetryStrategyView), "core")
        except Exception as e:
            logger.debug(f"Core list_retry_strategies failed: {e}")

    # Fallback
    return (list(RetryStrategyView), "fallback")


def get_strategy_info(strategy: str) -> Tuple[str, str, str]:
    """Get display name and description for a strategy.

    Args:
        strategy: Strategy name.

    Returns:
        Tuple of (display_name, description, method).
    """
    if _get_strategy_description is not None and _RetryStrategy is not None:
        try:
            strategy_enum = _RetryStrategy(strategy)
            desc = _get_strategy_description(strategy_enum)
            view = RetryStrategyView(strategy)
            return (view.display_name, desc, "core")
        except Exception as e:
            logger.debug(f"Core get_strategy_description failed: {e}")

    # Fallback
    try:
        view = RetryStrategyView(strategy)
        return (view.display_name, view.description, "fallback")
    except ValueError:
        return (strategy, "Unknown strategy", "fallback")


def create_retry_config(
    strategy: str = DEFAULT_RETRY_STRATEGY,
    max_retries: int = DEFAULT_MAX_RETRIES,
    context_lines: int = DEFAULT_CONTEXT_LINES,
) -> Tuple[RetryConfigView, str]:
    """Create a retry configuration.

    Args:
        strategy: Retry strategy name.
        max_retries: Maximum retries per line.
        context_lines: Context lines for contextual strategy.

    Returns:
        Tuple of (config, method).
    """
    config = RetryConfigView(
        strategy=strategy,
        max_retries=max_retries,
        context_lines=context_lines,
    )
    return (config, "adapter")


def handle_failed_lines(
    failed_indices: List[int],
    original_lines: List[str],
    translations: List[str],
    translate_fn: Callable[[List[str], str | None], List[str]],
    config: RetryConfigView,
    system_prompt: str = "",
) -> Tuple[BatchRetryResultView, str]:
    """Handle failed translation lines with retry logic.

    Args:
        failed_indices: Indices of lines that failed.
        original_lines: Original source lines.
        translations: Current translation list (modified in place).
        translate_fn: Function to call for translation (lines, prompt) -> translations.
        config: Retry configuration.
        system_prompt: System prompt to use.

    Returns:
        Tuple of (result, method).
    """
    if _create_retry_handler is not None and _RetryHandler is not None:
        try:
            handler = _create_retry_handler(
                strategy=config.strategy,
                max_retries=config.max_retries,
                context_lines=config.context_lines,
            )
            raw_result = handler.handle_failed_lines(
                failed_indices=failed_indices,
                original_lines=original_lines,
                translations=translations,
                translate_fn=translate_fn,
                system_prompt=system_prompt,
            )
            # Convert to view
            line_results = []
            for lr in raw_result.line_results:
                line_results.append(RetryResultView(
                    line_index=lr.line_index,
                    success=lr.success,
                    translation=lr.translation,
                    attempts=lr.attempts,
                    strategy_used=lr.strategy_used.value if hasattr(lr.strategy_used, 'value') else str(lr.strategy_used),
                    error_message=lr.error_message or "",
                ))
            result = BatchRetryResultView(
                successful_count=raw_result.successful_count,
                failed_count=raw_result.failed_count,
                skipped_count=raw_result.skipped_count,
                total_attempts=raw_result.total_attempts,
                line_results=line_results,
            )
            return (result, "core")
        except Exception as e:
            logger.debug(f"Core handle_failed_lines failed: {e}")

    # Fallback: simple retry logic
    result = BatchRetryResultView()
    for idx in failed_indices:
        try:
            # Simple single retry
            batch_result = translate_fn([original_lines[idx]], system_prompt)
            trans = batch_result[0] if batch_result else ""
            if trans and trans.strip():
                translations[idx] = trans
                result.successful_count += 1
                result.line_results.append(RetryResultView(
                    line_index=idx,
                    success=True,
                    translation=trans,
                    attempts=1,
                    strategy_used="fallback",
                ))
            else:
                result.failed_count += 1
                result.line_results.append(RetryResultView(
                    line_index=idx,
                    success=False,
                    translation=original_lines[idx],
                    attempts=1,
                    strategy_used="fallback",
                    error_message="Empty translation",
                ))
        except Exception as e:
            result.failed_count += 1
            result.line_results.append(RetryResultView(
                line_index=idx,
                success=False,
                translation=original_lines[idx],
                attempts=1,
                strategy_used="fallback",
                error_message=str(e),
            ))
        result.total_attempts += 1

    return (result, "fallback")


# ---------------- Prompt Builder Functions ---------------- #


def build_full_system_prompt(
    metadata: Dict[str, Any],
    glossary_entries: Optional[List[Dict[str, Any]]] = None,
    characters: Optional[List[Dict[str, Any]]] = None,
    sample_lines: Optional[List[str]] = None,
    rolling_context_text: str = "",
    pov_data: Optional[Dict[str, Any]] = None,
    config_dir: Optional[Path] = None,
    chunk_lines: Optional[List[str]] = None,
    code_patterns: Optional[List[Dict[str, Any]]] = None,
    merge_instruction: str = "",
) -> Tuple[str, Dict[str, int]]:
    """Build the full system prompt following spec §5.2 injection order.

    This is the **single source of truth** for prompt assembly, shared
    by the Costs step (prompt overhead estimate) and the Translation
    step (actual API requests + request preview).

    §5.2 Injection Order:
        1. Language Direction
        2. System Instructions (system_instructions)
        3. Style
        4. Tone
        4b. Protagonist + Narration  (Task 75)
        5. Summary
        6. Genre
        7. POV (narrative perspective) — skipped when 4b has narration
        8. Conditional Prompts (selective per-chunk)
        8b. Merged-request instruction (Efficient mode Step 5)
        9. Glossary + Characters (selective per-chunk)
        10. Rolling Context (conditional)

    When ``chunk_lines`` is provided, glossary entries and characters
    are filtered to only those whose source term / original_name
    appears in the chunk.  Conditional prompts are likewise detected
    against the chunk rather than the full sample.

    Args:
        metadata: Information-step metadata dict with keys
            source_language, target_language, system_instructions, style,
            tone, summary, genre.
        glossary_entries: Active glossary entries, each a dict with
            source, target, notes, active keys.
        characters: Character list from metadata (original_name,
            name, gender/notes).
        sample_lines: Lines for conditional prompt detection (first
            ~200 preprocessed lines).  Used as fallback when
            ``chunk_lines`` is not provided.
        rolling_context_text: Pre-formatted rolling context to append.
        pov_data: POV dict from manifest (pov, confidence keys).
        config_dir: Config directory for conditional prompt loading.
        chunk_lines: When provided, enables per-chunk selective
            filtering of glossary, characters, and conditional prompts.
        code_patterns: Code patterns from manifest for protagonist
            detection (optional, Task 75).
        merge_instruction: Instruction text describing block relatedness
            for merged requests (Step 5 Efficient mode).  Injected as
            §5.2 item 8b.

    Returns:
        Tuple of (assembled_prompt, token_breakdown) where
        token_breakdown maps section name → estimated word count.
    """
    if metadata is None:
        metadata = {}

    parts: List[str] = []
    breakdown: Dict[str, int] = {}

    def _add(section_name: str, text: str) -> None:
        if text and text.strip():
            parts.append(text)
            breakdown[section_name] = len(text.split())

    # --- Section toggle flags (from Information step metadata) ---
    # Each flag controls whether that section is included in the prompt.
    # Missing keys default to their original behaviour for backward compat.
    genre_enabled = metadata.get("genre_enabled", False)
    summary_enabled = metadata.get("summary_enabled", False)
    style_enabled = metadata.get("style_enabled", False)
    tone_enabled = metadata.get("tone_enabled", False)
    si_enabled = metadata.get("system_instructions_enabled", True)
    glossary_enabled = metadata.get("glossary_enabled", True)
    code_database_enabled = metadata.get("code_database_enabled", True)

    # --- 1. Language Direction ---
    source_lang = (metadata.get("source_language", "") or "").strip()
    target_lang = (metadata.get("target_language", "") or "").strip()
    if source_lang and target_lang:
        _add(
            "language",
            f"# Language\nTranslate from {source_lang} to {target_lang}.",
        )

    # --- 2. System Instructions ---
    if si_enabled:
        sys_instructions = (
            metadata.get("system_instructions", "") or ""
        ).strip()
        if sys_instructions:
            _add("system_instructions", sys_instructions)

    # --- 3. Style ---
    if style_enabled:
        style = (
            metadata.get("style", "") or metadata.get("custom_style", "")
            or ""
        ).strip()
        if style:
            _add("style", f"# Translation Style Guidelines\n{style}")

    # --- 4. Tone ---
    if tone_enabled:
        tone = (
            metadata.get("tone", "") or metadata.get("custom_tone", "")
            or ""
        ).strip()
        if tone:
            _add("tone", f"# Translation Tone\n{tone}")

    # --- 4b. Protagonist + Narration (Task 75) ---
    protagonist_section = ""
    if _format_protagonist_prompt and (characters or code_patterns):
        pov_obj = None
        if pov_data and isinstance(pov_data, dict) and _POVResult:
            pov_obj = _POVResult.from_dict(pov_data)
        protagonist_section = _format_protagonist_prompt(
            characters or [],
            code_patterns,
            pov_obj,
        )
    if protagonist_section:
        _add("protagonist", f"# Protagonist\n{protagonist_section}")

    # --- 5. Summary ---
    if summary_enabled:
        summary = (metadata.get("summary", "") or "").strip()
        if summary:
            _add("summary", f"# Game Context\n{summary}")

    # --- 6. Genre ---
    if genre_enabled:
        genre = (metadata.get("genre", "") or "").strip()
        if genre:
            _add("genre", f"# Genre\n{genre}")

    # --- 7. POV (skipped when protagonist section has narration) ---
    if not protagonist_section and pov_data and isinstance(pov_data, dict):
        if pov_data.get("confidence") == "high":
            pov_label = {
                "1st": "first",
                "2nd": "second",
                "3rd": "third",
            }.get(pov_data.get("pov", ""), pov_data.get("pov", ""))
            _add(
                "pov",
                f"# Narrative Perspective\n"
                f"The narrative uses {pov_label} person perspective. "
                f"Maintain consistent {pov_label} person perspective "
                f"throughout.",
            )

    # --- 8. Conditional Prompts (selective per-chunk) ---
    cond_lines = chunk_lines if chunk_lines is not None else (sample_lines or [])
    if cond_lines:
        cond_text, _ = build_conditional_instructions(
            cond_lines[:200], config_dir,
        )
        if cond_text and cond_text.strip():
            _add("conditional", cond_text.strip())

    # --- 8b. Merged-request instruction (Efficient mode Step 5) ---
    if merge_instruction and merge_instruction.strip():
        _add(
            "merge_instruction",
            f"# Request Structure\n{merge_instruction.strip()}",
        )

    # --- 9. Glossary + Characters (selective per-chunk) ---
    # When chunk_lines is provided, only include entries whose source
    # term / original_name appears in the chunk text.
    # Glossary entries are included only when glossary_enabled is True.
    # Characters are always included when glossary_enabled is True
    # (they are part of the glossary section).
    chunk_text_joined = "\n".join(chunk_lines) if chunk_lines else ""

    glossary_block = ""
    if glossary_enabled and glossary_entries:
        active = [e for e in glossary_entries if e.get("active", True)]
        if chunk_lines is not None:
            active = [
                e for e in active
                if e.get("source", "") and e["source"] in chunk_text_joined
            ]
        if active:
            g_lines = ["# Glossary", "Use these terms strictly:"]
            for entry in active:
                src = entry.get("source", "")
                tgt = entry.get("target", "")
                notes = entry.get("notes", "")
                if src:
                    line_text = f"- {src} → {tgt}" if tgt else f"- {src}"
                    if notes:
                        line_text += f" ({notes})"
                    g_lines.append(line_text)
            glossary_block = "\n".join(g_lines)

    if glossary_enabled and characters:
        relevant_chars = characters
        if chunk_lines is not None:
            relevant_chars = [
                ch for ch in characters
                if ch.get("original_name", "")
                and ch["original_name"] in chunk_text_joined
            ]
        char_lines: List[str] = ["# Characters"]
        for ch in relevant_chars:
            orig = ch.get("original_name", "")
            eng = ch.get("translation", "") or ch.get("name", "")
            notes = ch.get("notes", "")
            if orig:
                entry_text = f"- {orig}"
                if eng:
                    entry_text += f" → {eng}"
                if notes:
                    entry_text += f" ({notes})"
                char_lines.append(entry_text)
        if len(char_lines) > 1:
            if glossary_block:
                glossary_block += "\n\n" + "\n".join(char_lines)
            else:
                glossary_block = "\n".join(char_lines)

    if glossary_block:
        _add("glossary", glossary_block)

    # --- 10. Rolling Context ---
    if rolling_context_text and rolling_context_text.strip():
        _add(
            "rolling_context",
            f"# Rolling Context\n{rolling_context_text.strip()}",
        )

    assembled = "\n\n".join(parts)
    return assembled, breakdown


def build_prompt_preview(
    lines: List[str],
    game_summary: str = "",
    glossary_text: str = "",
    style_text: str = "",
    config_dir: Optional[Path] = None,
) -> Tuple[PromptPreviewView, str]:
    """Build a preview of the complete prompt.

    Args:
        lines: Sample lines to analyze for conditional prompts.
        game_summary: Game summary text.
        glossary_text: Glossary entries text.
        style_text: Translation style text.
        config_dir: Config directory.

    Returns:
        Tuple of (preview, method).
    """
    # Build sections
    parts = []
    breakdown = {}

    # Game summary section
    summary_section = ""
    if game_summary.strip():
        summary_section = f"# Game Context\n{game_summary.strip()}"
        parts.append(summary_section)
        breakdown["game_summary"] = len(game_summary.split())

    # Glossary section
    glossary_section = ""
    if glossary_text.strip():
        glossary_section = f"# Glossary\n{glossary_text.strip()}"
        parts.append(glossary_section)
        breakdown["glossary"] = len(glossary_text.split())

    # Style section
    style_section = ""
    if style_text.strip():
        style_section = f"# Translation Style\n{style_text.strip()}"
        parts.append(style_section)
        breakdown["style"] = len(style_text.split())

    # Conditional section
    conditional_section, _ = build_conditional_instructions(lines, config_dir)
    if conditional_section.strip():
        parts.append(conditional_section.strip())
        breakdown["conditional"] = len(conditional_section.split())

    # Combine into system prompt
    system_prompt = "\n\n".join(parts)

    # Estimate tokens (rough: 1 token ≈ 4 chars for English)
    total_tokens = len(system_prompt) // 4

    preview = PromptPreviewView(
        system_prompt=system_prompt,
        game_summary=summary_section,
        glossary_section=glossary_section,
        style_section=style_section,
        conditional_section=conditional_section,
        total_tokens=total_tokens,
        breakdown=breakdown,
    )

    return (preview, "adapter")


def create_prompt_builder(
    config_dir: Optional[Path] = None,
) -> Tuple[Any, str]:
    """Create a PromptBuilder instance.

    Args:
        config_dir: Config directory.

    Returns:
        Tuple of (builder, method) where builder is PromptBuilder or None.
    """
    if _PromptBuilder is not None:
        try:
            builder = _PromptBuilder(config_dir=config_dir or Path("."))
            return (builder, "core")
        except Exception as e:
            logger.debug(f"Core PromptBuilder failed: {e}")

    return (None, "unavailable")


def get_rolling_context_config(
    config_dir: Optional[Path] = None,
) -> Tuple[RollingContextView, str]:
    """Get rolling context configuration.

    Args:
        config_dir: Config directory.

    Returns:
        Tuple of (config, method).
    """
    if _PromptBuilder is not None and _RollingContextConfig is not None:
        try:
            builder = _PromptBuilder(config_dir=config_dir or Path("."))
            rc = builder.rolling_context_config
            view = RollingContextView(
                enabled=rc.enabled,
                lines_before=rc.lines_before,
                scene_markers=rc.scene_markers[:],
                use_translated=rc.use_translated,
            )
            return (view, "core")
        except Exception as e:
            logger.debug(f"Core rolling context config failed: {e}")

    # Fallback
    return (RollingContextView(), "fallback")


def format_rolling_context_section(
    context_lines: List[str],
    is_translated: bool = True,
) -> Tuple[str, str]:
    """Format rolling context for user message.

    Args:
        context_lines: Previous lines to include.
        is_translated: Whether lines are already translated.

    Returns:
        Tuple of (formatted_context, method).
    """
    if _format_rolling_context is not None:
        try:
            result = _format_rolling_context(context_lines, is_translated)
            return (result, "core")
        except Exception as e:
            logger.debug(f"Core format_rolling_context failed: {e}")

    # Fallback
    if not context_lines:
        return ("", "fallback")

    label = "Previous translations" if is_translated else "Previous lines"
    context_text = "\n".join(f"  {line}" for line in context_lines)
    return (f"\n[{label} for context - do not re-translate these:]\n{context_text}\n\n", "fallback")
