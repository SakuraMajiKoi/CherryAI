"""Common error handling for CherryAI.

Centralized error codes, messages, and logging utilities.
Used by CLI, GUI, and other modules for consistent error reporting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional


class ErrorCode(Enum):
    """Enumeration of all error codes in CherryAI."""

    # Configuration Errors (100-199)
    CONFIG_NOT_FOUND = auto()
    CONFIG_INVALID = auto()
    CONFIG_MISSING_SECTION = auto()

    # API Errors (200-299)
    API_KEY_MISSING = auto()
    API_KEY_INVALID = auto()
    API_CONNECTION_FAILED = auto()
    API_RATE_LIMITED = auto()
    API_TIMEOUT = auto()
    API_RESPONSE_INVALID = auto()
    API_PROVIDER_UNSUPPORTED = auto()

    # File Errors (300-399)
    FILE_NOT_FOUND = auto()
    FILE_UNREADABLE = auto()
    FILE_WRITE_FAILED = auto()
    FILE_FORMAT_UNSUPPORTED = auto()
    FILE_EMPTY = auto()
    FILE_ENCODING_ERROR = auto()

    # Processing Errors (400-499)
    PROCESSING_FAILED = auto()
    MANIFEST_INVALID = auto()
    MODE_NOT_FOUND = auto()
    REGEX_INVALID = auto()
    PLACEHOLDER_COLLISION = auto()

    # Dependency Errors (500-599)
    DEPENDENCY_MISSING = auto()
    DEPENDENCY_VERSION_MISMATCH = auto()

    # Test-Specific Errors (600-699)
    TEST_SAMPLE_MISSING = auto()
    TEST_PIPELINE_FAILED = auto()
    TEST_VALIDATION_FAILED = auto()


# Human-readable error messages
ERROR_MESSAGES: Dict[ErrorCode, str] = {
    # Configuration
    ErrorCode.CONFIG_NOT_FOUND: "Configuration file not found at: {path}",
    ErrorCode.CONFIG_INVALID: "Configuration file is invalid or corrupted: {details}",
    ErrorCode.CONFIG_MISSING_SECTION: "Missing required configuration section: [{section}]",

    # API
    ErrorCode.API_KEY_MISSING: (
        "API key not configured. Add to CherryAI.ini:\n"
        "  [api]\n"
        "  api_key = your_api_key_here"
    ),
    ErrorCode.API_KEY_INVALID: "API key is invalid or rejected by the provider: {details}",
    ErrorCode.API_CONNECTION_FAILED: "Failed to connect to API: {details}",
    ErrorCode.API_RATE_LIMITED: "API rate limit reached. Try again in {wait_time}s.",
    ErrorCode.API_TIMEOUT: "API request timed out after {timeout}s.",
    ErrorCode.API_RESPONSE_INVALID: "API returned invalid response: {details}",
    ErrorCode.API_PROVIDER_UNSUPPORTED: "Unsupported API provider: {provider}",

    # File
    ErrorCode.FILE_NOT_FOUND: "File not found: {path}",
    ErrorCode.FILE_UNREADABLE: "Cannot read file: {path}. Error: {details}",
    ErrorCode.FILE_WRITE_FAILED: "Failed to write file: {path}. Error: {details}",
    ErrorCode.FILE_FORMAT_UNSUPPORTED: "Unsupported file format: {extension}",
    ErrorCode.FILE_EMPTY: "File is empty: {path}",
    ErrorCode.FILE_ENCODING_ERROR: "Encoding error reading file: {path}. Try UTF-8.",

    # Processing
    ErrorCode.PROCESSING_FAILED: "Processing failed: {details}",
    ErrorCode.MANIFEST_INVALID: "Manifest file is invalid: {details}",
    ErrorCode.MODE_NOT_FOUND: "Processing mode not found: {mode}",
    ErrorCode.REGEX_INVALID: "Invalid regex pattern: {pattern}. Error: {details}",
    ErrorCode.PLACEHOLDER_COLLISION: "Placeholder collision detected: {placeholder}",

    # Dependencies
    ErrorCode.DEPENDENCY_MISSING: (
        "Required dependency not installed: {package}.\n"
        "Run: pip install {package}"
    ),
    ErrorCode.DEPENDENCY_VERSION_MISMATCH: (
        "Dependency version mismatch: {package}\n"
        "Required: {required}, Installed: {installed}"
    ),

    # Test
    ErrorCode.TEST_SAMPLE_MISSING: "Test sample file not found. Expected at: {path}",
    ErrorCode.TEST_PIPELINE_FAILED: "Test pipeline failed at stage '{stage}': {details}",
    ErrorCode.TEST_VALIDATION_FAILED: "Test validation failed: {details}",
}


@dataclass
class CherryError:
    """Structured error with code, message, and context."""

    code: ErrorCode
    context: Dict[str, Any]
    recoverable: bool = True

    @property
    def message(self) -> str:
        """Get the formatted error message."""
        template = ERROR_MESSAGES.get(self.code, f"Unknown error: {self.code}")
        try:
            return template.format(**self.context)
        except KeyError:
            return f"{template} (context: {self.context})"

    def log(self, level: int = logging.ERROR) -> None:
        """Log the error at the specified level."""
        logger = logging.getLogger("cherryai.errors")
        logger.log(level, f"[{self.code.name}] {self.message}")


class ErrorCollector:
    """Collects errors during a multi-step operation for reporting."""

    def __init__(self) -> None:
        self.errors: List[CherryError] = []
        self.warnings: List[CherryError] = []
        self._logger = logging.getLogger("cherryai.errors")

    def add_error(
        self,
        code: ErrorCode,
        recoverable: bool = True,
        **context: Any,
    ) -> CherryError:
        """Add an error with context."""
        error = CherryError(code=code, context=context, recoverable=recoverable)
        self.errors.append(error)
        error.log(logging.ERROR)
        return error

    def add_warning(self, code: ErrorCode, **context: Any) -> CherryError:
        """Add a warning with context."""
        warning = CherryError(code=code, context=context, recoverable=True)
        self.warnings.append(warning)
        warning.log(logging.WARNING)
        return warning

    def has_errors(self) -> bool:
        """Check if any errors were collected."""
        return len(self.errors) > 0

    def has_fatal_errors(self) -> bool:
        """Check if any non-recoverable errors exist."""
        return any(not e.recoverable for e in self.errors)

    def get_summary(self) -> str:
        """Get a summary of all collected errors and warnings."""
        lines = []
        if self.errors:
            lines.append(f"=== ERRORS ({len(self.errors)}) ===")
            for e in self.errors:
                lines.append(f"  [{e.code.name}] {e.message}")
        if self.warnings:
            lines.append(f"=== WARNINGS ({len(self.warnings)}) ===")
            for w in self.warnings:
                lines.append(f"  [{w.code.name}] {w.message}")
        if not lines:
            lines.append("No errors or warnings.")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all collected errors and warnings."""
        self.errors.clear()
        self.warnings.clear()


