"""CherryAI Manifest Manager.

Unified state management using the manifest as the single source of truth.
Replaces the previous session-based system (gui/state/store.py).

TASK 19: All GUI state is now stored in the manifest file, including:
- Step state (status, last run, configuration)
- Project metadata (name, languages, style, characters)
- Translation data (lines with all progressive fields)
- Glossary entries (project-specific)
- Operations and mappings

Save Triggers (automatic):
- On close (WM_DELETE_WINDOW)
- On step change (tab switch)
- Before translation start
- During translation (after each batch)
- Autosave interval (TASK 29.1)

No manual save buttons required.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .mainhelper import Manifest, LineEntry, Operation

logger = logging.getLogger(__name__)


class _SafeManifestEncoder(json.JSONEncoder):
    """Defensive JSON encoder for manifest saves.

    Converts objects with a ``to_dict()`` method (e.g. ``TableRow``,
    ``FileDirEntry``) to plain dicts, and ``Path`` objects to strings.
    Prevents "is not JSON serializable" crashes during autosave if GUI
    objects leak into ``_manifest_data``.
    """

    def default(self, o: Any) -> Any:
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if isinstance(o, Path):
            return str(o)
        return super().default(o)


# Constants
MANIFEST_DIR = Path("Projects")
MANIFEST_EXT = ".CherryAI.json"
MANIFEST_VERSION = "3.2"  # TASK 38: Optimized format - removed redundant per-line fields

# Step definitions matching GUI step order
STEP_NAMES = [
    "Input",
    "Analysis",
    "Information",
    "Preprocessing",
    "Estimation",
    "Translation",
    "Postprocessing",
    "Wordwrap",
    "Quality Assurance",
    "Output",
]


@dataclass
class StepState:
    """State for a single workflow step.
    
    Replaces gui/state/store.py::StepState but stored in manifest.
    """
    
    name: str
    status: str = "not-started"  # not-started, in-progress, completed
    skipped: bool = False
    last_run: Optional[str] = None  # ISO timestamp
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "name": self.name,
            "status": self.status,
        }
        if self.skipped:
            result["skipped"] = True
        if self.last_run:
            result["last_run"] = self.last_run
        if self.data:
            result["data"] = self._serialize_value(self.data)
        return result
    
    def _serialize_value(self, value: Any) -> Any:
        """Recursively serialize a value for JSON."""
        if hasattr(value, "to_dict"):
            return value.to_dict()
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, Path):
            return str(value)
        else:
            return value
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StepState":
        """Deserialize from dictionary."""
        return cls(
            name=d.get("name", ""),
            status=d.get("status", "not-started"),
            skipped=d.get("skipped", False),
            last_run=d.get("last_run"),
            data=d.get("data", {}),
        )
    
    def reset(self) -> None:
        """Reset step to initial state."""
        self.status = "not-started"
        self.skipped = False
        self.last_run = None
        self.data = {}


@dataclass
class ProjectInfo:
    """Project metadata stored in manifest.
    
    Consolidates InformationStep metadata into manifest.
    """
    
    project_name: str = ""
    game_title: str = ""
    source_language: str = "Japanese"
    target_language: str = "English"
    genre: str = ""
    summary: str = ""
    style_preset: str = "natural"
    custom_style: str = ""
    tone_preset: str = "neutral"
    custom_tone: str = ""
    system_instructions: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (sparse - only non-empty values)."""
        result: Dict[str, Any] = {}
        if self.project_name:
            result["project_name"] = self.project_name
        if self.game_title:
            result["game_title"] = self.game_title
        if self.source_language != "Japanese":
            result["source_language"] = self.source_language
        if self.target_language != "English":
            result["target_language"] = self.target_language
        if self.genre:
            result["genre"] = self.genre
        if self.summary:
            result["summary"] = self.summary
        if self.style_preset != "natural":
            result["style_preset"] = self.style_preset
        if self.custom_style:
            result["custom_style"] = self.custom_style
        if self.tone_preset != "neutral":
            result["tone_preset"] = self.tone_preset
        if self.custom_tone:
            result["custom_tone"] = self.custom_tone
        if self.system_instructions:
            result["system_instructions"] = self.system_instructions
        return result
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProjectInfo":
        """Deserialize from dictionary."""
        return cls(
            project_name=d.get("project_name", ""),
            game_title=d.get("game_title", ""),
            source_language=d.get("source_language", "Japanese"),
            target_language=d.get("target_language", "English"),
            genre=d.get("genre", ""),
            summary=d.get("summary", ""),
            style_preset=d.get("style_preset", "natural"),
            custom_style=d.get("custom_style", ""),
            tone_preset=d.get("tone_preset", "neutral"),
            custom_tone=d.get("custom_tone", ""),
            system_instructions=d.get("system_instructions", d.get("custom_notes", "")),
        )


@dataclass
class GlossaryConfig:
    """Glossary configuration in manifest.
    
    Controls whether to use global glossary and stores project-specific entries.
    """
    
    use_global: bool = True  # Use global user/glossary.csv
    project_entries: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {"use_global": self.use_global}
        if self.project_entries:
            result["project_entries"] = self.project_entries
        return result
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GlossaryConfig":
        """Deserialize from dictionary."""
        return cls(
            use_global=d.get("use_global", True),
            project_entries=d.get("project_entries", []),
        )


