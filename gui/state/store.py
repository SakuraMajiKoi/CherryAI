"""CherryAI GUI v2 State Store.

Manages session state, per-step save states, and undo/redo stacks.
Full implementation for Phase 4 with autosave and session restore.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
from copy import deepcopy
from datetime import datetime
import json
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Autosave configuration
AUTOSAVE_INTERVAL_SECONDS = 60
AUTOSAVE_DIR = Path("temp")
AUTOSAVE_FILENAME = "gui_session_autosave.json"
MAX_UNDO_STACK_SIZE = 50


@dataclass
class StepState:
    """State for a single workflow step.

    Attributes:
        step_id: Unique identifier for the step (0-9).
        name: Human-readable step name.
        status: Current status ('not-started', 'in-progress', 'completed').
        data: Arbitrary step-specific data.
        skipped: Whether the step was explicitly skipped.
    """

    step_id: int
    name: str
    status: str = "not-started"
    data: Dict[str, Any] = field(default_factory=dict)
    skipped: bool = False

    def _serialize_value(self, value: Any) -> Any:
        """Recursively serialize a value for JSON.

        Args:
            value: Value to serialize.

        Returns:
            JSON-serializable value.
        """
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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status,
            "data": self._serialize_value(self.data),
            "skipped": self.skipped,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StepState":
        """Deserialize from dictionary."""
        return cls(
            step_id=d["step_id"],
            name=d["name"],
            status=d.get("status", "not-started"),
            data=d.get("data", {}),
            skipped=d.get("skipped", False),
        )

    def reset(self) -> None:
        """Reset step to initial state."""
        self.status = "not-started"
        self.data = {}
        self.skipped = False


# Step definitions with their IDs and names
# NOTE: Information and Preprocessing precede Costs so that cost estimation
#       can compare original vs. preprocessed token counts.
STEP_DEFINITIONS: List[tuple] = [
    (0, "Input"),
    (1, "Analysis"),
    (2, "Information"),      # Moved before Preprocessing/Costs
    (3, "Preprocessing"),    # Moved before Costs
    (4, "Costs"),            # After Preprocessing for dual estimation
    (5, "Translation"),
    (6, "Postprocessing"),
    (7, "Wordwrap"),
    (8, "Quality Assurance"),
    (9, "Output"),
]

# Preset definitions: name -> list of step indices to mark as done automatically
# NOTE: Step order - 2=Information, 3=Preprocessing, 4=Costs
PRESET_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "Sample": {
        "description": "Quick test with minimal steps",
        "auto_steps": [0, 1],  # Only Input and Analysis
        "skip_steps": [2, 4, 6, 7, 8],  # Skip Info, Costs, Post, Wordwrap, QA
    },
    "Dirty & Cheap": {
        "description": "Fast translation with minimal processing",
        "auto_steps": [0, 1, 3, 5, 9],  # Input, Analysis, Preprocess, Translate, Output
        "skip_steps": [2, 4, 6, 7, 8],  # Skip Info, Costs, Post, Wordwrap, QA
    },
    "Automatic Luxury": {
        "description": "Full pipeline with all automation",
        "auto_steps": list(range(10)),  # All steps
        "skip_steps": [],
    },
    "Everything Custom": {
        "description": "Manual control at every step",
        "auto_steps": [],  # No automatic steps
        "skip_steps": [],
    },
}


# TASK 16.5: Default preprocessing configuration for GUI Step 4
# Stored in step data for Preprocessing step (step_id=3)
DEFAULT_PREPROCESS_CONFIG: Dict[str, Any] = {
    # Deduplication
    "dedup_enabled": True,
    "dedup_threshold": 1,
    "aggressive_dedup_enabled": False,  # TASK 42.4: Number normalization
    # Ellipsis handling (via modi/standard_mode.py)
    "ellipsis_enabled": True,
    # Symbol conversion (via modi/standard_mode.py)
    "symbol_conversion_enabled": True,
    "symbol_src_lang": "ja",
    "symbol_tgt_lang": "en",
    # PROTECTED compression (via modi/standard_mode.py)
    "prot_compression_enabled": True,
    # Speaker replacement (via modi/standard_mode.py)
    "speaker_replacement_enabled": False,
    # Code spacing (via modi/standard_mode.py)
    "code_spacing_enabled": False,
    # Custom placeholder rules (via modi/custom_placeholder.py)
    "placeholder_rules": [],
    # Protect code patterns (via modi/protect_code.py)
    "protect_code_patterns": [],
}


@dataclass
class UndoAction:
    """Represents an undoable action.

    Attributes:
        action_type: Type of action (step_change, data_change, status_change).
        description: Human-readable description.
        timestamp: When the action occurred.
        before_state: State snapshot before the action.
        after_state: State snapshot after the action.
    """

    action_type: str
    description: str
    timestamp: datetime
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action_type": self.action_type,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "before_state": self.before_state,
            "after_state": self.after_state,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UndoAction":
        """Deserialize from dictionary."""
        return cls(
            action_type=d["action_type"],
            description=d["description"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            before_state=d["before_state"],
            after_state=d["after_state"],
        )


@dataclass
class SessionState:
    """Session state for the entire application.

    Manages loaded files, current step, step states, and undo/redo.
    Full implementation with autosave and session restore for Phase 4.

    Attributes:
        loaded_files: List of loaded file paths.
        current_step: Index of the currently active step (0-9).
        steps: State for each workflow step.
        undo_stack: Stack of undoable actions.
        redo_stack: Stack of redoable actions.
        manifest_path: Path to the currently loaded manifest, if any.
        active_preset: Currently active preset name.
        last_modified: Timestamp of last modification.
        dirty: Whether there are unsaved changes.
    """

    loaded_files: List[Path] = field(default_factory=list)
    current_step: int = 0
    steps: List[StepState] = field(default_factory=list)
    undo_stack: List[UndoAction] = field(default_factory=list)
    redo_stack: List[UndoAction] = field(default_factory=list)
    manifest_path: Optional[Path] = None
    active_preset: str = "Everything Custom"
    global_options: Any = None
    last_modified: Optional[datetime] = None
    dirty: bool = False
    _pending_action: Optional[UndoAction] = None
    _autosave_thread: Optional[threading.Thread] = field(
        default=None, repr=False, compare=False
    )
    _autosave_stop: bool = field(default=False, repr=False, compare=False)
    _change_listeners: List[Callable[[], None]] = field(
        default_factory=list, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        """Initialize step states if empty."""
        if not self.steps:
            self.steps = [
                StepState(step_id=sid, name=name) for sid, name in STEP_DEFINITIONS
            ]
        if self.last_modified is None:
            self.last_modified = datetime.now()

    def add_change_listener(self, listener: Callable[[], None]) -> None:
        """Add a listener to be notified on state changes.

        Args:
            listener: Callback function to invoke on changes.
        """
        self._change_listeners.append(listener)

    def remove_change_listener(self, listener: Callable[[], None]) -> None:
        """Remove a change listener.

        Args:
            listener: Callback function to remove.
        """
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    def set_dirty(self, dirty: bool = True) -> None:
        """Set the dirty flag.
        
        Args:
            dirty: Whether the session has unsaved changes.
        """
        self.dirty = dirty
        if dirty:
            self._notify_change()

    def _notify_change(self) -> None:
        """Notify all listeners of a state change."""
        self.last_modified = datetime.now()
        self.dirty = True
        for listener in self._change_listeners:
            try:
                listener()
            except Exception as e:
                logger.warning("Change listener error: %s", e)

    def _get_state_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of current state for undo/redo.

        Returns:
            Dictionary representing current state.
        """
        return {
            "loaded_files": [str(p) for p in self.loaded_files],
            "current_step": self.current_step,
            "steps": [s.to_dict() for s in self.steps],
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "active_preset": self.active_preset,
        }

    def _restore_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Restore state from a snapshot.

        Args:
            snapshot: State dictionary to restore from.
        """
        self.loaded_files = [Path(p) for p in snapshot.get("loaded_files", [])]
        self.current_step = snapshot.get("current_step", 0)
        if "steps" in snapshot:
            self.steps = [StepState.from_dict(s) for s in snapshot["steps"]]
        if snapshot.get("manifest_path"):
            self.manifest_path = Path(snapshot["manifest_path"])
        else:
            self.manifest_path = None
        self.active_preset = snapshot.get("active_preset", "Everything Custom")

    def push_undo(self, action_type: str, description: str) -> None:
        """Push current state to undo stack before making a change.

        Args:
            action_type: Type of action being performed.
            description: Human-readable description of the action.
        """
        before_state = self._get_state_snapshot()
        # Store pending action - will be completed when _complete_undo_action is called
        self._pending_action = UndoAction(
            action_type=action_type,
            description=description,
            timestamp=datetime.now(),
            before_state=before_state,
            after_state={},  # Will be filled in later
        )

    def _complete_undo_action(self) -> None:
        """Complete the pending undo action with the current state."""
        if hasattr(self, "_pending_action") and self._pending_action:
            self._pending_action.after_state = self._get_state_snapshot()
            self.undo_stack.append(self._pending_action)
            # Limit stack size
            if len(self.undo_stack) > MAX_UNDO_STACK_SIZE:
                self.undo_stack.pop(0)
            # Clear redo stack on new action
            self.redo_stack.clear()
            self._pending_action = None
            logger.debug("Undo action completed: %s", self.undo_stack[-1].description)

    def get_step(self, step_id: int) -> StepState:
        """Get state for a specific step.

        Args:
            step_id: Step index (0-9).

        Returns:
            StepState for the requested step.
        """
        return self.steps[step_id]

    def set_step_status(self, step_id: int, status: str) -> None:
        """Set status for a step.

        Args:
            step_id: Step index (0-9).
            status: New status ('not-started', 'in-progress', 'completed').
        """
        old_status = self.steps[step_id].status
        if old_status != status:
            self.push_undo(
                "status_change",
                f"Change step {step_id + 1} status: {old_status} → {status}",
            )
            self.steps[step_id].status = status
            self._complete_undo_action()
            self._notify_change()

    def set_step_data(self, step_id: int, key: str, value: Any) -> None:
        """Set data for a step.

        Args:
            step_id: Step index (0-9).
            key: Data key.
            value: Data value.
        """
        self.push_undo("data_change", f"Update step {step_id + 1} data: {key}")
        self.steps[step_id].data[key] = value
        self._complete_undo_action()
        self._notify_change()

    def get_step_data(self, step_id: int, key: str, default: Any = None) -> Any:
        """Get data for a step.

        Args:
            step_id: Step index (0-9).
            key: Data key.
            default: Default value if key not found.

        Returns:
            Data value or default.
        """
        return self.steps[step_id].data.get(key, default)

    def mark_done(self, step_id: Optional[int] = None) -> None:
        """Mark a step as completed.

        Args:
            step_id: Step to mark. Defaults to current step.
        """
        if step_id is None:
            step_id = self.current_step
        self.set_step_status(step_id, "completed")

    def mark_skipped(self, step_id: int) -> None:
        """Mark a step as skipped.

        Args:
            step_id: Step to mark as skipped.
        """
        self.push_undo("skip_step", f"Skip step {step_id + 1}")
        self.steps[step_id].skipped = True
        self.steps[step_id].status = "completed"
        self._complete_undo_action()
        self._notify_change()

    def rollback_step(self, step_id: int) -> None:
        """Rollback a step to not-started state.

        Args:
            step_id: Step to rollback.
        """
        self.push_undo("rollback_step", f"Rollback step {step_id + 1}")
        self.steps[step_id].reset()
        self._complete_undo_action()
        self._notify_change()

    def advance_step(self) -> bool:
        """Advance to the next step.

        Returns:
            True if advanced, False if already at last step.
        """
        if self.current_step < len(self.steps) - 1:
            self.push_undo(
                "step_change",
                f"Advance from step {self.current_step + 1} to {self.current_step + 2}",
            )
            self.current_step += 1
            self._complete_undo_action()
            self._notify_change()
            return True
        return False

    def go_to_step(self, step_id: int) -> None:
        """Navigate to a specific step.

        Args:
            step_id: Step index to navigate to (0-9).
        """
        if 0 <= step_id < len(self.steps) and step_id != self.current_step:
            self.push_undo(
                "step_change",
                f"Navigate from step {self.current_step + 1} to {step_id + 1}",
            )
            self.current_step = step_id
            self._complete_undo_action()
            self._notify_change()

    def undo(self) -> bool:
        """Undo last action.

        Returns:
            True if undo succeeded, False if nothing to undo.
        """
        if not self.undo_stack:
            logger.debug("Nothing to undo")
            return False

        action = self.undo_stack.pop()
        # Push to redo stack
        self.redo_stack.append(action)
        # Restore before state
        self._restore_from_snapshot(action.before_state)
        self._notify_change()
        logger.info("Undo: %s", action.description)
        return True

    def redo(self) -> bool:
        """Redo last undone action.

        Returns:
            True if redo succeeded, False if nothing to redo.
        """
        if not self.redo_stack:
            logger.debug("Nothing to redo")
            return False

        action = self.redo_stack.pop()
        # Push back to undo stack
        self.undo_stack.append(action)
        # Restore after state
        self._restore_from_snapshot(action.after_state)
        self._notify_change()
        logger.info("Redo: %s", action.description)
        return True

    def can_undo(self) -> bool:
        """Check if undo is available.

        Returns:
            True if there are actions to undo.
        """
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available.

        Returns:
            True if there are actions to redo.
        """
        return len(self.redo_stack) > 0

    def get_undo_description(self) -> Optional[str]:
        """Get description of the next undo action.

        Returns:
            Description string or None if nothing to undo.
        """
        if self.undo_stack:
            return self.undo_stack[-1].description
        return None

    def get_redo_description(self) -> Optional[str]:
        """Get description of the next redo action.

        Returns:
            Description string or None if nothing to redo.
        """
        if self.redo_stack:
            return self.redo_stack[-1].description
        return None

    def apply_preset(self, preset_name: str) -> None:
        """Apply a workflow preset.

        Args:
            preset_name: Name of the preset to apply.

        Raises:
            ValueError: If preset name is not recognized.
        """
        if preset_name not in PRESET_DEFINITIONS:
            raise ValueError(f"Unknown preset: {preset_name}")

        preset = PRESET_DEFINITIONS[preset_name]
        self.push_undo("apply_preset", f"Apply preset: {preset_name}")

        # Reset all steps first
        for step in self.steps:
            step.reset()

        # Mark auto steps
        for step_id in preset.get("auto_steps", []):
            if step_id < len(self.steps):
                self.steps[step_id].status = "in-progress"

        # Mark skipped steps
        for step_id in preset.get("skip_steps", []):
            if step_id < len(self.steps):
                self.steps[step_id].skipped = True
                self.steps[step_id].status = "completed"

        self.active_preset = preset_name
        self._complete_undo_action()
        self._notify_change()
        logger.info("Applied preset: %s", preset_name)

    def get_completion_percentage(self) -> float:
        """Calculate workflow completion percentage.

        Returns:
            Completion percentage (0-100).
        """
        completed = sum(1 for s in self.steps if s.status == "completed")
        return (completed / len(self.steps)) * 100

    def get_next_incomplete_step(self) -> Optional[int]:
        """Get the next step that is not completed.

        Returns:
            Step ID of next incomplete step, or None if all done.
        """
        for step in self.steps:
            if step.status != "completed":
                return step.step_id
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session state to dictionary."""
        return {
            "loaded_files": [str(p) for p in self.loaded_files],
            "current_step": self.current_step,
            "steps": [s.to_dict() for s in self.steps],
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "active_preset": self.active_preset,
            "last_modified": (
                self.last_modified.isoformat() if self.last_modified else None
            ),
            "undo_stack": [a.to_dict() for a in self.undo_stack[-10:]],  # Last 10 only
            "redo_stack": [a.to_dict() for a in self.redo_stack[-10:]],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SessionState":
        """Deserialize session state from dictionary.
        
        Maps loaded steps by NAME to handle step order changes between versions.
        This ensures old sessions with different step ordering still load correctly.
        """
        state = cls()
        state.loaded_files = [Path(p) for p in d.get("loaded_files", [])]
        state.current_step = d.get("current_step", 0)
        
        # Map steps by name to handle reordering between versions
        if "steps" in d:
            # Build name -> loaded data mapping
            loaded_steps_by_name: Dict[str, Dict[str, Any]] = {}
            for step_data in d["steps"]:
                name = step_data.get("name", "")
                if name:
                    loaded_steps_by_name[name] = step_data
            
            # Create fresh steps from current definitions
            state.steps = [
                StepState(step_id=sid, name=name) for sid, name in STEP_DEFINITIONS
            ]
            
            # Restore data into steps by matching names
            for step in state.steps:
                if step.name in loaded_steps_by_name:
                    loaded_data = loaded_steps_by_name[step.name]
                    step.status = loaded_data.get("status", "not-started")
                    step.data = loaded_data.get("data", {})
                    step.skipped = loaded_data.get("skipped", False)
                    logger.debug(
                        "Restored step %d '%s' from session (status=%s, data_keys=%s)",
                        step.step_id, step.name, step.status, list(step.data.keys())
                    )
        
        if d.get("manifest_path"):
            state.manifest_path = Path(d["manifest_path"])
        state.active_preset = d.get("active_preset", "Everything Custom")
        if d.get("last_modified"):
            state.last_modified = datetime.fromisoformat(d["last_modified"])
        if "undo_stack" in d:
            state.undo_stack = [UndoAction.from_dict(a) for a in d["undo_stack"]]
        if "redo_stack" in d:
            state.redo_stack = [UndoAction.from_dict(a) for a in d["redo_stack"]]
        state.dirty = False
        return state

    def save_to_file(self, path: Path) -> None:
        """Save session state to file.

        Args:
            path: Path to save session state.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        self.dirty = False
        logger.info("Session state saved to %s", path)

    @classmethod
    def load_from_file(cls, path: Path) -> "SessionState":
        """Load session state from file.

        Args:
            path: Path to load session state from.

        Returns:
            Loaded SessionState instance.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Session state loaded from %s", path)
        return cls.from_dict(data)

    def start_autosave(self) -> None:
        """Start the autosave background thread."""
        if self._autosave_thread is not None and self._autosave_thread.is_alive():
            return  # Already running

        self._autosave_stop = False

        def autosave_loop() -> None:
            while not self._autosave_stop:
                time.sleep(AUTOSAVE_INTERVAL_SECONDS)
                if self._autosave_stop:
                    break
                if self.dirty:
                    try:
                        autosave_path = AUTOSAVE_DIR / AUTOSAVE_FILENAME
                        self.save_to_file(autosave_path)
                        logger.debug("Autosaved session state")
                    except Exception as e:
                        logger.warning("Autosave failed: %s", e)

        self._autosave_thread = threading.Thread(
            target=autosave_loop, daemon=True, name="SessionAutosave"
        )
        self._autosave_thread.start()
        logger.info("Autosave started (interval: %ds)", AUTOSAVE_INTERVAL_SECONDS)

    def stop_autosave(self) -> None:
        """Stop the autosave background thread."""
        self._autosave_stop = True
        if self._autosave_thread is not None:
            self._autosave_thread.join(timeout=2)
            self._autosave_thread = None
        logger.info("Autosave stopped")


# Global session state instance
_session: Optional[SessionState] = None


def get_session() -> SessionState:
    """Get the global session state instance.

    Returns:
        The current SessionState.
    """
    global _session
    if _session is None:
        _session = SessionState()
    return _session


def reset_session() -> SessionState:
    """Reset the global session state.

    Returns:
        A fresh SessionState instance.
    """
    global _session
    if _session is not None:
        _session.stop_autosave()
    _session = SessionState()
    return _session


def load_session_from_autosave() -> Optional[SessionState]:
    """Try to load session from autosave file.

    Returns:
        Loaded SessionState if autosave exists, None otherwise.
    """
    autosave_path = AUTOSAVE_DIR / AUTOSAVE_FILENAME
    if autosave_path.exists():
        try:
            return SessionState.load_from_file(autosave_path)
        except Exception as e:
            logger.warning("Failed to load autosave: %s", e)
    return None


def get_preset_definitions() -> Dict[str, Dict[str, Any]]:
    """Get all preset definitions.

    Returns:
        Dictionary of preset definitions.
    """
    return PRESET_DEFINITIONS.copy()


def get_preset_names() -> List[str]:
    """Get list of available preset names.

    Returns:
        List of preset names.
    """
    return list(PRESET_DEFINITIONS.keys())
