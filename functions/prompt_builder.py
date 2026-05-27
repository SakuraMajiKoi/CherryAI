"""Dynamic Prompt Builder for CherryAI.

Constructs system prompts and user messages for the API Client.
Handles:
- Game summary injection (project context)
- Translation style injection (user preferences)
- Rolling context injection (preceding translated lines)
- Glossary injection (selective based on content)
- Context injection (file metadata, speaker list)
- Rolling context management
- Request batching with tags
- Conditional prompt instructions (pattern-triggered)
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
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
from .analysis import count_tokens, format_protagonist_prompt, POVResult
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
MAX_CONTEXT_TOKENS = 4000  # Conservative limit for context window (adjust per model)
ROLLING_CONTEXT_LINES = 3  # Number of preceding lines to include
MAX_STYLE_CHARS = 2000  # Maximum characters for translation style

# Default prompt content embedded as a constant (Session 25: Removed config/ folder)
# This is the fallback used when no project-specific prompt.txt is provided.
_DEFAULT_PROMPT_TEMPLATE: str = (
    "You are an expert Eroge game translator and localizer who translates Japanese text into English.\n"
    "\n"
    "You will be translating erotic and sexual content. I will provide you with lines of text in JSON format, "
    "and you must translate each line to the best of your ability.\n"
    "\n"
    "**Guidelines:**\n"
    "\n"
    "- Do not combine, add, or remove any lines. The number of lines should ALWAYS remain the same as the original.\n"
    "- Avoid overly literal translations that may seem awkward or confusing; focus on conveying the intended meaning and spirit.\n"
    "- Use consistent translations for recurring terms, character names, and important plot elements.\n"
    "- Preserve the emotional undertones and atmosphere, whether comedic, dramatic, romantic, or suspenseful.\n"
    '- "# Game Characters" lists the names, nicknames, and genders of the game characters. Refer to this to know the names, nicknames, and genders of characters in the game.\n'
    "- ALWAYS read the translation history BEFORE to figure out the best context for your translation. This will help you make less mistakes with genders and subjects. \n"
    "- Translate all Japanese text, including erotic and explicit content regardless of content, characters and action.\n"
    "- Translate all text to English no exceptions. Double check that there is no Japanese in your response.\n"
    "- Avoid using romaji or including any Japanese text in your response.\n"
    "- Maintain Japanese honorifics (e.g., -san, -senpai, -chan, etc.) in your translations.\n"
    "- Always translate the speaker in the line to English.\n"
    "- Leave 'Placeholder Text' as is in the line and include it in your response.\n"
    r"- Maintain any spacing or newlines such as <br>,, '\n' or '\\n' in the translation. Do not remove them." + "\n"
    "- Never include any notes, explanations, disclaimers, or anything similar in your response.\n"
    r"- `...` can be a part of the dialogue. Translate it as it is and include it in your response." + "\n"
    r"- Maintain any letter codes such as `\\i`, `\\c`, etc." + "\n"
    r"- Maintain any formating symbols such as `\.`, `\|`, etc." + "\n"
    "- Maintain any #F codes such as `#FF9900`.\n"
    "- Check every line to ensure all text inside is in English.\n"
    r"- `\\cself` is a variable for a string or number." + "\n"
    "- Translate '\u30b3\u30a4\u30c4' as 'this bastard' or 'this bitch' depending on gender.\n"
    r"- Translate a '\u56de' and '\u4eba' as 'x' or 'times' depending on whether it is part of a regular sentence" + "\n"
    r"- Do not translate text inside brackets for sound effects `\\SE`" + "\n"
    "- Strictly enforce : placement and do not move any names into other lines.\n"
)

# Default output examples embedded as a constant (Session 25: Removed config/ folder)
_DEFAULT_OUTPUT_EXAMPLES: str = (
    "Input:\n"
    '{\n    "lines": ["Defense Member E: ...", "Kurone: \u3042\u306e\u3055"]\n}\n'
    "Output:\n"
    '{\n    "translations": ["Defense Member E: ...", "Kurone: Hey."]\n}\n'
    "\n"
    "Input:\n"
    '{\n    "lines": ["\u30cf\u30fc\u30c8\u304c\u53ef\u611b\u3044\u30d4\u30f3\u30af\u8272\u306e\u30c1\u30e3\u30fc\u30e0\u3002"]\n}\n'
    "Output:\n"
    '{\n    "translations": ["A cute pink heart charm."]\n}\n'
)

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

    First checks ``user/CherryAI.ini [prompts]`` for a user override, then
    falls back to the built-in constants above.

    Args:
        context_type: ``"dialogue"``, ``"menu"``, ``"choice"``, or ``"unknown"``.

    Returns:
        Prompt instruction block (may be empty if *context_type* is not recognised).
    """
    # Try reading a user-customised value from the INI.
    try:
        from .ini_manager import get_conditional_prompt
        ini_val = get_conditional_prompt(context_type, "")
        if ini_val:
            return ini_val
    except Exception:
        pass

    # Fall back to the hardcoded constant.
    return _CONTEXT_PROMPT_MAP.get(context_type, "")


