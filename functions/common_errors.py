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

    # Translation Pipeline Errors (700-799)
    TRANSLATION_NON_STRUCTURED_OUTPUT = auto()
    TRANSLATION_LINE_COUNT_MISMATCH = auto()
    TRANSLATION_EMPTY_RESPONSE = auto()
    TRANSLATION_REFUSED = auto()
    TRANSLATION_ABORT = auto()


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

    # Translation Pipeline
    ErrorCode.TRANSLATION_NON_STRUCTURED_OUTPUT: (
        "API returned non-JSON output: {details}"
    ),
    ErrorCode.TRANSLATION_LINE_COUNT_MISMATCH: (
        "Expected {expected} lines, got {actual}: {details}"
    ),
    ErrorCode.TRANSLATION_EMPTY_RESPONSE: "API returned an empty response.",
    ErrorCode.TRANSLATION_REFUSED: "API refused to translate: {details}",
    ErrorCode.TRANSLATION_ABORT: "Translation aborted: {details}",
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


# =============================================================================
# API Error Classification (Translation Pipeline)
# =============================================================================


class APIErrorCategory(Enum):
    """Categories of API errors for user-facing classification."""

    AUTH_INVALID = "auth_invalid"
    AUTH_WRONG_KEY = "auth_wrong_key"
    MODEL_NOT_FOUND = "model_not_found"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    CONTENT_FILTERED = "content_filtered"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    SERVER_OVERLOADED = "server_overloaded"
    CONNECTION_ERROR = "connection_error"
    NON_STRUCTURED_OUTPUT = "non_structured_output"
    LINE_COUNT_MISMATCH = "line_count_mismatch"
    EMPTY_RESPONSE = "empty_response"
    THINKING_NOT_AVAILABLE = "thinking_not_available"
    BATCH_NOT_AVAILABLE = "batch_not_available"
    TEMPERATURE_NOT_AVAILABLE = "temperature_not_available"
    PROMPT_CACHE_NOT_AVAILABLE = "prompt_cache_not_available"
    PERMISSION_DENIED = "permission_denied"
    BAD_REQUEST = "bad_request"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedAPIError:
    """A classified API error with user-facing message and guidance.

    Attributes:
        category: The error classification.
        user_message: Human-readable explanation for the user.
        steps: List of steps the user can take to resolve the issue.
        raw_message: The original error message from the API.
        is_retryable: Whether the error may resolve with a retry.
        is_fatal: Whether translation must stop immediately.
    """

    category: APIErrorCategory
    user_message: str
    steps: List[str]
    raw_message: str
    is_retryable: bool = False
    is_fatal: bool = True


