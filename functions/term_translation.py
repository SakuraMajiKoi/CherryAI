"""Unified term translation dispatcher.

Routes term translation requests through the mode selected in
Global Options → Utility → Term Translation Mode:

- **Simple** — Modified Hepburn romanization (built-in).
- **MTL** — Machine translation via EasyNMT / opus-mt.
- **LLM** — Uses the active LLM API provider.

Public API
----------
- :func:`translate_term`      — translate a single term
- :func:`translate_terms`     — translate a list of terms
- :func:`get_current_mode`    — read the configured mode
- :func:`ensure_mtl_ready`    — lazy-install EasyNMT + opus-mt
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Valid modes
MODES = ("Simple", "MTL", "LLM")


# ============================================================================
# Mode detection
# ============================================================================

def get_current_mode() -> str:
    """Return the Term Translation mode from Global Options (default: Simple).

    Returns:
        One of ``'Simple'``, ``'MTL'``, or ``'LLM'``.
    """
    try:
        from CherryAI.functions import ini_manager
        mode = ini_manager.get_user_default("utility", "term_translation_mode")
        if mode and mode in MODES:
            return mode
    except Exception:
        pass
    return "Simple"


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
) -> str:
    """Translate a single term using the active mode.

    Args:
        term: Source-language term.
        source_lang: ISO 639-1 source language code.
        target_lang: ISO 639-1 target language code.
        mode: Override mode (defaults to configured mode).
        context: Optional context hint (used by LLM mode).

    Returns:
        Translated term string.
    """
    if not term or not term.strip():
        return term

    active = mode or get_current_mode()

    if active == "MTL":
        return _translate_mtl(term, source_lang, target_lang)
    if active == "LLM":
        return _translate_llm(term, source_lang, target_lang, context)
    # Default: Simple (romanization)
    return _translate_simple(term)


def translate_terms(
    terms: List[str],
    source_lang: str = "ja",
    target_lang: str = "en",
    *,
    mode: Optional[str] = None,
    context: str = "",
) -> List[str]:
    """Translate a list of terms using the active mode.

    For MTL mode, terms are batched into a single EasyNMT call for
    efficiency.  For LLM mode, all terms are sent in one prompt.

    Args:
        terms: List of source-language terms.
        source_lang: ISO 639-1 source language code.
        target_lang: ISO 639-1 target language code.
        mode: Override mode (defaults to configured mode).
        context: Optional context hint (used by LLM mode).

    Returns:
        List of translated terms (same length as input).
    """
    if not terms:
        return []

    active = mode or get_current_mode()

    if active == "MTL":
        return _translate_mtl_batch(terms, source_lang, target_lang)
    if active == "LLM":
        return _translate_llm_batch(terms, source_lang, target_lang, context)
    return [_translate_simple(t) for t in terms]


# ============================================================================
# Simple mode (romanization)
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
# MTL mode (EasyNMT / opus-mt)
# ============================================================================

_easynmt_model = None  # Lazy singleton


def ensure_mtl_ready() -> None:
    """Install EasyNMT (if needed) and load the opus-mt model.

    EasyNMT and its dependencies are installed into the user's
    normal Python environment on first use.  Models are downloaded
    into the default HuggingFace cache.

    The addon is registered in ``user/addons/addon.ini``.

    Raises:
        ImportError: If ``pip install easynmt`` fails.
    """
    global _easynmt_model
    if _easynmt_model is not None:
        return

    try:
        from easynmt import EasyNMT  # noqa: F401
    except ImportError:
        logger.info("EasyNMT not found — installing via pip…")
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "easynmt"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ImportError(
                f"Failed to install EasyNMT:\n{result.stderr}"
            )
        logger.info("EasyNMT installed successfully")

    from easynmt import EasyNMT
    _easynmt_model = EasyNMT("opus-mt")

    # Register in addon manager
    try:
        from CherryAI.functions.addon_manager import register_addon
        register_addon("easynmt", version="2.0.2", model="opus-mt")
    except Exception:
        pass


def _translate_mtl(term: str, source_lang: str, target_lang: str) -> str:
    """Translate a single term with EasyNMT."""
    ensure_mtl_ready()
    try:
        result = _easynmt_model.translate(
            term, source_lang=source_lang, target_lang=target_lang,
        )
        return result if result else term
    except Exception as exc:
        logger.warning("MTL translation failed for '%s': %s", term, exc)
        return term


def _translate_mtl_batch(
    terms: List[str], source_lang: str, target_lang: str,
) -> List[str]:
    """Translate a batch of terms with EasyNMT."""
    ensure_mtl_ready()
    try:
        results = _easynmt_model.translate(
            terms, source_lang=source_lang, target_lang=target_lang,
        )
        if isinstance(results, list) and len(results) == len(terms):
            return results
        return [str(r) for r in results] if results else terms
    except Exception as exc:
        logger.warning("MTL batch translation failed: %s", exc)
        return terms


# ============================================================================
# LLM mode
# ============================================================================

# Language name helpers
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
) -> str:
    """Translate a single term using the active LLM provider."""
    results = _translate_llm_batch(
        [term], source_lang, target_lang, context,
    )
    return results[0] if results else term


def _translate_llm_batch(
    terms: List[str],
    source_lang: str,
    target_lang: str,
    context: str = "",
) -> List[str]:
    """Translate a batch of terms using the active LLM API.

    Sends a single prompt requesting translation of all terms at once.
    The prompt is kept simple per the specification.
    """
    if not terms:
        return []

    import json

    src = _lang_name(source_lang)
    tgt = _lang_name(target_lang)

    # Build prompt
    term_list = "\n".join(f"- {t}" for t in terms)
    system_prompt = (
        f"You are a professional translator. Translate the following "
        f"{src} terms to {tgt}. These are character names, glossary "
        f"terms, or code pattern labels from a video game.\n"
        f"Return ONLY a JSON object: {{\"translations\": [...]}} "
        f"with exactly {len(terms)} translated strings in the same order."
    )
    if context:
        system_prompt += f"\nContext: {context}"

    user_content = f"Translate these terms:\n{term_list}"

    try:
        from CherryAI.functions import ini_manager

        # Build a minimal OpenAI-compatible client from active settings
        provider = ini_manager.get_user_default("api", "provider") or "openai"
        model = ini_manager.get_user_default("api", "model") or "gpt-4o-mini"
        api_key = _get_api_key()
        base_url = ini_manager.get_user_default("api", "base_url") or None

        import importlib
        openai_mod = importlib.import_module("openai")
        client_cls = getattr(openai_mod, "OpenAI")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = client_cls(**kwargs)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        translations = data.get("translations", [])
        if len(translations) == len(terms):
            return translations
        logger.warning(
            "LLM returned %d translations for %d terms",
            len(translations), len(terms),
        )
        # Pad or truncate
        return (translations + terms[len(translations):])[:len(terms)]

    except Exception as exc:
        logger.warning("LLM term translation failed: %s", exc)
        return terms


def _get_api_key() -> str:
    """Retrieve the active API key from API.ini or in-memory settings."""
    try:
        from CherryAI.functions import api_config
        providers = api_config.load_providers()
        if providers:
            first = providers[0]
            key = first.get("api_key", "")
            if key:
                return key
    except Exception:
        pass
    try:
        from CherryAI.functions import ini_manager
        return ini_manager.get_user_default("api", "api_key") or ""
    except Exception:
        return ""
