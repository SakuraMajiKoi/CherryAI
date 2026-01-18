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

# Constants
MANIFEST_DIR = Path("Projects")
MANIFEST_EXT = ".CherryAI.json"
MANIFEST_VERSION = "3.0"

# Step definitions matching GUI step order
STEP_NAMES = [
    "Input and Extraction",
    "Analysis",
    "Estimation",
    "Information",
    "Preprocessing",
    "Translation",
    "Quality Assurance",
    "Postprocessing",
    "Wordwrap and Overwrite",
    "Output and Injection",
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
    custom_notes: str = ""
    
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
        if self.custom_notes:
            result["custom_notes"] = self.custom_notes
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
            custom_notes=d.get("custom_notes", ""),
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
        self._autosave_interval: int = 15  # seconds
        self._save_on_close: bool = True
        self._autosave_thread: Optional[threading.Thread] = None
        self._autosave_stop_event: threading.Event = threading.Event()
        self._autosave_lock: threading.Lock = threading.Lock()
        
        # Load autosave settings from INI
        self._load_autosave_settings()
        
        # Ensure manifests directory exists
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_autosave_settings(self) -> None:
        """Load autosave settings from INI file."""
        try:
            from .ini_manager import get_default
            
            self._autosave_enabled = bool(
                get_default("autosave", "enabled", True, bool)
            )
            self._autosave_interval = int(
                get_default("autosave", "interval_seconds", 15, int) or 15
            )
            self._save_on_close = bool(
                get_default("autosave", "save_on_close", True, bool)
            )
            
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
        """Get the project name."""
        return self._manifest_data.get("project_name", "")
    
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
        """Create an empty manifest structure with all v3.0 fields.
        
        TASK 21.2: Extended to include ALL fields needed by GUI and processing.
        Uses defaults from INI file via ini_manager.
        """
        now = datetime.utcnow().isoformat() + "Z"
        defaults = self._get_manifest_defaults()
        
        return {
            # === Core Metadata ===
            "version": MANIFEST_VERSION,
            "created_at": now,
            "updated_at": now,
            
            # === Project Identity ===
            "project_name": defaults.get("project_name", "Project1"),
            "source_files": [],
            "current_step": 0,
            
            # === v2.1 Processing Data (unchanged format) ===
            "lines": [],
            "operations": [],
            "mappings": {},
            "summary": "",
            "metadata": {},
            
            # === v3.0 Project Settings ===
            "project_info": self._create_project_info_defaults(defaults),
            "characters": [],
            "code_patterns": [],
            "step_state": {name: StepState(name=name).to_dict() for name in STEP_NAMES},
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
                "FailureHandling": defaults.get("post_failure_handling", "FlagForReview"),
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
                "FileNaming": defaults.get("output_file_naming", "PutInSubfolder"),
                "TextOption": defaults.get("output_text_option", "translated"),
                "OverwriteExistingFiles": defaults.get("output_overwrite_existing_files", False),
                "Backup": defaults.get("output_backup", "Timestamp"),
                "BackupExtension": defaults.get("output_backup_extension", ".bk"),
                "ExportManifestFile": defaults.get("output_export_manifest_file", False),
                "ExportProcessingLogs": defaults.get("output_export_processing_logs", False),
                "ExportGlossaryEntries": defaults.get("output_export_glossary_entries", False),
            },
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
            "post_failure_handling": "FlagForReview",
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
            "output_file_naming": "PutInSubfolder",
            "output_text_option": "translated",
            "output_overwrite_existing_files": False,
            "output_backup": "Timestamp",
            "output_backup_extension": ".bk",
            "output_export_manifest_file": False,
            "output_export_processing_logs": False,
            "output_export_glossary_entries": False,
        }
    
    def _create_project_info_defaults(self, defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Create project_info dict with defaults.
        
        Args:
            defaults: Dictionary of default values from INI.
            
        Returns:
            project_info dictionary with all fields.
        """
        return {
            "project_name": defaults.get("project_name", "Project1"),
            "game_title": defaults.get("title", "Title1"),
            "source_language": defaults.get("source_language", "Japanese"),
            "target_language": defaults.get("target_language", "English"),
            "genre": defaults.get("genre", "fictional, nonfictional"),
            "summary": defaults.get("summary", "[Summary of the Content]"),
            "style_preset": defaults.get("style_preset", "neutral"),
            "custom_style": "",
            "tone_preset": defaults.get("tone_preset", "natural"),
            "custom_tone": "",
            "custom_notes": "",
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
    
    def _ensure_all_fields_present(self) -> None:
        """Ensure all v3.0 fields are present in loaded manifest.
        
        TASK 21.2: Called after load() to add missing fields with defaults.
        This ensures old manifests get upgraded to v3.0 field set.
        """
        defaults = self._get_manifest_defaults()
        empty = self._create_empty_manifest()
        
        # Add missing top-level fields
        for key, default_value in empty.items():
            if key not in self._manifest_data:
                self._manifest_data[key] = default_value
                logger.debug("Added missing field: %s", key)
        
        # Ensure nested objects have all fields
        self._ensure_nested_fields("ValidationRules", empty.get("ValidationRules", {}))
        self._ensure_nested_fields("QAOptions", empty.get("QAOptions", {}))
        self._ensure_nested_fields("RequestOptions", empty.get("RequestOptions", {}))
        self._ensure_nested_fields("PostProcessing", empty.get("PostProcessing", {}))
        self._ensure_nested_fields("WordwrapSettings", empty.get("WordwrapSettings", {}))
        self._ensure_nested_fields("OutputFormat", empty.get("OutputFormat", {}))
    
    def _ensure_nested_fields(self, parent_key: str, defaults: Dict[str, Any]) -> None:
        """Ensure nested dict has all required fields.
        
        Args:
            parent_key: Key of the nested dict in manifest.
            defaults: Default values for the nested dict.
        """
        if parent_key not in self._manifest_data:
            self._manifest_data[parent_key] = defaults
            return
        
        if not isinstance(self._manifest_data[parent_key], dict):
            self._manifest_data[parent_key] = defaults
            return
        
        for key, value in defaults.items():
            if key not in self._manifest_data[parent_key]:
                self._manifest_data[parent_key][key] = value
                logger.debug("Added missing nested field: %s.%s", parent_key, key)
    
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
    
    # ========================== Project Operations ========================== #
    
    def create_new(self, project_name: str, source_files: List[Path]) -> Path:
        """Create a new project manifest.
        
        Args:
            project_name: Name for the project (used in filename)
            source_files: List of source file paths
            
        Returns:
            Path to the created manifest file
            
        TASK 29.1: Starts autosave thread after creation.
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
        self._manifest_data["project_name"] = project_name
        # Store source files as absolute paths (TASK 32.1)
        self._manifest_data["source_files"] = [str(p.resolve()) for p in source_files]
        
        # Initialize lines from source files
        self._initialize_lines_from_files(source_files)
        
        self._dirty = True
        self._current_step = 0
        self.save()
        
        # Start autosave thread
        self.start_autosave()
        
        logger.info("Created new manifest: %s", self._manifest_path)
        return self._manifest_path
    
    def _initialize_lines_from_files(self, source_files: List[Path]) -> None:
        """Initialize lines array from source files."""
        lines: List[Dict[str, Any]] = []
        idx = 0
        
        for file_path in source_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                for line_text in content.split("\n"):
                    lines.append({
                        "idx": idx,
                        "orig": line_text,
                        "source_file": str(file_path),
                    })
                    idx += 1
            except Exception as e:
                logger.warning("Failed to read source file %s: %s", file_path, e)
        
        self._manifest_data["lines"] = lines
    
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
            
            # Ensure all v3.0 fields are present (backward compatibility)
            self._ensure_all_fields_present()
            
            self._current_step = data.get("current_step", 0)
            self._dirty = False
            
            # Start autosave thread
            self.start_autosave()
            
            logger.info("Loaded manifest: %s (v%s)", manifest_path, data.get("version", "?"))
            return True
            
        except Exception as e:
            logger.error("Failed to load manifest %s: %s", manifest_path, e)
            return False
    
    def _migrate_manifest(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate older manifest versions to v3.0.
        
        Handles migration from v1.x and v2.x manifests, preserving all line
        data, operations, and settings.
        """
        version = data.get("version", "1.0")
        
        if version.startswith("1.") or version.startswith("2."):
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
            
            data["version"] = MANIFEST_VERSION
        
        return data
    
    def save(self) -> bool:
        """Save the manifest to disk.
        
        Returns:
            True if saved successfully
        """
        if self._manifest_path is None:
            logger.warning("Cannot save: no manifest path set")
            return False
        
        try:
            self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._manifest_path, "w", encoding="utf-8") as f:
                json.dump(self._manifest_data, f, ensure_ascii=False, indent=2)
            
            self._dirty = False
            logger.debug("Saved manifest: %s", self._manifest_path)
            return True
            
        except Exception as e:
            logger.error("Failed to save manifest: %s", e)
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
        
        self._manifest_path = None
        self._manifest_data = self._create_empty_manifest()
        self._dirty = False
        self._current_step = 0
    
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
    
    # ========================== Project Info Operations ========================== #
    
    def get_project_info(self) -> ProjectInfo:
        """Get project information."""
        data = self._manifest_data.get("project_info", {})
        return ProjectInfo.from_dict(data)
    
    def set_project_info(self, info: ProjectInfo) -> None:
        """Set project information."""
        self._manifest_data["project_info"] = info.to_dict()
        self._mark_dirty()
    
    def update_project_info(self, **kwargs: Any) -> None:
        """Update specific project info fields."""
        info = self.get_project_info()
        for key, value in kwargs.items():
            if hasattr(info, key):
                setattr(info, key, value)
        self.set_project_info(info)
    
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
    
    def set_line_field(self, idx: int, field: str, value: Any) -> None:
        """Set a field on a specific line."""
        lines = self._manifest_data.get("lines", [])
        for line in lines:
            if line.get("idx") == idx:
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
    
    def get_source_files(self) -> List[Path]:
        """Get source file paths."""
        return [Path(p) for p in self._manifest_data.get("source_files", [])]
    
    def set_source_files(self, files: List[Path]) -> None:
        """Set source file paths.
        
        Stores as absolute paths (TASK 32.1).
        """
        # Store as absolute paths
        self._manifest_data["source_files"] = [str(p.resolve()) for p in files]
        self._mark_dirty()
    
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
            "FailureHandling": "FlagForReview",
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
            "FileNaming": "PutInSubfolder",
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
            "project_info": deepcopy(self._manifest_data.get("project_info", {})),
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