# Mapping of error categories to user-facing messages and guidance.
_API_ERROR_INFO: Dict[APIErrorCategory, Dict[str, Any]] = {
    APIErrorCategory.AUTH_INVALID: {
        "message": "Authentication failed. Your API key is invalid or expired.",
        "steps": [
            "Go to Global Options → API and verify your API key.",
            "Generate a new API key from your provider's dashboard.",
            "Ensure the key is saved correctly (no extra spaces).",
        ],
    },
    APIErrorCategory.AUTH_WRONG_KEY: {
        "message": "The API key provided is incorrect.",
        "steps": [
            "Double-check the API key in Global Options → API.",
            "Make sure you're using the right key for the selected provider.",
            "Try generating a fresh API key.",
        ],
    },
    APIErrorCategory.MODEL_NOT_FOUND: {
        "message": "The selected model was not found.",
        "steps": [
            "Check the model name in Request Options.",
            "Open Global Options → API → Available Models to see valid models.",
            "The model may have been deprecated — try a different model.",
        ],
    },
    APIErrorCategory.RATE_LIMITED: {
        "message": "Too many requests. The API rate limit has been reached.",
        "steps": [
            "Wait a moment and try again.",
            "Reduce the number of concurrent requests in Global Options.",
            "Consider upgrading your API plan for higher rate limits.",
        ],
    },
    APIErrorCategory.QUOTA_EXCEEDED: {
        "message": "API quota exhausted. You have run out of credits or hit your monthly limit.",
        "steps": [
            "Check your billing/usage on the provider's dashboard.",
            "Add more credits or upgrade your plan.",
            "Switch to a free-tier model (e.g., Gemini Flash Lite).",
        ],
    },
    APIErrorCategory.CONTENT_FILTERED: {
        "message": "The API refused to translate due to content policy restrictions.",
        "steps": [
            "Review the input text for content that may violate provider policies.",
            "Try a provider with fewer content restrictions (Gemini, local LLM).",
            "Split the problematic content into smaller, isolated requests.",
        ],
    },
    APIErrorCategory.TIMEOUT: {
        "message": "The API request timed out.",
        "steps": [
            "Increase the timeout in Global Options → Request Settings.",
            "Reduce Lines/Chunk to send smaller requests.",
            "Check your internet connection.",
        ],
    },
    APIErrorCategory.SERVER_ERROR: {
        "message": "The API server encountered an internal error.",
        "steps": [
            "This is a temporary issue on the provider's side.",
            "Wait a few minutes and try again.",
            "Check the provider's status page for outages.",
        ],
    },
    APIErrorCategory.SERVER_OVERLOADED: {
        "message": "The API server is temporarily overloaded.",
        "steps": [
            "Wait a few minutes and try again.",
            "Try during off-peak hours.",
            "Switch to a less popular model temporarily.",
        ],
    },
    APIErrorCategory.CONNECTION_ERROR: {
        "message": "Could not connect to the API server.",
        "steps": [
            "Check your internet connection.",
            "Verify the API Base URL in Global Options.",
            "Check if a firewall or proxy is blocking the connection.",
        ],
    },
    APIErrorCategory.NON_STRUCTURED_OUTPUT: {
        "message": "The API returned non-JSON output instead of structured translations.",
        "steps": [
            "The model may not support JSON/structured output mode.",
            "Try a different model that supports structured output.",
            "If using a local LLM, ensure it supports JSON mode.",
        ],
    },
    APIErrorCategory.LINE_COUNT_MISMATCH: {
        "message": "The API returned a different number of lines than expected.",
        "steps": [
            "This may be a model quality issue. Try a different model.",
            "Reduce Lines/Chunk to send smaller batches.",
            "The translation will be retried automatically.",
        ],
    },
    APIErrorCategory.EMPTY_RESPONSE: {
        "message": "The API returned an empty response.",
        "steps": [
            "This is usually a temporary server issue. Try again.",
            "If persistent, try a different model.",
            "Check if the input text is too short or unusual.",
        ],
    },
    APIErrorCategory.THINKING_NOT_AVAILABLE: {
        "message": "Extended thinking/reasoning mode is not available for this model.",
        "steps": [
            "Disable Thinking Mode in Global Options → Request Settings.",
            "Switch to a model that supports thinking (Claude, o1, o3).",
        ],
    },
    APIErrorCategory.BATCH_NOT_AVAILABLE: {
        "message": "Batch API mode is not available for this model or provider.",
        "steps": [
            "Disable Batch Mode and use standard translation.",
            "Check if your provider supports the Batch API.",
        ],
    },
    APIErrorCategory.TEMPERATURE_NOT_AVAILABLE: {
        "message": "Temperature setting is not supported for this model.",
        "steps": [
            "Some reasoning models (o1, o3) do not accept temperature.",
            "Set temperature to 1.0 or remove the temperature setting.",
        ],
    },
    APIErrorCategory.PROMPT_CACHE_NOT_AVAILABLE: {
        "message": "Prompt caching is not available for this model or provider.",
        "steps": [
            "Disable Prompt Caching in Global Options.",
            "Prompt caching is only available for OpenAI gpt-4o and newer.",
        ],
    },
    APIErrorCategory.PERMISSION_DENIED: {
        "message": "Access denied. You don't have permission to use this resource.",
        "steps": [
            "Verify your API key has the required permissions.",
            "Check your organization/project settings with the provider.",
            "Your region may not be supported — check provider documentation.",
        ],
    },
    APIErrorCategory.BAD_REQUEST: {
        "message": "The API rejected the request as malformed.",
        "steps": [
            "Check if the model name is correct.",
            "Review request settings (temperature, max tokens, etc.).",
            "This may indicate an unsupported parameter for the model.",
        ],
    },
    APIErrorCategory.UNKNOWN: {
        "message": "An unexpected API error occurred.",
        "steps": [
            "Copy the error message below and report it to the developer.",
            "Try again — the issue may be temporary.",
            "Check the provider's status page for known issues.",
        ],
    },
}


