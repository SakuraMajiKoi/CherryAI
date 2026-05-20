"""CherryAI GUI v2 Enhanced Progress Tracker.

Provides an enhanced progress tracker panel with:
- Preset selection and application
- Step status display with icons
- Skip/rollback functionality
- Subtask expansion
- Completion percentage display
- Keyboard shortcut hints
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from CherryAI.gui.theme.colors import THEME
from CherryAI.gui.state.store import (
    SessionState,
    StepState,
    STEP_DEFINITIONS,
    PRESET_DEFINITIONS,
    get_preset_names,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes for Subtask Tracking (TASK 18.3)
# ============================================================================


@dataclass
class Subtask:
    """Represents a subtask within a step.
    
    Subtasks provide granular progress updates within longer-running steps
    like Analysis or Translation.
    
    Attributes:
        name: Display name of the subtask.
        status: Current status ('pending', 'running', 'completed', 'failed').
        progress: Progress percentage (0-100).
        message: Optional status message.
    """
    
    name: str
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subtask":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            status=data.get("status", "pending"),
            progress=data.get("progress", 0.0),
            message=data.get("message", ""),
        )


@dataclass
class SubtaskGroup:
    """A group of subtasks for a step.
    
    Attributes:
        step_id: The parent step ID.
        subtasks: List of subtasks in order.
        expanded: Whether the subtask list is expanded in UI.
    """
    
    step_id: int
    subtasks: List[Subtask] = field(default_factory=list)
    expanded: bool = False
    
    def add_subtask(self, name: str) -> Subtask:
        """Add a new subtask.
        
        Args:
            name: Display name for the subtask.
            
        Returns:
            The created Subtask instance.
        """
        subtask = Subtask(name=name)
        self.subtasks.append(subtask)
        return subtask
    
    def update_subtask(
        self,
        name: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
    ) -> bool:
        """Update a subtask by name.
        
        Args:
            name: Name of the subtask to update.
            status: New status (optional).
            progress: New progress (optional).
            message: New message (optional).
            
        Returns:
            True if subtask was found and updated.
        """
        for subtask in self.subtasks:
            if subtask.name == name:
                if status is not None:
                    subtask.status = status
                if progress is not None:
                    subtask.progress = progress
                if message is not None:
                    subtask.message = message
                return True
        return False
    
    def get_overall_progress(self) -> float:
        """Get overall progress of all subtasks.
        
        Returns:
            Average progress percentage (0-100).
        """
        if not self.subtasks:
            return 0.0
        return sum(s.progress for s in self.subtasks) / len(self.subtasks)
    
    def clear(self) -> None:
        """Clear all subtasks."""
        self.subtasks.clear()


class StepRow(ttk.Frame):
    """A single row in the progress tracker representing one workflow step.

    Provides:
    - Status icon (✓, –, ✗, ⊘ for skipped)
    - Dual tick display for multi-phase steps (Task 40.5)
    - Clickable step name
    - Context menu for skip/rollback
    - Subtask expansion with progress display
    """

    def __init__(
        self,
        parent: tk.Widget,
        step_state: StepState,
        is_current: bool,
        on_click: Callable[[int], None],
        on_skip: Callable[[int], None],
        on_rollback: Callable[[int], None],
        subtask_group: Optional[SubtaskGroup] = None,
        dual_ticks: Optional[Tuple[bool, bool]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize step row.

        Args:
            parent: Parent widget.
            step_state: State for this step.
            is_current: Whether this is the current step.
            on_click: Callback when step is clicked.
            on_skip: Callback to skip this step.
            on_rollback: Callback to rollback this step.
            subtask_group: Optional subtask group for this step.
            dual_ticks: Optional tuple of (tick1, tick2) for dual-phase
                steps. None means single-icon mode.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(parent, **kwargs)
        self.step_state = step_state
        self.is_current = is_current
        self.on_click = on_click
        self.on_skip = on_skip
        self.on_rollback = on_rollback
        self.subtask_group = subtask_group
        self.dual_ticks = dual_ticks
        self._subtasks_frame: Optional[ttk.Frame] = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the step row UI."""
        self.configure(style="TFrame")
        
        # Main row frame
        main_row = ttk.Frame(self)
        main_row.pack(fill="x")

        # Status icon
        icon = self._get_status_icon()
        icon_color = self._get_status_color()
        self._status_label = ttk.Label(
            main_row,
            text=icon,
            font=("Segoe UI", 10),
            width=3,
            foreground=icon_color,
        )
        self._status_label.pack(side="left")

        # Step name (clickable)
        step_text = f"{self.step_state.step_id + 1}. {self.step_state.name}"
        font = ("Segoe UI", 9, "bold") if self.is_current else ("Segoe UI", 9)
        self._name_label = ttk.Label(
            main_row,
            text=step_text,
            font=font,
            cursor="hand2",
        )
        self._name_label.pack(side="left", fill="x", expand=True)
        
        # Subtask expand/collapse button (if has subtasks)
        if self.subtask_group and self.subtask_group.subtasks:
            expand_text = "▼" if self.subtask_group.expanded else "▶"
            self._expand_btn = ttk.Label(
                main_row,
                text=expand_text,
                font=("Segoe UI", 8),
                cursor="hand2",
            )
            self._expand_btn.pack(side="right", padx=2)
            self._expand_btn.bind("<Button-1>", self._toggle_subtasks)

        # Bind click event
        self._name_label.bind(
            "<Button-1>", lambda e: self.on_click(self.step_state.step_id)
        )

        # Bind right-click context menu
        self._name_label.bind("<Button-3>", self._show_context_menu)
        self._status_label.bind("<Button-3>", self._show_context_menu)
        
        # Build subtasks frame (if expanded)
        if self.subtask_group and self.subtask_group.expanded:
            self._build_subtasks()

    def _build_subtasks(self) -> None:
        """Build the subtasks display (indented under main row)."""
        if not self.subtask_group or not self.subtask_group.subtasks:
            return
            
        self._subtasks_frame = ttk.Frame(self)
        self._subtasks_frame.pack(fill="x", padx=(20, 0))
        
        for subtask in self.subtask_group.subtasks:
            subtask_row = ttk.Frame(self._subtasks_frame)
            subtask_row.pack(fill="x", pady=1)
            
            # Subtask status icon
            icon = self._get_subtask_icon(subtask.status)
            color = self._get_subtask_color(subtask.status)
            ttk.Label(
                subtask_row,
                text=icon,
                font=("Segoe UI", 8),
                foreground=color,
                width=2,
            ).pack(side="left")
            
            # Subtask name
            ttk.Label(
                subtask_row,
                text=subtask.name,
                font=("Segoe UI", 8),
                foreground=THEME.text_secondary,
            ).pack(side="left")
            
            # Progress bar (if running)
            if subtask.status == "running" and subtask.progress > 0:
                progress_var = tk.DoubleVar(value=subtask.progress)
                ttk.Progressbar(
                    subtask_row,
                    variable=progress_var,
                    maximum=100,
                    length=50,
                ).pack(side="right", padx=2)
            
            # Message (if any)
            if subtask.message:
                ttk.Label(
                    subtask_row,
                    text=subtask.message,
                    font=("Segoe UI", 7),
                    foreground=THEME.text_disabled,
                ).pack(side="right", padx=5)

    def _toggle_subtasks(self, event: Optional[tk.Event] = None) -> None:
        """Toggle subtask expansion."""
        if not self.subtask_group:
            return
            
        self.subtask_group.expanded = not self.subtask_group.expanded
        
        if self.subtask_group.expanded:
            self._expand_btn.configure(text="▼")
            self._build_subtasks()
        else:
            self._expand_btn.configure(text="▶")
            if self._subtasks_frame:
                self._subtasks_frame.destroy()
                self._subtasks_frame = None

    def _get_subtask_icon(self, status: str) -> str:
        """Get icon for subtask status."""
        icons = {
            "pending": "○",
            "running": "◐",
            "completed": "●",
            "failed": "✗",
        }
        return icons.get(status, "○")

    def _get_subtask_color(self, status: str) -> str:
        """Get color for subtask status."""
        colors = {
            "pending": THEME.text_disabled,
            "running": THEME.accent_info,
            "completed": THEME.accent_success,
            "failed": THEME.accent_error,
        }
        return colors.get(status, THEME.text_disabled)

    def _get_status_icon(self) -> str:
        """Get the status icon for this step.

        For dual-tick steps (Task 40.5), returns ☐☐ / ☑☐ / ☑☑.
        Otherwise returns the standard single-character icon.

        Returns:
            Status icon character(s).
        """
        if self.dual_ticks is not None:
            tick1, tick2 = self.dual_ticks
            c1 = "☑" if tick1 else "☐"
            c2 = "☑" if tick2 else "☐"
            return f"{c1}{c2}"
        if self.step_state.skipped:
            return "⊘"  # Skipped
        icons = {
            "completed": "✓",
            "partial": "◐",
            "in-progress": "–",
            "not-started": "✗",
        }
        return icons.get(self.step_state.status, "✗")

    def _get_status_color(self) -> str:
        """Get the status color for this step.

        Returns:
            Color string.
        """
        if self.step_state.skipped:
            return THEME.text_disabled
        colors = {
            "completed": THEME.accent_success,
            "partial": THEME.accent_warning,
            "in-progress": THEME.accent_info,
            "not-started": THEME.text_disabled,
        }
        return colors.get(self.step_state.status, THEME.text_disabled)

    def _show_context_menu(self, event: tk.Event) -> None:
        """Show context menu for step actions.

        Args:
            event: Mouse event.
        """
        menu = tk.Menu(self, tearoff=0)

        # Skip option (only for not-completed steps)
        if self.step_state.status not in {"completed", "partial"}:
            menu.add_command(
                label="Skip Step",
                command=lambda: self.on_skip(self.step_state.step_id),
            )

        # Rollback option (only for completed steps)
        if self.step_state.status in {"completed", "partial"}:
            menu.add_command(
                label="Rollback Step",
                command=lambda: self.on_rollback(self.step_state.step_id),
            )

        if menu.index("end") is not None:
            menu.tk_popup(event.x_root, event.y_root)


