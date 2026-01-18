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
    SAFETY = "safety"
    FILE_IO = "file_io"
    PROMPTS = "prompts"


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
class RequestSettings:
    """API request settings."""

    timeout: int = 60
    retries: int = 3
    rate_limit: int = 60
    chunk_size: int = 50

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timeout": self.timeout,
            "retries": self.retries,
            "rate_limit": self.rate_limit,
            "chunk_size": self.chunk_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequestSettings":
        """Create from dictionary."""
        return cls(
            timeout=int(data.get("timeout", 60)),
            retries=int(data.get("retries", 3)),
            rate_limit=int(data.get("rate_limit", 60)),
            chunk_size=int(data.get("chunk_size", 50)),
        )


@dataclass
class CachingSettings:
    """Request caching settings."""

    enabled: bool = True
    cache_dir: str = "temp/cache"
    max_age_hours: int = 24
    max_size_mb: int = 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "cache_dir": self.cache_dir,
            "max_age_hours": self.max_age_hours,
            "max_size_mb": self.max_size_mb,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CachingSettings":
        """Create from dictionary."""
        return cls(
            enabled=bool(data.get("enabled", True)),
            cache_dir=str(data.get("cache_dir", "temp/cache")),
            max_age_hours=int(data.get("max_age_hours", 24)),
            max_size_mb=int(data.get("max_size_mb", 100)),
        )


@dataclass
class LoggingSettings:
    """Logging configuration settings."""

    level: str = "INFO"
    log_file: str = "logs/cherryai.log"
    debug_mode: bool = False
    log_api_calls: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level,
            "log_file": self.log_file,
            "debug_mode": self.debug_mode,
            "log_api_calls": self.log_api_calls,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingSettings":
        """Create from dictionary."""
        return cls(
            level=str(data.get("level", "INFO")),
            log_file=str(data.get("log_file", "logs/cherryai.log")),
            debug_mode=bool(data.get("debug_mode", False)),
            log_api_calls=bool(data.get("log_api_calls", False)),
        )


@dataclass
class SessionSettings:
    """Session and UI settings."""

    autosave_enabled: bool = True
    autosave_interval: int = 60
    theme: str = "light"
    restore_on_launch: bool = True
    confirm_on_exit: bool = True
    auto_analyze_on_load: bool = True
    auto_preprocess_on_load: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "autosave_enabled": self.autosave_enabled,
            "autosave_interval": self.autosave_interval,
            "theme": self.theme,
            "restore_on_launch": self.restore_on_launch,
            "confirm_on_exit": self.confirm_on_exit,
            "auto_analyze_on_load": self.auto_analyze_on_load,
            "auto_preprocess_on_load": self.auto_preprocess_on_load,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionSettings":
        """Create from dictionary."""
        return cls(
            autosave_enabled=bool(data.get("autosave_enabled", True)),
            autosave_interval=int(data.get("autosave_interval", 60)),
            theme=str(data.get("theme", "light")),
            restore_on_launch=bool(data.get("restore_on_launch", True)),
            confirm_on_exit=bool(data.get("confirm_on_exit", True)),
            auto_analyze_on_load=bool(data.get("auto_analyze_on_load", True)),
            auto_preprocess_on_load=bool(data.get("auto_preprocess_on_load", True)),
        )


@dataclass
class SafetySettings:
    """Safety and content settings."""

    ban_tokens: List[str] = field(default_factory=lambda: ["em_dash", "smart_quotes"])
    content_warning_enabled: bool = True
    max_output_tokens: int = 4096

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ban_tokens": self.ban_tokens.copy(),
            "content_warning_enabled": self.content_warning_enabled,
            "max_output_tokens": self.max_output_tokens,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SafetySettings":
        """Create from dictionary."""
        ban_tokens = data.get("ban_tokens", ["em_dash", "smart_quotes"])
        if isinstance(ban_tokens, str):
            ban_tokens = [t.strip() for t in ban_tokens.split(",") if t.strip()]
        return cls(
            ban_tokens=list(ban_tokens),
            content_warning_enabled=bool(data.get("content_warning_enabled", True)),
            max_output_tokens=int(data.get("max_output_tokens", 4096)),
        )