def classify_api_error(error: Exception) -> ClassifiedAPIError:
    """Classify an API exception into a user-facing error with guidance.

    Inspects the exception type and message to determine the category,
    then returns a ``ClassifiedAPIError`` with user-friendly text and
    remediation steps.

    Args:
        error: The exception raised during an API call.

    Returns:
        A classified error with user message and next steps.
    """
    raw = str(error)
    raw_lower = raw.lower()

    # OpenAI SDK exception types (may not be available if package missing)
    err_type = type(error).__name__

    # --- Authentication errors ---
    if err_type == "AuthenticationError" or "401" in raw:
        if "incorrect api key" in raw_lower:
            cat = APIErrorCategory.AUTH_WRONG_KEY
        else:
            cat = APIErrorCategory.AUTH_INVALID
        return _build_classified(cat, raw)

    # --- Permission / region ---
    if err_type == "PermissionDeniedError" or "403" in raw:
        return _build_classified(APIErrorCategory.PERMISSION_DENIED, raw)

    # --- Model not found ---
    if err_type == "NotFoundError" or "404" in raw:
        if "model" in raw_lower:
            return _build_classified(APIErrorCategory.MODEL_NOT_FOUND, raw)
        return _build_classified(APIErrorCategory.BAD_REQUEST, raw)

    # --- Rate limit / quota ---
    if err_type == "RateLimitError" or "429" in raw:
        if "quota" in raw_lower or "billing" in raw_lower or "credit" in raw_lower:
            return _build_classified(APIErrorCategory.QUOTA_EXCEEDED, raw)
        return _build_classified(APIErrorCategory.RATE_LIMITED, raw, is_retryable=True)

    # --- Bad request (parameter issues) ---
    if err_type == "BadRequestError" or "400" in raw:
        if "thinking" in raw_lower or "reasoning" in raw_lower:
            return _build_classified(
                APIErrorCategory.THINKING_NOT_AVAILABLE, raw,
            )
        if "batch" in raw_lower:
            return _build_classified(
                APIErrorCategory.BATCH_NOT_AVAILABLE, raw,
            )
        if "temperature" in raw_lower:
            return _build_classified(
                APIErrorCategory.TEMPERATURE_NOT_AVAILABLE, raw,
            )
        if "prompt_cache" in raw_lower or "cache" in raw_lower:
            return _build_classified(
                APIErrorCategory.PROMPT_CACHE_NOT_AVAILABLE, raw,
            )
        if ("content" in raw_lower and "policy" in raw_lower) or "flagged" in raw_lower:
            return _build_classified(
                APIErrorCategory.CONTENT_FILTERED, raw,
            )
        return _build_classified(APIErrorCategory.BAD_REQUEST, raw)

    # --- Timeout ---
    if err_type == "APITimeoutError" or "timeout" in raw_lower:
        return _build_classified(
            APIErrorCategory.TIMEOUT, raw, is_retryable=True,
        )

    # --- Server errors ---
    if err_type == "InternalServerError" or "500" in raw:
        return _build_classified(
            APIErrorCategory.SERVER_ERROR, raw, is_retryable=True,
        )

    # --- Overloaded ---
    if "503" in raw or "overloaded" in raw_lower or "slow down" in raw_lower:
        return _build_classified(
            APIErrorCategory.SERVER_OVERLOADED, raw, is_retryable=True,
        )

    # --- Connection errors ---
    if err_type == "APIConnectionError" or "connection" in raw_lower:
        return _build_classified(
            APIErrorCategory.CONNECTION_ERROR, raw, is_retryable=True,
        )

    # --- Content policy / refusal ---
    if ("refuse" in raw_lower or "cannot translate" in raw_lower
            or "unable to translate" in raw_lower
            or "content policy" in raw_lower):
        return _build_classified(APIErrorCategory.CONTENT_FILTERED, raw)

    # --- Translation-specific errors ---
    if "invalid json" in raw_lower or "non-json" in raw_lower:
        return _build_classified(
            APIErrorCategory.NON_STRUCTURED_OUTPUT, raw,
        )
    if "line count mismatch" in raw_lower:
        return _build_classified(
            APIErrorCategory.LINE_COUNT_MISMATCH, raw, is_retryable=True,
        )
    if "empty response" in raw_lower:
        return _build_classified(
            APIErrorCategory.EMPTY_RESPONSE, raw, is_retryable=True,
        )

    # --- Fallback: unknown ---
    return _build_classified(APIErrorCategory.UNKNOWN, raw)


def _build_classified(
    category: APIErrorCategory,
    raw_message: str,
    is_retryable: bool = False,
) -> ClassifiedAPIError:
    """Build a ClassifiedAPIError from a category lookup."""
    info = _API_ERROR_INFO.get(category, _API_ERROR_INFO[APIErrorCategory.UNKNOWN])
    return ClassifiedAPIError(
        category=category,
        user_message=info["message"],
        steps=list(info["steps"]),
        raw_message=raw_message,
        is_retryable=is_retryable,
        is_fatal=not is_retryable,
    )


class TranslationAbortError(Exception):
    """Raised when translation must stop immediately.

    Carries a :class:`ClassifiedAPIError` so the GUI can display
    a user-friendly message with remediation steps.
    """

    def __init__(self, classified: ClassifiedAPIError) -> None:
        self.classified = classified
        super().__init__(classified.user_message)

    @property
    def user_message(self) -> str:
        """Short user-facing explanation."""
        return self.classified.user_message

    @property
    def steps(self) -> List[str]:
        """List of remediation steps."""
        return self.classified.steps

    @property
    def raw_message(self) -> str:
        """Original API error text (copyable for developer reports)."""
        return self.classified.raw_message

    @property
    def is_retryable(self) -> bool:
        """Whether a retry may resolve the issue."""
        return self.classified.is_retryable

    def format_for_display(self) -> str:
        """Format as a multi-line string for GUI display."""
        lines = [self.user_message, ""]
        if self.steps:
            lines.append("What you can do:")
            for i, step in enumerate(self.steps, 1):
                lines.append(f"  {i}. {step}")
        if self.raw_message and self.classified.category == APIErrorCategory.UNKNOWN:
            lines.append("")
            lines.append(f"API message: {self.raw_message}")
        return "\n".join(lines)