class ProgressPanel(ttk.Frame):
    """Enhanced progress tracker panel.

    Features:
    - Preset selection dropdown
    - Step list with status icons
    - Skip/rollback per step
    - Completion percentage
    - Collapsible design
    """

    def __init__(
        self,
        parent: tk.Widget,
        session: SessionState,
        on_step_click: Callable[[int], None],
        **kwargs: Any,
    ) -> None:
        """Initialize progress panel.

        Args:
            parent: Parent widget.
            session: Session state reference.
            on_step_click: Callback when a step is clicked.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(parent, **kwargs)
        self.session = session
        self.on_step_click = on_step_click
        self._collapsed = False
        self._step_rows: List[StepRow] = []
        self._subtask_groups: Dict[int, SubtaskGroup] = {}
        # Task 40.5: Dual ticks state per step (step_id -> (tick1, tick2))
        self._dual_ticks: Dict[int, Tuple[bool, bool]] = {}
        self._build_ui()

        # Listen for session changes
        self.session.add_change_listener(self._on_session_change)

    def _build_ui(self) -> None:
        """Build the progress panel UI."""
        self.configure(style="TFrame")

        # Header with collapse button
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", padx=5, pady=5)

        self._header_label = ttk.Label(
            header_frame,
            text="Progress",
            font=("Segoe UI", 11, "bold"),
        )
        self._header_label.pack(side="left")

        self._collapse_btn = ttk.Button(
            header_frame,
            text="◀",
            width=3,
            command=self._toggle_collapse,
        )
        self._collapse_btn.pack(side="right")

        # Separator
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=5)

        # Content frame (collapsible)
        self._content_frame = ttk.Frame(self)
        self._content_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Preset selector
        self._build_preset_section()

        # Completion bar
        self._build_completion_section()

        # Steps container
        self._steps_frame = ttk.Frame(self._content_frame)
        self._steps_frame.pack(fill="both", expand=True, pady=5)

        # Shortcuts hint
        self._build_shortcuts_section()

        # Build step list
        self._rebuild_steps()

    def _build_preset_section(self) -> None:
        """Build the preset selector section."""
        preset_frame = ttk.LabelFrame(self._content_frame, text="Workflow Preset")
        preset_frame.pack(fill="x", pady=5)

        self._preset_var = tk.StringVar(value=self.session.active_preset)
        preset_cb = ttk.Combobox(
            preset_frame,
            textvariable=self._preset_var,
            values=get_preset_names(),
            state="readonly",
            width=20,
        )
        preset_cb.pack(padx=5, pady=5, fill="x")
        preset_cb.bind("<<ComboboxSelected>>", self._on_preset_change)

        # Preset description
        self._preset_desc = ttk.Label(
            preset_frame,
            text=self._get_preset_description(self.session.active_preset),
            font=("Segoe UI", 8),
            foreground=THEME.text_secondary,
            wraplength=180,
        )
        self._preset_desc.pack(padx=5, pady=(0, 5))

    def _build_completion_section(self) -> None:
        """Build the completion percentage section."""
        completion_frame = ttk.Frame(self._content_frame)
        completion_frame.pack(fill="x", pady=5)

        self._completion_label = ttk.Label(
            completion_frame,
            text="0% Complete",
            font=("Segoe UI", 9),
        )
        self._completion_label.pack(side="left")

        self._completion_var = tk.DoubleVar(value=0)
        self._completion_bar = ttk.Progressbar(
            completion_frame,
            variable=self._completion_var,
            maximum=100,
            length=100,
        )
        self._completion_bar.pack(side="right", padx=5)

        self._update_completion()

    def _build_shortcuts_section(self) -> None:
        """Build the keyboard shortcuts hint section."""
        shortcuts_frame = ttk.LabelFrame(self._content_frame, text="Shortcuts")
        shortcuts_frame.pack(fill="x", pady=5)

        shortcuts_text = "Ctrl+D: Mark done\nCtrl+Z: Undo\nCtrl+Y: Redo"
        shortcuts_label = ttk.Label(
            shortcuts_frame,
            text=shortcuts_text,
            font=("Segoe UI", 8),
            foreground=THEME.text_secondary,
        )
        shortcuts_label.pack(padx=5, pady=5)

    def _rebuild_steps(self) -> None:
        """Rebuild the step list."""
        # Clear existing
        for widget in self._steps_frame.winfo_children():
            widget.destroy()
        self._step_rows.clear()

        # Create step rows
        for step_id, step_name in STEP_DEFINITIONS:
            step_state = self.session.get_step(step_id)
            is_current = step_id == self.session.current_step
            subtask_group = self._subtask_groups.get(step_id)

            # Task 40.5: Dual ticks for Costs step (step_id 2)
            dual_ticks = self._dual_ticks.get(step_id)

            row = StepRow(
                self._steps_frame,
                step_state=step_state,
                is_current=is_current,
                on_click=self.on_step_click,
                on_skip=self._on_skip_step,
                on_rollback=self._on_rollback_step,
                subtask_group=subtask_group,
                dual_ticks=dual_ticks,
            )
            row.pack(fill="x", pady=1)
            self._step_rows.append(row)

    def _update_completion(self) -> None:
        """Update the completion percentage display."""
        percentage = self.session.get_completion_percentage()
        self._completion_var.set(percentage)
        self._completion_label.configure(text=f"{percentage:.0f}% Complete")

    def _get_preset_description(self, preset_name: str) -> str:
        """Get the description for a preset.

        Args:
            preset_name: Name of the preset.

        Returns:
            Preset description string.
        """
        if preset_name in PRESET_DEFINITIONS:
            return PRESET_DEFINITIONS[preset_name].get("description", "")
        return ""

    def _toggle_collapse(self) -> None:
        """Toggle collapsed state."""
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._content_frame.pack_forget()
            self._collapse_btn.configure(text="▶")
            self._header_label.configure(text="")
        else:
            self._content_frame.pack(fill="both", expand=True, padx=5, pady=5)
            self._collapse_btn.configure(text="◀")
            self._header_label.configure(text="Progress")

    def _on_preset_change(self, event: tk.Event) -> None:
        """Handle preset selection change.

        Args:
            event: Combobox event.
        """
        preset_name = self._preset_var.get()
        if preset_name != self.session.active_preset:
            if messagebox.askyesno(
                "Apply Preset",
                f"Apply '{preset_name}' preset?\n\n"
                f"{self._get_preset_description(preset_name)}\n\n"
                "This will reset step statuses.",
            ):
                try:
                    self.session.apply_preset(preset_name)
                    self._preset_desc.configure(
                        text=self._get_preset_description(preset_name)
                    )
                    self.refresh()
                except ValueError as e:
                    messagebox.showerror("Error", str(e))
            else:
                # Revert combobox to current preset
                self._preset_var.set(self.session.active_preset)

    def _on_skip_step(self, step_id: int) -> None:
        """Handle skip step request.

        Args:
            step_id: Step to skip.
        """
        step_name = STEP_DEFINITIONS[step_id][1]
        if messagebox.askyesno(
            "Skip Step",
            f"Skip step {step_id + 1}: {step_name}?\n\n"
            "The step will be marked as completed without running.",
        ):
            self.session.mark_skipped(step_id)
            self.refresh()

    def _on_rollback_step(self, step_id: int) -> None:
        """Handle rollback step request.

        Args:
            step_id: Step to rollback.
        """
        step_name = STEP_DEFINITIONS[step_id][1]
        if messagebox.askyesno(
            "Rollback Step",
            f"Rollback step {step_id + 1}: {step_name}?\n\n"
            "The step will be reset to 'not started' state.",
        ):
            self.session.rollback_step(step_id)
            self.refresh()

    def _on_session_change(self) -> None:
        """Handle session state change notification."""
        # Refresh UI when session changes
        self.after(0, self.refresh)

    def refresh(self) -> None:
        """Refresh the progress panel to reflect current state."""
        self._rebuild_steps()
        self._update_completion()
        self._preset_var.set(self.session.active_preset)
        self._preset_desc.configure(
            text=self._get_preset_description(self.session.active_preset)
        )

    # ========================================================================
    # Subtask Management API (TASK 18.3)
    # ========================================================================

    def register_subtasks(self, step_id: int, subtask_names: List[str]) -> None:
        """Register subtasks for a step.
        
        Call this at the start of a long-running process to define the subtasks.
        
        Args:
            step_id: The step ID (0-9).
            subtask_names: List of subtask display names in order.
            
        Example:
            progress.register_subtasks(1, [
                "Loading files",
                "Analyzing patterns",
                "Detecting speakers",
                "Generating report",
            ])
        """
        group = SubtaskGroup(step_id=step_id)
        for name in subtask_names:
            group.add_subtask(name)
        self._subtask_groups[step_id] = group
        logger.debug(f"Registered {len(subtask_names)} subtasks for step {step_id}")
        self.refresh()

    def update_subtask(
        self,
        step_id: int,
        subtask_name: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
    ) -> None:
        """Update a subtask's status/progress.
        
        Args:
            step_id: The step ID containing the subtask.
            subtask_name: Name of the subtask to update.
            status: New status ('pending', 'running', 'completed', 'failed').
            progress: Progress percentage (0-100).
            message: Optional status message.
            
        Example:
            progress.update_subtask(1, "Loading files", status="running", progress=50)
            progress.update_subtask(1, "Loading files", status="completed", progress=100)
        """
        group = self._subtask_groups.get(step_id)
        if group:
            if group.update_subtask(subtask_name, status, progress, message):
                self.refresh()
            else:
                logger.warning(f"Subtask '{subtask_name}' not found in step {step_id}")

    def complete_subtask(self, step_id: int, subtask_name: str) -> None:
        """Mark a subtask as completed.
        
        Convenience method equivalent to update_subtask(..., status='completed', progress=100).
        
        Args:
            step_id: The step ID containing the subtask.
            subtask_name: Name of the subtask to complete.
        """
        self.update_subtask(step_id, subtask_name, status="completed", progress=100.0)

    def fail_subtask(self, step_id: int, subtask_name: str, message: str = "") -> None:
        """Mark a subtask as failed.
        
        Args:
            step_id: The step ID containing the subtask.
            subtask_name: Name of the subtask that failed.
            message: Optional error message.
        """
        self.update_subtask(step_id, subtask_name, status="failed", message=message)

    def clear_subtasks(self, step_id: int) -> None:
        """Clear all subtasks for a step.
        
        Call this when a step completes or is reset.
        
        Args:
            step_id: The step ID to clear subtasks from.
        """
        if step_id in self._subtask_groups:
            del self._subtask_groups[step_id]
            self.refresh()

    def get_subtask_progress(self, step_id: int) -> float:
        """Get overall subtask progress for a step.
        
        Args:
            step_id: The step ID to check.
            
        Returns:
            Average progress percentage (0-100), or 0 if no subtasks.
        """
        group = self._subtask_groups.get(step_id)
        if group:
            return group.get_overall_progress()
        return 0.0

    def expand_subtasks(self, step_id: int, expanded: bool = True) -> None:
        """Expand or collapse subtasks for a step.
        
        Args:
            step_id: The step ID to expand/collapse.
            expanded: True to expand, False to collapse.
        """
        group = self._subtask_groups.get(step_id)
        if group:
            group.expanded = expanded
            self.refresh()

    # ========================================================================
    # Dual Tick API (TASK 40.5)
    # ========================================================================

    def set_dual_ticks(
        self,
        step_id: int,
        tick1: bool,
        tick2: bool,
    ) -> None:
        """Set dual tick state for a multi-phase step (Task 40.5).

        Args:
            step_id: The step ID to set dual ticks for.
            tick1: Whether the first tick is checked.
            tick2: Whether the second tick is checked.
        """
        self._dual_ticks[step_id] = (tick1, tick2)
        self.refresh()

    def clear_dual_ticks(self, step_id: int) -> None:
        """Remove dual tick state for a step.

        Args:
            step_id: The step ID to clear dual ticks from.
        """
        self._dual_ticks.pop(step_id, None)
        self.refresh()

    def get_dual_ticks(self, step_id: int) -> Optional[Tuple[bool, bool]]:
        """Get dual tick state for a step.

        Args:
            step_id: The step ID to check.

        Returns:
            Tuple of (tick1, tick2) or None if not a dual-tick step.
        """
        return self._dual_ticks.get(step_id)

    def destroy(self) -> None:
        """Clean up when widget is destroyed."""
        self.session.remove_change_listener(self._on_session_change)
        super().destroy()


class ProgressTracker(ProgressPanel):
    """Alias for ProgressPanel for backwards compatibility.

    This class is used by gui/app.py and maintains the same interface.
    """

    pass
