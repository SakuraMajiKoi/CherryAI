"""Dynamic Prompt Builder for CherryAI.

Constructs system prompts and user messages for the API Client.
Handles:
- Game summary injection (project context)
- Translation style injection (user preferences)
- Rolling context injection (preceding translated lines)
- Glossary injection (selective based on content)
- Context injection (file metadata, speaker list)
- Rolling context management
- Request batching with context markers
- Conditional prompt instructions (pattern-triggered)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .glossary import read_unified_glossary, GlossaryEntry, TYPE_NAME, TYPE_TERM
from .analysis import count_tokens
from .conditional_prompts import ConditionalPromptManager
from .config import load_config
from .project_config import (
    ProjectConfig,
    load_game_summary,
    format_summary_for_prompt,
    load_project_config_from_ini,
)
from .validation import detect_speaker_dialogue_format, SpeakerFormatInfo

# Constants
DEFAULT_PROMPT_TEMPLATE = "config/prompt.txt"
MAX_CONTEXT_TOKENS = 4000  # Conservative limit for context window (adjust per model)
ROLLING_CONTEXT_LINES = 3  # Number of preceding lines to include
MAX_STYLE_CHARS = 2000  # Maximum characters for translation style


# =============================================================================
# SPEAKER QUOTE STRIPPING
# =============================================================================


@dataclass
class StrippedQuoteInfo:
    """Information about stripped quotes from a speaker line.
    
    Used to restore quotes after translation. Each line that had quotes
    stripped gets one of these to track the original quote characters.
    """
    
    line_index: int
    speaker_name: str
    colon_char: str
    opening_quote: str
    closing_quote: str
    had_quotes: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage in manifest."""
        return {
            "idx": self.line_index,
            "speaker": self.speaker_name,
            "colon": self.colon_char,
            "open": self.opening_quote,
            "close": self.closing_quote,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrippedQuoteInfo":
        """Deserialize from manifest storage."""
        return cls(
            line_index=data["idx"],
            speaker_name=data["speaker"],
            colon_char=data["colon"],
            opening_quote=data["open"],
            closing_quote=data["close"],
        )


@dataclass
class QuoteStrippingResult:
    """Result of stripping quotes from a batch of lines."""
    
    stripped_lines: List[str]
    quote_info: List[StrippedQuoteInfo]
    tokens_saved: int = 0
    
    @property
    def lines_affected(self) -> int:
        """Number of lines that had quotes stripped."""
        return len(self.quote_info)


def strip_speaker_quotes(
    lines: List[str],
    start_index: int = 0,
) -> QuoteStrippingResult:
    """Strip surrounding quotes from speaker dialogue lines.
    
    Converts lines like:
        Speaker: "Dialogue text here"
    To:
        Speaker: Dialogue text here
    
    This saves 2 tokens per speaker line in the API request. The quote info
    is returned so quotes can be restored after translation.
    
    Args:
        lines: List of lines to process.
        start_index: Starting index for line numbering in quote_info.
        
    Returns:
        QuoteStrippingResult with stripped lines and restoration info.
    """
    stripped_lines: List[str] = []
    quote_info: List[StrippedQuoteInfo] = []
    tokens_saved = 0
    
    for i, line in enumerate(lines):
        # Detect speaker format
        info = detect_speaker_dialogue_format(line)
        
        if info.has_speaker_format and info.is_balanced and info.dialogue_content:
            # Strip the quotes - reconstruct line without outer quotes
            # Format: Speaker: Dialogue content
            new_line = f"{info.speaker_name}{info.colon_char} {info.dialogue_content}"
            stripped_lines.append(new_line)
            
            # Track for restoration
            quote_info.append(StrippedQuoteInfo(
                line_index=start_index + i,
                speaker_name=info.speaker_name,
                colon_char=info.colon_char,
                opening_quote=info.opening_quote,
                closing_quote=info.closing_quote,
            ))
            
            # Each quote pair is typically 2 tokens
            tokens_saved += 2
        else:
            # Keep line as-is
            stripped_lines.append(line)
    
    return QuoteStrippingResult(
        stripped_lines=stripped_lines,
        quote_info=quote_info,
        tokens_saved=tokens_saved,
    )


def restore_speaker_quotes(
    translated_lines: List[str],
    quote_info: List[StrippedQuoteInfo],
    base_index: int = 0,
) -> List[str]:
    """Restore quotes to translated speaker lines.
    
    Takes translated lines and restores the original quote characters
    around dialogue content for lines that had quotes stripped.
    
    Args:
        translated_lines: Translated lines to restore quotes to.
        quote_info: List of StrippedQuoteInfo from stripping phase.
        base_index: Base index to subtract from quote_info indices.
        
    Returns:
        List of lines with quotes restored.
    """
    # Build lookup map: line_index -> quote_info
    quote_map: Dict[int, StrippedQuoteInfo] = {
        q.line_index - base_index: q for q in quote_info
    }
    
    result: List[str] = []
    
    for i, line in enumerate(translated_lines):
        if i not in quote_map:
            # No quotes to restore for this line
            result.append(line)
            continue
        
        info = quote_map[i]
        
        # Try to detect speaker format in translated line
        trans_info = detect_speaker_dialogue_format(line)
        
        if trans_info.has_speaker_format:
            # Already has speaker format - may or may not have quotes
            if trans_info.is_balanced:
                # Already has quotes - use translated as-is
                result.append(line)
            else:
                # Has speaker format but missing quotes - restore them
                # Find colon position and add quotes around the rest
                colon_pos = line.find(trans_info.colon_char)
                if colon_pos >= 0:
                    speaker_part = line[:colon_pos + 1]
                    dialogue_part = line[colon_pos + 1:].strip()
                    restored = f"{speaker_part} {info.opening_quote}{dialogue_part}{info.closing_quote}"
                    result.append(restored)
                else:
                    result.append(line)
        else:
            # Translated line lost speaker format entirely
            # Try simple restoration: wrap entire line with quotes after speaker prefix
            # Check if line starts with the expected speaker name
            if line.strip().startswith(info.speaker_name):
                # Find where content starts
                after_name = line[len(info.speaker_name):].lstrip()
                if after_name.startswith(info.colon_char):
                    # Has colon - restore quotes around rest
                    colon_idx = line.find(info.colon_char)
                    speaker_part = line[:colon_idx + 1]
                    dialogue_part = line[colon_idx + 1:].strip()
                    restored = f"{speaker_part} {info.opening_quote}{dialogue_part}{info.closing_quote}"
                    result.append(restored)
                else:
                    # No colon - add colon and quotes
                    dialogue_part = after_name.strip()
                    restored = f"{info.speaker_name}{info.colon_char} {info.opening_quote}{dialogue_part}{info.closing_quote}"
                    result.append(restored)
            else:
                # Speaker name not preserved at all - wrap entire content
                # This is a fallback for badly translated lines
                restored = f"{info.speaker_name}{info.colon_char} {info.opening_quote}{line.strip()}{info.closing_quote}"
                result.append(restored)
    
    return result


def load_translation_style(
    style_file: str = "config/translation_style.txt",
    config_dir: Optional[Path] = None,
    max_chars: int = MAX_STYLE_CHARS,
) -> str:
    """Load and clean translation style from file.
    
    Args:
        style_file: Path to style file (relative to config_dir or absolute)
        config_dir: Directory containing config files
        max_chars: Maximum characters to return (truncates with warning)
        
    Returns:
        Cleaned style text with comments and placeholders removed.
    """
    if config_dir is None:
        config_dir = Path("config")
    
    # Handle absolute vs relative paths
    style_path = Path(style_file)
    if not style_path.is_absolute():
        style_path = config_dir / style_file
    
    if not style_path.exists():
        return ""
    
    try:
        content = style_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    
    # Remove comment lines (lines starting with # after stripping)
    lines = content.splitlines()
    cleaned_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        # Skip full comment lines
        if stripped.startswith("#"):
            continue
        # Skip empty lines at the start
        if not cleaned_lines and not stripped:
            continue
        # Skip placeholder lines
        if "[placeholder]" in stripped.lower():
            continue
        cleaned_lines.append(line)
    
    # Remove trailing empty lines
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
    
    result = "\n".join(cleaned_lines).strip()
    
    # Truncate if too long (reserve space for "..." if truncating)
    if len(result) > max_chars:
        logging.warning(f"Translation style truncated from {len(result)} to {max_chars} chars")
        result = result[:max_chars - 3] + "..."
    
    return result


def format_style_for_prompt(style: str) -> str:
    """Format translation style text for prompt injection.
    
    Args:
        style: Raw translation style text
        
    Returns:
        Formatted style block for system prompt.
    """
    if not style or not style.strip():
        return ""
    
    return f"\n\n# Translation Style Guidelines\n{style.strip()}"


def format_rolling_context(context_lines: List[str], is_translated: bool = True) -> str:
    """Format rolling context for prompt injection.
    
    Args:
        context_lines: Previous lines to include as context
        is_translated: Whether the lines are already translated
        
    Returns:
        Formatted context block for user message.
    """
    if not context_lines:
        return ""
    
    label = "Previous translations" if is_translated else "Previous lines"
    context_text = "\n".join(f"  {line}" for line in context_lines)
    return f"\n[{label} for context - do not re-translate these:]\n{context_text}\n\n"


@dataclass
class RequestBatch:
    """A batch of lines to be sent to the API."""
    lines: List[str]
    indices: List[int]  # Original line indices
    context_before: List[str] = field(default_factory=list)  # Rolling context (translated)
    system_prompt: str = ""
    quote_info: List[StrippedQuoteInfo] = field(default_factory=list)  # For quote restoration
    
    @property
    def line_count(self) -> int:
        return len(self.lines)
    
    def get_context_prefix(self) -> str:
        """Get formatted rolling context prefix for user message."""
        return format_rolling_context(self.context_before)


@dataclass
class RollingContextConfig:
    """Configuration for rolling context feature."""
    enabled: bool = True
    lines_before: int = 3
    scene_markers: List[str] = field(default_factory=lambda: ["=====", "-----", "***"])
    use_translated: bool = True
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "RollingContextConfig":
        """Create from config dictionary."""
        import os
        rc_section = config.get("rolling_context", {})
        markers_str = rc_section.get("scene_markers", "=====,-----,***")
        markers = [m.strip() for m in markers_str.split(",") if m.strip()]
        # Robust boolean parsing for 'enabled' and 'use_translated'
        def _as_bool(val: Any, default: bool) -> bool:
            if isinstance(val, bool):
                return val
            if val is None:
                return default
            s = str(val).strip().lower()
            if s in ("true", "1", "yes", "on"): return True
            if s in ("false", "0", "no", "off"): return False
            return default
        # Environment overrides for test mode (only when CHERRYAI_TEST_MODE is set)
        test_mode = os.environ.get("CHERRYAI_TEST_MODE", "").strip()
        env_enabled = os.environ.get("CHERRYAI_TEST_RC_ENABLED", "").strip() if test_mode else ""
        env_use_translated = os.environ.get("CHERRYAI_TEST_RC_USE_TRANSLATED", "").strip() if test_mode else ""
        enabled_val = _as_bool(rc_section.get("enabled", True), True)
        use_translated_val = _as_bool(rc_section.get("use_translated", True), True)
        if env_enabled:
            enabled_val = env_enabled.lower() == "true"
        if env_use_translated:
            use_translated_val = env_use_translated.lower() == "true"
        # Parse lines_before robustly (accept int or numeric string; fallback to default 3)
        lines_before_raw = rc_section.get("lines_before", 3)
        try:
            lines_before_val = int(lines_before_raw) if lines_before_raw is not None else 3
        except Exception:
            lines_before_val = 3
        return cls(
            enabled=enabled_val,
            lines_before=lines_before_val,
            scene_markers=markers,
            use_translated=use_translated_val,
        )

class PromptBuilder:
    """Builds dynamic prompts for translation requests."""

    def __init__(
        self,
        config_dir: Path = Path("config"),
        project_config: Optional[ProjectConfig] = None,
        rc_config: Optional[RollingContextConfig] = None,
    ):
        """Initialize the prompt builder.
        
        Args:
            config_dir: Directory containing config files (prompt.txt, game_summary.txt)
            project_config: Optional project configuration. If None, loads from INI.
        """
        self.logger = logging.getLogger("cherryai.prompt")
        self.config_dir = config_dir
        self.glossary: Dict[str, GlossaryEntry] = {}
        self.base_prompt_template = ""
        self.conditional_manager = ConditionalPromptManager(config_dir)
        
        # Project configuration
        self.project_config = project_config or load_project_config_from_ini()
        self.game_summary = ""
        self.translation_style = ""
        
        # Rolling context configuration (allow explicit override for tests)
        if rc_config is not None:
            self.rolling_context_config = rc_config
            full_config = load_config()
        else:
            full_config = load_config()
            self.rolling_context_config = RollingContextConfig.from_config(full_config)
        
        # Translation style file from config
        trans_section = full_config.get("translation", {})
        self.style_file = trans_section.get("style_file", "config/translation_style.txt")
        
        self._load_resources()

    def _load_resources(self) -> None:
        """Load glossary, prompt template, game summary, and translation style."""
        # Load Glossary
        try:
            self.glossary = read_unified_glossary()
            self.logger.info(f"Loaded {len(self.glossary)} glossary entries.")
        except Exception as e:
            self.logger.warning(f"Failed to load glossary: {e}")

        # Load Prompt Template
        template_path = self.config_dir / "prompt.txt"
        try:
            if template_path.exists():
                self.base_prompt_template = template_path.read_text(encoding="utf-8")
            else:
                self.logger.warning(f"Prompt template not found at {template_path}")
                self.base_prompt_template = "You are a helpful translator."
        except Exception as e:
            self.logger.error(f"Failed to load prompt template: {e}")
        
        # Load Game Summary
        self._load_game_summary()
        
        # Load Translation Style
        self._load_translation_style()
    
    def _load_game_summary(self) -> None:
        """Load game summary from configured file."""
        summary_file = self.project_config.summary_file if self.project_config else "config/game_summary.txt"
        raw_summary = load_game_summary(summary_file)
        self.game_summary = format_summary_for_prompt(raw_summary, self.project_config)
        if self.game_summary:
            self.logger.info(f"Loaded game summary ({len(self.game_summary)} chars)")
    
    def _load_translation_style(self) -> None:
        """Load translation style from configured file."""
        self.translation_style = load_translation_style(self.style_file, self.config_dir)
        if self.translation_style:
            self.logger.info(f"Loaded translation style ({len(self.translation_style)} chars)")
    
    def _load_output_examples(self) -> str:
        """Load output examples from config/output_examples.txt.
        
        Returns:
            Output examples text, or empty string if not found.
        """
        examples_path = self.config_dir / "output_examples.txt"
        try:
            if examples_path.exists():
                content = examples_path.read_text(encoding="utf-8").strip()
                if content:
                    self.logger.debug(f"Loaded output examples ({len(content)} chars)")
                    return content
        except Exception as e:
            self.logger.warning(f"Failed to load output examples: {e}")
        return ""
    
    def set_project_config(self, project_config: ProjectConfig) -> None:
        """Update project configuration and reload summary.
        
        Args:
            project_config: New project configuration
        """
        self.project_config = project_config
        self._load_game_summary()

    def build_batches(
        self, 
        lines: List[str], 
        max_batch_size: int = 50, 
        min_batch_size: int = 10,
        context_markers: Optional[List[str]] = None,
        strip_quotes: bool = False,
    ) -> List[RequestBatch]:
        """Split lines into batches respecting context markers and size limits.
        
        Args:
            lines: List of text lines to translate.
            max_batch_size: Maximum lines per request.
            min_batch_size: Minimum lines (soft limit, unless marker forces split).
            context_markers: List of regex strings that indicate a scene change.
            strip_quotes: If True, strip quotes from speaker lines to save tokens.
        
        Returns:
            List of RequestBatch objects.
        """
        batches: List[RequestBatch] = []
        current_batch_lines: List[str] = []
        current_batch_indices: List[int] = []
        scene_break_pending = False  # Track if next batch should reset context
        
        # Use config markers if none provided
        if context_markers is None:
            context_markers = self.rolling_context_config.scene_markers
        
        # Compile markers
        marker_patterns = [re.compile(re.escape(p)) for p in (context_markers or [])]

        for i, line in enumerate(lines):
            # Check for context markers (scene breaks)
            is_marker = any(p.search(line) for p in marker_patterns)
            
            # If marker found and batch is big enough, split with context reset
            if is_marker and len(current_batch_lines) >= min_batch_size:
                self._finalize_batch(
                    batches, current_batch_lines, current_batch_indices,
                    reset_context=scene_break_pending,
                    strip_quotes=strip_quotes,
                )
                current_batch_lines = []
                current_batch_indices = []
                scene_break_pending = True  # Next batch starts fresh context

            current_batch_lines.append(line)
            current_batch_indices.append(i)

            # Check max size
            if len(current_batch_lines) >= max_batch_size:
                self._finalize_batch(
                    batches, current_batch_lines, current_batch_indices,
                    reset_context=scene_break_pending,
                    strip_quotes=strip_quotes,
                )
                current_batch_lines = []
                current_batch_indices = []
                scene_break_pending = False  # Reset after use

        # Final batch
        if current_batch_lines:
            self._finalize_batch(
                batches, current_batch_lines, current_batch_indices,
                reset_context=scene_break_pending,
                strip_quotes=strip_quotes,
            )

        # If rolling context is disabled, ensure no batch carries context
        if not self.rolling_context_config.enabled:
            for b in batches:
                b.context_before = []
        return batches

    def _finalize_batch(
        self, 
        batches: List[RequestBatch], 
        lines: List[str], 
        indices: List[int],
        reset_context: bool = False,
        strip_quotes: bool = False,
    ) -> None:
        """Create a RequestBatch and add it to the list.
        
        Args:
            batches: List to append to
            lines: Lines in this batch
            indices: Original line indices
            reset_context: If True, don't carry over context (scene break)
            strip_quotes: If True, strip quotes from speaker lines
        """
        # Calculate rolling context from previous batch if available
        context_before: List[str] = []
        if batches and not reset_context and self.rolling_context_config.enabled:
            prev_batch = batches[-1]
            # Use configured number of lines from previous batch
            n = self.rolling_context_config.lines_before
            context_before = prev_batch.lines[-n:] if n > 0 else []

        # Apply quote stripping if enabled
        quote_info: List[StrippedQuoteInfo] = []
        batch_lines = lines
        if strip_quotes:
            # Get starting index for this batch
            start_idx = indices[0] if indices else 0
            strip_result = strip_speaker_quotes(lines, start_index=start_idx)
            batch_lines = strip_result.stripped_lines
            quote_info = strip_result.quote_info

        # Build specific system prompt for this batch
        system_prompt = self._construct_system_prompt(batch_lines)
        
        # If rolling context is disabled, force empty context
        if not self.rolling_context_config.enabled:
            context_before = []

        batches.append(RequestBatch(
            lines=batch_lines,
            indices=indices,
            context_before=context_before,
            system_prompt=system_prompt,
            quote_info=quote_info,
        ))
        # Enforce disabled rolling context explicitly
        if not self.rolling_context_config.enabled:
            batches[-1].context_before = []

    def _is_game_summary_empty(self) -> bool:
        """Check if game summary is just a template with placeholders."""
        if not self.game_summary:
            return True
        # Check for common placeholder patterns
        placeholders = ["[title", "[setting", "[character", "[plot", "[tone", "[special", "goes here"]
        summary_lower = self.game_summary.lower()
        return any(p in summary_lower for p in placeholders)

    def _construct_system_prompt(self, lines: List[str]) -> str:
        """Construct the system prompt with game summary, glossary, and conditional instructions.
        
        Injection order (optimized for token savings - TASK 12):
        1. Base prompt template (instructions)
        2. Game summary (project context - if not empty/placeholder)
        3. Output examples (from output_examples.txt)
        4. Glossary terms (content-based, only if entries found)
        5. Character list (content-based, only if characters found)
        6. Translation style (user preferences)
        7. Conditional instructions (pattern-triggered)
        
        Empty sections are SKIPPED to save tokens.
        """
        prompt_parts = []
        
        # 1. Base prompt template (instructions)
        if self.base_prompt_template:
            prompt_parts.append(self.base_prompt_template)
        
        # 2. Inject Game Summary (context) - skip if empty or just a template
        if self.game_summary and not self._is_game_summary_empty():
            prompt_parts.append(self.game_summary)
        
        # 3. Output examples (from output_examples.txt)
        output_examples = self._load_output_examples()
        if output_examples:
            prompt_parts.append(f"# Output Format Examples\n{output_examples}")
        
        # 4. Identify Glossary Terms present in this batch
        batch_text = "\n".join(lines)
        relevant_entries = []
        
        # Optimization: Check for terms in the text
        for original, entry in self.glossary.items():
            if original in batch_text:
                relevant_entries.append(entry)
        
        # 5. Format Glossary Block (conditional - only if terms found with translations)
        entries_with_translation = [e for e in relevant_entries if e.translation]
        if entries_with_translation:
            glossary_block = "# Glossary\nUse these terms strictly:\n"
            for entry in entries_with_translation:
                notes = f" ({entry.notes})" if entry.notes else ""
                glossary_block += f"- {entry.original}: {entry.translation}{notes}\n"
            prompt_parts.append(glossary_block)

        # 6. Add Character List (conditional - only if characters found with translations)
        characters = [e for e in relevant_entries if e.entry_type == TYPE_NAME and e.translation]
        if characters:
            char_block = "# Game Characters\n"
            for char in characters:
                gender = char.gender if char.gender else "Unknown"
                char_block += f"- {char.original}: {char.translation} (Gender: {gender})\n"
            prompt_parts.append(char_block)
        
        # 7. Inject Translation Style (user preferences) - skip if empty
        # Ensure style is loaded even if resources were not yet loaded
        if not self.translation_style and self.style_file:
            try:
                self.translation_style = load_translation_style(self.style_file, self.config_dir)
            except Exception:
                self.translation_style = ""
        # Additional fallback: try local config_dir/translation_style.txt
        if not self.translation_style:
            try:
                self.translation_style = load_translation_style("translation_style.txt", self.config_dir)
            except Exception:
                pass
        if self.translation_style and self.translation_style.strip():
            # Use canonical formatting to satisfy tests
            prompt_parts.append(format_style_for_prompt(self.translation_style))

        # 8. Add Conditional Instructions (pattern-triggered)
        conditional_block = self.conditional_manager.build_conditional_instructions(lines)
        if conditional_block:
            prompt_parts.append(conditional_block.strip())


        return "\n\n".join(prompt_parts)
    
    def update_batch_context(
        self, 
        batch: RequestBatch, 
        translated_lines: List[str]
    ) -> None:
        """Update a batch's rolling context with translated content.
        
        This is called after translation to update subsequent batches
        with the actual translated content for context.
        
        Args:
            batch: The batch whose context_before to update
            translated_lines: The translated lines from the previous batch
        """
        # Respect disabled: do not modify context (preserve existing source context)
        if not self.rolling_context_config.enabled:
            return
        # Empty translated list clears context
        if not translated_lines:
            batch.context_before = []
            return
        # Respect use_translated flag: keep source context unchanged
        if not self.rolling_context_config.use_translated:
            return
        # Use last N translated lines
        try:
            n = max(0, int(self.rolling_context_config.lines_before))
        except Exception:
            n = ROLLING_CONTEXT_LINES
        # Heuristic safeguard: honor prior source context width when smaller
        if batch.context_before:
            n = min(n, len(batch.context_before))
        batch.context_before = translated_lines[-n:] if n > 0 else []

    def restore_batch_quotes(
        self,
        batch: RequestBatch,
        translated_lines: List[str],
    ) -> List[str]:
        """Restore quotes to translated lines if they were stripped.
        
        Args:
            batch: The batch containing quote_info for restoration.
            translated_lines: The translated lines from the API.
            
        Returns:
            List of lines with quotes restored (if any were stripped).
        """
        if not batch.quote_info:
            # No quotes were stripped for this batch
            return translated_lines
        
        # Get the base index for this batch
        base_index = batch.indices[0] if batch.indices else 0
        
        return restore_speaker_quotes(translated_lines, batch.quote_info, base_index)

    def estimate_tokens(self, batches: List[RequestBatch]) -> int:
        """Estimate total tokens for a list of batches."""
        total = 0
        for batch in batches:
            # Estimate prompt + content
            # Simple heuristic: 1 token ~= 4 chars (English) or 1 char (CJK)
            # Use analysis.count_tokens if available for better accuracy
            prompt_tokens, _ = count_tokens(batch.system_prompt)
            content_tokens, _ = count_tokens("\n".join(batch.lines))
            total += prompt_tokens + content_tokens
        return total

    def estimate_tokens_saved(self, batches: List[RequestBatch]) -> int:
        """Estimate tokens saved by quote stripping.
        
        Args:
            batches: List of batches with quote_info populated.
            
        Returns:
            Estimated number of tokens saved.
        """
        total = 0
        for batch in batches:
            # Each stripped quote pair saves approximately 2 tokens
            total += len(batch.quote_info) * 2
        return total