def validate_config_for_api() -> ErrorCollector:
    """Validate that the configuration is sufficient for API calls.

    Returns:
        ErrorCollector with any validation errors.
    """
    from .config import load_config, get_config_file, ensure_config_initialized

    collector = ErrorCollector()
    config_file = get_config_file()

    # Ensure config file exists with defaults
    if not config_file.exists():
        collector.add_warning(ErrorCode.CONFIG_NOT_FOUND, path=str(config_file))
        # Initialize with defaults
        ensure_config_initialized(config_file)

    # Load config (with_defaults=True ensures [api] section exists)
    config = load_config(config_file, with_defaults=True)

    # [api] section should always exist now due to defaults
    api_config = config.get("api", {})

    # Check API key (this is the critical one for actual API calls)
    api_key = api_config.get("api_key", "").strip()
    if not api_key:
        collector.add_error(ErrorCode.API_KEY_MISSING, recoverable=False)

    # Check provider (optional, default is openai)
    provider = api_config.get("provider", "openai").lower()
    valid_providers = {"openai", "gemini", "anthropic", "local"}
    if provider not in valid_providers:
        collector.add_warning(
            ErrorCode.API_PROVIDER_UNSUPPORTED,
            provider=provider,
        )

    return collector


def validate_file_readable(path: Path) -> Optional[CherryError]:
    """Validate that a file exists and is readable.

    Returns:
        CherryError if validation fails, None if OK.
    """
    if not path.exists():
        return CherryError(
            code=ErrorCode.FILE_NOT_FOUND,
            context={"path": str(path)},
            recoverable=False,
        )

    try:
        with path.open("r", encoding="utf-8") as f:
            content = f.read(1024)  # Read first 1KB to test
            if not content.strip():
                return CherryError(
                    code=ErrorCode.FILE_EMPTY,
                    context={"path": str(path)},
                    recoverable=True,
                )
    except UnicodeDecodeError as e:
        return CherryError(
            code=ErrorCode.FILE_ENCODING_ERROR,
            context={"path": str(path), "details": str(e)},
            recoverable=False,
        )
    except OSError as e:
        return CherryError(
            code=ErrorCode.FILE_UNREADABLE,
            context={"path": str(path), "details": str(e)},
            recoverable=False,
        )

    return None


def check_dependencies() -> ErrorCollector:
    """Check that all required dependencies are installed.

    Returns:
        ErrorCollector with any missing dependencies.
    """
    collector = ErrorCollector()

    # Required packages
    required = {
        "openpyxl": "Excel file support",
    }

    # Optional packages
    optional = {
        "openai": "API translation",
        "tiktoken": "Token counting",
    }

    for package, purpose in required.items():
        try:
            __import__(package)
        except ImportError:
            collector.add_error(
                ErrorCode.DEPENDENCY_MISSING,
                package=package,
                recoverable=True,
            )

    for package, purpose in optional.items():
        try:
            __import__(package)
        except ImportError:
            collector.add_warning(
                ErrorCode.DEPENDENCY_MISSING,
                package=package,
            )

    return collector
