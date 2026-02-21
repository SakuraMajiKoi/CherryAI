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

from .glossary import (
    read_unified_glossary,
    GlossaryEntry,
    TYPE_NAME,
    TYPE_TERM,
    filter_glossary_for_chunk,
    GLOSSARY_FILTER_ALL,
    GLOSSARY_FILTER_ORIGINAL,
    GLOSSARY_FILTER_BOTH,
)
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
# Context-Type Prompt Templates (Phase 50)
# =============================================================================
# Short instruction snippets injected into the system prompt based on the
# detected or inherited context type of a request.

CONTEXT_PROMPT_DIALOGUE = (
    "# Content Type: Dialogue\n"
    "These lines are character dialogue. "
    "Pay attention to the speaker names, maintain consistent voice and tone "
    "for each character, and preserve emotional nuances in the conversation."
)

CONTEXT_PROMPT_MENU = (
    "# Content Type: Menu\n"
    "These lines are menu items from a game UI. "
    "Translate each item concisely and clearly. Preserve formatting, order, "
    "and any shortcut indicators. Keep translations brief and action-oriented."
)

CONTEXT_PROMPT_CHOICE = (
    "# Content Type: Choices\n"
    "These lines are player choices or options. "
    "Translate each choice concisely and distinctly so the player can "
    "differentiate between options. Preserve numbering or bullet formatting."
)

CONTEXT_PROMPT_UNKNOWN = (
    "# Content Type: Mixed\n"
    "These lines may contain dialogue, menu items, or choices. "
    "Translate each line appropriately based on its apparent purpose. "
    "Maintain formatting and keep menu/choice items concise."
)

_CONTEXT_PROMPT_MAP: Dict[str, str] = {
    "dialogue": CONTEXT_PROMPT_DIALOGUE,
    "menu": CONTEXT_PROMPT_MENU,
    "choice": CONTEXT_PROMPT_CHOICE,
    "unknown": CONTEXT_PROMPT_UNKNOWN,
}


def get_context_prompt(context_type: str) -> str:
    """Return the prompt snippet for the given context type.

    Args:
        context_type: ``"dialogue"``, ``"menu"``, ``"choice"``, or ``"unknown"``.

    Returns:
        Prompt instruction block (may be empty if *context_type* is not recognised).
    """
    return _CONTEXT_PROMPT_MAP.get(context_type, "")


# =============================================================================
# REQUEST FORMATION (4-STEP PROCESS) — Phase 49
# =============================================================================


@dataclass
class LineInfo:
    """Lightweight line representation for request formation.

    Attributes:
        index: Original manifest line index (0-based).
        text: Text to translate (prepro or orig).
        is_invalid: True for placeholder, dedup, or context marker lines.
        context_marker: Optional marker type (``"file_end"``, ``"dialogue"``,
            ``"menu"``, ``"choice"``).  ``None`` means no marker.
    """

    index: int
    text: str
    is_invalid: bool = False
    context_marker: Optional[str] = None


@dataclass
class RequestFormationConfig:
    """Configuration for the 4-step request formation process.

    Attributes:
        max_lines: Hard maximum lines per request.
        min_lines: Soft minimum — requests below this are merged (Step 4).
        max_tokens: Token limit per request (0 = no token limit).
        model: Model name for token counting.
    """

    max_lines: int = 50
    min_lines: int = 10
    max_tokens: int = 0
    model: str = "gpt-4o"


@dataclass
class TranslationRequest:
    """A structured translation request produced by :func:`build_requests`.

    Attributes:
        lines: Translatable line texts (invalid lines excluded).
        line_indices: Original manifest indices corresponding to *lines*.
        context_type: ``"dialogue"``, ``"menu"``, ``"choice"``, or ``"unknown"``.
        is_split: ``True`` if this request was created by size-based splitting.
        provides_context: Whether this request provides rolling context forward.
        receives_context: Whether this request receives rolling context from prior.
    """

    lines: List[str] = field(default_factory=list)
    line_indices: List[int] = field(default_factory=list)
    context_type: str = "unknown"
    is_split: bool = False
    provides_context: bool = True
    receives_context: bool = True
    _file_section: int = 0  # Internal: file-section id (Step 2 groups)

    @property
    def line_count(self) -> int:
        """Number of translatable lines in this request."""
        return len(self.lines)


