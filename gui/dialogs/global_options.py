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


# =============================================================================
# Enums
# =============================================================================


class OptionSection(Enum):
    """Sections in the global options dialog."""

    API = "api"
    REQUEST = "request"
    CACHING = "caching"
    LOGGING = "logging"
    SESSION = "session"
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
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
]


@dataclass
class RequestSettings:
    """API request settings."""

    timeout: int = 60
    retries: int = 3
    rate_limit: int = 60
    chunk_size: int = 50
    thinking_enabled: bool = False  # Task 43.8
    thinking_budget: int = 10000  # Task 43.8
    rolling_context_lines: int = 3  # Task 43.9
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
            "thinking_enabled": self.thinking_enabled,
            "thinking_budget": self.thinking_budget,
            "rolling_context_lines": self.rolling_context_lines,
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
            thinking_enabled=bool(data.get("thinking_enabled", False)),
            thinking_budget=int(data.get("thinking_budget", 10000)),
            rolling_context_lines=int(data.get("rolling_context_lines", 3)),
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level,
            "location": self.location,
            "debug": self.debug,
            "api_log": self.api_log,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingSettings":
        """Create from dictionary."""
        return cls(
            level=str(data.get("level", "Error")),
            location=str(data.get("location", "log/")),
            debug=bool(data.get("debug", False)),
            api_log=bool(data.get("api_log", True)),
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
class LimitSettings:
    """Safety / output-limit settings (section [limit] in INI)."""

    banned: str = "\u2014, \u2013"  # em-dash, en-dash
    output: int = 4096
    warnings: bool = True   # Enable Content Warning
    safe: bool = True       # Skip Unsafe Requests

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "banned": self.banned,
            "output": self.output,
            "warnings": self.warnings,
            "safe": self.safe,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LimitSettings":
        """Create from dictionary."""
        return cls(
            banned=str(data.get("banned", "\u2014, \u2013")),
            output=int(data.get("output", 4096)),
            warnings=bool(data.get("warnings", True)),
            safe=bool(data.get("safe", True)),
        )

    def get_banned_chars(self) -> List[str]:
        """Return the banned characters as a list (split on comma)."""
        return [c.strip() for c in self.banned.split(",") if c.strip()]


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
class GlobalOptions:
    """Container for all global options."""

    api: APISettings = field(default_factory=APISettings)
    request: RequestSettings = field(default_factory=RequestSettings)
    caching: CachingSettings = field(default_factory=CachingSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    session: SessionSettings = field(default_factory=SessionSettings)
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
            "caching": self.caching.to_dict(),
            "logging": self.logging.to_dict(),
            "session": self.session.to_dict(),
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
            caching=CachingSettings.from_dict(data.get("caching", {})),
            logging=LoggingSettings.from_dict(data.get("logging", {})),
            session=SessionSettings.from_dict(data.get("session", {})),
            limit=LimitSettings.from_dict(limit_data),
            file_io=FileIOSettings.from_dict(data.get("file_io", {})),
            prompts=PromptsSettings.from_dict(data.get("prompts", {})),
            providers=providers,
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
    OptionSection.REQUEST: "Set request timeouts, retries, and rate limiting.",
    OptionSection.CACHING: "Configure request caching to reduce API calls.",
    OptionSection.LOGGING: "Set logging level and debug options.",
    OptionSection.SESSION: "Configure session autosave and UI preferences.",
    OptionSection.LIMIT: "Configure output limits, banned characters, and content safeguards.",
    OptionSection.FILE_IO: "Set default file encoding and format options.",
    OptionSection.PROMPTS: "Configure custom prompts for Edit and TLC steps.",
    OptionSection.SECURITY: "Manage the master password that encrypts stored API keys.",
}


CATEGORY_ORDER: List[Tuple[OptionCategory, List[OptionSection]]] = [
    (OptionCategory.CONNECTION, [OptionSection.API, OptionSection.REQUEST]),
    (OptionCategory.PROCESSING, [OptionSection.CACHING, OptionSection.LIMIT, OptionSection.PROMPTS]),
    (OptionCategory.APPLICATION, [OptionSection.SESSION, OptionSection.LOGGING, OptionSection.FILE_IO, OptionSection.SECURITY]),
]


CATEGORY_NAMES: Dict[OptionCategory, str] = {
    OptionCategory.CONNECTION: "Connection",
    OptionCategory.PROCESSING: "Processing",
    OptionCategory.APPLICATION: "Application",
}

SECTION_NAMES: Dict[OptionSection, str] = {
    OptionSection.API: "API Provider",
    OptionSection.REQUEST: "Request Settings",
    OptionSection.CACHING: "Caching",
    OptionSection.LOGGING: "Logging",
    OptionSection.SESSION: "Session",
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
        self.geometry("750x600")
        self.resizable(True, True)
        self.minsize(650, 500)

        print("DEBUG: GlobalOptionsDialog bare init complete", flush=True)
        
        self.parent = parent
        self.on_save = on_save
        self.options = initial_options or GlobalOptions()

        logger.debug("GlobalOptionsDialog: Starting initialization")
        print("DEBUG: GlobalOptionsDialog: Starting initialization")

        # Track current section for navigation
        self._current_section: Optional[OptionSection] = None
        self._selecting: bool = False  # Guard against recursive selection

        # Initialize variables before building UI
        logger.debug("GlobalOptionsDialog: Initializing variables")
        print("DEBUG: GlobalOptionsDialog: Initializing variables")
        self._init_variables()
        
        print("DEBUG: Variables initialized")
        

        # Build UI
        logger.debug("GlobalOptionsDialog: Building UI")
        print("DEBUG: GlobalOptionsDialog: Building UI")
        self._build_ui()
        
        print("DEBUG: UI built")

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
        print("DEBUG: GlobalOptionsDialog initialized")

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
        self.temperature_var = tk.DoubleVar(value=self.options.api.temperature)

        # Request settings
        self.timeout_var = tk.IntVar(value=self.options.request.timeout)
        self.retries_var = tk.IntVar(value=self.options.request.retries)
        self.rate_limit_var = tk.IntVar(value=self.options.request.rate_limit)
        self.chunk_size_var = tk.IntVar(value=self.options.request.chunk_size)
        self.thinking_enabled_var = tk.BooleanVar(
            value=self.options.request.thinking_enabled,
        )
        self.thinking_budget_var = tk.IntVar(
            value=self.options.request.thinking_budget,
        )
        self.rolling_context_var = tk.IntVar(
            value=self.options.request.rolling_context_lines,
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

        # Session settings
        self.autosave_enabled_var = tk.BooleanVar(value=self.options.session.autosave)
        self.autosave_interval_var = tk.IntVar(value=self.options.session.interval)
        self.theme_var = tk.StringVar(value=self.options.session.theme)
        # Read from [session] section which controls actual startup behavior
        self.restore_on_launch_var = tk.BooleanVar(value=ini_manager.get_restore_on_launch())

        # Limit settings (replaces Safety)
        self.ban_tokens_var = tk.StringVar(value=self.options.limit.banned)
        self.content_warning_var = tk.BooleanVar(value=self.options.limit.warnings)
        self.max_output_tokens_var = tk.IntVar(value=self.options.limit.output)
        self.safe_var = tk.BooleanVar(value=self.options.limit.safe)

        # File I/O settings
        self.encoding_var = tk.StringVar(value=self.options.file_io.encoding)
        self.line_ending_var = tk.StringVar(value=self.options.file_io.lines)
        self.preserve_bom_var = tk.BooleanVar(value=self.options.file_io.preservebom)
        self.backup_originals_var = tk.BooleanVar(value=self.options.file_io.backup)

        # Prompts settings
        self.edit_prompt_var = tk.StringVar(value=self.options.prompts.edit)
        self.tlc_prompt_var = tk.StringVar(value=self.options.prompts.tlc)
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

    def _build_ui(self) -> None:
        """Build the options UI with navigation and content panels."""
        print("DEBUG: _build_ui started")
        # Main container
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Horizontal paned window
        paned = ttk.PanedWindow(main_frame, orient="horizontal")
        paned.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Left side: Navigation tree
        nav_frame = ttk.Frame(paned, width=180)
        print("DEBUG: Building navigation")
        self._build_navigation(nav_frame)
        paned.add(nav_frame, weight=0)

        # Right side: Content area
        self._content_frame = ttk.Frame(paned)
        paned.add(self._content_frame, weight=1)

        # Build all section panels (hidden initially)
        self._section_panels: Dict[OptionSection, ttk.Frame] = {}
        
        print("DEBUG: Building API section")
        self._build_api_section()
        print("DEBUG: Building Request section")
        self._build_request_section()
        print("DEBUG: Building Caching section")
        self._build_caching_section()
        print("DEBUG: Building Logging section")
        self._build_logging_section()
        print("DEBUG: Building Session section")
        self._build_session_section()
        print("DEBUG: Building Limit section")
        self._build_limit_section()
        print("DEBUG: Building File IO section")
        self._build_file_io_section()
        print("DEBUG: Building Prompts section")
        self._build_prompts_section()
        print("DEBUG: Building Security section")
        self._build_security_section()

        # Bottom: Buttons
        print("DEBUG: Building buttons")
        self._build_buttons(main_frame)
        print("DEBUG: _build_ui finished")

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

        # API Key
        key_row = ttk.Frame(provider_frame)
        key_row.pack(fill=tk.X, pady=5)

        ttk.Label(key_row, text="API Key:", width=15).pack(side=tk.LEFT)
        self._api_key_entry = ttk.Entry(key_row, textvariable=self.api_key_var, width=40, show="•")
        self._api_key_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

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

        # Model settings
        model_frame = ttk.LabelFrame(panel, text="Model Settings", padding=10)
        model_frame.pack(fill=tk.X, pady=(0, 10))

        model_row = ttk.Frame(model_frame)
        model_row.pack(fill=tk.X, pady=5)

        ttk.Label(model_row, text="Model:", width=15).pack(side=tk.LEFT)
        self._model_combo = ttk.Combobox(model_row, textvariable=self.model_var, width=30)
        self._model_combo.pack(side=tk.LEFT, padx=5)

        self._refresh_models_btn = ttk.Button(
            model_row,
            text="⟳ Refresh Models",
            command=self._on_refresh_models,
        )
        self._refresh_models_btn.pack(side=tk.LEFT, padx=5)

        self._refresh_models_label = ttk.Label(model_row, text="", foreground="gray")
        self._refresh_models_label.pack(side=tk.LEFT, padx=5)

        self._update_model_list()

        # Temperature
        temp_row = ttk.Frame(model_frame)
        temp_row.pack(fill=tk.X, pady=5)

        ttk.Label(temp_row, text="Temperature:", width=15).pack(side=tk.LEFT)
        temp_scale = ttk.Scale(temp_row, from_=0.0, to=2.0, variable=self.temperature_var, orient=tk.HORIZONTAL, length=200)
        temp_scale.pack(side=tk.LEFT, padx=5)

        self._temp_label = ttk.Label(temp_row, text=f"{self.temperature_var.get():.1f}")
        self._temp_label.pack(side=tk.LEFT, padx=5)
        self.temperature_var.trace_add("write", self._update_temp_label)

        temp_help = ttk.Label(model_frame, text="Lower = more deterministic, Higher = more creative (0.0-2.0)", foreground="gray")
        temp_help.pack(anchor=tk.W, pady=(0, 5))

        # Test connection button
        test_frame = ttk.Frame(panel)
        test_frame.pack(fill=tk.X, pady=10)

        test_btn = ttk.Button(test_frame, text="Test API Connection", command=self._test_connection)
        test_btn.pack(side=tk.LEFT)

        self._test_status_label = ttk.Label(test_frame, text="")
        self._test_status_label.pack(side=tk.LEFT, padx=10)

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

        ttk.Button(key_btns, text="Save Key", width=10, command=self._save_api_key).pack(pady=2)
        ttk.Button(key_btns, text="Load Key", width=10, command=self._load_api_key).pack(pady=2)
        ttk.Button(key_btns, text="Remove", width=10, command=self._remove_api_key).pack(pady=2)

        # Populate from API.ini
        self._refresh_providers_tree()

    def _build_request_section(self) -> None:
        """Build the request settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.REQUEST] = panel

        # Section header
        header = ttk.Label(panel, text="Request Settings", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.REQUEST], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Settings frame
        settings_frame = ttk.LabelFrame(panel, text="Request Parameters", padding=10)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # Chunk size
        chunk_row = ttk.Frame(settings_frame)
        chunk_row.pack(fill=tk.X, pady=5)

        ttk.Label(chunk_row, text="Lines per Request:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(chunk_row, from_=5, to=200, textvariable=self.chunk_size_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(chunk_row, text="(5-200, default: 50)", foreground="gray").pack(side=tk.LEFT, padx=5)

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

        # Rate limit
        rate_row = ttk.Frame(settings_frame)
        rate_row.pack(fill=tk.X, pady=5)

        ttk.Label(rate_row, text="Rate Limit (req/min):", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(rate_row, from_=1, to=1000, textvariable=self.rate_limit_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(rate_row, text="(1-1000, default: 60)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # Thinking Mode (Task 43.8)
        think_frame = ttk.LabelFrame(panel, text="Thinking Mode", padding=10)
        think_frame.pack(fill=tk.X, pady=(0, 10))

        think_check = ttk.Checkbutton(
            think_frame, text="Enable Thinking Mode",
            variable=self.thinking_enabled_var,
        )
        think_check.pack(anchor=tk.W, pady=2)

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

        think_help = ttk.Label(
            think_frame,
            text="Applies extended thinking for Claude and reasoning effort for OpenAI models.",
            foreground="gray",
        )
        think_help.pack(anchor=tk.W, pady=(0, 5))

        # Rolling Context (Task 43.9)
        ctx_frame = ttk.LabelFrame(panel, text="Rolling Context", padding=10)
        ctx_frame.pack(fill=tk.X, pady=(0, 10))

        ctx_row = ttk.Frame(ctx_frame)
        ctx_row.pack(fill=tk.X, pady=5)
        ttk.Label(ctx_row, text="Context Lines:", width=18).pack(side=tk.LEFT)
        ttk.Spinbox(
            ctx_row, from_=0, to=10,
            textvariable=self.rolling_context_var, width=10,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(ctx_row, text="(0-10 preceding lines, default: 3)", foreground="gray").pack(
            side=tk.LEFT, padx=5,
        )

        ctx_help = ttk.Label(
            ctx_frame,
            text="Number of preceding translated lines included for context in each request.",
            foreground="gray",
        )
        ctx_help.pack(anchor=tk.W, pady=(0, 5))

        # Speaker Dedup (Task 51.4)
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

        # Glossary Filter (Task 52.3)
        gloss_frame = ttk.LabelFrame(
            panel, text="Glossary Inclusion", padding=10,
        )
        gloss_frame.pack(fill=tk.X, pady=(0, 10))

        gloss_row = ttk.Frame(gloss_frame)
        gloss_row.pack(fill=tk.X, pady=5)
        ttk.Label(gloss_row, text="Filter Mode:", width=18).pack(side=tk.LEFT)
        ttk.Combobox(
            gloss_row,
            textvariable=self.glossary_filter_var,
            values=["all", "original_only", "original_or_translation"],
            state="readonly",
            width=22,
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            gloss_frame,
            text="Selective: include only glossary entries whose terms appear in the chunk.",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 5))

        # Consistency Mode (Phase 55)
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

        # Theme settings
        theme_frame = ttk.LabelFrame(panel, text="Appearance", padding=10)
        theme_frame.pack(fill=tk.X, pady=(0, 10))

        theme_row = ttk.Frame(theme_frame)
        theme_row.pack(fill=tk.X, pady=5)

        ttk.Label(theme_row, text="Theme:", width=15).pack(side=tk.LEFT)
        theme_combo = ttk.Combobox(
            theme_row,
            textvariable=self.theme_var,
            values=[t.value for t in ThemeMode],
            state="readonly",
            width=15,
        )
        theme_combo.pack(side=tk.LEFT, padx=5)

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

        # Content warning
        warning_check = ttk.Checkbutton(panel, text="Enable content warnings in output", variable=self.content_warning_var)
        warning_check.pack(anchor=tk.W, pady=5)

        # Safe mode
        safe_check = ttk.Checkbutton(panel, text="Skip unsafe requests", variable=self.safe_var)
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
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.PROMPTS] = panel

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

        # Edit prompt frame
        edit_frame = ttk.LabelFrame(panel, text="Edit Step Prompt", padding=10)
        edit_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

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
        tlc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

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
        self._change_pw_btn.pack(side=tk.LEFT)

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
            else:
                self._sec_status_label.configure(
                    text="\u26A0\ufe0f  No master password set. API keys are stored unencrypted.",
                    foreground="#E67E22",
                )
                self._set_pw_btn.configure(state="normal")
                self._change_pw_btn.configure(state="disabled")
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
        """Handle provider selection change."""
        provider = self.provider_var.get()
        if provider in API_PROVIDERS:
            info = API_PROVIDERS[provider]
            self.base_url_var.set(info.get("base_url", ""))
            self._update_model_list()

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
            success, msg = _api_config.test_api_connection(
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
                except Exception:
                    pass

            try:
                self.after(0, _update_ui)
            except Exception:
                pass

        t = threading.Thread(target=_do_test, daemon=True)
        t.start()

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
        """Save the current API key to API.ini with a user-chosen name."""
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

        # Get/set password
        password = self._ensure_password_set()
        if not password:
            return

        if _api_config.set_api_key(provider, api_key, password, key_name.strip()):
            messagebox.showinfo(
                "Saved",
                f"API key '{key_name.strip()}' saved for {provider}.",
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
        """Handle Save as Default button - save current values as user defaults."""
        from CherryAI.functions import ini_manager

        response = messagebox.askyesno(
            "Save as Default",
            "Save current settings as your personal defaults?\n\n"
            "These will be used for new projects and when restoring defaults.",
        )
        if not response:
            return

        try:
            # Collect current values and save as user defaults
            # API settings
            api_defaults = {
                "provider": self.provider_var.get(),
                "model": self.model_var.get(),
                "temperature": str(self.temperature_var.get()),
            }
            ini_manager.save_as_user_defaults("api", api_defaults)

            # Request settings
            request_defaults = {
                "timeout": str(self.timeout_var.get()),
                "retries": str(self.retries_var.get()),
                "rate_limit_requests": str(self.rate_limit_var.get()),
                "chunk_size": str(self.chunk_size_var.get()),
            }
            ini_manager.save_as_user_defaults("api", request_defaults)

            # Caching settings
            caching_defaults = {
                "enabled": "true" if self.cache_enabled_var.get() else "false",
                "dir": self.cache_dir_var.get(),
                "age": str(self.cache_max_age_var.get()),
                "size": str(self.cache_max_size_var.get()),
                "mode": self.cache_mode_var.get(),
            }
            ini_manager.save_as_user_defaults("caching", caching_defaults)

            # Logging settings
            logging_defaults = {
                "level": self.log_level_var.get(),
                "location": self.log_file_var.get(),
                "debug": "true" if self.debug_mode_var.get() else "false",
                "api_log": "true" if self.log_api_calls_var.get() else "false",
            }
            ini_manager.save_as_user_defaults("log", logging_defaults)

            # Session settings
            session_defaults = {
                "autosave": "true" if self.autosave_enabled_var.get() else "false",
                "interval": str(self.autosave_interval_var.get()),
                "theme": self.theme_var.get(),
                "load_last": "true" if self.restore_on_launch_var.get() else "false",
            }
            ini_manager.save_as_user_defaults("session", session_defaults)

            # Also sync load_last to [session] section for startup
            ini_manager.set_restore_on_launch(self.restore_on_launch_var.get())

            # Limit settings
            limit_defaults = {
                "banned": self.ban_tokens_var.get(),
                "warnings": "true" if self.content_warning_var.get() else "false",
                "output": str(self.max_output_tokens_var.get()),
                "safe": "true" if self.safe_var.get() else "false",
            }
            ini_manager.save_as_user_defaults("limit", limit_defaults)

            # File I/O settings
            file_io_defaults = {
                "encoding": self.encoding_var.get(),
                "lines": self.line_ending_var.get(),
                "preservebom": "true" if self.preserve_bom_var.get() else "false",
                "backup": "true" if self.backup_originals_var.get() else "false",
            }
            ini_manager.save_as_user_defaults("fileio", file_io_defaults)

            # Prompts settings
            prompts_defaults = {
                "edit": self._edit_prompt_text.get("1.0", tk.END).strip(),
                "tlc": self._tlc_prompt_text.get("1.0", tk.END).strip(),
                "dialogue": self._dialogue_prompt_text.get("1.0", tk.END).strip(),
                "menu": self._menu_prompt_text.get("1.0", tk.END).strip(),
                "choice": self._choice_prompt_text.get("1.0", tk.END).strip(),
                "unknown": self._unknown_prompt_text.get("1.0", tk.END).strip(),
            }
            ini_manager.save_as_user_defaults("prompts", prompts_defaults)

            messagebox.showinfo("Defaults Saved", "Your settings have been saved as defaults.")
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

        # Session defaults
        self.autosave_enabled_var.set(
            bool(ini_manager.get_initial_default("session", "autosave", True, bool))
        )
        self.autosave_interval_var.set(
            int(ini_manager.get_initial_default("session", "interval", 60, int) or 60)
        )
        self.theme_var.set(
            ini_manager.get_initial_default("session", "theme", "light", str) or "light"
        )
        self.restore_on_launch_var.set(
            bool(ini_manager.get_initial_default("session", "load_last", True, bool))
        )

        # Limit defaults
        self.ban_tokens_var.set(
            ini_manager.get_initial_default("limit", "banned", "\u2014, \u2013", str) or "\u2014, \u2013"
        )
        self.content_warning_var.set(
            bool(ini_manager.get_initial_default("limit", "warnings", True, bool))
        )
        self.max_output_tokens_var.set(
            int(ini_manager.get_initial_default("limit", "output", 4096, int) or 4096)
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

        # Prompts defaults
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
        )

        self.options.request = RequestSettings(
            timeout=self.timeout_var.get(),
            retries=self.retries_var.get(),
            rate_limit=self.rate_limit_var.get(),
            chunk_size=self.chunk_size_var.get(),
            thinking_enabled=self.thinking_enabled_var.get(),
            thinking_budget=self.thinking_budget_var.get(),
            rolling_context_lines=self.rolling_context_var.get(),
            remove_duplicate_speakers=self.remove_dup_speakers_var.get(),
            glossary_filter_mode=self.glossary_filter_var.get(),
            consistency_mode=self.consistency_mode_var.get(),
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
        )

        self.options.session = SessionSettings(
            autosave=self.autosave_enabled_var.get(),
            interval=self.autosave_interval_var.get(),
            theme=self.theme_var.get(),
            load_last=self.restore_on_launch_var.get(),
        )

        self.options.limit = LimitSettings(
            banned=self.ban_tokens_var.get(),
            warnings=self.content_warning_var.get(),
            output=self.max_output_tokens_var.get(),
            safe=self.safe_var.get(),
        )

        self.options.file_io = FileIOSettings(
            encoding=self.encoding_var.get(),
            lines=self.line_ending_var.get(),
            preservebom=self.preserve_bom_var.get(),
            backup=self.backup_originals_var.get(),
        )

        self.options.prompts = PromptsSettings(
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

        # Invoke callback
        if self.on_save:
            self.on_save(self.options)

        # Persist conditional prompts to INI immediately so prompt_builder.py
        # can read them when building the next translation request.
        try:
            from CherryAI.functions.ini_manager import set_conditional_prompt
            set_conditional_prompt("dialogue", self.options.prompts.dialogue)
            set_conditional_prompt("menu", self.options.prompts.menu)
            set_conditional_prompt("choice", self.options.prompts.choice)
            set_conditional_prompt("unknown", self.options.prompts.unknown)
        except Exception as _e:
            logger.warning("Failed to persist conditional prompts to INI: %s", _e)

        logger.info("Global options saved")

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
        """
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
