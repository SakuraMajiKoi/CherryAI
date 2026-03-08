"""CherryAI GUI v2 Base Step.

Abstract base class for all workflow step tabs.

TASK 19: Updated to support ManifestManager for unified state persistence.
TASK 43.14: Added tab caching infrastructure.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional, Union
import hashlib
import json
import logging
import tkinter as tk
from tkinter import ttk

from CherryAI.gui.theme.colors import THEME

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


class BaseStep(ABC, ttk.Frame):
    """Abstract base class for workflow step tabs.

    Each step tab extends this class and implements the required methods.
    Provides common functionality for theming, state access, and layout.

    TASK 19: Now supports both SessionState (legacy) and ManifestManager (new).
    The manifest_manager property provides access to the new unified state system.

    Attributes:
        step_id: Unique identifier for this step (0-9).
        step_name: Human-readable name for this step.
        session: Reference to the session state (legacy, may be None).
        _manifest_manager: Reference to ManifestManager (new).
    """

    step_id: int = 0
    step_name: str = "Base Step"

    def __init__(
        self,
        parent: tk.Widget,
        session: Optional["SessionState"] = None,
        manifest_manager: Optional["ManifestManager"] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the step tab.

        Args:
            parent: Parent widget (typically the notebook).
            session: Session state reference (legacy, optional).
            manifest_manager: ManifestManager reference (new, optional).
            **kwargs: Additional keyword arguments for ttk.Frame.
        """
        super().__init__(parent, **kwargs)
        self.session = session
        self._manifest_manager = manifest_manager
        # TASK 43.14: Tab caching state
        self._cache_hash: Optional[str] = None
        self._build_ui()

    @property
    def manifest_manager(self) -> Optional["ManifestManager"]:
        """Get the ManifestManager instance.
        
        Returns the explicitly set manager, or tries to get the global one.
        """
        if self._manifest_manager is not None:
            return self._manifest_manager
        
        # Try to get global manager
        try:
            from CherryAI.functions.manifest_manager import get_manifest_manager
            return get_manifest_manager()
        except ImportError:
            return None

    @abstractmethod
    def _build_ui(self) -> None:
        """Build the step's user interface.

        Subclasses must implement this to create their UI.
        """
        pass

    @abstractmethod
    def on_enter(self) -> None:
        """Called when the step tab is selected/entered.

        Use this to refresh data or update the display.
        """
        pass

    @abstractmethod
    def on_leave(self) -> None:
        """Called when leaving this step tab.

        Use this to save state or validate before leaving.
        This triggers automatic save to manifest (TASK 19).
        """
        pass

    def get_step_data(self) -> Dict[str, Any]:
        """Get this step's data from state.

        TASK 19: Prefers ManifestManager, falls back to session.

        Returns:
            Dictionary of step-specific data.
        """
        # Try manifest manager first (new system)
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            return mgr.get_step_data(self.step_id)
        
        # Fall back to session (legacy)
        if self.session is not None:
            return self.session.get_step(self.step_id).data
        
        return {}

    def set_step_data(self, data: Dict[str, Any]) -> None:
        """Set this step's data in state.

        TASK 19: Prefers ManifestManager, falls back to session.
        Both paths trigger automatic save.

        Args:
            data: Dictionary of step-specific data.
        """
        # Try manifest manager first (new system)
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.set_step_data(self.step_id, data)
            logger.debug("Step %d data saved to manifest", self.step_id)
            return
        
        # Fall back to session (legacy)
        if self.session is not None:
            self.session.get_step(self.step_id).data = data
            self.session.set_dirty(True)
            logger.debug("Step %d data saved to session", self.step_id)

    def update_step_data(self, key: str, value: Any) -> None:
        """Update a single key in step data.
        
        TASK 19: More efficient than set_step_data for single updates.
        
        Args:
            key: Data key to update.
            value: New value.
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.update_step_data(self.step_id, key, value)
            return
        
        # Fall back to full data replacement
        data = self.get_step_data()
        data[key] = value
        self.set_step_data(data)

    def get_step_data_value(self, key: str, default: Any = None) -> Any:
        """Get a single value from step data.
        
        Args:
            key: Data key.
            default: Default value if not found.
            
        Returns:
            Value or default.
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            return mgr.get_step_data_value(self.step_id, key, default)
        
        return self.get_step_data().get(key, default)

    def mark_done(self) -> None:
        """Mark this step as completed."""
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.mark_step_done(self.step_id)
            return
        
        if self.session is not None:
            self.session.mark_done(self.step_id)

    def set_status(self, status: str) -> None:
        """Set this step's status.

        Args:
            status: Status string ('not-started', 'in-progress', 'completed').
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.set_step_status(self.step_id, status)
            return
        
        if self.session is not None:
            self.session.set_step_status(self.step_id, status)
    
    def save_to_manifest(self) -> None:
        """Explicitly save current state to manifest.
        
        TASK 19: Called automatically on step change and close.
        Can also be called manually if needed.
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.save()

    # -----------------------------------------------------------------
    # Tab Caching (TASK 43.14)
    # -----------------------------------------------------------------

    def _compute_cache_hash(self) -> str:
        """Compute a hash representing the relevant manifest data for this step.

        Subclasses should override to include only the manifest keys that
        affect this step's display.  The default implementation hashes
        the entire step data dict.

        Returns:
            Hex digest string.
        """
        data = self.get_step_data()
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def _is_cache_valid(self) -> bool:
        """Check whether the cached state still matches the manifest.

        Returns:
            ``True`` if the cache hash matches (no refresh needed).
        """
        if self._cache_hash is None:
            return False
        return self._compute_cache_hash() == self._cache_hash

    def _update_cache(self) -> None:
        """Store the current cache hash after a refresh."""
        self._cache_hash = self._compute_cache_hash()

    def _invalidate_cache(self) -> None:
        """Invalidate the cache so the next ``on_enter`` forces refresh."""
        self._cache_hash = None

    def _force_refresh(self) -> None:
        """Bypass cache and perform a full refresh.

        Subclasses can bind this to a Refresh button.  The default
        invalidates the cache and calls ``on_enter()``.
        """
        self._invalidate_cache()
        self.on_enter()

    def on_new_project(self) -> None:
        """Reset all cached state when a new project is created.

        Called by ``App._on_new_session()`` to ensure every step tab
        starts with a clean slate.  Subclasses should override to clear
        their own instance-level data caches (e.g. ``_loaded_files``,
        ``_lines``, ``_analysis_results``).  Always call ``super()``
        first so the cache hash is invalidated.
        """
        self._invalidate_cache()