# =============================================================================
# PLACEHOLDER DETECTION (shared by Formation, Estimation, and Translation)
# =============================================================================

# Matches any placeholder token produced by CherryAI's preprocessing pipeline.
# All tool-generated placeholders follow the ``__WORD__`` convention:
# ``__PROTECTED__``, ``__PROTECTED_1__``, ``__COLOR__``, ``__FONT_2__``,
# ``__CODE_PROTECTED_5__``, ``__DEDUP__``, ``__CUSTOM__``, ``__NAME__``,
# ``__TEMPREPL_0_1__``, ``__PROT__`` (legacy), and any user-defined token.
_PLACEHOLDER_TOKEN_RE = re.compile(
    r"__[A-Z][A-Z0-9_]*__",
    re.IGNORECASE,
)

# Matches lines that consist only of dots/periods and whitespace.
# These are non-translatable ellipsis or separator lines that should be
# preserved as-is (e.g. "...", "..................", ". . . . .").
_DOTS_ONLY_RE = re.compile(r"^[\s.…．·•・]+$")
_NON_TRANSLATABLE_CONNECTOR_RE = re.compile(r"[\s+\-=:;,./\\|!?*#@&^~()\[\]{}<>]+")


@lru_cache(maxsize=128)
def _build_preserve_pattern_only_regex(
    preserve_patterns: Tuple[str, ...],
) -> Optional[re.Pattern[str]]:
    """Build a cached alternation regex for preserved code patterns."""
    escaped_patterns: List[str] = []
    for pattern in preserve_patterns:
        clean = pattern.strip()
        if not clean:
            continue
        escaped_patterns.append(
            re.escape(clean).replace(re.escape("<NUM>"), r"\d+")
        )

    if not escaped_patterns:
        return None

    alternation = "|".join(f"(?:{pattern})" for pattern in escaped_patterns)
    return re.compile(alternation)


def is_placeholder_only(text: str) -> bool:
    """Return ``True`` when *text* consists entirely of placeholder tokens
    or non-translatable punctuation (dot-only lines).

    A line is "placeholder-only" when, after removing every recognised
    placeholder token (any ``__UPPERCASE_WORD__`` pattern such as
    ``__PROTECTED__``, ``__DEDUP__``, ``__COLOR__``, ``__FONT__``,
    ``__TEMPREPL_0_1__``, and user-defined tokens), nothing but
    whitespace remains.

    Lines consisting solely of dots, ellipsis characters, and whitespace
    (e.g. ``"..."``, ``".................."``, ``". . ."``) are also
    treated as non-translatable.

    Empty / whitespace-only strings return ``False`` (they are handled
    separately as "empty lines").

    Examples::

        >>> is_placeholder_only("__PROTECTED__")
        True
        >>> is_placeholder_only("__DEDUP__  __PROTECTED__")
        True
        >>> is_placeholder_only("__COLOR__ __FONT_1__")
        True
        >>> is_placeholder_only("Text __PROTECTED__")
        False
        >>> is_placeholder_only("[ __PROTECTED__ ]")
        False
        >>> is_placeholder_only("")
        False
        >>> is_placeholder_only("..................")
        True
        >>> is_placeholder_only("...")
        True
    """
    stripped = text.strip()
    if not stripped:
        return False
    # Check for dot-only / ellipsis-only lines
    if _DOTS_ONLY_RE.match(stripped):
        return True
    remaining = _PLACEHOLDER_TOKEN_RE.sub("", stripped)
    return not remaining.strip()