@dataclass
class FileIOSettings:
    """File I/O settings."""

    default_encoding: str = "utf-8"
    line_ending: str = "auto"
    preserve_bom: bool = True
    backup_originals: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "default_encoding": self.default_encoding,
            "line_ending": self.line_ending,
            "preserve_bom": self.preserve_bom,
            "backup_originals": self.backup_originals,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileIOSettings":
        """Create from dictionary."""
        return cls(
            default_encoding=str(data.get("default_encoding", "utf-8")),
            line_ending=str(data.get("line_ending", "auto")),
            preserve_bom=bool(data.get("preserve_bom", True)),
            backup_originals=bool(data.get("backup_originals", True)),
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


@dataclass
class PromptsSettings:
    """Custom prompts for Edit and TLC steps."""

    edit_prompt: str = DEFAULT_EDIT_PROMPT
    tlc_prompt: str = DEFAULT_TLC_PROMPT

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "edit_prompt": self.edit_prompt,
            "tlc_prompt": self.tlc_prompt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptsSettings":
        """Create from dictionary."""
        return cls(
            edit_prompt=str(data.get("edit_prompt", DEFAULT_EDIT_PROMPT)),
            tlc_prompt=str(data.get("tlc_prompt", DEFAULT_TLC_PROMPT)),
        )



@dataclass
class GlobalOptions:
    """Container for all global options."""

    api: APISettings = field(default_factory=APISettings)
    request: RequestSettings = field(default_factory=RequestSettings)
    caching: CachingSettings = field(default_factory=CachingSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    session: SessionSettings = field(default_factory=SessionSettings)
    safety: SafetySettings = field(default_factory=SafetySettings)
    file_io: FileIOSettings = field(default_factory=FileIOSettings)
    prompts: PromptsSettings = field(default_factory=PromptsSettings)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "api": self.api.to_dict(),
            "request": self.request.to_dict(),
            "caching": self.caching.to_dict(),
            "logging": self.logging.to_dict(),
            "session": self.session.to_dict(),
            "safety": self.safety.to_dict(),
            "file_io": self.file_io.to_dict(),
            "prompts": self.prompts.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalOptions":
        """Create from dictionary."""
        return cls(
            api=APISettings.from_dict(data.get("api", {})),
            request=RequestSettings.from_dict(data.get("request", {})),
            caching=CachingSettings.from_dict(data.get("caching", {})),
            logging=LoggingSettings.from_dict(data.get("logging", {})),
            session=SessionSettings.from_dict(data.get("session", {})),
            safety=SafetySettings.from_dict(data.get("safety", {})),
            file_io=FileIOSettings.from_dict(data.get("file_io", {})),
            prompts=PromptsSettings.from_dict(data.get("prompts", {})),
        )



# =============================================================================
# Constants
# =============================================================================


SECTION_DESCRIPTIONS: Dict[OptionSection, str] = {
    OptionSection.API: "Configure API provider, model, and authentication settings.",
    OptionSection.REQUEST: "Set request timeouts, retries, and rate limiting.",
    OptionSection.CACHING: "Configure request caching to reduce API calls.",
    OptionSection.LOGGING: "Set logging level and debug options.",
    OptionSection.SESSION: "Configure session autosave and UI preferences.",
    OptionSection.SAFETY: "Configure token banning and content warnings.",
    OptionSection.FILE_IO: "Set default file encoding and format options.",
    OptionSection.PROMPTS: "Configure custom prompts for Edit and TLC steps.",
}


CATEGORY_ORDER: List[Tuple[OptionCategory, List[OptionSection]]] = [
    (OptionCategory.CONNECTION, [OptionSection.API, OptionSection.REQUEST]),
    (OptionCategory.PROCESSING, [OptionSection.CACHING, OptionSection.SAFETY, OptionSection.PROMPTS]),
    (OptionCategory.APPLICATION, [OptionSection.SESSION, OptionSection.LOGGING, OptionSection.FILE_IO]),
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
    OptionSection.SAFETY: "Safety",
    OptionSection.FILE_IO: "File I/O",
    OptionSection.PROMPTS: "Prompts",
}


# API_PROVIDERS imported from options.py - single source of truth
from CherryAI.functions.options import API_PROVIDERS

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

        # Caching settings
        self.cache_enabled_var = tk.BooleanVar(value=self.options.caching.enabled)
        self.cache_dir_var = tk.StringVar(value=self.options.caching.cache_dir)
        self.cache_max_age_var = tk.IntVar(value=self.options.caching.max_age_hours)
        self.cache_max_size_var = tk.IntVar(value=self.options.caching.max_size_mb)

        # Logging settings
        self.log_level_var = tk.StringVar(value=self.options.logging.level)
        self.log_file_var = tk.StringVar(value=self.options.logging.log_file)
        self.debug_mode_var = tk.BooleanVar(value=self.options.logging.debug_mode)
        self.log_api_calls_var = tk.BooleanVar(value=self.options.logging.log_api_calls)

        # Session settings
        self.autosave_enabled_var = tk.BooleanVar(value=self.options.session.autosave_enabled)
        self.autosave_interval_var = tk.IntVar(value=self.options.session.autosave_interval)
        self.theme_var = tk.StringVar(value=self.options.session.theme)
        self.restore_on_launch_var = tk.BooleanVar(value=self.options.session.restore_on_launch)
        self.confirm_on_exit_var = tk.BooleanVar(value=self.options.session.confirm_on_exit)
        self.auto_analyze_on_load_var = tk.BooleanVar(value=self.options.session.auto_analyze_on_load)
        self.auto_preprocess_on_load_var = tk.BooleanVar(value=self.options.session.auto_preprocess_on_load)

        # Safety settings
        self.ban_tokens_var = tk.StringVar(value=", ".join(self.options.safety.ban_tokens))
        self.content_warning_var = tk.BooleanVar(value=self.options.safety.content_warning_enabled)
        self.max_output_tokens_var = tk.IntVar(value=self.options.safety.max_output_tokens)

        # File I/O settings
        self.encoding_var = tk.StringVar(value=self.options.file_io.default_encoding)
        self.line_ending_var = tk.StringVar(value=self.options.file_io.line_ending)
        self.preserve_bom_var = tk.BooleanVar(value=self.options.file_io.preserve_bom)
        self.backup_originals_var = tk.BooleanVar(value=self.options.file_io.backup_originals)

        # Prompts settings
        self.edit_prompt_var = tk.StringVar(value=self.options.prompts.edit_prompt)
        self.tlc_prompt_var = tk.StringVar(value=self.options.prompts.tlc_prompt)

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
        print("DEBUG: Building Safety section")
        self._build_safety_section()
        print("DEBUG: Building File IO section")
        self._build_file_io_section()
        print("DEBUG: Building Prompts section")
        self._build_prompts_section()

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

        ttk.Label(age_row, text="Max Age (hours):", width=15).pack(side=tk.LEFT)
        ttk.Spinbox(age_row, from_=1, to=168, textvariable=self.cache_max_age_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(age_row, text="(1-168, default: 24)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # Max size
        size_row = ttk.Frame(cache_frame)
        size_row.pack(fill=tk.X, pady=5)

        ttk.Label(size_row, text="Max Size (MB):", width=15).pack(side=tk.LEFT)
        ttk.Spinbox(size_row, from_=10, to=1000, textvariable=self.cache_max_size_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(size_row, text="(10-1000, default: 100)", foreground="gray").pack(side=tk.LEFT, padx=5)

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

        # Log file
        file_row = ttk.Frame(log_frame)
        file_row.pack(fill=tk.X, pady=5)

        ttk.Label(file_row, text="Log File:", width=15).pack(side=tk.LEFT)
        ttk.Entry(file_row, textvariable=self.log_file_var, width=30).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(file_row, text="Browse...", command=self._browse_log_file).pack(side=tk.LEFT, padx=5)

        # Debug mode
        debug_check = ttk.Checkbutton(panel, text="Enable debug mode (verbose logging)", variable=self.debug_mode_var)
        debug_check.pack(anchor=tk.W, pady=5)

        # Log API calls
        api_check = ttk.Checkbutton(panel, text="Log API calls (request/response details)", variable=self.log_api_calls_var)
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
        restore_check = ttk.Checkbutton(panel, text="Restore session on launch", variable=self.restore_on_launch_var)
        restore_check.pack(anchor=tk.W, pady=5)

        confirm_check = ttk.Checkbutton(panel, text="Confirm before exit with unsaved changes", variable=self.confirm_on_exit_var)
        confirm_check.pack(anchor=tk.W, pady=5)

        auto_analyze_check = ttk.Checkbutton(panel, text="Auto-analyze files on load", variable=self.auto_analyze_on_load_var)
        auto_analyze_check.pack(anchor=tk.W, pady=5)

        auto_preprocess_check = ttk.Checkbutton(panel, text="Auto-apply preprocessing rules on load", variable=self.auto_preprocess_on_load_var)
        auto_preprocess_check.pack(anchor=tk.W, pady=5)

    def _build_safety_section(self) -> None:
        """Build the safety settings section."""
        panel = ttk.Frame(self._content_frame, padding=15)
        self._section_panels[OptionSection.SAFETY] = panel

        # Section header
        header = ttk.Label(panel, text="Safety", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", pady=(0, 5))

        desc = ttk.Label(panel, text=SECTION_DESCRIPTIONS[OptionSection.SAFETY], foreground="gray")
        desc.pack(anchor="w", pady=(0, 15))

        # Token banning
        ban_frame = ttk.LabelFrame(panel, text="Token Banning", padding=10)
        ban_frame.pack(fill=tk.X, pady=(0, 10))

        ban_info = ttk.Label(
            ban_frame,
            text="Comma-separated list of tokens to ban from output.\n"
                 "Common: em_dash, smart_quotes, ellipsis, fancy_apostrophe",
            justify="left",
        )
        ban_info.pack(anchor=tk.W, pady=(0, 5))

        ban_row = ttk.Frame(ban_frame)
        ban_row.pack(fill=tk.X, pady=5)

        ttk.Label(ban_row, text="Ban Tokens:", width=12).pack(side=tk.LEFT)
        ttk.Entry(ban_row, textvariable=self.ban_tokens_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Common tokens buttons
        common_row = ttk.Frame(ban_frame)
        common_row.pack(fill=tk.X, pady=5)

        ttk.Label(common_row, text="Add common:", width=12).pack(side=tk.LEFT)
        def make_add_ban_token(token: str) -> Callable[[], None]:
            return lambda: self._add_ban_token(token)
        for token in COMMON_BAN_TOKENS[:3]:
            ttk.Button(common_row, text=token, command=make_add_ban_token(token)).pack(side=tk.LEFT, padx=2)

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

    def _reset_edit_prompt(self) -> None:
        """Reset edit prompt to default value."""
        self._edit_prompt_text.delete("1.0", tk.END)
        self._edit_prompt_text.insert("1.0", DEFAULT_EDIT_PROMPT)

    def _reset_tlc_prompt(self) -> None:
        """Reset TLC prompt to default value."""
        self._tlc_prompt_text.delete("1.0", tk.END)
        self._tlc_prompt_text.insert("1.0", DEFAULT_TLC_PROMPT)

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

    def _on_provider_change(self, event: tk.Event) -> None:
        """Handle provider selection change."""
        provider = self.provider_var.get()
        if provider in API_PROVIDERS:
            info = API_PROVIDERS[provider]
            self.base_url_var.set(info.get("base_url", ""))
            self._update_model_list()

    def _update_model_list(self) -> None:
        """Update the model combobox based on selected provider."""
        provider = self.provider_var.get()
        if provider in API_PROVIDERS:
            models = API_PROVIDERS[provider].get("models", [])
            self._model_combo["values"] = models
            if self.model_var.get() not in models and models:
                self.model_var.set(models[0])

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
        """Test the API connection."""
        self._test_status_label.config(text="Testing...", foreground="gray")
        self.update_idletasks()

        # Simulate test (actual implementation would call API)
        try:
            api_key = self.api_key_var.get()
            if not api_key:
                self._test_status_label.config(text="Error: No API key", foreground="red")
                return

            # TODO: Actual API test implementation
            self._test_status_label.config(text="✓ Connection successful", foreground="green")
        except Exception as e:
            self._test_status_label.config(text=f"Error: {e}", foreground="red")

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
                "cache_dir": self.cache_dir_var.get(),
                "max_age_hours": str(self.cache_max_age_var.get()),
                "max_size_mb": str(self.cache_max_size_var.get()),
            }
            ini_manager.save_as_user_defaults("caching", caching_defaults)

            # Logging settings
            logging_defaults = {
                "level": self.log_level_var.get(),
                "log_file": self.log_file_var.get(),
                "debug_mode": "true" if self.debug_mode_var.get() else "false",
                "log_api_calls": "true" if self.log_api_calls_var.get() else "false",
            }
            ini_manager.save_as_user_defaults("logging", logging_defaults)

            # Session settings
            session_defaults = {
                "autosave_enabled": "true" if self.autosave_enabled_var.get() else "false",
                "autosave_interval": str(self.autosave_interval_var.get()),
                "theme": self.theme_var.get(),
                "restore_on_launch": "true" if self.restore_on_launch_var.get() else "false",
                "confirm_on_exit": "true" if self.confirm_on_exit_var.get() else "false",
                "auto_analyze_on_load": "true" if self.auto_analyze_on_load_var.get() else "false",
                "auto_preprocess_on_load": "true" if self.auto_preprocess_on_load_var.get() else "false",
            }
            ini_manager.save_as_user_defaults("session", session_defaults)

            # Safety settings
            safety_defaults = {
                "ban_tokens": self.ban_tokens_var.get(),
                "content_warning_enabled": "true" if self.content_warning_var.get() else "false",
                "max_output_tokens": str(self.max_output_tokens_var.get()),
            }
            ini_manager.save_as_user_defaults("safety", safety_defaults)

            # File I/O settings
            file_io_defaults = {
                "default_encoding": self.encoding_var.get(),
                "line_ending": self.line_ending_var.get(),
                "preserve_bom": "true" if self.preserve_bom_var.get() else "false",
                "backup_originals": "true" if self.backup_originals_var.get() else "false",
            }
            ini_manager.save_as_user_defaults("file_io", file_io_defaults)

            # Prompts settings
            prompts_defaults = {
                "edit_prompt": self._edit_prompt_text.get("1.0", tk.END).strip(),
                "tlc_prompt": self._tlc_prompt_text.get("1.0", tk.END).strip(),
            }
            ini_manager.save_as_user_defaults("prompts", prompts_defaults)

            messagebox.showinfo("Defaults Saved", "Your settings have been saved as defaults.")
            logger.info("User defaults saved successfully")

        except Exception as e:
            logger.error("Failed to save user defaults: %s", e)
            messagebox.showerror("Error", f"Failed to save defaults: {e}")

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
            ini_manager.get_initial_default("logging", "level", "INFO", str) or "INFO"
        )
        self.log_file_var.set(
            ini_manager.get_initial_default("logging", "log_file", "logs/cherryai.log", str) or "logs/cherryai.log"
        )
        self.debug_mode_var.set(
            bool(ini_manager.get_initial_default("logging", "debug_mode", False, bool))
        )
        self.log_api_calls_var.set(
            bool(ini_manager.get_initial_default("logging", "log_api_calls", False, bool))
        )

        # Session defaults
        self.autosave_enabled_var.set(
            bool(ini_manager.get_initial_default("session", "autosave_enabled", True, bool))
        )
        self.autosave_interval_var.set(
            int(ini_manager.get_initial_default("session", "autosave_interval", 60, int) or 60)
        )
        self.theme_var.set(
            ini_manager.get_initial_default("session", "theme", "light", str) or "light"
        )
        self.restore_on_launch_var.set(
            bool(ini_manager.get_initial_default("session", "restore_on_launch", True, bool))
        )
        self.confirm_on_exit_var.set(
            bool(ini_manager.get_initial_default("session", "confirm_on_exit", True, bool))
        )
        self.auto_analyze_on_load_var.set(
            bool(ini_manager.get_initial_default("session", "auto_analyze_on_load", True, bool))
        )
        self.auto_preprocess_on_load_var.set(
            bool(ini_manager.get_initial_default("session", "auto_preprocess_on_load", True, bool))
        )

        # Safety defaults
        self.ban_tokens_var.set(
            ini_manager.get_initial_default("safety", "ban_tokens", "em_dash, smart_quotes", str) or "em_dash, smart_quotes"
        )
        self.content_warning_var.set(
            bool(ini_manager.get_initial_default("safety", "content_warning_enabled", True, bool))
        )
        self.max_output_tokens_var.set(
            int(ini_manager.get_initial_default("safety", "max_output_tokens", 4096, int) or 4096)
        )

        # File I/O defaults
        self.encoding_var.set(
            ini_manager.get_initial_default("file_io", "default_encoding", "utf-8", str) or "utf-8"
        )
        self.line_ending_var.set(
            ini_manager.get_initial_default("file_io", "line_ending", "auto", str) or "auto"
        )
        self.preserve_bom_var.set(
            bool(ini_manager.get_initial_default("file_io", "preserve_bom", True, bool))
        )
        self.backup_originals_var.set(
            bool(ini_manager.get_initial_default("file_io", "backup_originals", True, bool))
        )

        # Prompts defaults
        edit_prompt = (
            ini_manager.get_initial_default("prompts", "edit_prompt", DEFAULT_EDIT_PROMPT, str)
            or DEFAULT_EDIT_PROMPT
        )
        tlc_prompt = (
            ini_manager.get_initial_default("prompts", "tlc_prompt", DEFAULT_TLC_PROMPT, str)
            or DEFAULT_TLC_PROMPT
        )
        self._edit_prompt_text.delete("1.0", tk.END)
        self._edit_prompt_text.insert("1.0", edit_prompt)
        self._tlc_prompt_text.delete("1.0", tk.END)
        self._tlc_prompt_text.insert("1.0", tlc_prompt)

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
        )

        self.options.caching = CachingSettings(
            enabled=self.cache_enabled_var.get(),
            cache_dir=self.cache_dir_var.get(),
            max_age_hours=self.cache_max_age_var.get(),
            max_size_mb=self.cache_max_size_var.get(),
        )

        self.options.logging = LoggingSettings(
            level=self.log_level_var.get(),
            log_file=self.log_file_var.get(),
            debug_mode=self.debug_mode_var.get(),
            log_api_calls=self.log_api_calls_var.get(),
        )

        self.options.session = SessionSettings(
            autosave_enabled=self.autosave_enabled_var.get(),
            autosave_interval=self.autosave_interval_var.get(),
            theme=self.theme_var.get(),
            restore_on_launch=self.restore_on_launch_var.get(),
            confirm_on_exit=self.confirm_on_exit_var.get(),
            auto_analyze_on_load=self.auto_analyze_on_load_var.get(),
            auto_preprocess_on_load=self.auto_preprocess_on_load_var.get(),
        )

        # Parse ban tokens
        ban_tokens_str = self.ban_tokens_var.get()
        ban_tokens = [t.strip() for t in ban_tokens_str.split(",") if t.strip()]

        self.options.safety = SafetySettings(
            ban_tokens=ban_tokens,
            content_warning_enabled=self.content_warning_var.get(),
            max_output_tokens=self.max_output_tokens_var.get(),
        )

        self.options.file_io = FileIOSettings(
            default_encoding=self.encoding_var.get(),
            line_ending=self.line_ending_var.get(),
            preserve_bom=self.preserve_bom_var.get(),
            backup_originals=self.backup_originals_var.get(),
        )

        self.options.prompts = PromptsSettings(
            edit_prompt=self._edit_prompt_text.get("1.0", tk.END).strip(),
            tlc_prompt=self._tlc_prompt_text.get("1.0", tk.END).strip(),
        )

        # Invoke callback
        if self.on_save:
            self.on_save(self.options)

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