@dataclass
class FileDirEntry:
    """File directory entry mapping line index ranges to source files.
    
    TASK 35.1: Maps global line indices to source files for input/output decoupling.
    TASK 38: Optimized - source_hint removed (use source_root + rel_path).
    
    Attributes:
        first_idx: First line index (inclusive, global 0-based).
        last_idx: Last line index (inclusive, global 0-based).
        format: File format (txt, csv, tsv, json, xlsx, rpgm, etc.).
        rel_path: Path relative to source_root (preserves folder structure).
        encoding: File encoding (utf-8, shift_jis, etc.).
        type: Content type classification (dialogue, menu?, menu, or empty).
    """
    
    first_idx: int
    last_idx: int
    format: str
    rel_path: str
    encoding: str = "utf-8"
    type: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (sparse format)."""
        result: Dict[str, Any] = {}
        if self.type:
            result["type"] = self.type
        result["first_idx"] = self.first_idx
        result["last_idx"] = self.last_idx
        result["format"] = self.format
        result["rel_path"] = self.rel_path
        if self.encoding != "utf-8":
            result["encoding"] = self.encoding
        return result
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FileDirEntry":
        """Deserialize from dictionary."""
        return cls(
            first_idx=d.get("first_idx", 0),
            last_idx=d.get("last_idx", 0),
            format=d.get("format", "txt"),
            rel_path=d.get("rel_path", ""),
            encoding=d.get("encoding", "utf-8"),
            type=d.get("type", ""),
        )
    
    @property
    def line_count(self) -> int:
        """Get number of lines in this file."""
        return self.last_idx - self.first_idx + 1
    
    def contains_idx(self, idx: int) -> bool:
        """Check if this entry contains the given line index."""
        return self.first_idx <= idx <= self.last_idx
    
    @property
    def filename(self) -> str:
        """Get just the filename from rel_path."""
        return Path(self.rel_path).name


class ManifestManager:
    """Centralized manifest operations for GUI state management.
    
    This class replaces SessionState from gui/state/store.py.
    All state is stored in a single manifest file per project.
    
    TASK 29.1: Added autosave functionality with configurable interval.
    Autosave runs in a background thread and only saves when dirty flag is set.
    
    Usage:
        manager = ManifestManager()
        manager.create_new("My Project", [Path("file.txt")])
        manager.set_step_data(3, {"metadata": {...}})
        manager.save()  # Called automatically on close/step change
        
        # Autosave (started automatically, can be disabled via INI)
        manager.start_autosave()  # Manual start if needed
        manager.stop_autosave()   # Manual stop if needed
    """
    
    def __init__(self) -> None:
        """Initialize manager with no loaded manifest."""
        self._manifest_path: Optional[Path] = None
        self._manifest_data: Dict[str, Any] = self._create_empty_manifest()
        self._dirty: bool = False
        self._change_listeners: List[Callable[[], None]] = []
        self._current_step: int = 0
        
        # TASK 29.1: Autosave configuration
        self._autosave_enabled: bool = True
        self._autosave_interval: int = 60  # seconds (matches [session] default)
        self._save_on_close: bool = True
        self._autosave_thread: Optional[threading.Thread] = None
        self._autosave_stop_event: threading.Event = threading.Event()
        self._autosave_lock: threading.Lock = threading.Lock()
        
        # Load autosave settings from INI
        self._load_autosave_settings()
        
        # Ensure manifests directory exists
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_autosave_settings(self) -> None:
        """Load autosave settings from ``[session]`` INI section.

        Reads the ``autosave`` (bool) and ``interval`` (int, seconds) keys
        that are set by Global Options → Session Settings.  ``save_on_close``
        is always ``True`` (no INI toggle — we never want to lose work).
        """
        try:
            from .ini_manager import get_default

            self._autosave_enabled = bool(
                get_default("session", "autosave", True, bool)
            )
            self._autosave_interval = int(
                get_default("session", "interval", 60, int) or 60
            )
            # save_on_close is always True — no user toggle needed
            self._save_on_close = True

            # Clamp interval to reasonable bounds (5-300 seconds)
            self._autosave_interval = max(5, min(300, self._autosave_interval))

            logger.debug(
                "Autosave settings: enabled=%s, interval=%ds, save_on_close=%s",
                self._autosave_enabled,
                self._autosave_interval,
                self._save_on_close,
            )
        except Exception as e:
            logger.warning("Failed to load autosave settings: %s", e)
    
    @property
    def autosave_enabled(self) -> bool:
        """Check if autosave is enabled."""
        return self._autosave_enabled
    
    @autosave_enabled.setter
    def autosave_enabled(self, value: bool) -> None:
        """Enable or disable autosave."""
        self._autosave_enabled = value
        if value and self._autosave_thread is None:
            self.start_autosave()
        elif not value:
            self.stop_autosave()
    
    @property
    def autosave_interval(self) -> int:
        """Get the autosave interval in seconds."""
        return self._autosave_interval
    
    @autosave_interval.setter
    def autosave_interval(self, value: int) -> None:
        """Set the autosave interval in seconds."""
        self._autosave_interval = max(5, min(300, value))
    
    @property
    def save_on_close(self) -> bool:
        """Check if save on close is enabled."""
        return self._save_on_close
    
    @save_on_close.setter
    def save_on_close(self, value: bool) -> None:
        """Enable or disable save on close."""
        self._save_on_close = value
    
    def start_autosave(self) -> None:
        """Start the autosave background thread.
        
        The thread will periodically check the dirty flag and save if needed.
        Safe to call multiple times - will not start duplicate threads.
        """
        if not self._autosave_enabled:
            logger.debug("Autosave disabled, not starting thread")
            return
        
        with self._autosave_lock:
            if self._autosave_thread is not None and self._autosave_thread.is_alive():
                logger.debug("Autosave thread already running")
                return
            
            self._autosave_stop_event.clear()
            self._autosave_thread = threading.Thread(
                target=self._autosave_loop,
                name="ManifestAutosave",
                daemon=True,  # Thread dies when main thread exits
            )
            self._autosave_thread.start()
            logger.info(
                "Started autosave thread (interval=%ds)", self._autosave_interval
            )
    
    def stop_autosave(self) -> None:
        """Stop the autosave background thread.
        
        Signals the thread to stop and waits for it to finish.
        Safe to call multiple times.
        """
        with self._autosave_lock:
            if self._autosave_thread is None:
                return
            
            self._autosave_stop_event.set()
            
            # Wait for thread to finish (with timeout)
            if self._autosave_thread.is_alive():
                self._autosave_thread.join(timeout=2.0)
            
            self._autosave_thread = None
            logger.info("Stopped autosave thread")
    
    def _autosave_loop(self) -> None:
        """Background thread loop for autosave.
        
        Runs until stop event is set. Checks dirty flag every interval
        and saves if manifest has unsaved changes.
        """
        logger.debug("Autosave loop started")
        
        while not self._autosave_stop_event.is_set():
            # Wait for interval or stop event
            if self._autosave_stop_event.wait(timeout=self._autosave_interval):
                # Stop event was set
                break
            
            # Check if we have unsaved changes
            if self._dirty and self._manifest_path is not None:
                logger.debug("Autosave triggered (dirty=%s)", self._dirty)
                try:
                    self.save()
                except Exception as e:
                    logger.error("Autosave failed: %s", e)
        
        logger.debug("Autosave loop ended")
    
    @property
    def is_loaded(self) -> bool:
        """Check if a manifest is currently loaded."""
        return self._manifest_path is not None
    
    @property
    def manifest_path(self) -> Optional[Path]:
        """Get the current manifest file path."""
        return self._manifest_path
    
    @property
    def project_name(self) -> str:
        """Get the project name from Information metadata."""
        meta = self.get_info_metadata()
        name = meta.get("project_name", "")
        if not name:
            # Fallback to manifest filename stem
            if self._manifest_path is not None:
                name = self._manifest_path.stem.replace(MANIFEST_EXT.replace(".", ""), "").rstrip(".")
        return name
    
    @property
    def current_step(self) -> int:
        """Get the current step index."""
        return self._current_step
    
    @current_step.setter
    def current_step(self, value: int) -> None:
        """Set the current step index."""
        if 0 <= value < len(STEP_NAMES):
            self._current_step = value
            self._manifest_data["current_step"] = value
            self._mark_dirty()
    
    @property
    def dirty(self) -> bool:
        """Check if there are unsaved changes."""
        return self._dirty
    
    def _create_empty_manifest(self) -> Dict[str, Any]:
        """Create an empty manifest structure with all v3.1 fields.
        
        TASK 21.2: Extended to include ALL fields needed by GUI and processing.
        TASK 35.1: Added filedir for input/output decoupling.
        Uses defaults from INI file via ini_manager.
        Defaults for system_instructions and summary are seeded at creation
        so that Steps 4/5 can operate without the Information tab being
        visited first.
        """
        now = datetime.utcnow().isoformat() + "Z"
        defaults = self._get_manifest_defaults()
        
        # Seed Information step metadata with default values.
        info_metadata = self._get_info_defaults()
        step_states: Dict[str, Any] = {}
        for name in STEP_NAMES:
            ss = StepState(name=name).to_dict()
            if name == "Information":
                ss["data"] = {"metadata": info_metadata}
            step_states[name] = ss
        
        return {
            # === Core Metadata ===
            "version": MANIFEST_VERSION,
            "created_at": now,
            "updated_at": now,
            
            # === Project Identity ===
            "current_step": 0,
            
            # === v3.2 Source Path Management (TASK 38) ===
            # source_root: Display-only folder name of the nearest common
            # ancestor.  NOT a resolvable path.  File resolution uses the
            # project's Original/ directory instead.
            "source_root": "",
            
            # === v3.1 File Directory (TASK 35.1) ===
            # Maps line index ranges to source files for input/output decoupling
            # TASK 38: rel_path is now relative to source_root, source_hint removed
            "filedir": [],
            
            # === v2.1 Processing Data (TASK 38: lines no longer need source_file) ===
            "lines": [],
            "operations": [],
            "mappings": {},
            "summary": "",
            "metadata": {},
            
            # === v3.0 Project Settings ===
            "characters": [],
            "code_patterns": [],
            "step_state": step_states,
            "glossary": GlossaryConfig().to_dict(),
            
            # === v3.0 Preprocessing Options ===
            "Deduplication": defaults.get("deduplication", True),
            "DeduplicationThreshold": defaults.get("deduplication_threshold", 1),
            "EllipsisCompression": defaults.get("ellipsis_compression", True),
            "SymbolConversion": defaults.get("symbol_conversion", True),
            "SpeakerNameReplacement": defaults.get("speaker_name_replacement", False),
            "CodeSpacingRules": defaults.get("code_spacing_rules", True),
            "ProtectCodePatterns": [],
            "CustomPlaceholders": [],
            "AnchorRemoval": [],
            
            # === v3.0 Estimation Data ===
            "InputLines": 0,
            "InputTokens": 0,
            "OutputTokens": 0,
            
            # === v3.0 Validation Rules ===
            "ValidationRules": {
                "PlaceholderPreservation": defaults.get("validation_placeholder_preservation", True),
                "AnchorPreservation": defaults.get("validation_anchor_preservation", True),
                "JapaneseCharacterDetection": defaults.get("validation_japanese_character_detection", True),
                "SpeakerFormat": defaults.get("validation_speaker_format", True),
                "QuoteBalance": defaults.get("validation_quote_balance", True),
                "EmptyTranslation": defaults.get("validation_empty_translation", True),
            },
            
            # === v3.1 Character/Word Validation (TASK 36.1) ===
            # Whitelist: allowed characters (empty = all allowed)
            # Blacklist: forbidden characters (checked after whitelist)
            # WordBlacklist: forbidden words/phrases (case-insensitive, whole word match)
            # AutofixMap: character replacements for auto-correction
            "CharacterWhitelist": defaults.get("character_whitelist", ""),
            "CharacterBlacklist": defaults.get("character_blacklist", ""),
            "WordBlacklist": self._parse_list_default(
                defaults.get("word_blacklist", "")
            ),
            "AutofixMap": self._parse_dict_default(
                defaults.get("autofix_map", "")
            ),
            
            # === v3.0 QA Options ===
            "QAOptions": {
                "RerunPolicy": defaults.get("qa_rerun_policy", "FailedOnly"),
                "MaxJapaneseChars": defaults.get("qa_max_japanese_chars", 4),
                "MaxLineLength": defaults.get("qa_max_line_length", 0),
            },
            
            # === v3.0 Request Options (passed to API client) ===
            "RequestOptions": {
                "Model": "",  # Uses global API model by default
                "Temperature": defaults.get("request_temperature", 0.2),
                "LinesPerChunk": defaults.get("request_lines_per_chunk", 30),
                "RetryStrategy": defaults.get("request_retry_strategy", "Batch"),
                "MaxRetries": defaults.get("request_max_retries", 3),
                "EnableRequestCaching": defaults.get("request_enable_caching", True),
                "LineByLineMode": defaults.get("request_line_by_line_mode", False),
                "Thinking": defaults.get("request_thinking", False),
                "ThinkingBudget": defaults.get("request_thinking_budget", 1000),
            },
            
            # === v3.0 Post Processing Options ===
            "PostProcessing": {
                "PlaceholderRecovery": defaults.get("post_placeholder_recovery", True),
                "BracketBalanceRecovery": defaults.get("post_bracket_balance_recovery", True),
                "QuoteBalanceRecovery": defaults.get("post_quote_balance_recovery", True),
                "WhitespaceNormalization": defaults.get("post_whitespace_normalization", True),
                "RestoreCodeCharacters": defaults.get("post_restore_code_characters", True),
                "RestoreLinebreaks": defaults.get("post_restore_linebreaks", True),
                "EnableSymbolConversion": defaults.get("post_enable_symbol_conversion", True),
                "FullwidthToHalfwidth": defaults.get("post_fullwidth_to_halfwidth", True),
                "FailureHandling": defaults.get("post_failure_handling", "flag"),
            },
            
            # === v3.0 Wordwrap Settings ===
            "WordwrapSettings": {
                "Mode": defaults.get("wordwrap_mode", "Manual"),
                "Width": defaults.get("wordwrap_width", 48),
                "BreakChar": defaults.get("wordwrap_break_char", ""),
                "MaxLines": defaults.get("wordwrap_max_lines", 4),
                "PreventOrphans": defaults.get("wordwrap_prevent_orphans", True),
                "PreferPunctuationBreaks": defaults.get("wordwrap_prefer_punctuation_breaks", True),
                "SpeakerHandling": defaults.get("wordwrap_speaker_handling", "Sameline"),
                "IgnorePatterns": self._parse_list_default(
                    defaults.get("wordwrap_ignore_patterns", "Angle,Square,Curly,En")
                ),
                "Typography": defaults.get("wordwrap_typography", "Western"),
            },
            
            # === v3.0 Output Format ===
            "OutputFormat": {
                "PreserveFolderStructure": defaults.get("output_preserve_folder_structure", True),
                "Format": "",  # Auto-detect from input
                "PairMode": defaults.get("output_pair_mode", "translated_only"),
                "Encoding": "",  # Auto-detect
                "FileNaming": defaults.get("output_file_naming", "subfolder"),
                "TextOption": defaults.get("output_text_option", "translated"),
                "OverwriteExistingFiles": defaults.get("output_overwrite_existing_files", False),
                "Backup": defaults.get("output_backup", "Timestamp"),
                "BackupExtension": defaults.get("output_backup_extension", ".bk"),
                "ExportManifestFile": defaults.get("output_export_manifest_file", False),
                "ExportProcessingLogs": defaults.get("output_export_processing_logs", False),
                "ExportGlossaryEntries": defaults.get("output_export_glossary_entries", False),
            },

            # === API Log ===
            "log": "",
        }
    
    def _get_manifest_defaults(self) -> Dict[str, Any]:
        """Get manifest defaults from INI file.
        
        Returns:
            Dictionary of default values for manifest fields.
        """
        try:
            from . import ini_manager
            return ini_manager.get_all_manifest_defaults()
        except ImportError:
            logger.warning("ini_manager not available, using builtin defaults")
            return self._get_builtin_defaults()
    
    def _get_builtin_defaults(self) -> Dict[str, Any]:
        """Get hardcoded defaults as fallback.
        
        Used when ini_manager is not available.
        """
        return {
            "project_name": "Project1",
            "title": "Title1",
            "genre": "fictional, nonfictional",
            "source_language": "Japanese",
            "target_language": "English",
            "summary": "[Summary of the Content]",
            "style_preset": "neutral",
            "tone_preset": "natural",
            "deduplication": True,
            "deduplication_threshold": 1,
            "ellipsis_compression": True,
            "symbol_conversion": True,
            "speaker_name_replacement": False,
            "code_spacing_rules": True,
            "validation_placeholder_preservation": True,
            "validation_anchor_preservation": True,
            "validation_japanese_character_detection": True,
            "validation_speaker_format": True,
            "validation_quote_balance": True,
            "validation_empty_translation": True,
            "qa_rerun_policy": "FailedOnly",
            "qa_max_japanese_chars": 4,
            "qa_max_line_length": 0,
            "request_temperature": 0.2,
            "request_lines_per_chunk": 30,
            "request_retry_strategy": "Batch",
            "request_max_retries": 3,
            "request_enable_caching": True,
            "request_line_by_line_mode": False,
            "request_thinking": False,
            "request_thinking_budget": 1000,
            "post_placeholder_recovery": True,
            "post_bracket_balance_recovery": True,
            "post_quote_balance_recovery": True,
            "post_whitespace_normalization": True,
            "post_restore_code_characters": True,
            "post_restore_linebreaks": True,
            "post_enable_symbol_conversion": True,
            "post_fullwidth_to_halfwidth": True,
            "post_failure_handling": "flag",
            "wordwrap_mode": "Manual",
            "wordwrap_width": 48,
            "wordwrap_break_char": "",
            "wordwrap_max_lines": 4,
            "wordwrap_prevent_orphans": True,
            "wordwrap_prefer_punctuation_breaks": True,
            "wordwrap_speaker_handling": "Sameline",
            "wordwrap_ignore_patterns": "Angle,Square,Curly,En",
            "wordwrap_typography": "Western",
            "output_preserve_folder_structure": True,
            "output_pair_mode": "translated_only",
            "output_file_naming": "subfolder",
            "output_text_option": "translated",
            "output_overwrite_existing_files": False,
            "output_backup": "Timestamp",
            "output_backup_extension": ".bk",
            "output_export_manifest_file": False,
            "output_export_processing_logs": False,
            "output_export_glossary_entries": False,
        }
    
    # _create_project_info_defaults removed — project_info is no longer a
    # top-level manifest key.  Metadata lives in step_state.Information.data.metadata.

    def _get_info_defaults(self) -> Dict[str, Any]:
        """Return default Information metadata seeded at manifest creation.

        Ensures that system_instructions, si_preset, summary, and other
        defaults are present in the manifest from the start so that
        Steps 4 (Costs) and 5 (Translation) can operate without
        requiring the Information tab to be visited first.
        """
        try:
            from . import ini_manager
            si_text = ini_manager.get_default_text("SystemInstruction")
            summary_text = ini_manager.get_default_text("Summary")
        except ImportError:
            si_text = ""
            summary_text = ""
        return {
            "source_language": "Japanese",
            "target_language": "English",
            "system_instructions": si_text,
            "si_preset": "Default",
            "io_examples": "disabled",
            "summary": summary_text,
            "style_preset": "Natural",
            "tone_preset": "Neutral",
            "system_instructions_enabled": True,
            "glossary_enabled": True,
            "code_database_enabled": True,
            "genre_enabled": False,
            "summary_enabled": False,
            "style_enabled": False,
            "tone_enabled": False,
        }
    
    def _parse_list_default(self, value: Any) -> list:
        """Parse a comma-separated string into a list.
        
        Args:
            value: String like "A,B,C" or already a list.
            
        Returns:
            List of strings.
        """
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return []
    
    def _parse_dict_default(self, value: Any) -> Dict[str, str]:
        """Parse a string into a dictionary for autofix mappings.
        
        TASK 36.1: Supports two formats:
        - Comma-separated pairs: "a=b,c=d" -> {"a": "b", "c": "d"}
        - JSON dict: '{"a": "b"}' -> {"a": "b"}
        
        Args:
            value: String like "a=b,c=d" or JSON dict, or already a dict.
            
        Returns:
            Dictionary mapping offending chars to replacements.
        """
        if isinstance(value, dict):
            return value
        if not isinstance(value, str) or not value:
            return {}
        
        # Try JSON format first
        value = value.strip()
        if value.startswith("{"):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                pass
        
        # Parse comma-separated key=value pairs
        result: Dict[str, str] = {}
        for pair in value.split(","):
            if "=" in pair:
                key, val = pair.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key:
                    result[key] = val
        return result
    
    def _mark_dirty(self) -> None:
        """Mark the manifest as having unsaved changes."""
        self._dirty = True
        self._manifest_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._notify_listeners()
    
    def _notify_listeners(self) -> None:
        """Notify all change listeners."""
        for listener in self._change_listeners:
            try:
                listener()
            except Exception as e:
                logger.warning("Change listener error: %s", e)
    
    def add_change_listener(self, listener: Callable[[], None]) -> None:
        """Add a listener for state changes."""
        self._change_listeners.append(listener)
    
    def remove_change_listener(self, listener: Callable[[], None]) -> None:
        """Remove a change listener."""
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)
    
    # ========================== Source Path Helpers (TASK 38) ========================== #
    
    @property
    def source_root(self) -> str:
        """Folder name (display-only) of the common source ancestor."""
        return self._manifest_data.get("source_root", "")
    
    @source_root.setter
    def source_root(self, value: str) -> None:
        """Set the source root folder name."""
        self._manifest_data["source_root"] = value
        self._mark_dirty()
    
    def resolve_file_path(self, rel_path: str) -> Path:
        """Resolve a relative path to an absolute path.

        Uses the project's ``Original/`` directory as the base — this is
        where source files are copied on first load.  ``source_root`` is
        a display-only folder name and is **not** used for resolution.

        Args:
            rel_path: Path relative to the original files directory
                (e.g. ``"battle_on.json"`` or ``"event/arena/arena_01.json"``).

        Returns:
            Absolute Path inside ``<project>/Original/``.
        """
        return self.get_original_dir() / rel_path
    
    def make_relative_path(self, abs_path: Path) -> str:
        """Convert an absolute path to a path relative to Original/ dir.
        
        Args:
            abs_path: Absolute file path.
            
        Returns:
            Relative path string, or filename if path is outside Original/.
        """
        orig_dir = self.get_original_dir()
        try:
            return str(abs_path.relative_to(orig_dir))
        except ValueError:
            return abs_path.name
    
    def get_file_for_line_idx(self, idx: int) -> Optional[Dict[str, Any]]:
        """Get the filedir entry for a given line index.
        
        Args:
            idx: Global line index (0-based).
            
        Returns:
            Filedir entry dict or None if not found.
        """
        for entry in self._manifest_data.get("filedir", []):
            first = entry.get("first_idx", 0)
            last = entry.get("last_idx", 0)
            if first <= idx <= last:
                return entry
        return None
    
    def get_source_file_for_line(self, idx: int) -> Optional[Path]:
        """Get the absolute source file path for a given line index.
        
        Args:
            idx: Global line index (0-based).
            
        Returns:
            Absolute Path to source file, or None if not found.
        """
        entry = self.get_file_for_line_idx(idx)
        if entry:
            return self.resolve_file_path(entry.get("rel_path", ""))
        return None
    
    @staticmethod
    def _compute_full_root(source_files: List[Any]) -> str:
        """Compute the full common root path from a list of source files.

        Used internally during project creation for building relative paths.
        Not stored in the manifest — only the folder name is persisted.

        Args:
            source_files: List of source file paths (str or Path).

        Returns:
            Full common ancestor directory as string, or empty string.
        """
        if not source_files:
            return ""

        paths = [Path(f) if isinstance(f, str) else f for f in source_files]

        if len(paths) == 1:
            return str(paths[0].parent)

        import os
        try:
            common = os.path.commonpath([str(p) for p in paths])
            return common
        except ValueError:
            return ""

    @staticmethod
    def compute_source_root(source_files: List[Any]) -> str:
        """Return the folder name (last path component) of the common root.

        This is the value stored in ``source_root`` — a short, portable,
        privacy-safe identifier.  It is **not** a resolvable path.

        Args:
            source_files: List of source file paths (str or Path).

        Returns:
            Folder name string, or empty string if no files.
        """
        full = ManifestManager._compute_full_root(source_files)
        if not full:
            return ""
        return Path(full).name
    
    # ========================== Project Operations ========================== #
    
    def create_new(self, project_name: str, source_files: List[Path]) -> Path:
        """Create a new project manifest.
        
        Args:
            project_name: Name for the project (used in filename)
            source_files: List of source file paths
            
        Returns:
            Path to the created manifest file
            
        TASK 29.1: Starts autosave thread after creation.
        TASK 38: Uses optimized format with source_root and compact lines.
        """
        # Sanitize project name for filename
        safe_name = "".join(c for c in project_name if c.isalnum() or c in " -_").strip()
        if not safe_name:
            safe_name = "Untitled"
        
        # Create manifest path
        self._manifest_path = MANIFEST_DIR / f"{safe_name}{MANIFEST_EXT}"
        
        # Handle duplicate names
        counter = 1
        while self._manifest_path.exists():
            self._manifest_path = MANIFEST_DIR / f"{safe_name}_{counter}{MANIFEST_EXT}"
            counter += 1
        
        # Initialize manifest data
        self._manifest_data = self._create_empty_manifest()
        
        # Store project_name in Information metadata (single source of truth)
        self.set_info_metadata_field("project_name", project_name)
        
        # Compute full common root (for building rel_paths) and folder name
        full_root = self._compute_full_root(source_files)
        folder_name = Path(full_root).name if full_root else ""
        self._manifest_data["source_root"] = folder_name
        
        # Initialize lines and filedir using the *full* root for rel_paths
        self._initialize_lines_from_files(source_files, full_root)
        
        # Initialize API log for this project
        log_filename = self._manifest_path.stem + ".api_log.jsonl"
        self._manifest_data["log"] = log_filename
        log_path = self._manifest_path.parent / log_filename
        try:
            from .api_log import reset_api_log_store
            reset_api_log_store(log_path)
        except Exception:
            logger.debug("API log store init skipped")

        self._dirty = True
        self._current_step = 0
        self.save()
        
        # Start autosave thread
        self.start_autosave()
        
        logger.info("Created new manifest: %s", self._manifest_path)
        return self._manifest_path
    
    def _initialize_lines_from_files(
        self,
        source_files: List[Path],
        full_root: str = "",
    ) -> None:
        """Initialize lines array and filedir from source files.

        Args:
            source_files: Absolute paths to source files.
            full_root: Full common ancestor path used *only* to compute
                relative paths for filedir.  Not stored in the manifest.

        TASK 38: Lines no longer store source_file - use filedir for lookup.
        """
        lines: List[Dict[str, Any]] = []
        filedir: List[Dict[str, Any]] = []
        idx = 0
        
        for file_path in source_files:
            try:
                first_idx = idx
                content = file_path.read_text(encoding="utf-8")
                file_lines = content.split("\n")
                
                for line_text in file_lines:
                    # TASK 38: Compact line format - only idx and orig
                    lines.append({
                        "idx": idx,
                        "orig": line_text,
                    })
                    idx += 1
                
                # Build filedir entry — rel_path relative to full_root
                if full_root:
                    try:
                        rel_path = str(file_path.relative_to(full_root))
                    except ValueError:
                        rel_path = file_path.name
                else:
                    rel_path = file_path.name
                
                # Detect format from extension
                ext = file_path.suffix.lower()
                format_map = {
                    ".txt": "txt", ".csv": "csv", ".tsv": "tsv",
                    ".json": "json", ".xlsx": "xlsx", ".html": "html",
                }
                file_format = format_map.get(ext, "txt")
                
                filedir.append({
                    "first_idx": first_idx,
                    "last_idx": idx - 1,
                    "format": file_format,
                    "rel_path": rel_path,
                })
                
            except Exception as e:
                logger.warning("Failed to read source file %s: %s", file_path, e)
        
        self._manifest_data["lines"] = lines
        self._manifest_data["filedir"] = filedir
    
    def load(self, manifest_path: Path) -> bool:
        """Load an existing manifest.
        
        Args:
            manifest_path: Path to the manifest file
            
        Returns:
            True if loaded successfully
            
        TASK 29.1: Starts autosave thread after loading.
        """
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Migrate older versions if needed
            data = self._migrate_manifest(data)
            
            self._manifest_path = manifest_path
            self._manifest_data = data
            
            self._current_step = data.get("current_step", 0)
            self._dirty = False

            # Load API log for this project
            log_filename = data.get("log", "")
            if log_filename:
                log_path = manifest_path.parent / log_filename
            else:
                log_filename = manifest_path.stem + ".api_log.jsonl"
                log_path = manifest_path.parent / log_filename
                self._manifest_data["log"] = log_filename
            try:
                from .api_log import reset_api_log_store
                store = reset_api_log_store(log_path)
                store.load()
            except Exception:
                logger.debug("API log store load skipped")
            
            # Start autosave thread
            self.start_autosave()
            
            logger.info("Loaded manifest: %s (v%s)", manifest_path, data.get("version", "?"))
            return True
            
        except Exception as e:
            logger.error("Failed to load manifest %s: %s", manifest_path, e)
            return False
    
    def _migrate_manifest(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate older manifest versions to v3.2.
        
        Handles migration from v1.x, v2.x, v3.0, and v3.1 manifests, preserving all 
        line data, operations, and settings.
        
        TASK 35.1: Adds filedir migration.
        TASK 38: v3.2 optimization - remove redundant fields, add source_root.
        """
        version = data.get("version", "1.0")
        
        # Handle v1.x, v2.x, v3.0 migrations
        if version.startswith("1.") or version.startswith("2.") or version == "3.0":
            logger.info("Migrating manifest from v%s to v%s", version, MANIFEST_VERSION)
            
            # Ensure all v3.0 fields exist
            if "step_state" not in data:
                data["step_state"] = {name: StepState(name=name).to_dict() for name in STEP_NAMES}
            
            # Migrate project_info from various old fields
            if "project_info" not in data or not data["project_info"]:
                metadata = data.get("metadata", {})
                old_project_info = data.get("project_info", {})
                
                # Build merged project info
                merged_info: Dict[str, Any] = {}
                
                # Get project name from various sources
                project_name = (
                    old_project_info.get("project_name") or
                    data.get("project_name") or
                    metadata.get("project_name") or
                    ""
                )
                if not project_name:
                    # Derive from source_file or origin_file
                    source = data.get("source_file") or data.get("origin_file") or ""
                    if source:
                        merged_info["project_name"] = Path(source).stem
                else:
                    merged_info["project_name"] = project_name
                
                # Migrate languages
                if "language_source" in data:
                    merged_info["source_language"] = data["language_source"]
                if "language_target" in data:
                    merged_info["target_language"] = data["language_target"]
                
                # Merge any existing old metadata
                for key, value in old_project_info.items():
                    if key not in merged_info and value:
                        merged_info[key] = value
                for key, value in metadata.items():
                    if key not in merged_info and value and key not in ("auto_created", "created_utc"):
                        merged_info[key] = value
                
                data["project_info"] = merged_info
            
            # Also set top-level project_name for easy access
            if not data.get("project_name"):
                data["project_name"] = data.get("project_info", {}).get("project_name", "")
            
            if "glossary" not in data:
                data["glossary"] = GlossaryConfig().to_dict()
            
            if "current_step" not in data:
                data["current_step"] = 0
            
            # Migrate source files - handle both singular and plural
            if "source_files" not in data:
                # v2.0 uses 'source_file', older uses 'origin_file'
                source_file = data.get("source_file") or data.get("origin_file")
                if source_file:
                    data["source_files"] = [source_file]
                else:
                    data["source_files"] = []
            
            if "characters" not in data:
                data["characters"] = []
            
            if "code_patterns" not in data:
                data["code_patterns"] = []
            
            # Ensure lines exist - v2.0 should already have them
            if "lines" not in data:
                data["lines"] = []
            
            # Ensure operations exist
            if "operations" not in data:
                data["operations"] = []
            
            # Ensure mappings exist
            if "mappings" not in data:
                data["mappings"] = {}
            
            # Copy essential timestamps
            if "created_at" not in data:
                if "metadata" in data and "created_utc" in data["metadata"]:
                    data["created_at"] = data["metadata"]["created_utc"]
                else:
                    data["created_at"] = datetime.utcnow().isoformat() + "Z"
            
            if "updated_at" not in data:
                data["updated_at"] = datetime.utcnow().isoformat() + "Z"
            
            # TASK 35.1: Migrate filedir
            # Build filedir from lines if not present (backward compatibility)
            if "filedir" not in data:
                data["filedir"] = self._build_filedir_from_legacy(data)
            
            # Also run v3.1→v3.2 optimization
            version = "3.1"
        
        # TASK 38: v3.1 → v3.2 optimization
        # Remove redundant source_file from lines, store source_root as folder name
        if version == "3.1":
            logger.info("Optimizing manifest from v3.1 to v3.2")
            
            # Compute full common root (for building rel_paths) and folder name
            source_files = data.get("source_files", [])
            full_root = self._compute_full_root(source_files) if source_files else ""
            folder_name = Path(full_root).name if full_root else ""
            data["source_root"] = folder_name
            
            # Update filedir entries — remove source_hint, make rel_path relative
            filedir = data.get("filedir", [])
            for entry in filedir:
                if "source_hint" in entry:
                    del entry["source_hint"]
                rel_path = entry.get("rel_path", "")
                if full_root and rel_path:
                    try:
                        rel_path_obj = Path(rel_path)
                        if rel_path_obj.is_absolute():
                            rel_path = str(rel_path_obj.relative_to(full_root))
                            entry["rel_path"] = rel_path
                    except ValueError:
                        pass
            
            # Remove source_file from all line entries (compact format)
            lines = data.get("lines", [])
            for line in lines:
                if "source_file" in line:
                    del line["source_file"]
            
            # Remove source_files array (no longer needed)
            data.pop("source_files", None)
            
            data["version"] = MANIFEST_VERSION
        
        # TASK 71: Strip redundant step_state arrays.
        # all_lines, processed_lines, postprocessed_lines duplicate lines[].orig /
        # prepro / postpro.  files duplicates filedir[].  Remove them on load so
        # the next save produces a compact manifest.
        _REDUNDANT_STEP_KEYS: Dict[str, List[str]] = {
            "Input": ["all_lines", "files"],
            "Preprocessing": ["processed_lines"],
            "Postprocessing": ["postprocessed_lines"],
        }
        step_state = data.get("step_state", {})
        for step_name, keys in _REDUNDANT_STEP_KEYS.items():
            step_entry = step_state.get(step_name, {})
            step_data = step_entry.get("data", {})
            for key in keys:
                if key in step_data:
                    logger.debug("Stripping redundant key '%s' from %s step_data",
                                 key, step_name)
                    del step_data[key]
        
        return data
    
    def _build_filedir_from_legacy(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build filedir entries from legacy manifest data.
        
        TASK 35.1: For backward compatibility when loading older manifests
        that don't have filedir.
        TASK 38: v3.2 format - no source_hint, rel_path relative to source_root.
        
        Args:
            data: Legacy manifest data.
            
        Returns:
            List of filedir entry dictionaries.
        """
        lines = data.get("lines", [])
        source_files = data.get("source_files", [])
        source_root = data.get("source_root", "")
        file_format = data.get("format", "txt")
        
        if not lines:
            return []
        
        if not source_files:
            # No source file info - create single entry for all lines
            source_file = data.get("source_file") or data.get("origin_file") or "unknown.txt"
            rel_path = Path(source_file).name
            if source_root:
                try:
                    rel_path = str(Path(source_file).relative_to(source_root))
                except ValueError:
                    pass
            return [{
                "first_idx": 0,
                "last_idx": len(lines) - 1,
                "format": file_format,
                "rel_path": rel_path,
            }]
        
        # Group lines by source_file
        files_with_lines: Dict[str, List[int]] = {}
        for line in lines:
            source = line.get("source_file", source_files[0])
            idx = line.get("idx", 0)
            if source not in files_with_lines:
                files_with_lines[source] = []
            files_with_lines[source].append(idx)
        
        # Build filedir entries
        filedir: List[Dict[str, Any]] = []
        for source_file in source_files:
            indices = files_with_lines.get(source_file, [])
            if not indices:
                continue
            
            # Make rel_path relative to source_root
            rel_path = Path(source_file).name
            if source_root:
                try:
                    rel_path = str(Path(source_file).relative_to(source_root))
                except ValueError:
                    pass
            
            filedir.append({
                "first_idx": min(indices),
                "last_idx": max(indices),
                "format": file_format,
                "rel_path": rel_path,
            })
        
        return filedir
    
    def save(self) -> bool:
        """Save the manifest to disk atomically.

        Writes to a temporary file first, then replaces the real file via
        ``os.replace`` so readers never see a partially-written manifest.
        Uses ``deepcopy`` to prevent "dictionary changed size during
        iteration" when autosave runs while the main thread modifies data
        and a custom JSON encoder as safety net for objects with
        ``to_dict()`` (e.g. ``TableRow``, ``FileDirEntry``).

        Returns:
            True if saved successfully.
        """
        if self._manifest_path is None:
            logger.warning("Cannot save: no manifest path set")
            return False

        try:
            self._manifest_path.parent.mkdir(parents=True, exist_ok=True)

            # Snapshot to prevent concurrent modification
            data_snapshot = deepcopy(self._manifest_data)

            # Atomic write: temp file → rename
            tmp_path = self._manifest_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data_snapshot, f, ensure_ascii=False, indent=2,
                          cls=_SafeManifestEncoder)
                f.flush()
                os.fsync(f.fileno())

            os.replace(str(tmp_path), str(self._manifest_path))

            self._dirty = False

            # Also persist the API log
            try:
                from .api_log import get_api_log_store
                get_api_log_store().save()
            except Exception:
                logger.debug("API log save skipped")

            logger.debug("Saved manifest: %s", self._manifest_path)
            return True

        except Exception as e:
            logger.error("Failed to save manifest: %s", e)
            # Clean up temp file on failure
            try:
                tmp_path = self._manifest_path.with_suffix(".tmp")
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return False
    
    def close(self) -> None:
        """Close the current manifest.
        
        TASK 29.1: Respects save_on_close setting and stops autosave thread.
        """
        # Stop autosave thread first
        self.stop_autosave()
        
        # Save if dirty and save_on_close is enabled
        if self._dirty and self._save_on_close:
            self.save()
        
        # Clear API log store
        try:
            from .api_log import get_api_log_store
            store = get_api_log_store()
            store.save()
            store.clear()
        except Exception:
            logger.debug("API log store close skipped")

        self._manifest_path = None
        self._manifest_data = self._create_empty_manifest()
        self._dirty = False
        self._current_step = 0
    
    # ========================== Information Metadata Access ======================== #

    def get_info_metadata(self) -> Dict[str, Any]:
        """Get the Information step metadata dict (single source of truth).

        Returns a *reference* to the dict inside step_state so callers can
        mutate it directly (followed by ``_mark_dirty()``).  If the path
        does not exist yet it is created with safe defaults.
        """
        ss = self._manifest_data.setdefault("step_state", {})
        info = ss.setdefault(
            "Information",
            {"name": "Information", "status": "not-started"},
        )
        data = info.setdefault("data", {})
        meta = data.setdefault("metadata", {})
        return meta

    def set_info_metadata(self, metadata: Dict[str, Any]) -> None:
        """Replace the Information step metadata dict wholesale."""
        ss = self._manifest_data.setdefault("step_state", {})
        info = ss.setdefault(
            "Information",
            {"name": "Information", "status": "not-started"},
        )
        data = info.setdefault("data", {})
        data["metadata"] = metadata
        self._mark_dirty()

    def set_info_metadata_field(self, key: str, value: Any) -> None:
        """Set a single field inside Information metadata."""
        meta = self.get_info_metadata()
        meta[key] = value
        self._mark_dirty()

    def get_info_metadata_field(
        self, key: str, default: Any = ""
    ) -> Any:
        """Read a single field from Information metadata."""
        return self.get_info_metadata().get(key, default)

    # ========================== Step State Operations ========================== #
    
    def get_step_state(self, step_index: int) -> StepState:
        """Get state for a specific step.
        
        Args:
            step_index: Step index (0-9)
            
        Returns:
            StepState for the step
        """
        if step_index < 0 or step_index >= len(STEP_NAMES):
            raise ValueError(f"Invalid step index: {step_index}")
        
        step_name = STEP_NAMES[step_index]
        step_data = self._manifest_data.get("step_state", {}).get(step_name, {})
        
        if not step_data:
            return StepState(name=step_name)
        
        return StepState.from_dict(step_data)
    
    def set_step_state(self, step_index: int, state: StepState) -> None:
        """Set state for a specific step.
        
        Args:
            step_index: Step index (0-9)
            state: StepState to set
        """
        if step_index < 0 or step_index >= len(STEP_NAMES):
            raise ValueError(f"Invalid step index: {step_index}")
        
        step_name = STEP_NAMES[step_index]
        if "step_state" not in self._manifest_data:
            self._manifest_data["step_state"] = {}
        
        self._manifest_data["step_state"][step_name] = state.to_dict()
        self._mark_dirty()
    
    def get_step_data(self, step_index: int) -> Dict[str, Any]:
        """Get data dictionary for a step.
        
        Args:
            step_index: Step index (0-9)
            
        Returns:
            Step data dictionary
        """
        return self.get_step_state(step_index).data
    
    def set_step_data(self, step_index: int, data: Dict[str, Any]) -> None:
        """Set data dictionary for a step.
        
        Args:
            step_index: Step index (0-9)
            data: Data dictionary to set
        """
        state = self.get_step_state(step_index)
        state.data = data
        self.set_step_state(step_index, state)
    
    def update_step_data(self, step_index: int, key: str, value: Any) -> None:
        """Update a single key in step data.
        
        Args:
            step_index: Step index (0-9)
            key: Data key
            value: Value to set
        """
        state = self.get_step_state(step_index)
        state.data[key] = value
        self.set_step_state(step_index, state)
    
    def get_step_data_value(self, step_index: int, key: str, default: Any = None) -> Any:
        """Get a single value from step data.
        
        Args:
            step_index: Step index (0-9)
            key: Data key
            default: Default value if not found
            
        Returns:
            Value or default
        """
        return self.get_step_data(step_index).get(key, default)
    
    def set_step_status(self, step_index: int, status: str) -> None:
        """Set status for a step.
        
        Args:
            step_index: Step index (0-9)
            status: Status string ('not-started', 'in-progress', 'completed')
        """
        state = self.get_step_state(step_index)
        state.status = status
        if status == "completed":
            state.last_run = datetime.utcnow().isoformat() + "Z"
        self.set_step_state(step_index, state)
    
    def mark_step_done(self, step_index: int) -> None:
        """Mark a step as completed."""
        self.set_step_status(step_index, "completed")
    
    def mark_step_skipped(self, step_index: int) -> None:
        """Mark a step as skipped."""
        state = self.get_step_state(step_index)
        state.skipped = True
        state.status = "completed"
        self.set_step_state(step_index, state)

    def set_step_metrics(self, step_name: str, metrics: Dict[str, Any]) -> None:
        """Store utility metrics for a pipeline step.

        Merges *metrics* into the top-level manifest under the given
        *step_name* key (e.g. ``"Translation"``, ``"Postprocessing"``).

        Args:
            step_name: Canonical step identifier.
            metrics: Metric key-value pairs to store/update.
        """
        section = self._manifest_data.setdefault(step_name, {})
        section.update(metrics)
        self._mark_dirty()

    def get_step_metrics(self, step_name: str) -> Dict[str, Any]:
        """Retrieve stored utility metrics for a pipeline step.

        Args:
            step_name: Canonical step identifier.

        Returns:
            Copy of the metrics dict (empty dict if none stored).
        """
        from copy import deepcopy
        return deepcopy(self._manifest_data.get(step_name, {}))
    
    # ========================== Project Info Operations ========================== #
    
    def get_project_info(self) -> ProjectInfo:
        """Get project information from Information metadata."""
        data = self.get_info_metadata()
        return ProjectInfo.from_dict(data)
    
    def set_project_info(self, info: ProjectInfo) -> None:
        """Set project information into Information metadata."""
        meta = self.get_info_metadata()
        for key, value in info.to_dict().items():
            if value:  # Only write populated fields
                meta[key] = value
        self._mark_dirty()
    
    def update_project_info(self, **kwargs: Any) -> None:
        """Update specific project info fields in Information metadata."""
        meta = self.get_info_metadata()
        for key, value in kwargs.items():
            meta[key] = value
        self._mark_dirty()
    
    # ========================== Characters Operations ========================== #
    
    def get_characters(self) -> List[Dict[str, Any]]:
        """Get character list."""
        return self._manifest_data.get("characters", [])
    
    def set_characters(self, characters: List[Dict[str, Any]]) -> None:
        """Set character list."""
        self._manifest_data["characters"] = characters
        self._mark_dirty()
    
    def add_character(self, character: Dict[str, Any]) -> None:
        """Add a character."""
        if "characters" not in self._manifest_data:
            self._manifest_data["characters"] = []
        self._manifest_data["characters"].append(character)
        self._mark_dirty()
    
    # ========================== Code Patterns Operations ========================== #
    
    def get_code_patterns(self) -> List[Dict[str, Any]]:
        """Get code pattern list."""
        return self._manifest_data.get("code_patterns", [])
    
    def set_code_patterns(self, patterns: List[Dict[str, Any]]) -> None:
        """Set code pattern list."""
        self._manifest_data["code_patterns"] = patterns
        self._mark_dirty()
    
    # ========================== Glossary Operations ========================== #
    
    def get_glossary_config(self) -> GlossaryConfig:
        """Get glossary configuration."""
        data = self._manifest_data.get("glossary", {})
        return GlossaryConfig.from_dict(data)
    
    def set_glossary_config(self, config: GlossaryConfig) -> None:
        """Set glossary configuration."""
        self._manifest_data["glossary"] = config.to_dict()
        self._mark_dirty()
    
    def set_use_global_glossary(self, use_global: bool) -> None:
        """Set whether to use global glossary."""
        config = self.get_glossary_config()
        config.use_global = use_global
        self.set_glossary_config(config)
    
    def add_glossary_entry(self, entry: Dict[str, Any]) -> None:
        """Add a project-specific glossary entry."""
        config = self.get_glossary_config()
        config.project_entries.append(entry)
        self.set_glossary_config(config)
    
    # ========================== Lines Operations ========================== #
    
    def get_lines(self) -> List[Dict[str, Any]]:
        """Get all lines."""
        return self._manifest_data.get("lines", [])
    
    def set_lines(self, lines: List[Dict[str, Any]]) -> None:
        """Set all lines."""
        self._manifest_data["lines"] = lines
        self._mark_dirty()
    
    def get_line(self, idx: int) -> Optional[Dict[str, Any]]:
        """Get a line by index."""
        for line in self._manifest_data.get("lines", []):
            if line.get("idx") == idx:
                return line
        return None
    
    def get_all_orig_lines(self) -> List[str]:
        """Return the ``orig`` text for every line in index order.

        This replaces the legacy ``all_lines`` flat array that was
        previously duplicated in ``step_state.Input.data``.  All callers
        that need the original extracted text should use this method or
        the manifest ``lines[].orig`` field directly.
        """
        return [ln.get("orig", "") for ln in self._manifest_data.get("lines", [])]

    def set_line_field(self, idx: int, field: str, value: Any) -> None:
        """Set a field on a specific line.

        Only marks the manifest dirty when the value actually changes
        to prevent unnecessary autosave cycles.
        """
        lines = self._manifest_data.get("lines", [])
        for line in lines:
            if line.get("idx") == idx:
                if field in line and line[field] == value:
                    return  # No change
                line[field] = value
                self._mark_dirty()
                return
        # Line not found - create it
        lines.append({"idx": idx, field: value})
        self._mark_dirty()
    
    def update_translation(self, idx: int, translation: str) -> None:
        """Update translation for a line (called during translation)."""
        self.set_line_field(idx, "tl", translation)
    
    # ========================== Operations ========================== #
    
    def get_operations(self) -> List[Dict[str, Any]]:
        """Get operations list."""
        return self._manifest_data.get("operations", [])
    
    def set_operations(self, operations: List[Dict[str, Any]]) -> None:
        """Set operations list."""
        self._manifest_data["operations"] = operations
        self._mark_dirty()
    
    # ========================== Source Files ========================== #
    
    # source_files removed — use filedir + source_root instead.
    # Legacy callers that still call get_source_files/set_source_files will
    # get empty results / log warnings.

    def get_source_files(self) -> List[Path]:
        """Deprecated — source_files no longer stored. Use filedir."""
        logger.warning("get_source_files() is deprecated; use get_filedir()")
        return []

    def set_source_files(self, files: List[Path]) -> None:
        """Deprecated — source_files no longer stored. Use filedir."""
        logger.warning("set_source_files() is deprecated; use set_filedir()")
    
    # ========================== File Directory (TASK 35.1) ========================== #
    
    def get_filedir(self) -> List[FileDirEntry]:
        """Get file directory entries.
        
        Returns list of FileDirEntry objects mapping line index ranges to files.
        """
        entries = self._manifest_data.get("filedir", [])
        return [FileDirEntry.from_dict(e) for e in entries]
    
    def set_filedir(self, entries: List[FileDirEntry]) -> None:
        """Set file directory entries.
        
        Args:
            entries: List of FileDirEntry objects.
        """
        self._manifest_data["filedir"] = [e.to_dict() for e in entries]
        self._mark_dirty()
    
    def add_filedir_entry(self, entry: FileDirEntry) -> None:
        """Add a file directory entry.
        
        Args:
            entry: FileDirEntry to add.
        """
        if "filedir" not in self._manifest_data:
            self._manifest_data["filedir"] = []
        self._manifest_data["filedir"].append(entry.to_dict())
        self._mark_dirty()
    
    def clear_filedir(self) -> None:
        """Clear all file directory entries."""
        self._manifest_data["filedir"] = []
        self._mark_dirty()

    def remove_file(self, rel_path: str) -> bool:
        """Remove a file and its lines from the manifest, shifting subsequent indices.
        
        Args:
            rel_path: Relative path of the file to remove.
            
        Returns:
            True if removed, False if not found.
        """
        entries = self.get_filedir()
        target_entry = None
        target_index = -1
        for i, entry in enumerate(entries):
            if entry.rel_path == rel_path:
                target_entry = entry
                target_index = i
                break
                
        if not target_entry:
            return False
            
        line_count = target_entry.last_idx - target_entry.first_idx + 1
        
        # 1. Remove lines and shift existing
        new_lines = []
        for line in self._manifest_data.get("lines", []):
            idx = line.get("idx", 0)
            if target_entry.first_idx <= idx <= target_entry.last_idx:
                continue
            if idx > target_entry.last_idx:
                line["idx"] = idx - line_count
            new_lines.append(line)
        self._manifest_data["lines"] = new_lines
        
        # 2. Update subsequent filedir entries
        new_entries = []
        for i, entry in enumerate(entries):
            if i == target_index:
                continue
            if i > target_index:
                entry.first_idx -= line_count
                entry.last_idx -= line_count
            new_entries.append(entry)
            
        self.set_filedir(new_entries)
        
        # 3. Update total line counts
        if "metadata" in self._manifest_data:
            old_total = self._manifest_data["metadata"].get("total_lines", 0)
            if old_total >= line_count:
                self._manifest_data["metadata"]["total_lines"] = old_total - line_count
        
        self._mark_dirty()
        # Save immediately to prevent desync
        self.save()
        return True
    
    def get_filedir_entry_for_idx(self, idx: int) -> Optional[FileDirEntry]:
        """Get the FileDirEntry that contains the given line index.
        
        Args:
            idx: Line index to look up.
            
        Returns:
            FileDirEntry containing idx, or None if not found.
        """
        for entry_dict in self._manifest_data.get("filedir", []):
            entry = FileDirEntry.from_dict(entry_dict)
            if entry.contains_idx(idx):
                return entry
        return None
    
    def get_lines_for_filedir_entry(self, entry: FileDirEntry) -> List[Dict[str, Any]]:
        """Get all lines belonging to a FileDirEntry.
        
        Args:
            entry: FileDirEntry to get lines for.
            
        Returns:
            List of line dictionaries in the entry's index range.
        """
        lines = []
        for line in self._manifest_data.get("lines", []):
            idx = line.get("idx", -1)
            if entry.first_idx <= idx <= entry.last_idx:
                lines.append(line)
        return lines
    
    def get_project_dir(self) -> Path:
        """Get the project directory path.
        
        Returns path like Projects/{project_name}/ for storing Original/ and Patch/.
        """
        name = self.project_name or "Untitled"
        safe_name = "".join(c for c in name if c.isalnum() or c in " -_").strip()
        if not safe_name:
            safe_name = "Untitled"
        return MANIFEST_DIR / safe_name
    
    def get_original_dir(self) -> Path:
        """Get the Original/ directory path for copied source files.
        
        TASK 35.2: Returns Projects/{project_name}/Original/
        """
        return self.get_project_dir() / "Original"
    
    def get_patch_dir(self) -> Path:
        """Get the Patch/ directory path for output files.
        
        TASK 35.3: Returns Projects/{project_name}/Patch/
        """
        return self.get_project_dir() / "Patch"
    
    def copy_originals_to_project(
        self,
        source_paths: Optional[Dict[str, Path]] = None,
        force: bool = False,
    ) -> Dict[str, str]:
        """Copy source files into the project's Original/ directory.

        ``source_root`` is now a display-only folder name, so callers must
        provide the actual absolute paths via *source_paths*.

        Args:
            source_paths: Mapping of ``rel_path`` → absolute source ``Path``.
                If *None*, falls back to looking in ``step_state.Input.data.files``.
            force: If True, overwrite existing copies.

        Returns:
            Dict mapping original paths to copied paths.
        """
        import shutil

        filedir = self.get_filedir()
        if not filedir:
            logger.warning("No filedir entries to copy")
            return {}

        # Build source_paths from step_state.Input if not provided
        if source_paths is None:
            source_paths = self._build_source_paths_from_input()

        original_dir = self.get_original_dir()
        original_dir.mkdir(parents=True, exist_ok=True)

        copied_files: Dict[str, str] = {}

        for entry in filedir:
            abs_source = source_paths.get(entry.rel_path)
            if abs_source is None or not abs_source.exists():
                logger.warning("Source file not found for rel_path=%s", entry.rel_path)
                continue

            dest_path = original_dir / entry.rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if dest_path.exists() and not force:
                logger.debug("Original already exists: %s", dest_path)
                copied_files[str(abs_source)] = str(dest_path)
                continue

            try:
                shutil.copy2(abs_source, dest_path)
                copied_files[str(abs_source)] = str(dest_path)
                logger.info("Copied original: %s -> %s", abs_source.name, dest_path)
            except Exception as e:
                logger.error("Failed to copy %s: %s", abs_source, e)

        return copied_files

    def _build_source_paths_from_input(self) -> Dict[str, Path]:
        """Build rel_path → absolute-source-path map from Input step state.

        Falls back to matching filedir rel_paths against Input.data.files[].path.
        """
        result: Dict[str, Path] = {}
        ss = self._manifest_data.get("step_state", {})
        input_data = ss.get("Input", {}).get("data", {})
        files_list = input_data.get("files", [])

        filedir = self.get_filedir()
        # Build a quick lookup: filename → absolute path
        abs_by_name: Dict[str, Path] = {}
        for f in files_list:
            p = Path(f.get("path", ""))
            abs_by_name[p.name] = p
            # Also store by full path for exact matching
            abs_by_name[str(p)] = p

        for entry in filedir:
            rel = entry.rel_path
            # Try matching by filename (last component of rel_path)
            fname = Path(rel).name
            if fname in abs_by_name:
                result[rel] = abs_by_name[fname]
            elif rel in abs_by_name:
                result[rel] = abs_by_name[rel]

        return result
    
    def get_original_file_path(self, entry: FileDirEntry) -> Path:
        """Get the path to the copied original file for a filedir entry.
        
        TASK 35.2: Returns the path in Original/ directory.
        
        Args:
            entry: FileDirEntry to get original path for.
            
        Returns:
            Path to the original file in Original/ directory.
        """
        return self.get_original_dir() / entry.rel_path
    
    def get_patch_file_path(self, entry: FileDirEntry) -> Path:
        """Get the output path in Patch/ directory for a filedir entry.
        
        TASK 35.3: Returns the path where the translated file should be written.
        
        Args:
            entry: FileDirEntry to get patch path for.
            
        Returns:
            Path to the output file in Patch/ directory.
        """
        return self.get_patch_dir() / entry.rel_path
    
    def has_original_copies(self) -> bool:
        """Check if original files have been copied to the project.
        
        Returns:
            True if Original/ directory exists and has files.
        """
        original_dir = self.get_original_dir()
        if not original_dir.exists():
            return False
        return any(original_dir.iterdir())
    
    def build_filedir_from_files(
        self,
        file_infos: List[Dict[str, Any]],
    ) -> List[FileDirEntry]:
        """Build filedir entries from a list of file information.
        
        Args:
            file_infos: List of dicts with keys:
                - path: Path to file (absolute)
                - format: File format (txt, csv, etc.)
                - line_count: Number of lines
                - encoding: File encoding (optional, defaults to utf-8)
                
        Returns:
            List of FileDirEntry objects covering all files.
        """
        entries: List[FileDirEntry] = []
        current_idx = 0
        
        # Determine common base path for relative paths
        paths = [Path(f["path"]) for f in file_infos]
        base_path = self._find_common_base(paths) if paths else Path.cwd()
        
        for file_info in file_infos:
            file_path = Path(file_info["path"])
            line_count = file_info.get("line_count", 0)
            
            if line_count == 0:
                continue
                
            # Calculate relative path from common base
            try:
                rel_path = file_path.relative_to(base_path)
            except ValueError:
                # If can't make relative, use just filename
                rel_path = Path(file_path.name)
            
            # TASK 38: v3.2 - no source_hint, rel_path is relative to source_root
            entry = FileDirEntry(
                first_idx=current_idx,
                last_idx=current_idx + line_count - 1,
                format=file_info.get("format", "txt"),
                rel_path=str(rel_path),
                encoding=file_info.get("encoding", "utf-8"),
                type=file_info.get("type", ""),
            )
            entries.append(entry)
            current_idx += line_count
        
        return entries
    
    def _find_common_base(self, paths: List[Path]) -> Path:
        """Find the common base directory for a list of paths.
        
        Args:
            paths: List of file paths.
            
        Returns:
            Common parent directory.
        """
        if not paths:
            return Path.cwd()
        
        if len(paths) == 1:
            return paths[0].parent
        
        # Get all parts for each path
        parts_list = [list(p.resolve().parts) for p in paths]
        
        # Find common prefix
        common_parts: List[str] = []
        for parts in zip(*parts_list):
            if len(set(parts)) == 1:
                common_parts.append(parts[0])
            else:
                break
        
        if not common_parts:
            return Path.cwd()
        
        return Path(*common_parts)
    
    # ========================== Integration with mainhelper Manifest ========================== #
    
    def import_from_mainhelper_manifest(self, manifest: "Manifest") -> None:
        """Import data from a mainhelper.py Manifest into this project manifest.
        
        This bridges the processing manifest (mainhelper.Manifest) with the
        project manifest (ManifestManager). Called after processing to persist
        line data, operations, and mappings.
        
        Args:
            manifest: mainhelper.Manifest instance with processing results
        """
        from .mainhelper import Manifest as MainhelperManifest
        
        if not isinstance(manifest, MainhelperManifest):
            logger.warning("Expected mainhelper.Manifest, got %s", type(manifest))
            return
        
        # Import lines array
        if manifest.lines:
            lines_data = [line.to_dict() for line in manifest.lines]
            self._manifest_data["lines"] = lines_data
        
        # Import operations
        if manifest.operations:
            ops_data = [op.__dict__ for op in manifest.operations]
            self._manifest_data["operations"] = ops_data
        
        # Import mappings
        if manifest.mappings:
            self._manifest_data["mappings"] = manifest.mappings
        
        # Import metadata (but don't overwrite project info)
        if manifest.metadata:
            # Store processing metadata separately
            self._manifest_data.setdefault("processing_metadata", {})
            self._manifest_data["processing_metadata"].update(manifest.metadata)
        
        # Track origin file
        if manifest.origin_file:
            if "source_files" not in self._manifest_data:
                self._manifest_data["source_files"] = []
            if manifest.origin_file not in self._manifest_data["source_files"]:
                self._manifest_data["source_files"].append(manifest.origin_file)
        
        self._mark_dirty()
        logger.info("Imported %d lines from mainhelper manifest", len(manifest.lines))
    
    def export_to_mainhelper_manifest(self) -> "Manifest":
        """Export data to a mainhelper.py Manifest for processing.
        
        Creates a new Manifest instance from the project manifest data,
        suitable for use with Processor.
        
        Returns:
            mainhelper.Manifest instance ready for processing
        """
        from .mainhelper import Manifest as MainhelperManifest, LineEntry, Operation
        
        # Create new manifest
        manifest = MainhelperManifest(
            summary=self._manifest_data.get("summary", ""),
            metadata=self._manifest_data.get("processing_metadata", {}),
            operations=[],
            mappings=self._manifest_data.get("mappings", {}),
        )
        
        # Import operations
        for op_data in self._manifest_data.get("operations", []):
            manifest.operations.append(Operation(**op_data))
        
        # Import lines
        for line_data in self._manifest_data.get("lines", []):
            entry = LineEntry.from_dict(line_data)
            manifest.lines.append(entry)
        
        # Set origin file
        source_files = self._manifest_data.get("source_files", [])
        if source_files:
            manifest.origin_file = source_files[0]
        
        return manifest
    
    # ========================== Settings Access (TASK 21.3) ========================== #
    
    def get_request_options(self) -> Dict[str, Any]:
        """Get request options for API client.
        
        Returns settings in format expected by api_client functions:
        - Model: Model name/identifier
        - Temperature: Sampling temperature
        - LinesPerChunk: Lines per translation chunk
        - RetryStrategy: How to handle failures
        - MaxRetries: Maximum retry attempts
        - EnableRequestCaching: Cache responses
        - LineByLineMode: Translate line by line
        - Thinking: Enable thinking mode
        - ThinkingBudget: Token budget for thinking
        """
        return deepcopy(self._manifest_data.get("RequestOptions", {
            "Model": "",
            "Temperature": 0.2,
            "LinesPerChunk": 30,
            "RetryStrategy": "Batch",
            "MaxRetries": 3,
            "EnableRequestCaching": True,
            "LineByLineMode": False,
            "Thinking": False,
            "ThinkingBudget": 1000,
        }))
    
    def set_request_options(self, options: Dict[str, Any]) -> None:
        """Set request options."""
        self._manifest_data["RequestOptions"] = options
        self._mark_dirty()
    
    def get_preprocessing_options(self) -> Dict[str, Any]:
        """Get preprocessing options for preprocess step.
        
        Returns flat dict of preprocessing settings:
        - Deduplication: Enable deduplication
        - DeduplicationThreshold: Similarity threshold
        - EllipsisCompression: Compress ellipsis
        - SymbolConversion: Convert symbols
        - SpeakerNameReplacement: Replace speaker names
        - CodeSpacingRules: Apply code spacing
        - ProtectCodePatterns: Patterns to protect
        - CustomPlaceholders: Custom placeholder patterns
        - AnchorRemoval: Anchors to remove
        """
        return {
            "Deduplication": self._manifest_data.get("Deduplication", True),
            "DeduplicationThreshold": self._manifest_data.get("DeduplicationThreshold", 1),
            "EllipsisCompression": self._manifest_data.get("EllipsisCompression", True),
            "SymbolConversion": self._manifest_data.get("SymbolConversion", True),
            "SpeakerNameReplacement": self._manifest_data.get("SpeakerNameReplacement", False),
            "CodeSpacingRules": self._manifest_data.get("CodeSpacingRules", True),
            "ProtectCodePatterns": self._manifest_data.get("ProtectCodePatterns", []),
            "CustomPlaceholders": self._manifest_data.get("CustomPlaceholders", []),
            "AnchorRemoval": self._manifest_data.get("AnchorRemoval", []),
        }
    
    def set_preprocessing_options(self, options: Dict[str, Any]) -> None:
        """Set preprocessing options."""
        for key, value in options.items():
            if key in ("Deduplication", "DeduplicationThreshold", "EllipsisCompression",
                      "SymbolConversion", "SpeakerNameReplacement", "CodeSpacingRules",
                      "ProtectCodePatterns", "CustomPlaceholders", "AnchorRemoval"):
                self._manifest_data[key] = value
        self._mark_dirty()
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get validation rules for QA step.
        
        Returns settings for translation validation:
        - PlaceholderPreservation: Check placeholder preservation
        - AnchorPreservation: Check anchor preservation
        - JapaneseCharacterDetection: Detect remaining Japanese
        - SpeakerFormat: Validate speaker format
        - QuoteBalance: Check quote balance
        - EmptyTranslation: Flag empty translations
        """
        return deepcopy(self._manifest_data.get("ValidationRules", {
            "PlaceholderPreservation": True,
            "AnchorPreservation": True,
            "JapaneseCharacterDetection": True,
            "SpeakerFormat": True,
            "QuoteBalance": True,
            "EmptyTranslation": True,
        }))
    
    def set_validation_rules(self, rules: Dict[str, Any]) -> None:
        """Set validation rules."""
        self._manifest_data["ValidationRules"] = rules
        self._mark_dirty()
    
    # ========================== Character/Word Validation (TASK 36.1) ========================== #
    
    def get_character_whitelist(self) -> str:
        """Get the character whitelist string.
        
        TASK 36.1: Returns allowed characters. Empty string means all allowed.
        
        Returns:
            String of allowed characters.
        """
        return self._manifest_data.get("CharacterWhitelist", "")
    
    def set_character_whitelist(self, whitelist: str) -> None:
        """Set the character whitelist string.
        
        TASK 36.1: Set allowed characters for validation.
        
        Args:
            whitelist: String of allowed characters. Empty = all allowed.
        """
        self._manifest_data["CharacterWhitelist"] = whitelist
        self._mark_dirty()
    
    def get_character_blacklist(self) -> str:
        """Get the character blacklist string.
        
        TASK 36.1: Returns forbidden characters.
        
        Returns:
            String of forbidden characters.
        """
        return self._manifest_data.get("CharacterBlacklist", "")
    
    def set_character_blacklist(self, blacklist: str) -> None:
        """Set the character blacklist string.
        
        TASK 36.1: Set forbidden characters for validation.
        
        Args:
            blacklist: String of forbidden characters.
        """
        self._manifest_data["CharacterBlacklist"] = blacklist
        self._mark_dirty()
    
    def get_word_blacklist(self) -> List[str]:
        """Get the word blacklist.
        
        TASK 36.1: Returns forbidden words/phrases.
        Case-insensitive, whole word matching.
        
        Returns:
            List of forbidden words/phrases.
        """
        return deepcopy(self._manifest_data.get("WordBlacklist", []))
    
    def set_word_blacklist(self, blacklist: List[str]) -> None:
        """Set the word blacklist.
        
        TASK 36.1: Set forbidden words/phrases for validation.
        
        Args:
            blacklist: List of forbidden words/phrases.
        """
        self._manifest_data["WordBlacklist"] = blacklist
        self._mark_dirty()
    
    def add_word_to_blacklist(self, word: str) -> None:
        """Add a word to the blacklist.
        
        TASK 36.1: Add a single word to the forbidden list.
        
        Args:
            word: Word to blacklist.
        """
        if "WordBlacklist" not in self._manifest_data:
            self._manifest_data["WordBlacklist"] = []
        if word and word not in self._manifest_data["WordBlacklist"]:
            self._manifest_data["WordBlacklist"].append(word)
            self._mark_dirty()
    
    def remove_word_from_blacklist(self, word: str) -> None:
        """Remove a word from the blacklist.
        
        TASK 36.1: Remove a single word from the forbidden list.
        
        Args:
            word: Word to remove.
        """
        if "WordBlacklist" in self._manifest_data:
            try:
                self._manifest_data["WordBlacklist"].remove(word)
                self._mark_dirty()
            except ValueError:
                pass  # Word not in list
    
    def get_autofix_map(self) -> Dict[str, str]:
        """Get the autofix mapping.
        
        TASK 36.1: Returns mapping from offending characters to replacements.
        
        Returns:
            Dict mapping offending chars to replacement chars.
        """
        return deepcopy(self._manifest_data.get("AutofixMap", {}))
    
    def set_autofix_map(self, autofix_map: Dict[str, str]) -> None:
        """Set the autofix mapping.
        
        TASK 36.1: Set character replacement mappings for auto-correction.
        
        Args:
            autofix_map: Dict mapping offending chars to replacement chars.
        """
        self._manifest_data["AutofixMap"] = autofix_map
        self._mark_dirty()
    
    def add_autofix_entry(self, offending: str, replacement: str) -> None:
        """Add an autofix mapping entry.
        
        TASK 36.1: Add a single character replacement mapping.
        
        Args:
            offending: Offending character to replace.
            replacement: Replacement character.
        """
        if "AutofixMap" not in self._manifest_data:
            self._manifest_data["AutofixMap"] = {}
        if offending:
            self._manifest_data["AutofixMap"][offending] = replacement
            self._mark_dirty()
    
    def remove_autofix_entry(self, offending: str) -> None:
        """Remove an autofix mapping entry.
        
        TASK 36.1: Remove a single character replacement mapping.
        
        Args:
            offending: Offending character to remove from map.
        """
        if "AutofixMap" in self._manifest_data:
            if offending in self._manifest_data["AutofixMap"]:
                del self._manifest_data["AutofixMap"][offending]
                self._mark_dirty()
    
    def get_character_validation_config(self) -> Dict[str, Any]:
        """Get full character/word validation configuration.
        
        TASK 36.1: Returns all validation lists and mappings in one call.
        
        Returns:
            Dict with CharacterWhitelist, CharacterBlacklist, WordBlacklist, AutofixMap.
        """
        return {
            "CharacterWhitelist": self.get_character_whitelist(),
            "CharacterBlacklist": self.get_character_blacklist(),
            "WordBlacklist": self.get_word_blacklist(),
            "AutofixMap": self.get_autofix_map(),
        }
    
    def set_character_validation_config(self, config: Dict[str, Any]) -> None:
        """Set full character/word validation configuration.
        
        TASK 36.1: Set all validation lists and mappings in one call.
        
        Args:
            config: Dict with CharacterWhitelist, CharacterBlacklist, WordBlacklist, AutofixMap.
        """
        if "CharacterWhitelist" in config:
            self._manifest_data["CharacterWhitelist"] = config["CharacterWhitelist"]
        if "CharacterBlacklist" in config:
            self._manifest_data["CharacterBlacklist"] = config["CharacterBlacklist"]
        if "WordBlacklist" in config:
            self._manifest_data["WordBlacklist"] = config["WordBlacklist"]
        if "AutofixMap" in config:
            self._manifest_data["AutofixMap"] = config["AutofixMap"]
        self._mark_dirty()

    def get_qa_options(self) -> Dict[str, Any]:
        """Get QA options for quality assurance step.
        
        Returns QA configuration:
        - RerunPolicy: Which lines to rerun
        - MaxJapaneseChars: Max allowed Japanese characters
        - MaxLineLength: Max line length (0 = unlimited)
        """
        return deepcopy(self._manifest_data.get("QAOptions", {
            "RerunPolicy": "FailedOnly",
            "MaxJapaneseChars": 4,
            "MaxLineLength": 0,
        }))
    
    def set_qa_options(self, options: Dict[str, Any]) -> None:
        """Set QA options."""
        self._manifest_data["QAOptions"] = options
        self._mark_dirty()
    
    def get_postprocessing_options(self) -> Dict[str, Any]:
        """Get post-processing options.
        
        Returns settings for translation cleanup:
        - PlaceholderRecovery: Recover lost placeholders
        - BracketBalanceRecovery: Fix bracket balance
        - QuoteBalanceRecovery: Fix quote balance
        - WhitespaceNormalization: Normalize whitespace
        - RestoreCodeCharacters: Restore code characters
        - RestoreLinebreaks: Restore linebreaks
        - EnableSymbolConversion: Convert symbols back
        - FullwidthToHalfwidth: Convert fullwidth to halfwidth
        - FailureHandling: How to handle failures
        """
        return deepcopy(self._manifest_data.get("PostProcessing", {
            "PlaceholderRecovery": True,
            "BracketBalanceRecovery": True,
            "QuoteBalanceRecovery": True,
            "WhitespaceNormalization": True,
            "RestoreCodeCharacters": True,
            "RestoreLinebreaks": True,
            "EnableSymbolConversion": True,
            "FullwidthToHalfwidth": True,
            "FailureHandling": "flag",
        }))
    
    def set_postprocessing_options(self, options: Dict[str, Any]) -> None:
        """Set post-processing options."""
        self._manifest_data["PostProcessing"] = options
        self._mark_dirty()
    
    def get_wordwrap_options(self) -> Dict[str, Any]:
        """Get wordwrap settings for wordwrap step.
        
        Returns wordwrap configuration:
        - Mode: Wrap mode (Manual, Auto, Off)
        - Width: Line width in characters
        - BreakChar: Character to use for line breaks
        - MaxLines: Maximum lines per text block
        - PreventOrphans: Prevent orphan words
        - PreferPunctuationBreaks: Break at punctuation
        - SpeakerHandling: How to handle speaker names
        - IgnorePatterns: Patterns to skip wrapping
        - Typography: Typography style (Western, Japanese)
        """
        return deepcopy(self._manifest_data.get("WordwrapSettings", {
            "Mode": "Manual",
            "Width": 48,
            "BreakChar": "",
            "MaxLines": 4,
            "PreventOrphans": True,
            "PreferPunctuationBreaks": True,
            "SpeakerHandling": "Sameline",
            "IgnorePatterns": [],
            "Typography": "Western",
        }))
    
    def set_wordwrap_options(self, options: Dict[str, Any]) -> None:
        """Set wordwrap options."""
        self._manifest_data["WordwrapSettings"] = options
        self._mark_dirty()
    
    def get_output_options(self) -> Dict[str, Any]:
        """Get output format options.
        
        Returns output configuration:
        - PreserveFolderStructure: Keep folder structure
        - Format: Output format (auto-detect if empty)
        - PairMode: How to output pairs
        - Encoding: Output encoding (auto-detect if empty)
        - FileNaming: File naming convention
        - TextOption: Text output option
        - OverwriteExistingFiles: Overwrite existing
        - Backup: Backup strategy
        - BackupExtension: Backup file extension
        - ExportManifestFile: Export manifest
        - ExportProcessingLogs: Export logs
        - ExportGlossaryEntries: Export glossary
        """
        return deepcopy(self._manifest_data.get("OutputFormat", {
            "PreserveFolderStructure": True,
            "Format": "",
            "PairMode": "translated_only",
            "Encoding": "",
            "FileNaming": "subfolder",
            "TextOption": "translated",
            "OverwriteExistingFiles": False,
            "Backup": "Timestamp",
            "BackupExtension": ".bk",
            "ExportManifestFile": False,
            "ExportProcessingLogs": False,
            "ExportGlossaryEntries": False,
        }))
    
    def set_output_options(self, options: Dict[str, Any]) -> None:
        """Set output options."""
        self._manifest_data["OutputFormat"] = options
        self._mark_dirty()

    def get_dirty_flags(self) -> Dict[str, bool]:
        """Get pipeline dirty flags.

        Returns dict with ``process`` and ``wordwrap`` booleans indicating
        whether those pipeline stages need re-running before export.
        """
        return deepcopy(self._manifest_data.get("DirtyFlags", {
            "process": False,
            "wordwrap": False,
        }))

    def set_dirty_flag(self, flag_name: str, value: bool) -> None:
        """Set a single pipeline dirty flag.

        Args:
            flag_name: ``"process"`` or ``"wordwrap"``.
            value: True if the stage needs re-running.
        """
        flags = self._manifest_data.setdefault("DirtyFlags", {
            "process": False,
            "wordwrap": False,
        })
        flags[flag_name] = value
        self._mark_dirty()

    def get_estimation_data(self) -> Dict[str, int]:
        """Get estimation data.
        
        Returns token/line estimates:
        - InputLines: Number of input lines
        - InputTokens: Estimated input tokens
        - OutputTokens: Estimated output tokens
        """
        return {
            "InputLines": self._manifest_data.get("InputLines", 0),
            "InputTokens": self._manifest_data.get("InputTokens", 0),
            "OutputTokens": self._manifest_data.get("OutputTokens", 0),
        }
    
    def set_estimation_data(self, data: Dict[str, int]) -> None:
        """Set estimation data."""
        if "InputLines" in data:
            self._manifest_data["InputLines"] = data["InputLines"]
        if "InputTokens" in data:
            self._manifest_data["InputTokens"] = data["InputTokens"]
        if "OutputTokens" in data:
            self._manifest_data["OutputTokens"] = data["OutputTokens"]
        self._mark_dirty()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all v3.0 settings as a single dict.
        
        This is useful for passing complete settings to functions
        or for displaying all settings in a UI.
        
        Returns:
            Dict containing all processing settings grouped by category.
        """
        return {
            "project_info": deepcopy(self.get_info_metadata()),
            "preprocessing": self.get_preprocessing_options(),
            "request": self.get_request_options(),
            "validation": self.get_validation_rules(),
            "qa": self.get_qa_options(),
            "postprocessing": self.get_postprocessing_options(),
            "wordwrap": self.get_wordwrap_options(),
            "output": self.get_output_options(),
            "estimation": self.get_estimation_data(),
        }
    
    # ========================== Raw Access ========================== #
    
    def get_raw_data(self) -> Dict[str, Any]:
        """Get the raw manifest data dictionary.
        
        Use with caution - prefer specific getters.
        """
        return self._manifest_data
    
    def set_raw_data(self, data: Dict[str, Any]) -> None:
        """Set the raw manifest data dictionary.
        
        Use with caution - prefer specific setters.
        """
        self._manifest_data = data
        self._mark_dirty()


# ========================== Global Instance ========================== #

_manager: Optional[ManifestManager] = None


def get_manifest_manager() -> ManifestManager:
    """Get the global ManifestManager instance."""
    global _manager
    if _manager is None:
        _manager = ManifestManager()
    return _manager


def reset_manifest_manager() -> ManifestManager:
    """Reset and return a fresh ManifestManager instance."""
    global _manager
    if _manager is not None:
        _manager.close()
    _manager = ManifestManager()
    return _manager