# ---- Step helpers ----------------------------------------------------------


def _extract_valid_lines(
    line_infos: List[LineInfo],
) -> Tuple[List[LineInfo], List[LineInfo]]:
    """Separate valid (translatable) lines from invalid lines.

    Args:
        line_infos: Full list of line info objects.

    Returns:
        Tuple of (valid_lines, invalid_lines).
    """
    valid: List[LineInfo] = []
    invalid: List[LineInfo] = []
    for li in line_infos:
        if li.is_invalid:
            invalid.append(li)
        else:
            valid.append(li)
    return valid, invalid


def _step1_split_menu_choice(
    line_infos: List[LineInfo],
) -> Tuple[List[TranslationRequest], List[LineInfo]]:
    """Step 1: Split Menu and Choice blocks into their own requests.

    Consecutive lines with the same ``context_marker`` of ``"menu"`` or
    ``"choice"`` are grouped into dedicated requests.  All other valid
    lines are returned as remaining for subsequent steps.

    Args:
        line_infos: Translatable line infos (invalid lines already removed).

    Returns:
        Tuple of (menu_choice_requests, remaining_line_infos).
    """
    requests: List[TranslationRequest] = []
    remaining: List[LineInfo] = []
    current_block: List[LineInfo] = []
    current_marker: Optional[str] = None

    def _flush_block() -> None:
        if not current_block:
            return
        req = TranslationRequest(
            lines=[li.text for li in current_block],
            line_indices=[li.index for li in current_block],
            context_type=current_marker or "unknown",
            provides_context=False,
            receives_context=False,
        )
        requests.append(req)

    for li in line_infos:
        marker = li.context_marker
        if marker in ("menu", "choice"):
            if marker == current_marker:
                current_block.append(li)
            else:
                _flush_block()
                current_block = [li]
                current_marker = marker
        else:
            _flush_block()
            current_block = []
            current_marker = None
            remaining.append(li)

    _flush_block()
    return requests, remaining


def _step2_split_at_file_boundaries(
    line_infos: List[LineInfo],
) -> List[List[LineInfo]]:
    """Step 2: Split remaining lines at File End context markers.

    Each file boundary produces a separate candidate group.  Lines with
    ``context_marker == "file_end"`` act as separators and are discarded
    (they are invalid and already excluded from valid lines, but if they
    somehow appear here they are dropped).

    Args:
        line_infos: Remaining valid lines after Step 1.

    Returns:
        List of line-info groups (one per file section).
    """
    if not line_infos:
        return []

    groups: List[List[LineInfo]] = []
    current: List[LineInfo] = []

    for li in line_infos:
        if li.context_marker == "file_end":
            if current:
                groups.append(current)
                current = []
            # file_end itself is dropped
        else:
            current.append(li)

    if current:
        groups.append(current)

    return groups if groups else [line_infos]


def _count_tokens_for_lines(texts: List[str], model: str = "gpt-4o") -> int:
    """Estimate total tokens for a list of line texts.

    Uses :func:`analysis.count_tokens` (char-based estimate) as a fast
    fallback when tiktoken is not available.

    Args:
        texts: Line texts.
        model: Model name (unused currently; reserved for tiktoken).

    Returns:
        Estimated token count.
    """
    total = 0
    for text in texts:
        tokens, _ = count_tokens(text)
        total += tokens
    return total


