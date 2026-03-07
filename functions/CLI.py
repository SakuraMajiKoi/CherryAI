"""CLI implementation for CherryAI.

Handles 'estimate', 'translate', 'test', 'config', 'sample', 'glossary', and 'help' commands.
Supports both direct argument mode and interactive multi-step selection.
"""
import sys
import logging
import time
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Callable, TypedDict, Union, Literal, TYPE_CHECKING, cast

# Import core modules (package-relative only)
from .mainhelper import (
    Processor, Manifest, Operation, setup_logger,
    read_json_pairs, write_json_pairs,
    derive_output_path, now_iso
)
from .cli_io import (
    read_text_via_handler, write_text_via_handler,
    read_table_via_handler, write_table_via_handler,
    get_supported_extensions, is_supported_format,
    detect_delimiter_from_extension,
)
from .config import (
    load_config, save_config, get_api_config, set_api_config,
    get_api_presets, list_preset_names, DEFAULT_CONFIG
)
from .glossary import (
    read_unified_glossary, write_unified_glossary, 
    update_unified_glossary, GlossaryEntry,
    _unified_glossary_path, TYPE_NAME, TYPE_TERM
)
from CherryAI.formats import SIMPLE_FORMATS as FORMAT_EXTENSIONS

if TYPE_CHECKING:
    from .mainhelper import Processor  # type: ignore


class Task(TypedDict):
    path: Path
    proc: "Processor"
    prep: Dict[str, Any]
    mode: Literal["txt", "table", "json"]
    extra: Optional[Union[Tuple[List[List[str]], str], List[Tuple[str, str]]]]
    all_lines: List[str]
    limit: Optional[int]

# Supported extensions
SUPPORTED_EXTENSIONS = {".txt", ".csv", ".tsv", ".json", ".xlsx"}


# =============================================================================
# CLI PROGRESS DISPLAY
# =============================================================================


class CLIProgressDisplay:
    """Provides progress display for CLI translation operations.
    
    Features:
    - Progress bar with percentage and counts
    - Current batch/file indicator
    - ETA calculation based on average batch time
    - Graceful fallback for non-TTY environments
    """
    
    BAR_WIDTH = 30  # Width of the progress bar
    
    def __init__(
        self,
        total_files: int = 1,
        show_eta: bool = True,
        enable_progress: bool = True,
    ):
        """Initialize progress display.
        
        Args:
            total_files: Total number of files to translate.
            show_eta: Whether to show estimated time remaining.
            enable_progress: Whether to show progress (disable for non-TTY).
        """
        self.total_files = total_files
        self.current_file = 0
        self.current_file_name = ""
        self.show_eta = show_eta
        self.enable_progress = enable_progress
        
        # Timing for ETA calculation
        self.start_time: Optional[float] = None
        self.batch_times: List[float] = []
        self.last_batch_time: Optional[float] = None
        
        # Current progress state
        self.current_batch = 0
        self.total_batches = 0
        self.current_phase = ""
        
        # Check if we're in a TTY environment
        self.is_tty = sys.stdout.isatty()
        if not self.is_tty:
            self.enable_progress = False
    
    def start_file(self, file_name: str, file_num: int, total_batches: int) -> None:
        """Start processing a new file.
        
        Args:
            file_name: Name of the file being translated.
            file_num: Current file number (1-indexed).
            total_batches: Total batches in this file.
        """
        self.current_file = file_num
        self.current_file_name = file_name
        self.total_batches = total_batches
        self.current_batch = 0
        self.start_time = time.time()
        self.batch_times = []
        self.last_batch_time = time.time()
        
        if self.enable_progress:
            # Print file header
            file_indicator = f"[{file_num}/{self.total_files}]" if self.total_files > 1 else ""
            print(f"\n  {file_indicator} {file_name}")
    
    def update(self, phase: str, current: int, total: int, label: str) -> None:
        """Update progress display.
        
        This is called as the progress_callback from Processor.
        
        Args:
            phase: Current phase ("Pre", "Translating", "Post", etc.)
            current: Current item number.
            total: Total items.
            label: Additional label text.
        """
        if not self.enable_progress:
            return
        
        self.current_phase = phase
        now = time.time()
        
        # Track batch timing for translation phase
        if phase == "Translating" and self.last_batch_time:
            batch_duration = now - self.last_batch_time
            if batch_duration > 0.1:  # Only track meaningful durations
                self.batch_times.append(batch_duration)
            self.last_batch_time = now
        
        self.current_batch = current
        
        # Calculate progress
        if total > 0:
            percent = (current / total) * 100
            filled = int(self.BAR_WIDTH * current / total)
            empty = self.BAR_WIDTH - filled
        else:
            percent = 0
            filled = 0
            empty = self.BAR_WIDTH
        
        # Build progress bar
        bar = "█" * filled + "░" * empty
        
        # Calculate ETA
        eta_str = ""
        if self.show_eta and phase == "Translating" and len(self.batch_times) >= 2:
            avg_batch_time = sum(self.batch_times) / len(self.batch_times)
            remaining_batches = total - current
            eta_seconds = avg_batch_time * remaining_batches
            if eta_seconds < 60:
                eta_str = f" ETA: {int(eta_seconds)}s"
            elif eta_seconds < 3600:
                eta_str = f" ETA: {int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
            else:
                eta_str = f" ETA: {int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m"
        
        # Format output line
        progress_line = f"\r    [{bar}] {percent:5.1f}% ({current}/{total}) {phase}: {label}{eta_str}"
        
        # Print with carriage return for in-place update
        print(progress_line, end="", flush=True)
        
        # Print newline when complete
        if current >= total and total > 0:
            print()
    
    def end_file(self, success: bool, stats: Optional[Dict[str, Any]] = None) -> None:
        """Mark file processing as complete.
        
        Args:
            success: Whether the file was translated successfully.
            stats: Optional translation statistics.
        """
        if not self.enable_progress:
            return
        
        if success:
            elapsed = time.time() - self.start_time if self.start_time else 0
            elapsed_str = f"{elapsed:.1f}s" if elapsed < 60 else f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
            
            # Show summary stats if available
            if stats:
                token_info = ""
                if "total_tokens" in stats:
                    token_info = f" ({stats.get('total_tokens', 0)} tokens)"
                print(f"    ✓ Complete in {elapsed_str}{token_info}")
            else:
                print(f"    ✓ Complete in {elapsed_str}")
        else:
            print("    ✗ Failed")
    
    def print_summary(
        self,
        success_count: int,
        total_count: int,
        total_tokens: int = 0,
        total_cost: float = 0.0,
    ) -> None:
        """Print final summary of all translations.
        
        Args:
            success_count: Number of successfully translated files.
            total_count: Total number of files attempted.
            total_tokens: Total tokens used across all files.
            total_cost: Total estimated cost in USD.
        """
        print(f"""
  ─────────────────────────────────────
  Translation Summary
  ─────────────────────────────────────
  Files:  {success_count}/{total_count} successful""")
        
        if total_tokens > 0:
            print(f"  Tokens: {total_tokens:,}")
        
        if total_cost > 0:
            print(f"  Cost:   ${total_cost:.4f} USD (estimated)")
        
        print("  ─────────────────────────────────────")


def create_progress_callback(display: CLIProgressDisplay) -> Callable[[str, int, int, str], None]:
    """Create a progress callback function for Processor.
    
    Args:
        display: CLIProgressDisplay instance.
        
    Returns:
        Callback function compatible with Processor.progress_callback.
    """
    def callback(phase: str, current: int, total: int, label: str) -> None:
        display.update(phase, current, total, label)
    return callback


# =============================================================================
# LANGUAGE CONFIGURATION
# =============================================================================

# Import from languages.py - single source of truth
from .languages import (
    LANGUAGES,
    get_language_dict,
    build_language_aliases,
    normalize_language_code,
    get_language_name_from_code as get_language_name,
    is_valid_language,
)



# =============================================================================
# API PROVIDERS AND MODELS
# =============================================================================

# Import from options.py - single source of truth
from .options import (
    API_PROVIDERS,
    get_api_urls,
    get_all_provider_models,
    get_provider_models,
    get_provider_names,
)



# =============================================================================
# IO FORMAT CONFIGURATION
# =============================================================================

# Format descriptions for CLI display - derived from formats module
# The actual format validation uses FORMAT_EXTENSIONS from formats module
SIMPLE_FORMAT_DESCRIPTIONS: Dict[str, str] = {
    "txt": "Plain text (one line per line)",
    "csv": "Comma-separated values (column A = text)",
    "tsv": "Tab-separated values (column A = text)",
    "json": "JSON (array of strings or original/translated pairs)",
    "xlsx": "Excel (column A = text, column B = original)",
}

# Advanced formats (placeholder - not yet implemented)
ADVANCED_FORMATS: Dict[str, str] = {
    "rpgmaker_mv": "RPG Maker MV data files (planned)",
    "rpgmaker_mz": "RPG Maker MZ data files (planned)",
    "pdf": "PDF documents (planned)",
    "epub": "EPUB e-books (planned)",
}

# IO configuration options
IO_OPTIONS: Dict[str, Dict[str, Any]] = {
    "extract": {
        "section": "io",
        "key": "extract_format",
        "description": "Format for reading/extracting text from files",
        "type": "format",
        "known_values": SIMPLE_FORMAT_DESCRIPTIONS,
        "default": "txt",
    },
    "inject": {
        "section": "io",
        "key": "inject_format",
        "description": "Format for writing/injecting translated text",
        "type": "format",
        "known_values": SIMPLE_FORMAT_DESCRIPTIONS,
        "default": "txt",
    },
    "preserve_original": {
        "section": "io",
        "key": "preserve_original",
        "description": "Include original lines in output (for pair formats)",
        "type": "bool",
        "known_values": {"true": "Yes", "false": "No"},
        "default": "false",
    },
}

