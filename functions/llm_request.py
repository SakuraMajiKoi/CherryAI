"""Shared LLM chat request routing.

This module is intentionally small: it gives non-translation callers one
OpenAI-compatible route for translation utilities, glossary utilities, and
editor context-menu actions.  Local providers are handled by configuration
instead of per-feature branches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .local_llm import is_local_url


LOCAL_PROVIDER_NAMES = {"local", "lmstudio", "ollama", "koboldcpp"}


@dataclass
class ChatRequestResult:
    """Normalized result for a chat completion request."""

    content: str
    raw: Any = None


def is_local_provider(provider: str, base_url: Optional[str] = None) -> bool:
    """Return True when a provider/base URL points at a local backend."""
    provider_key = (provider or "").strip().lower()
    return provider_key in LOCAL_PROVIDER_NAMES or is_local_url(base_url or "")


def resolve_api_key(
    *,
    provider: str,
    api_key: str,
    base_url: Optional[str] = None,
) -> str:
    """Return an API key suitable for cloud and no-key local providers."""
    key = (api_key or "").strip()
    if key:
        return key
    if is_local_provider(provider, base_url):
        return "local"
    return ""


def build_openai_client_kwargs(
    *,
    provider: str,
    api_key: str,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Build common OpenAI SDK client kwargs for any compatible provider."""
    resolved_key = resolve_api_key(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
    )
    if not resolved_key:
        raise RuntimeError(
            f"No API key found for provider '{provider}'. Configure an API key "
            "or select a local provider."
        )

    kwargs: Dict[str, Any] = {"api_key": resolved_key}
    if base_url:
        kwargs["base_url"] = base_url
    if timeout is not None:
        kwargs["timeout"] = timeout
    return kwargs


def build_chat_request_kwargs(
    *,
    provider: str,
    model: str,
    messages: List[Dict[str, str]],
    response_format: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build common chat-completion kwargs with provider-specific extras."""
    request_kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if response_format is not None:
        request_kwargs["response_format"] = response_format
    if temperature is not None:
        request_kwargs["temperature"] = temperature
    if max_tokens is not None:
        request_kwargs["max_tokens"] = max_tokens
    if (provider or "").strip().lower() == "openai":
        request_kwargs["store"] = False
    if extra:
        request_kwargs.update(extra)
    return request_kwargs


def send_chat_completion(
    *,
    provider: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    response_format: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> ChatRequestResult:
    """Send one OpenAI-compatible chat completion request."""
    import importlib

    openai_mod = importlib.import_module("openai")
    client_cls = getattr(openai_mod, "OpenAI")
    client = client_cls(**build_openai_client_kwargs(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    ))
    request_kwargs = build_chat_request_kwargs(
        provider=provider,
        model=model,
        messages=messages,
        response_format=response_format,
        temperature=temperature,
        max_tokens=max_tokens,
        extra=extra,
    )
    response = client.chat.completions.create(**request_kwargs)
    content = response.choices[0].message.content or ""
    return ChatRequestResult(content=content, raw=response)