def _step3_split_and_balance(
    groups: List[List[LineInfo]],
    config: RequestFormationConfig,
) -> List[TranslationRequest]:
    """Step 3: Split oversized groups and balance line counts.

    Each group from Step 2 that exceeds ``config.max_lines`` (or
    ``config.max_tokens`` when > 0) is split into balanced sub-groups.

    Args:
        groups: Line-info groups from Step 2.
        config: Formation configuration.

    Returns:
        List of TranslationRequest objects.
    """
    requests: List[TranslationRequest] = []

    for group in groups:
        if not group:
            continue

        line_count = len(group)

        # Check token limit if configured
        exceeds_tokens = False
        if config.max_tokens > 0:
            total_tokens = _count_tokens_for_lines(
                [li.text for li in group], config.model,
            )
            exceeds_tokens = total_tokens > config.max_tokens

        if line_count <= config.max_lines and not exceeds_tokens:
            # Fits in one request
            ctx = group[0].context_marker if group[0].context_marker in (
                "dialogue", "menu", "choice",
            ) else "unknown"
            requests.append(TranslationRequest(
                lines=[li.text for li in group],
                line_indices=[li.index for li in group],
                context_type=ctx,
            ))
            continue

        # Need to split — calculate number of sub-groups
        if config.max_tokens > 0 and exceeds_tokens:
            total_tokens = _count_tokens_for_lines(
                [li.text for li in group], config.model,
            )
            n_by_tokens = max(1, -(-total_tokens // config.max_tokens))
            n_by_lines = max(1, -(-line_count // config.max_lines))
            n_splits = max(n_by_tokens, n_by_lines)
        else:
            n_splits = max(1, -(-line_count // config.max_lines))

        # Balance: divide lines as evenly as possible
        base_size = line_count // n_splits
        remainder = line_count % n_splits
        offset = 0
        for i in range(n_splits):
            size = base_size + (1 if i < remainder else 0)
            chunk = group[offset : offset + size]
            if chunk:
                ctx = chunk[0].context_marker if chunk[0].context_marker in (
                    "dialogue", "menu", "choice",
                ) else "unknown"
                requests.append(TranslationRequest(
                    lines=[li.text for li in chunk],
                    line_indices=[li.index for li in chunk],
                    context_type=ctx,
                    is_split=True,
                ))
            offset += size

    return requests


def _step4_merge_short_requests(
    requests: List[TranslationRequest],
    config: RequestFormationConfig,
) -> List[TranslationRequest]:
    """Step 4: Merge short requests below ``config.min_lines``.

    Only requests that would receive no rolling context and provide none
    are candidates for merging.  Merged requests must not exceed
    ``config.max_lines``.

    Args:
        requests: Requests from Step 3.
        config: Formation configuration.

    Returns:
        Optimised list of TranslationRequests.
    """
    if not requests or config.min_lines <= 0:
        return requests

    merged: List[TranslationRequest] = []

    for req in requests:
        if (
            req.line_count >= config.min_lines
            or req.context_type in ("menu", "choice")
        ):
            merged.append(req)
            continue

        # Try to merge with previous request of the same context type
        if merged:
            prev = merged[-1]
            combined = prev.line_count + req.line_count
            same_type = prev.context_type == req.context_type
            same_section = prev._file_section == req._file_section
            fits = combined <= config.max_lines
            # Check token limit
            token_ok = True
            if config.max_tokens > 0 and fits:
                combined_tokens = _count_tokens_for_lines(
                    prev.lines + req.lines, config.model,
                )
                token_ok = combined_tokens <= config.max_tokens

            if same_type and same_section and fits and token_ok:
                prev.lines.extend(req.lines)
                prev.line_indices.extend(req.line_indices)
                prev.is_split = False
                continue

        merged.append(req)

    return merged


def build_requests(
    line_infos: List[LineInfo],
    config: Optional[RequestFormationConfig] = None,
) -> List[TranslationRequest]:
    """Build translation requests using the 4-step formation process.

    This is the shared builder called by both **Estimation** (Step 2) and
    **Translation** (Step 5) to guarantee cost estimates match actual usage.

    The four steps are:

    1. Split Menu/Choice blocks into dedicated requests.
    2. Split remaining lines at file-end boundaries.
    3. Apply max-size limits and balance sub-groups.
    4. Merge short requests below the minimum size.

    Invalid lines (placeholders, dedup, context markers) are excluded
    automatically.

    Args:
        line_infos: List of :class:`LineInfo` for all manifest lines.
        config: Formation configuration.  Uses defaults if ``None``.

    Returns:
        Ordered list of :class:`TranslationRequest` objects.
    """
    if config is None:
        config = RequestFormationConfig()

    # Remove invalid lines BUT keep file_end markers for Step 2
    valid, _ = _extract_valid_lines(line_infos)

    # Collect file_end markers separately — they are boundaries, not content
    file_ends: List[LineInfo] = [
        li for li in line_infos
        if li.is_invalid and li.context_marker == "file_end"
    ]

    if not valid:
        return []

    # Step 1 — split Menu / Choice
    mc_requests, remaining = _step1_split_menu_choice(valid)

    # Step 2 — split at file boundaries
    # Merge file_end markers back into remaining for boundary detection
    boundary_input = sorted(
        remaining + file_ends,
        key=lambda li: li.index,
    )
    groups = _step2_split_at_file_boundaries(boundary_input)

    # Step 3 — size-based splitting and balancing
    dialogue_requests = _step3_split_and_balance(groups, config)

    # Tag file-section IDs so Step 4 does not merge across boundaries
    section_id = 0
    req_idx = 0
    for group in groups:
        if not group:
            continue
        # Count how many requests belong to this group
        group_indices = {li.index for li in group}
        while req_idx < len(dialogue_requests):
            r = dialogue_requests[req_idx]
            if r.line_indices and r.line_indices[0] in group_indices:
                r._file_section = section_id
                req_idx += 1
            else:
                break
        section_id += 1

    # Step 4 — merge short requests (respects file section boundaries)
    dialogue_requests = _step4_merge_short_requests(dialogue_requests, config)

    # Combine: menu/choice first, then dialogue/unknown in original order
    all_requests = mc_requests + dialogue_requests

    # Sort by first line index to maintain document order
    all_requests.sort(key=lambda r: r.line_indices[0] if r.line_indices else 0)

    return all_requests


# ---- LineEntry → LineInfo conversion (Phase 50) ----------------------------


def build_line_infos(
    entries: "List[Any]",
    detected_markers: Optional[List[Optional[str]]] = None,
) -> List[LineInfo]:
    """Create :class:`LineInfo` objects from manifest ``LineEntry`` instances.

    For each entry the function determines:

    * **is_invalid** — ``True`` for context-marker lines, placeholder-only
      lines (``__PROTECTED__``, ``__DEDUP__``, ``__CUSTOM__``), or entries whose
      ``orig`` is empty.
    * **context_marker** — propagated from the ``LineEntry.context_marker``
      field first; if that is ``None``, the ``detected_markers`` list is
      consulted.  Normal (non-marker) lines inherit the *active* context
      type from the most recent preceding marker.

    Args:
        entries: Manifest ``LineEntry`` objects (duck-typed — only ``idx``,
            ``orig``, ``prepro``, ``context_marker``, and
            ``is_context_marker()`` are accessed).
        detected_markers: Optional per-line marker list produced by
            :func:`analysis.detect_context_markers`.  Must be the same
            length as *entries* when provided.

    Returns:
        List of :class:`LineInfo`, one per entry.
    """
    import re as _re

    _PLACEHOLDER_RE = _re.compile(
        r"^(?:__PROTECTED__\d*|__DEDUP_\d+__|__CUSTOM__\d*)$"
    )

    n = len(entries)
    result: List[LineInfo] = []

    # Build a merged marker list: entry.context_marker > detected_markers
    merged: List[Optional[str]] = [None] * n
    for i, entry in enumerate(entries):
        cm = getattr(entry, "context_marker", None)
        if cm is not None:
            merged[i] = cm
        elif detected_markers is not None and i < len(detected_markers):
            merged[i] = detected_markers[i]

    # Determine active context type at each position
    active: List[str] = ["unknown"] * n
    current_ctx = "unknown"
    for i in range(n):
        if merged[i] is not None:
            current_ctx = merged[i]
        active[i] = current_ctx

    for i, entry in enumerate(entries):
        text = getattr(entry, "prepro", None) or getattr(entry, "orig", "")

        # Determine if invalid
        is_marker = getattr(entry, "is_context_marker", lambda: False)()
        is_placeholder = bool(_PLACEHOLDER_RE.match(text.strip())) if text else False
        is_empty = not text.strip()
        invalid = is_marker or is_placeholder or is_empty

        # For marker lines, use the marker type directly;
        # for normal lines, use the active (inherited) context type.
        if is_marker:
            ctx = merged[i]
        else:
            ctx = active[i] if active[i] != "file_end" else "unknown"

        result.append(LineInfo(
            index=getattr(entry, "idx", i),
            text=text,
            is_invalid=invalid,
            context_marker=ctx,
        ))

    return result


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
        self.glossary_filter_mode: str = GLOSSARY_FILTER_ALL  # Phase 52
        self.pov_result: Optional[Dict[str, Any]] = None  # Phase 54
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

    def _construct_system_prompt(
        self,
        lines: List[str],
        context_type: Optional[str] = None,
    ) -> str:
        """Construct the system prompt with game summary, glossary, and conditional instructions.
        
        Injection order (optimized for token savings - TASK 12):
        1. Base prompt template (instructions)
        2. Context-type instructions (Phase 50 — dialogue/menu/choice/unknown)
        3. Game summary (project context - if not empty/placeholder)
        4. Output examples (from output_examples.txt)
        5. Glossary terms (content-based, only if entries found)
        6. Character list (content-based, only if characters found)
        7. Translation style (user preferences)
        8. Conditional instructions (pattern-triggered)
        
        Empty sections are SKIPPED to save tokens.

        Args:
            lines: Batch lines for glossary/conditional matching.
            context_type: Optional context type from request formation
                (``"dialogue"``, ``"menu"``, ``"choice"``, ``"unknown"``).
        """
        prompt_parts = []
        
        # 1. Base prompt template (instructions)
        if self.base_prompt_template:
            prompt_parts.append(self.base_prompt_template)

        # 2. Context-type instructions (Phase 50)
        if context_type:
            ctx_prompt = get_context_prompt(context_type)
            if ctx_prompt:
                prompt_parts.append(ctx_prompt)
        
        # 3. Inject Game Summary (context) - skip if empty or just a template
        if self.game_summary and not self._is_game_summary_empty():
            prompt_parts.append(self.game_summary)
        
        # 4. Output examples (from output_examples.txt)
        output_examples = self._load_output_examples()
        if output_examples:
            prompt_parts.append(f"# Output Format Examples\n{output_examples}")
        
        # 5. Filter glossary entries for this batch (Phase 52)
        relevant_entries = filter_glossary_for_chunk(
            self.glossary, lines, self.glossary_filter_mode,
        )
        
        # 6. Format Glossary Block (conditional - only if terms found with translations)
        entries_with_translation = [e for e in relevant_entries if e.translation]
        if entries_with_translation:
            glossary_block = "# Glossary\nUse these terms strictly:\n"
            for entry in entries_with_translation:
                notes = f" ({entry.notes})" if entry.notes else ""
                glossary_block += f"- {entry.original}: {entry.translation}{notes}\n"
            prompt_parts.append(glossary_block)

        # 7. Add Character List (conditional - only if characters found with translations)
        characters = [e for e in relevant_entries if e.entry_type == TYPE_NAME and e.translation]
        if characters:
            char_block = "# Game Characters\n"
            for char in characters:
                gender = char.gender if char.gender else "Unknown"
                char_block += f"- {char.original}: {char.translation} (Gender: {gender})\n"
            prompt_parts.append(char_block)
        
        # 8. Inject Translation Style (user preferences) - skip if empty
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

        # 9. Narrative Perspective (Phase 54 — only when confidence is high)
        if self.pov_result and self.pov_result.get("confidence") == "high":
            pov_label = {
                "1st": "first",
                "2nd": "second",
                "3rd": "third",
            }.get(self.pov_result["pov"], self.pov_result["pov"])
            pov_block = (
                f"# Narrative Perspective\n"
                f"The narrative uses {pov_label} person perspective. "
                f"Maintain consistent {pov_label} person perspective throughout."
            )
            prompt_parts.append(pov_block)

        # 10. Add Conditional Instructions (pattern-triggered)
        conditional_block = self.conditional_manager.build_conditional_instructions(lines)
        if conditional_block:
            prompt_parts.append(conditional_block.strip())


        return "\n\n".join(prompt_parts)

    def build_edit_tlc_prompt(
        self,
        base_prompt: str,
        lines: List[str],
        components: Optional[Dict[str, bool]] = None,
        character_notes: Optional[List[Dict[str, Any]]] = None,
        code_glossary: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build a system prompt for Edit or TLC passes with configurable components.

        Args:
            base_prompt: The custom Edit or TLC prompt (from PromptsSettings).
            lines: The lines being processed (for glossary term matching).
            components: Dict of component toggles:
                - glossary: Include glossary terms (default True)
                - game_summary: Include game summary (default True)
                - character_notes: Include character notes (default True)
                - code_glossary: Include code glossary (default True)
            character_notes: List of character note dicts from manifest.
            code_glossary: List of code pattern dicts from manifest.

        Returns:
            Assembled system prompt string.

        PHASE 37 (TASK 37.2): Allows Edit/TLC prompts to selectively include
        context components like glossary, game summary, character notes, etc.
        """
        # Default components if not specified
        if components is None:
            components = {
                "glossary": True,
                "game_summary": True,
                "character_notes": True,
                "code_glossary": True,
            }

        prompt_parts: List[str] = []

        # 1. Base Edit/TLC prompt (always included)
        if base_prompt and base_prompt.strip():
            prompt_parts.append(base_prompt.strip())

        # 2. Game summary (conditional)
        if components.get("game_summary", True):
            if self.game_summary and not self._is_game_summary_empty():
                prompt_parts.append(self.game_summary)

        # 3. Glossary terms (conditional)
        if components.get("glossary", True):
            batch_text = "\n".join(lines)
            relevant_entries = []

            for original, entry in self.glossary.items():
                if original in batch_text:
                    relevant_entries.append(entry)

            # Format Glossary Block (only if terms found with translations)
            entries_with_translation = [e for e in relevant_entries if e.translation]
            if entries_with_translation:
                glossary_block = "# Glossary\nUse these terms strictly:\n"
                for entry in entries_with_translation:
                    notes = f" ({entry.notes})" if entry.notes else ""
                    glossary_block += f"- {entry.original}: {entry.translation}{notes}\n"
                prompt_parts.append(glossary_block)

            # Add Character List from glossary (if glossary enabled)
            characters = [e for e in relevant_entries if e.entry_type == TYPE_NAME and e.translation]
            if characters:
                char_block = "# Game Characters\n"
                for char in characters:
                    gender = char.gender if char.gender else "Unknown"
                    char_block += f"- {char.original}: {char.translation} (Gender: {gender})\n"
                prompt_parts.append(char_block)

        # 4. Character notes from manifest (conditional)
        if components.get("character_notes", True) and character_notes:
            char_notes_block = "# Character Notes\n"
            for char_note in character_notes:
                name = char_note.get("name") or char_note.get("original_name", "Unknown")
                notes = char_note.get("notes", "")
                style = char_note.get("speaking_style", "")
                gender = char_note.get("gender", "")
                if notes or style:
                    char_notes_block += f"- {name}"
                    if gender:
                        char_notes_block += f" ({gender})"
                    char_notes_block += ":"
                    if notes:
                        char_notes_block += f" {notes}"
                    if style:
                        char_notes_block += f" [Style: {style}]"
                    char_notes_block += "\n"
            if char_notes_block != "# Character Notes\n":
                prompt_parts.append(char_notes_block)

        # 5. Code database from manifest (conditional)
        # TASK 41.8: Handle Preserve / Translate / Remove actions.
        if components.get("code_glossary", True) and code_glossary:
            code_block = "# Code Patterns\n"
            for pattern in code_glossary:
                pat = pattern.get("pattern", "")
                action = pattern.get("action", "preserve")
                notes = pattern.get("notes", "")
                example = pattern.get("example", "")
                if not pat:
                    continue
                # "Remove" entries are NOT sent to the prompt; they
                # are handled entirely in post-processing.
                if action == "remove":
                    continue
                if action == "translate":
                    hint = notes if notes else "contextually"
                    code_block += f"- Translate [{pat}] as {hint}\n"
                else:
                    # Default "preserve"
                    code_block += f"- Do not translate [{pat}]"
                    if example:
                        code_block += f" (e.g., {example})"
                    code_block += "\n"
            if code_block != "# Code Patterns\n":
                prompt_parts.append(code_block)

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