# Configurable options with their types and validators
CONFIG_OPTIONS: Dict[str, Dict[str, Any]] = {
    "api_url": {
        "section": "api",
        "key": "base_url",
        "description": "API base URL (e.g., OpenAI, Gemini, local)",
        "type": "url",
        "known_values": get_api_urls(),
    },
    "api_key": {
        "section": "api",
        "key": "api_key",
        "description": "API key for authentication",
        "type": "secret",
        "known_values": None,
    },
    "model": {
        "section": "api",
        "key": "model",
        "description": "Model to use for translation",
        "type": "string",
        "known_values": None,  # Dynamic based on provider
    },
    "temperature": {
        "section": "api",
        "key": "temperature",
        "description": "Temperature for generation (0.0-2.0)",
        "type": "float",
        "known_values": None,
        "validator": lambda x: 0.0 <= float(x) <= 2.0,
    },
    "chunk_size": {
        "section": "api",
        "key": "chunk_size",
        "description": "Lines per translation chunk (10-200)",
        "type": "int",
        "known_values": None,
        "validator": lambda x: 10 <= int(x) <= 200,
    },
    "timeout": {
        "section": "api",
        "key": "timeout",
        "description": "API timeout in seconds (10-600)",
        "type": "int",
        "known_values": None,
        "validator": lambda x: 10 <= int(x) <= 600,
    },
    "source_lang": {
        "section": "api",
        "key": "source_lang",
        "description": "Default source language for translation",
        "type": "language",
        "known_values": get_language_dict(),
    },
    "target_lang": {
        "section": "api",
        "key": "target_lang",
        "description": "Default target language for translation",
        "type": "language",
        "known_values": get_language_dict(),
    },
    "preset": {
        "section": "api_presets",
        "key": None,  # Special handling
        "description": "Apply a saved API preset",
        "type": "preset",
        "known_values": None,  # Dynamic
    },
}


# normalize_language_code and get_language_name are now imported from languages.py


# =============================================================================
# API OVERRIDE HELPERS
# =============================================================================

def _apply_api_overrides(overrides: Dict[str, Any]) -> None:
    """Apply API configuration overrides from CLI arguments.
    
    Validates and applies overrides to the current API configuration.
    Preset is applied first, then individual settings override preset values.
    
    Args:
        overrides: Dictionary with optional keys:
            - preset: Apply a preset before other overrides
            - model: Override model name
            - temperature: Override temperature (0.0-2.0)
            - timeout: Override timeout in seconds
            - chunk_size: Override lines per API request
    """
    if not overrides:
        return
    
    # Apply preset first if specified
    preset_name = overrides.get("preset")
    if preset_name:
        from .config import get_preset_config, get_api_config, set_api_config
        preset = get_preset_config(preset_name)
        if preset:
            current = get_api_config()
            current.update(preset)
            set_api_config(current)
            print(f"Applied preset: {preset_name}")
        else:
            available = list_preset_names()
            print(f"Warning: Unknown preset '{preset_name}'. Available: {', '.join(available)}")
    
    # Apply individual overrides
    settings_to_apply = {}
    
    if "model" in overrides and overrides["model"]:
        settings_to_apply["model"] = overrides["model"]
        print(f"Model override: {overrides['model']}")
    
    if "temperature" in overrides and overrides["temperature"] is not None:
        temp = overrides["temperature"]
        if 0.0 <= temp <= 2.0:
            settings_to_apply["temperature"] = temp
            print(f"Temperature override: {temp}")
        else:
            print(f"Warning: Temperature {temp} out of range (0.0-2.0), ignoring")
    
    if "timeout" in overrides and overrides["timeout"] is not None:
        timeout = overrides["timeout"]
        if 10 <= timeout <= 600:
            settings_to_apply["timeout"] = timeout
            print(f"Timeout override: {timeout}s")
        else:
            print(f"Warning: Timeout {timeout} out of range (10-600), ignoring")
    
    if "chunk_size" in overrides and overrides["chunk_size"] is not None:
        chunk = overrides["chunk_size"]
        if 10 <= chunk <= 200:
            settings_to_apply["chunk_size"] = chunk
            print(f"Chunk size override: {chunk} lines")
        else:
            print(f"Warning: Chunk size {chunk} out of range (10-200), ignoring")
    
    # Logit bias settings
    if "banned_tokens" in overrides and overrides["banned_tokens"]:
        settings_to_apply["banned_tokens"] = overrides["banned_tokens"]
        settings_to_apply["logit_bias_enabled"] = True
        print(f"Token banning enabled: {overrides['banned_tokens']}")
    
    if "logit_bias_preset" in overrides and overrides["logit_bias_preset"]:
        settings_to_apply["logit_bias_preset"] = overrides["logit_bias_preset"]
        settings_to_apply["logit_bias_enabled"] = True
        print(f"Logit bias preset: {overrides['logit_bias_preset']}")
    
    # Retry strategy settings
    if "retry_strategy" in overrides and overrides["retry_strategy"]:
        settings_to_apply["retry_strategy"] = overrides["retry_strategy"]
        print(f"Retry strategy: {overrides['retry_strategy']}")
    
    # Cache settings
    if overrides.get("use_cache"):
        settings_to_apply["cache_enabled"] = True
        print("Request caching enabled")
    
    if "cache_mode" in overrides and overrides["cache_mode"]:
        settings_to_apply["cache_mode"] = overrides["cache_mode"]
        print(f"Cache mode: {overrides['cache_mode']}")
    
    if overrides.get("clear_cache"):
        settings_to_apply["clear_cache"] = True
        print("Cache will be cleared before starting")
    
    # Style preset settings
    if "style_preset" in overrides and overrides["style_preset"]:
        settings_to_apply["style_preset"] = overrides["style_preset"]
        print(f"Style preset: {overrides['style_preset']}")
    
    # Rate limit settings
    if overrides.get("rate_limit_enabled"):
        settings_to_apply["rate_limit_enabled"] = True
        print("Rate limiting enabled")
    
    if "max_concurrent" in overrides and overrides["max_concurrent"] is not None:
        settings_to_apply["max_concurrent"] = overrides["max_concurrent"]
        print(f"Max concurrent requests: {overrides['max_concurrent']}")
    
    if "rate_limit_margin" in overrides and overrides["rate_limit_margin"] is not None:
        settings_to_apply["rate_limit_margin"] = overrides["rate_limit_margin"]
        print(f"Rate limit safety margin: {overrides['rate_limit_margin']}")
    
    # Local LLM settings
    if overrides.get("no_api_key"):
        settings_to_apply["no_api_key"] = True
        print("API key validation disabled (local LLM mode)")
    
    if overrides.get("check_local"):
        # Perform local server health check
        try:
            from .local_llm import check_server_health, get_local_error_help, is_local_url
            from .config import get_api_config
            
            config = get_api_config()
            api_url = config.get("api_url", "")
            
            if is_local_url(api_url):
                print(f"Checking local server health at {api_url}...")
                info = check_server_health(api_url)
                if info.is_healthy:
                    print(f"✅ Local server is healthy ({info.response_time_ms:.0f}ms)")
                    if info.models:
                        print(f"   Available models: {', '.join(info.models[:3])}")
                else:
                    print(f"⚠️  Local server check failed: {info.error_message}")
                    print("   Translation may fail. Start your local LLM server first.")
            else:
                print(f"Note: --check-local only applies to local URLs, skipping for {api_url}")
        except ImportError:
            print("Warning: Could not import local_llm module for health check")
    
    if settings_to_apply:
        from .config import set_api_config
        set_api_config(settings_to_apply)