class PlaceholderStep(BaseStep):
    """Placeholder step for unimplemented tabs.

    Shows a "Not Implemented" message with the step number and name.
    """

    def __init__(
        self,
        parent: tk.Widget,
        session: Optional["SessionState"] = None,
        step_id: int = 0,
        step_name: str = "",
        manifest_manager: Optional["ManifestManager"] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize placeholder step.

        Args:
            parent: Parent widget.
            session: Session state reference (legacy).
            step_id: Step number (0-9).
            step_name: Step name for display.
            manifest_manager: ManifestManager reference (new).
            **kwargs: Additional keyword arguments.
        """
        self.step_id = step_id
        self.step_name = step_name
        super().__init__(parent, session, manifest_manager, **kwargs)

    def _build_ui(self) -> None:
        """Build placeholder UI."""
        # Center the content
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Create a centered frame
        center_frame = ttk.Frame(self)
        center_frame.grid(row=0, column=0)

        # Step number and name
        title = f"Step {self.step_id + 1}: {self.step_name}"
        title_label = ttk.Label(
            center_frame,
            text=title,
            font=("Segoe UI", 18, "bold"),
        )
        title_label.pack(pady=20)

        # Not implemented message
        msg_label = ttk.Label(
            center_frame,
            text="Not Implemented",
            font=("Segoe UI", 14),
            foreground=THEME.text_secondary,
        )
        msg_label.pack(pady=10)

        # Phase info
        phase_label = ttk.Label(
            center_frame,
            text=f"This step will be implemented in Phase {self._get_phase()}",
            font=("Segoe UI", 10),
            foreground=THEME.text_disabled,
        )
        phase_label.pack(pady=5)

    def _get_phase(self) -> int:
        """Get the implementation phase for this step.

        Returns:
            Phase number from the implementation plan.
        """
        # NOTE: Step order changed - 2=Estimation, 3=Information, 4=Preprocessing
        phase_map = {
            0: 1,   # Input
            1: 3,   # Analysis
            2: 6,   # Estimation (moved from position 4)
            3: 12,  # Information (moved from position 2)
            4: 5,   # Preprocessing (moved from position 3)
            5: 7,   # Translation
            6: 8,   # Quality Assurance
            7: 9,   # Postprocessing
            8: 10,  # Wordwrap
            9: 11,  # Output
        }
        return phase_map.get(self.step_id, 0)

    def on_enter(self) -> None:
        """Called when entering this tab."""
        pass  # Placeholder does nothing

    def on_leave(self) -> None:
        """Called when leaving this tab."""
        pass  # Placeholder does nothing
