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

No manual save buttons required.
"""

from __future__ import annotations

import json
import logging
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
    
    Usage:
        manager = ManifestManager()
        manager.create_new("My Project", [Path("file.txt")])
        manager.set_step_data(3, {"metadata": {...}})
        manager.save()  # Called automatically on close/step change
    """
    
    def __init__(self) -> None:
        """Initialize manager with no loaded manifest."""
        self._manifest_path: Optional[Path] = None
        self._manifest_data: Dict[str, Any] = self._create_empty_manifest()
        self._dirty: bool = False
        self._change_listeners: List[Callable[[], None]] = []
        self._current_step: int = 0
        
        # Ensure manifests directory exists
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    
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
        """Create an empty manifest structure."""
        now = datetime.utcnow().isoformat() + "Z"
        return {
            "version": MANIFEST_VERSION,
            "project_name": "",
            "created_at": now,
            "updated_at": now,
            "source_files": [],
            "current_step": 0,
            "project_info": ProjectInfo().to_dict(),
            "characters": [],
            "code_patterns": [],
            "step_state": {name: StepState(name=name).to_dict() for name in STEP_NAMES},
            "glossary": GlossaryConfig().to_dict(),
            "lines": [],
            "operations": [],
            "mappings": {},
        }
    
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
        self._manifest_data["source_files"] = [str(p) for p in source_files]
        
        # Initialize lines from source files
        self._initialize_lines_from_files(source_files)
        
        self._dirty = True
        self._current_step = 0
        self.save()
        
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
        """Close the current manifest (saves if dirty)."""
        if self._dirty:
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
        """Set source file paths."""
        self._manifest_data["source_files"] = [str(p) for p in files]
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