def validate_api_overrides(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout: Optional[int] = None,
    chunk_size: Optional[int] = None,
    preset: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """Validate API override parameters.
    
    Args:
        model: Model name (any string allowed)
        temperature: Temperature value (0.0-2.0)
        timeout: Timeout in seconds (10-600)
        chunk_size: Lines per request (10-200)
        preset: Preset name
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors: List[str] = []
    
    if temperature is not None:
        if not (0.0 <= temperature <= 2.0):
            errors.append(f"Temperature must be between 0.0 and 2.0, got {temperature}")
    
    if timeout is not None:
        if not (10 <= timeout <= 600):
            errors.append(f"Timeout must be between 10 and 600 seconds, got {timeout}")
    
    if chunk_size is not None:
        if not (10 <= chunk_size <= 200):
            errors.append(f"Chunk size must be between 10 and 200, got {chunk_size}")
    
    if preset is not None:
        available = list_preset_names()
        if preset not in available:
            errors.append(f"Unknown preset '{preset}'. Available: {', '.join(available)}")
    
    return (len(errors) == 0, errors)


# =============================================================================
# INTERACTIVE CLI HELPERS
# =============================================================================

def _print_header(title: str) -> None:
    """Print a formatted section header."""
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def _print_languages_table() -> None:
    """Print a formatted table of supported languages."""
    print("\n  Supported Languages:")
    print("  " + "-" * 56)
    print(f"  {'Code':<8} {'Name':<20} {'Native':<15}")
    print("  " + "-" * 56)
    for code, info in get_language_dict().items():
        print(f"  {code:<8} {info['name']:<20} {info['native']:<15}")
    print("  " + "-" * 56)


def _select_language(prompt: str, default: Optional[str] = None) -> str:
    """Interactive language selection with validation.
    
    Args:
        prompt: The prompt to display.
        default: Default language code if user presses Enter.
        
    Returns:
        Validated language code.
    """
    _print_languages_table()
    
    default_display = f" [{default}]" if default else ""
    
    while True:
        user_input = input(f"\n  {prompt}{default_display}: ").strip()
        
        if not user_input and default:
            normalized = normalize_language_code(default)
            if normalized:
                print(f"  → Using default: {get_language_name(normalized)}")
                return normalized
        
        if user_input:
            normalized = normalize_language_code(user_input)
            if normalized:
                print(f"  → Selected: {get_language_name(normalized)}")
                return normalized
            else:
                print(f"  ✗ Unknown language: '{user_input}'. Please try again.")
                print("    Hint: Use codes like 'ja', 'en', 'de' or names like 'Japanese', 'German'")


def _select_file_interactive() -> Optional[Path]:
    """Interactive file selection."""
    print("\n  Enter the path to a file or directory to translate.")
    print("  Supported formats: .txt, .csv, .tsv, .json, .xlsx")
    print("  Tip: You can drag and drop a file here.\n")
    
    while True:
        path_input = input("  File or folder path: ").strip().strip('"').strip("'")
        
        if not path_input:
            print("  ✗ No path provided. Please enter a valid path.")
            continue
            
        p = Path(path_input)
        if not p.exists():
            print(f"  ✗ Path not found: {path_input}")
            retry = input("  Try again? [Y/n]: ").strip().lower()
            if retry in ("n", "no"):
                return None
            continue
            
        return p


def _get_current_config() -> Tuple[str, str]:
    """Get current source and target language from config."""
    config = load_config()
    api_section = config.get("api", {})
    source = api_section.get("source_lang", "Japanese")
    target = api_section.get("target_lang", "English")
    return source, target


def _update_config_languages(source: str, target: str) -> None:
    """Update the configuration with new language settings."""
    config = load_config()
    if "api" not in config:
        config["api"] = {}
    config["api"]["source_lang"] = get_language_name(source)
    config["api"]["target_lang"] = get_language_name(target)
    save_config(config)


def run_interactive_cli() -> int:
    """Run the full interactive CLI workflow.
    
    Guides user through:
    1. File selection
    2. Language selection (source and target)
    3. Cost estimation
    4. Translation confirmation
    5. Output
    
    Returns:
        Exit code (0 = success, 1 = failure/abort).
    """
    _print_header("CherryAI Interactive Translation")
    
    print("\n  Welcome to CherryAI Interactive Mode!")
    print("  This wizard will guide you through the translation process.\n")
    
    # Step 1: File Selection
    _print_header("Step 1: Select Input File")
    
    file_path = _select_file_interactive()
    if not file_path:
        print("\n  Aborted: No file selected.")
        return 1
    
    files = _get_files(str(file_path))
    if not files:
        print("\n  ✗ No supported files found at the specified path.")
        return 1
    
    print(f"\n  ✓ Found {len(files)} file(s) to process:")
    for f in files[:5]:  # Show first 5
        print(f"    • {f.name}")
    if len(files) > 5:
        print(f"    ... and {len(files) - 5} more")
    
    # Step 2: Language Selection
    _print_header("Step 2: Select Languages")
    
    current_source, current_target = _get_current_config()
    print(f"\n  Current settings: {current_source} → {current_target}")
    
    change_langs = input("\n  Change language settings? [y/N]: ").strip().lower()
    
    if change_langs in ("y", "yes"):
        source_lang = _select_language("Source language (text is written in)", "ja")
        target_lang = _select_language("Target language (translate to)", "en")
        
        # Validate not same
        if source_lang == target_lang:
            print("\n  ⚠ Warning: Source and target languages are the same!")
            proceed = input("  Continue anyway? [y/N]: ").strip().lower()
            if proceed not in ("y", "yes"):
                return 1
        
        # Save to config
        _update_config_languages(source_lang, target_lang)
        print(f"\n  ✓ Languages set: {get_language_name(source_lang)} → {get_language_name(target_lang)}")
    else:
        # Use existing
        source_lang = normalize_language_code(current_source) or "ja"
        target_lang = normalize_language_code(current_target) or "en"
        print(f"\n  ✓ Using existing: {get_language_name(source_lang)} → {get_language_name(target_lang)}")
    
    # Step 3: Estimation
    _print_header("Step 3: Cost Estimation")
    
    print("\n  Calculating translation cost...")
    
    total_input = 0
    total_output = 0
    total_cost = 0.0
    tasks: List[Task] = []
    
    for i, fp in enumerate(files, 1):
        try:
            text = ""
            mode: Literal["txt", "table", "json"] = "txt"
            extra_data: Optional[Union[Tuple[List[List[str]], str], List[Tuple[str, str]]]] = None
            
            if fp.suffix == ".txt":
                text = read_text_via_handler(fp)
            elif fp.suffix in (".csv", ".tsv"):
                rows, delim = read_table_via_handler(fp)
                text = "\n".join(row[0] for row in rows if row)
                mode = "table"
                extra_data = (rows, delim)
            elif fp.suffix == ".json":
                pairs = read_json_pairs(fp)
                text = "\n".join(t for _, t in pairs)
                mode = "json"
                extra_data = pairs
            else:
                continue
            
            manifest = Manifest(
                summary=str(fp),
                operations=[],
                metadata={"created": now_iso()}
            )
            proc = Processor([], manifest)
            prep = proc.prepare_auto_translate(text)
            est = prep["estimation"]
            
            tasks.append({
                "path": fp,
                "proc": proc,
                "prep": prep,
                "mode": mode,
                "extra": extra_data,
                "all_lines": text.splitlines(),
                "limit": None,
            })
            
            total_input += est["input_tokens"]
            total_output += est["output_tokens"]
            total_cost += est["cost_usd"]
            
            print(f"  [{i}/{len(files)}] {fp.name}: ~{est['input_tokens']:,} tokens")
            
        except Exception as e:
            print(f"  [{i}/{len(files)}] {fp.name}: Error - {e}")
    
    if not tasks:
        print("\n  ✗ No valid files to translate.")
        return 1
    
    # Step 4: Confirmation
    _print_header("Step 4: Confirm Translation")
    
    print(f"""
  Summary:
  ─────────────────────────────────────
  Files to translate:  {len(tasks)}
  Source language:     {get_language_name(source_lang)}
  Target language:     {get_language_name(target_lang)}
  ─────────────────────────────────────
  Estimated tokens:    {total_input:,} → {total_output:,}
  Estimated cost:      ${total_cost:.4f} USD
  ─────────────────────────────────────
""")
    
    confirm = input("  Proceed with translation? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("\n  Aborted by user.")
        return 0
    
    # Step 5: Translation
    _print_header("Step 5: Translating")
    
    # Initialize progress display
    progress_display = CLIProgressDisplay(
        total_files=len(tasks),
        show_eta=True,
        enable_progress=True,
    )
    
    success_count = 0
    total_tokens_used = 0
    
    for i, task in enumerate(tasks, 1):
        fp = task["path"]
        proc = task["proc"]
        batches = task["prep"]["batches"]
        
        # Start file in progress display
        progress_display.start_file(fp.name, i, len(batches))
        
        # Set progress callback on processor
        proc.progress_callback = create_progress_callback(progress_display)
        
        try:
            final_text, stats = proc.execute_auto_translate(batches)
            
            out_path = derive_output_path(fp, suffix="_translated")
            
            if task["mode"] == "txt":
                write_text_via_handler(out_path, final_text)
            elif task["mode"] == "table":
                rows, delim = cast(Tuple[List[List[str]], str], task["extra"])
                translated_lines = final_text.splitlines()
                t_idx = 0
                for r in rows:
                    if r:
                        if t_idx < len(translated_lines):
                            r[0] = translated_lines[t_idx]
                            t_idx += 1
                write_table_via_handler(out_path, rows, delim)
            elif task["mode"] == "json":
                pairs = cast(List[Tuple[str, str]], task["extra"])
                translated_lines = final_text.splitlines()
                new_pairs = []
                for j, (k, _) in enumerate(pairs):
                    val = translated_lines[j] if j < len(translated_lines) else ""
                    new_pairs.append((k, val))
                write_json_pairs(out_path, new_pairs)
            
            # Track stats and display completion
            progress_display.end_file(True, stats)
            print(f"      Saved to: {out_path.name}")
            success_count += 1
            
            # Track token usage if available
            if stats and "total_tokens" in stats:
                total_tokens_used += stats.get("total_tokens", 0)
            
        except Exception as e:
            progress_display.end_file(False)
            print(f"      Error: {e}")
            logging.exception(f"CLI Translation failed for {fp}")
    
    # Final Summary
    _print_header("Complete")
    
    progress_display.print_summary(
        success_count=success_count,
        total_count=len(tasks),
        total_tokens=total_tokens_used,
        total_cost=total_cost,
    )
    
    return 0 if success_count == len(tasks) else 1


def _get_files(path_str: str) -> List[Path]:
    """Recursively find supported files in the given path."""
    p = Path(path_str)
    if not p.exists():
        print(f"Error: Path not found: {path_str}")
        return []
    
    files = []
    if p.is_file():
        if p.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(p)
    elif p.is_dir():
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(p.rglob(f"*{ext}"))
    
    return sorted(list(set(files)))


def _apply_partial_translation(
    lines: List[str],
    translated_lines: List[str],
    translate_limit: int,
    skip_marker: str = "[UNTRANSLATED]"
) -> Tuple[List[str], int, int]:
    """Apply partial translation results to original lines.
    
    Args:
        lines: Original lines (all of them).
        translated_lines: Translated lines (only first N).
        translate_limit: Number of lines that were translated.
        skip_marker: Marker to append to untranslated lines.
        
    Returns:
        Tuple of (final_lines, translated_count, skipped_count).
    """
    final_lines: List[str] = []
    translated_count = 0
    skipped_count = 0
    
    for i, original in enumerate(lines):
        if i < len(translated_lines):
            # This line was translated
            final_lines.append(translated_lines[i])
            translated_count += 1
        else:
            # This line was skipped - keep original with marker
            if skip_marker and original.strip():
                final_lines.append(f"{original} {skip_marker}")
            else:
                final_lines.append(original)
            skipped_count += 1
    
    return final_lines, translated_count, skipped_count


def get_partial_translation_config() -> Dict[str, Any]:
    """Get partial translation settings from config.
    
    Returns:
        Dictionary with enabled, max_lines, and skip_marker.
    """
    config = load_config()
    pt_section = config.get("partial_translation", {})
    return {
        "enabled": str(pt_section.get("enabled", "false")).lower() == "true",
        "max_lines": int(pt_section.get("max_lines", 200)),
        "skip_marker": pt_section.get("skip_marker", "[UNTRANSLATED]"),
    }


def _confirm_cli(estimation: Dict[str, Any]) -> bool:
    """CLI confirmation callback."""
    print("\n--- Cost Estimation ---")
    print(f"Input Tokens: {estimation['input_tokens']:,}")
    print(f"Est. Output Tokens: {estimation['output_tokens']:,}")
    print(f"Estimated Cost: ${estimation['cost_usd']:.4f}")
    print("-----------------------")
    
    while True:
        response = input("Proceed with translation? [y/N]: ").strip().lower()
        if response in ("y", "yes"):
            return True
        if response in ("n", "no", ""):
            return False

def run_estimate_cli(path_str: str) -> int:
    """Run estimation for files in path."""
    files = _get_files(path_str)
    if not files:
        print("No supported files found.")
        return 1

    print(f"Found {len(files)} files to estimate.")
    
    total_input = 0
    total_output = 0
    total_cost = 0.0

    for i, file_path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] Analyzing {file_path.name}...")
        try:
            # Load content using format handlers
            text = ""
            if file_path.suffix == ".txt":
                text = read_text_via_handler(file_path)
            elif file_path.suffix in (".csv", ".tsv"):
                rows, _ = read_table_via_handler(file_path)
                text = "\n".join(row[0] for row in rows if row)
            elif file_path.suffix == ".json":
                pairs = read_json_pairs(file_path)
                text = "\n".join(t for _, t in pairs)
            else:
                print(f"  Skipping {file_path.name} (format not fully supported in CLI estimate yet)")
                continue

            # Create dummy processor (no operations for pure estimation of raw text)
            # If we want to estimate *after* pre-processing, we should run pre-processing.
            # But we don't have operations defined in CLI. 
            # We'll assume raw text estimation.
            manifest = Manifest(summary=str(file_path), operations=[], metadata={})
            proc = Processor([], manifest)
            
            res = proc.prepare_auto_translate(text)
            est = res["estimation"]
            
            print(f"  Tokens: {est['input_tokens']} -> {est['output_tokens']} | Cost: ${est['cost_usd']:.4f}")
            
            total_input += est['input_tokens']
            total_output += est['output_tokens']
            total_cost += est['cost_usd']

        except Exception as e:
            print(f"  Error estimating {file_path.name}: {e}")

    print("\n=== Total Estimation ===")
    print(f"Files: {len(files)}")
    print(f"Total Input Tokens: {total_input:,}")
    print(f"Total Output Tokens: {total_output:,}")
    print(f"Total Estimated Cost: ${total_cost:.4f}")
    return 0


def run_translate_cli(
    path_str: str,
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None,
    translate_lines: Optional[int] = None,
    api_overrides: Optional[Dict[str, Any]] = None,
    line_by_line: bool = False,
    context_lines: int = 1,
    thinking: bool = False,
    thinking_budget: int = 10000,
    skip_confirmation: bool = False,
) -> int:
    """Run 1-Click translation for files in path.
    
    Args:
        path_str: Path to file or directory.
        source_lang: Source language code (e.g., 'ja', 'en'). If None, uses config.
        target_lang: Target language code (e.g., 'en', 'de'). If None, uses config.
        translate_lines: Maximum number of lines to translate. If None, translates all.
                        If set, only first N lines are sent to API, rest are marked skipped.
        api_overrides: Dictionary of API settings to override (model, temperature, 
                      timeout, chunk_size, preset).
        line_by_line: If True, translate each line individually with minimal prompt.
        context_lines: For line-by-line mode, number of adjacent lines to include as context (0-3).
        thinking: If True, enable extended thinking mode for compatible models.
        thinking_budget: Token budget for thinking mode (default: 10000).
        skip_confirmation: If True, skip the confirmation prompt (for -y flag).
        
    Returns:
        Exit code (0 = success, 1 = failure).
    """
    files = _get_files(path_str)
    if not files:
        print("No supported files found.")
        return 1

    print(f"Found {len(files)} files to translate.")
    
    # Apply API overrides if provided
    if api_overrides:
        _apply_api_overrides(api_overrides)
    
    # Show line-by-line mode status
    if line_by_line:
        print(f"Line-by-line mode: Translating each line individually (context: {context_lines} lines)")
    
    # Show thinking mode status
    if thinking:
        print(f"Thinking mode: Enabled (budget: {thinking_budget} tokens)")
    
    # Show partial translation mode status
    if translate_lines is not None:
        print(f"Partial translation mode: Only first {translate_lines} lines will be translated.")
    
    # Handle language settings
    if source_lang or target_lang:
        # Validate and normalize
        if source_lang:
            normalized_src = normalize_language_code(source_lang)
            if not normalized_src:
                print(f"Error: Unknown source language '{source_lang}'")
                print("Use --list-languages to see supported languages.")
                return 1
            source_lang = normalized_src
        
        if target_lang:
            normalized_tgt = normalize_language_code(target_lang)
            if not normalized_tgt:
                print(f"Error: Unknown target language '{target_lang}'")
                print("Use --list-languages to see supported languages.")
                return 1
            target_lang = normalized_tgt
        
        # Update config with provided languages
        if source_lang and target_lang:
            _update_config_languages(source_lang, target_lang)
            print(f"Language: {get_language_name(source_lang)} → {get_language_name(target_lang)}")
    else:
        # Show current language settings
        current_src, current_tgt = _get_current_config()
        print(f"Language: {current_src} → {current_tgt} (from config)")
    
    # Determine effective line limit for partial translation
    effective_limit: Optional[int] = translate_lines
    if effective_limit is None:
        pt_config = get_partial_translation_config()
        if pt_config["enabled"]:
            effective_limit = pt_config["max_lines"]
            print(f"Using partial translation config: max {effective_limit} lines")
    
    print("Calculating total estimation...")
    # Reuse estimate logic or just do it here. 
    # To be safe and accurate, we should probably do it per file during the loop 
    # OR do a pre-pass. A pre-pass is safer for costs.
    
    # ... (Implementation of pre-pass similar to run_estimate_cli but storing results) ...
    # For brevity and responsiveness, let's process one by one or ask for global confirmation.
    # Let's do global confirmation.
    
    tasks: List[Task] = []
    total_cost = 0.0
    
    for file_path in files:
        try:
            # Read content using format handlers
            text = ""
            mode: Literal["txt", "table", "json"] = "txt"
            extra_data: Optional[Union[Tuple[List[List[str]], str], List[Tuple[str, str]]]] = None
            all_lines: List[str] = []  # Store original lines for partial mode
            
            if file_path.suffix == ".txt":
                text = read_text_via_handler(file_path)
            elif file_path.suffix in (".csv", ".tsv"):
                rows, delim = read_table_via_handler(file_path)
                text = "\n".join(row[0] for row in rows if row)
                mode = "table"
                extra_data = (rows, delim)
            elif file_path.suffix == ".json":
                pairs = read_json_pairs(file_path)
                text = "\n".join(t for _, t in pairs)
                mode = "json"
                extra_data = pairs
            else:
                print(f"Skipping {file_path.name} (unsupported format)")
                continue

            # Apply partial translation limit if set
            all_lines = text.splitlines()
            text_for_translate = text
            if effective_limit is not None and len(all_lines) > effective_limit:
                text_for_translate = "\n".join(all_lines[:effective_limit])
                print(f"  {file_path.name}: {len(all_lines)} lines, "
                      f"translating first {effective_limit}")

            # Setup Processor
            # Note: CLI uses default operations (empty) + standard helpers default
            manifest = Manifest(
                summary=str(file_path), 
                operations=[], 
                metadata={"created": now_iso()}
            )
            # Enable standard helpers by default for CLI?
            # manifest.mappings["standard_mode_config"] = {"dedup_enabled": True, ...}
            # Let's stick to defaults defined in Processor/StandardMode
            
            proc = Processor([], manifest)
            prep = proc.prepare_auto_translate(text_for_translate)
            
            tasks.append({
                "path": file_path,
                "proc": proc,
                "prep": prep,
                "mode": mode,
                "extra": extra_data,
                "all_lines": all_lines,
                "limit": effective_limit,
            })
            
            total_cost += prep["estimation"]["cost_usd"]
            
        except Exception as e:
            print(f"Error preparing {file_path.name}: {e}")

    if not tasks:
        print("No valid tasks prepared.")
        return 1

    print(f"\nPrepared {len(tasks)} files.")
    print(f"Total Estimated Cost: ${total_cost:.4f}")
    
    if not skip_confirmation and not _confirm_cli({"input_tokens": 0, "output_tokens": 0, "cost_usd": total_cost}):
        print("Aborted.")
        return 0

    print("\nStarting Translation...")
    success_count = 0
    pt_config = get_partial_translation_config()
    skip_marker = pt_config.get("skip_marker", "[UNTRANSLATED]")
    
    # Enable API logging for integration testing
    enable_api_log = True
    from pathlib import Path
    api_log_path = Path(__file__).parent.parent / "logs" / "api_log.txt"
    # Clear existing log file
    api_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(api_log_path, "w", encoding="utf-8") as f:
        f.write(f"API Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"File: {files[0].name if files else 'N/A'}\n")
        f.write("=" * 80 + "\n")
    
    for i, task in enumerate(tasks, 1):
        file_path = task["path"]
        print(f"[{i}/{len(tasks)}] Translating {file_path.name}...")
        
        try:
            proc = task["proc"]
            batches = task["prep"]["batches"]
            all_lines = task["all_lines"]
            limit = task["limit"]
            
            # Execute translation with API logging
            if line_by_line:
                # Use line-by-line translation mode
                try:
                    from .api_client import APIClient
                except ImportError:
                    from CherryAI.functions.api_client import APIClient
                
                client = APIClient(
                    enable_api_log=enable_api_log,
                    api_log_path=str(api_log_path),
                )
                
                # Apply thinking mode settings
                if thinking:
                    client.config.thinking_enabled = True
                    client.config.thinking_budget = thinking_budget
                
                # Get lines to translate (respecting limit)
                lines_to_translate = all_lines[:limit] if limit is not None else all_lines
                
                # Progress callback for line-by-line
                def line_progress(current: int, total: int) -> None:
                    if current % 10 == 0 or current == total:
                        print(f"  Line {current}/{total}...")
                
                translated_lines = client.translate_line_by_line(
                    lines_to_translate,
                    context_lines=context_lines,
                    minimal_prompt=True,
                    progress_callback=line_progress,
                )
                final_text = "\n".join(translated_lines)
                stats: Dict[str, Any] = {}  # Line-by-line doesn't return detailed stats yet
            else:
                # Use standard batch translation
                # Pass thinking mode config through api_overrides if enabled
                thinking_config: Dict[str, Any] = {}
                if thinking:
                    thinking_config["thinking_enabled"] = True
                    thinking_config["thinking_budget"] = thinking_budget
                
                final_text, stats = proc.execute_auto_translate(
                    batches,
                    enable_api_log=enable_api_log,
                    api_log_path=str(api_log_path),
                )
            
            # Apply partial translation merge if limit was active
            if limit is not None and len(all_lines) > limit:
                translated_lines = final_text.splitlines()
                merged_lines, trans_count, skip_count = _apply_partial_translation(
                    all_lines, translated_lines, limit, skip_marker
                )
                final_text = "\n".join(merged_lines)
                print(f"  Partial mode: {trans_count} translated, {skip_count} skipped")
            
            # Save Output using format handlers
            out_path = derive_output_path(file_path, suffix="_translated")
            
            if task["mode"] == "txt":
                write_text_via_handler(out_path, final_text)
            elif task["mode"] == "table":
                rows, delim = cast(Tuple[List[List[str]], str], task["extra"])
                # Split final text back to rows
                translated_lines = final_text.splitlines()
                # Re-inject
                # This is tricky if line counts mismatch due to some error, 
                # but execute_auto_translate tries to maintain parity.
                # We need to map back to non-empty rows.
                t_idx = 0
                for r in rows:
                    if r:
                        if t_idx < len(translated_lines):
                            r[0] = translated_lines[t_idx]
                            t_idx += 1
                write_table_via_handler(out_path, rows, delim)
            elif task["mode"] == "json":
                pairs = cast(List[Tuple[str, str]], task["extra"])
                translated_lines = final_text.splitlines()
                new_pairs = []
                for j, (k, _) in enumerate(pairs):
                    val = translated_lines[j] if j < len(translated_lines) else ""
                    new_pairs.append((k, val))
                write_json_pairs(out_path, new_pairs)

            print(f"  -> Saved to {out_path.name}")
            success_count += 1
            
        except Exception as e:
            print(f"  Failed to translate {file_path.name}: {e}")
            logging.exception(f"CLI Translation failed for {file_path}")

            print(f"  -> Saved to {out_path.name}")
            success_count += 1
            
        except Exception as e:
            print(f"  Failed to translate {file_path.name}: {e}")
            logging.exception(f"CLI Translation failed for {file_path}")

    print(f"\nCompleted. {success_count}/{len(tasks)} files translated successfully.")
    return 0


def run_test_cli(skip_api: bool = False) -> int:
    """Run the one-click test suite.

    Args:
        skip_api: If True, skip actual API calls.

    Returns:
        Exit code (0 = all passed, 1 = some failed).
    """
    try:
        from .One_Click_Test import run_one_click_test
    except ImportError:
        from CherryAI.functions.One_Click_Test import run_one_click_test

    report = run_one_click_test(skip_api=skip_api, verbose=True)

    # Print summary
    print("\n" + report.get_summary())

    # Return exit code based on results
    if report.all_passed():
        return 0
    return 1


def run_list_languages_cli() -> int:
    """Print all supported languages.
    
    Returns:
        Exit code (always 0).
    """
    _print_header("Supported Languages")
    
    print("\n  CherryAI supports the following languages for translation:\n")
    
    for code, info in get_language_dict().items():
        print(f"  {code:<8}  {info['name']:<25}  {info['native']}")
        print(f"           {info['description']}")
        print()
    
    print("  Usage Examples:")
    print("  ─────────────────────────────────────────────────────")
    print("  python CherryAI.py translate file.txt --source ja --target en")
    print("  python CherryAI.py translate file.txt -s japanese -t german")
    print("  python CherryAI.py translate file.txt --source jp --target de")
    print()
    
    return 0


def run_config_cli(option: Optional[str] = None, value: Optional[str] = None) -> int:
    """Handle configuration commands.
    
    Usage patterns:
    - config                      -> Show all configurable options
    - config api_url              -> Show known API URLs with numbers to select
    - config api_url 1            -> Select option 1 from known URLs
    - config api_url https://...  -> Set custom URL
    
    Args:
        option: Configuration option name (e.g., 'api_url', 'model', 'api_key')
        value: Value to set (number for selection or direct value)
        
    Returns:
        Exit code (0 = success, 1 = failure).
    """
    if option is None:
        # Show all configurable options
        return _show_config_options()
    
    option_lower = option.lower()
    
    if option_lower not in CONFIG_OPTIONS:
        print(f"  ✗ Unknown configuration option: '{option}'")
        print(f"  Use 'config' to see available options.")
        return 1
    
    opt_info = CONFIG_OPTIONS[option_lower]
    
    if value is None:
        # Show current value and available options
        return _show_config_option_details(option_lower, opt_info)
    
    # Set the value
    return _set_config_value(option_lower, opt_info, value)


def _show_config_options() -> int:
    """Display all available configuration options."""
    _print_header("Configuration Options")
    
    config = load_config()
    api_section = config.get("api", {})
    
    print("\n  Available options for 'config <option> [value]':\n")
    print("  " + "-" * 60)
    print(f"  {'Option':<15} {'Current Value':<25} {'Description'}")
    print("  " + "-" * 60)
    
    for opt_name, opt_info in CONFIG_OPTIONS.items():
        if opt_info["key"]:
            current = api_section.get(opt_info["key"], "Not set")
            # Mask API key
            if opt_info["type"] == "secret" and current and current != "Not set":
                current = current[:4] + "..." + current[-4:] if len(current) > 8 else "****"
        else:
            current = "(action)"
        
        desc = opt_info["description"][:30] + "..." if len(opt_info["description"]) > 30 else opt_info["description"]
        print(f"  {opt_name:<15} {str(current):<25} {desc}")
    
    print("  " + "-" * 60)
    print("\n  Usage:")
    print("    config <option>           Show details and available values")
    print("    config <option> <value>   Set value (number or direct input)")
    print("\n  Examples:")
    print("    config api_url            Show known API URLs")
    print("    config api_url 2          Select the 2nd known URL")
    print("    config api_url https://my.api.com/v1")
    print("    config api_key sk-abc123...")
    print("    config model gpt-4o")
    print()
    
    return 0


def _show_config_option_details(option: str, opt_info: Dict[str, Any]) -> int:
    """Show details for a specific configuration option."""
    _print_header(f"Configuration: {option}")
    
    config = load_config()
    section = config.get(opt_info["section"], {})
    
    # Get current value
    if opt_info["key"]:
        current = section.get(opt_info["key"], "Not set")
        if opt_info["type"] == "secret" and current and current != "Not set":
            display_current = current[:4] + "..." + current[-4:] if len(current) > 8 else "****"
        else:
            display_current = current
    else:
        display_current = "(action)"
    
    print(f"\n  {opt_info['description']}")
    print(f"\n  Current value: {display_current}")
    
    # Show known values if available
    known = opt_info.get("known_values")
    if known:
        print("\n  Known options:")
        print("  " + "-" * 50)
        
        if isinstance(known, dict):
            items = list(known.items())
            for i, (name, val) in enumerate(items, 1):
                if opt_info["type"] == "language":
                    print(f"  [{i}] {name:<10} {val.get('name', val)}")
                else:
                    print(f"  [{i}] {name:<15} {val}")
        
        print("  " + "-" * 50)
        print(f"\n  Usage: config {option} <number> or config {option} <custom_value>")
    
    # Special handling for presets
    if option == "preset":
        presets = list_preset_names()
        if presets:
            print("\n  Available presets:")
            print("  " + "-" * 50)
            for i, name in enumerate(presets, 1):
                print(f"  [{i}] {name}")
            print("  " + "-" * 50)
    
    # Show models for current provider
    if option == "model":
        base_url = section.get("base_url", "")
        provider = _detect_provider_from_url(base_url)
        if provider and provider in get_all_provider_models():
            print(f"\n  Known models for {provider}:")
            print("  " + "-" * 50)
            for i, model in enumerate(get_all_provider_models()[provider], 1):
                marker = " ←" if model == current else ""
                print(f"  [{i}] {model}{marker}")
            print("  " + "-" * 50)
    
    print()
    return 0


def _detect_provider_from_url(url: str) -> Optional[str]:
    """Detect provider from base URL."""
    url_lower = url.lower()
    if "openai.com" in url_lower:
        return "openai"
    if "generativelanguage.googleapis.com" in url_lower:
        return "gemini"
    if "anthropic.com" in url_lower:
        return "anthropic"
    if "localhost" in url_lower:
        return "local"
    return None


def _set_config_value(option: str, opt_info: Dict[str, Any], value: str) -> int:
    """Set a configuration value with validation."""
    config = load_config()
    
    # Handle numeric selection from known values
    known = opt_info.get("known_values")
    if known and value.isdigit():
        idx = int(value) - 1
        if isinstance(known, dict):
            items = list(known.items())
            if 0 <= idx < len(items):
                name, actual_value = items[idx]
                if opt_info["type"] == "language":
                    value = known[name].get("name", name)
                else:
                    value = actual_value
            else:
                print(f"  ✗ Invalid selection: {value}. Choose 1-{len(items)}.")
                return 1
    
    # Handle preset selection
    if option == "preset":
        presets = list_preset_names()
        if value.isdigit():
            idx = int(value) - 1
            if 0 <= idx < len(presets):
                value = presets[idx]
            else:
                print(f"  ✗ Invalid selection: {value}. Choose 1-{len(presets)}.")
                return 1
        # Apply preset
        preset_config = get_api_presets().get(value)
        if not preset_config:
            print(f"  ✗ Unknown preset: '{value}'")
            return 1
        # Merge preset into API config
        api = config.get("api", {})
        for k, v in preset_config.items():
            api[k] = v
        config["api"] = api
        save_config(config)
        print(f"  ✓ Applied preset '{value}'")
        print(f"    Model: {preset_config.get('model', 'unchanged')}")
        print(f"    URL: {preset_config.get('base_url', 'unchanged')}")
        return 0
    
    # Handle model selection by number
    if option == "model" and value.isdigit():
        base_url = config.get("api", {}).get("base_url", "")
        provider = _detect_provider_from_url(base_url)
        if provider and provider in get_all_provider_models():
            idx = int(value) - 1
            models = get_all_provider_models()[provider]
            if 0 <= idx < len(models):
                value = models[idx]
            else:
                print(f"  ✗ Invalid selection: {value}. Choose 1-{len(models)}.")
                return 1
    
    # Validate value based on type
    validation_error = _validate_config_value(option, opt_info, value)
    if validation_error:
        print(f"  ✗ Validation failed: {validation_error}")
        return 1
    
    # Convert value to appropriate type
    converted_value: object = value
    if opt_info["type"] == "int":
        converted_value = int(value)
    elif opt_info["type"] == "float":
        converted_value = float(value)
    
    # Update config
    section_name = opt_info["section"]
    key = opt_info["key"]
    
    if section_name not in config:
        config[section_name] = {}
    config[section_name][key] = converted_value
    
    save_config(config)
    
    # Display confirmation
    display_val = converted_value
    if opt_info["type"] == "secret":
        sv = str(converted_value)
        display_val = sv[:4] + "..." + sv[-4:] if len(sv) > 8 else "****"
    
    print(f"  ✓ Set {option} = {display_val}")
    return 0


def _validate_config_value(option: str, opt_info: Dict[str, Any], value: str) -> Optional[str]:
    """Validate a configuration value. Returns error message or None if valid."""
    val_type = opt_info["type"]
    
    if val_type == "url":
        if not value.startswith(("http://", "https://")):
            return "URL must start with http:// or https://"
    
    elif val_type == "int":
        try:
            int(value)
        except ValueError:
            return f"Must be an integer"
    
    elif val_type == "float":
        try:
            float(value)
        except ValueError:
            return f"Must be a number"
    
    elif val_type == "language":
        if not normalize_language_code(value):
            return f"Unknown language: '{value}'. Use 'languages' command to see valid codes."
    
    # Run custom validator if present
    validator = opt_info.get("validator")
    if validator:
        try:
            if not validator(value):
                return f"Value out of allowed range"
        except Exception:
            return f"Invalid value format"
    
    return None


# =============================================================================
# IO CONFIGURATION COMMAND
# =============================================================================

def run_io_cli(
    option: Optional[str] = None,
    value: Optional[str] = None,
    value2: Optional[str] = None
) -> int:
    """Handle IO format configuration commands.
    
    Usage patterns:
    - io                          -> Show current IO settings
    - io extract                  -> Show extract format options
    - io inject                   -> Show inject format options
    - io extract txt              -> Set extract format to txt
    - io inject json              -> Set inject format to json
    - io standard txt json        -> Set extract=txt, inject=json
    - io preserve_original true   -> Enable preserving original lines
    
    Args:
        option: IO option (extract, inject, standard, preserve_original)
        value: Format or value to set
        value2: Second format (for 'standard' command)
        
    Returns:
        Exit code (0 = success, 1 = failure).
    """
    if option is None:
        # Show current IO settings
        return _show_io_settings()
    
    option_lower = option.lower()
    
    # Handle 'standard' command: io standard <extract> <inject>
    if option_lower == "standard":
        if not value:
            print("  ✗ Usage: io standard <extract_format> <inject_format>")
            print("  Example: io standard txt json")
            return 1
        if not value2:
            print("  ✗ Missing inject format. Usage: io standard <extract> <inject>")
            return 1
        return _set_io_standard(value, value2)
    
    # Handle 'formats' command: show all available formats
    if option_lower == "formats":
        return _show_io_formats()
    
    # Handle specific options
    if option_lower in IO_OPTIONS:
        opt_info = IO_OPTIONS[option_lower]
        if value is None:
            return _show_io_option_details(option_lower, opt_info)
        return _set_io_value(option_lower, opt_info, value)
    
    print(f"  ✗ Unknown IO option: '{option}'")
    print("  Available: extract, inject, standard, preserve_original, formats")
    return 1


def _show_io_settings() -> int:
    """Display current IO configuration."""
    _print_header("IO Configuration")
    
    config = load_config()
    io_section = config.get("io", {})
    
    extract_fmt = io_section.get("extract_format", "txt")
    inject_fmt = io_section.get("inject_format", "txt")
    preserve = io_section.get("preserve_original", False)
    
    print("\n  Current Settings:")
    print("  " + "-" * 50)
    print(f"  Extract Format:     {extract_fmt}")
    print(f"  Inject Format:      {inject_fmt}")
    print(f"  Preserve Original:  {preserve}")
    print("  " + "-" * 50)
    
    print("\n  Usage:")
    print("    io extract <format>           Set input format")
    print("    io inject <format>            Set output format")
    print("    io standard <ext> <inj>       Set both at once")
    print("    io preserve_original true     Keep original in output")
    print("    io formats                    List all available formats")
    
    print("\n  Quick Examples:")
    print("    io standard txt json          Read txt, output json with originals")
    print("    io standard csv txt           Read csv, output plain txt")
    print("    io inject xlsx                Output to Excel")
    print()
    
    return 0


def _show_io_formats() -> int:
    """Display all available file formats."""
    _print_header("Available File Formats")
    
    print("\n  Simple Formats (fully supported):")
    print("  " + "-" * 55)
    for fmt, desc in SIMPLE_FORMAT_DESCRIPTIONS.items():
        print(f"  {fmt:<8} {desc}")
    print("  " + "-" * 55)
    
    print("\n  Advanced Formats (planned):")
    print("  " + "-" * 55)
    for fmt, desc in ADVANCED_FORMATS.items():
        print(f"  {fmt:<12} {desc}")
    print("  " + "-" * 55)
    
    print("\n  Format Capabilities:")
    print("  ┌─────────┬──────────┬──────────┬──────────────────┐")
    print("  │ Format  │ Extract  │ Inject   │ Supports Pairs   │")
    print("  ├─────────┼──────────┼──────────┼──────────────────┤")
    print("  │ txt     │    ✓     │    ✓     │       No         │")
    print("  │ csv     │    ✓     │    ✓     │       Yes        │")
    print("  │ tsv     │    ✓     │    ✓     │       Yes        │")
    print("  │ json    │    ✓     │    ✓     │       Yes        │")
    print("  │ xlsx    │    ✓     │    ✓     │       Yes        │")
    print("  └─────────┴──────────┴──────────┴──────────────────┘")
    print()
    
    return 0


def _show_io_option_details(option: str, opt_info: Dict[str, Any]) -> int:
    """Show details for a specific IO option."""
    _print_header(f"IO: {option}")
    
    config = load_config()
    io_section = config.get("io", {})
    
    current = io_section.get(opt_info["key"], opt_info.get("default", "Not set"))
    
    print(f"\n  {opt_info['description']}")
    print(f"\n  Current value: {current}")
    
    known = opt_info.get("known_values")
    if known:
        print("\n  Available options:")
        print("  " + "-" * 40)
        for i, (name, desc) in enumerate(known.items(), 1):
            marker = " ← current" if name == str(current).lower() else ""
            print(f"  [{i}] {name:<10} {desc}{marker}")
        print("  " + "-" * 40)
    
    print(f"\n  Usage: io {option} <value>")
    print()
    
    return 0


def _set_io_value(option: str, opt_info: Dict[str, Any], value: str) -> int:
    """Set an IO configuration value."""
    config = load_config()
    
    value_lower = value.lower()
    
    # Handle numbered selection
    if value.isdigit():
        known = opt_info.get("known_values", {})
        if known:
            idx = int(value) - 1
            keys = list(known.keys())
            if 0 <= idx < len(keys):
                value_lower = keys[idx]
            else:
                print(f"  ✗ Invalid selection: {value}. Choose 1-{len(keys)}.")
                return 1
    
    # Validate format using formats module
    if opt_info["type"] == "format":
        if f".{value_lower}" not in FORMAT_EXTENSIONS:
            print(f"  ✗ Unknown format: '{value}'")
            print(f"  Supported: {', '.join(SIMPLE_FORMAT_DESCRIPTIONS.keys())}")
            return 1
    elif opt_info["type"] == "bool":
        if value_lower not in ("true", "false", "yes", "no", "1", "0"):
            print(f"  ✗ Invalid boolean: '{value}'. Use true/false.")
            return 1
        bool_value = value_lower in ("true", "yes", "1")
    
    # Update config
    if "io" not in config:
        config["io"] = {}
    if opt_info["type"] == "bool":
        config["io"][opt_info["key"]] = bool_value
    else:
        config["io"][opt_info["key"]] = value_lower
    
    save_config(config)
    
    if opt_info["type"] == "bool":
        print(f"  ✓ Set {option} = {bool_value}")
    else:
        print(f"  ✓ Set {option} = {value_lower}")
    return 0


def _set_io_standard(extract_fmt: str, inject_fmt: str) -> int:
    """Set both extract and inject formats at once."""
    extract_lower = extract_fmt.lower()
    inject_lower = inject_fmt.lower()
    
    # Validate formats using formats module
    if f".{extract_lower}" not in FORMAT_EXTENSIONS:
        print(f"  ✗ Unknown extract format: '{extract_fmt}'")
        print(f"  Supported: {', '.join(SIMPLE_FORMAT_DESCRIPTIONS.keys())}")
        return 1
    
    if f".{inject_lower}" not in FORMAT_EXTENSIONS:
        print(f"  ✗ Unknown inject format: '{inject_fmt}'")
        print(f"  Supported: {', '.join(SIMPLE_FORMAT_DESCRIPTIONS.keys())}")
        return 1
    
    config = load_config()
    
    if "io" not in config:
        config["io"] = {}
    
    config["io"]["extract_format"] = extract_lower
    config["io"]["inject_format"] = inject_lower
    
    # Auto-enable preserve_original if using a pair format for injection
    pair_formats = {"csv", "tsv", "json", "xlsx"}
    if inject_lower in pair_formats and extract_lower != inject_lower:
        config["io"]["preserve_original"] = True
        print(f"  ✓ Auto-enabled preserve_original for {inject_lower} output")
    
    save_config(config)
    
    print(f"  ✓ IO Configuration Updated:")
    print(f"    Extract: {extract_lower} (read from)")
    print(f"    Inject:  {inject_lower} (write to)")
    
    return 0


# =============================================================================
# SAMPLE COMMAND
# =============================================================================

def run_sample_cli(
    path_str: str,
    lines: int = 50,
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None,
    api_overrides: Optional[Dict[str, Any]] = None,
) -> int:
    """Run a sample translation of the first N lines.
    
    This is a convenience command for quick testing. The user should ensure
    the sample lines are representative of the content to translate.
    
    Args:
        path_str: Path to input file.
        lines: Number of lines to translate (default 50).
        source_lang: Source language code.
        target_lang: Target language code.
        api_overrides: Dictionary of API settings to override.
        
    Returns:
        Exit code (0 = success, 1 = failure).
    """
    _print_header(f"Sample Translation ({lines} lines)")
    
    files = _get_files(path_str)
    if not files:
        print("  ✗ No supported files found.")
        return 1
    
    if len(files) > 1:
        print(f"  Found {len(files)} files. Using first file: {files[0].name}")
    
    file_path = files[0]
    print(f"\n  Input: {file_path.name}")
    print(f"  Lines: First {lines} lines")
    
    # Handle languages
    if source_lang:
        normalized_src = normalize_language_code(source_lang)
        if not normalized_src:
            print(f"  ✗ Unknown source language: '{source_lang}'")
            return 1
        source_lang = normalized_src
    
    if target_lang:
        normalized_tgt = normalize_language_code(target_lang)
        if not normalized_tgt:
            print(f"  ✗ Unknown target language: '{target_lang}'")
            return 1
        target_lang = normalized_tgt
    
    # Show language settings
    if source_lang and target_lang:
        _update_config_languages(source_lang, target_lang)
        print(f"  Language: {get_language_name(source_lang)} → {get_language_name(target_lang)}")
    else:
        current_src, current_tgt = _get_current_config()
        print(f"  Language: {current_src} → {current_tgt} (from config)")
    
    # Delegate to translate with line limit
    print("\n  Starting sample translation...")
    return run_translate_cli(
        path_str=str(file_path),
        source_lang=source_lang,
        target_lang=target_lang,
        translate_lines=lines,
        api_overrides=api_overrides,
    )


# =============================================================================
# GLOSSARY COMMANDS
# =============================================================================

def run_glossary_cli(
    action: Optional[str] = None,
    args: Optional[List[str]] = None
) -> int:
    """Handle glossary-related commands.
    
    Usage patterns:
    - glossary                    -> Show glossary summary
    - glossary list               -> List all entries
    - glossary list names         -> List only name entries
    - glossary list terms         -> List only term entries
    - glossary search <query>     -> Search for entries
    - glossary add <orig> <trans> -> Add a new entry
    - glossary path               -> Show glossary file path
    - glossary export <path>      -> Export glossary to file
    
    Args:
        action: Action to perform (list, search, add, path, export)
        args: Additional arguments for the action
        
    Returns:
        Exit code (0 = success, 1 = failure).
    """
    if args is None:
        args = []
    
    if action is None:
        return _show_glossary_summary()
    
    action_lower = action.lower()
    
    if action_lower == "list":
        filter_type = args[0] if args else None
        return _list_glossary_entries(filter_type)
    
    elif action_lower == "search":
        if not args:
            print("  ✗ Usage: glossary search <query>")
            return 1
        return _search_glossary(args[0])
    
    elif action_lower == "add":
        if len(args) < 2:
            print("  ✗ Usage: glossary add <original> <translation> [notes]")
            return 1
        original = args[0]
        translation = args[1]
        notes = args[2] if len(args) > 2 else ""
        return _add_glossary_entry(original, translation, notes)
    
    elif action_lower == "path":
        path = _unified_glossary_path()
        print(f"\n  Glossary file: {path}")
        print(f"  Exists: {'Yes' if path.exists() else 'No'}")
        if path.exists():
            entries = read_unified_glossary()
            print(f"  Entries: {len(entries)}")
        print()
        return 0
    
    elif action_lower == "export":
        if not args:
            print("  ✗ Usage: glossary export <path>")
            return 1
        return _export_glossary(args[0])
    
    else:
        print(f"  ✗ Unknown glossary action: '{action}'")
        print("  Valid actions: list, search, add, path, export")
        return 1


def _show_glossary_summary() -> int:
    """Show a summary of the glossary."""
    _print_header("Glossary Summary")
    
    try:
        entries = read_unified_glossary()
    except Exception as e:
        print(f"\n  ✗ Failed to read glossary: {e}")
        return 1
    
    if not entries:
        print("\n  Glossary is empty.")
        print("  Use 'glossary add <original> <translation>' to add entries.")
        print()
        return 0
    
    # Count by type
    names = sum(1 for e in entries.values() if e.entry_type == TYPE_NAME)
    terms = sum(1 for e in entries.values() if e.entry_type == TYPE_TERM)
    other = len(entries) - names - terms
    
    # Count with translations
    with_trans = sum(1 for e in entries.values() if e.translation)
    
    print(f"""
  Glossary Statistics:
  ─────────────────────────────────────
  Total Entries:     {len(entries)}
  With Translation:  {with_trans}
  ─────────────────────────────────────
  Names:             {names}
  Terms:             {terms}
  Other:             {other}
  ─────────────────────────────────────

  Commands:
    glossary list [names|terms]   List entries
    glossary search <query>       Search entries
    glossary add <orig> <trans>   Add entry
    glossary path                 Show file location
    glossary export <path>        Export to file
""")
    
    return 0


def _list_glossary_entries(filter_type: Optional[str] = None) -> int:
    """List glossary entries, optionally filtered by type."""
    entries = read_unified_glossary()
    
    if not entries:
        print("\n  Glossary is empty.\n")
        return 0
    
    # Filter entries
    filtered_entries: List[GlossaryEntry] = list(entries.values())
    if filter_type:
        filter_lower = filter_type.lower()
        if filter_lower in ("name", "names"):
            filtered_entries = [e for e in filtered_entries if e.entry_type == TYPE_NAME]
        elif filter_lower in ("term", "terms"):
            filtered_entries = [e for e in filtered_entries if e.entry_type == TYPE_TERM]
    
    _print_header(f"Glossary Entries ({len(filtered_entries)} items)")
    
    print("\n  " + "-" * 70)
    print(f"  {'Original':<25} {'Translation':<25} {'Type':<10}")
    print("  " + "-" * 70)
    
    for entry in filtered_entries[:50]:  # Limit display
        orig = entry.original[:23] + ".." if len(entry.original) > 25 else entry.original
        trans = entry.translation[:23] + ".." if len(entry.translation) > 25 else entry.translation
        print(f"  {orig:<25} {trans:<25} {entry.entry_type:<10}")
    
    if len(filtered_entries) > 50:
        print(f"\n  ... and {len(filtered_entries) - 50} more entries")
    
    print("  " + "-" * 70)
    print()
    
    return 0


def _search_glossary(query: str) -> int:
    """Search glossary for matching entries."""
    entries = read_unified_glossary()
    
    query_lower = query.lower()
    matches = [
        e for e in entries.values()
        if query_lower in e.original.lower() or query_lower in e.translation.lower()
    ]
    
    _print_header(f"Glossary Search: '{query}'")
    
    if not matches:
        print("\n  No matching entries found.\n")
        return 0
    
    print(f"\n  Found {len(matches)} match(es):\n")
    print("  " + "-" * 70)
    
    for entry in matches[:20]:
        print(f"  Original:    {entry.original}")
        if entry.translation:
            print(f"  Translation: {entry.translation}")
        if entry.notes:
            print(f"  Notes:       {entry.notes}")
        if entry.entry_type:
            print(f"  Type:        {entry.entry_type}")
        print("  " + "-" * 70)
    
    if len(matches) > 20:
        print(f"\n  ... and {len(matches) - 20} more matches")
    
    print()
    return 0


def _add_glossary_entry(original: str, translation: str, notes: str = "") -> int:
    """Add a new entry to the glossary."""
    entry = GlossaryEntry(
        original=original,
        translation=translation,
        notes=notes,
        source="CLI",
        entry_type=TYPE_TERM,
    )
    
    try:
        update_unified_glossary([entry])
        print(f"\n  ✓ Added glossary entry:")
        print(f"    {original} → {translation}")
        if notes:
            print(f"    Notes: {notes}")
        print()
        return 0
    except Exception as e:
        print(f"\n  ✗ Failed to add entry: {e}\n")
        return 1


def _export_glossary(path: str) -> int:
    """Export glossary to a file."""
    entries = read_unified_glossary()
    
    if not entries:
        print("\n  ✗ Glossary is empty, nothing to export.\n")
        return 1
    
    out_path = Path(path)
    
    try:
        # Determine format from extension
        suffix = out_path.suffix.lower()
        
        if suffix == ".csv":
            import csv
            with out_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Original", "Translation", "Notes", "Type"])
                for entry in entries.values():
                    writer.writerow([entry.original, entry.translation, entry.notes, entry.entry_type])
        
        elif suffix == ".txt":
            with out_path.open("w", encoding="utf-8") as f:
                for entry in entries.values():
                    f.write(f"{entry.original}\t{entry.translation}\n")
        
        else:
            # Default to tab-separated
            with out_path.open("w", encoding="utf-8") as f:
                for entry in entries.values():
                    f.write(f"{entry.original}\t{entry.translation}\t{entry.notes}\n")
        
        print(f"\n  ✓ Exported {len(entries)} entries to: {out_path}")
        print()
        return 0
    
    except Exception as e:
        print(f"\n  ✗ Export failed: {e}\n")
        return 1


# =============================================================================
# HELP COMMAND
# =============================================================================

def run_help_cli(topic: Optional[str] = None) -> int:
    """Display help information.
    
    Args:
        topic: Optional topic for detailed help.
        
    Returns:
        Exit code (always 0).
    """
    if topic:
        return _show_topic_help(topic)
    
    _print_header("CherryAI Command Line Help")
    
    print("""
  COMMANDS
  ─────────────────────────────────────────────────────────────────────

  translate <path>          Translate files (1-Click pipeline)
  sample <path>             Quick sample translation (default 50 lines)
  estimate <path>           Estimate translation cost
  test                      Run diagnostic tests
  
  config                    Show/set API configuration options
  io                        Configure input/output formats
  glossary                  Manage translation glossary
  languages                 List supported languages
  help                      Show this help message

  QUICK START
  ─────────────────────────────────────────────────────────────────────
  
  1. Set your API key:
     python CherryAI.py config api_key <your-key>
  
  2. Choose API provider:
     python CherryAI.py config api_url
     python CherryAI.py config api_url 2  (select from list)
  
  3. Translate a file:
     python CherryAI.py translate myfile.txt -s ja -t en -n 50

  PARAMETERS
  ─────────────────────────────────────────────────────────────────────
  
  -s, --source <lang>       Source language (ja, en, de, fr, es, ko, zh-CN, zh-TW)
  -t, --target <lang>       Target language
  -n, --lines <N>           Translate only first N lines
  -y, --yes                 Skip confirmation prompts
  -i, --interactive         Step-by-step wizard mode
  --skip-api                For test: skip API calls

  EXAMPLES
  ─────────────────────────────────────────────────────────────────────
  
  # Configure API
  python CherryAI.py config api_url gemini
  python CherryAI.py config api_key AIza...
  python CherryAI.py config model gemini-2.0-flash

  # Configure IO formats
  python CherryAI.py io standard txt json
  python CherryAI.py io formats

  # Translate
  python CherryAI.py translate game.txt -s ja -t en
  python CherryAI.py sample game.txt -n 100
  python CherryAI.py translate folder/ -s ja -t de -y

  # Glossary
  python CherryAI.py glossary list names
  python CherryAI.py glossary add "リオス" "Rios"
  python CherryAI.py glossary search hero

  For more details: python CherryAI.py help <command>
""")
    
    return 0


def _show_topic_help(topic: str) -> int:
    """Show detailed help for a specific topic."""
    topic_lower = topic.lower()
    
    help_topics: Dict[str, str] = {
        "translate": """
  TRANSLATE COMMAND
  ─────────────────────────────────────────────────────────────────────
  
  Translates text files using an LLM API.
  
  Usage: python CherryAI.py translate <path> [options]
  
  Arguments:
    path                    File or directory to translate
  
  Options:
    -s, --source <lang>     Source language code (e.g., ja, japanese)
    -t, --target <lang>     Target language code (e.g., en, english)
    -n, --lines <N>         Only translate first N lines
    -y, --yes               Skip confirmation prompt
    -i, --interactive       Use step-by-step wizard
    --line-by-line          Translate each line individually (slower but more control)
    --context <N>           For line-by-line: adjacent lines as context (0-3, default 1)
    --thinking              Enable extended thinking mode for compatible models
    --thinking-budget <N>   Token budget for thinking mode (default: 10000)
    --chunk-mode <mode>     Chunking strategy: lines (default), tokens, or hybrid
    --chunk-tokens <N>      Max tokens per chunk for tokens/hybrid mode (default: 4000)
  
  Translation Modes:
    Standard (default)      Batches lines for efficiency, uses full context
    Line-by-Line            One line at a time, minimal prompt, maximum control
  
  Chunking Modes:
    lines (default)         Chunk by line count (--chunk-size)
    tokens                  Chunk by token count (--chunk-tokens, uses tiktoken)
    hybrid                  Use whichever limit is reached first
    
    Token-based chunking is useful for:
    - Files with very long lines that could exceed context limits
    - More accurate cost estimation per batch
    - Preventing context overflow in mixed-length content
  
  Thinking Mode:
    Extended thinking enables step-by-step reasoning for models that support it.
    Supported models: Claude 4+ (Sonnet, Opus, Haiku), OpenAI o1/o3 series
    Note: Significantly increases token usage and cost.
  
  Examples:
    translate sample.txt -s ja -t en -n 50
    translate game_data/ -s japanese -t german -y
    translate --interactive
    translate file.txt --line-by-line --context 2
    translate file.txt --thinking --thinking-budget 16000
    translate file.txt --chunk-mode hybrid --chunk-tokens 2000
""",
        "config": """
  CONFIG COMMAND
  ─────────────────────────────────────────────────────────────────────
  
  View and modify CherryAI configuration.
  
  Usage: python CherryAI.py config [option] [value]
  
  Without arguments: Show all options and current values
  With option only:  Show details and available values for that option
  With option+value: Set the option to the specified value
  
  Options:
    api_url         API endpoint URL
    api_key         API authentication key
    model           LLM model name
    temperature     Generation temperature (0.0-2.0)
    chunk_size      Lines per API request (10-200)
    timeout         API timeout in seconds
    source_lang     Default source language
    target_lang     Default target language
    preset          Apply a saved configuration preset
  
  Examples:
    config                           Show all options
    config api_url                   Show known URLs
    config api_url 2                 Select 2nd known URL
    config api_url https://api.example.com/v1
    config api_key sk-abc123...
    config model gpt-4o
    config preset gemini_free
""",
        "glossary": """
  GLOSSARY COMMAND
  ─────────────────────────────────────────────────────────────────────
  
  Manage the translation glossary (term dictionary).
  
  Usage: python CherryAI.py glossary [action] [args...]
  
  Actions:
    (none)              Show glossary summary
    list [type]         List entries (optional: names, terms)
    search <query>      Search for entries
    add <orig> <trans>  Add new entry
    path                Show glossary file location
    export <path>       Export to CSV or text file
  
  Examples:
    glossary                     Show summary
    glossary list                List all entries
    glossary list names          List character names only
    glossary search hero         Find entries containing "hero"
    glossary add "勇者" "Hero"   Add a term
    glossary export terms.csv    Export to CSV
""",
        "sample": """
  SAMPLE COMMAND
  ─────────────────────────────────────────────────────────────────────
  
  Quick sample translation for testing quality.
  
  Usage: python CherryAI.py sample <path> [options]
  
  Arguments:
    path                    File to translate
  
  Options:
    -n, --lines <N>         Number of lines (default: 50)
    -s, --source <lang>     Source language
    -t, --target <lang>     Target language
  
  Note: Make sure the first N lines of your file are representative
  of the content you want to translate.
  
  Examples:
    sample game.txt                 Translate first 50 lines
    sample game.txt -n 100          Translate first 100 lines
    sample game.txt -s ja -t en     Specify languages
""",
        "languages": """
  LANGUAGES COMMAND
  ─────────────────────────────────────────────────────────────────────
  
  Shows all supported language codes and names.
  
  Usage: python CherryAI.py languages
  
  Supported languages:
    ja      Japanese
    en      English
    de      German
    fr      French
    es      Spanish
    ko      Korean
    zh-CN   Chinese (Simplified)
    zh-TW   Chinese (Traditional)
  
  Aliases are supported: jp, jpn, japanese all map to 'ja'.
""",
        "test": """
  TEST COMMAND
  ─────────────────────────────────────────────────────────────────────
  
  Run diagnostic tests to verify installation and API connectivity.
  
  Usage: python CherryAI.py test [options]
  
  Options:
    --skip-api          Skip API connectivity tests (offline mode)
  
  Tests performed:
    1. Dependencies     Check required packages
    2. Configuration    Validate config file
    3. File I/O         Test read/write operations
    4. Pre-Processing   Test placeholder protection
    5. API Connection   Test API connectivity
    6. Translation      Test actual translation
    7. Post-Processing  Test placeholder restoration
  
  Examples:
    test                Run all tests
    test --skip-api     Run offline tests only
""",
        "io": """
  IO COMMAND
  ─────────────────────────────────────────────────────────────────────
  
  Configure input/output file formats for translation.
  
  Usage: python CherryAI.py io [option] [value] [value2]
  
  Commands:
    io                             Show current IO settings
    io formats                     List all available formats
    io extract <format>            Set input format (txt, csv, json, etc.)
    io inject <format>             Set output format
    io standard <extract> <inject> Set both formats at once
    io preserve_original true      Include original lines in output
  
  Supported Formats:
    txt     Plain text (one line per line)
    csv     Comma-separated values
    tsv     Tab-separated values
    json    JSON (array of strings or objects)
    xlsx    Excel spreadsheet
  
  Format Capabilities:
    - txt: Simple, no pair support
    - csv, tsv, xlsx: Supports original + translated pairs
    - json: Supports pairs as {"original": ..., "translated": ...}
  
  Examples:
    io standard txt json          Read txt, output json with originals
    io standard csv txt           Read csv column A, output plain txt
    io inject xlsx                Set output format to Excel
    io preserve_original true     Include original in pair formats
""",
    }
    
    if topic_lower in help_topics:
        print(help_topics[topic_lower])
        return 0
    
    print(f"\n  No detailed help for '{topic}'.")
    print("  Available topics: translate, config, glossary, sample, languages, test, io")
    print()
    return 0