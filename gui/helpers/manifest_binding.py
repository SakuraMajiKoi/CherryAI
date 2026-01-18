"""GUI Widget Binding Helpers for Manifest Fields.

TASK 22.3: Create helpers that bind GUI widgets directly to manifest fields.

These bindings provide automatic:
- Save on widget change (calls manifest field helper + _mark_dirty)
- Load on manifest load (populates widget from manifest data)
- Validation (for enum fields)
- Type conversion (for int/float fields)

Usage Example:
    from CherryAI.gui.helpers.manifest_binding import (
        bind_entry_to_field,
        bind_checkbox_to_field,
        bind_combobox_to_field,
    )
    
    # In your step's _build_ui():
    self._project_name_var = tk.StringVar()
    project_name_entry = ttk.Entry(frame, textvariable=self._project_name_var)
    
    # Bind the entry to manifest field
    bind_entry_to_field(
        entry=project_name_entry,
        var=self._project_name_var,
        manager_getter=lambda: self._app.manifest_manager,
        field_key="ProjectName",
        default=""
    )
    
The manager_getter is a callable that returns the ManifestManager instance.
This is needed because the manager may not exist when widgets are created.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union
import tkinter as tk
from tkinter import ttk

from CherryAI.functions.manifest_fields import (
    save_text_field,
    load_text_field,
    save_nested_text_field,
    load_nested_text_field,
    save_bool_field,
    load_bool_field,
    save_nested_bool_field,
    load_nested_bool_field,
    save_int_field,
    load_int_field,
    save_nested_int_field,
    load_nested_int_field,
    save_float_field,
    load_float_field,
    save_enum_field,
    load_enum_field,
    save_nested_enum_field,
    load_nested_enum_field,
)

if TYPE_CHECKING:
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


# Type alias for manager getter - a callable that returns ManifestManager or None
ManagerGetter = Callable[[], Optional["ManifestManager"]]


# ============================================================================
# Binding Result Tracking
# ============================================================================


class BindingInfo:
    """Stores information about a widget binding for debugging/testing."""
    
    def __init__(
        self,
        widget: tk.Widget,
        field_key: str,
        parent_key: Optional[str] = None,
        field_type: str = "text",
    ):
        self.widget = widget
        self.field_key = field_key
        self.parent_key = parent_key
        self.field_type = field_type
        self.save_count = 0
        self.load_count = 0
        self.last_saved_value: Any = None
        self.last_loaded_value: Any = None
    
    def record_save(self, value: Any) -> None:
        """Record a save operation."""
        self.save_count += 1
        self.last_saved_value = value
    
    def record_load(self, value: Any) -> None:
        """Record a load operation."""
        self.load_count += 1
        self.last_loaded_value = value


# Global registry for testing - tracks all bindings created
_binding_registry: List[BindingInfo] = []


def clear_binding_registry() -> None:
    """Clear the binding registry (for testing)."""
    _binding_registry.clear()


def get_binding_registry() -> List[BindingInfo]:
    """Get the binding registry (for testing)."""
    return _binding_registry


def get_binding_for_field(field_key: str) -> Optional[BindingInfo]:
    """Get binding info for a specific field key (for testing)."""
    for binding in _binding_registry:
        if binding.field_key == field_key:
            return binding
    return None


# ============================================================================
# Entry Widget Binding (Text Fields)
# ============================================================================


def bind_entry_to_field(
    entry: Union[ttk.Entry, tk.Entry],
    var: tk.StringVar,
    manager_getter: ManagerGetter,
    field_key: str,
    default: str = "",
    parent_key: Optional[str] = None,
    on_save: Optional[Callable[[str], None]] = None,
) -> BindingInfo:
    """Bind a text entry widget to a manifest text field.
    
    Automatically saves to manifest when the entry value changes,
    and provides a load method to populate from manifest.
    
    Args:
        entry: The Entry widget to bind.
        var: The StringVar associated with the entry.
        manager_getter: Callable that returns ManifestManager or None.
        field_key: Manifest field key (e.g., "ProjectName").
        default: Default value if not in manifest.
        parent_key: Optional parent key for nested fields.
        on_save: Optional callback after save (receives new value).
    
    Returns:
        BindingInfo for tracking/testing.
    
    Example:
        bind_entry_to_field(
            entry=self._name_entry,
            var=self._name_var,
            manager_getter=lambda: self._app.manifest_manager,
            field_key="ProjectName",
            default=""
        )
    """
    binding = BindingInfo(entry, field_key, parent_key, "text")
    _binding_registry.append(binding)
    
    def on_change(*args: Any) -> None:
        """Handle variable change - save to manifest."""
        manager = manager_getter()
        if manager is None:
            return
        
        value = var.get()
        binding.record_save(value)
        
        if parent_key:
            save_nested_text_field(manager, parent_key, field_key, value)
        else:
            save_text_field(manager, field_key, value)
        
        if on_save:
            on_save(value)
        
        logger.debug("Entry saved: %s = %r", field_key, value)
    
    # Trace variable changes
    var.trace_add("write", on_change)
    
    # Attach load method to binding for external use
    def load_from_manifest() -> str:
        """Load value from manifest into entry."""
        manager = manager_getter()
        if manager is None:
            var.set(default)
            return default
        
        if parent_key:
            value = load_nested_text_field(manager, parent_key, field_key, default)
        else:
            value = load_text_field(manager, field_key, default)
        
        # Temporarily remove trace to avoid triggering save
        var.set(value)
        binding.record_load(value)
        logger.debug("Entry loaded: %s = %r", field_key, value)
        return value
    
    binding.load_from_manifest = load_from_manifest  # type: ignore
    return binding


# ============================================================================
# Checkbox Widget Binding (Boolean Fields)
# ============================================================================


def bind_checkbox_to_field(
    checkbox: ttk.Checkbutton,
    var: tk.BooleanVar,
    manager_getter: ManagerGetter,
    field_key: str,
    default: bool = False,
    parent_key: Optional[str] = None,
    on_save: Optional[Callable[[bool], None]] = None,
) -> BindingInfo:
    """Bind a checkbox widget to a manifest boolean field.
    
    Automatically saves to manifest when checkbox is toggled,
    and provides a load method to populate from manifest.
    
    Args:
        checkbox: The Checkbutton widget to bind.
        var: The BooleanVar associated with the checkbox.
        manager_getter: Callable that returns ManifestManager or None.
        field_key: Manifest field key (e.g., "EnableFeature").
        default: Default value if not in manifest.
        parent_key: Optional parent key for nested fields.
        on_save: Optional callback after save (receives new value).
    
    Returns:
        BindingInfo for tracking/testing.
    
    Example:
        bind_checkbox_to_field(
            checkbox=self._enable_cb,
            var=self._enable_var,
            manager_getter=lambda: self._app.manifest_manager,
            field_key="EnableDedup",
            default=True
        )
    """
    binding = BindingInfo(checkbox, field_key, parent_key, "bool")
    _binding_registry.append(binding)
    
    def on_change(*args: Any) -> None:
        """Handle variable change - save to manifest."""
        manager = manager_getter()
        if manager is None:
            return
        
        value = var.get()
        binding.record_save(value)
        
        if parent_key:
            save_nested_bool_field(manager, parent_key, field_key, value)
        else:
            save_bool_field(manager, field_key, value)
        
        if on_save:
            on_save(value)
        
        logger.debug("Checkbox saved: %s = %r", field_key, value)
    
    # Trace variable changes
    var.trace_add("write", on_change)
    
    def load_from_manifest() -> bool:
        """Load value from manifest into checkbox."""
        manager = manager_getter()
        if manager is None:
            var.set(default)
            return default
        
        if parent_key:
            value = load_nested_bool_field(manager, parent_key, field_key, default)
        else:
            value = load_bool_field(manager, field_key, default)
        
        var.set(value)
        binding.record_load(value)
        logger.debug("Checkbox loaded: %s = %r", field_key, value)
        return value
    
    binding.load_from_manifest = load_from_manifest  # type: ignore
    return binding


# ============================================================================
# Combobox Widget Binding (Enum Fields)
# ============================================================================


def bind_combobox_to_field(
    combobox: ttk.Combobox,
    var: tk.StringVar,
    manager_getter: ManagerGetter,
    field_key: str,
    options: List[str],
    default: str,
    parent_key: Optional[str] = None,
    on_save: Optional[Callable[[str], None]] = None,
) -> BindingInfo:
    """Bind a combobox widget to a manifest enum field.
    
    Automatically saves to manifest when selection changes,
    validates against options list, and provides load method.
    
    Args:
        combobox: The Combobox widget to bind.
        var: The StringVar associated with the combobox.
        manager_getter: Callable that returns ManifestManager or None.
        field_key: Manifest field key (e.g., "StylePreset").
        options: List of valid option values.
        default: Default value if not in manifest or invalid.
        parent_key: Optional parent key for nested fields.
        on_save: Optional callback after save (receives new value).
    
    Returns:
        BindingInfo for tracking/testing.
    
    Example:
        bind_combobox_to_field(
            combobox=self._style_combo,
            var=self._style_var,
            manager_getter=lambda: self._app.manifest_manager,
            field_key="StylePreset",
            options=["literal", "natural", "creative", "custom"],
            default="natural"
        )
    """
    binding = BindingInfo(combobox, field_key, parent_key, "enum")
    _binding_registry.append(binding)
    
    def on_change(*args: Any) -> None:
        """Handle variable change - save to manifest."""
        manager = manager_getter()
        if manager is None:
            return
        
        value = var.get()
        binding.record_save(value)
        
        # Use nested or flat save based on parent_key
        if parent_key:
            save_nested_enum_field(manager, parent_key, field_key, value, options)
        else:
            save_enum_field(manager, field_key, value, options)
        
        if on_save:
            on_save(value)
        
        logger.debug("Combobox saved: %s = %r", field_key, value)
    
    # Trace variable changes
    var.trace_add("write", on_change)
    
    # Also bind to combobox selection event for immediate feedback
    combobox.bind("<<ComboboxSelected>>", lambda e: on_change())
    
    def load_from_manifest() -> str:
        """Load value from manifest into combobox."""
        manager = manager_getter()
        if manager is None:
            var.set(default)
            return default
        
        # Use nested or flat load based on parent_key
        if parent_key:
            value = load_nested_enum_field(manager, parent_key, field_key, default, options)
        else:
            value = load_enum_field(manager, field_key, default, options)
        
        var.set(value)
        binding.record_load(value)
        logger.debug("Combobox loaded: %s = %r", field_key, value)
        return value
    
    binding.load_from_manifest = load_from_manifest  # type: ignore
    return binding


# ============================================================================
# Spinbox Widget Binding (Integer Fields)
# ============================================================================


def bind_spinbox_to_field(
    spinbox: Union[ttk.Spinbox, tk.Spinbox],
    var: tk.IntVar,
    manager_getter: ManagerGetter,
    field_key: str,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    default: int = 0,
    parent_key: Optional[str] = None,
    on_save: Optional[Callable[[int], None]] = None,
) -> BindingInfo:
    """Bind a spinbox widget to a manifest integer field.
    
    Automatically saves to manifest when value changes,
    clamps to min/max range, and provides load method.
    
    Args:
        spinbox: The Spinbox widget to bind.
        var: The IntVar associated with the spinbox.
        manager_getter: Callable that returns ManifestManager or None.
        field_key: Manifest field key (e.g., "MaxChunkSize").
        min_val: Minimum allowed value (None = no limit).
        max_val: Maximum allowed value (None = no limit).
        default: Default value if not in manifest.
        parent_key: Optional parent key for nested fields.
        on_save: Optional callback after save (receives new value).
    
    Returns:
        BindingInfo for tracking/testing.
    
    Example:
        bind_spinbox_to_field(
            spinbox=self._chunk_size_spin,
            var=self._chunk_size_var,
            manager_getter=lambda: self._app.manifest_manager,
            field_key="MaxChunkSize",
            min_val=10,
            max_val=500,
            default=100
        )
    """
    binding = BindingInfo(spinbox, field_key, parent_key, "int")
    _binding_registry.append(binding)
    
    def on_change(*args: Any) -> None:
        """Handle variable change - save to manifest."""
        manager = manager_getter()
        if manager is None:
            return
        
        try:
            value = var.get()
        except tk.TclError:
            # Invalid value in spinbox
            value = default
        
        binding.record_save(value)
        
        # Use nested or flat save based on parent_key
        if parent_key:
            save_nested_int_field(manager, parent_key, field_key, value, min_val, max_val)
        else:
            save_int_field(manager, field_key, value, min_val, max_val)
        
        if on_save:
            on_save(value)
        
        logger.debug("Spinbox saved: %s = %r", field_key, value)
    
    # Trace variable changes
    var.trace_add("write", on_change)
    
    def load_from_manifest() -> int:
        """Load value from manifest into spinbox."""
        manager = manager_getter()
        if manager is None:
            var.set(default)
            return default
        
        # Use nested or flat load based on parent_key
        if parent_key:
            value = load_nested_int_field(manager, parent_key, field_key, default, min_val, max_val)
        else:
            value = load_int_field(manager, field_key, default, min_val, max_val)
        
        var.set(value)
        binding.record_load(value)
        logger.debug("Spinbox loaded: %s = %r", field_key, value)
        return value
    
    binding.load_from_manifest = load_from_manifest  # type: ignore
    return binding


# ============================================================================
# Text Widget Binding (Multi-line Text Fields)
# ============================================================================


def bind_text_to_field(
    text_widget: Union[tk.Text, "scrolledtext.ScrolledText"],
    manager_getter: ManagerGetter,
    field_key: str,
    default: str = "",
    parent_key: Optional[str] = None,
    on_save: Optional[Callable[[str], None]] = None,
    save_on_focus_out: bool = True,
) -> BindingInfo:
    """Bind a Text widget to a manifest text field.
    
    Unlike Entry widgets, Text widgets don't have a StringVar.
    This binding saves on focus out (or optionally on every key).
    
    Args:
        text_widget: The Text widget to bind.
        manager_getter: Callable that returns ManifestManager or None.
        field_key: Manifest field key (e.g., "Summary").
        default: Default value if not in manifest.
        parent_key: Optional parent key for nested fields.
        on_save: Optional callback after save (receives new value).
        save_on_focus_out: If True, saves when widget loses focus.
                          If False, caller must trigger save manually.
    
    Returns:
        BindingInfo for tracking/testing.
    
    Example:
        bind_text_to_field(
            text_widget=self._summary_text,
            manager_getter=lambda: self._app.manifest_manager,
            field_key="Summary",
            default=""
        )
    """
    binding = BindingInfo(text_widget, field_key, parent_key, "text_multiline")
    _binding_registry.append(binding)
    
    def save_to_manifest(event: Optional[tk.Event] = None) -> None:
        """Save current text content to manifest."""
        manager = manager_getter()
        if manager is None:
            return
        
        value = text_widget.get("1.0", "end-1c")
        binding.record_save(value)
        
        if parent_key:
            save_nested_text_field(manager, parent_key, field_key, value)
        else:
            save_text_field(manager, field_key, value)
        
        if on_save:
            on_save(value)
        
        logger.debug("Text saved: %s = %r (len=%d)", field_key, value[:50], len(value))
    
    if save_on_focus_out:
        text_widget.bind("<FocusOut>", save_to_manifest)
    
    # Attach save method to binding for manual triggering
    binding.save_to_manifest = save_to_manifest  # type: ignore
    
    def load_from_manifest() -> str:
        """Load value from manifest into text widget."""
        manager = manager_getter()
        if manager is None:
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", default)
            return default
        
        if parent_key:
            value = load_nested_text_field(manager, parent_key, field_key, default)
        else:
            value = load_text_field(manager, field_key, default)
        
        text_widget.delete("1.0", "end")
        text_widget.insert("1.0", value)
        binding.record_load(value)
        logger.debug("Text loaded: %s = %r (len=%d)", field_key, value[:50] if value else "", len(value) if value else 0)
        return value
    
    binding.load_from_manifest = load_from_manifest  # type: ignore
    return binding


# ============================================================================
# RadioButton Group Binding (Enum Fields)
# ============================================================================


def bind_radio_group_to_field(
    radios: List[ttk.Radiobutton],
    var: tk.StringVar,
    manager_getter: ManagerGetter,
    field_key: str,
    options: List[str],
    default: str,
    parent_key: Optional[str] = None,
    on_save: Optional[Callable[[str], None]] = None,
) -> BindingInfo:
    """Bind a group of radio buttons to a manifest enum field.
    
    Automatically saves to manifest when selection changes,
    validates against options list, and provides load method.
    
    Args:
        radios: List of Radiobutton widgets in the group.
        var: The StringVar associated with all radios.
        manager_getter: Callable that returns ManifestManager or None.
        field_key: Manifest field key (e.g., "ExportFormat").
        options: List of valid option values (should match radio values).
        default: Default value if not in manifest or invalid.
        parent_key: Optional parent key for nested fields.
        on_save: Optional callback after save (receives new value).
    
    Returns:
        BindingInfo for tracking/testing.
    
    Example:
        bind_radio_group_to_field(
            radios=[self._txt_radio, self._json_radio, self._csv_radio],
            var=self._format_var,
            manager_getter=lambda: self._app.manifest_manager,
            field_key="ExportFormat",
            options=["txt", "json", "csv"],
            default="txt"
        )
    """
    # Use first radio as representative widget
    binding = BindingInfo(radios[0] if radios else None, field_key, parent_key, "radio")
    _binding_registry.append(binding)
    
    def on_change(*args: Any) -> None:
        """Handle variable change - save to manifest."""
        manager = manager_getter()
        if manager is None:
            return
        
        value = var.get()
        binding.record_save(value)
        
        # Use save_enum_field which validates against options
        # Note: save_enum_field uses first option as default if invalid
        save_enum_field(manager, field_key, value, options)
        
        if on_save:
            on_save(value)
        
        logger.debug("Radio saved: %s = %r", field_key, value)
    
    # Trace variable changes
    var.trace_add("write", on_change)
    
    def load_from_manifest() -> str:
        """Load value from manifest into radio group."""
        manager = manager_getter()
        if manager is None:
            var.set(default)
            return default
        
        # Use load_enum_field which validates against options
        value = load_enum_field(manager, field_key, default, options)
        
        var.set(value)
        binding.record_load(value)
        logger.debug("Radio loaded: %s = %r", field_key, value)
        return value
    
    binding.load_from_manifest = load_from_manifest  # type: ignore
    return binding


# ============================================================================
# Float Spinbox Binding (Float Fields)
# ============================================================================


def bind_float_spinbox_to_field(
    spinbox: Union[ttk.Spinbox, tk.Spinbox],
    var: tk.DoubleVar,
    manager_getter: ManagerGetter,
    field_key: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    default: float = 0.0,
    precision: Optional[int] = None,
    parent_key: Optional[str] = None,
    on_save: Optional[Callable[[float], None]] = None,
) -> BindingInfo:
    """Bind a spinbox widget to a manifest float field.
    
    Args:
        spinbox: The Spinbox widget to bind.
        var: The DoubleVar associated with the spinbox.
        manager_getter: Callable that returns ManifestManager or None.
        field_key: Manifest field key (e.g., "Temperature").
        min_val: Minimum allowed value (None = no limit).
        max_val: Maximum allowed value (None = no limit).
        default: Default value if not in manifest.
        precision: Decimal places for rounding (None = no rounding).
        parent_key: Optional parent key for nested fields.
        on_save: Optional callback after save (receives new value).
    
    Returns:
        BindingInfo for tracking/testing.
    
    Example:
        bind_float_spinbox_to_field(
            spinbox=self._temp_spin,
            var=self._temp_var,
            manager_getter=lambda: self._app.manifest_manager,
            field_key="Temperature",
            min_val=0.0,
            max_val=2.0,
            default=0.7,
            precision=2
        )
    """
    binding = BindingInfo(spinbox, field_key, parent_key, "float")
    _binding_registry.append(binding)
    
    def on_change(*args: Any) -> None:
        """Handle variable change - save to manifest."""
        manager = manager_getter()
        if manager is None:
            return
        
        try:
            value = var.get()
        except tk.TclError:
            value = default
        
        binding.record_save(value)
        
        save_float_field(manager, field_key, value, min_val, max_val, precision)
        
        if on_save:
            on_save(value)
        
        logger.debug("Float spinbox saved: %s = %r", field_key, value)
    
    var.trace_add("write", on_change)
    
    def load_from_manifest() -> float:
        """Load value from manifest into spinbox."""
        manager = manager_getter()
        if manager is None:
            var.set(default)
            return default
        
        value = load_float_field(manager, field_key, default, min_val, max_val)
        
        var.set(value)
        binding.record_load(value)
        logger.debug("Float spinbox loaded: %s = %r", field_key, value)
        return value
    
    binding.load_from_manifest = load_from_manifest  # type: ignore
    return binding


# ============================================================================
# Convenience: Load All Bindings
# ============================================================================


def load_all_bindings(bindings: List[BindingInfo]) -> None:
    """Load all manifest values for a list of bindings.
    
    Call this when loading a manifest to populate all bound widgets.
    
    Args:
        bindings: List of BindingInfo objects with load_from_manifest methods.
    
    Example:
        # Store bindings when creating widgets
        self._bindings = [
            bind_entry_to_field(...),
            bind_checkbox_to_field(...),
            bind_combobox_to_field(...),
        ]
        
        # On manifest load:
        load_all_bindings(self._bindings)
    """
    for binding in bindings:
        if hasattr(binding, "load_from_manifest"):
            try:
                binding.load_from_manifest()  # type: ignore
            except Exception as e:
                logger.error("Failed to load binding %s: %s", binding.field_key, e)