def is_code_pattern_only(
    text: str,
    preserve_patterns: List[str],
) -> bool:
    """Return ``True`` when *text* consists entirely of preserved code patterns.

    A line is "code-pattern-only" when, after removing every occurrence
    of each pattern in *preserve_patterns* (and placeholder tokens and
    whitespace/punctuation connectors), nothing translatable remains.

    This is used as a skip condition: lines that are purely preserved
    code patterns need not be sent to the LLM because the patterns are
    kept verbatim.

    ``<NUM>`` in a pattern is treated as a ``\\d+`` wildcard to match
    concrete numeric instances (e.g. ``<文字色 <NUM>>`` matches
    ``<文字色 255 50 50>``).

    Args:
        text: Line text (preprocessed or original).
        preserve_patterns: Pattern strings from ``code_patterns`` entries
            with ``action="preserve"``.

    Returns:
        ``True`` if the line is entirely composed of preserved code
        patterns (and placeholders / non-translatable glue).
    """
    stripped = text.strip()
    if not stripped:
        return False
    if not preserve_patterns:
        return False

    matcher = _build_preserve_pattern_only_regex(tuple(preserve_patterns))
    if matcher is None:
        return False

    remaining = matcher.sub("", stripped)

    # Also strip placeholders and non-translatable punctuation/whitespace
    remaining = _PLACEHOLDER_TOKEN_RE.sub("", remaining)
    # Remove common non-translatable connectors: whitespace, +, -, =,
    # punctuation that wouldn't need translation on its own.
    remaining = _NON_TRANSLATABLE_CONNECTOR_RE.sub("", remaining)
    return not remaining


# =============================================================================
# REQUEST FORMATION (4-STEP PROCESS) — Phase 49
# =============================================================================


@dataclass
class LineInfo:
    """Lightweight line representation for request formation.

    Attributes:
        index: Original manifest line index (0-based).
        text: Text to translate (prepro or orig).
        is_invalid: True for placeholder, dedup, or tag lines.
        tag: Optional tag type (``"file_end"``, ``"dialogue"``,
            ``"menu"``, ``"choice"``).  ``None`` means no tag.
    """

    index: int
    text: str
    is_invalid: bool = False
    tag: Optional[str] = None


