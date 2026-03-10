"""File format handlers for CherryAI.

This module provides pluggable file format handlers with separate
extract (read) and inject (write) capabilities.

Supported Format Categories:
- simple: txt, csv, tsv, json, xlsx (basic text/table formats)
- rpgmaker: RPG Maker MV/MZ custom JSON and JS files (planned)
- document: PDF, EPUB extraction/injection (planned)

Usage:
    from CherryAI.formats import get_handler, SUPPORTED_FORMATS
    
    # Get handler for a file type
    handler = get_handler("txt")
    lines = handler.extract(path)
    handler.inject(path, lines, original_lines)

IO Configuration:
    The IO config allows setting different formats for extract (input)
    and inject (output). For example:
    - Extract from .txt, inject to .json with original lines preserved
    - Extract from .csv, inject to .txt for simple output
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type, Any, TYPE_CHECKING
from dataclasses import dataclass
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from .parser_base import ParserScript

from .handshake import ExtractedLine, ParserError, SpeakerInfo, validate_parser


__all__ = [
    "FormatHandler",
    "FormatRegistry",
    "get_handler",
    "get_registry",
    "ParserRegistry",
    "get_parser_registry",
    "detect_parser",
    "list_parser_names",
    "validate_parser",
    "ExtractedLine",
    "ParserError",
    "SpeakerInfo",
    "SUPPORTED_FORMATS",
    "SIMPLE_FORMATS",
    "RPGMAKER_FORMATS",
    "DOCUMENT_FORMATS",
    "MARKDOWN_FORMATS",
    "LENIENT_JSON_FORMATS",
    "TRANSLATOR_FORMATS",
]


# Format category definitions
SIMPLE_FORMATS = {".txt", ".csv", ".tsv", ".json", ".xlsx"}
RPGMAKER_FORMATS = {".rpgjson", ".rpgjs"}  # Custom extensions for clarity
DOCUMENT_FORMATS = {".pdf", ".epub"}
MARKDOWN_FORMATS = {".md"}
LENIENT_JSON_FORMATS = {".json5", ".jsonc"}
TRANSLATOR_FORMATS = {".trans"}

SUPPORTED_FORMATS = (
    SIMPLE_FORMATS
    | RPGMAKER_FORMATS
    | DOCUMENT_FORMATS
    | MARKDOWN_FORMATS
    | LENIENT_JSON_FORMATS
    | TRANSLATOR_FORMATS
)


@dataclass
class IOConfig:
    """Configuration for input/output format handling.
    
    Attributes:
        extract_format: Format to use for reading/extracting text.
        inject_format: Format to use for writing/injecting text.
        preserve_original: If True, output includes original lines.
        encoding: Text encoding (default: utf-8).
    """
    extract_format: str = "txt"
    inject_format: str = "txt"
    preserve_original: bool = False
    encoding: str = "utf-8"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to dictionary."""
        return {
            "extract_format": self.extract_format,
            "inject_format": self.inject_format,
            "preserve_original": self.preserve_original,
            "encoding": self.encoding,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IOConfig":
        """Deserialize config from dictionary."""
        return cls(
            extract_format=data.get("extract_format", "txt"),
            inject_format=data.get("inject_format", "txt"),
            preserve_original=data.get("preserve_original", False),
            encoding=data.get("encoding", "utf-8"),
        )


class FormatHandler(ABC):
    """Abstract base class for file format handlers.
    
    Each format handler must implement:
    - extract(): Read text lines from a file
    - inject(): Write text lines to a file
    
    Handlers may also implement:
    - supports_original(): Whether format can store original lines
    - get_metadata(): Extract format-specific metadata
    """
    
    # Format identifier (e.g., "txt", "json", "rpgmaker_mv")
    format_id: str = ""
    
    # File extensions this handler supports
    extensions: Tuple[str, ...] = ()
    
    # Human-readable description
    description: str = ""
    
    # Whether this format can store original + translated pairs
    supports_pairs: bool = False
    
    @abstractmethod
    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract text lines from a file.
        
        Args:
            path: Path to the file to read.
            encoding: Text encoding.
            
        Returns:
            List of text lines.
        """
        pass
    
    @abstractmethod
    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8"
    ) -> None:
        """Write text lines to a file.
        
        Args:
            path: Path to write the file.
            lines: Translated/processed lines to write.
            original_lines: Optional original lines (for pair formats).
            encoding: Text encoding.
        """
        pass
    
    def supports_original(self) -> bool:
        """Whether this format can store original lines alongside translations."""
        return self.supports_pairs
    
    def get_metadata(self, path: Path) -> Dict[str, Any]:
        """Extract format-specific metadata from a file.
        
        Override in subclasses to provide format-specific info.
        """
        return {
            "format": self.format_id,
            "path": str(path),
            "exists": path.exists(),
        }


class FormatRegistry:
    """Registry for file format handlers.
    
    Provides handler lookup by format ID or file extension.
    """
    
    def __init__(self) -> None:
        self._handlers: Dict[str, FormatHandler] = {}
        self._extension_map: Dict[str, str] = {}
    
    def register(self, handler: FormatHandler) -> None:
        """Register a format handler.
        
        Args:
            handler: FormatHandler instance to register.
        """
        self._handlers[handler.format_id] = handler
        for ext in handler.extensions:
            self._extension_map[ext.lower()] = handler.format_id
    
    def get(self, format_id: str) -> Optional[FormatHandler]:
        """Get handler by format ID.
        
        Args:
            format_id: Format identifier (e.g., "txt", "json").
            
        Returns:
            FormatHandler or None if not found.
        """
        return self._handlers.get(format_id.lower())
    
    def get_by_extension(self, ext: str) -> Optional[FormatHandler]:
        """Get handler by file extension.
        
        Args:
            ext: File extension (e.g., ".txt", ".json").
            
        Returns:
            FormatHandler or None if not found.
        """
        ext_lower = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        format_id = self._extension_map.get(ext_lower)
        if format_id:
            return self._handlers.get(format_id)
        return None
    
    def get_for_path(self, path: Path) -> Optional[FormatHandler]:
        """Get handler for a file path based on extension.
        
        Args:
            path: File path.
            
        Returns:
            FormatHandler or None if not found.
        """
        return self.get_by_extension(path.suffix)
    
    def list_formats(self) -> List[Dict[str, Any]]:
        """List all registered formats with their info."""
        result = []
        for format_id, handler in sorted(self._handlers.items()):
            result.append({
                "id": format_id,
                "extensions": handler.extensions,
                "description": handler.description,
                "supports_pairs": handler.supports_pairs,
            })
        return result
    
    def list_extensions(self) -> List[str]:
        """List all supported file extensions."""
        return sorted(self._extension_map.keys())


# Global registry instance
_registry: Optional[FormatRegistry] = None


def get_registry() -> FormatRegistry:
    """Get the global format registry, initializing if needed."""
    global _registry
    if _registry is None:
        _registry = FormatRegistry()
        _load_handlers()
    return _registry


def _load_handlers() -> None:
    """Load all format handlers into the registry."""
    global _registry
    if _registry is None:
        return  # Should not happen, but guard against it
        
    from . import simple
    
    # Register simple format handlers
    for handler in simple.get_handlers():
        _registry.register(handler)
    
    # Register HTML handlers (optional - requires beautifulsoup4)
    try:
        from . import html
        for handler in html.get_handlers():
            _registry.register(handler)
    except ImportError:
        pass  # beautifulsoup4 not installed
    
    # Register Markdown handler
    try:
        from . import markdown
        for handler in markdown.get_handlers():
            _registry.register(handler)
    except ImportError:
        pass

    # Register lenient JSON handler (JSON5 / JSONC)
    try:
        from . import json_lenient
        for handler in json_lenient.get_handlers():
            _registry.register(handler)
    except ImportError:
        pass

    # Register Translator++ handler
    try:
        from . import translator_plus
        for handler in translator_plus.get_handlers():
            _registry.register(handler)
    except ImportError:
        pass

    # Future: register rpgmaker and document handlers
    # from . import rpgmaker, document


def get_handler(format_id_or_ext: str) -> Optional[FormatHandler]:
    """Get a format handler by ID or extension.
    
    Args:
        format_id_or_ext: Format ID (e.g., "txt") or extension (e.g., ".txt").
        
    Returns:
        FormatHandler or None if not found.
    """
    registry = get_registry()
    
    # Try as format ID first
    handler = registry.get(format_id_or_ext)
    if handler:
        return handler
    
    # Try as extension
    return registry.get_by_extension(format_id_or_ext)


# ---------------------------------------------------------------------------
# Phase 53 — Parser Script Registry
# ---------------------------------------------------------------------------

class ParserRegistry:
    """Registry for :class:`ParserScript` implementations.

    Provides lookup by parser name and auto-detection for file paths.
    """

    def __init__(self) -> None:
        from .parser_base import ParserScript
        self._parsers: Dict[str, "ParserScript"] = {}

    def register(self, parser: "ParserScript") -> None:
        """Register a parser script.

        Args:
            parser: ParserScript instance to register.
        """
        self._parsers[parser.name.lower()] = parser

    def get(self, name: str) -> Optional["ParserScript"]:
        """Lookup parser by name (case-insensitive).

        Args:
            name: Parser name.

        Returns:
            ParserScript or None.
        """
        return self._parsers.get(name.lower())

    def detect(self, file_path: Path) -> Optional["ParserScript"]:
        """Auto-detect which parser handles *file_path*.

        Iterates registered parsers calling :meth:`can_handle` and returns
        the first match.  Returns ``None`` if no parser matches.
        """
        for parser in self._parsers.values():
            try:
                if parser.can_handle(file_path):
                    return parser
            except Exception:
                continue
        return None

    def list_parsers(self) -> List[Dict[str, Any]]:
        """List registered parsers with capability summaries."""
        return [p.info() for p in self._parsers.values()]


# Global parser registry singleton
_parser_registry: Optional[ParserRegistry] = None


def get_parser_registry() -> ParserRegistry:
    """Get the global parser registry, initializing if needed."""
    global _parser_registry
    if _parser_registry is None:
        _parser_registry = ParserRegistry()
        _load_parsers()
    return _parser_registry


def _load_parsers() -> None:
    """Load all parser scripts into the registry."""
    global _parser_registry
    if _parser_registry is None:
        return

    try:
        from .parser_rpgmaker import RpgMakerMVParser, RpgMakerMZParser
        _parser_registry.register(RpgMakerMVParser())
        _parser_registry.register(RpgMakerMZParser())
    except Exception:
        pass  # Graceful degradation

    try:
        from .LightVN import LightVNParser
        _parser_registry.register(LightVNParser())
    except Exception:
        pass  # Graceful degradation


def detect_parser(file_path: Path) -> Optional["ParserScript"]:
    """Convenience: auto-detect parser for *file_path*."""
    return get_parser_registry().detect(file_path)


def list_parser_names() -> List[str]:
    """Return display names of all registered parsers.

    Used by the GUI format combobox to dynamically include parser options.
    """
    registry = get_parser_registry()
    return [p["name"] for p in registry.list_parsers()]
