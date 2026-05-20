"""CherryAI GUI v2 - Global Options Dialog.

Provides a centralized options dialog accessible from the Tools menu.
Organizes all application settings into categorized sections:
- API: Provider, model, key, base URL, temperature
- Request: Timeout, retries, rate limit, chunk size
- Caching: Request caching, cache location
- Logging: Log level, log file, debug mode
- Session: Autosave, theme, restore on launch
- Safety: Token banning, content warnings
- File IO: Default formats, encoding, line endings
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Deferred imports (avoid circular at module load time)
from CherryAI.functions import api_config as _api_config  # noqa: E402
from CherryAI.gui.theme.colors import (
    apply_theme,
    apply_window_preferences,
    get_theme_display_name,
    get_theme_display_names,
)


# =============================================================================
# Enums
# =============================================================================


class OptionSection(Enum):
    """Sections in the global options dialog."""

    API = "api"
    REQUEST = "request"          # displayed as "Model Settings"
    TRANSLATION = "translation"  # Translation Options
    UTILITY = "utility"          # Term Translation utility
    CACHING = "caching"
    LOGGING = "logging"
    SESSION = "session"
    GUI = "gui"
    LIMIT = "limit"
    FILE_IO = "file_io"
    PROMPTS = "prompts"
    SECURITY = "security"


class OptionCategory(Enum):
    """Categories for organizing option sections."""

    CONNECTION = "connection"
    PROCESSING = "processing"
    APPLICATION = "application"


class LogLevel(Enum):
    """Logging level options."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ThemeMode(Enum):
    """Theme mode options."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class LineEnding(Enum):
    """Line ending options."""

    LF = "lf"
    CRLF = "crlf"
    CR = "cr"
    AUTO = "auto"


class EncodingOption(Enum):
    """Encoding options for file I/O."""

    UTF8 = "utf-8"
    UTF8_BOM = "utf-8-sig"
    UTF16 = "utf-16"
    SHIFT_JIS = "shift_jis"
    EUC_JP = "euc_jp"
    AUTO = "auto"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class APISettings:
    """API connection settings."""

    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    cost_cap: float = 999.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "cost_cap": self.cost_cap,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APISettings":
        """Create from dictionary."""
        return cls(
            provider=data.get("provider", "openai"),
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", ""),
            model=data.get("model", "gpt-4o-mini"),
            temperature=float(data.get("temperature", 0.3)),
            cost_cap=float(data.get("cost_cap", 999.0)),
        )


@dataclass
class APIProviderEntry:
    """Single API provider configuration (Task 43.6).

    Attributes:
        name: Display name for the provider (e.g. 'OpenAI GPT-4o').
        provider_type: Provider backend type (openai, gemini, anthropic, local).
        url: API base URL (empty for defaults).
        api_key: API key/token.
        model: Model identifier string.
    """

    name: str = ""
    provider_type: str = "openai"
    url: str = ""
    api_key: str = ""
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "provider_type": self.provider_type,
            "url": self.url,
            "api_key": self.api_key,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIProviderEntry":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            provider_type=data.get("provider_type", "openai"),
            url=data.get("url", ""),
            api_key=data.get("api_key", ""),
            model=data.get("model", ""),
        )


# Provider presets for quick setup (Task 43.6)
PROVIDER_PRESETS: List[APIProviderEntry] = [
    APIProviderEntry(
        name="OpenAI GPT-4o-mini",
        provider_type="openai",
        url="",
        api_key="",
        model="gpt-4o-mini",
    ),
    APIProviderEntry(
        name="OpenAI GPT-4o",
        provider_type="openai",
        url="",
        api_key="",
        model="gpt-4o",
    ),
    APIProviderEntry(
        name="Google Gemini 2.5 Flash",
        provider_type="gemini",
        url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key="",
        model="gemini-2.5-flash-preview-05-20",
    ),
    APIProviderEntry(
        name="Anthropic Claude Sonnet",
        provider_type="anthropic",
        url="https://api.anthropic.com/v1/",
        api_key="",
        model="claude-sonnet-4-20250514",
    ),
    APIProviderEntry(
        name="Local LLM (OpenAI-compat)",
        provider_type="local",
        url="http://localhost:1234/v1",
        api_key="not-needed",
        model="local-model",
    ),
    APIProviderEntry(
        name="LM Studio",
        provider_type="lmstudio",
        url="http://localhost:1234/v1",
        api_key="lm-studio",
        model="local-model",
    ),
]


@dataclass
class RequestSettings:
    """API request settings."""

    timeout: int = 60
    retries: int = 3
    rate_limit: int = 60
    chunk_size: int = 50
    max_input_tokens: int = 0  # Task 41 — 0 = no limit (input lines only)
    thinking_enabled: bool = False  # Task 43.8
    thinking_budget: int = 10000  # Task 43.8
    reasoning_effort: str = "medium"  # low/medium/high for optional/mandatory models
    rolling_context_lines: int = 3  # Task 43.9 — "Lines (Before)"
    rolling_context_between: int = 0  # Task 78 — "Lines (Between)"
    rolling_context_after: int = 0  # Task 78 — "Lines (After)"
    use_translated_context: bool = True  # Task 78 — prefer tl over orig
    remove_duplicate_speakers: bool = False  # Task 51.4
    glossary_filter_mode: str = "all"  # Task 52.3
    consistency_mode: str = "disabled"  # Phase 55

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timeout": self.timeout,
            "retries": self.retries,
            "rate_limit": self.rate_limit,
            "chunk_size": self.chunk_size,
            "max_input_tokens": self.max_input_tokens,
            "thinking_enabled": self.thinking_enabled,
            "thinking_budget": self.thinking_budget,
            "reasoning_effort": self.reasoning_effort,
            "rolling_context_lines": self.rolling_context_lines,
            "rolling_context_between": self.rolling_context_between,
            "rolling_context_after": self.rolling_context_after,
            "use_translated_context": self.use_translated_context,
            "remove_duplicate_speakers": self.remove_duplicate_speakers,
            "glossary_filter_mode": self.glossary_filter_mode,
            "consistency_mode": self.consistency_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequestSettings":
        """Create from dictionary."""
        return cls(
            timeout=int(data.get("timeout", 60)),
            retries=int(data.get("retries", 3)),
            rate_limit=int(data.get("rate_limit", 60)),
            chunk_size=int(data.get("chunk_size", 50)),
            max_input_tokens=int(data.get("max_input_tokens", 0)),
            thinking_enabled=bool(data.get("thinking_enabled", False)),
            thinking_budget=int(data.get("thinking_budget", 10000)),
            reasoning_effort=str(data.get("reasoning_effort", "medium")),
            rolling_context_lines=int(data.get("rolling_context_lines", 3)),
            rolling_context_between=int(data.get("rolling_context_between", 0)),
            rolling_context_after=int(data.get("rolling_context_after", 0)),
            use_translated_context=bool(data.get("use_translated_context", True)),
            remove_duplicate_speakers=bool(
                data.get("remove_duplicate_speakers", False)
            ),
            glossary_filter_mode=str(
                data.get("glossary_filter_mode", "all")
            ),
            consistency_mode=str(
                data.get("consistency_mode", "disabled")
            ),
        )


@dataclass
class CachingSettings:
    """Request caching settings."""

    enabled: bool = True
    dir: str = "Cache"
    age: int = 0       # max age in days; 0 = unlimited
    size: int = 0      # max size in MB;  0 = unlimited
    mode: str = "strict"  # disabled, strict, line, model_only, any

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "dir": self.dir,
            "age": self.age,
            "size": self.size,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CachingSettings":
        """Create from dictionary."""
        return cls(
            enabled=bool(data.get("enabled", True)),
            dir=str(data.get("dir", "Cache")),
            age=int(data.get("age", 0)),
            size=int(data.get("size", 0)),
            mode=str(data.get("mode", "strict")),
        )


@dataclass
class LoggingSettings:
    """Logging configuration settings."""

    level: str = "Error"
    location: str = "log/"
    debug: bool = False
    api_log: bool = True  # API request/response logs
    log_requests: bool = False  # Log outgoing requests as JSON files

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level,
            "location": self.location,
            "debug": self.debug,
            "api_log": self.api_log,
            "log_requests": self.log_requests,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingSettings":
        """Create from dictionary."""
        return cls(
            level=str(data.get("level", "Error")),
            location=str(data.get("location", "log/")),
            debug=bool(data.get("debug", False)),
            api_log=bool(data.get("api_log", True)),
            log_requests=bool(data.get("log_requests", False)),
        )


@dataclass
class SessionSettings:
    """Session and UI settings."""

    autosave: bool = True
    interval: int = 60
    theme: str = "light"
    load_last: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "autosave": self.autosave,
            "interval": self.interval,
            "theme": self.theme,
            "load_last": self.load_last,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionSettings":
        """Create from dictionary."""
        return cls(
            autosave=bool(data.get("autosave", True)),
            interval=int(data.get("interval", 60)),
            theme=str(data.get("theme", "light")),
            load_last=bool(data.get("load_last", True)),
        )


@dataclass
class GUISettings:
    """GUI design and window behavior settings."""

    design: str = "pale_blue"
    save_window_dimensions: bool = True
    launch_maximized: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "design": self.design,
            "save_window_dimensions": self.save_window_dimensions,
            "launch_maximized": self.launch_maximized,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GUISettings":
        """Create from dictionary."""
        return cls(
            design=str(data.get("design", "pale_blue")),
            save_window_dimensions=bool(data.get("save_window_dimensions", True)),
            launch_maximized=bool(data.get("launch_maximized", False)),
        )


@dataclass
class LimitSettings:
    """Safety / output-limit settings (section [limit] in INI)."""

    banned: str = "\u2014, \u2013"  # em-dash, en-dash
    output: int = 4096
    warning_abort_enabled: bool = True
    warning_abort_after: int = 1
    skip_unsafe_requests: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "banned": self.banned,
            "output": self.output,
            "warning_abort_enabled": self.warning_abort_enabled,
            "warning_abort_after": self.warning_abort_after,
            "skip_unsafe_requests": self.skip_unsafe_requests,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LimitSettings":
        """Create from dictionary."""
        def _as_bool(value: Any, default: bool) -> bool:
            if value is None:
                return default
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            banned=str(data.get("banned", "\u2014, \u2013")),
            output=int(data.get("output", 4096)),
            warning_abort_enabled=_as_bool(
                data.get("warning_abort_enabled", data.get("warnings")),
                True,
            ),
            warning_abort_after=max(1, int(data.get("warning_abort_after", 1))),
            skip_unsafe_requests=_as_bool(
                data.get("skip_unsafe_requests", data.get("safe")),
                True,
            ),
        )

    def get_banned_chars(self) -> List[str]:
        """Return the banned characters as a list (split on comma)."""
        return [c.strip() for c in self.banned.split(",") if c.strip()]

    @property
    def warnings(self) -> bool:
        """Backward-compatible alias for the unsafe abort toggle."""
        return self.warning_abort_enabled

    @warnings.setter
    def warnings(self, value: bool) -> None:
        self.warning_abort_enabled = bool(value)

    @property
    def safe(self) -> bool:
        """Backward-compatible alias for the skip-unsafe policy toggle."""
        return self.skip_unsafe_requests

    @safe.setter
    def safe(self, value: bool) -> None:
        self.skip_unsafe_requests = bool(value)


# Keep old name as alias for backwards compatibility with existing tests
SafetySettings = LimitSettings


@dataclass
class FileIOSettings:
    """File I/O settings."""

    encoding: str = "auto"
    preservebom: bool = True
    lines: str = "auto"
    backup: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "encoding": self.encoding,
            "preservebom": self.preservebom,
            "lines": self.lines,
            "backup": self.backup,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileIOSettings":
        """Create from dictionary."""
        return cls(
            encoding=str(data.get("encoding", "auto")),
            preservebom=bool(data.get("preservebom", True)),
            lines=str(data.get("lines", "auto")),
            backup=bool(data.get("backup", True)),
        )


# Default prompts for Edit and TLC steps
DEFAULT_EDIT_PROMPT = (
    "Review and improve the translation while maintaining accuracy and natural flow. "
    "Fix any grammar issues, awkward phrasing, or inconsistencies. "
    "Preserve the original meaning and tone."
)

DEFAULT_TLC_PROMPT = (
    "Perform a Translation/Localization Check (TLC) on the translation. "
    "Verify accuracy against the source text, check for natural {target_lang} expression, "
    "ensure consistency in terminology and style, and flag any issues or suggest improvements."
)

# Default conditional (context-type) prompts — must match prompt_builder.py constants
DEFAULT_DIALOGUE_PROMPT = (
    "# Content Type: Dialogue\n"
    "These lines are character dialogue. "
    "Pay attention to the speaker names, maintain consistent voice and tone "
    "for each character, and preserve emotional nuances in the conversation."
)

DEFAULT_MENU_PROMPT = (
    "# Content Type: Menu\n"
    "These lines are menu items from a game UI. "
    "Translate each item concisely and clearly. Preserve formatting, order, "
    "and any shortcut indicators. Keep translations brief and action-oriented."
)

DEFAULT_CHOICE_PROMPT = (
    "# Content Type: Choices\n"
    "These lines are player choices or options. "
    "Translate each choice concisely and distinctly so the player can "
    "differentiate between options. Preserve numbering or bullet formatting."
)

DEFAULT_UNKNOWN_PROMPT = (
    "# Content Type: Mixed\n"
    "These lines may contain dialogue, menu items, or choices. "
    "Translate each line appropriately based on its apparent purpose. "
    "Maintain formatting and keep menu/choice items concise."
)

# Default prompts for Term Translation and Gender Inference utility features
DEFAULT_TERM_GLOSSARY_PROMPT = (
    "You are a professional {source_lang}-to-{target_lang} translator. "
    "Translate each term succinctly. These are character names or glossary "
    "terms from a video game. "
    "Return ONLY a JSON object: {{\"translations\": [...]}} with exactly "
    "{count} translated strings in the same order as the input."
)

DEFAULT_TERM_CODE_PROMPT = (
    "You are a professional {source_lang}-to-{target_lang} translator. "
    "For each code pattern label, provide a succinct {target_lang} explanation "
    "of what the code represents. "
    "Return ONLY a JSON object: {{\"translations\": [...]}} with exactly "
    "{count} strings in the same order as the input."
)

DEFAULT_GENDER_INFERENCE_PROMPT = (
    'Infer the gender of the speaker "{name}" from the dialogue excerpt '
    "below. Base your answer on how others address this speaker, their "
    "speech patterns, and contextual clues. "
    "Don't guess a gender if you are unsure.\n\n"
    "{excerpt}\n\n"
    "Return a JSON object with exactly these fields:\n"
    '- details: gender (one word, "Unknown")'
)


# PHASE 37: Edit/TLC prompt component toggles
class EditInputPolicy(Enum):
    """Input source policy for Edit pass (TASK 37.1)."""

    TL_ONLY = "tl_only"           # Use TL field only (default)
    ORIG_AND_TL = "orig_and_tl"   # Include original for reference
    TLC_ONLY = "tlc_only"         # Use latest TLC output only
    TL_AND_TLC = "tl_and_tlc"     # Use both TL and TLC


class TLCInputPolicy(Enum):
    """Input source policy for TLC pass (TASK 37.1)."""

    TL_ONLY = "tl_only"           # Use TL field only
    ORIG_AND_TL = "orig_and_tl"   # Include original for reference (default)
    EDIT_ONLY = "edit_only"       # Use latest Edit output only
    EDIT_AND_ORIG = "edit_and_orig"  # Use Edit output with original


@dataclass
class PromptsSettings:
    """Custom prompts for Edit, TLC, and context-type steps (TASK 37.1)."""

    # Utility prompts (Term Translation + Gender Inference)
    term_glossary: str = DEFAULT_TERM_GLOSSARY_PROMPT
    term_code: str = DEFAULT_TERM_CODE_PROMPT
    gender_inference: str = DEFAULT_GENDER_INFERENCE_PROMPT
    # Edit / TLC step prompts
    edit: str = DEFAULT_EDIT_PROMPT
    tlc: str = DEFAULT_TLC_PROMPT
    # Conditional (context-type) prompts injected based on content type
    dialogue: str = DEFAULT_DIALOGUE_PROMPT
    menu: str = DEFAULT_MENU_PROMPT
    choice: str = DEFAULT_CHOICE_PROMPT
    unknown: str = DEFAULT_UNKNOWN_PROMPT
    # Prompt component toggles
    glossary: bool = True
    summary: bool = True
    code: bool = True
    input: str = "tl_only"  # Edit input source policy
    # TLC component toggles (separate tracking)
    tlc_include_glossary: bool = True
    tlc_include_game_summary: bool = True
    tlc_include_code_glossary: bool = True
    # PHASE 37: Input policies
    edit_input_policy: str = "tl_only"
    tlc_input_policy: str = "orig_and_tl"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "term_glossary": self.term_glossary,
            "term_code": self.term_code,
            "gender_inference": self.gender_inference,
            "edit": self.edit,
            "tlc": self.tlc,
            "dialogue": self.dialogue,
            "menu": self.menu,
            "choice": self.choice,
            "unknown": self.unknown,
            "glossary": self.glossary,
            "summary": self.summary,
            "code": self.code,
            "input": self.input,
            "tlc_include_glossary": self.tlc_include_glossary,
            "tlc_include_game_summary": self.tlc_include_game_summary,
            "tlc_include_code_glossary": self.tlc_include_code_glossary,
            "edit_input_policy": self.edit_input_policy,
            "tlc_input_policy": self.tlc_input_policy,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptsSettings":
        """Create from dictionary."""
        return cls(
            term_glossary=str(
                data.get("term_glossary", DEFAULT_TERM_GLOSSARY_PROMPT),
            ),
            term_code=str(
                data.get("term_code", DEFAULT_TERM_CODE_PROMPT),
            ),
            gender_inference=str(
                data.get("gender_inference", DEFAULT_GENDER_INFERENCE_PROMPT),
            ),
            edit=str(data.get("edit", DEFAULT_EDIT_PROMPT)),
            tlc=str(data.get("tlc", DEFAULT_TLC_PROMPT)),
            dialogue=str(data.get("dialogue", DEFAULT_DIALOGUE_PROMPT)),
            menu=str(data.get("menu", DEFAULT_MENU_PROMPT)),
            choice=str(data.get("choice", DEFAULT_CHOICE_PROMPT)),
            unknown=str(data.get("unknown", DEFAULT_UNKNOWN_PROMPT)),
            glossary=bool(data.get("glossary", True)),
            summary=bool(data.get("summary", True)),
            code=bool(data.get("code", True)),
            input=str(data.get("input", "tl_only")),
            tlc_include_glossary=bool(data.get("tlc_include_glossary", True)),
            tlc_include_game_summary=bool(data.get("tlc_include_game_summary", True)),
            tlc_include_code_glossary=bool(data.get("tlc_include_code_glossary", True)),
            edit_input_policy=str(data.get("edit_input_policy", "tl_only")),
            tlc_input_policy=str(data.get("tlc_input_policy", "orig_and_tl")),
        )

    def get_edit_components(self) -> Dict[str, bool]:
        """Get edit component toggles as dict."""
        return {
            "glossary": self.glossary,
            "game_summary": self.summary,
            "code_glossary": self.code,
        }

    def get_tlc_components(self) -> Dict[str, bool]:
        """Get TLC component toggles as dict."""
        return {
            "glossary": self.tlc_include_glossary,
            "game_summary": self.tlc_include_game_summary,
            "code_glossary": self.tlc_include_code_glossary,
        }


@dataclass
class TranslationSettings:
    """Translation workflow settings stored under Translation Options.

    Fields that were previously scattered across the UI are collected
    here for proper persistence and coherent grouping.
    """

    overwrite_translation: bool = False
    skip_non_source_language: bool = True
    retry_strategy: str = "batch"
    request_slicing: str = "conservative"
    exchange_forbidden_chars: bool = True
    flag_for_qa_review: bool = True
    retry_forbidden_chars: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overwrite_translation": self.overwrite_translation,
            "skip_non_source_language": self.skip_non_source_language,
            "retry_strategy": self.retry_strategy,
            "request_slicing": self.request_slicing,
            "exchange_forbidden_chars": self.exchange_forbidden_chars,
            "flag_for_qa_review": self.flag_for_qa_review,
            "retry_forbidden_chars": self.retry_forbidden_chars,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationSettings":
        """Create from dictionary."""
        return cls(
            overwrite_translation=bool(
                data.get("overwrite_translation", False)
            ),
            skip_non_source_language=bool(
                data.get("skip_non_source_language", True)
            ),
            retry_strategy=str(
                data.get("retry_strategy", "batch")
            ),
            request_slicing=str(
                data.get("request_slicing", "conservative")
            ),
            exchange_forbidden_chars=bool(
                data.get("exchange_forbidden_chars", True)
            ),
            flag_for_qa_review=bool(
                data.get("flag_for_qa_review", True)
            ),
            retry_forbidden_chars=bool(
                data.get("retry_forbidden_chars", False)
            ),
        )


@dataclass
class UtilitySettings:
    """Utility settings for term translation and gender inference.

    Attributes:
        term_translation_mode: Active mode — 'Romaji' or 'LLM'.
        term_api_key_provider: Provider for term translation API key.
        term_api_key_name: Name of saved API key for term translation.
        term_model: Model identifier for term translation LLM.
        term_batch_size: Number of terms per LLM request.
        gender_inference_mode: 'Script only' or 'Script + LLM'.
        gender_api_key_provider: Provider for gender inference API key.
        gender_api_key_name: Name of saved API key for gender inference.
        gender_model: Model identifier for gender inference LLM.
        gender_script_minimum: Min agreements for script checks (minimumscript).
        gender_script_maximum: Max script checks (maximumscript).
        gender_script_ignore_unknown: Unknown results don't count toward max.
        gender_script_do_all: Always run max checks vs. early stop.
        gender_llm_minimum: Min agreements for LLM checks (minimumLLM).
        gender_llm_maximum: Max LLM checks (maximumLLM).
        gender_llm_ignore_unknown: Unknown results don't count toward max.
        gender_llm_do_all: Always run max checks vs. early stop.
        speaker_threshold: Minimum speaker occurrences for visibility (default 10).
    """

    term_translation_mode: str = "Romaji"
    term_api_key_provider: str = ""
    term_api_key_name: str = ""
    term_model: str = ""
    term_batch_size: int = 10
    gender_inference_mode: str = "Script only"
    gender_api_key_provider: str = ""
    gender_api_key_name: str = ""
    gender_model: str = ""
    gender_script_minimum: int = 30
    gender_script_maximum: int = 50
    gender_script_ignore_unknown: bool = True
    gender_script_do_all: bool = True
    gender_llm_minimum: int = 3
    gender_llm_maximum: int = 5
    gender_llm_ignore_unknown: bool = True
    gender_llm_do_all: bool = False
    speaker_threshold: int = 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "term_translation_mode": self.term_translation_mode,
            "term_api_key_provider": self.term_api_key_provider,
            "term_api_key_name": self.term_api_key_name,
            "term_model": self.term_model,
            "term_batch_size": self.term_batch_size,
            "gender_inference_mode": self.gender_inference_mode,
            "gender_api_key_provider": self.gender_api_key_provider,
            "gender_api_key_name": self.gender_api_key_name,
            "gender_model": self.gender_model,
            "gender_script_minimum": self.gender_script_minimum,
            "gender_script_maximum": self.gender_script_maximum,
            "gender_script_ignore_unknown": self.gender_script_ignore_unknown,
            "gender_script_do_all": self.gender_script_do_all,
            "gender_llm_minimum": self.gender_llm_minimum,
            "gender_llm_maximum": self.gender_llm_maximum,
            "gender_llm_ignore_unknown": self.gender_llm_ignore_unknown,
            "gender_llm_do_all": self.gender_llm_do_all,
            "speaker_threshold": self.speaker_threshold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UtilitySettings":
        """Create from dictionary."""
        def _as_bool(value: Any, default: bool) -> bool:
            if value is None:
                return default
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)

        mode = str(data.get("term_translation_mode", "Romaji"))
        if mode in ("Simple", "MTL"):
            mode = "Romaji"
        gi_mode = str(data.get("gender_inference_mode", "Script only"))
        if gi_mode not in ("Script only", "Script + LLM"):
            gi_mode = "Script only"
        return cls(
            term_translation_mode=mode,
            term_api_key_provider=str(data.get("term_api_key_provider", "")),
            term_api_key_name=str(data.get("term_api_key_name", "")),
            term_model=str(data.get("term_model", "")),
            term_batch_size=int(data.get("term_batch_size", 10)),
            gender_inference_mode=gi_mode,
            gender_api_key_provider=str(data.get("gender_api_key_provider", "")),
            gender_api_key_name=str(data.get("gender_api_key_name", "")),
            gender_model=str(data.get("gender_model", "")),
            gender_script_minimum=int(data.get("gender_script_minimum", 30)),
            gender_script_maximum=int(data.get("gender_script_maximum", 50)),
            gender_script_ignore_unknown=_as_bool(
                data.get("gender_script_ignore_unknown"), True,
            ),
            gender_script_do_all=_as_bool(
                data.get("gender_script_do_all"), True,
            ),
            gender_llm_minimum=int(data.get("gender_llm_minimum", 3)),
            gender_llm_maximum=int(data.get("gender_llm_maximum", 5)),
            gender_llm_ignore_unknown=_as_bool(
                data.get("gender_llm_ignore_unknown"), True,
            ),
            gender_llm_do_all=_as_bool(
                data.get("gender_llm_do_all"), False,
            ),
            speaker_threshold=int(data.get("speaker_threshold", 10)),
        )


@dataclass
class GlobalOptions:
    """Container for all global options."""

    api: APISettings = field(default_factory=APISettings)
    request: RequestSettings = field(default_factory=RequestSettings)
    translation: TranslationSettings = field(default_factory=TranslationSettings)
    utility: UtilitySettings = field(default_factory=UtilitySettings)
    caching: CachingSettings = field(default_factory=CachingSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    session: SessionSettings = field(default_factory=SessionSettings)
    gui: GUISettings = field(default_factory=GUISettings)
    limit: LimitSettings = field(default_factory=LimitSettings)
    file_io: FileIOSettings = field(default_factory=FileIOSettings)
    prompts: PromptsSettings = field(default_factory=PromptsSettings)
    providers: List[APIProviderEntry] = field(default_factory=list)

    # Keep old 'safety' attribute as an alias so existing code still works.
    @property
    def safety(self) -> LimitSettings:
        """Backward-compat alias for ``limit``."""
        return self.limit

    @safety.setter
    def safety(self, value: LimitSettings) -> None:
        self.limit = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "api": self.api.to_dict(),
            "request": self.request.to_dict(),
            "translation": self.translation.to_dict(),
            "utility": self.utility.to_dict(),
            "caching": self.caching.to_dict(),
            "logging": self.logging.to_dict(),
            "session": self.session.to_dict(),
            "gui": self.gui.to_dict(),
            "limit": self.limit.to_dict(),
            "file_io": self.file_io.to_dict(),
            "prompts": self.prompts.to_dict(),
            "providers": [p.to_dict() for p in self.providers],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalOptions":
        """Create from dictionary."""
        providers_raw = data.get("providers", [])
        providers = [APIProviderEntry.from_dict(p) for p in providers_raw]
        # Support both 'limit' and legacy 'safety' key.
        limit_data = data.get("limit") or data.get("safety") or {}
        return cls(
            api=APISettings.from_dict(data.get("api", {})),
            request=RequestSettings.from_dict(data.get("request", {})),
            translation=TranslationSettings.from_dict(
                data.get("translation", {})
            ),
            utility=UtilitySettings.from_dict(data.get("utility", {})),
            caching=CachingSettings.from_dict(data.get("caching", {})),
            logging=LoggingSettings.from_dict(data.get("logging", {})),
            session=SessionSettings.from_dict(data.get("session", {})),
            gui=GUISettings.from_dict(data.get("gui", {})),
            limit=LimitSettings.from_dict(limit_data),
            file_io=FileIOSettings.from_dict(data.get("file_io", {})),
            prompts=PromptsSettings.from_dict(data.get("prompts", {})),
            providers=providers,
        )

    @classmethod
    def load_from_ini(cls) -> "GlobalOptions":
        """Load all persisted Global Options from ``CherryAI.ini``.

        Uses ``get_effective_default`` (user_defaults → factory defaults →
        fallback) so every field is correctly populated even before the user
        has ever clicked Apply in Global Options.
        """
        try:
            from CherryAI.functions import api_config, ini_manager
        except Exception:
            return cls()

        def _str(section: str, key: str, fallback: str = "") -> str:
            val = ini_manager.get_effective_default(section, key, fallback, str)
            return str(val) if val is not None else fallback

        def _int(section: str, key: str, fallback: int = 0) -> int:
            val = ini_manager.get_effective_default(section, key, fallback, int)
            try:
                return int(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return fallback

        def _float(section: str, key: str, fallback: float = 0.0) -> float:
            val = ini_manager.get_effective_default(section, key, fallback, float)
            try:
                return float(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return fallback

        def _bool(section: str, key: str, fallback: bool = False) -> bool:
            val = ini_manager.get_effective_default(section, key, fallback, bool)
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.lower() in ("true", "yes", "1", "on")
            return fallback

        # -- API settings (stored under "api" prefix) --
        api = APISettings(
            provider=_str("api", "provider", "openai"),
            model=_str("api", "model", "gpt-4o-mini"),
            temperature=_float("api", "temperature", 0.3),
            cost_cap=_float("api", "cost_cap", _model_registry.DEFAULT_COST_CAP),
        )

        # -- Request settings (also stored under "api" prefix) --
        request = RequestSettings(
            timeout=_int("api", "timeout", 60),
            retries=_int("api", "retries", 3),
            rate_limit=_int("api", "rate_limit_requests", 60),
            chunk_size=_int("api", "chunk_size", 50),
            max_input_tokens=_int("api", "max_input_tokens", 0),
            thinking_enabled=_bool("api", "thinking_enabled", False),
            thinking_budget=_int("api", "thinking_budget", 10000),
            rolling_context_lines=_int("api", "rolling_context_lines", 3),
            rolling_context_between=_int("api", "rolling_context_between", 0),
            rolling_context_after=_int("api", "rolling_context_after", 0),
            use_translated_context=_bool("api", "use_translated_context", True),
            remove_duplicate_speakers=_bool("api", "remove_duplicate_speakers", False),
            glossary_filter_mode=_str("api", "glossary_filter_mode", "all"),
            consistency_mode=_str("api", "consistency_mode", "disabled"),
        )

        # -- Translation settings --
        translation = TranslationSettings(
            overwrite_translation=_bool("translation", "overwrite_translation", False),
            skip_non_source_language=_bool("translation", "skip_non_source_language", True),
            retry_strategy=_str("translation", "retry_strategy", "batch"),
            request_slicing=_str("translation", "request_slicing", "conservative"),
        )

        # -- Caching settings --
        caching = CachingSettings(
            enabled=_bool("caching", "enabled", True),
            dir=_str("caching", "dir", "Cache"),
            age=_int("caching", "age", 0),
            size=_int("caching", "size", 0),
            mode=_str("caching", "mode", "strict"),
        )

        # -- Logging settings --
        logging_s = LoggingSettings(
            level=_str("log", "level", "Error"),
            location=_str("log", "location", "log/"),
            debug=_bool("log", "debug", False),
            api_log=_bool("log", "api_log", True),
            log_requests=_bool("log", "log_requests", False),
        )

        # -- Session settings --
        session = SessionSettings(
            autosave=_bool("session", "autosave", True),
            interval=_int("session", "interval", 60),
            theme=_str("session", "theme", "light"),
            load_last=_bool("session", "load_last", True),
        )

        gui = GUISettings(
            design=_str("ui", "design", "pale_blue"),
            save_window_dimensions=_bool("ui", "save_window_dimensions", True),
            launch_maximized=_bool("ui", "launch_maximized", False),
        )

        # -- Limit settings --
        limit = LimitSettings(
            banned=_str("limit", "banned", "\u2014, \u2013"),
            output=_int("limit", "output", 4096),
            warning_abort_enabled=_bool(
                "limit",
                "unsafe_abort_enabled",
                _bool("limit", "warnings", True),
            ),
            warning_abort_after=max(1, _int("limit", "unsafe_abort_after", 1)),
            skip_unsafe_requests=_bool(
                "limit",
                "skip_unsafe_requests",
                _bool("limit", "safe", True),
            ),
        )

        # -- File I/O settings --
        file_io = FileIOSettings(
            encoding=_str("fileio", "encoding", "auto"),
            lines=_str("fileio", "lines", "auto"),
            preservebom=_bool("fileio", "preservebom", True),
            backup=_bool("fileio", "backup", True),
        )

        # -- Utility settings (uses user_defaults + API.ini profiles) --
        utility = UtilitySettings.from_dict({
            "term_translation_mode": _str("utility", "term_translation_mode", "Romaji"),
            "term_api_key_provider": (
                api_config.get_profile_setting("term_translation", "provider") or ""
            ),
            "term_api_key_name": (
                api_config.get_profile_setting("term_translation", "key_name") or ""
            ),
            "term_model": (
                api_config.get_profile_setting("term_translation", "model") or ""
            ),
            "term_batch_size": _int("utility", "term_batch_size", 10),
            "gender_inference_mode": _str(
                "utility", "gender_inference_mode", "Script only",
            ),
            "gender_api_key_provider": (
                api_config.get_profile_setting("gender_inference", "provider") or ""
            ),
            "gender_api_key_name": (
                api_config.get_profile_setting("gender_inference", "key_name") or ""
            ),
            "gender_model": (
                api_config.get_profile_setting("gender_inference", "model") or ""
            ),
            "gender_script_minimum": _int("utility", "gender_script_minimum", 30),
            "gender_script_maximum": _int("utility", "gender_script_maximum", 50),
            "gender_script_ignore_unknown": _bool(
                "utility", "gender_script_ignore_unknown", True,
            ),
            "gender_script_do_all": _bool("utility", "gender_script_do_all", True),
            "gender_llm_minimum": _int("utility", "gender_llm_minimum", 3),
            "gender_llm_maximum": _int("utility", "gender_llm_maximum", 5),
            "gender_llm_ignore_unknown": _bool(
                "utility", "gender_llm_ignore_unknown", True,
            ),
            "gender_llm_do_all": _bool("utility", "gender_llm_do_all", False),
            "speaker_threshold": _int("utility", "speaker_threshold", 10),
        })

        # -- Prompts settings --
        prompts = PromptsSettings.from_dict({
            "term_glossary": (
                _str("prompts", "term_glossary", "") or DEFAULT_TERM_GLOSSARY_PROMPT
            ),
            "term_code": (
                _str("prompts", "term_code", "") or DEFAULT_TERM_CODE_PROMPT
            ),
            "gender_inference": (
                _str("prompts", "gender_inference", "") or DEFAULT_GENDER_INFERENCE_PROMPT
            ),
            "edit": _str("prompts", "edit", DEFAULT_EDIT_PROMPT),
            "tlc": _str("prompts", "tlc", DEFAULT_TLC_PROMPT),
            "dialogue": _str("prompts", "dialogue", DEFAULT_DIALOGUE_PROMPT),
            "menu": _str("prompts", "menu", DEFAULT_MENU_PROMPT),
            "choice": _str("prompts", "choice", DEFAULT_CHOICE_PROMPT),
            "unknown": _str("prompts", "unknown", DEFAULT_UNKNOWN_PROMPT),
        })

        return cls(
            api=api,
            request=request,
            translation=translation,
            utility=utility,
            caching=caching,
            logging=logging_s,
            session=session,
            gui=gui,
            limit=limit,
            file_io=file_io,
            prompts=prompts,
        )

    def get_model_list(self) -> List[str]:
        """Return list of available model names from providers (Task 43.6).

        Always includes 'Mock Translation' as first entry.
        """
        models: List[str] = ["Mock Translation"]
        for p in self.providers:
            if p.model and p.model not in models:
                models.append(p.model)
        return models

    def get_provider_for_model(self, model: str) -> Optional[APIProviderEntry]:
        """Return the provider entry for a given model name."""
        for p in self.providers:
            if p.model == model:
                return p
        return None



# =============================================================================
# Constants
# =============================================================================


SECTION_DESCRIPTIONS: Dict[OptionSection, str] = {
    OptionSection.API: "Configure API provider, model, and authentication settings.",
    OptionSection.REQUEST: "Model-level settings: temperature, thinking, timeouts, and rate limits.",
    OptionSection.TRANSLATION: "Translation-level options: chunking, retries, caching, and output.",
    OptionSection.UTILITY: "Configure Term Translation and Gender Inference settings.",
    OptionSection.CACHING: "Configure request caching to reduce API calls.",
    OptionSection.LOGGING: "Set logging level and debug options.",
    OptionSection.SESSION: "Configure autosave and startup session behavior.",
    OptionSection.GUI: "Configure GUI design, saved window dimensions, and maximized startup behavior.",
    OptionSection.LIMIT: "Configure output limits, banned characters, and content safeguards.",
    OptionSection.FILE_IO: "Set default file encoding and format options.",
    OptionSection.PROMPTS: "Configure custom prompts for Edit and TLC steps.",
    OptionSection.SECURITY: "Manage the master password that encrypts stored API keys.",
}


CATEGORY_ORDER: List[Tuple[OptionCategory, List[OptionSection]]] = [
    (OptionCategory.CONNECTION, [OptionSection.API, OptionSection.REQUEST, OptionSection.TRANSLATION, OptionSection.UTILITY]),
    (OptionCategory.PROCESSING, [OptionSection.CACHING, OptionSection.LIMIT, OptionSection.PROMPTS]),
    (OptionCategory.APPLICATION, [OptionSection.SESSION, OptionSection.GUI, OptionSection.LOGGING, OptionSection.FILE_IO, OptionSection.SECURITY]),
]


CATEGORY_NAMES: Dict[OptionCategory, str] = {
    OptionCategory.CONNECTION: "Connection",
    OptionCategory.PROCESSING: "Processing",
    OptionCategory.APPLICATION: "Application",
}

SECTION_NAMES: Dict[OptionSection, str] = {
    OptionSection.API: "API Provider",
    OptionSection.REQUEST: "Model Settings",
    OptionSection.TRANSLATION: "Translation Options",
    OptionSection.UTILITY: "Utility",
    OptionSection.CACHING: "Caching",
    OptionSection.LOGGING: "Logging",
    OptionSection.SESSION: "Session",
    OptionSection.GUI: "GUI",
    OptionSection.LIMIT: "Limits",
    OptionSection.FILE_IO: "File I/O",
    OptionSection.PROMPTS: "Prompts",
    OptionSection.SECURITY: "Security",
}


# API_PROVIDERS imported from options.py - single source of truth
from CherryAI.functions.options import API_PROVIDERS, reload_api_providers
import CherryAI.functions.model_registry as _model_registry

# Common ban tokens
COMMON_BAN_TOKENS: List[str] = [
    "em_dash",
    "smart_quotes",
    "ellipsis",
    "fancy_apostrophe",
    "non_breaking_space",
]


# =============================================================================
# Dialog Class
# =============================================================================


class GlobalOptionsDialog(tk.Toplevel):
    """Modal dialog for managing global application options.

    Provides a categorized interface for all application settings:
    - Connection: API provider, request settings
    - Processing: Caching, safety settings
    - Application: Session, logging, file I/O

    Callback is invoked with GlobalOptions when user saves.
    """

    _ROOT_ATTR = "_global_options_dialog"

    @classmethod
    def open_or_focus(
        cls,
        parent: tk.Misc,
        initial_options: Optional[GlobalOptions] = None,
        on_save: Optional[Callable[[GlobalOptions], None]] = None,
        section: Optional[OptionSection] = None,
    ) -> "GlobalOptionsDialog":
        """Open the dialog once per root window or focus the existing one."""
        root = parent.winfo_toplevel()
        existing = getattr(root, cls._ROOT_ATTR, None)
        if isinstance(existing, cls):
            try:
                if existing.winfo_exists():
                    if on_save is not None:
                        existing.add_save_listener(on_save)
                    if section is not None:
                        existing._show_panel(section)
                    existing._present()
                    return existing
            except tk.TclError:
                pass

        dialog = cls(root, initial_options=initial_options, on_save=on_save)
        dialog._instance_owner = root
        setattr(root, cls._ROOT_ATTR, dialog)
        if section is not None:
            dialog._show_panel(section)
        dialog._present()
        return dialog

    def __init__(
        self,
        parent: tk.Tk,
        initial_options: Optional[GlobalOptions] = None,
        on_save: Optional[Callable[[GlobalOptions], None]] = None,
    ) -> None:
        """Initialize Global Options dialog.

        Args:
            parent: Parent window (usually the main App).
            initial_options: Initial options to populate form.
            on_save: Callback when user saves (receives GlobalOptions).
        """
        super().__init__(parent)

        self.title("Global Options")
        self.resizable(True, True)
        self.minsize(750, 600)

        self.parent = parent
        self.on_save = on_save
        self._instance_owner: Optional[tk.Misc] = None
        self._save_listeners: List[Callable[[GlobalOptions], None]] = []
        if on_save is not None:
            self.add_save_listener(on_save)
        self.options = initial_options or GlobalOptions()

        logger.debug("GlobalOptionsDialog: Starting initialization")

        # Track current section for navigation
        self._current_section: Optional[OptionSection] = None
        self._selecting: bool = False  # Guard against recursive selection

        # Initialize variables before building UI
        logger.debug("GlobalOptionsDialog: Initializing variables")
        self._init_variables()

        # Build UI
        logger.debug("GlobalOptionsDialog: Building UI")
        self._build_ui()

        apply_window_preferences(
            self,
            parent=self.parent,
            window_key="GlobalOptionsDialog",
            default_geometry="900x750",
            center_on_parent=True,
        )

        # Handle window close button (X)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Bind Escape key to close
        self.bind("<Escape>", lambda e: self._on_cancel())

        # Show initial panel directly (without triggering treeview events)
        # This avoids the recursive event loop issue during initialization
        self._show_panel(OptionSection.API)
        
        # Defer treeview selection update until window is fully rendered
        # Using a longer delay and update_idletasks to ensure window is ready
        self.after(50, self._finalize_treeview_selection)

        logger.debug("GlobalOptionsDialog initialized")

    @staticmethod
    def _callback_key(callback: Callable[[GlobalOptions], None]) -> Tuple[Any, Any]:
        """Return a stable deduplication key for a callback."""
        return (
            getattr(callback, "__self__", None),
            getattr(callback, "__func__", callback),
        )

    def add_save_listener(self, callback: Callable[[GlobalOptions], None]) -> None:
        """Register an additional save listener if it is not already tracked."""
        new_key = self._callback_key(callback)
        for existing in self._save_listeners:
            if self._callback_key(existing) == new_key:
                return
        self._save_listeners.append(callback)

    def _present(self) -> None:
        """Bring the dialog to the foreground."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            logger.debug("Global Options dialog could not be presented", exc_info=True)

    def _clear_root_reference(self) -> None:
        """Remove the dialog from the root window registry if registered."""
        owner = self._instance_owner
        if owner is None:
            return
        if getattr(owner, self._ROOT_ATTR, None) is self:
            setattr(owner, self._ROOT_ATTR, None)
        self._instance_owner = None

    def _finalize_treeview_selection(self) -> None:
        """Set the initial treeview selection after window is fully rendered."""
        try:
            self.update_idletasks()  # Process pending display updates
            self._selecting = True  # Prevent recursive handling
            self._nav_tree.selection_set("sec_api")
            self._selecting = False
        except Exception as e:
            logger.error(f"Error setting initial treeview selection: {e}")
            print(f"DEBUG: Error in _finalize_treeview_selection: {e}")

    # def _finalize_init(self) -> None:
    #     """Finalize initialization after window is mapped."""
    #     logger.debug("GlobalOptionsDialog: Finalizing init")
    #     print("DEBUG: GlobalOptionsDialog: Finalizing init")
        
    #     try:
    #         # Make modal
    #         self.transient(self.parent)
    #         self.grab_set()
    #         self.focus_set()

    #         # Center on parent
    #         self.update_idletasks()
    #         self._center_on_parent()

    #         # Select first section
    #         self._select_section(OptionSection.API)
    #     except Exception as e:
    #         logger.error(f"Error in _finalize_init: {e}")
    #         print(f"ERROR: _finalize_init failed: {e}")

    def _center_on_parent(self) -> None:
        """Center the dialog on the parent window."""
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        dialog_w = self.winfo_width()
        dialog_h = self.winfo_height()
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        self.geometry(f"+{x}+{y}")

    def _init_variables(self) -> None:
        """Initialize all tkinter variables for form controls."""
        from CherryAI.functions import ini_manager  # PHASE 58.11: For restore_on_launch
        
        # API settings
        self.provider_var = tk.StringVar(value=self.options.api.provider)
        self.api_key_var = tk.StringVar(value=self.options.api.api_key)
        self.base_url_var = tk.StringVar(value=self.options.api.base_url)
        self.model_var = tk.StringVar(value=self.options.api.model)
        self.model_var.trace_add("write", self._on_model_change)
        self.temperature_var = tk.DoubleVar(value=self.options.api.temperature)
        self.top_p_var = tk.DoubleVar(value=1.0)
        self.frequency_penalty_var = tk.DoubleVar(value=0.2)
        self.presence_penalty_var = tk.DoubleVar(value=0.0)
        self.cost_cap_var = tk.DoubleVar(value=self.options.api.cost_cap)

        # Request settings
        self.timeout_var = tk.IntVar(value=self.options.request.timeout)
        self.retries_var = tk.IntVar(value=self.options.request.retries)
        self.rate_limit_var = tk.IntVar(value=self.options.request.rate_limit)
        self.max_concurrent_var = tk.IntVar(value=3)
        self.requests_per_second_enabled_var = tk.BooleanVar(value=False)
        self.requests_per_second_var = tk.DoubleVar(value=1.0)
        self.temporary_backoff_mode_var = tk.StringVar(value="exponential")
        self.temporary_backoff_attempts_var = tk.IntVar(value=5)
        self.temporary_backoff_total_seconds_var = tk.IntVar(value=120)
        self.chunk_size_var = tk.IntVar(value=self.options.request.chunk_size)
        self.max_input_tokens_var = tk.IntVar(
            value=self.options.request.max_input_tokens,
        )
        self.thinking_enabled_var = tk.BooleanVar(
            value=self.options.request.thinking_enabled,
        )
        self.thinking_budget_var = tk.IntVar(
            value=self.options.request.thinking_budget,
        )
        self.reasoning_effort_var = tk.StringVar(
            value=self.options.request.reasoning_effort,
        )
        self.rolling_context_var = tk.IntVar(
            value=self.options.request.rolling_context_lines,
        )
        self.rolling_context_between_var = tk.IntVar(
            value=self.options.request.rolling_context_between,
        )
        self.rolling_context_after_var = tk.IntVar(
            value=self.options.request.rolling_context_after,
        )
        self.use_translated_context_var = tk.BooleanVar(
            value=self.options.request.use_translated_context,
        )
        self.remove_dup_speakers_var = tk.BooleanVar(
            value=self.options.request.remove_duplicate_speakers,
        )
        self.glossary_filter_var = tk.StringVar(
            value=self.options.request.glossary_filter_mode,
        )
        self.consistency_mode_var = tk.StringVar(
            value=self.options.request.consistency_mode,
        )

        # Translation settings
        self.overwrite_translation_var = tk.BooleanVar(
            value=self.options.translation.overwrite_translation,
        )
        self.skip_non_source_var = tk.BooleanVar(
            value=self.options.translation.skip_non_source_language,
        )
        self.retry_strategy_var = tk.StringVar(
            value=self.options.translation.retry_strategy,
        )
        self.request_slicing_var = tk.StringVar(
            value=self.options.translation.request_slicing,
        )
        self.exchange_forbidden_var = tk.BooleanVar(
            value=self.options.translation.exchange_forbidden_chars,
        )
        self.flag_qa_review_var = tk.BooleanVar(
            value=self.options.translation.flag_for_qa_review,
        )
        self.retry_forbidden_var = tk.BooleanVar(
            value=self.options.translation.retry_forbidden_chars,
        )

        # Caching settings
        self.cache_enabled_var = tk.BooleanVar(value=self.options.caching.enabled)
        self.cache_dir_var = tk.StringVar(value=self.options.caching.dir)
        self.cache_max_age_var = tk.IntVar(value=self.options.caching.age)
        self.cache_max_size_var = tk.IntVar(value=self.options.caching.size)
        self.cache_mode_var = tk.StringVar(value=self.options.caching.mode)

        # Logging settings
        self.log_level_var = tk.StringVar(value=self.options.logging.level)
        self.log_file_var = tk.StringVar(value=self.options.logging.location)
        self.debug_mode_var = tk.BooleanVar(value=self.options.logging.debug)
        self.log_api_calls_var = tk.BooleanVar(value=self.options.logging.api_log)
        self.log_requests_var = tk.BooleanVar(value=self.options.logging.log_requests)

        # Session settings
        self.autosave_enabled_var = tk.BooleanVar(value=self.options.session.autosave)
        self.autosave_interval_var = tk.IntVar(value=self.options.session.interval)
        # Read from [session] section which controls actual startup behavior
        self.restore_on_launch_var = tk.BooleanVar(value=ini_manager.get_restore_on_launch())

        # GUI settings
        self.gui_design_var = tk.StringVar(
            value=get_theme_display_name(self.options.gui.design),
        )
        self.save_window_dimensions_var = tk.BooleanVar(
            value=self.options.gui.save_window_dimensions,
        )
        self.launch_maximized_var = tk.BooleanVar(
            value=self.options.gui.launch_maximized,
        )

        # Limit settings (replaces Safety)
        self.ban_tokens_var = tk.StringVar(value=self.options.limit.banned)
        self.warning_abort_enabled_var = tk.BooleanVar(
            value=self.options.limit.warning_abort_enabled,
        )
        self.content_warning_var = self.warning_abort_enabled_var
        self.warning_abort_after_var = tk.IntVar(
            value=self.options.limit.warning_abort_after,
        )
        self.max_output_tokens_var = tk.IntVar(value=self.options.limit.output)
        self.skip_unsafe_requests_var = tk.BooleanVar(
            value=self.options.limit.skip_unsafe_requests,
        )
        self.safe_var = self.skip_unsafe_requests_var

        # File I/O settings
        self.encoding_var = tk.StringVar(value=self.options.file_io.encoding)
        self.line_ending_var = tk.StringVar(value=self.options.file_io.lines)
        self.preserve_bom_var = tk.BooleanVar(value=self.options.file_io.preservebom)
        self.backup_originals_var = tk.BooleanVar(value=self.options.file_io.backup)

        # Prompts settings
        self.edit_prompt_var = tk.StringVar(value=self.options.prompts.edit)
        self.tlc_prompt_var = tk.StringVar(value=self.options.prompts.tlc)
        # Utility prompts (Term Translation + Gender Inference)
        self.term_glossary_prompt_var = tk.StringVar(
            value=self.options.prompts.term_glossary,
        )
        self.term_code_prompt_var = tk.StringVar(
            value=self.options.prompts.term_code,
        )
        self.gender_inference_prompt_var = tk.StringVar(
            value=self.options.prompts.gender_inference,
        )
        # Conditional (context-type) prompt vars
        self.dialogue_prompt_var = tk.StringVar(value=self.options.prompts.dialogue)
        self.menu_prompt_var = tk.StringVar(value=self.options.prompts.menu)
        self.choice_prompt_var = tk.StringVar(value=self.options.prompts.choice)
        self.unknown_prompt_var = tk.StringVar(value=self.options.prompts.unknown)
        # Component toggles (simplified — single set for both edit and TLC)
        self.edit_include_glossary_var = tk.BooleanVar(value=self.options.prompts.glossary)
        self.edit_include_game_summary_var = tk.BooleanVar(value=self.options.prompts.summary)
        self.edit_include_code_glossary_var = tk.BooleanVar(value=self.options.prompts.code)
        self.tlc_include_glossary_var = tk.BooleanVar(value=self.options.prompts.tlc_include_glossary)
        self.tlc_include_game_summary_var = tk.BooleanVar(value=self.options.prompts.tlc_include_game_summary)
        self.tlc_include_code_glossary_var = tk.BooleanVar(value=self.options.prompts.tlc_include_code_glossary)
        # Input policies
        self.edit_input_policy_var = tk.StringVar(value=self.options.prompts.edit_input_policy)
        self.tlc_input_policy_var = tk.StringVar(value=self.options.prompts.tlc_input_policy)

        # Pattern-triggered conditional prompt vars (from INI)
        self._pattern_prompt_enabled_vars: Dict[str, tk.BooleanVar] = {}
        self._pattern_prompt_text_widgets: Dict[str, tk.Text] = {}
        self._merged_request_text_widgets: Dict[str, tk.Text] = {}
        try:
            from CherryAI.functions.ini_manager import (
                PATTERN_PROMPT_NAMES,
                get_pattern_prompt_enabled,
            )
            for _name in PATTERN_PROMPT_NAMES:
                self._pattern_prompt_enabled_vars[_name] = tk.BooleanVar(
                    value=get_pattern_prompt_enabled(_name),
                )
        except Exception:
            pass

    def _build_ui(self) -> None:
        """Build the options UI with navigation and content panels."""
        # Main container
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Horizontal paned window
        paned = ttk.PanedWindow(main_frame, orient="horizontal")
        paned.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Left side: Navigation tree
        nav_frame = ttk.Frame(paned, width=180)
        self._build_navigation(nav_frame)
        paned.add(nav_frame, weight=0)

        # Right side: Content area
        self._content_frame = ttk.Frame(paned)
        paned.add(self._content_frame, weight=1)

        # Build all section panels (hidden initially)
        self._section_panels: Dict[OptionSection, ttk.Frame] = {}
        
        self._build_api_section()
        self._build_request_section()
        self._build_translation_section()
        self._build_utility_section()
        self._build_caching_section()
        self._build_logging_section()
        self._build_session_section()
        self._build_gui_section()
        self._build_limit_section()
        self._build_file_io_section()
        self._build_prompts_section()
        self._build_security_section()

        # Bottom: Buttons
        self._build_buttons(main_frame)

    def _build_navigation(self, parent: ttk.Frame) -> None:
        """Build the navigation tree on the left side."""
        # Navigation label
        nav_label = ttk.Label(parent, text="Categories", font=("TkDefaultFont", 10, "bold"))
        nav_label.pack(anchor="w", pady=(0, 5))

        # Treeview for navigation
        self._nav_tree = ttk.Treeview(parent, show="tree", selectmode="browse", height=15)
        self._nav_tree.pack(fill=tk.BOTH, expand=True)

        # Populate tree with categories and sections
        for category, sections in CATEGORY_ORDER:
            category_id = self._nav_tree.insert(
                "",
                "end",
                iid=f"cat_{category.value}",
                text=CATEGORY_NAMES[category],
                open=True,
            )
            for section in sections:
                self._nav_tree.insert(
                    category_id,
                    "end",
                    iid=f"sec_{section.value}",
                    text=SECTION_NAMES[section],
                )

        # Bind selection
        self._nav_tree.bind("<<TreeviewSelect>>", self._on_nav_select)

    def _on_nav_select(self, event: tk.Event) -> None:
        """Handle navigation tree selection.
        
        This is called when the user clicks on a treeview item.
        We only need to show the panel - the selection is already set by the click.
        """
        selection = self._nav_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        if item_id.startswith("sec_"):
            section_value = item_id[4:]
            for section in OptionSection:
                if section.value == section_value:
                    # Just show the panel, don't call selection_set (already selected by click)
                    self._show_panel(section)
                    break

    def _show_panel(self, section: OptionSection) -> None:
        """Show the panel for the given section without changing treeview selection.
        
        This is the core panel-switching logic, separated from selection handling
        to avoid recursive event loops.
        """
        # Hide current panel
        if self._current_section is not None:
            panel = self._section_panels.get(self._current_section)
            if panel:
                panel.pack_forget()

        # Show new panel
        panel = self._section_panels.get(section)
        if panel:
            panel.pack(fill=tk.BOTH, expand=True)

        self._current_section = section

    def _select_section(self, section: OptionSection) -> None:
        """Show the panel for the selected section AND update treeview selection.
        
        Use this when you need to programmatically switch sections and want
        the treeview to reflect the change.
        """
        # Guard against recursive calls (selection_set triggers <<TreeviewSelect>>)
        if self._selecting:
            return
        self._selecting = True
        
        try:
            # Show the panel
            self._show_panel(section)
            
            # Update navigation selection (this triggers <<TreeviewSelect>> but guard prevents recursion)
            self._nav_tree.selection_set(f"sec_{section.value}")
        finally:
            self._selecting = False

    def _create_scrollable_panel(
        self, section: OptionSection,
    ) -> ttk.Frame:
        """Create a scrollable panel for a section.

        Returns the inner frame where widgets should be packed. The outer
        panel (with canvas + scrollbar) is registered in ``_section_panels``.

        Args:
            section: The option section this panel belongs to.

        Returns:
            The inner scrollable frame.
        """
        outer = ttk.Frame(self._content_frame)
        self._section_panels[section] = outer

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas, padding=15)

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Resize inner frame width to canvas width
        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        return inner

    def _build_api_section(self) -> None:
        """Build the API settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.API] = panel

        # Section header
        header = ttk.Label(panel, text="API Provider", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.API], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Provider selection
        provider_frame = ttk.LabelFrame(panel, text="Provider", padding=10)
        provider_frame.pack(fill=tk.X, pady=(0, 10))

        provider_row = ttk.Frame(provider_frame)
        provider_row.pack(fill=tk.X, pady=5)

        ttk.Label(provider_row, text="Provider:", width=15).pack(side=tk.LEFT)
        provider_combo = ttk.Combobox(
            provider_row,
            textvariable=self.provider_var,
            values=list(API_PROVIDERS.keys()),
            state="readonly",
            width=20,
        )
        provider_combo.pack(side=tk.LEFT, padx=5)
        provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)
        self._provider_combo_ref = provider_combo

        ttk.Button(
            provider_row, text="Details",
            command=self._show_available_models,
        ).pack(side=tk.LEFT, padx=(10, 5))

        ttk.Label(provider_row, text="Cost Cap: $").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Spinbox(
            provider_row,
            from_=0.0,
            to=999.0,
            increment=1.0,
            textvariable=self.cost_cap_var,
            width=8,
        ).pack(side=tk.LEFT)

        self._test_status_label = ttk.Label(provider_row, text="")
        self._test_status_label.pack(side=tk.LEFT, padx=5)

        # API Key
        key_row = ttk.Frame(provider_frame)
        key_row.pack(fill=tk.X, pady=5)

        ttk.Label(key_row, text="API Key:", width=15).pack(side=tk.LEFT)
        self._api_key_entry = ttk.Entry(key_row, textvariable=self.api_key_var, width=40, show="•")
        self._api_key_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(key_row, text="Save", width=5, command=self._save_api_key).pack(side=tk.LEFT, padx=(2, 0))

        self._show_key_var = tk.BooleanVar(value=False)
        show_btn = ttk.Checkbutton(key_row, text="Show", variable=self._show_key_var, command=self._toggle_key_visibility)
        show_btn.pack(side=tk.LEFT, padx=5)

        # Base URL
        url_row = ttk.Frame(provider_frame)
        url_row.pack(fill=tk.X, pady=5)

        ttk.Label(url_row, text="Base URL:", width=15).pack(side=tk.LEFT)
        ttk.Entry(url_row, textvariable=self.base_url_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        url_help = ttk.Label(provider_frame, text="Leave empty for default. Required for Gemini and custom endpoints.", foreground="gray")
        url_help.pack(anchor=tk.W, pady=(0, 5))

        # Model Settings removed — model is now selected per-key in
        # the Translation Step.  Temperature moved to Request Settings.
        # Keep hidden references for backward compatibility.
        self._model_combo = ttk.Combobox(panel, textvariable=self.model_var)
        # Don't pack — hidden widget for settings persistence only
        self._refresh_models_btn = None
        self._refresh_models_label = None
        self._update_model_list()

        # ---- Saved API Keys ----
        keys_frame = ttk.LabelFrame(panel, text="Saved API Keys", padding=10)
        keys_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Treeview
        cols = ("name", "provider")
        self._providers_tree = ttk.Treeview(
            keys_frame, columns=cols, show="headings", height=5,
        )
        self._providers_tree.heading("name", text="Name")
        self._providers_tree.heading("provider", text="Provider")
        self._providers_tree.column("name", width=200)
        self._providers_tree.column("provider", width=120)
        self._providers_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # Scrollbar
        prov_scroll = ttk.Scrollbar(
            keys_frame, orient="vertical",
            command=self._providers_tree.yview,
        )
        self._providers_tree.configure(yscrollcommand=prov_scroll.set)
        prov_scroll.pack(side=tk.LEFT, fill=tk.Y)

        # Buttons
        key_btns = ttk.Frame(keys_frame)
        key_btns.pack(side=tk.LEFT, padx=(10, 0), fill=tk.Y)

        ttk.Button(key_btns, text="Load Key", width=10, command=self._load_api_key).pack(pady=2)
        ttk.Button(key_btns, text="Remove", width=10, command=self._remove_api_key).pack(pady=2)

        # Populate from API.ini
        self._refresh_providers_tree()

    def _get_cost_cap_value(self) -> float:
        """Return the current cost cap, clamped to the supported range."""
        try:
            value = float(self.cost_cap_var.get())
        except (TypeError, ValueError, tk.TclError):
            value = _model_registry.get_configured_cost_cap()

        value = max(0.0, min(999.0, value))
        try:
            self.cost_cap_var.set(value)
        except tk.TclError:
            pass
        return value

    def _build_request_section(self) -> None:
        """Build the request settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.REQUEST] = panel

        # Section header
        header = ttk.Label(panel, text="Model Settings", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.REQUEST], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Model Selection (V8: per-model settings)
        model_frame = ttk.LabelFrame(panel, text="Model Selection", padding=10)
        model_frame.pack(fill=tk.X, pady=(0, 10))

        model_row = ttk.Frame(model_frame)
        model_row.pack(fill=tk.X, pady=5)

        ttk.Label(model_row, text="Model:", width=18).pack(side=tk.LEFT)
        self._settings_model_combo = ttk.Combobox(
            model_row, textvariable=self.model_var, width=35,
        )
        self._settings_model_combo.pack(side=tk.LEFT, padx=5)

        self._model_info_label = ttk.Label(
            model_frame,
            text="Settings below are stored per model.",
            foreground="gray",
        )
        self._model_info_label.pack(anchor=tk.W, pady=(0, 5))

        # Keep combo values in sync with provider's models
        self._sync_settings_model_combo()

        # Settings frame
        settings_frame = ttk.LabelFrame(panel, text="Request Parameters", padding=10)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # Chunk size
        chunk_row = ttk.Frame(settings_frame)
        chunk_row.pack(fill=tk.X, pady=5)

        ttk.Label(chunk_row, text="Lines per Request:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(chunk_row, from_=1, to=99999, textvariable=self.chunk_size_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(chunk_row, text="(min 1, default: 50)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # Max input tokens per request (Task 41)
        tokens_row = ttk.Frame(settings_frame)
        tokens_row.pack(fill=tk.X, pady=5)

        ttk.Label(tokens_row, text="Max Input Tokens:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            tokens_row, from_=0, to=128000, increment=500,
            textvariable=self.max_input_tokens_var, width=10,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            tokens_row,
            text="(0 = no limit, input lines only)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        # Timeout
        timeout_row = ttk.Frame(settings_frame)
        timeout_row.pack(fill=tk.X, pady=5)

        ttk.Label(timeout_row, text="Timeout (seconds):", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(timeout_row, from_=10, to=600, textvariable=self.timeout_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(timeout_row, text="(10-600, default: 60)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # Retries
        retries_row = ttk.Frame(settings_frame)
        retries_row.pack(fill=tk.X, pady=5)

        ttk.Label(retries_row, text="Max Retries:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(retries_row, from_=0, to=10, textvariable=self.retries_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(retries_row, text="(0-10, default: 3)", foreground="gray").pack(side=tk.LEFT, padx=5)

        backoff_mode_row = ttk.Frame(settings_frame)
        backoff_mode_row.pack(fill=tk.X, pady=5)

        ttk.Label(backoff_mode_row, text="Temp. Backoff:", width=18).pack(side=tk.LEFT)
        ttk.Combobox(
            backoff_mode_row,
            textvariable=self.temporary_backoff_mode_var,
            values=["linear", "exponential"],
            state="readonly",
            width=18,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            backoff_mode_row,
            text="(used only for timeout/server/connection retries)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        backoff_attempts_row = ttk.Frame(settings_frame)
        backoff_attempts_row.pack(fill=tk.X, pady=5)

        ttk.Label(backoff_attempts_row, text="Backoff Attempts:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            backoff_attempts_row,
            from_=0,
            to=20,
            textvariable=self.temporary_backoff_attempts_var,
            width=10,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            backoff_attempts_row,
            text="(temporary failures only)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        backoff_total_row = ttk.Frame(settings_frame)
        backoff_total_row.pack(fill=tk.X, pady=5)

        ttk.Label(backoff_total_row, text="Backoff Budget (s):", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            backoff_total_row,
            from_=0,
            to=3600,
            textvariable=self.temporary_backoff_total_seconds_var,
            width=10,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            backoff_total_row,
            text="(total wait cap across temporary retries)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        # Number of Threads
        threads_row = ttk.Frame(settings_frame)
        threads_row.pack(fill=tk.X, pady=5)

        ttk.Label(threads_row, text="Number of Threads:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            threads_row,
            from_=1,
            to=512,
            textvariable=self.max_concurrent_var,
            width=10,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            threads_row,
            text="(parallel request strings per model, default: 3)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        # Rate limit
        rate_row = ttk.Frame(settings_frame)
        rate_row.pack(fill=tk.X, pady=5)

        ttk.Label(rate_row, text="Rate Limit (req/min):", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(rate_row, from_=1, to=1000, textvariable=self.rate_limit_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(rate_row, text="(1-1000, default: 60)", foreground="gray").pack(side=tk.LEFT, padx=5)

        rps_row = ttk.Frame(settings_frame)
        rps_row.pack(fill=tk.X, pady=5)

        ttk.Label(rps_row, text="Rate Limit (req/sec):", width=18).pack(side=tk.LEFT)
        ttk.Checkbutton(
            rps_row,
            text="Enable",
            variable=self.requests_per_second_enabled_var,
            command=self._update_rps_widget_state,
        ).pack(side=tk.LEFT, padx=(0, 8))
        self._rps_spin = ttk.Spinbox(
            rps_row,
            from_=0.01,
            to=999.99,
            increment=0.01,
            textvariable=self.requests_per_second_var,
            width=10,
            format="%.2f",
        )
        self._rps_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            rps_row,
            text="(optional dispatch cap, default: off)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        # Model Tuning
        think_frame = ttk.LabelFrame(panel, text="Model Tuning", padding=10)
        think_frame.pack(fill=tk.X, pady=(0, 10))
        self._think_frame = think_frame

        temp_row = ttk.Frame(think_frame)
        temp_row.pack(fill=tk.X, pady=5)
        self._temp_row = temp_row

        ttk.Label(temp_row, text="Temperature:", width=18).pack(side=tk.LEFT)
        self._temp_scale = ttk.Scale(
            temp_row, from_=0.0, to=2.0,
            variable=self.temperature_var,
            orient=tk.HORIZONTAL, length=200,
        )
        self._temp_scale.pack(side=tk.LEFT, padx=5)

        self._temp_label = ttk.Label(
            temp_row, text=f"{self.temperature_var.get():.1f}",
        )
        self._temp_label.pack(side=tk.LEFT, padx=5)
        self.temperature_var.trace_add("write", self._update_temp_label)

        self._temp_hint_label = ttk.Label(
            think_frame,
            text="Lower = more deterministic, Higher = more creative (0.0-2.0)",
            foreground="gray",
        )
        self._temp_hint_label.pack(anchor=tk.W, pady=(0, 5))
        self._temp_warning_label = ttk.Label(think_frame, text="", foreground="#cc6600")
        self._temp_warning_label.pack(anchor=tk.W, pady=(0, 5))

        top_p_row = ttk.Frame(think_frame)
        top_p_row.pack(fill=tk.X, pady=5)
        self._top_p_row = top_p_row

        ttk.Label(top_p_row, text="Top P:", width=18).pack(side=tk.LEFT)
        self._top_p_scale = ttk.Scale(
            top_p_row,
            from_=0.0,
            to=1.0,
            variable=self.top_p_var,
            orient=tk.HORIZONTAL,
            length=200,
        )
        self._top_p_scale.pack(side=tk.LEFT, padx=5)
        self._top_p_label = ttk.Label(top_p_row, text=f"{self.top_p_var.get():.2f}")
        self._top_p_label.pack(side=tk.LEFT, padx=5)
        self.top_p_var.trace_add("write", self._update_top_p_label)
        self._top_p_hint_label = ttk.Label(
            think_frame,
            text="Lower narrows token sampling; keep near 1.0 unless you need tighter output.",
            foreground="gray",
        )
        self._top_p_hint_label.pack(anchor=tk.W, pady=(0, 5))
        self._top_p_warning_label = ttk.Label(think_frame, text="", foreground="#cc6600")
        self._top_p_warning_label.pack(anchor=tk.W, pady=(0, 5))

        freq_row = ttk.Frame(think_frame)
        freq_row.pack(fill=tk.X, pady=5)
        self._frequency_penalty_row = freq_row

        ttk.Label(freq_row, text="Frequency Penalty:", width=18).pack(side=tk.LEFT)
        self._frequency_penalty_scale = ttk.Scale(
            freq_row,
            from_=-2.0,
            to=2.0,
            variable=self.frequency_penalty_var,
            orient=tk.HORIZONTAL,
            length=200,
        )
        self._frequency_penalty_scale.pack(side=tk.LEFT, padx=5)
        self._frequency_penalty_label = ttk.Label(
            freq_row,
            text=f"{self.frequency_penalty_var.get():.2f}",
        )
        self._frequency_penalty_label.pack(side=tk.LEFT, padx=5)
        self.frequency_penalty_var.trace_add(
            "write", self._update_frequency_penalty_label,
        )
        self._frequency_penalty_hint_label = ttk.Label(
            think_frame,
            text="Positive values discourage repetition; negatives boost recurrence.",
            foreground="gray",
        )
        self._frequency_penalty_hint_label.pack(anchor=tk.W, pady=(0, 5))
        self._frequency_penalty_warning_label = ttk.Label(
            think_frame,
            text="",
            foreground="#cc6600",
        )
        self._frequency_penalty_warning_label.pack(anchor=tk.W, pady=(0, 5))

        presence_row = ttk.Frame(think_frame)
        presence_row.pack(fill=tk.X, pady=5)
        self._presence_penalty_row = presence_row

        ttk.Label(presence_row, text="Presence Penalty:", width=18).pack(side=tk.LEFT)
        self._presence_penalty_scale = ttk.Scale(
            presence_row,
            from_=-2.0,
            to=2.0,
            variable=self.presence_penalty_var,
            orient=tk.HORIZONTAL,
            length=200,
        )
        self._presence_penalty_scale.pack(side=tk.LEFT, padx=5)
        self._presence_penalty_label = ttk.Label(
            presence_row,
            text=f"{self.presence_penalty_var.get():.2f}",
        )
        self._presence_penalty_label.pack(side=tk.LEFT, padx=5)
        self.presence_penalty_var.trace_add(
            "write", self._update_presence_penalty_label,
        )
        self._presence_penalty_hint_label = ttk.Label(
            think_frame,
            text="Positive values encourage new tokens; negatives reinforce existing patterns.",
            foreground="gray",
        )
        self._presence_penalty_hint_label.pack(anchor=tk.W, pady=(0, 5))
        self._presence_penalty_warning_label = ttk.Label(
            think_frame,
            text="",
            foreground="#cc6600",
        )
        self._presence_penalty_warning_label.pack(anchor=tk.W, pady=(0, 5))

        think_check = ttk.Checkbutton(
            think_frame, text="Enable Thinking Mode",
            variable=self.thinking_enabled_var,
        )
        think_check.pack(anchor=tk.W, pady=2)
        self._thinking_cb = think_check

        budget_row = ttk.Frame(think_frame)
        budget_row.pack(fill=tk.X, pady=5)
        ttk.Label(budget_row, text="Thinking Budget:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            budget_row, from_=1000, to=100000, increment=1000,
            textvariable=self.thinking_budget_var, width=10,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(budget_row, text="tokens (1000-100000)", foreground="gray").pack(
            side=tk.LEFT, padx=5,
        )
        self._thinking_budget_row = budget_row

        effort_row = ttk.Frame(think_frame)
        effort_row.pack(fill=tk.X, pady=5)
        ttk.Label(effort_row, text="Reasoning Effort:", width=18).pack(side=tk.LEFT)
        self._reasoning_effort_combo = ttk.Combobox(
            effort_row, textvariable=self.reasoning_effort_var,
            values=["low", "medium", "high"], state="readonly", width=10,
        )
        self._reasoning_effort_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            effort_row, text="(low / medium / high)", foreground="gray",
        ).pack(side=tk.LEFT, padx=5)
        self._reasoning_effort_row = effort_row

        think_help = ttk.Label(
            think_frame,
            text="Applies extended thinking for Claude and reasoning effort for OpenAI models.",
            foreground="gray",
        )
        think_help.pack(anchor=tk.W, pady=(0, 2))

        think_warn = ttk.Label(
            think_frame,
            text=(
                "⚠ Thinking/reasoning significantly increases cost and latency. "
                "It is not known to improve translation quality and may even "
                "negatively affect it."
            ),
            foreground="#cc6600",
            wraplength=450,
        )
        think_warn.pack(anchor=tk.W, pady=(0, 5))

        self._update_rps_widget_state()
        self._refresh_tuning_warnings()

    def _build_translation_section(self) -> None:
        """Build the Translation Options section.

        Contains workflow defaults, request-level knobs that affect
        translation behaviour (rolling context, speaker dedup, retry
        strategy, request slicing, consistency), and output toggles.
        """
        panel = self._create_scrollable_panel(OptionSection.TRANSLATION)

        # Section header
        header = ttk.Label(
            panel, text="Translation Options",
            font=("TkDefaultFont", 12, "bold"),
        )
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(
            panel,
            text=SECTION_DESCRIPTIONS[OptionSection.TRANSLATION],
            foreground="gray",
        )
        desc.pack(anchor="w", pady=(0, 15))

        # --- Workflow Defaults ---
        wf_frame = ttk.LabelFrame(panel, text="Workflow Defaults", padding=10)
        wf_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Checkbutton(
            wf_frame, text="Overwrite Translation (re-translate already translated lines)",
            variable=self.overwrite_translation_var,
        ).pack(anchor=tk.W, pady=2)

        ttk.Checkbutton(
            wf_frame, text="Skip Non-Source Language Lines",
            variable=self.skip_non_source_var,
        ).pack(anchor=tk.W, pady=2)

        ttk.Label(
            wf_frame,
            text="These defaults apply when creating new projects.",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(5, 0))

        # --- Rolling Context (moved from Model Settings) ---
        ctx_frame = ttk.LabelFrame(panel, text="Rolling Context", padding=10)
        ctx_frame.pack(fill=tk.X, pady=(0, 10))

        # Lines (Before)
        ctx_row_before = ttk.Frame(ctx_frame)
        ctx_row_before.pack(fill=tk.X, pady=2)
        ttk.Label(ctx_row_before, text="Lines (Before):", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            ctx_row_before, from_=0, to=10,
            textvariable=self.rolling_context_var, width=10,
        ).pack(side=tk.LEFT, padx=5)

        # Lines (Between)
        ctx_row_between = ttk.Frame(ctx_frame)
        ctx_row_between.pack(fill=tk.X, pady=2)
        ttk.Label(ctx_row_between, text="Lines (Between):", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            ctx_row_between, from_=0, to=10,
            textvariable=self.rolling_context_between_var, width=10,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            ctx_row_between,
            text="(skipped lines inserted between input lines)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        # Lines (After)
        ctx_row_after = ttk.Frame(ctx_frame)
        ctx_row_after.pack(fill=tk.X, pady=2)
        ttk.Label(ctx_row_after, text="Lines (After):", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            ctx_row_after, from_=0, to=10,
            textvariable=self.rolling_context_after_var, width=10,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            ctx_row_after,
            text="(following translated lines appended for forward context)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        # Prefer Translated
        ttk.Checkbutton(
            ctx_frame,
            text="Prefer translated lines over originals for context",
            variable=self.use_translated_context_var,
        ).pack(anchor=tk.W, pady=(5, 0))

        # --- Speaker Dedup (moved from Model Settings) ---
        speaker_frame = ttk.LabelFrame(
            panel, text="Speaker Deduplication", padding=10,
        )
        speaker_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Checkbutton(
            speaker_frame,
            text="Remove duplicate speakers",
            variable=self.remove_dup_speakers_var,
        ).pack(anchor=tk.W, pady=5)

        ttk.Label(
            speaker_frame,
            text="Strip repeated speaker prefixes in consecutive lines to save tokens.",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

        # --- Retry Strategy (moved from Request Options in Translation step) ---
        retry_frame = ttk.LabelFrame(panel, text="Retry Strategy", padding=10)
        retry_frame.pack(fill=tk.X, pady=(0, 10))

        retry_row = ttk.Frame(retry_frame)
        retry_row.pack(fill=tk.X, pady=5)
        ttk.Label(retry_row, text="Strategy:", width=18).pack(side=tk.LEFT)
        ttk.Combobox(
            retry_row,
            textvariable=self.retry_strategy_var,
            values=["batch", "line", "merge"],
            state="readonly",
            width=22,
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            retry_frame,
            text="How failed chunks are retried: batch (resend), line (split), merge (recombine).",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

        # --- Request Slicing ---
        slice_frame = ttk.LabelFrame(panel, text="Request Slicing", padding=10)
        slice_frame.pack(fill=tk.X, pady=(0, 10))

        slice_row = ttk.Frame(slice_frame)
        slice_row.pack(fill=tk.X, pady=5)
        ttk.Label(slice_row, text="Mode:", width=18).pack(side=tk.LEFT)
        ttk.Combobox(
            slice_row,
            textvariable=self.request_slicing_var,
            values=["conservative", "efficient"],
            state="readonly",
            width=22,
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            slice_frame,
            text="Conservative keeps original chunking. Efficient merges small requests "
            "to reduce API calls.",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

        # --- Character Validation (Phase 78) ---
        charval_frame = ttk.LabelFrame(
            panel, text="Character Validation", padding=10,
        )
        charval_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Checkbutton(
            charval_frame,
            text="Exchange forbidden characters via Autofix Map",
            variable=self.exchange_forbidden_var,
        ).pack(anchor=tk.W, pady=2)

        ttk.Checkbutton(
            charval_frame,
            text="Flag lines with forbidden characters for QA review",
            variable=self.flag_qa_review_var,
        ).pack(anchor=tk.W, pady=2)

        ttk.Checkbutton(
            charval_frame,
            text="Retry lines that contain forbidden characters",
            variable=self.retry_forbidden_var,
        ).pack(anchor=tk.W, pady=2)

        ttk.Label(
            charval_frame,
            text="Controls how blacklisted/whitelisted character violations are handled "
            "after translation.",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

        # --- Consistency Mode (Phase 55) ---
        consist_frame = ttk.LabelFrame(
            panel, text="Consistency System", padding=10,
        )
        consist_frame.pack(fill=tk.X, pady=(0, 10))

        consist_row = ttk.Frame(consist_frame)
        consist_row.pack(fill=tk.X, pady=5)
        ttk.Label(consist_row, text="Mode:", width=18).pack(side=tk.LEFT)
        ttk.Combobox(
            consist_row,
            textvariable=self.consistency_mode_var,
            values=["disabled", "preliminary", "during", "check"],
            state="readonly",
            width=22,
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            consist_frame,
            text="Ensure recurring terms are translated consistently across all requests.",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

    def _build_caching_section(self) -> None:
        """Build the caching settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.CACHING] = panel

        # Section header
        header = ttk.Label(panel, text="Caching", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.CACHING], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Enable caching
        enable_check = ttk.Checkbutton(panel, text="Enable request caching", variable=self.cache_enabled_var)
        enable_check.pack(anchor=tk.W, pady=5)

        # Cache mode (Task 43.7)
        mode_row = ttk.Frame(panel)
        mode_row.pack(fill=tk.X, pady=5)
        ttk.Label(mode_row, text="Cache Mode:", width=15).pack(side=tk.LEFT)
        cache_modes = ["disabled", "line", "strict", "model_only", "any"]
        ttk.Combobox(
            mode_row, textvariable=self.cache_mode_var,
            values=cache_modes, state="readonly", width=15,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            mode_row,
            text="(line = per-line match, strict = exact request, any = model-agnostic)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        # Cache settings frame
        cache_frame = ttk.LabelFrame(panel, text="Cache Settings", padding=10)
        cache_frame.pack(fill=tk.X, pady=(0, 10))

        # Cache directory
        dir_row = ttk.Frame(cache_frame)
        dir_row.pack(fill=tk.X, pady=5)

        ttk.Label(dir_row, text="Cache Directory:", width=15).pack(side=tk.LEFT)
        ttk.Entry(dir_row, textvariable=self.cache_dir_var, width=30).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(dir_row, text="Browse...", command=self._browse_cache_dir).pack(side=tk.LEFT, padx=5)

        # Max age
        age_row = ttk.Frame(cache_frame)
        age_row.pack(fill=tk.X, pady=5)

        ttk.Label(age_row, text="Max Age (days):", width=15).pack(side=tk.LEFT)
        ttk.Spinbox(age_row, from_=0, to=365, textvariable=self.cache_max_age_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(age_row, text="(0 = unlimited)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # Max size
        size_row = ttk.Frame(cache_frame)
        size_row.pack(fill=tk.X, pady=5)

        ttk.Label(size_row, text="Max Size (MB):", width=15).pack(side=tk.LEFT)
        ttk.Spinbox(size_row, from_=0, to=10000, textvariable=self.cache_max_size_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(size_row, text="(0 = unlimited)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # Clear cache button
        clear_frame = ttk.Frame(panel)
        clear_frame.pack(fill=tk.X, pady=10)

        ttk.Button(clear_frame, text="Clear Cache", command=self._clear_cache).pack(side=tk.LEFT)

    def _build_logging_section(self) -> None:
        """Build the logging settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.LOGGING] = panel

        # Section header
        header = ttk.Label(panel, text="Logging", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.LOGGING], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Logging settings frame
        log_frame = ttk.LabelFrame(panel, text="Log Configuration", padding=10)
        log_frame.pack(fill=tk.X, pady=(0, 10))

        # Log level
        level_row = ttk.Frame(log_frame)
        level_row.pack(fill=tk.X, pady=5)

        ttk.Label(level_row, text="Log Level:", width=15).pack(side=tk.LEFT)
        level_combo = ttk.Combobox(
            level_row,
            textvariable=self.log_level_var,
            values=[l.value for l in LogLevel],
            state="readonly",
            width=15,
        )
        level_combo.pack(side=tk.LEFT, padx=5)

        # Log location (directory)
        file_row = ttk.Frame(log_frame)
        file_row.pack(fill=tk.X, pady=5)

        ttk.Label(file_row, text="Log Directory:", width=15).pack(side=tk.LEFT)
        ttk.Entry(file_row, textvariable=self.log_file_var, width=30).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(file_row, text="Browse...", command=self._browse_log_file).pack(side=tk.LEFT, padx=5)

        # Debug mode
        debug_check = ttk.Checkbutton(panel, text="Enable debug mode (verbose logging)", variable=self.debug_mode_var)
        debug_check.pack(anchor=tk.W, pady=5)

        # Log API requests/responses
        api_check = ttk.Checkbutton(panel, text="Log API requests/responses", variable=self.log_api_calls_var)
        api_check.pack(anchor=tk.W, pady=5)

        # Log outgoing requests as JSON files
        req_check = ttk.Checkbutton(
            panel,
            text="Log outgoing requests as JSON (for debugging)",
            variable=self.log_requests_var,
        )
        req_check.pack(anchor=tk.W, pady=5)

        # Open log button
        open_frame = ttk.Frame(panel)
        open_frame.pack(fill=tk.X, pady=10)

        ttk.Button(open_frame, text="Open Log File", command=self._open_log_file).pack(side=tk.LEFT)

    def _build_session_section(self) -> None:
        """Build the session settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.SESSION] = panel

        # Section header
        header = ttk.Label(panel, text="Session", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.SESSION], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Autosave settings
        autosave_frame = ttk.LabelFrame(panel, text="Autosave", padding=10)
        autosave_frame.pack(fill=tk.X, pady=(0, 10))

        autosave_check = ttk.Checkbutton(autosave_frame, text="Enable autosave", variable=self.autosave_enabled_var)
        autosave_check.pack(anchor=tk.W, pady=5)

        interval_row = ttk.Frame(autosave_frame)
        interval_row.pack(fill=tk.X, pady=5)

        ttk.Label(interval_row, text="Interval (seconds):", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(interval_row, from_=10, to=600, textvariable=self.autosave_interval_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_row, text="(10-600, default: 60)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # Behavior settings
        restore_check = ttk.Checkbutton(panel, text="Load last project on launch", variable=self.restore_on_launch_var)
        restore_check.pack(anchor=tk.W, pady=5)

        # Confirmation dialogs reset
        confirm_frame = ttk.LabelFrame(panel, text="Confirmation Dialogs", padding=10)
        confirm_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(
            confirm_frame,
            text=(
                "Some dialogs have a 'Don't ask again' option.\n"
                "Click below to re-enable all suppressed dialogs."
            ),
            justify="left",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Button(
            confirm_frame,
            text="Reset All Confirmation Dialogs",
            command=self._on_reset_confirmations,
        ).pack(anchor=tk.W)

        # Restore Defaults
        restore_frame = ttk.LabelFrame(panel, text="Restore Defaults", padding=10)
        restore_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(
            restore_frame,
            text=(
                "Reset selected settings areas to factory defaults.\n"
                "Choose which areas to restore in the next dialog."
            ),
            justify="left",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Button(
            restore_frame,
            text="Restore Defaults…",
            command=self._on_restore_defaults,
        ).pack(anchor=tk.W)

    def _build_gui_section(self) -> None:
        """Build the GUI settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.GUI] = panel

        header = ttk.Label(panel, text="GUI", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.GUI], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        design_frame = ttk.LabelFrame(panel, text="Design", padding=10)
        design_frame.pack(fill=tk.X, pady=(0, 10))

        design_row = ttk.Frame(design_frame)
        design_row.pack(fill=tk.X, pady=5)

        ttk.Label(design_row, text="Design:", width=15).pack(side=tk.LEFT)
        ttk.Combobox(
            design_row,
            textvariable=self.gui_design_var,
            values=get_theme_display_names(),
            state="readonly",
            width=22,
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            design_frame,
            text="Pale Blue keeps the current look. The dark designs switch text to white and use alternating grey table rows.",
            foreground="gray",
            wraplength=520,
            justify="left",
        ).pack(anchor=tk.W, pady=(2, 0))

        window_frame = ttk.LabelFrame(panel, text="Window Behavior", padding=10)
        window_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Checkbutton(
            window_frame,
            text="Save all window dimensions",
            variable=self.save_window_dimensions_var,
        ).pack(anchor=tk.W, pady=3)

        ttk.Checkbutton(
            window_frame,
            text="Launch every window maximized",
            variable=self.launch_maximized_var,
        ).pack(anchor=tk.W, pady=3)

        ttk.Label(
            window_frame,
            text="Saved dimensions restore each window's last normal size. Maximized launch overrides saved sizes until disabled.",
            foreground="gray",
            wraplength=520,
            justify="left",
        ).pack(anchor=tk.W, pady=(4, 0))

    def _build_limit_section(self) -> None:
        """Build the limits settings section (replaces old Safety section)."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.LIMIT] = panel

        # Section header
        header = ttk.Label(panel, text="Limits", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.LIMIT], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Banned characters
        ban_frame = ttk.LabelFrame(panel, text="Banned Characters", padding=10)
        ban_frame.pack(fill=tk.X, pady=(0, 10))

        ban_info = ttk.Label(
            ban_frame,
            text="Comma-separated list of characters to ban from output.\n"
                 "Example: \u2014, \u2013  (em-dash, en-dash)",
            justify="left",
        )
        ban_info.pack(anchor=tk.W, pady=(0, 5))

        ban_row = ttk.Frame(ban_frame)
        ban_row.pack(fill=tk.X, pady=5)

        ttk.Label(ban_row, text="Banned:", width=12).pack(side=tk.LEFT)
        ttk.Entry(ban_row, textvariable=self.ban_tokens_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Output limits
        limit_frame = ttk.LabelFrame(panel, text="Output Limits", padding=10)
        limit_frame.pack(fill=tk.X, pady=(0, 10))

        tokens_row = ttk.Frame(limit_frame)
        tokens_row.pack(fill=tk.X, pady=5)

        ttk.Label(tokens_row, text="Max Output Tokens:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(tokens_row, from_=256, to=16384, textvariable=self.max_output_tokens_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(tokens_row, text="(256-16384, default: 4096)", foreground="gray").pack(side=tk.LEFT, padx=5)

        warning_row = ttk.Frame(panel)
        warning_row.pack(anchor=tk.W, pady=5)
        ttk.Checkbutton(
            warning_row,
            variable=self.warning_abort_enabled_var,
        ).pack(side=tk.LEFT)
        ttk.Label(warning_row, text="Abort after").pack(side=tk.LEFT, padx=(6, 6))
        ttk.Spinbox(
            warning_row,
            from_=1,
            to=999,
            textvariable=self.warning_abort_after_var,
            width=6,
        ).pack(side=tk.LEFT)
        ttk.Label(warning_row, text="Unsafe Request").pack(side=tk.LEFT, padx=(6, 0))

        # Safe mode
        safe_check = ttk.Checkbutton(
            panel,
            text="Skip unsafe requests",
            variable=self.skip_unsafe_requests_var,
        )
        safe_check.pack(anchor=tk.W, pady=5)

    def _build_file_io_section(self) -> None:
        """Build the file I/O settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.FILE_IO] = panel

        # Section header
        header = ttk.Label(panel, text="File I/O", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.FILE_IO], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Encoding settings
        encoding_frame = ttk.LabelFrame(panel, text="Encoding", padding=10)
        encoding_frame.pack(fill=tk.X, pady=(0, 10))

        enc_row = ttk.Frame(encoding_frame)
        enc_row.pack(fill=tk.X, pady=5)

        ttk.Label(enc_row, text="Default Encoding:", width=18).pack(side=tk.LEFT)
        enc_combo = ttk.Combobox(
            enc_row,
            textvariable=self.encoding_var,
            values=[e.value for e in EncodingOption],
            width=15,
        )
        enc_combo.pack(side=tk.LEFT, padx=5)

        bom_check = ttk.Checkbutton(encoding_frame, text="Preserve BOM (Byte Order Mark) when present", variable=self.preserve_bom_var)
        bom_check.pack(anchor=tk.W, pady=5)

        # Line ending settings
        line_frame = ttk.LabelFrame(panel, text="Line Endings", padding=10)
        line_frame.pack(fill=tk.X, pady=(0, 10))

        line_row = ttk.Frame(line_frame)
        line_row.pack(fill=tk.X, pady=5)

        ttk.Label(line_row, text="Line Ending:", width=18).pack(side=tk.LEFT)
        line_combo = ttk.Combobox(
            line_row,
            textvariable=self.line_ending_var,
            values=[l.value for l in LineEnding],
            state="readonly",
            width=15,
        )
        line_combo.pack(side=tk.LEFT, padx=5)

        line_help = ttk.Label(line_frame, text="auto: Detect from input file, LF: Unix, CRLF: Windows, CR: Classic Mac", foreground="gray")
        line_help.pack(anchor=tk.W, pady=(0, 5))

        # Backup settings
        backup_check = ttk.Checkbutton(panel, text="Create backup of original files before overwriting", variable=self.backup_originals_var)
        backup_check.pack(anchor=tk.W, pady=5)

    # Alias kept for any call sites that still use the old name
    _build_safety_section = _build_limit_section  # type: ignore[assignment]

    def _build_prompts_section(self) -> None:
        """Build the prompts settings section for Edit and TLC steps."""
        panel = self._create_scrollable_panel(OptionSection.PROMPTS)

        # Section header
        header = ttk.Label(panel, text="Custom Prompts", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.PROMPTS], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Info about placeholders
        placeholder_info = ttk.Label(
            panel,
            text="Use {source_lang} and {target_lang} as placeholders for the configured languages.",
            foreground="gray",
            font=("TkDefaultFont", 9, "italic"),
        )
        placeholder_info.pack(anchor="w", pady=(0, 10))

        # ── Utility Prompts (Term Translation + Gender Inference) ─────────
        _util_entries = [
            (
                "Translate Terms — Glossary",
                "Prompt sent when translating character names / glossary terms.",
                self.term_glossary_prompt_var,
                "_term_glossary_prompt_text",
                DEFAULT_TERM_GLOSSARY_PROMPT,
            ),
            (
                "Translate Terms — Code",
                "Prompt sent when translating code-pattern labels.",
                self.term_code_prompt_var,
                "_term_code_prompt_text",
                DEFAULT_TERM_CODE_PROMPT,
            ),
            (
                "Gender Inference",
                "Prompt sent for LLM-based gender inference of speakers.",
                self.gender_inference_prompt_var,
                "_gender_inference_prompt_text",
                DEFAULT_GENDER_INFERENCE_PROMPT,
            ),
        ]

        for _label, _desc_text, _var, _attr, _default in _util_entries:
            uf = ttk.LabelFrame(panel, text=_label, padding=10)
            uf.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            ttk.Label(uf, text=_desc_text, foreground="gray").pack(
                anchor="w", pady=(0, 5),
            )

            tc = ttk.Frame(uf)
            tc.pack(fill=tk.BOTH, expand=True, pady=5)

            tw = tk.Text(tc, height=4, width=60, wrap=tk.WORD)
            tw.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tw.insert("1.0", _var.get())
            setattr(self, _attr, tw)

            sb = ttk.Scrollbar(tc, orient=tk.VERTICAL, command=tw.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            tw.config(yscrollcommand=sb.set)

            def _make_reset(widget: tk.Text, default: str) -> Any:
                def _reset() -> None:
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", default)
                return _reset

            br = ttk.Frame(uf)
            br.pack(anchor="w", pady=(5, 0))
            ttk.Button(
                br, text="Reset to Default",
                command=_make_reset(tw, _default),
            ).pack(side=tk.LEFT)

        # ── Edit Step Prompt (hidden — kept for data round-trip) ──────────
        # The widgets are created but *not* packed so _on_apply can still
        # read their contents.  The edit prompt text is populated invisibly.
        edit_frame = ttk.LabelFrame(panel, text="Edit Step Prompt", padding=10)
        # edit_frame intentionally NOT packed — hidden per user request

        edit_desc = ttk.Label(
            edit_frame,
            text="This prompt is used for the Edit steps to improve translations.",
            foreground="gray",
        )
        edit_desc.pack(anchor="w", pady=(0, 5))

        # Text widget for edit prompt (multi-line)
        edit_text_frame = ttk.Frame(edit_frame)
        edit_text_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self._edit_prompt_text = tk.Text(edit_text_frame, height=5, width=60, wrap=tk.WORD)
        self._edit_prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._edit_prompt_text.insert("1.0", self.edit_prompt_var.get())

        edit_scroll = ttk.Scrollbar(edit_text_frame, orient=tk.VERTICAL, command=self._edit_prompt_text.yview)
        edit_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._edit_prompt_text.config(yscrollcommand=edit_scroll.set)

        # Reset to default button for edit prompt
        edit_btn_frame = ttk.Frame(edit_frame)
        edit_btn_frame.pack(anchor="w", pady=(5, 0))
        ttk.Button(edit_btn_frame, text="Reset to Default", command=self._reset_edit_prompt).pack(side=tk.LEFT)

        # Edit component toggles
        edit_components_frame = ttk.LabelFrame(edit_frame, text="Include in Edit Prompt", padding=5)
        edit_components_frame.pack(fill=tk.X, pady=(10, 0))

        edit_comp_row1 = ttk.Frame(edit_components_frame)
        edit_comp_row1.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(edit_comp_row1, text="Glossary", variable=self.edit_include_glossary_var).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(edit_comp_row1, text="Game Summary", variable=self.edit_include_game_summary_var).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(edit_comp_row1, text="Code Glossary", variable=self.edit_include_code_glossary_var).pack(side=tk.LEFT, padx=10)

        # PHASE 37: Edit input policy
        edit_policy_row = ttk.Frame(edit_frame)
        edit_policy_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(edit_policy_row, text="Input Source:").pack(side=tk.LEFT)
        edit_policy_combo = ttk.Combobox(
            edit_policy_row,
            textvariable=self.edit_input_policy_var,
            values=[e.value for e in EditInputPolicy],
            state="readonly",
            width=18,
        )
        edit_policy_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(edit_policy_row, text="(What text fields feed the Edit prompt)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # TLC prompt frame
        tlc_frame = ttk.LabelFrame(panel, text="TLC Step Prompt", padding=10)
        # tlc_frame intentionally NOT packed — hidden per user request

        tlc_desc = ttk.Label(
            tlc_frame,
            text="This prompt is used for Translation/Localization Check (TLC) steps.",
            foreground="gray",
        )
        tlc_desc.pack(anchor="w", pady=(0, 5))

        # Text widget for TLC prompt (multi-line)
        tlc_text_frame = ttk.Frame(tlc_frame)
        tlc_text_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self._tlc_prompt_text = tk.Text(tlc_text_frame, height=5, width=60, wrap=tk.WORD)
        self._tlc_prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tlc_prompt_text.insert("1.0", self.tlc_prompt_var.get())

        tlc_scroll = ttk.Scrollbar(tlc_text_frame, orient=tk.VERTICAL, command=self._tlc_prompt_text.yview)
        tlc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._tlc_prompt_text.config(yscrollcommand=tlc_scroll.set)

        # Reset to default button for TLC prompt
        tlc_btn_frame = ttk.Frame(tlc_frame)
        tlc_btn_frame.pack(anchor="w", pady=(5, 0))
        ttk.Button(tlc_btn_frame, text="Reset to Default", command=self._reset_tlc_prompt).pack(side=tk.LEFT)

        # TLC component toggles
        tlc_components_frame = ttk.LabelFrame(tlc_frame, text="Include in TLC Prompt", padding=5)
        tlc_components_frame.pack(fill=tk.X, pady=(10, 0))

        tlc_comp_row1 = ttk.Frame(tlc_components_frame)
        tlc_comp_row1.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(tlc_comp_row1, text="Glossary", variable=self.tlc_include_glossary_var).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(tlc_comp_row1, text="Game Summary", variable=self.tlc_include_game_summary_var).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(tlc_comp_row1, text="Code Glossary", variable=self.tlc_include_code_glossary_var).pack(side=tk.LEFT, padx=10)

        # TLC input policy
        tlc_policy_row = ttk.Frame(tlc_frame)
        tlc_policy_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(tlc_policy_row, text="Input Source:").pack(side=tk.LEFT)
        tlc_policy_combo = ttk.Combobox(
            tlc_policy_row,
            textvariable=self.tlc_input_policy_var,
            values=[e.value for e in TLCInputPolicy],
            state="readonly",
            width=18,
        )
        tlc_policy_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(tlc_policy_row, text="(What text fields feed the TLC prompt)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # ── Conditional (Context-Type) Prompts ────────────────────────────────
        cond_frame = ttk.LabelFrame(panel, text="Conditional Prompts (Context-Type)", padding=10)
        cond_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        cond_desc = ttk.Label(
            cond_frame,
            text=(
                "These prompts are injected into the translation request based on the\n"
                "detected content type (set via Context Markers in the translation step)."
            ),
            foreground="gray",
        )
        cond_desc.pack(anchor="w", pady=(0, 8))

        # Helper to build one row per context type
        _cond_entries = [
            ("Dialogue", "dialogue", self.dialogue_prompt_var, "_dialogue_prompt_text", DEFAULT_DIALOGUE_PROMPT),
            ("Menu", "menu", self.menu_prompt_var, "_menu_prompt_text", DEFAULT_MENU_PROMPT),
            ("Choices", "choice", self.choice_prompt_var, "_choice_prompt_text", DEFAULT_CHOICE_PROMPT),
            ("Unknown / Mixed", "unknown", self.unknown_prompt_var, "_unknown_prompt_text", DEFAULT_UNKNOWN_PROMPT),
        ]

        for _label, _key, _var, _attr, _default in _cond_entries:
            row_frame = ttk.LabelFrame(cond_frame, text=_label, padding=6)
            row_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

            txt_container = ttk.Frame(row_frame)
            txt_container.pack(fill=tk.BOTH, expand=True)

            txt_widget = tk.Text(txt_container, height=3, width=60, wrap=tk.WORD)
            txt_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            txt_widget.insert("1.0", _var.get())
            setattr(self, _attr, txt_widget)

            sb = ttk.Scrollbar(txt_container, orient=tk.VERTICAL, command=txt_widget.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            txt_widget.config(yscrollcommand=sb.set)

            # Capture loop var in closure
            def _make_reset(widget: tk.Text, default: str) -> Any:
                def _reset() -> None:
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", default)
                return _reset

            btn_row = ttk.Frame(row_frame)
            btn_row.pack(anchor="w", pady=(4, 0))
            ttk.Button(btn_row, text="Reset to Default", command=_make_reset(txt_widget, _default)).pack(side=tk.LEFT)

        # ── Conditional (Pattern-Triggered) Prompts ───────────────────────
        self._build_pattern_prompts_section(panel)

    def _build_pattern_prompts_section(self, panel: ttk.Frame) -> None:
        """Build the Pattern-Triggered Conditional Prompts subsection.

        Each prompt gets an enabled checkbox and an editable instruction
        text widget.  A separate area holds merged-request instruction
        texts (``all_unrelated`` / ``block_unrelated``).
        """
        from CherryAI.functions.ini_manager import (
            PATTERN_PROMPT_NAMES,
            get_pattern_prompt_text,
            get_merged_request_text,
        )
        from CherryAI.functions.conditional_prompts import BUILTIN_CONDITIONS

        # Build lookup: name → default instruction text from code constants.
        _defaults: Dict[str, str] = {c.name: c.instruction for c in BUILTIN_CONDITIONS}

        # Human-readable labels
        _LABELS: Dict[str, str] = {
            "temp_replacement": "Temporary Replacement",
            "delimiter_protection": "Delimiter Protection",
            "linebreaks": "Linebreaks",
            "color_codes": "Color Codes",
            "media_commands": "Media Commands",
            "text_formatting": "Text Formatting",
            "ruby_text": "Ruby Text / Furigana",
            "ellipsis": "Ellipsis",
            "speaker_dialogue_format": "Speaker: Dialogue Format",
        }

        _DESCS: Dict[str, str] = {
            "temp_replacement": "Detects TEMPREPL and Custom Placeholder tokens",
            "delimiter_protection": "Protects content within [square], {curly}, <angle>, __dunder__ delimiters",
            "linebreaks": "Preserves <br> tags, \\n escapes, and literal newlines",
            "color_codes": "Preserves color codes like \\c[N]",
            "media_commands": "Preserves sound/media commands like \\se[], \\pic[]",
            "text_formatting": "Preserves formatting codes like \\fb, \\fr, \\b",
            "ruby_text": "Preserves furigana structure \\rb[text,reading]",
            "ellipsis": "Preserves ellipsis patterns (\u2026, ...)",
            "speaker_dialogue_format": "Detects Speaker: Dialogue format",
        }

        pat_frame = ttk.LabelFrame(
            panel, text="Conditional Prompts (Pattern Triggered)", padding=10,
        )
        pat_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        ttk.Label(
            pat_frame,
            text=(
                "These prompts are injected when matching patterns are detected in the\n"
                "input lines. Disable a prompt to suppress it; edit the text to customise."
            ),
            foreground="gray",
        ).pack(anchor="w", pady=(0, 8))

        def _make_reset(widget: tk.Text, default: str) -> Any:
            def _reset() -> None:
                widget.delete("1.0", tk.END)
                widget.insert("1.0", default)
            return _reset

        for _name in PATTERN_PROMPT_NAMES:
            label = _LABELS.get(_name, _name)
            desc = _DESCS.get(_name, "")
            default_text = _defaults.get(_name, "")
            ini_text = get_pattern_prompt_text(_name, default_text)

            row = ttk.LabelFrame(pat_frame, text=label, padding=6)
            row.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

            # Enabled checkbox + description on same line
            top_row = ttk.Frame(row)
            top_row.pack(fill=tk.X)
            enabled_var = self._pattern_prompt_enabled_vars.get(_name)
            if enabled_var is None:
                enabled_var = tk.BooleanVar(value=True)
                self._pattern_prompt_enabled_vars[_name] = enabled_var
            ttk.Checkbutton(top_row, text="Enabled", variable=enabled_var).pack(
                side=tk.LEFT,
            )
            if desc:
                ttk.Label(top_row, text=desc, foreground="gray").pack(
                    side=tk.LEFT, padx=(10, 0),
                )

            # Instruction text editor
            txt_container = ttk.Frame(row)
            txt_container.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
            tw = tk.Text(txt_container, height=2, width=60, wrap=tk.WORD)
            tw.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tw.insert("1.0", ini_text)
            self._pattern_prompt_text_widgets[_name] = tw

            sb = ttk.Scrollbar(txt_container, orient=tk.VERTICAL, command=tw.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            tw.config(yscrollcommand=sb.set)

            btn = ttk.Frame(row)
            btn.pack(anchor="w", pady=(4, 0))
            ttk.Button(
                btn, text="Reset to Default",
                command=_make_reset(tw, default_text),
            ).pack(side=tk.LEFT)

        # ── Merged Request Instructions ──────────────────────────────────
        merge_frame = ttk.LabelFrame(
            pat_frame, text="Merged Request Instructions", padding=6,
        )
        merge_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        ttk.Label(
            merge_frame,
            text="Instructions injected when Efficient mode merges requests across file boundaries.",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 6))

        _merge_entries = [
            (
                "All Unrelated",
                "all_unrelated",
                "All lines are unrelated to each other.",
            ),
            (
                "Block Unrelated",
                "block_unrelated",
                "This request has lines unrelated to each other.",
            ),
        ]
        for _label, _kind, _default_text in _merge_entries:
            mrow = ttk.LabelFrame(merge_frame, text=_label, padding=4)
            mrow.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

            ini_val = get_merged_request_text(_kind, _default_text)
            mc = ttk.Frame(mrow)
            mc.pack(fill=tk.BOTH, expand=True)
            mw = tk.Text(mc, height=2, width=60, wrap=tk.WORD)
            mw.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            mw.insert("1.0", ini_val)
            self._merged_request_text_widgets[_kind] = mw

            msb = ttk.Scrollbar(mc, orient=tk.VERTICAL, command=mw.yview)
            msb.pack(side=tk.RIGHT, fill=tk.Y)
            mw.config(yscrollcommand=msb.set)

            mbtn = ttk.Frame(mrow)
            mbtn.pack(anchor="w", pady=(4, 0))
            ttk.Button(
                mbtn, text="Reset to Default",
                command=_make_reset(mw, _default_text),
            ).pack(side=tk.LEFT)

    def _reset_edit_prompt(self) -> None:
        """Reset edit prompt to default value."""
        self._edit_prompt_text.delete("1.0", tk.END)
        self._edit_prompt_text.insert("1.0", DEFAULT_EDIT_PROMPT)

    def _reset_tlc_prompt(self) -> None:
        """Reset TLC prompt to default value."""
        self._tlc_prompt_text.delete("1.0", tk.END)
        self._tlc_prompt_text.insert("1.0", DEFAULT_TLC_PROMPT)

    # ------------------------------------------------------------------
    # Security section
    # ------------------------------------------------------------------

    def _build_security_section(self) -> None:
        """Build the Security settings panel.

        Lets the user set or change the master password that encrypts all
        API keys stored in ``user/API.ini``.  Also shows a brief security
        summary and a standalone :class:`PasswordStrengthWidget` that
        provides real-time strength feedback while the user experiments.
        """
        from CherryAI.gui.dialogs.password_dialog import SetPasswordDialog, ChangePasswordDialog
        from CherryAI.gui.widgets.password_strength import PasswordStrengthWidget

        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.SECURITY] = panel

        # Header
        ttk.Label(
            panel, text="Security", font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w", pady=(0, 5))
        ttk.Label(
            panel,
            text=SECTION_DESCRIPTIONS[OptionSection.SECURITY],
            foreground="gray",
        ).pack(anchor="w", pady=(0, 15))

        # ---- Master password frame -----------------------------------
        pw_frame = ttk.LabelFrame(panel, text="Master Password", padding=12)
        pw_frame.pack(fill=tk.X, pady=(0, 12))

        # Status label (updated by _refresh_security_status)
        self._sec_status_label = ttk.Label(pw_frame, text="")
        self._sec_status_label.pack(anchor="w", pady=(0, 10))

        # Button row
        btn_row = ttk.Frame(pw_frame)
        btn_row.pack(anchor="w")

        self._set_pw_btn = ttk.Button(
            btn_row,
            text="Set Password…",
            command=self._on_set_password,
        )
        self._set_pw_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._change_pw_btn = ttk.Button(
            btn_row,
            text="Change Password…",
            command=self._on_change_password,
        )
        self._change_pw_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._disable_pw_btn = ttk.Button(
            btn_row,
            text="Disable Password",
            command=self._on_disable_password,
        )
        self._disable_pw_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._reset_pw_btn = ttk.Button(
            btn_row,
            text="Reset Password",
            command=self._on_reset_password,
        )
        self._reset_pw_btn.pack(side=tk.LEFT)

        # ---- Strength tester frame -----------------------------------
        tester_frame = ttk.LabelFrame(panel, text="Password Strength Tester", padding=12)
        tester_frame.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(
            tester_frame,
            text="Type any password to see its strength (nothing is saved here).",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 8))

        self._strength_tester = PasswordStrengthWidget(
            tester_frame,
            label_text="Test password:",
            label_width=14,
        )
        self._strength_tester.pack(fill=tk.X)

        # ---- Info / legend frame -------------------------------------
        info_frame = ttk.LabelFrame(panel, text="Strength Tiers (HiveSystems 2025)", padding=12)
        info_frame.pack(fill=tk.X, pady=(0, 12))

        tiers = [
            (_api_config.PasswordStrength.INSTANTLY, "#9B59B6",
             "< 8 characters — cracked instantly"),
            (_api_config.PasswordStrength.WEAK,      "#E74C3C",
             "8 chars, numbers/lowercase only"),
            (_api_config.PasswordStrength.GOOD,      "#E67E22",
             "Mixed types, but short"),
            (_api_config.PasswordStrength.GREAT,     "#F1C40F",
             "12+ chars with \u2265 3 character types"),
            (_api_config.PasswordStrength.SAFE,      "#2ECC71",
             "16+ chars, or 12+ chars with all 4 types"),
        ]

        for tier_name, colour, description in tiers:
            row = ttk.Frame(info_frame)
            row.pack(fill=tk.X, pady=2)
            # Colour swatch
            tk.Label(
                row,
                text="  ",
                bg=colour,
                width=3,
                relief="flat",
            ).pack(side=tk.LEFT, padx=(0, 8), ipady=3)
            ttk.Label(
                row,
                text=f"{tier_name}: {description}",
            ).pack(side=tk.LEFT, anchor="w")

        # ---- Technical info -----------------------------------------
        tech_label = ttk.Label(
            panel,
            text=(
                "Encryption: bcrypt work-factor 10 hash \u2022 "
                "PBKDF2-SHA256 (390,000 iter.) key derivation \u2022 "
                "Fernet AES-256 API key encryption.\n"
                "Master password is never stored in plaintext. "
                "See doc/passwords.md for full details."
            ),
            foreground="gray",
            wraplength=500,
            justify="left",
        )
        tech_label.pack(anchor="w", pady=(4, 0))

        # Populate status
        self._refresh_security_status()

    def _refresh_security_status(self) -> None:
        """Update the password status indicator in the Security panel."""
        try:
            if _api_config.is_password_set():
                self._sec_status_label.configure(
                    text="\u2705  Master password is set. API keys are encrypted.",
                    foreground="#2ECC71",
                )
                self._set_pw_btn.configure(state="disabled")
                self._change_pw_btn.configure(state="normal")
                self._disable_pw_btn.configure(state="normal")
                self._reset_pw_btn.configure(state="normal")
            else:
                self._sec_status_label.configure(
                    text="\u26A0\ufe0f  No master password set. API keys are stored unencrypted.",
                    foreground="#E67E22",
                )
                self._set_pw_btn.configure(state="normal")
                self._change_pw_btn.configure(state="disabled")
                self._disable_pw_btn.configure(state="disabled")
                self._reset_pw_btn.configure(state="disabled")
        except Exception as exc:
            logger.warning("Could not read security status: %s", exc)

    def _on_set_password(self) -> None:
        """Open the Set Password dialog."""
        from CherryAI.gui.dialogs.password_dialog import SetPasswordDialog
        dlg = SetPasswordDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            messagebox.showinfo(
                "Password Set",
                "Master password has been set. API keys will now be encrypted.",
                parent=self,
            )
            self._refresh_security_status()

    def _on_change_password(self) -> None:
        """Open the Change Password dialog."""
        from CherryAI.gui.dialogs.password_dialog import ChangePasswordDialog
        dlg = ChangePasswordDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            messagebox.showinfo(
                "Password Changed",
                "Master password changed. All API keys have been re-encrypted.",
                parent=self,
            )
            self._refresh_security_status()

    def _on_disable_password(self) -> None:
        """Disable the master password, storing all keys in plaintext."""
        confirm = messagebox.askyesno(
            "Disable Password",
            "This will remove encryption from all stored API keys.\n"
            "Keys will be stored in plaintext in API.ini.\n\n"
            "Continue?",
            parent=self,
        )
        if not confirm:
            return
        pw = self._prompt_password("Enter Current Password")
        if not pw:
            return
        success, msg = _api_config.disable_password(pw)
        if success:
            messagebox.showinfo("Password Disabled", msg, parent=self)
            self._refresh_security_status()
            self._refresh_providers_tree()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def _on_reset_password(self) -> None:
        """Reset the master password, removing all stored keys."""
        confirm = messagebox.askyesno(
            "Reset Password",
            "WARNING: This will remove the master password AND delete\n"
            "all stored API keys (they cannot be decrypted without\n"
            "the password).\n\n"
            "This action cannot be undone. Continue?",
            icon="warning",
            parent=self,
        )
        if not confirm:
            return
        success, msg = _api_config.reset_password()
        if success:
            messagebox.showinfo("Password Reset", msg, parent=self)
            self._refresh_security_status()
            self._refresh_providers_tree()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def _build_utility_section(self) -> None:
        """Build the Utility settings panel (Term Translation + Gender Inference)."""
        from CherryAI.functions import api_config as _api_config

        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.UTILITY] = panel

        # Scrollable canvas for long content
        canvas = tk.Canvas(panel, highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse-wheel scrolling (bind/unbind on Enter/Leave to avoid stale refs)
        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        # Header
        ttk.Label(
            inner, text="Utility", font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w", pady=(0, 5))
        ttk.Label(
            inner,
            text=SECTION_DESCRIPTIONS[OptionSection.UTILITY],
            foreground="gray",
        ).pack(anchor="w", pady=(0, 15))

        # -- Gather API key list for comboboxes --
        api_keys = _api_config.list_api_keys()  # [(provider, name), ...]
        key_labels = [f"{p} / {n}" for p, n in api_keys]

        def _key_label(provider: str, name: str) -> str:
            if provider and name:
                return f"{provider} / {name}"
            return ""

        # =====================================================================
        # Term Translation
        # =====================================================================
        tt_frame = ttk.LabelFrame(inner, text="Term Translation", padding=12)
        tt_frame.pack(fill=tk.X, pady=(0, 12))

        # Mode
        row = ttk.Frame(tt_frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="Mode:", width=15).pack(side=tk.LEFT)
        self._term_mode_var = tk.StringVar(
            value=self.options.utility.term_translation_mode,
        )
        term_mode_cb = ttk.Combobox(
            row, textvariable=self._term_mode_var,
            values=["Romaji", "LLM"], state="readonly", width=18,
        )
        term_mode_cb.pack(side=tk.LEFT)

        # API Key
        row = ttk.Frame(tt_frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="API Key:", width=15).pack(side=tk.LEFT)
        self._term_api_provider_var = tk.StringVar(
            value=self.options.utility.term_api_key_provider,
        )
        self._term_api_name_var = tk.StringVar(
            value=self.options.utility.term_api_key_name,
        )
        self._term_key_combo_var = tk.StringVar(
            value=_key_label(
                self.options.utility.term_api_key_provider,
                self.options.utility.term_api_key_name,
            ),
        )
        self._term_key_cb = ttk.Combobox(
            row, textvariable=self._term_key_combo_var,
            values=key_labels, state="readonly", width=30,
        )
        self._term_key_cb.pack(side=tk.LEFT)

        def _on_term_key_change(_event: tk.Event = None) -> None:
            val = self._term_key_combo_var.get()
            if " / " in val:
                p, n = val.split(" / ", 1)
                self._term_api_provider_var.set(p)
                self._term_api_name_var.set(n)
                self._update_term_model_list(p)
                # Auto-fill model from default model for this key
                default_model = _api_config.get_default_model(p, n)
                if default_model and not self._term_model_var.get():
                    self._term_model_var.set(default_model)

        self._term_key_cb.bind("<<ComboboxSelected>>", _on_term_key_change)

        # Model
        row = ttk.Frame(tt_frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="Model:", width=15).pack(side=tk.LEFT)
        self._term_model_var = tk.StringVar(
            value=self.options.utility.term_model,
        )
        self._term_model_cb = ttk.Combobox(
            row, textvariable=self._term_model_var, width=30,
        )
        self._term_model_cb.pack(side=tk.LEFT)
        # Populate models based on current provider
        self._update_term_model_list(
            self.options.utility.term_api_key_provider,
        )

        # Batch Size
        row = ttk.Frame(tt_frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="Batch Size:", width=15).pack(side=tk.LEFT)
        self._term_batch_size_var = tk.IntVar(
            value=self.options.utility.term_batch_size,
        )
        ttk.Spinbox(
            row, textvariable=self._term_batch_size_var,
            from_=1, to=100, width=6,
        ).pack(side=tk.LEFT)
        ttk.Label(
            row, text="terms per LLM request", foreground="gray",
        ).pack(side=tk.LEFT, padx=(6, 0))

        # Mode description
        ttk.Label(
            tt_frame,
            text=(
                "Romaji — Modified Hepburn romanization (built-in, kana-only).\n"
                "LLM — Uses the selected API key and model to translate terms."
            ),
            font=("Segoe UI", 8), foreground="gray",
            wraplength=450, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        # =====================================================================
        # Gender Inference
        # =====================================================================
        gi_frame = ttk.LabelFrame(inner, text="Gender Inference", padding=12)
        gi_frame.pack(fill=tk.X, pady=(0, 12))

        # Mode
        row = ttk.Frame(gi_frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="Mode:", width=15).pack(side=tk.LEFT)
        self._gender_mode_var = tk.StringVar(
            value=self.options.utility.gender_inference_mode,
        )
        gender_mode_cb = ttk.Combobox(
            row, textvariable=self._gender_mode_var,
            values=["Script only", "Script + LLM"], state="readonly", width=18,
        )
        gender_mode_cb.pack(side=tk.LEFT)

        # API Key
        row = ttk.Frame(gi_frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="API Key:", width=15).pack(side=tk.LEFT)
        self._gender_api_provider_var = tk.StringVar(
            value=self.options.utility.gender_api_key_provider,
        )
        self._gender_api_name_var = tk.StringVar(
            value=self.options.utility.gender_api_key_name,
        )
        self._gender_key_combo_var = tk.StringVar(
            value=_key_label(
                self.options.utility.gender_api_key_provider,
                self.options.utility.gender_api_key_name,
            ),
        )
        self._gender_key_cb = ttk.Combobox(
            row, textvariable=self._gender_key_combo_var,
            values=key_labels, state="readonly", width=30,
        )
        self._gender_key_cb.pack(side=tk.LEFT)

        def _on_gender_key_change(_event: tk.Event = None) -> None:
            val = self._gender_key_combo_var.get()
            if " / " in val:
                p, n = val.split(" / ", 1)
                self._gender_api_provider_var.set(p)
                self._gender_api_name_var.set(n)
                self._update_gender_model_list(p)
                default_model = _api_config.get_default_model(p, n)
                if default_model and not self._gender_model_var.get():
                    self._gender_model_var.set(default_model)

        self._gender_key_cb.bind("<<ComboboxSelected>>", _on_gender_key_change)

        # Model
        row = ttk.Frame(gi_frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="Model:", width=15).pack(side=tk.LEFT)
        self._gender_model_var = tk.StringVar(
            value=self.options.utility.gender_model,
        )
        self._gender_model_cb = ttk.Combobox(
            row, textvariable=self._gender_model_var, width=30,
        )
        self._gender_model_cb.pack(side=tk.LEFT)
        # Populate models based on current provider
        self._update_gender_model_list(
            self.options.utility.gender_api_key_provider,
        )

        # --- Script Confidence ---
        sc_frame = ttk.LabelFrame(gi_frame, text="Script Confidence", padding=8)
        sc_frame.pack(fill=tk.X, pady=(8, 4))

        sc_row = ttk.Frame(sc_frame)
        sc_row.pack(fill=tk.X, pady=2)
        self._gender_script_min_var = tk.IntVar(
            value=self.options.utility.gender_script_minimum,
        )
        ttk.Spinbox(
            sc_row, textvariable=self._gender_script_min_var,
            from_=1, to=100, width=5,
        ).pack(side=tk.LEFT)
        ttk.Label(sc_row, text=" of ").pack(side=tk.LEFT)
        self._gender_script_max_var = tk.IntVar(
            value=self.options.utility.gender_script_maximum,
        )
        ttk.Spinbox(
            sc_row, textvariable=self._gender_script_max_var,
            from_=1, to=100, width=5,
        ).pack(side=tk.LEFT)

        self._gender_script_ign_var = tk.BooleanVar(
            value=self.options.utility.gender_script_ignore_unknown,
        )
        ttk.Checkbutton(
            sc_row, text="Ignore Unknown",
            variable=self._gender_script_ign_var,
        ).pack(side=tk.LEFT, padx=(12, 0))

        self._gender_script_doall_var = tk.BooleanVar(
            value=self.options.utility.gender_script_do_all,
        )
        ttk.Checkbutton(
            sc_row, text="Do all Requests",
            variable=self._gender_script_doall_var,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # --- LLM Confidence ---
        lc_frame = ttk.LabelFrame(gi_frame, text="LLM Confidence", padding=8)
        lc_frame.pack(fill=tk.X, pady=(4, 4))

        lc_row = ttk.Frame(lc_frame)
        lc_row.pack(fill=tk.X, pady=2)
        self._gender_llm_min_var = tk.IntVar(
            value=self.options.utility.gender_llm_minimum,
        )
        ttk.Spinbox(
            lc_row, textvariable=self._gender_llm_min_var,
            from_=1, to=100, width=5,
        ).pack(side=tk.LEFT)
        ttk.Label(lc_row, text=" of ").pack(side=tk.LEFT)
        self._gender_llm_max_var = tk.IntVar(
            value=self.options.utility.gender_llm_maximum,
        )
        ttk.Spinbox(
            lc_row, textvariable=self._gender_llm_max_var,
            from_=1, to=100, width=5,
        ).pack(side=tk.LEFT)

        self._gender_llm_ign_var = tk.BooleanVar(
            value=self.options.utility.gender_llm_ignore_unknown,
        )
        ttk.Checkbutton(
            lc_row, text="Ignore Unknown",
            variable=self._gender_llm_ign_var,
        ).pack(side=tk.LEFT, padx=(12, 0))

        self._gender_llm_doall_var = tk.BooleanVar(
            value=self.options.utility.gender_llm_do_all,
        )
        ttk.Checkbutton(
            lc_row, text="Do all Requests",
            variable=self._gender_llm_doall_var,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # Mode description
        ttk.Label(
            gi_frame,
            text=(
                "Script only — Uses built-in script analysis (pronouns, "
                "honorifics, markers).\n"
                "Script + LLM — Runs script first, then LLM for remaining "
                "unknowns."
            ),
            font=("Segoe UI", 8), foreground="gray",
            wraplength=450, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        # =====================================================================
        # Misc
        # =====================================================================
        misc_frame = ttk.LabelFrame(inner, text="Misc", padding=12)
        misc_frame.pack(fill=tk.X, pady=(0, 12))

        # Speaker Threshold
        row = ttk.Frame(misc_frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="Speaker Threshold:", width=18).pack(side=tk.LEFT)
        self._speaker_threshold_var = tk.IntVar(
            value=self.options.utility.speaker_threshold,
        )
        ttk.Spinbox(
            row, textvariable=self._speaker_threshold_var,
            from_=1, to=9999, width=6,
        ).pack(side=tk.LEFT)
        ttk.Label(
            row, text="minimum occurrences", foreground="gray",
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(
            misc_frame,
            text=(
                "Speakers below this count are collapsed in Analysis findings "
                "and excluded from Glossary import and Term Translation."
            ),
            font=("Segoe UI", 8), foreground="gray",
            wraplength=450, justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _build_buttons(self, parent: ttk.Frame) -> None:
        """Build the action buttons at the bottom."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Right-aligned buttons
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Apply", command=self._on_apply).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.RIGHT, padx=5)

        # Left-aligned buttons
        ttk.Button(button_frame, text="Save as Default", command=self._on_save_as_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Restore Initial Defaults", command=self._on_restore_initial_defaults).pack(side=tk.LEFT, padx=5)

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def _on_provider_change(self, event: Optional[tk.Event]) -> None:
        """Handle provider selection change with provider validation."""
        provider = self.provider_var.get()
        if provider in API_PROVIDERS:
            info = API_PROVIDERS[provider]
            self.base_url_var.set(info.get("base_url", ""))
            self._update_model_list()

        # Provider Handshake validation (V8)
        self._apply_provider_constraints()

    def _on_model_change(self, *_args: Any) -> None:
        """Handle model selection change — re-apply provider constraints.

        Also loads per-model settings (temperature, thinking) when
        they differ from the global defaults.
        """
        self._load_model_settings()
        self._apply_provider_constraints()

    def _apply_provider_constraints(self) -> None:
        """Apply provider/model capability constraints to UI widgets.

        Validates the selected provider, then shows or hides temperature
        and thinking widgets based on the provider's reported capabilities
        for the currently selected model.  Also warns when the model
        does not support structured JSON output.
        """
        # Guard: widgets not yet created during __init__
        if not hasattr(self, "_temp_row"):
            return

        try:
            from CherryAI.providers import (
                ProviderRegistry, validate_provider,
            )
        except Exception:
            return  # providers package not available — skip

        provider_key = self.provider_var.get()
        provider = ProviderRegistry.get(provider_key)
        if provider is None:
            return

        # --- Validate provider (only after initial build) ---
        if getattr(self, "_constraints_initialized", False):
            errors = validate_provider(provider)
            if errors:
                messagebox.showwarning(
                    "Provider Validation",
                    f"Provider '{provider.display_name}' has issues:\n\n"
                    + "\n".join(f"• {e}" for e in errors),
                    parent=self,
                )

        model_id = self.model_var.get()

        # --- Temperature constraints ---
        temp_cfg = provider.get_temperature_config(model_id)
        self._apply_tuning_control(
            config=temp_cfg,
            variable=self.temperature_var,
            scale=self._temp_scale,
            hint_label=self._temp_hint_label,
            supported_hint=(
                f"Range {temp_cfg.min_value:.1f}-{temp_cfg.max_value:.1f}"
                f"  (default {temp_cfg.default:.1f})"
            ),
            unsupported_hint="Temperature is not available for this model.",
        )

        top_p_cfg = provider.get_top_p_config(model_id)
        self._apply_tuning_control(
            config=top_p_cfg,
            variable=self.top_p_var,
            scale=self._top_p_scale,
            hint_label=self._top_p_hint_label,
            supported_hint=(
                f"Range {top_p_cfg.min_value:.2f}-{top_p_cfg.max_value:.2f}"
                f"  (default {top_p_cfg.default:.2f})"
            ),
            unsupported_hint="Top P is not available for this model.",
        )

        frequency_penalty_cfg = provider.get_frequency_penalty_config(model_id)
        self._apply_tuning_control(
            config=frequency_penalty_cfg,
            variable=self.frequency_penalty_var,
            scale=self._frequency_penalty_scale,
            hint_label=self._frequency_penalty_hint_label,
            supported_hint=(
                f"Range {frequency_penalty_cfg.min_value:.2f}-{frequency_penalty_cfg.max_value:.2f}"
                f"  (default {frequency_penalty_cfg.default:.2f})"
            ),
            unsupported_hint="Frequency penalty is not available for this model.",
        )

        presence_penalty_cfg = provider.get_presence_penalty_config(model_id)
        self._apply_tuning_control(
            config=presence_penalty_cfg,
            variable=self.presence_penalty_var,
            scale=self._presence_penalty_scale,
            hint_label=self._presence_penalty_hint_label,
            supported_hint=(
                f"Range {presence_penalty_cfg.min_value:.2f}-{presence_penalty_cfg.max_value:.2f}"
                f"  (default {presence_penalty_cfg.default:.2f})"
            ),
            unsupported_hint="Presence penalty is not available for this model.",
        )

        # --- Thinking constraints ---
        think_cfg = provider.get_thinking_config(model_id)
        if think_cfg.available:
            effort_levels = list(think_cfg.effort_levels or ("low", "medium", "high"))
            default_effort = think_cfg.effort_default or effort_levels[-1]
            if hasattr(self, "_reasoning_effort_combo"):
                self._reasoning_effort_combo.configure(values=effort_levels)
            if self.reasoning_effort_var.get() not in effort_levels:
                self.reasoning_effort_var.set(default_effort)
            self._think_frame.pack(fill=tk.X, pady=(0, 10))
            if think_cfg.mandatory:
                # Mandatory thinking — force on and disable toggle
                self.thinking_enabled_var.set(True)
                if hasattr(self, "_thinking_cb"):
                    self._thinking_cb.configure(state="disabled")
            else:
                # Optional thinking — enable toggle
                if hasattr(self, "_thinking_cb"):
                    self._thinking_cb.configure(state="normal")
            # Show effort dropdown for optional/mandatory modes
            if think_cfg.mode in ("optional", "mandatory"):
                if hasattr(self, "_reasoning_effort_row"):
                    self._reasoning_effort_row.pack(fill=tk.X, pady=5)
                if hasattr(self, "_thinking_budget_row"):
                    self._thinking_budget_row.pack_forget()
            # Show budget for explicit (Claude) mode
            elif think_cfg.mode == "explicit":
                if hasattr(self, "_thinking_budget_row"):
                    self._thinking_budget_row.pack(fill=tk.X, pady=5)
                if hasattr(self, "_reasoning_effort_row"):
                    self._reasoning_effort_row.pack_forget()
            else:
                # Builtin: no budget or effort needed
                if hasattr(self, "_thinking_budget_row"):
                    self._thinking_budget_row.pack_forget()
                if hasattr(self, "_reasoning_effort_row"):
                    self._reasoning_effort_row.pack_forget()
        else:
            self.thinking_enabled_var.set(False)
            if hasattr(self, "_thinking_cb"):
                self._thinking_cb.configure(state="disabled")
            if hasattr(self, "_thinking_budget_row"):
                self._thinking_budget_row.pack_forget()
            if hasattr(self, "_reasoning_effort_row"):
                self._reasoning_effort_row.pack_forget()

        self._refresh_tuning_warnings()

        # --- Structured output warning (only on user action) ---
        if getattr(self, "_constraints_initialized", False):
            if model_id and not provider.supports_structured_output(model_id):
                messagebox.showwarning(
                    "Structured Output",
                    f"Model '{model_id}' does not support "
                    "structured JSON output.\n"
                    "Translation quality may be reduced.",
                    parent=self,
                )

        # Mark that future calls come from user interaction
        self._constraints_initialized = True

    def _update_model_list(self) -> None:
        """Update the model combobox from the model registry for the current provider."""
        from CherryAI.functions.options import get_provider_models
        provider = self.provider_var.get()
        models = get_provider_models(provider)
        if not models and provider in API_PROVIDERS:
            models = API_PROVIDERS[provider].get("models", [])
        self._model_combo["values"] = models
        if self.model_var.get() not in models and models:
            self.model_var.set(models[0])
        # Keep visible combo in sync
        self._sync_settings_model_combo()

    def _update_term_model_list(self, provider: str) -> None:
        """Update the Term Translation model combobox for the given provider."""
        from CherryAI.functions.options import get_provider_models
        if not provider:
            return
        models = get_provider_models(provider)
        if not models and provider in API_PROVIDERS:
            models = API_PROVIDERS[provider].get("models", [])
        if hasattr(self, "_term_model_cb"):
            self._term_model_cb["values"] = models

    def _update_gender_model_list(self, provider: str) -> None:
        """Update the Gender Inference model combobox for the given provider."""
        from CherryAI.functions.options import get_provider_models
        if not provider:
            return
        models = get_provider_models(provider)
        if not models and provider in API_PROVIDERS:
            models = API_PROVIDERS[provider].get("models", [])
        if hasattr(self, "_gender_model_cb"):
            self._gender_model_cb["values"] = models

    def _sync_settings_model_combo(self) -> None:
        """Sync the visible Model Selection combo with the hidden one."""
        if not hasattr(self, "_settings_model_combo"):
            return
        self._settings_model_combo["values"] = self._model_combo["values"]

    def _load_model_settings(self) -> None:
        """Load per-model settings from INI (temperature, thinking).

        Falls back to provider defaults when no saved per-model entry exists.
        """
        try:
            from CherryAI.functions import ini_manager
            from CherryAI.functions.api_config import get_model_settings
        except Exception:
            return

        model_id = self.model_var.get()
        if not model_id:
            return

        saved = ini_manager.get_all_user_defaults("model_settings")
        api_saved = get_model_settings(model_id)
        prefix = f"{model_id}."
        allowed_efforts = ("low", "medium", "high")
        default_effort = "medium"
        try:
            from CherryAI.providers import ProviderRegistry

            provider = ProviderRegistry.get(self.provider_var.get())
            if provider:
                think_cfg = provider.get_thinking_config(model_id)
                if think_cfg.effort_levels:
                    allowed_efforts = tuple(
                        str(level).strip().lower()
                        for level in think_cfg.effort_levels
                    )
                if think_cfg.effort_default:
                    default_effort = think_cfg.effort_default.strip().lower()
                elif allowed_efforts:
                    default_effort = allowed_efforts[-1]
        except Exception:
            pass

        # Temperature
        temp_key = f"{prefix}temperature"
        if "temperature" in api_saved:
            try:
                self.temperature_var.set(float(api_saved["temperature"]))
            except (ValueError, tk.TclError, TypeError):
                self._apply_provider_temp_default(model_id)
        elif temp_key in saved:
            try:
                self.temperature_var.set(float(saved[temp_key]))
            except (ValueError, tk.TclError):
                pass
        else:
            # Use provider default if available
            self._apply_provider_temp_default(model_id)

        def _apply_saved_float(
            key: str,
            var: tk.DoubleVar,
            fallback: float,
            minimum: float,
            maximum: float,
        ) -> None:
            if key not in api_saved:
                var.set(fallback)
                return
            try:
                value = float(api_saved[key])
            except (ValueError, tk.TclError, TypeError):
                value = fallback
            var.set(max(minimum, min(maximum, value)))

        _apply_saved_float("top_p", self.top_p_var, 1.0, 0.0, 1.0)
        _apply_saved_float(
            "frequency_penalty",
            self.frequency_penalty_var,
            0.2,
            -2.0,
            2.0,
        )
        _apply_saved_float(
            "presence_penalty",
            self.presence_penalty_var,
            0.0,
            -2.0,
            2.0,
        )

        # Thinking enabled
        think_key = f"{prefix}thinking_enabled"
        if "thinking_enabled" in api_saved:
            self.thinking_enabled_var.set(
                str(api_saved["thinking_enabled"]).lower()
                in ("true", "1", "yes"),
            )
        elif think_key in saved:
            self.thinking_enabled_var.set(
                saved[think_key].lower() in ("true", "1", "yes"),
            )
        else:
            self.thinking_enabled_var.set(False)

        # Thinking budget
        budget_key = f"{prefix}thinking_budget"
        if "thinking_budget" in api_saved:
            try:
                self.thinking_budget_var.set(int(api_saved["thinking_budget"]))
            except (ValueError, tk.TclError, TypeError):
                pass
        elif budget_key in saved:
            try:
                self.thinking_budget_var.set(int(saved[budget_key]))
            except (ValueError, tk.TclError):
                pass

        # Reasoning effort
        effort_key = f"{prefix}reasoning_effort"
        if "reasoning_effort" in api_saved:
            val = str(api_saved["reasoning_effort"]).strip().lower()
            if val in allowed_efforts:
                self.reasoning_effort_var.set(val)
            else:
                self.reasoning_effort_var.set(default_effort)
        elif effort_key in saved:
            val = saved[effort_key].strip().lower()
            if val in allowed_efforts:
                self.reasoning_effort_var.set(val)
            else:
                self.reasoning_effort_var.set(default_effort)
        else:
            self.reasoning_effort_var.set(default_effort)

        try:
            self.max_concurrent_var.set(
                max(1, min(512, int(api_saved.get("max_concurrent", 3)))),
            )
        except (ValueError, tk.TclError, TypeError):
            self.max_concurrent_var.set(3)

        self.requests_per_second_enabled_var.set(
            str(api_saved.get("requests_per_second_enabled", "false")).lower()
            in ("true", "1", "yes"),
        )
        try:
            self.requests_per_second_var.set(
                max(0.01, min(999.99, float(api_saved.get("requests_per_second", 1.0)))),
            )
        except (ValueError, tk.TclError, TypeError):
            self.requests_per_second_var.set(1.0)

        backoff_mode = str(
            api_saved.get("temporary_backoff_mode", "exponential"),
        ).strip().lower()
        if backoff_mode not in ("linear", "exponential"):
            backoff_mode = "exponential"
        self.temporary_backoff_mode_var.set(backoff_mode)

        try:
            self.temporary_backoff_attempts_var.set(
                max(0, int(api_saved.get("temporary_backoff_attempts", 5))),
            )
        except (ValueError, tk.TclError, TypeError):
            self.temporary_backoff_attempts_var.set(5)

        try:
            self.temporary_backoff_total_seconds_var.set(
                max(0, int(api_saved.get("temporary_backoff_total_seconds", 120))),
            )
        except (ValueError, tk.TclError, TypeError):
            self.temporary_backoff_total_seconds_var.set(120)

        self._update_rps_widget_state()
        self._refresh_tuning_warnings()

    def _apply_provider_temp_default(self, model_id: str) -> None:
        """Set temperature to the provider's default for this model."""
        try:
            from CherryAI.providers import ProviderRegistry
            provider = ProviderRegistry.get(self.provider_var.get())
            if provider:
                cfg = provider.get_temperature_config(model_id)
                if cfg.supported:
                    self.temperature_var.set(cfg.default)
        except Exception:
            pass

    def _save_model_settings(self) -> None:
        """Persist per-model settings (temperature, thinking) to INI."""
        try:
            from CherryAI.functions import ini_manager
            from CherryAI.functions.api_config import set_model_settings
        except Exception:
            return

        model_id = self.model_var.get()
        if not model_id:
            return

        vals = {
            f"{model_id}.temperature": str(self.temperature_var.get()),
            f"{model_id}.thinking_enabled": str(
                self.thinking_enabled_var.get(),
            ).lower(),
            f"{model_id}.thinking_budget": str(self.thinking_budget_var.get()),
            f"{model_id}.reasoning_effort": self.reasoning_effort_var.get(),
        }
        ini_manager.save_as_user_defaults("model_settings", vals)
        set_model_settings(
            model_id,
            {
                "temperature": str(self.temperature_var.get()),
                "top_p": str(self.top_p_var.get()),
                "frequency_penalty": str(self.frequency_penalty_var.get()),
                "presence_penalty": str(self.presence_penalty_var.get()),
                "thinking_enabled": str(self.thinking_enabled_var.get()).lower(),
                "thinking_budget": str(self.thinking_budget_var.get()),
                "reasoning_effort": self.reasoning_effort_var.get(),
                "max_concurrent": str(self.max_concurrent_var.get()),
                "requests_per_second_enabled": str(
                    self.requests_per_second_enabled_var.get(),
                ).lower(),
                "requests_per_second": str(self.requests_per_second_var.get()),
                "temporary_backoff_mode": self.temporary_backoff_mode_var.get(),
                "temporary_backoff_attempts": str(
                    self.temporary_backoff_attempts_var.get(),
                ),
                "temporary_backoff_total_seconds": str(
                    self.temporary_backoff_total_seconds_var.get(),
                ),
            },
        )

    def _on_refresh_models(self) -> None:
        """Refresh model lists — uses built-in curated fallback data.

        A full live-fetch from provider APIs requires API keys; this method
        refreshes the INI cache from the embedded fallback so model lists are
        always up-to-date with the latest built-in data while the app is running.
        Call ``model_registry.refresh_models(api_keys=…)`` programmatically
        when keys are available.
        """
        import threading
        from CherryAI.functions.config import reload_model_pricing

        self._refresh_models_btn.configure(state="disabled")
        self._refresh_models_label.configure(text="Refreshing…", foreground="gray")
        self.update_idletasks()

        def _do_refresh() -> None:
            try:
                # Save fallback data to INI (ensures it's always current)
                for provider_id, models in _model_registry.FALLBACK_MODELS.items():
                    _model_registry.save_to_ini(provider_id, models)
                reload_api_providers()
                reload_model_pricing()
                msg = "✓ Models updated"
                color = "green"
            except Exception as exc:
                msg = f"Error: {exc}"
                color = "red"

            def _update_ui() -> None:
                try:
                    self._refresh_models_btn.configure(state="normal")
                    self._refresh_models_label.configure(text=msg, foreground=color)
                    self._update_model_list()
                    self._provider_combo_ref.configure(values=list(API_PROVIDERS.keys()))
                except Exception:
                    pass

            try:
                self.after(0, _update_ui)
            except Exception:
                pass

        t = threading.Thread(target=_do_refresh, daemon=True)
        t.start()

    def _toggle_key_visibility(self) -> None:
        """Toggle API key visibility."""
        if self._show_key_var.get():
            self._api_key_entry.config(show="")
        else:
            self._api_key_entry.config(show="•")

    def _update_temp_label(self, *args: Any) -> None:
        """Update temperature label when value changes."""
        try:
            self._temp_label.config(text=f"{self.temperature_var.get():.1f}")
        except tk.TclError:
            pass
        self._refresh_tuning_warnings()

    def _update_top_p_label(self, *args: Any) -> None:
        """Update top-p label when value changes."""
        try:
            self._top_p_label.config(text=f"{self.top_p_var.get():.2f}")
        except tk.TclError:
            pass
        self._refresh_tuning_warnings()

    def _update_frequency_penalty_label(self, *args: Any) -> None:
        """Update frequency penalty label when value changes."""
        try:
            self._frequency_penalty_label.config(
                text=f"{self.frequency_penalty_var.get():.2f}",
            )
        except tk.TclError:
            pass
        self._refresh_tuning_warnings()

    def _update_presence_penalty_label(self, *args: Any) -> None:
        """Update presence penalty label when value changes."""
        try:
            self._presence_penalty_label.config(
                text=f"{self.presence_penalty_var.get():.2f}",
            )
        except tk.TclError:
            pass
        self._refresh_tuning_warnings()

    def _update_rps_widget_state(self) -> None:
        """Enable or disable the req/sec spinbox based on its checkbox."""
        if not hasattr(self, "_rps_spin"):
            return
        try:
            self._rps_spin.configure(
                state=(
                    "normal"
                    if self.requests_per_second_enabled_var.get()
                    else "disabled"
                ),
            )
        except tk.TclError:
            pass

    def _apply_tuning_control(
        self,
        *,
        config: Any,
        variable: tk.DoubleVar,
        scale: ttk.Scale,
        hint_label: ttk.Label,
        supported_hint: str,
        unsupported_hint: str,
    ) -> None:
        """Clamp and enable/disable a tuning control from provider config."""
        try:
            scale.configure(from_=config.min_value, to=config.max_value)
            if config.supported:
                hint_label.configure(text=supported_hint, foreground="gray")
                scale.state(["!disabled"])
                current = variable.get()
                if current < config.min_value:
                    variable.set(config.min_value)
                elif current > config.max_value:
                    variable.set(config.max_value)
            else:
                hint_label.configure(text=unsupported_hint, foreground="gray")
                variable.set(config.default)
                scale.state(["disabled"])
        except tk.TclError:
            pass

    def _refresh_tuning_warnings(self) -> None:
        """Update warning labels for model tuning controls."""
        self._set_tuning_warning(
            getattr(self, "_temp_warning_label", None),
            self.temperature_var.get(),
            warn_if=lambda value: value > 0.4,
            red_if=lambda value: value > 0.8,
            orange_text="Warning: values above 0.4 can reduce translation stability.",
            red_text="Warning: values above 0.8 are high-risk for unstable translation output.",
        )
        self._set_tuning_warning(
            getattr(self, "_top_p_warning_label", None),
            self.top_p_var.get(),
            warn_if=lambda value: value < 0.9,
            red_if=lambda value: value < 0.8,
            orange_text="Warning: values below 0.9 can noticeably narrow output variety.",
            red_text="Warning: values below 0.8 strongly constrain sampling and may degrade translations.",
        )
        self._set_tuning_warning(
            getattr(self, "_frequency_penalty_warning_label", None),
            self.frequency_penalty_var.get(),
            warn_if=lambda value: value > 0.2,
            red_if=lambda value: value < 0.0 or value > 0.4,
            orange_text="Warning: values above 0.2 can over-penalize repetition in translations.",
            red_text="Warning: negative values or values above 0.4 are high-risk for unstable wording.",
        )
        self._set_tuning_warning(
            getattr(self, "_presence_penalty_warning_label", None),
            self.presence_penalty_var.get(),
            warn_if=lambda value: value > 0.1,
            red_if=lambda value: value < 0.0 or value > 0.2,
            orange_text="Warning: values above 0.1 can push the model toward unnecessary novelty.",
            red_text="Warning: negative values or values above 0.2 are high-risk for unstable translations.",
        )

    def _set_tuning_warning(
        self,
        label: Optional[ttk.Label],
        value: float,
        *,
        warn_if: Any,
        red_if: Any,
        orange_text: str,
        red_text: str,
    ) -> None:
        """Render a warning label for a tuning value."""
        if label is None:
            return
        try:
            if red_if(value):
                label.configure(text=red_text, foreground="#cc3333")
            elif warn_if(value):
                label.configure(text=orange_text, foreground="#cc6600")
            else:
                label.configure(text="")
        except tk.TclError:
            pass

    def _show_available_models(self) -> None:
        """Show the Available Models window with cached registry data.

        Loads model metadata from the local model_registry (API.ini cache)
        instead of making a live API call.  The window provides an "Update"
        button that triggers a live connection test and refreshes the table.
        """
        from functions import model_registry
        from functions.options import _CLOUD_PROVIDER_META

        provider = self.provider_var.get()
        if not provider:
            self._test_status_label.config(
                text="Select a provider first.", foreground="orange",
            )
            return

        registry_id = _CLOUD_PROVIDER_META.get(provider, {}).get(
            "registry_id", provider,
        )
        model_ids = model_registry.get_provider_model_ids(registry_id)

        api_key = self.api_key_var.get().strip()
        base_url = self.base_url_var.get().strip()

        self._show_available_models_window(
            provider, api_key, base_url, model_ids,
        )

    def _test_connection(self) -> None:
        """Test the API connection by calling models.list() on the provider."""
        import threading

        api_key = self.api_key_var.get().strip()
        if not api_key:
            self._test_status_label.config(
                text="Error: No API key", foreground="red",
            )
            return

        provider = self.provider_var.get()
        base_url = self.base_url_var.get().strip()

        self._test_status_label.config(text="Testing…", foreground="gray")
        self.update_idletasks()

        def _do_test() -> None:
            success, msg, model_ids = _api_config.test_api_connection(
                api_key=api_key,
                provider=provider,
                base_url=base_url,
                timeout=15.0,
            )
            color = "green" if success else "red"
            prefix = "✓ " if success else "✗ "

            def _update_ui() -> None:
                try:
                    self._test_status_label.config(
                        text=f"{prefix}{msg}", foreground=color,
                    )
                    if success and model_ids:
                        self._show_api_test_results(
                            provider, api_key, base_url, model_ids,
                        )
                except Exception:
                    pass

            try:
                self.after(0, _update_ui)
            except Exception:
                pass

        t = threading.Thread(target=_do_test, daemon=True)
        t.start()

    def _show_available_models_window(
        self,
        provider: str,
        api_key: str,
        base_url: str,
        model_ids: list,
    ) -> None:
        """Open the Available Models window with model details and filters.

        Displays a filterable Treeview of models enriched with metadata from
        the model registry (pricing, capabilities).  An "Update" button
        fetches live model data from the API and refreshes the table.  Model
        IDs are normalised (``models/`` prefix stripped) so that Gemini IDs
        always match the registry.

        Args:
            provider:  Provider name (openai, gemini, …).
            api_key:   API key for live tests (may be empty).
            base_url:  Base URL (may be empty for default).
            model_ids: List of model ID strings (from registry or API).
        """
        from functions import model_registry
        from functions.options import _CLOUD_PROVIDER_META

        registry_id = _CLOUD_PROVIDER_META.get(provider, {}).get(
            "registry_id", provider,
        )

        # Normalise model IDs — strip "models/" prefix used by Gemini API
        normalised_ids: list[str] = []
        for mid in model_ids:
            clean = mid.removeprefix("models/") if mid.startswith("models/") else mid
            if clean not in normalised_ids:
                normalised_ids.append(clean)
        # Use a mutable list so the Update button can swap contents in-place
        current_ids: list[str] = list(normalised_ids)

        win = tk.Toplevel(self)
        win.title(f"Available Models — {provider}")
        win.geometry("950x550")
        win.minsize(750, 400)
        win.transient(self)
        win.grab_set()

        # Header
        hdr = ttk.Frame(win, padding=10)
        hdr.pack(fill=tk.X)
        hdr_label = ttk.Label(
            hdr,
            text=f"Provider: {provider}  —  {len(current_ids)} model(s)",
            font=("", 11, "bold"),
        )
        hdr_label.pack(side=tk.LEFT)

        # Filter bar — structured output ON by default; states persisted
        filter_bar = ttk.Frame(win, padding=(10, 0, 10, 5))
        filter_bar.pack(fill=tk.X)

        # Load saved filter state (default: structured=True, rest=False)
        _saved_struct = _api_config.get_api_setting(
            "filter_structured", "1",
        )
        _saved_batch = _api_config.get_api_setting(
            "filter_batch", "0",
        )
        _saved_thinking = _api_config.get_api_setting(
            "filter_thinking", "0",
        )
        _saved_cached = _api_config.get_api_setting(
            "filter_cached", "0",
        )
        _saved_unknown_price = _api_config.get_api_setting(
            "filter_unknown_price", "0",
        )
        _saved_above_cost_cap = _api_config.get_api_setting(
            "filter_above_cost_cap", "0",
        )

        struct_var = tk.BooleanVar(value=_saved_struct == "1")
        batch_var = tk.BooleanVar(value=_saved_batch == "1")
        thinking_var = tk.BooleanVar(value=_saved_thinking == "1")
        cached_var = tk.BooleanVar(value=_saved_cached == "1")
        unknown_price_var = tk.BooleanVar(value=_saved_unknown_price == "1")
        above_cost_cap_var = tk.BooleanVar(value=_saved_above_cost_cap == "1")

        idx_structured = 1
        idx_batch = 2
        idx_thinking = 3
        idx_cached_input = 8
        idx_status = 11

        def _apply_filter() -> None:
            """Rebuild the Treeview based on current filter checkboxes."""
            # Persist filter state
            _api_config.set_api_setting(
                "filter_structured", "1" if struct_var.get() else "0",
            )
            _api_config.set_api_setting(
                "filter_batch", "1" if batch_var.get() else "0",
            )
            _api_config.set_api_setting(
                "filter_thinking", "1" if thinking_var.get() else "0",
            )
            _api_config.set_api_setting(
                "filter_cached", "1" if cached_var.get() else "0",
            )
            _api_config.set_api_setting(
                "filter_unknown_price",
                "1" if unknown_price_var.get() else "0",
            )
            _api_config.set_api_setting(
                "filter_above_cost_cap",
                "1" if above_cost_cap_var.get() else "0",
            )
            tree.delete(*tree.get_children())
            for mid in current_ids:
                info = model_registry.get_model_info(mid)
                row = _build_row(mid, info)
                if struct_var.get() and row[idx_structured] != "✓":
                    continue
                if batch_var.get() and row[idx_batch] != "✓":
                    continue
                # "No / Optional Thinking" — hide models that *require*
                # thinking (row[3] == "✓") when the checkbox is ON.
                if thinking_var.get() and row[idx_thinking] == "✓":
                    continue
                if cached_var.get() and row[idx_cached_input] == "—":
                    continue
                if not unknown_price_var.get() and row[idx_status] == "Unknown Price":
                    continue
                if not above_cost_cap_var.get() and row[idx_status] == "Above Cost Cap":
                    continue
                tree.insert("", tk.END, values=row)

        ttk.Checkbutton(
            filter_bar, text="Structured Output only",
            variable=struct_var, command=_apply_filter,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(
            filter_bar, text="Batch only",
            variable=batch_var, command=_apply_filter,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(
            filter_bar, text="No / Optional Thinking",
            variable=thinking_var, command=_apply_filter,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(
            filter_bar, text="Cached Input",
            variable=cached_var, command=_apply_filter,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(
            filter_bar, text="Unknown Price",
            variable=unknown_price_var, command=_apply_filter,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(
            filter_bar, text="Above Cost Cap",
            variable=above_cost_cap_var, command=_apply_filter,
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Treeview columns
        try:
            from CherryAI.providers import ProviderRegistry
            provider_impl = ProviderRegistry.get(registry_id)
        except Exception:
            provider_impl = None

        cols = (
            "model", "structured", "batch", "thinking", "temperature",
            "top_p", "freq_pen", "pres_pen", "cached_input",
            "input_price", "output_price", "status", "context",
        )
        col_widths = {
            "model": 250, "structured": 90, "batch": 60,
            "thinking": 70, "temperature": 70, "top_p": 70,
            "freq_pen": 70, "pres_pen": 70, "cached_input": 90,
            "input_price": 100, "output_price": 100,
            "status": 120,
            "context": 100,
        }
        col_headings = {
            "model": "Model", "structured": "Structured",
            "batch": "Batch", "thinking": "Thinking",
            "temperature": "Temp", "top_p": "Top P",
            "freq_pen": "Freq Pen", "pres_pen": "Pres Pen",
            "cached_input": "Cached $/1M",
            "input_price": "Input $/1M", "output_price": "Output $/1M",
            "status": "Status",
            "context": "Context",
        }

        tree_frame = ttk.Frame(win, padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=15,
        )
        for c in cols:
            tree.heading(c, text=col_headings[c])
            anchor = tk.W if c == "model" else tk.CENTER
            tree.column(c, width=col_widths[c], anchor=anchor)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        def _build_row(
            mid: str, info: Optional[model_registry.ModelInfo],
        ) -> tuple:
            """Build a display row from a model ID and optional registry info."""
            def _format_price(value: Optional[float], unknown: str = "Unknown") -> str:
                if value is None:
                    return unknown
                return f"${value:.2f}"

            def _format_support(supported: bool) -> str:
                return "✓" if supported else "—"

            temp_display = "?"
            top_p_display = "?"
            freq_display = "?"
            pres_display = "?"
            if provider_impl is not None:
                try:
                    temp_display = _format_support(
                        provider_impl.get_temperature_config(mid).supported,
                    )
                    top_p_display = _format_support(
                        provider_impl.get_top_p_config(mid).supported,
                    )
                    freq_display = _format_support(
                        provider_impl.get_frequency_penalty_config(mid).supported,
                    )
                    pres_display = _format_support(
                        provider_impl.get_presence_penalty_config(mid).supported,
                    )
                except Exception:
                    pass

            if info:
                cost_status = model_registry.get_model_cost_status(
                    info,
                    cost_cap=self._get_cost_cap_value(),
                )
                if info.thinking:
                    if info.thinking_mode in ("mandatory", "builtin"):
                        thinking_display = "✓"
                    else:
                        thinking_display = "Optional"
                else:
                    thinking_display = "—"
                if not cost_status.price_known:
                    status_display = "Unknown Price"
                elif cost_status.above_cost_cap:
                    status_display = "Above Cost Cap"
                elif info.output_price == 0.0:
                    status_display = "Free"
                else:
                    status_display = "OK"
                return (
                    mid,
                    "✓" if info.structured_output else "—",
                    "✓" if info.batch_mode else "—",
                    thinking_display,
                    temp_display,
                    top_p_display,
                    freq_display,
                    pres_display,
                    _format_price(info.cached_input_price, unknown="—"),
                    _format_price(info.input_price),
                    _format_price(info.output_price),
                    status_display,
                    f"{info.context_window:,}" if info.context_window else "—",
                )
            unknown_status = model_registry.get_model_cost_status_by_id(
                mid,
                cost_cap=self._get_cost_cap_value(),
            )
            status_display = (
                "Above Cost Cap"
                if unknown_status.above_cost_cap
                else "Unknown Price"
            )
            return (
                mid,
                "?",
                "?",
                "?",
                temp_display,
                top_p_display,
                freq_display,
                pres_display,
                "—",
                "Unknown",
                "Unknown",
                status_display,
                "?",
            )

        # Populate table (respects current filter state)
        _apply_filter()

        # Bottom button bar
        btn_bar = ttk.Frame(win, padding=10)
        btn_bar.pack(fill=tk.X)

        test_result_label = ttk.Label(btn_bar, text="", foreground="gray")
        test_result_label.pack(
            side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True,
        )

        def _test_selected_model() -> None:
            """Run a translation probe against the selected model."""
            import threading as _thr

            sel = tree.selection()
            if not sel:
                test_result_label.config(
                    text="Select a model first.", foreground="orange",
                )
                return
            mid = tree.item(sel[0], "values")[0]
            test_result_label.config(
                text=f"Testing {mid}…", foreground="gray",
            )
            win.update_idletasks()

            def _run() -> None:
                result = _api_config.test_model_translation(
                    api_key=api_key,
                    model_id=mid,
                    provider=provider,
                    base_url=base_url,
                    timeout=30.0,
                )
                ok = result.get("success", False)
                checks = result.get("checks", [])
                elapsed = result.get("elapsed_seconds", 0.0)
                passed = sum(1 for c in checks if c.get("passed"))
                total = len(checks)
                summary = (
                    f"{'✓' if ok else '✗'} {mid}: {passed}/{total} checks "
                    f"passed ({elapsed:.1f}s)"
                )
                color = "green" if ok else "red"
                if passed > 0 and not ok:
                    color = "orange"

                def _upd() -> None:
                    try:
                        test_result_label.config(
                            text=summary, foreground=color,
                        )
                    except Exception:
                        pass

                try:
                    win.after(0, _upd)
                except Exception:
                    pass

            _thr.Thread(target=_run, daemon=True).start()

        def _update_models() -> None:
            """Fetch live model list from the API and refresh the table."""
            import threading as _thr

            effective_key = api_key
            if not effective_key:
                test_result_label.config(
                    text="No API key — enter one in the Provider section.",
                    foreground="orange",
                )
                return

            test_result_label.config(
                text="Updating…", foreground="gray",
            )
            win.update_idletasks()

            def _run() -> None:
                success, msg, live_ids = _api_config.test_api_connection(
                    api_key=effective_key,
                    provider=provider,
                    base_url=base_url,
                    timeout=15.0,
                )

                # When successful, also refresh the model registry to persist
                # model metadata (pricing, capabilities) into API.ini.
                saved_count = 0
                if success and live_ids:
                    try:
                        refreshed = model_registry.refresh_models(
                            api_keys={registry_id: effective_key},
                            providers=[registry_id],
                            probe_limits=True,
                        )
                        saved_count = len(refreshed.get(registry_id, []))
                        # Reload config.py pricing cache
                        from functions.config import reload_model_pricing
                        reload_model_pricing()
                    except Exception:
                        pass

                def _refresh_ui() -> None:
                    try:
                        if success and live_ids:
                            # Normalise IDs (strip models/ prefix)
                            current_ids.clear()
                            seen: set[str] = set()
                            for mid in live_ids:
                                clean = mid.removeprefix("models/")
                                if clean not in seen:
                                    current_ids.append(clean)
                                    seen.add(clean)
                            hdr_label.config(
                                text=(
                                    f"Provider: {provider}  —  "
                                    f"{len(current_ids)} model(s)"
                                ),
                            )
                            _apply_filter()
                            extra = (
                                f" ({saved_count} saved to registry)"
                                if saved_count else ""
                            )
                            test_result_label.config(
                                text=f"✓ {msg}{extra}",
                                foreground="green",
                            )
                        else:
                            test_result_label.config(
                                text=f"✗ {msg}", foreground="red",
                            )
                    except Exception:
                        pass

                try:
                    win.after(0, _refresh_ui)
                except Exception:
                    pass

            _thr.Thread(target=_run, daemon=True).start()

        def _set_as_default() -> None:
            """Set the selected model as the default for the current key."""
            sel = tree.selection()
            if not sel:
                test_result_label.config(
                    text="Select a model first.", foreground="orange",
                )
                return
            mid = tree.item(sel[0], "values")[0]
            # Determine provider's key name from what's currently loaded
            # Find matching key in saved keys
            try:
                keys = _api_config.list_api_keys()
            except Exception:
                keys = []
            matched_name = "default"
            for kp, kn in keys:
                if kp.lower() == provider.lower():
                    matched_name = kn
                    break
            _api_config.set_default_model(provider, matched_name, mid)
            test_result_label.config(
                text=f"✓ Default model set: {mid}", foreground="green",
            )

        ttk.Button(
            btn_bar, text="Test Model Translation",
            command=_test_selected_model,
        ).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(
            btn_bar, text="Set as Default",
            command=_set_as_default,
        ).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(
            btn_bar, text="Update",
            command=_update_models,
        ).pack(side=tk.RIGHT, padx=(5, 0))

        def _save_filtered() -> None:
            """Save the currently visible (filtered) model list."""
            visible_ids = [
                tree.item(child, "values")[0]
                for child in tree.get_children()
            ]
            if not visible_ids:
                test_result_label.config(
                    text="No models to save.", foreground="orange",
                )
                return
            _api_config.set_api_setting(
                "saved_models",
                ",".join(visible_ids),
            )
            test_result_label.config(
                text=(
                    f"✓ {len(visible_ids)} model(s) saved to "
                    f"preferences."
                ),
                foreground="green",
            )

        ttk.Button(
            btn_bar, text="Save",
            command=_save_filtered,
        ).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(
            btn_bar, text="Close", command=win.destroy,
        ).pack(side=tk.RIGHT)

    # Keep legacy name as alias for backward compatibility
    _show_api_test_results = _show_available_models_window

    # ---- API Key management helpers ----

    def _prompt_password(self, title: str = "Password") -> Optional[str]:
        """Show a simple password dialog.  Returns None if cancelled."""
        import tkinter.simpledialog as simpledialog

        pw = simpledialog.askstring(
            title, "Enter master password:", show="•", parent=self,
        )
        return pw if pw else None

    def _ensure_password_set(self) -> Optional[str]:
        """Ensure a master password is set.  Returns the password or None.

        If no password has been set yet, prompts the user to create one.
        Otherwise, prompts to verify the existing password.
        """
        if _api_config.is_password_set():
            return self._prompt_password("Unlock API Keys")

        # First-time password setup
        import tkinter.simpledialog as simpledialog

        pw = simpledialog.askstring(
            "Set Master Password",
            "No master password set yet.\n"
            "Enter a new master password to protect your API keys:",
            show="•",
            parent=self,
        )
        if not pw:
            return None

        pw2 = simpledialog.askstring(
            "Confirm Password",
            "Confirm master password:",
            show="•",
            parent=self,
        )
        if pw != pw2:
            messagebox.showerror("Error", "Passwords do not match.", parent=self)
            return None

        if _api_config.set_password(pw):
            messagebox.showinfo(
                "Password Set",
                "Master password has been set successfully.",
                parent=self,
            )
            return pw
        messagebox.showerror(
            "Error", "Failed to set master password (bcrypt unavailable?).",
            parent=self,
        )
        return None

    def _refresh_providers_tree(self) -> None:
        """Rebuild the API keys Treeview from ``user/API.ini``."""
        tree = self._providers_tree
        for child in tree.get_children():
            tree.delete(child)
        for idx, (provider, name) in enumerate(_api_config.list_api_keys()):
            tree.insert("", "end", iid=str(idx), values=(name, provider))

    def _save_api_key(self) -> None:
        """Save the current API key to API.ini with a user-chosen name.

        If no master password is set, the key is stored in plaintext.
        If a password is set, the key is encrypted with it.
        """
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning(
                "No Key", "Enter an API key first.", parent=self,
            )
            return

        provider = self.provider_var.get()
        if not provider:
            messagebox.showwarning(
                "No Provider", "Select a provider first.", parent=self,
            )
            return

        # Ask for a name
        import tkinter.simpledialog as simpledialog

        key_name = simpledialog.askstring(
            "Save API Key",
            f"Enter a name for this {provider} key:",
            initialvalue="default",
            parent=self,
        )
        if not key_name or not key_name.strip():
            return

        # If no password is set, store plaintext
        if not _api_config.is_password_set():
            if _api_config.set_api_key_plain(provider, api_key, key_name.strip()):
                messagebox.showinfo(
                    "Saved",
                    f"API key '{key_name.strip()}' saved for {provider} (plaintext).",
                    parent=self,
                )
                self._refresh_providers_tree()
            else:
                messagebox.showerror("Error", "Failed to save key.", parent=self)
            return

        # Password is set — encrypt
        password = self._prompt_password("Enter Master Password")
        if not password:
            return

        if _api_config.set_api_key(provider, api_key, password, key_name.strip()):
            messagebox.showinfo(
                "Saved",
                f"API key '{key_name.strip()}' saved for {provider} (encrypted).",
                parent=self,
            )
            self._refresh_providers_tree()
        else:
            messagebox.showerror(
                "Error",
                "Failed to save — incorrect password or encryption unavailable.",
                parent=self,
            )

    def _load_api_key(self) -> None:
        """Load a saved API key into the API key entry field."""
        sel = self._providers_tree.selection()
        if not sel:
            messagebox.showinfo(
                "Select Key", "Select a saved key to load.", parent=self,
            )
            return

        values = self._providers_tree.item(sel[0], "values")
        key_name, provider = values[0], values[1]

        # If no password set, load plaintext directly
        if not _api_config.is_password_set():
            plaintext = _api_config.get_api_key_plain(provider, key_name)
            if plaintext:
                self.api_key_var.set(plaintext)
                self.provider_var.set(provider)
                self._on_provider_change(None)
                messagebox.showinfo(
                    "Loaded",
                    f"Key '{key_name}' loaded for {provider}.",
                    parent=self,
                )
            else:
                messagebox.showerror(
                    "Error", "Key not found.", parent=self,
                )
            return

        password = self._prompt_password("Unlock API Key")
        if not password:
            return

        plaintext = _api_config.get_api_key(provider, password, key_name)
        if plaintext:
            self.api_key_var.set(plaintext)
            self.provider_var.set(provider)
            self._on_provider_change(None)
            messagebox.showinfo(
                "Loaded",
                f"Key '{key_name}' loaded for {provider}.",
                parent=self,
            )
        else:
            messagebox.showerror(
                "Error",
                "Failed to decrypt — wrong password or key not found.",
                parent=self,
            )

    def _remove_api_key(self) -> None:
        """Remove the selected saved API key."""
        sel = self._providers_tree.selection()
        if not sel:
            return
        values = self._providers_tree.item(sel[0], "values")
        key_name, provider = values[0], values[1]
        if messagebox.askyesno(
            "Remove Key", f"Remove saved key '{key_name}' ({provider})?",
            parent=self,
        ):
            _api_config.delete_api_key(provider, key_name)
            self._refresh_providers_tree()

    def _browse_cache_dir(self) -> None:
        """Browse for cache directory."""
        directory = filedialog.askdirectory(title="Select Cache Directory")
        if directory:
            self.cache_dir_var.set(directory)

    def _clear_cache(self) -> None:
        """Clear the request cache."""
        response = messagebox.askyesno("Clear Cache", "Are you sure you want to clear the cache?")
        if response:
            cache_dir = Path(self.cache_dir_var.get())
            if cache_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(cache_dir)
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    messagebox.showinfo("Cache Cleared", "Cache has been cleared successfully.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to clear cache: {e}")
            else:
                messagebox.showinfo("Cache Empty", "Cache directory does not exist.")

    def _browse_log_file(self) -> None:
        """Browse for log file location."""
        file_path = filedialog.asksaveasfilename(
            title="Select Log File",
            defaultextension=".log",
            filetypes=[("Log Files", "*.log"), ("All Files", "*.*")],
        )
        if file_path:
            self.log_file_var.set(file_path)

    def _open_log_file(self) -> None:
        """Open the log file in the default text editor."""
        log_path = Path(self.log_file_var.get())
        if log_path.exists():
            import os
            os.startfile(str(log_path))
        else:
            messagebox.showinfo("Log File", "Log file does not exist yet.")

    def _add_ban_token(self, token: str) -> None:
        """Add a token to the ban list."""
        current = self.ban_tokens_var.get()
        tokens = [t.strip() for t in current.split(",") if t.strip()]
        if token not in tokens:
            tokens.append(token)
            self.ban_tokens_var.set(", ".join(tokens))

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.destroy()

    def _on_apply(self) -> None:
        """Handle Apply button - save without closing."""
        self._save_options()

    def _on_ok(self) -> None:
        """Handle OK button - save and close."""
        self._save_options()
        self.destroy()

    def _on_save_as_default(self) -> None:
        """Handle Save as Default button - save current values as user defaults.

        Collects current form values into the options object, persists
        everything to ``CherryAI.ini`` via ``_persist_to_ini()``, and
        shows a confirmation message.
        """
        response = messagebox.askyesno(
            "Save as Default",
            "Save current settings as your personal defaults?\n\n"
            "These will be used for new projects and when restoring defaults.",
        )
        if not response:
            return

        try:
            self._save_options()
            messagebox.showinfo(
                "Defaults Saved",
                "Your settings have been saved as defaults.",
            )
            logger.info("User defaults saved successfully")
        except Exception as e:
            logger.error("Failed to save user defaults: %s", e)
            messagebox.showerror("Error", f"Failed to save defaults: {e}")

    def _on_reset_confirmations(self) -> None:
        """Re-enable all suppressed confirmation dialogs."""
        from CherryAI.gui.helpers.confirmations import reset_all_suppressions

        reset_all_suppressions()
        messagebox.showinfo(
            "Confirmations Reset",
            "All confirmation dialogs have been re-enabled.",
        )
        logger.info("All confirmation dialog suppressions reset")

    def _on_reset_presets(self) -> None:
        """Reset style and tone presets to factory defaults via INI."""
        from CherryAI.functions import ini_manager  # noqa: PLC0415

        if not messagebox.askyesno(
            "Reset Presets",
            "Reset style and tone presets to factory defaults?\n\n"
            "All user-saved presets will be removed.",
        ):
            return
        ini_manager.restore_preset_defaults("style")
        ini_manager.restore_preset_defaults("tone")
        ini_manager.reload_ini()
        messagebox.showinfo(
            "Presets Reset",
            "Style and tone presets have been restored to defaults.\n"
            "Reload the Information step to see the change.",
        )
        logger.info("Style/tone presets reset to factory defaults")

    def _on_restore_defaults(self) -> None:
        """Open a checklist dialog so the user can choose which areas to restore."""
        import tkinter as _tk

        dlg = tk.Toplevel(self)
        dlg.title("Restore Defaults")
        dlg.geometry("380x340")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text="Select areas to reset to factory defaults:", padding=(10, 10, 10, 5)).pack(anchor="w")

        areas = [
            ("confirmation_dialogs", "Confirmation Dialogs"),
            ("style_tone", "Style & Tone Presets"),
            ("system_instructions", "System Instructions"),
            ("session", "Session Settings"),
        ]

        vars_: Dict[str, tk.BooleanVar] = {}
        for key, label in areas:
            v = tk.BooleanVar(value=False)
            vars_[key] = v
            ttk.Checkbutton(dlg, text=label, variable=v, padding=(20, 2)).pack(anchor="w")

        def _apply() -> None:
            if vars_["confirmation_dialogs"].get():
                self._on_reset_confirmations()
            if vars_["style_tone"].get():
                self._on_reset_presets()
            if vars_["system_instructions"].get():
                try:
                    from CherryAI.functions import ini_manager  # noqa: PLC0415
                    ini_manager.remove_section("system_instructions")
                    ini_manager.reload_ini()  # re-seeds Default preset
                except Exception:  # noqa: BLE001
                    pass
            if vars_["session"].get():
                try:
                    from CherryAI.functions import ini_manager
                    ini_manager.set_session_setting("load_last", "true")
                except Exception:
                    pass
            dlg.destroy()

        btn_frame = ttk.Frame(dlg, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(btn_frame, text="Restore Selected", command=_apply).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)

    def _on_restore_initial_defaults(self) -> None:
        """Handle Restore Initial Defaults button - restore factory settings."""
        from CherryAI.functions import ini_manager

        response = messagebox.askyesno(
            "Restore Initial Defaults",
            "Restore all settings to factory defaults?\n\n"
            "This will clear your saved personal defaults and\n"
            "reset the form to the initial values.",
        )
        if not response:
            return

        try:
            # Clear all user defaults
            ini_manager.restore_initial_defaults()

            # Reload defaults cache
            ini_manager.reload_defaults_cache()

            # Reset form to initial defaults
            self._load_initial_defaults()

            messagebox.showinfo("Defaults Restored", "Settings have been restored to factory defaults.")
            logger.info("Initial defaults restored")

        except Exception as e:
            logger.error("Failed to restore initial defaults: %s", e)
            messagebox.showerror("Error", f"Failed to restore defaults: {e}")

    def _load_initial_defaults(self) -> None:
        """Load initial defaults from config/defaults.ini into form fields."""
        from CherryAI.functions import ini_manager

        # API defaults
        self.provider_var.set(
            ini_manager.get_initial_default("api", "provider", "openai", str) or "openai"
        )
        self.model_var.set(
            ini_manager.get_initial_default("api", "model", "gpt-4o-mini", str) or "gpt-4o-mini"
        )
        self.temperature_var.set(
            float(ini_manager.get_initial_default("api", "temperature", 0.3, float) or 0.3)
        )
        # Don't reset API key - that's sensitive
        self.base_url_var.set(
            ini_manager.get_initial_default("api", "base_url", "", str) or ""
        )
        self.cost_cap_var.set(
            float(
                ini_manager.get_initial_default(
                    "api",
                    "cost_cap",
                    _model_registry.DEFAULT_COST_CAP,
                    float,
                )
                or _model_registry.DEFAULT_COST_CAP
            )
        )

        # Request defaults
        self.timeout_var.set(
            int(ini_manager.get_initial_default("api", "timeout", 60, int) or 60)
        )
        self.retries_var.set(
            int(ini_manager.get_initial_default("api", "retries", 3, int) or 3)
        )
        self.rate_limit_var.set(
            int(ini_manager.get_initial_default("api", "rate_limit_requests", 60, int) or 60)
        )
        self.chunk_size_var.set(
            int(ini_manager.get_initial_default("api", "chunk_size", 50, int) or 50)
        )
        self.max_input_tokens_var.set(
            int(ini_manager.get_initial_default("api", "max_input_tokens", 0, int) or 0)
        )

        # Rolling context defaults
        self.rolling_context_var.set(
            int(ini_manager.get_initial_default("request", "rolling_context_lines", 3, int) or 3)
        )
        self.rolling_context_between_var.set(
            int(ini_manager.get_initial_default("request", "rolling_context_between", 0, int) or 0)
        )
        self.rolling_context_after_var.set(
            int(ini_manager.get_initial_default("request", "rolling_context_after", 0, int) or 0)
        )
        self.use_translated_context_var.set(
            bool(ini_manager.get_initial_default("request", "use_translated_context", True, bool))
        )

        # Translation defaults
        self.overwrite_translation_var.set(
            bool(ini_manager.get_initial_default("translation", "overwrite_translation", False, bool))
        )
        self.skip_non_source_var.set(
            bool(ini_manager.get_initial_default("translation", "skip_non_source_language", True, bool))
        )
        self.retry_strategy_var.set(
            ini_manager.get_initial_default("translation", "retry_strategy", "batch", str) or "batch"
        )
        self.request_slicing_var.set(
            ini_manager.get_initial_default("translation", "request_slicing", "conservative", str)
            or "conservative"
        )
        self.exchange_forbidden_var.set(
            bool(ini_manager.get_initial_default("translation", "exchange_forbidden_chars", True, bool))
        )
        self.flag_qa_review_var.set(
            bool(ini_manager.get_initial_default("translation", "flag_for_qa_review", True, bool))
        )
        self.retry_forbidden_var.set(
            bool(ini_manager.get_initial_default("translation", "retry_forbidden_chars", False, bool))
        )

        # Caching defaults
        self.cache_enabled_var.set(
            bool(ini_manager.get_initial_default("caching", "enabled", True, bool))
        )
        self.cache_dir_var.set(
            ini_manager.get_initial_default("caching", "cache_dir", "temp/cache", str) or "temp/cache"
        )
        self.cache_max_age_var.set(
            int(ini_manager.get_initial_default("caching", "max_age_hours", 24, int) or 24)
        )
        self.cache_max_size_var.set(
            int(ini_manager.get_initial_default("caching", "max_size_mb", 100, int) or 100)
        )

        # Logging defaults
        self.log_level_var.set(
            ini_manager.get_initial_default("log", "level", "Error", str) or "Error"
        )
        self.log_file_var.set(
            ini_manager.get_initial_default("log", "location", "log/", str) or "log/"
        )
        self.debug_mode_var.set(
            bool(ini_manager.get_initial_default("log", "debug", False, bool))
        )
        self.log_api_calls_var.set(
            bool(ini_manager.get_initial_default("log", "api_log", True, bool))
        )
        self.log_requests_var.set(
            bool(ini_manager.get_initial_default("log", "log_requests", False, bool))
        )

        # Session defaults
        self.autosave_enabled_var.set(
            bool(ini_manager.get_initial_default("session", "autosave", True, bool))
        )
        self.autosave_interval_var.set(
            int(ini_manager.get_initial_default("session", "interval", 60, int) or 60)
        )
        self.restore_on_launch_var.set(
            bool(ini_manager.get_initial_default("session", "load_last", True, bool))
        )

        # GUI defaults
        self.gui_design_var.set(
            get_theme_display_name(
                ini_manager.get_initial_default("ui", "design", "pale_blue", str) or "pale_blue"
            )
        )
        self.save_window_dimensions_var.set(
            bool(ini_manager.get_initial_default("ui", "save_window_dimensions", True, bool))
        )
        self.launch_maximized_var.set(
            bool(ini_manager.get_initial_default("ui", "launch_maximized", False, bool))
        )

        # Limit defaults
        self.ban_tokens_var.set(
            ini_manager.get_initial_default("limit", "banned", "\u2014, \u2013", str) or "\u2014, \u2013"
        )
        self.warning_abort_enabled_var.set(
            bool(
                ini_manager.get_initial_default(
                    "limit",
                    "unsafe_abort_enabled",
                    bool(ini_manager.get_initial_default("limit", "warnings", True, bool)),
                    bool,
                )
            )
        )
        self.warning_abort_after_var.set(
            max(
                1,
                int(ini_manager.get_initial_default("limit", "unsafe_abort_after", 1, int) or 1),
            )
        )
        self.max_output_tokens_var.set(
            int(ini_manager.get_initial_default("limit", "output", 4096, int) or 4096)
        )
        self.skip_unsafe_requests_var.set(
            bool(
                ini_manager.get_initial_default(
                    "limit",
                    "skip_unsafe_requests",
                    bool(ini_manager.get_initial_default("limit", "safe", True, bool)),
                    bool,
                )
            )
        )

        # File I/O defaults
        self.encoding_var.set(
            ini_manager.get_initial_default("fileio", "encoding", "auto", str) or "auto"
        )
        self.line_ending_var.set(
            ini_manager.get_initial_default("fileio", "lines", "auto", str) or "auto"
        )
        self.preserve_bom_var.set(
            bool(ini_manager.get_initial_default("fileio", "preservebom", True, bool))
        )
        self.backup_originals_var.set(
            bool(ini_manager.get_initial_default("fileio", "backup", True, bool))
        )

        # Prompts defaults — utility prompts
        _util_prompt_defaults = {
            "term_glossary": (
                DEFAULT_TERM_GLOSSARY_PROMPT,
                self._term_glossary_prompt_text,
            ),
            "term_code": (
                DEFAULT_TERM_CODE_PROMPT,
                self._term_code_prompt_text,
            ),
            "gender_inference": (
                DEFAULT_GENDER_INFERENCE_PROMPT,
                self._gender_inference_prompt_text,
            ),
        }
        for _key, (_default, _widget) in _util_prompt_defaults.items():
            _val = (
                ini_manager.get_initial_default(
                    "prompts", _key, _default, str,
                )
                or _default
            )
            _widget.delete("1.0", tk.END)
            _widget.insert("1.0", _val)

        # Prompts defaults — Edit / TLC
        edit_prompt = (
            ini_manager.get_initial_default("prompts", "edit", DEFAULT_EDIT_PROMPT, str)
            or DEFAULT_EDIT_PROMPT
        )
        tlc_prompt = (
            ini_manager.get_initial_default("prompts", "tlc", DEFAULT_TLC_PROMPT, str)
            or DEFAULT_TLC_PROMPT
        )
        self._edit_prompt_text.delete("1.0", tk.END)
        self._edit_prompt_text.insert("1.0", edit_prompt)
        self._tlc_prompt_text.delete("1.0", tk.END)
        self._tlc_prompt_text.insert("1.0", tlc_prompt)

        # Conditional prompt defaults (from [conditional_prompts] via ini_manager)
        _cond_defaults = {
            "dialogue": DEFAULT_DIALOGUE_PROMPT,
            "menu": DEFAULT_MENU_PROMPT,
            "choice": DEFAULT_CHOICE_PROMPT,
            "unknown": DEFAULT_UNKNOWN_PROMPT,
        }
        _cond_widgets = {
            "dialogue": self._dialogue_prompt_text,
            "menu": self._menu_prompt_text,
            "choice": self._choice_prompt_text,
            "unknown": self._unknown_prompt_text,
        }
        for _key, _widget in _cond_widgets.items():
            _val = (
                ini_manager.get_initial_default("conditional_prompts", _key, _cond_defaults[_key], str)
                or _cond_defaults[_key]
            )
            _widget.delete("1.0", tk.END)
            _widget.insert("1.0", _val)

        # Update model list for new provider
        self._update_model_list()

    def _save_options(self) -> None:
        """Save the current options."""
        # Collect all values into options object
        self.options.api = APISettings(
            provider=self.provider_var.get(),
            api_key=self.api_key_var.get(),
            base_url=self.base_url_var.get(),
            model=self.model_var.get(),
            temperature=self.temperature_var.get(),
            cost_cap=self._get_cost_cap_value(),
        )

        self.options.request = RequestSettings(
            timeout=self.timeout_var.get(),
            retries=self.retries_var.get(),
            rate_limit=self.rate_limit_var.get(),
            chunk_size=self.chunk_size_var.get(),
            max_input_tokens=self.max_input_tokens_var.get(),
            thinking_enabled=self.thinking_enabled_var.get(),
            thinking_budget=self.thinking_budget_var.get(),
            rolling_context_lines=self.rolling_context_var.get(),
            rolling_context_between=self.rolling_context_between_var.get(),
            rolling_context_after=self.rolling_context_after_var.get(),
            use_translated_context=self.use_translated_context_var.get(),
            remove_duplicate_speakers=self.remove_dup_speakers_var.get(),
            glossary_filter_mode=self.glossary_filter_var.get(),
            consistency_mode=self.consistency_mode_var.get(),
        )

        self.options.translation = TranslationSettings(
            overwrite_translation=self.overwrite_translation_var.get(),
            skip_non_source_language=self.skip_non_source_var.get(),
            retry_strategy=self.retry_strategy_var.get(),
            request_slicing=self.request_slicing_var.get(),
            exchange_forbidden_chars=self.exchange_forbidden_var.get(),
            flag_for_qa_review=self.flag_qa_review_var.get(),
            retry_forbidden_chars=self.retry_forbidden_var.get(),
        )

        self.options.utility = UtilitySettings(
            term_translation_mode=self._term_mode_var.get(),
            term_api_key_provider=self._term_api_provider_var.get(),
            term_api_key_name=self._term_api_name_var.get(),
            term_model=self._term_model_var.get(),
            term_batch_size=self._term_batch_size_var.get(),
            gender_inference_mode=self._gender_mode_var.get(),
            gender_api_key_provider=self._gender_api_provider_var.get(),
            gender_api_key_name=self._gender_api_name_var.get(),
            gender_model=self._gender_model_var.get(),
            gender_script_minimum=self._gender_script_min_var.get(),
            gender_script_maximum=self._gender_script_max_var.get(),
            gender_script_ignore_unknown=self._gender_script_ign_var.get(),
            gender_script_do_all=self._gender_script_doall_var.get(),
            gender_llm_minimum=self._gender_llm_min_var.get(),
            gender_llm_maximum=self._gender_llm_max_var.get(),
            gender_llm_ignore_unknown=self._gender_llm_ign_var.get(),
            gender_llm_do_all=self._gender_llm_doall_var.get(),
            speaker_threshold=self._speaker_threshold_var.get(),
        )

        # Persist utility API settings to API.ini profiles
        from CherryAI.functions import api_config as _api_cfg
        _api_cfg.set_profile_setting(
            "term_translation", "provider",
            self.options.utility.term_api_key_provider,
        )
        _api_cfg.set_profile_setting(
            "term_translation", "key_name",
            self.options.utility.term_api_key_name,
        )
        _api_cfg.set_profile_setting(
            "term_translation", "model",
            self.options.utility.term_model,
        )
        _api_cfg.set_profile_setting(
            "gender_inference", "provider",
            self.options.utility.gender_api_key_provider,
        )
        _api_cfg.set_profile_setting(
            "gender_inference", "key_name",
            self.options.utility.gender_api_key_name,
        )
        _api_cfg.set_profile_setting(
            "gender_inference", "model",
            self.options.utility.gender_model,
        )

        self.options.caching = CachingSettings(
            enabled=self.cache_enabled_var.get(),
            dir=self.cache_dir_var.get(),
            age=self.cache_max_age_var.get(),
            size=self.cache_max_size_var.get(),
            mode=self.cache_mode_var.get(),
        )

        self.options.logging = LoggingSettings(
            level=self.log_level_var.get(),
            location=self.log_file_var.get(),
            debug=self.debug_mode_var.get(),
            api_log=self.log_api_calls_var.get(),
            log_requests=self.log_requests_var.get(),
        )

        self.options.session = SessionSettings(
            autosave=self.autosave_enabled_var.get(),
            interval=self.autosave_interval_var.get(),
            theme=self.options.session.theme,
            load_last=self.restore_on_launch_var.get(),
        )

        from CherryAI.gui.theme.colors import get_theme_mode_from_display
        self.options.gui = GUISettings(
            design=get_theme_mode_from_display(self.gui_design_var.get()).value,
            save_window_dimensions=self.save_window_dimensions_var.get(),
            launch_maximized=self.launch_maximized_var.get(),
        )

        self.options.limit = LimitSettings(
            banned=self.ban_tokens_var.get(),
            warning_abort_enabled=self.warning_abort_enabled_var.get(),
            warning_abort_after=max(1, self.warning_abort_after_var.get()),
            output=self.max_output_tokens_var.get(),
            skip_unsafe_requests=self.skip_unsafe_requests_var.get(),
        )

        self.options.file_io = FileIOSettings(
            encoding=self.encoding_var.get(),
            lines=self.line_ending_var.get(),
            preservebom=self.preserve_bom_var.get(),
            backup=self.backup_originals_var.get(),
        )

        self.options.prompts = PromptsSettings(
            term_glossary=self._term_glossary_prompt_text.get(
                "1.0", tk.END,
            ).strip(),
            term_code=self._term_code_prompt_text.get(
                "1.0", tk.END,
            ).strip(),
            gender_inference=self._gender_inference_prompt_text.get(
                "1.0", tk.END,
            ).strip(),
            edit=self._edit_prompt_text.get("1.0", tk.END).strip(),
            tlc=self._tlc_prompt_text.get("1.0", tk.END).strip(),
            dialogue=self._dialogue_prompt_text.get("1.0", tk.END).strip(),
            menu=self._menu_prompt_text.get("1.0", tk.END).strip(),
            choice=self._choice_prompt_text.get("1.0", tk.END).strip(),
            unknown=self._unknown_prompt_text.get("1.0", tk.END).strip(),
            # Component toggles
            glossary=self.edit_include_glossary_var.get(),
            summary=self.edit_include_game_summary_var.get(),
            code=self.edit_include_code_glossary_var.get(),
            tlc_include_glossary=self.tlc_include_glossary_var.get(),
            tlc_include_game_summary=self.tlc_include_game_summary_var.get(),
            tlc_include_code_glossary=self.tlc_include_code_glossary_var.get(),
            # Input policies
            edit_input_policy=self.edit_input_policy_var.get(),
            tlc_input_policy=self.tlc_input_policy_var.get(),
        )

        # Invoke callbacks
        for callback in list(self._save_listeners):
            callback(self.options)

        # Persist all settings to INI so they survive application restart.
        self._persist_to_ini()

        # Persist per-model overrides (V8)
        self._save_model_settings()

        logger.info("Global options saved")

    def _persist_to_ini(self) -> None:
        """Write current options to ``CherryAI.ini`` for persistence.

        Called by both Apply/OK and Save-as-Default paths so the
        settings always survive an application restart.
        """
        try:
            from CherryAI.functions import ini_manager

            # API / Request settings → [api] section
            api_vals = {
                "provider": self.options.api.provider,
                "model": self.options.api.model,
                "temperature": str(self.options.api.temperature),
                "cost_cap": str(self.options.api.cost_cap),
                "timeout": str(self.options.request.timeout),
                "retries": str(self.options.request.retries),
                "rate_limit_requests": str(self.options.request.rate_limit),
                "chunk_size": str(self.options.request.chunk_size),
                "max_input_tokens": str(self.options.request.max_input_tokens),
                "thinking_enabled": str(self.options.request.thinking_enabled).lower(),
                "thinking_budget": str(self.options.request.thinking_budget),
                "rolling_context_lines": str(self.options.request.rolling_context_lines),
                "rolling_context_between": str(self.options.request.rolling_context_between),
                "rolling_context_after": str(self.options.request.rolling_context_after),
                "use_translated_context": str(
                    self.options.request.use_translated_context
                ).lower(),
                "remove_duplicate_speakers": str(
                    self.options.request.remove_duplicate_speakers
                ).lower(),
                "glossary_filter_mode": self.options.request.glossary_filter_mode,
                "consistency_mode": self.options.request.consistency_mode,
            }
            ini_manager.save_as_user_defaults("api", api_vals)

            # Translation settings → [translation] section
            translation_vals = {
                "overwrite_translation": str(
                    self.options.translation.overwrite_translation
                ).lower(),
                "skip_non_source_language": str(
                    self.options.translation.skip_non_source_language
                ).lower(),
                "retry_strategy": self.options.translation.retry_strategy,
                "request_slicing": self.options.translation.request_slicing,
            }
            ini_manager.save_as_user_defaults("translation", translation_vals)

            # Utility
            utility_vals = {
                "term_translation_mode": self.options.utility.term_translation_mode,
                "term_batch_size": str(self.options.utility.term_batch_size),
                "gender_inference_mode": self.options.utility.gender_inference_mode,
                "gender_script_minimum": str(
                    self.options.utility.gender_script_minimum,
                ),
                "gender_script_maximum": str(
                    self.options.utility.gender_script_maximum,
                ),
                "gender_script_ignore_unknown": str(
                    self.options.utility.gender_script_ignore_unknown,
                ).lower(),
                "gender_script_do_all": str(
                    self.options.utility.gender_script_do_all,
                ).lower(),
                "gender_llm_minimum": str(
                    self.options.utility.gender_llm_minimum,
                ),
                "gender_llm_maximum": str(
                    self.options.utility.gender_llm_maximum,
                ),
                "gender_llm_ignore_unknown": str(
                    self.options.utility.gender_llm_ignore_unknown,
                ).lower(),
                "gender_llm_do_all": str(
                    self.options.utility.gender_llm_do_all,
                ).lower(),
                "speaker_threshold": str(
                    self.options.utility.speaker_threshold,
                ),
            }
            ini_manager.save_as_user_defaults("utility", utility_vals)

            # Save API-related utility settings to API.ini profiles
            from CherryAI.functions import api_config as _api_cfg
            _api_cfg.set_profile_setting(
                "term_translation", "provider",
                self.options.utility.term_api_key_provider,
            )
            _api_cfg.set_profile_setting(
                "term_translation", "key_name",
                self.options.utility.term_api_key_name,
            )
            _api_cfg.set_profile_setting(
                "term_translation", "model",
                self.options.utility.term_model,
            )
            _api_cfg.set_profile_setting(
                "gender_inference", "provider",
                self.options.utility.gender_api_key_provider,
            )
            _api_cfg.set_profile_setting(
                "gender_inference", "key_name",
                self.options.utility.gender_api_key_name,
            )
            _api_cfg.set_profile_setting(
                "gender_inference", "model",
                self.options.utility.gender_model,
            )

            # Caching
            caching_vals = {
                "enabled": str(self.options.caching.enabled).lower(),
                "dir": self.options.caching.dir,
                "age": str(self.options.caching.age),
                "size": str(self.options.caching.size),
                "mode": self.options.caching.mode,
            }
            ini_manager.save_as_user_defaults("caching", caching_vals)

            # Logging
            logging_vals = {
                "level": self.options.logging.level,
                "location": self.options.logging.location,
                "debug": str(self.options.logging.debug).lower(),
                "api_log": str(self.options.logging.api_log).lower(),
                "log_requests": str(self.options.logging.log_requests).lower(),
            }
            ini_manager.save_as_user_defaults("log", logging_vals)

            # Session
            session_vals = {
                "autosave": str(self.options.session.autosave).lower(),
                "interval": str(self.options.session.interval),
                "theme": self.options.session.theme,
                "load_last": str(self.options.session.load_last).lower(),
            }
            ini_manager.save_as_user_defaults("session", session_vals)
            ini_manager.set_restore_on_launch(self.options.session.load_last)

            gui_vals = {
                "design": self.options.gui.design,
                "save_window_dimensions": str(self.options.gui.save_window_dimensions).lower(),
                "launch_maximized": str(self.options.gui.launch_maximized).lower(),
            }
            ini_manager.save_as_user_defaults("ui", gui_vals)
            ini_manager.set_gui_design(self.options.gui.design)
            ini_manager.set_save_window_dimensions(self.options.gui.save_window_dimensions)
            ini_manager.set_launch_maximized(self.options.gui.launch_maximized)

            # Limits
            limit_vals = {
                "banned": self.options.limit.banned,
                "unsafe_abort_enabled": str(self.options.limit.warning_abort_enabled).lower(),
                "unsafe_abort_after": str(self.options.limit.warning_abort_after),
                "warnings": str(self.options.limit.warnings).lower(),
                "output": str(self.options.limit.output),
                "skip_unsafe_requests": str(self.options.limit.skip_unsafe_requests).lower(),
                "safe": str(self.options.limit.safe).lower(),
            }
            ini_manager.save_as_user_defaults("limit", limit_vals)

            # File I/O
            file_io_vals = {
                "encoding": self.options.file_io.encoding,
                "lines": self.options.file_io.lines,
                "preservebom": str(self.options.file_io.preservebom).lower(),
                "backup": str(self.options.file_io.backup).lower(),
            }
            ini_manager.save_as_user_defaults("fileio", file_io_vals)

            # Prompts
            prompts_vals = {
                "term_glossary": self.options.prompts.term_glossary,
                "term_code": self.options.prompts.term_code,
                "gender_inference": self.options.prompts.gender_inference,
                "edit": self.options.prompts.edit,
                "tlc": self.options.prompts.tlc,
                "dialogue": self.options.prompts.dialogue,
                "menu": self.options.prompts.menu,
                "choice": self.options.prompts.choice,
                "unknown": self.options.prompts.unknown,
            }
            ini_manager.save_as_user_defaults("prompts", prompts_vals)

            # Conditional prompts
            from CherryAI.functions.ini_manager import set_conditional_prompt
            set_conditional_prompt("dialogue", self.options.prompts.dialogue)
            set_conditional_prompt("menu", self.options.prompts.menu)
            set_conditional_prompt("choice", self.options.prompts.choice)
            set_conditional_prompt("unknown", self.options.prompts.unknown)

            # Pattern-triggered conditional prompts → [pattern_prompts]
            from CherryAI.functions.ini_manager import (
                PATTERN_PROMPT_NAMES,
                set_pattern_prompt_enabled,
                set_pattern_prompt_text,
                set_merged_request_text,
            )
            for _name in PATTERN_PROMPT_NAMES:
                if _name in self._pattern_prompt_enabled_vars:
                    set_pattern_prompt_enabled(
                        _name, self._pattern_prompt_enabled_vars[_name].get(),
                    )
                if _name in self._pattern_prompt_text_widgets:
                    set_pattern_prompt_text(
                        _name,
                        self._pattern_prompt_text_widgets[_name].get(
                            "1.0", tk.END,
                        ).strip(),
                    )
            for _kind, _widget in self._merged_request_text_widgets.items():
                set_merged_request_text(_kind, _widget.get("1.0", tk.END).strip())

        except Exception as exc:
            logger.warning("Failed to persist settings to INI: %s", exc)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_options(self) -> GlobalOptions:
        """Get the current options (after saving).

        Returns:
            Current GlobalOptions.
        """
        return self.options

    def destroy(self) -> None:
        """Safely destroy the dialog, releasing the grab first.
        
        This override ensures the grab is released even if an error occurs,
        preventing the parent window from becoming unresponsive.
        Also cleans up any global mousewheel bindings to prevent
        "invalid command name" errors after dialog destruction.
        """
        self._clear_root_reference()

        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass

        try:
            self.grab_release()
        except tk.TclError:
            # Grab may already be released or not set
            pass
        
        try:
            super().destroy()
        except tk.TclError:
            # Window may already be destroyed
            pass
        
        logger.debug("GlobalOptionsDialog destroyed")


# =============================================================================
# Helper Dialogs
# =============================================================================


class _PresetPickerDialog(tk.Toplevel):
    """Simple listbox picker for provider presets."""

    def __init__(self, parent: tk.Toplevel, names: List[str]) -> None:
        super().__init__(parent)
        self.title("Add Preset Provider")
        self.geometry("320x250")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: Optional[int] = None

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Select a preset:").pack(anchor="w", pady=(0, 5))

        self._lb = tk.Listbox(frame, height=8)
        for n in names:
            self._lb.insert(tk.END, n)
        self._lb.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=(10, 0))
        ttk.Button(btn_row, text="Add", width=10, command=self._on_ok).pack(
            side=tk.LEFT, padx=5,
        )
        ttk.Button(btn_row, text="Cancel", width=10, command=self.destroy).pack(
            side=tk.LEFT, padx=5,
        )

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window()

    def _on_ok(self) -> None:
        sel = self._lb.curselection()
        if sel:
            self.result = sel[0]
        self.destroy()