@dataclass
class RequestFormationConfig:
    """Configuration for the 4-step (+1) request formation process.

    Attributes:
        max_lines: Hard maximum lines per request.
        min_lines: Soft minimum — requests below this are merged (Step 4).
        max_tokens: Token limit per request (0 = no token limit).
        model: Model name for token counting.
        efficient_merge: When ``True``, runs a post-formation Step 5 that
            merges small requests **across** file boundaries and context
            types when they carry no rolling context.  Activated by
            ``request_slicing = "efficient"`` in Global Options.
        rolling_context_between: Lines (Between) setting; when > 0, blocks
            merging of requests that would gain between-context.
        rolling_context_after: Lines (After) setting; when > 0, blocks
            merging of requests that would gain after-context.
    """

    max_lines: int = 50
    min_lines: int = 10
    max_tokens: int = 0
    model: str = "gpt-4o"
    efficient_merge: bool = False
    rolling_context_between: int = 0
    rolling_context_after: int = 0


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
    _merge_boundaries: List[int] = field(default_factory=list)
    """Line-count boundaries of original requests that were merged.

    E.g. ``[1, 1, 3]`` means three original requests with 1, 1, and 3 lines
    were merged into a single request of 5 lines.  Empty when the request
    was not produced by merging.
    """

    @property
    def line_count(self) -> int:
        """Number of translatable lines in this request."""
        return len(self.lines)

    @property
    def is_merged(self) -> bool:
        """True when this request is the result of merging multiple requests."""
        return len(self._merge_boundaries) > 1


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

    Consecutive lines with the same ``tag`` of ``"menu"`` or
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
        marker = li.tag
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
    ``tag == "file_end"`` act as separators and are discarded
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
        if li.tag == "file_end":
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
        tokens, _ = count_tokens(text, model=model)
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
            ctx = group[0].tag if group[0].tag in (
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
                ctx = chunk[0].tag if chunk[0].tag in (
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


def _step5_efficient_merge(
    requests: List[TranslationRequest],
    config: RequestFormationConfig,
) -> List[TranslationRequest]:
    """Step 5 — cross-file merge of small context-free requests.

    Only runs when ``config.efficient_merge`` is ``True`` (Efficient
    request-slicing mode).  Merges consecutive requests that carry **no**
    rolling context, regardless of file section or context type, up to the
    configured ``max_lines`` / ``max_tokens`` limits.

    A request is considered a *merge candidate* when:

    * ``receives_context`` is ``False`` (no before-context dependency).
    * The *next* request in document order also has ``receives_context``
      ``False`` — meaning this request does not feed a context chain.
    * It is not a ``"menu"`` or ``"choice"`` context type.

    In practice this targets singleton file-section requests (one request
    per file) which are common in Efficient mode with large chunk sizes.

    If ``rolling_context_between`` or ``rolling_context_after`` are
    configured and there is a line-index gap between two candidate
    requests, the merge is blocked to preserve the runtime context.

    Merged requests record original block sizes in ``_merge_boundaries``
    so that a conditional prompt can describe block relatedness.

    Args:
        requests: Ordered requests from Steps 1–4.
        config: Formation configuration.

    Returns:
        Optimised list with small context-free requests merged.
    """
    if not requests or not config.efficient_merge:
        return requests

    n = len(requests)

    def _is_candidate(idx: int) -> bool:
        req = requests[idx]
        if req.context_type in ("menu", "choice"):
            return False
        if req.receives_context:
            return False
        # If the *next* request depends on this one for rolling context,
        # merging would break the chain.
        if idx + 1 < n and requests[idx + 1].receives_context:
            return False
        return True

    candidate_set = {i for i in range(n) if _is_candidate(i)}
    if not candidate_set:
        return requests

    merged: List[TranslationRequest] = []
    prev_is_candidate = False

    for i, req in enumerate(requests):
        is_cand = i in candidate_set

        if is_cand and prev_is_candidate and merged:
            prev = merged[-1]
            combined = prev.line_count + req.line_count
            fits = combined <= config.max_lines

            # Block merge when between/after context configured and a gap
            # exists (skipped lines between the two requests).
            gap_blocked = False
            if fits and (
                config.rolling_context_between > 0
                or config.rolling_context_after > 0
            ):
                prev_last = (
                    max(prev.line_indices) if prev.line_indices else -1
                )
                req_first = (
                    min(req.line_indices) if req.line_indices else -1
                )
                if req_first - prev_last > 1:
                    gap_blocked = True

            token_ok = True
            if config.max_tokens > 0 and fits and not gap_blocked:
                combined_tokens = _count_tokens_for_lines(
                    prev.lines + req.lines, config.model,
                )
                token_ok = combined_tokens <= config.max_tokens

            if fits and not gap_blocked and token_ok:
                if not prev._merge_boundaries:
                    prev._merge_boundaries = [prev.line_count]
                prev._merge_boundaries.append(req.line_count)
                prev.lines.extend(req.lines)
                prev.line_indices.extend(req.line_indices)
                prev.is_split = False
                continue

        merged.append(req)
        prev_is_candidate = is_cand

    return merged


def build_requests(
    line_infos: List[LineInfo],
    config: Optional[RequestFormationConfig] = None,
) -> List[TranslationRequest]:
    """Build translation requests using the 4+1 step formation process.

    This is the shared builder called by both **Estimation** (Step 2) and
    **Translation** (Step 5) to guarantee cost estimates match actual usage.

    The steps are:

    1. Split Menu/Choice blocks into dedicated requests.
    2. Split remaining lines at file-end boundaries.
    3. Apply max-size limits and balance sub-groups.
    4. Merge short requests below the minimum size.
    5. *(Efficient mode only)* Merge small context-free requests across
       file boundaries — see :func:`_step5_efficient_merge`.

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
        if li.is_invalid and li.tag == "file_end"
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
        first_in_section = True
        while req_idx < len(dialogue_requests):
            r = dialogue_requests[req_idx]
            if r.line_indices and r.line_indices[0] in group_indices:
                r._file_section = section_id
                # First request of a file section has no prior context
                if first_in_section:
                    r.receives_context = False
                    first_in_section = False
                req_idx += 1
            else:
                break
        section_id += 1

    # Step 4 — merge short requests (respects file section boundaries)
    dialogue_requests = _step4_merge_short_requests(dialogue_requests, config)

    # Combine: menu/choice first, then dialogue/unknown in original order
    all_requests = mc_requests + dialogue_requests

    # Sort by first line index to maintain document order
    all_requests.sort(
        key=lambda r: r.line_indices[0] if r.line_indices else 0,
    )

    # Step 5 — efficient cross-file merge (only in Efficient mode)
    if config.efficient_merge:
        all_requests = _step5_efficient_merge(all_requests, config)

    return all_requests


# Priority order: lower number = higher priority (processed first).
_CONTEXT_TYPE_PRIORITY: Dict[str, int] = {
    "dialogue": 0,
    "choice": 1,
    "mixed": 2,
    "unknown": 2,
    "menu": 3,
}


@dataclass
class RequestString:
    """A chain of requests linked by rolling context.

    Requests that share a rolling-context dependency (``provides_context``
    → ``receives_context`` chain within the same file section) form a
    *string*.  Strings must be executed sequentially, but independent
    strings can run in parallel.

    Attributes:
        requests: Ordered requests in the chain.
        context_type: Dominant context type for sorting.
        has_rolling_context: Whether the string uses rolling context.
    """

    requests: List[TranslationRequest] = field(default_factory=list)
    context_type: str = "unknown"
    has_rolling_context: bool = False

    @property
    def priority(self) -> int:
        """Sorting priority (lower = higher priority)."""
        return _CONTEXT_TYPE_PRIORITY.get(self.context_type, 2)

    @property
    def line_count(self) -> int:
        """Total translatable lines across all requests in the string."""
        return sum(r.line_count for r in self.requests)


def sort_requests_by_type(
    requests: List[TranslationRequest],
) -> List[RequestString]:
    """Group and sort requests by context type and rolling-context chains.

    Produces a list of :class:`RequestString` objects sorted by:

    1. **Context type priority**: Dialogue > Choice > Mixed/Unknown > Menu.
    2. **Rolling context**: Strings with rolling context before standalone.
    3. **Size (descending)**: Longer strings first within each priority.

    Requests within a rolling-context chain maintain their original
    document order (they must execute sequentially).

    Args:
        requests: Formation-pipeline output from :func:`build_requests`.

    Returns:
        Sorted list of :class:`RequestString` objects.
    """
    if not requests:
        return []

    # --- Phase 1: Build strings (rolling-context chains) ---
    strings: List[RequestString] = []
    current_chain: List[TranslationRequest] = []
    current_section: int | None = None

    for req in requests:
        section = getattr(req, "_file_section", 0)

        # Start a new chain when:
        #  - This is the first request
        #  - This request does not receive context (start of a new chain)
        #  - We crossed a file section boundary
        if (
            not current_chain
            or not req.receives_context
            or section != current_section
        ):
            # Flush the previous chain
            if current_chain:
                strings.append(_build_string(current_chain))
            current_chain = [req]
            current_section = section
        else:
            current_chain.append(req)

    if current_chain:
        strings.append(_build_string(current_chain))

    # --- Phase 2: Sort strings ---
    strings.sort(key=lambda s: (
        s.priority,               # Type priority (dialogue first)
        0 if s.has_rolling_context else 1,  # RC chains before standalone
        -s.line_count,            # Longer strings first
    ))

    return strings


def _build_string(chain: List[TranslationRequest]) -> RequestString:
    """Build a :class:`RequestString` from a chain of requests."""
    # Dominant context type = most common among the chain
    type_counts: Dict[str, int] = {}
    for req in chain:
        ct = req.context_type or "unknown"
        type_counts[ct] = type_counts.get(ct, 0) + req.line_count

    dominant = max(type_counts, key=type_counts.get)  # type: ignore[arg-type]
    has_rc = len(chain) > 1 and any(r.receives_context for r in chain)

    return RequestString(
        requests=list(chain),
        context_type=dominant,
        has_rolling_context=has_rc,
    )


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
    * **tag** — propagated from the ``LineEntry.tag``
      field first; if that is ``None``, the ``detected_markers`` list is
      consulted.  Normal (non-marker) lines inherit the *active* context
      type from the most recent preceding marker.

    Args:
        entries: Manifest ``LineEntry`` objects (duck-typed — only ``idx``,
            ``orig``, ``prepro``, ``tag``, and
            ``is_tag()`` are accessed).
        detected_markers: Optional per-line marker list produced by
            :func:`analysis.detect_tags`.  Must be the same
            length as *entries* when provided.

    Returns:
        List of :class:`LineInfo`, one per entry.
    """
    import re as _re

    n = len(entries)
    result: List[LineInfo] = []

    # Build a merged marker list: entry.tag > detected_markers
    merged: List[Optional[str]] = [None] * n
    for i, entry in enumerate(entries):
        cm = getattr(entry, "tag", None)
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
        is_marker = getattr(entry, "is_tag", lambda: False)()
        is_placeholder = is_placeholder_only(text) if text else False
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
            tag=ctx,
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
    style_file: str = "",
    config_dir: Optional[Path] = None,
    max_chars: int = MAX_STYLE_CHARS,
) -> str:
    """Load and clean translation style from file.
    
    Args:
        style_file: Path to style file (relative to config_dir or absolute). Empty = no file.
        config_dir: Directory containing config files
        max_chars: Maximum characters to return (truncates with warning)
        
    Returns:
        Cleaned style text with comments and placeholders removed.
    """
    if not style_file:
        return ""
    
    if config_dir is None:
        config_dir = Path(".")
    
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


def format_rolling_context(
    context_lines: List[str],
    is_translated: bool = True,
    context_type: str = "before",
) -> str:
    """Format rolling context for prompt injection.

    Args:
        context_lines: Lines to include as context.
        is_translated: Whether the lines are already translated.
        context_type: One of ``"before"``, ``"between"``, ``"after"``.

    Returns:
        Formatted context block for the prompt.
    """
    if not context_lines:
        return ""

    _labels = {
        "before": ("Previous translations" if is_translated else "Previous lines"),
        "between": "Translated lines interspersed in this batch",
        "after": ("Following translations" if is_translated else "Following lines"),
    }
    label = _labels.get(context_type, _labels["before"])
    context_text = "\n".join(f"  {line}" for line in context_lines)
    return f"\n[{label} for context - do not re-translate these:]\n{context_text}\n\n"


@dataclass
class RequestBatch:
    """A batch of lines to be sent to the API."""
    lines: List[str]
    indices: List[int]  # Original line indices
    context_before: List[str] = field(default_factory=list)  # Rolling context (before)
    context_between: List[str] = field(default_factory=list)  # Rolling context (between)
    context_after: List[str] = field(default_factory=list)  # Rolling context (after)
    system_prompt: str = ""
    quote_info: List[StrippedQuoteInfo] = field(default_factory=list)

    @property
    def line_count(self) -> int:
        return len(self.lines)

    def get_context_prefix(self) -> str:
        """Get formatted rolling context prefix for user message."""
        return format_rolling_context(self.context_before, context_type="before")

    @property
    def has_rolling_context(self) -> bool:
        """True when any rolling-context slot is populated."""
        return bool(self.context_before or self.context_between or self.context_after)


@dataclass
class RollingContextConfig:
    """Configuration for rolling context feature.

    Attributes:
        enabled: Master toggle for rolling context.
        lines_before: Preceding translated lines included for context.
        lines_between: Translated lines inserted *between* input lines
            when lines in the request were skipped (already-translated
            or non-source-language).  Default 0 (off).
        lines_after: Following translated lines appended after input
            lines for forward context.  Default 0 (off).
        scene_markers: Patterns that reset rolling context.
        use_translated: Prefer translated text over originals when both
            exist.  Falls back to original when translated is unavailable.
    """
    enabled: bool = True
    lines_before: int = 3
    lines_between: int = 0
    lines_after: int = 0
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
        # Parse integer fields robustly
        def _int(val: Any, default: int) -> int:
            try:
                return int(val) if val is not None else default
            except Exception:
                return default

        lines_before_val = _int(rc_section.get("lines_before", 3), 3)
        lines_between_val = _int(rc_section.get("lines_between", 0), 0)
        lines_after_val = _int(rc_section.get("lines_after", 0), 0)
        return cls(
            enabled=enabled_val,
            lines_before=lines_before_val,
            lines_between=lines_between_val,
            lines_after=lines_after_val,
            scene_markers=markers,
            use_translated=use_translated_val,
        )

class PromptBuilder:
    """Builds dynamic prompts for translation requests."""

    def __init__(
        self,
        config_dir: Path = Path("."),
        project_config: Optional[ProjectConfig] = None,
        rc_config: Optional[RollingContextConfig] = None,
    ):
        """Initialize the prompt builder.
        
        Args:
            config_dir: Optional directory to look for override files (prompt.txt, etc.).
                        Defaults to current directory. Session 25: config/ folder removed.
            project_config: Optional project configuration. If None, loads from INI.
        """
        self.logger = logging.getLogger("cherryai.prompt")
        self.config_dir = config_dir
        self.glossary: Dict[str, GlossaryEntry] = {}
        self.glossary_filter_mode: str = GLOSSARY_FILTER_ALL  # Phase 52
        self.pov_result: Optional[Dict[str, Any]] = None  # Phase 54
        self.characters: List[Dict[str, Any]] = []  # Task 75
        self.code_patterns: List[Dict[str, Any]] = []  # Task 75
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
        
        # Translation style file from config (empty string = no external file)
        trans_section = full_config.get("translation", {})
        self.style_file = trans_section.get("style_file", "")
        
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
                self.base_prompt_template = _DEFAULT_PROMPT_TEMPLATE
        except Exception as e:
            self.logger.error(f"Failed to load prompt template: {e}")
            self.base_prompt_template = _DEFAULT_PROMPT_TEMPLATE
        
        # Load Game Summary
        self._load_game_summary()
        
        # Load Translation Style
        self._load_translation_style()
    
    def _load_game_summary(self) -> None:
        """Load game summary from configured file."""
        summary_file = self.project_config.summary_file if self.project_config else ""
        if not summary_file:
            self.game_summary = ""
            return
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
        """Load output examples from config_dir/output_examples.txt or embedded default.
        
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
        # Fall back to embedded default (Session 25: Removed config/ folder)
        return _DEFAULT_OUTPUT_EXAMPLES
    
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
        """Construct the system prompt for a translation batch (Phase 62 slot order).

        Injection order:
        1. Language direction   — "Translate {source} into {target}." (skipped if both empty)
        2. System Instructions  — base prompt template (eroge translator instructions)
        3. Style                — translation style guide (content-based)
        4. Tone                 — project tone (comedic / dramatic / dark, etc.)
        5. Summary              — game context (skipped if empty / placeholder)
        6. Conditional block    — context-type prompt + POV + pattern-triggered (merged)
        7. Glossary block       — filtered entries with translations (selective, content-based)

        Output examples are **not** injected into the system prompt (Phase 62).
        Rolling context and input lines are handled at the batch level, not here.

        Empty sections are SKIPPED to save tokens.

        Args:
            lines: Batch lines for glossary/conditional matching.
            context_type: Optional context type from request formation
                (``"dialogue"``, ``"menu"``, ``"choice"``, ``"unknown"``).
        """
        prompt_parts = []

        # 1. Language direction header
        source_lang = (
            self.project_config.source_lang if self.project_config and self.project_config.source_lang
            else ""
        )
        target_lang = (
            self.project_config.target_lang if self.project_config and self.project_config.target_lang
            else ""
        )
        if target_lang:
            if source_lang:
                lang_header = f"# Translation Direction\nTranslate {source_lang} into {target_lang}."
            else:
                lang_header = f"# Translation Direction\nTranslate into {target_lang}."
            prompt_parts.append(lang_header)

        # 2. System Instructions (base prompt template)
        if self.base_prompt_template:
            prompt_parts.append(self.base_prompt_template)

        # 3. Style (translation style guide)
        # Ensure style is loaded even if resources were not yet loaded
        if not self.translation_style and self.style_file:
            try:
                self.translation_style = load_translation_style(self.style_file, self.config_dir)
            except Exception:
                self.translation_style = ""
        if not self.translation_style:
            try:
                self.translation_style = load_translation_style("translation_style.txt", self.config_dir)
            except Exception:
                pass
        if self.translation_style and self.translation_style.strip():
            prompt_parts.append(format_style_for_prompt(self.translation_style))

        # 4. Tone (project-level tone field, separate from style)
        tone = (
            self.project_config.tone if self.project_config and self.project_config.tone
            else ""
        )
        if tone and tone.strip():
            prompt_parts.append(f"# Tone\n{tone.strip()}")

        # 4b. Protagonist + Narration (Task 75)
        protagonist_section = ""
        if self.characters or self.code_patterns:
            pov_obj = None
            if self.pov_result:
                pov_obj = POVResult.from_dict(self.pov_result)
            protagonist_section = format_protagonist_prompt(
                self.characters,
                self.code_patterns or None,
                pov_obj,
            )
        if protagonist_section:
            prompt_parts.append(f"# Protagonist\n{protagonist_section}")

        # 5. Game Summary (project context — skip if empty / placeholder)
        if self.game_summary and not self._is_game_summary_empty():
            prompt_parts.append(self.game_summary)

        # 6. Conditional block (POV + pattern-triggered; context-type is now
        #    injected as a separate static slot 5b before this block)
        conditionals: List[str] = []

        # 6a. Context-type instructions (static, cacheable — slot 5b)
        if context_type:
            ctx_prompt = get_context_prompt(context_type)
            if ctx_prompt:
                prompt_parts.append(ctx_prompt.strip())

        # 6b. Narrative Perspective (Phase 54 — skip when protagonist has narration)
        if (
            not protagonist_section
            and self.pov_result
            and self.pov_result.get("confidence") == "high"
        ):
            pov_label = {
                "1st": "first",
                "2nd": "second",
                "3rd": "third",
            }.get(self.pov_result["pov"], self.pov_result["pov"])
            conditionals.append(
                f"# Narrative Perspective\n"
                f"The narrative uses {pov_label} person perspective. "
                f"Maintain consistent {pov_label} person perspective throughout."
            )

        # 6c. Pattern-triggered conditional instructions
        conditional_block = self.conditional_manager.build_conditional_instructions(lines)
        if conditional_block:
            conditionals.append(conditional_block.strip())

        if conditionals:
            prompt_parts.append("\n\n".join(conditionals))

        # 7. Glossary block (selective: entries relevant to this batch, with translations)
        relevant_entries = filter_glossary_for_chunk(
            self.glossary, lines, self.glossary_filter_mode,
        )

        # Build unified glossary block — characters are listed inline with gender
        entries_with_translation = [e for e in relevant_entries if e.translation]
        if entries_with_translation:
            glossary_block_lines = ["# Glossary", "Use these terms strictly:"]
            for entry in entries_with_translation:
                # Build annotation: type, gender, notes
                annotations: List[str] = []
                if entry.entry_type == TYPE_NAME:
                    gender = entry.gender if entry.gender else ""
                    if gender:
                        annotations.append(f"Gender: {gender}")
                if entry.notes:
                    annotations.append(entry.notes)
                annotation = f" ({'; '.join(annotations)})" if annotations else ""
                glossary_block_lines.append(
                    f"- {entry.original}: {entry.translation}{annotation}"
                )
            prompt_parts.append("\n".join(glossary_block_lines))

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
                name = (
                    char_note.get("original_name")
                    or char_note.get("name", "Unknown")
                )
                translation = (
                    char_note.get("translation")
                    or char_note.get("name", "")
                )
                notes = char_note.get("notes", "")
                if notes or translation:
                    char_notes_block += f"- {name}"
                    if translation:
                        char_notes_block += f" → {translation}"
                    if notes:
                        char_notes_block += f": {notes}"
                    char_notes_block += "\n"
            if char_notes_block != "# Character Notes\n":
                prompt_parts.append(char_notes_block)

        # 5. Code database from manifest (conditional)
        if components.get("code_glossary", True) and code_glossary:
            code_block = "# Code Patterns\n"
            for pattern in code_glossary:
                pat = pattern.get("pattern", "")
                action = pattern.get("action", "preserve")
                notes = pattern.get("notes", "")
                example = pattern.get("example", "")
                if not pat:
                    continue
                if action == "provides_context":
                    hint = notes if notes else "contextually"
                    code_block += f"- Translate [{pat}] as {hint}\n"
                else:
                    # Default "preserve" and all other actions
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

