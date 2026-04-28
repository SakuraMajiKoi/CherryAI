"""Unified term translation dispatcher.

Routes term translation requests through the mode selected in
Global Options → Utility → Term Translation Mode:

- **Romaji** — Modified Hepburn romanization (built-in, kana only).
- **LLM** — Uses the selected API key and model from Utility settings.

Public API
----------
- :func:`translate_term`      — translate a single term
- :func:`translate_terms`     — translate a list of terms
- :func:`get_current_mode`    — read the configured mode
- :func:`extract_code_segments` — extract bracket-delimited code from text
- :func:`validate_translation_code` — check code preservation in translation
- :func:`prepare_translation_result` — strip, recover, and validate code terms
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Valid modes
MODES = ("Romaji", "LLM")

# Bracket pairs for code segment detection
_BRACKET_PAIRS: Dict[str, str] = {
    "[": "]", "［": "］",
    "{": "}", "｛": "｝",
    "<": ">", "＜": "＞",
    "⟨": "⟩", "⟪": "⟫",
    "〈": "〉", "《": "》",
}
_CLOSING_TO_OPENING: Dict[str, str] = {close: open_ for open_, close in _BRACKET_PAIRS.items()}


# ============================================================================
# Code validation helpers
# ============================================================================

def extract_code_segments(text: str) -> List[str]:
    """Extract bracket-delimited code segments from text.

    Uses balanced bracket matching so ``{{code}}`` closes on the
    second ``}`` rather than the first.

    Args:
        text: Text to scan for code segments.

    Returns:
        List of code segments including their delimiters.
    """
    segments: List[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char in _BRACKET_PAIRS:
            close = _BRACKET_PAIRS[char]
            depth = 1
            start = i
            i += 1
            while i < len(text) and depth > 0:
                if text[i] == char:
                    depth += 1
                elif text[i] == close:
                    depth -= 1
                i += 1
            if depth == 0:
                segments.append(text[start:i])
            continue
        i += 1
    return segments


def _is_balanced_code(text: str) -> bool:
    """Return ``True`` when bracket-delimited code in *text* is balanced."""
    stack: List[str] = []
    openers = set(_BRACKET_PAIRS)
    closers = set(_CLOSING_TO_OPENING)

    for char in text:
        if char in openers:
            stack.append(char)
            continue
        if char in closers:
            if not stack:
                return False
            opener = stack.pop()
            if _BRACKET_PAIRS[opener] != char:
                return False
    return not stack


def _get_full_code_wrapper(text: str) -> Optional[Tuple[str, str]]:
    """Return ``(prefix, suffix)`` if *text* is entirely one balanced code entry."""
    stripped = text.strip()
    if not stripped:
        return None

    segments = extract_code_segments(stripped)
    if len(segments) != 1 or segments[0] != stripped:
        return None

    open_char = stripped[0]
    close_char = _BRACKET_PAIRS.get(open_char)
    if not close_char:
        return None

    prefix_len = 0
    while prefix_len < len(stripped) and stripped[prefix_len] == open_char:
        prefix_len += 1

    suffix_len = 0
    while suffix_len < len(stripped) and stripped[len(stripped) - 1 - suffix_len] == close_char:
        suffix_len += 1

    if prefix_len != suffix_len:
        return None

    return open_char * prefix_len, close_char * suffix_len


def _has_matching_full_code_wrapper(original: str, translated: str) -> bool:
    """Return ``True`` when translated preserves the full-entry code wrapper."""
    wrapper = _get_full_code_wrapper(original)
    if not wrapper:
        return False

    stripped = translated.strip()
    prefix, suffix = wrapper
    if not stripped.startswith(prefix) or not stripped.endswith(suffix):
        return False
    if not _is_balanced_code(stripped):
        return False

    segments = extract_code_segments(stripped)
    return len(segments) == 1 and segments[0] == stripped


def recover_full_code_translation(original: str, translated: str) -> str:
    """Recover missing wrapper code when the original entry is entirely code."""
    stripped = translated.strip()
    if not stripped:
        return stripped

    wrapper = _get_full_code_wrapper(original)
    if not wrapper:
        return stripped
    if _has_matching_full_code_wrapper(original, stripped):
        return stripped

    prefix, suffix = wrapper
    open_char = prefix[0]
    close_char = suffix[0]
    inner = stripped

    while inner.startswith(open_char):
        inner = inner[1:].lstrip()
    while inner.endswith(close_char):
        inner = inner[:-1].rstrip()

    return f"{prefix}{inner}{suffix}"


def validate_translation_code(
    original: str, translated: str,
) -> Tuple[bool, List[str]]:
    """Validate that code segments in *original* are preserved in *translated*.

    Args:
        original: The source term (may contain code).
        translated: The translated term.

    Returns:
        Tuple of ``(is_valid, missing_segments)`` where *is_valid* is
        ``True`` when all code segments are present and *missing_segments*
        lists those that are absent from the translation.
    """
    original_stripped = original.strip()
    translated_stripped = translated.strip()

    orig_codes = extract_code_segments(original_stripped)
    if not orig_codes:
        return True, []

    if len(orig_codes) == 1 and orig_codes[0] == original_stripped:
        if orig_codes[0] in translated_stripped:
            return True, []
        if _has_matching_full_code_wrapper(original_stripped, translated_stripped):
            return True, []
        return False, [orig_codes[0]]

    missing: List[str] = []
    for code in orig_codes:
        if code not in translated_stripped:
            missing.append(code)
    return len(missing) == 0, missing


def prepare_translation_result(
    original: str,
    translated: str,
) -> Tuple[str, bool, List[str]]:
    """Strip, recover, and validate a translated term before storage."""
    candidate = translated.strip()
    candidate = recover_full_code_translation(original, candidate)
    valid, missing = validate_translation_code(original, candidate)
    return candidate, valid, missing


# ============================================================================
# Mode detection
# ============================================================================

def get_current_mode() -> str:
    """Return the Term Translation mode from Global Options.

    Returns:
        One of ``'Romaji'`` or ``'LLM'``.
    """
    try:
        from CherryAI.functions import ini_manager
        mode = ini_manager.get_user_default("utility", "term_translation_mode")
        if mode and mode in MODES:
            return mode
        if mode in ("Simple", "MTL"):
            return "Romaji"
    except Exception:
        pass
    return "Romaji"


def _get_utility_batch_size() -> int:
    """Return the configured batch size for LLM term translation."""
    try:
        from CherryAI.functions import ini_manager
        val = ini_manager.get_user_default("utility", "term_batch_size")
        if val:
            return max(1, int(val))
    except Exception:
        pass
    return 10


# ============================================================================
# Public dispatchers
# ============================================================================

def translate_term(
    term: str,
    source_lang: str = "ja",
    target_lang: str = "en",
    *,
    mode: Optional[str] = None,
    context: str = "",
    prompt_type: str = "glossary",
) -> str:
    """Translate a single term using the active mode.

    Args:
        term: Source-language term.
        source_lang: ISO 639-1 source language code.
        target_lang: ISO 639-1 target language code.
        mode: Override mode (defaults to configured mode).
        context: Optional context hint (used by LLM mode).
        prompt_type: ``'glossary'`` or ``'code'`` — selects the prompt.

    Returns:
        Translated term string.

    Raises:
        RuntimeError: If LLM API call fails.
    """
    if not term or not term.strip():
        return term

    active = mode or get_current_mode()

    if active == "LLM":
        return _translate_llm(
            term, source_lang, target_lang, context,
            prompt_type=prompt_type,
        )
    return _translate_simple(term)


def translate_terms(
    terms: List[str],
    source_lang: str = "ja",
    target_lang: str = "en",
    *,
    mode: Optional[str] = None,
    context: str = "",
    prompt_type: str = "glossary",
) -> List[str]:
    """Translate a list of terms using the active mode.

    For LLM mode, terms are split into batches of ``term_batch_size``.

    Args:
        terms: List of source-language terms.
        source_lang: ISO 639-1 source language code.
        target_lang: ISO 639-1 target language code.
        mode: Override mode (defaults to configured mode).
        context: Optional context hint (used by LLM mode).
        prompt_type: ``'glossary'`` or ``'code'`` — selects the prompt.

    Returns:
        List of translated terms (same length as input).

    Raises:
        RuntimeError: If any LLM API batch fails.
    """
    if not terms:
        return []

    active = mode or get_current_mode()

    if active == "LLM":
        batch_size = _get_utility_batch_size()
        results: List[str] = []
        for i in range(0, len(terms), batch_size):
            batch = terms[i : i + batch_size]
            results.extend(
                _translate_llm_batch(
                    batch, source_lang, target_lang, context,
                    prompt_type=prompt_type,
                ),
            )
        return results
    return [_translate_simple(t) for t in terms]


# ============================================================================
# Romaji mode (romanization)
# ============================================================================

def _translate_simple(term: str) -> str:
    """Romanize a term using Modified Hepburn."""
    from CherryAI.functions.romanization import (
        capitalize_name,
        romanize_if_japanese,
    )
    result = romanize_if_japanese(term)
    if result != term:
        return capitalize_name(result)
    return term


# ============================================================================
# LLM mode
# ============================================================================

_LANG_NAMES = {
    "ja": "Japanese", "en": "English", "ko": "Korean",
    "zh": "Chinese", "de": "German", "fr": "French",
    "es": "Spanish", "pt": "Portuguese", "ru": "Russian",
    "it": "Italian",
}


def _lang_name(code: str) -> str:
    """Return human name for language code."""
    return _LANG_NAMES.get(code, code)


def _translate_llm(
    term: str, source_lang: str, target_lang: str, context: str = "",
    *, prompt_type: str = "glossary",
) -> str:
    """Translate a single term using the configured LLM provider.

    Raises:
        RuntimeError: On API failure.
    """
    results = _translate_llm_batch(
        [term], source_lang, target_lang, context,
        prompt_type=prompt_type,
    )
    return results[0] if results else term


# JSON Schema for strict structured output — limits response to exact fields.
_TERM_TRANSLATION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "term_translations",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["translations"],
            "additionalProperties": False,
        },
    },
}


def _get_prompt_template(prompt_type: str) -> str:
    """Read the configurable prompt template from CherryAI.ini [prompts].

    Falls back to the compiled-in defaults from global_options.py.
    """
    from CherryAI.gui.dialogs.global_options import (
        DEFAULT_TERM_CODE_PROMPT,
        DEFAULT_TERM_GLOSSARY_PROMPT,
    )

    ini_key = "term_code" if prompt_type == "code" else "term_glossary"
    default = (
        DEFAULT_TERM_CODE_PROMPT if prompt_type == "code"
        else DEFAULT_TERM_GLOSSARY_PROMPT
    )
    try:
        from CherryAI.functions import ini_manager
        val = ini_manager.get_user_default("prompts", ini_key)
        if val:
            return val
    except Exception:
        pass
    return default


def _translate_llm_batch(
    terms: List[str],
    source_lang: str,
    target_lang: str,
    context: str = "",
    *,
    prompt_type: str = "glossary",
) -> List[str]:
    """Translate a batch of terms via the LLM API.

    Uses strict JSON-schema structured output, ``store=False`` and a
    ``max_tokens`` cap to minimise output-token waste.

    Reads provider/key/model from API.ini ``[term_translation]`` section
    and the prompt template from CherryAI.ini ``[prompts]``.

    Args:
        terms: Terms to translate.
        source_lang: ISO 639-1 source language code.
        target_lang: ISO 639-1 target language code.
        context: Extra context appended to the prompt.
        prompt_type: ``'glossary'`` or ``'code'``.

    Raises:
        RuntimeError: When the API call fails or returns bad data.
    """
    if not terms:
        return []

    import json

    src = _lang_name(source_lang)
    tgt = _lang_name(target_lang)

    template = _get_prompt_template(prompt_type)
    system_prompt = template.format(
        source_lang=src,
        target_lang=tgt,
        count=len(terms),
    )
    if context:
        system_prompt += f"\nContext: {context}"

    term_list = "\n".join(f"- {t}" for t in terms)
    user_content = f"Translate these terms:\n{term_list}"

    # Read API settings from API.ini [term_translation] section
    from CherryAI.functions import api_config

    provider = api_config.get_profile_setting(
        "term_translation", "provider",
    ) or "openai"
    key_name = api_config.get_profile_setting(
        "term_translation", "key_name",
    ) or "default"
    model = api_config.get_profile_setting(
        "term_translation", "model",
    ) or "gpt-4.1-nano"

    api_key = api_config.get_api_key_plain(provider, key_name)
    if not api_key:
        raise RuntimeError(
            f"No API key found for provider '{provider}', "
            f"name '{key_name}'. Configure it in Global Options → Utility."
        )

    base_url = api_config.get_profile_setting(
        "term_translation", "base_url",
    ) or None

    import importlib
    openai_mod = importlib.import_module("openai")
    client_cls = getattr(openai_mod, "OpenAI")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = client_cls(**kwargs)

    # Generous but bounded token budget: ~20 tokens per term.
    max_tokens = max(100, len(terms) * 20)

    try:
        from .api_log import (
            FAILURE_KIND_API,
            FAILURE_KIND_INFERENCE,
            LogCategory,
            LogEntryReceived,
            LogEntrySent,
            LogStatus,
            VALIDATION_STATUS_FAILED,
            VALIDATION_STATUS_PASSED,
            VALIDATION_STATUS_RECOVERED,
            VALIDATION_STATUS_UNKNOWN,
            get_api_log_store,
        )

        sent_entry = LogEntrySent(
            task_type="glossary",
            model=model,
            provider=provider,
            system_prompt=system_prompt,
            user_content=user_content,
            line_count=len(terms),
        )
    except Exception:
        sent_entry = None

    def _log_term_translation(
        status: Any,
        *,
        response_obj: Optional[Any] = None,
        content_text: str = "",
        error_message: str = "",
        validation_status: str = "",
        validation_error: str = "",
        validation_category: str = "",
        failure_kind: str = "",
    ) -> None:
        if sent_entry is None:
            return
        try:
            store = get_api_log_store()
            usage = getattr(response_obj, "usage", None) if response_obj is not None else None
            extra: dict[str, Any] = {}
            if validation_status:
                extra["validation_status"] = validation_status
            if validation_error:
                extra["validation_error"] = validation_error
            if validation_category:
                extra["validation_category"] = validation_category
            if failure_kind:
                extra["failure_kind"] = failure_kind
            store.log_pair(
                LogCategory.TERM_TRANSLATION,
                sent_entry,
                LogEntryReceived(
                    content=content_text,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                    total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
                    error_message=error_message,
                    extra=extra,
                ),
                status,
            )
        except Exception:
            pass

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format=_TERM_TRANSLATION_SCHEMA,
            temperature=0.3,
            max_tokens=max_tokens,
            store=False,
        )
    except Exception as exc:
        _log_term_translation(
            LogStatus.FAILED,
            error_message=str(exc),
            validation_status=VALIDATION_STATUS_UNKNOWN,
            validation_error=str(exc),
            failure_kind=FAILURE_KIND_API,
        )
        raise RuntimeError(
            f"LLM term translation API call failed: {exc}"
        ) from exc

    content = response.choices[0].message.content or ""

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        message = f"LLM returned invalid JSON: {exc}"
        _log_term_translation(
            LogStatus.FAILED,
            response_obj=response,
            content_text=content,
            error_message=message,
            validation_status=VALIDATION_STATUS_FAILED,
            validation_error=str(exc),
            validation_category="non_structured_output",
            failure_kind=FAILURE_KIND_INFERENCE,
        )
        raise RuntimeError(
            f"LLM returned invalid JSON: {exc}"
        ) from exc

    translations = data.get("translations", [])
    if len(translations) != len(terms):
        message = (
            f"LLM returned {len(translations)} translations for {len(terms)} terms"
        )
        _log_term_translation(
            LogStatus.RECOVERED,
            response_obj=response,
            content_text=content,
            validation_status=VALIDATION_STATUS_RECOVERED,
            validation_error=message,
            validation_category="line_count_mismatch",
            failure_kind=FAILURE_KIND_INFERENCE,
        )
        logger.warning(
            "LLM returned %d translations for %d terms — padding/truncating",
            len(translations), len(terms),
        )
        return (translations + terms[len(translations):])[:len(terms)]

    _log_term_translation(
        LogStatus.SUCCESS,
        response_obj=response,
        content_text=content,
        validation_status=VALIDATION_STATUS_PASSED,
    )
    return translations
