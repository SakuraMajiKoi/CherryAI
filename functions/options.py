"""Options dialog and state management for CherryAI GUI.

Centralizes options UI logic and state gathering.
Safe dependency chain: options.py → config.py → languages.py → stdlib only
(gui.py lazily imports options.py when needed)

Provides comprehensive API configuration through a tabbed dialog:
- General: Debug, autosave settings
- API: Provider, key, model, temperature, timeouts
- Translation: Source/target language, batch size
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import (
    get_api_config,
    get_ui_state,
    set_api_config,
    set_ui_state,
    DEFAULT_CONFIG,
)
from .languages import get_language_names


# =============================================================================
# API PROVIDERS - SINGLE SOURCE OF TRUTH
# =============================================================================

# Supported API providers with their default base URLs and models
# This is the canonical definition - import from here, don't duplicate!
API_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    },
    "local": {
        "name": "Local/Custom",
        "base_url": "http://localhost:11434/v1",
        "models": ["local-model", "custom"],
    },
    "ollama": {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3", "mistral", "codellama"],
    },
    "lmstudio": {
        "name": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "models": ["local-model"],
    },
}


def get_api_urls() -> Dict[str, str]:
    """Get mapping of provider keys to base URLs.

    Returns:
        Dict mapping provider key to base URL string.
        Compatible with CLI.py KNOWN_API_URLS format.
    """
    return {key: info["base_url"] for key, info in API_PROVIDERS.items()}


def get_provider_models(provider: str) -> List[str]:
    """Get list of models for a specific provider.

    Args:
        provider: Provider key (e.g., 'openai', 'gemini').

    Returns:
        List of model names for the provider, or empty list if not found.
    """
    if provider in API_PROVIDERS:
        return API_PROVIDERS[provider].get("models", [])
    return []


def get_all_provider_models() -> Dict[str, List[str]]:
    """Get mapping of all providers to their models.

    Returns:
        Dict mapping provider key to list of model names.
        Compatible with CLI.py KNOWN_MODELS format.
    """
    return {key: info["models"] for key, info in API_PROVIDERS.items()}


def get_provider_names() -> List[str]:
    """Get list of all provider keys.

    Returns:
        List of provider key strings.
    """
    return list(API_PROVIDERS.keys())


def get_provider_display_name(provider: str) -> str:
    """Get display name for a provider.

    Args:
        provider: Provider key (e.g., 'openai').

    Returns:
        Human-readable provider name, or the key if not found.
    """
    if provider in API_PROVIDERS:
        return API_PROVIDERS[provider].get("name", provider)
    return provider

# Supported languages for translation
# Imported from languages.py - single source of truth
SUPPORTED_LANGUAGES: List[str] = get_language_names()


class OptionsDialog(tk.Toplevel):
    """Modal dialog for managing application options and preferences.

    Provides a tabbed interface for:
    - General settings (debug, autosave)
    - API configuration (provider, key, model, temperature)
    - Translation settings (languages, batch size, timeouts)

    Callback is invoked with final state dict when user saves.
    """

    def __init__(
        self,
        parent: tk.Tk,
        initial_state: Optional[Dict[str, Any]] = None,
        on_save: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        """Initialize Options dialog.

        Args:
            parent: Parent window (usually the main App).
            initial_state: Initial state dict to populate form (UI state).
            on_save: Callback when user saves (receives combined state dict).
        """
        super().__init__(parent)
        self.title("CherryAI Options")
        self.geometry("600x550")
        self.resizable(True, True)
        self.minsize(500, 450)

        self.parent = parent
        self.on_save = on_save
        self.result_state: Dict[str, Any] = {}

        # Load current configs
        self.ui_state = initial_state or get_ui_state()
        self.api_config = get_api_config()

        # Variables for form controls
        self._init_variables()

        self._build_ui()
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        """Center the dialog on the parent window."""
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        dialog_w = self.winfo_width()
        dialog_h = self.winfo_height()
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        self.geometry(f"+{x}+{y}")

    def _init_variables(self) -> None:
        """Initialize all tkinter variables for form controls."""
        # General settings
        self.debug_var = tk.BooleanVar(value=self.ui_state.get("debug", False))
        self.autosave_var = tk.BooleanVar(value=self.ui_state.get("autosave", True))

        # Glossary settings (from UI state)
        self.glossary_update_mode_var = tk.StringVar(
            value=self.ui_state.get("glossary_update_mode", "Update")
        )
        self.gender_confidence_var = tk.IntVar(
            value=int(self.ui_state.get("gender_confidence", 75))
        )

        # API settings
        self.provider_var = tk.StringVar(
            value=self.api_config.get("provider", "openai")
        )
        self.api_key_var = tk.StringVar(value=self.api_config.get("api_key", ""))
        self.base_url_var = tk.StringVar(value=self.api_config.get("base_url", ""))
        self.model_var = tk.StringVar(
            value=self.api_config.get("model", "gpt-4o-mini")
        )
        self.temperature_var = tk.DoubleVar(
            value=float(self.api_config.get("temperature", 0.3))
        )

        # Request settings
        self.timeout_var = tk.IntVar(value=int(self.api_config.get("timeout", 60)))
        self.retries_var = tk.IntVar(value=int(self.api_config.get("retries", 3)))
        self.rate_limit_var = tk.IntVar(
            value=int(self.api_config.get("rate_limit_requests", 60))
        )
        self.chunk_size_var = tk.IntVar(
            value=int(self.api_config.get("chunk_size", 50))
        )

        # Translation settings
        self.source_lang_var = tk.StringVar(
            value=self.api_config.get("source_lang", "Japanese")
        )
        self.target_lang_var = tk.StringVar(
            value=self.api_config.get("target_lang", "English")
        )

    def _build_ui(self) -> None:
        """Build the options UI with tabs."""
        # Main container
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create tabs
        self._build_general_tab()
        self._build_api_tab()
        self._build_translation_tab()
        self._build_glossary_api_tab()

        # Buttons frame at bottom
        self._build_buttons(main_frame)

    def _build_general_tab(self) -> None:
        """Build the General settings tab."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text="General")

        # Debug mode
        debug_check = ttk.Checkbutton(
            tab,
            text="Enable debug logging",
            variable=self.debug_var,
        )
        debug_check.pack(anchor=tk.W, pady=5)

        debug_help = ttk.Label(
            tab,
            text="Enables verbose logging for troubleshooting issues.",
            foreground="gray",
        )
        debug_help.pack(anchor=tk.W, padx=(20, 0), pady=(0, 10))

        # Auto-save
        autosave_check = ttk.Checkbutton(
            tab,
            text="Auto-save state on exit",
            variable=self.autosave_var,
        )
        autosave_check.pack(anchor=tk.W, pady=5)

        autosave_help = ttk.Label(
            tab,
            text="Automatically saves window position and recent files on exit.",
            foreground="gray",
        )
        autosave_help.pack(anchor=tk.W, padx=(20, 0), pady=(0, 10))

        # Glossary Update Mode Section
        glossary_frame = ttk.LabelFrame(tab, text="Glossary Update Mode", padding=10)
        glossary_frame.pack(fill=tk.X, pady=(10, 10))

        glossary_info = ttk.Label(
            glossary_frame,
            text="Choose how Pre-Analysis updates glossary when entries exist:\n"
                 "• Add: Only add new entries (preserve all existing data)\n"
                 "• Update: Add new + fill empty fields in existing entries\n"
                 "• Overwrite: Add new + replace ALL fields in existing entries",
            justify="left",
            wraplength=450,
        )
        glossary_info.pack(anchor=tk.W, pady=(0, 10))

        mode_row = ttk.Frame(glossary_frame)
        mode_row.pack(fill=tk.X)

        ttk.Label(mode_row, text="Update Mode:", width=15).pack(side=tk.LEFT)
        mode_combo = ttk.Combobox(
            mode_row,
            textvariable=self.glossary_update_mode_var,
            values=["Add", "Update", "Overwrite", "New"],
            state="readonly",
            width=15,
        )
        mode_combo.pack(side=tk.LEFT, padx=5)

        # Gender Inference Section
        gender_frame = ttk.LabelFrame(tab, text="Gender Inference", padding=10)
        gender_frame.pack(fill=tk.X, pady=(10, 10))

        gender_info = ttk.Label(
            gender_frame,
            text="Confidence threshold for automatic gender assignment.\n"
                 "Higher values require stronger evidence. Range: 0-100%",
            justify="left",
            wraplength=450,
        )
        gender_info.pack(anchor=tk.W, pady=(0, 10))

        confidence_row = ttk.Frame(gender_frame)
        confidence_row.pack(fill=tk.X)

        ttk.Label(confidence_row, text="Threshold (%):", width=15).pack(side=tk.LEFT)
        confidence_spin = ttk.Spinbox(
            confidence_row,
            from_=0,
            to=100,
            textvariable=self.gender_confidence_var,
            width=10,
        )
        confidence_spin.pack(side=tk.LEFT, padx=5)

        ttk.Label(
            confidence_row,
            text="(0 = always assign, 100 = never)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

    def _build_api_tab(self) -> None:
        """Build the API Configuration tab."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text="API")

        # Provider selection
        provider_frame = ttk.LabelFrame(tab, text="API Provider", padding=10)
        provider_frame.pack(fill=tk.X, pady=(0, 10))

        provider_row = ttk.Frame(provider_frame)
        provider_row.pack(fill=tk.X, pady=5)

        ttk.Label(provider_row, text="Provider:", width=15).pack(side=tk.LEFT)
        provider_combo = ttk.Combobox(
            provider_row,
            textvariable=self.provider_var,
            values=list(API_PROVIDERS.keys()),
            state="readonly",
            width=20,
        )
        provider_combo.pack(side=tk.LEFT, padx=5)
        provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        # API Key
        key_row = ttk.Frame(provider_frame)
        key_row.pack(fill=tk.X, pady=5)

        ttk.Label(key_row, text="API Key:", width=15).pack(side=tk.LEFT)
        self.api_key_entry = ttk.Entry(
            key_row, textvariable=self.api_key_var, width=40, show="•"
        )
        self.api_key_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Show/Hide button
        self.show_key_var = tk.BooleanVar(value=False)
        show_btn = ttk.Checkbutton(
            key_row,
            text="Show",
            variable=self.show_key_var,
            command=self._toggle_key_visibility,
        )
        show_btn.pack(side=tk.LEFT, padx=5)

        # Base URL (optional)
        url_row = ttk.Frame(provider_frame)
        url_row.pack(fill=tk.X, pady=5)

        ttk.Label(url_row, text="Base URL:", width=15).pack(side=tk.LEFT)
        self.base_url_entry = ttk.Entry(
            url_row, textvariable=self.base_url_var, width=50
        )
        self.base_url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        url_help = ttk.Label(
            provider_frame,
            text="Leave empty for default. Required for Gemini and custom endpoints.",
            foreground="gray",
        )
        url_help.pack(anchor=tk.W, pady=(0, 5))

        # Model settings
        model_frame = ttk.LabelFrame(tab, text="Model Settings", padding=10)
        model_frame.pack(fill=tk.X, pady=(0, 10))

        model_row = ttk.Frame(model_frame)
        model_row.pack(fill=tk.X, pady=5)

        ttk.Label(model_row, text="Model:", width=15).pack(side=tk.LEFT)
        self.model_combo = ttk.Combobox(
            model_row,
            textvariable=self.model_var,
            width=30,
        )
        self.model_combo.pack(side=tk.LEFT, padx=5)
        self._update_model_list()

        # Temperature
        temp_row = ttk.Frame(model_frame)
        temp_row.pack(fill=tk.X, pady=5)

        ttk.Label(temp_row, text="Temperature:", width=15).pack(side=tk.LEFT)
        temp_scale = ttk.Scale(
            temp_row,
            from_=0.0,
            to=2.0,
            variable=self.temperature_var,
            orient=tk.HORIZONTAL,
            length=200,
        )
        temp_scale.pack(side=tk.LEFT, padx=5)

        self.temp_label = ttk.Label(temp_row, text=f"{self.temperature_var.get():.1f}")
        self.temp_label.pack(side=tk.LEFT, padx=5)
        self.temperature_var.trace_add("write", self._update_temp_label)

        temp_help = ttk.Label(
            model_frame,
            text="Lower = more deterministic, Higher = more creative (0.0-2.0)",
            foreground="gray",
        )
        temp_help.pack(anchor=tk.W, pady=(0, 5))

        # Test connection button
        test_frame = ttk.Frame(tab)
        test_frame.pack(fill=tk.X, pady=10)

        test_btn = ttk.Button(
            test_frame,
            text="Test API Connection",
            command=self._test_connection,
        )
        test_btn.pack(side=tk.LEFT)

        self.test_status_label = ttk.Label(test_frame, text="")
        self.test_status_label.pack(side=tk.LEFT, padx=10)

    def _build_translation_tab(self) -> None:
        """Build the Translation Settings tab."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text="Translation")

        # Language settings
        lang_frame = ttk.LabelFrame(tab, text="Languages", padding=10)
        lang_frame.pack(fill=tk.X, pady=(0, 10))

        # Source language
        source_row = ttk.Frame(lang_frame)
        source_row.pack(fill=tk.X, pady=5)

        ttk.Label(source_row, text="Source Language:", width=18).pack(side=tk.LEFT)
        source_combo = ttk.Combobox(
            source_row,
            textvariable=self.source_lang_var,
            values=SUPPORTED_LANGUAGES,
            width=25,
        )
        source_combo.pack(side=tk.LEFT, padx=5)

        # Target language
        target_row = ttk.Frame(lang_frame)
        target_row.pack(fill=tk.X, pady=5)

        ttk.Label(target_row, text="Target Language:", width=18).pack(side=tk.LEFT)
        target_combo = ttk.Combobox(
            target_row,
            textvariable=self.target_lang_var,
            values=SUPPORTED_LANGUAGES,
            width=25,
        )
        target_combo.pack(side=tk.LEFT, padx=5)

        # Request settings
        request_frame = ttk.LabelFrame(tab, text="Request Settings", padding=10)
        request_frame.pack(fill=tk.X, pady=(0, 10))

        # Chunk size (batch size)
        chunk_row = ttk.Frame(request_frame)
        chunk_row.pack(fill=tk.X, pady=5)

        ttk.Label(chunk_row, text="Lines per Request:", width=18).pack(side=tk.LEFT)
        chunk_spin = ttk.Spinbox(
            chunk_row,
            from_=10,
            to=200,
            textvariable=self.chunk_size_var,
            width=10,
        )
        chunk_spin.pack(side=tk.LEFT, padx=5)

        chunk_help = ttk.Label(
            chunk_row,
            text="(10-200, default: 50)",
            foreground="gray",
        )
        chunk_help.pack(side=tk.LEFT, padx=5)

        # Timeout
        timeout_row = ttk.Frame(request_frame)
        timeout_row.pack(fill=tk.X, pady=5)

        ttk.Label(timeout_row, text="Timeout (seconds):", width=18).pack(side=tk.LEFT)
        timeout_spin = ttk.Spinbox(
            timeout_row,
            from_=10,
            to=600,
            textvariable=self.timeout_var,
            width=10,
        )
        timeout_spin.pack(side=tk.LEFT, padx=5)

        timeout_help = ttk.Label(
            timeout_row,
            text="(10-600, default: 60)",
            foreground="gray",
        )
        timeout_help.pack(side=tk.LEFT, padx=5)

        # Retries
        retries_row = ttk.Frame(request_frame)
        retries_row.pack(fill=tk.X, pady=5)

        ttk.Label(retries_row, text="Max Retries:", width=18).pack(side=tk.LEFT)
        retries_spin = ttk.Spinbox(
            retries_row,
            from_=0,
            to=10,
            textvariable=self.retries_var,
            width=10,
        )
        retries_spin.pack(side=tk.LEFT, padx=5)

        retries_help = ttk.Label(
            retries_row,
            text="(0-10, default: 3)",
            foreground="gray",
        )
        retries_help.pack(side=tk.LEFT, padx=5)

        # Rate limit
        rate_row = ttk.Frame(request_frame)
        rate_row.pack(fill=tk.X, pady=5)

        ttk.Label(rate_row, text="Rate Limit (req/min):", width=18).pack(side=tk.LEFT)
        rate_spin = ttk.Spinbox(
            rate_row,
            from_=1,
            to=1000,
            textvariable=self.rate_limit_var,
            width=10,
        )
        rate_spin.pack(side=tk.LEFT, padx=5)

        rate_help = ttk.Label(
            rate_row,
            text="(1-1000, default: 60)",
            foreground="gray",
        )
        rate_help.pack(side=tk.LEFT, padx=5)

    def _build_glossary_api_tab(self) -> None:
        """Build the Glossary API (API2Glossary) testing tab."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text="Glossary API")

        # Info section
        info_frame = ttk.LabelFrame(tab, text="API2Glossary Configuration", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_label = ttk.Label(
            info_frame,
            text="Test the LLM API connection for speaker name enrichment.\n"
                 "This uses the API2Glossary module to analyze and enrich\n"
                 "speaker names detected during Pre-Analysis.",
            justify="left",
            wraplength=450,
        )
        info_label.pack(anchor=tk.W, pady=(0, 10))

        # Test connection button
        test_frame = ttk.Frame(info_frame)
        test_frame.pack(fill=tk.X)

        self.glossary_test_btn = ttk.Button(
            test_frame,
            text="Test Glossary API Connection",
            command=self._test_glossary_api,
        )
        self.glossary_test_btn.pack(side=tk.LEFT)

        self.glossary_test_status = ttk.Label(test_frame, text="")
        self.glossary_test_status.pack(side=tk.LEFT, padx=10)

        # Results text area
        result_frame = ttk.LabelFrame(tab, text="Test Results", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.glossary_result_text = tk.Text(
            result_frame, height=10, wrap="word", state="disabled"
        )
        self.glossary_result_text.pack(fill=tk.BOTH, expand=True)

    def _test_glossary_api(self) -> None:
        """Test the API2Glossary API connection."""
        self.glossary_test_status.configure(text="Testing...", foreground="gray")
        self.update_idletasks()

        try:
            # Import API2Glossary
            try:
                from .API2Glossary import test_api_connection
            except ImportError:
                try:
                    from CherryAI.functions.API2Glossary import test_api_connection
                except ImportError:
                    self.glossary_test_status.configure(
                        text="Error: API2Glossary not available", foreground="red"
                    )
                    self._update_glossary_result("Failed to import API2Glossary module.")
                    return

            # Run the test
            success, details = test_api_connection()

            if success:
                self.glossary_test_status.configure(text="✓ Success", foreground="green")
                result_text = "API connection test passed.\n\n"
                if "result" in details:
                    result_data = details["result"]
                    romaji = details.get("romaji", result_data.get("romaji", ""))
                    gender = details.get("gender", result_data.get("gender", ""))
                    note = details.get("note", result_data.get("note", ""))
                    result_text += "Test Details:\n"
                    if romaji:
                        result_text += f"  Romaji: {romaji}\n"
                    if gender:
                        result_text += f"  Gender: {gender}\n"
                    if note:
                        result_text += f"  Note: {note}\n"
                result_text += "\nThe API is properly configured."
            else:
                self.glossary_test_status.configure(text="✗ Failed", foreground="red")
                result_text = f"API connection test failed.\n\n"
                result_text += f"Message: {details.get('message', 'Unknown error')}\n"
                if details.get("error"):
                    result_text += f"Error: {details.get('error')}\n"
                result_text += "\nTroubleshooting:\n"
                result_text += "• Verify API_KEY in API2Glossary.py\n"
                result_text += "• Check API_URL is correct\n"
                result_text += "• Ensure MODEL_NAME is valid\n"

            self._update_glossary_result(result_text)

        except Exception as exc:
            self.glossary_test_status.configure(
                text=f"Error: {str(exc)[:30]}", foreground="red"
            )
            self._update_glossary_result(f"Exception during test:\n{exc}")

    def _update_glossary_result(self, text: str) -> None:
        """Update the glossary test result text area."""
        self.glossary_result_text.configure(state="normal")
        self.glossary_result_text.delete("1.0", tk.END)
        self.glossary_result_text.insert("1.0", text)
        self.glossary_result_text.configure(state="disabled")

    def _build_buttons(self, parent: ttk.Frame) -> None:
        """Build the button row at the bottom."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Right side buttons
        save_btn = ttk.Button(button_frame, text="Save", command=self._on_save)
        save_btn.pack(side=tk.RIGHT, padx=5)

        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self._on_cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

        # Left side button
        reset_btn = ttk.Button(
            button_frame, text="Reset to Defaults", command=self._on_reset
        )
        reset_btn.pack(side=tk.LEFT, padx=5)

    def _on_provider_change(self, event: Any = None) -> None:
        """Handle provider selection change."""
        provider = self.provider_var.get()
        if provider in API_PROVIDERS:
            provider_info = API_PROVIDERS[provider]
            # Update base URL to provider default if currently empty or different provider
            current_url = self.base_url_var.get()
            if not current_url or any(
                p["base_url"] == current_url for p in API_PROVIDERS.values()
            ):
                self.base_url_var.set(provider_info["base_url"])
            # Update model list
            self._update_model_list()

    def _update_model_list(self) -> None:
        """Update the model combobox values based on selected provider."""
        provider = self.provider_var.get()
        if provider in API_PROVIDERS:
            models = API_PROVIDERS[provider]["models"]
            self.model_combo["values"] = models
            # If current model not in list, select first available
            if self.model_var.get() not in models:
                self.model_var.set(models[0] if models else "")

    def _toggle_key_visibility(self) -> None:
        """Toggle API key visibility."""
        if self.show_key_var.get():
            self.api_key_entry.configure(show="")
        else:
            self.api_key_entry.configure(show="•")

    def _update_temp_label(self, *args: Any) -> None:
        """Update temperature display label."""
        try:
            self.temp_label.configure(text=f"{self.temperature_var.get():.1f}")
        except tk.TclError:
            pass  # Variable not yet set

    def _test_connection(self) -> None:
        """Test the API connection with current settings."""
        self.test_status_label.configure(text="Testing...", foreground="gray")
        self.update_idletasks()

        try:
            # Import API client
            try:
                from .api_client import APIClient, APIConfig
            except ImportError:
                self.test_status_label.configure(
                    text="Error: API client not available", foreground="red"
                )
                return

            # Create temporary config from current form values
            config = APIConfig(
                provider=self.provider_var.get(),
                api_key=self.api_key_var.get(),
                base_url=self.base_url_var.get() or None,
                model=self.model_var.get(),
                temperature=self.temperature_var.get(),
                timeout=self.timeout_var.get(),
            )

            # Test connection
            client = APIClient()
            # Override with form config
            client.config = config
            client._init_client()

            if client.client is None:
                self.test_status_label.configure(
                    text="Failed: No API key", foreground="red"
                )
                return

            # Try to list models as connectivity test
            models = client.get_models()

            if models:
                self.test_status_label.configure(
                    text=f"✓ Connected ({len(models)} models available)",
                    foreground="green",
                )
            else:
                self.test_status_label.configure(
                    text="✓ Connected (model list unavailable)", foreground="green"
                )

        except Exception as exc:
            self.test_status_label.configure(
                text=f"Failed: {str(exc)[:50]}", foreground="red"
            )

    def get_ui_state(self) -> Dict[str, Any]:
        """Return the current UI state from form controls.

        Returns:
            Dictionary of UI option states.
        """
        return {
            "debug": self.debug_var.get(),
            "autosave": self.autosave_var.get(),
            "glossary_update_mode": self.glossary_update_mode_var.get(),
            "gender_confidence": self.gender_confidence_var.get(),
        }

    def get_api_state(self) -> Dict[str, Any]:
        """Return the current API configuration from form controls.

        Returns:
            Dictionary of API settings.
        """
        return {
            "provider": self.provider_var.get(),
            "api_key": self.api_key_var.get(),
            "base_url": self.base_url_var.get(),
            "model": self.model_var.get(),
            "temperature": self.temperature_var.get(),
            "timeout": self.timeout_var.get(),
            "retries": self.retries_var.get(),
            "rate_limit_requests": self.rate_limit_var.get(),
            "chunk_size": self.chunk_size_var.get(),
            "source_lang": self.source_lang_var.get(),
            "target_lang": self.target_lang_var.get(),
        }

    def _validate_settings(self) -> Tuple[bool, str]:
        """Validate all settings before saving.

        Returns:
            Tuple of (is_valid, error_message).
        """
        # Validate temperature range
        temp = self.temperature_var.get()
        if not 0.0 <= temp <= 2.0:
            return False, "Temperature must be between 0.0 and 2.0"

        # Validate timeout range
        timeout = self.timeout_var.get()
        if not 10 <= timeout <= 600:
            return False, "Timeout must be between 10 and 600 seconds"

        # Validate chunk size
        chunk = self.chunk_size_var.get()
        if not 10 <= chunk <= 200:
            return False, "Lines per request must be between 10 and 200"

        # Validate retries
        retries = self.retries_var.get()
        if not 0 <= retries <= 10:
            return False, "Max retries must be between 0 and 10"

        # Validate rate limit
        rate = self.rate_limit_var.get()
        if not 1 <= rate <= 1000:
            return False, "Rate limit must be between 1 and 1000"

        return True, ""

    def _on_save(self) -> None:
        """Handle save button click."""
        # Validate first
        is_valid, error_msg = self._validate_settings()
        if not is_valid:
            messagebox.showerror("Validation Error", error_msg, parent=self)
            return

        # Save UI state
        ui_state = self.get_ui_state()
        try:
            set_ui_state(ui_state)
        except Exception as exc:
            logging.error(f"Failed to save UI options: {exc}")

        # Save API config
        api_state = self.get_api_state()
        try:
            set_api_config(api_state)
        except Exception as exc:
            logging.error(f"Failed to save API config: {exc}")
            messagebox.showerror(
                "Save Error", f"Failed to save API configuration: {exc}", parent=self
            )
            return

        # Combine for callback
        self.result_state = {"ui": ui_state, "api": api_state}

        if self.on_save:
            try:
                self.on_save(self.result_state)
            except Exception as exc:
                logging.error(f"Callback error in options save: {exc}")

        logging.info("Options saved successfully")
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle cancel button click."""
        self.destroy()

    def _on_reset(self) -> None:
        """Handle reset to defaults button click."""
        if not messagebox.askyesno(
            "Reset to Defaults",
            "Reset all options to their default values?",
            parent=self,
        ):
            return

        # Reset UI settings
        self.debug_var.set(False)
        self.autosave_var.set(True)
        self.glossary_update_mode_var.set("Update")
        self.gender_confidence_var.set(75)

        # Reset API settings from DEFAULT_CONFIG
        defaults = DEFAULT_CONFIG.get("api", {})
        self.provider_var.set(defaults.get("provider", "openai"))
        self.api_key_var.set("")  # Don't reset to stored key
        self.base_url_var.set(defaults.get("base_url", ""))
        self.model_var.set(defaults.get("model", "gpt-4o-mini"))
        self.temperature_var.set(float(defaults.get("temperature", 0.3)))
        self.timeout_var.set(int(defaults.get("timeout", 60)))
        self.retries_var.set(int(defaults.get("retries", 3)))
        self.rate_limit_var.set(int(defaults.get("rate_limit_requests", 60)))
        self.chunk_size_var.set(int(defaults.get("chunk_size", 50)))
        self.source_lang_var.set(defaults.get("source_lang", "Japanese"))
        self.target_lang_var.set(defaults.get("target_lang", "English"))

        # Update model list for provider
        self._update_model_list()

        logging.info("Options reset to defaults")


def open_options_dialog(
    parent: tk.Tk,
    on_save: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> OptionsDialog:
    """Convenience function to open the options dialog.

    Args:
        parent: Parent window.
        on_save: Callback when user saves (receives combined state dict).

    Returns:
        The OptionsDialog instance (allows caller to wait on it).
    """
    dialog = OptionsDialog(parent, on_save=on_save)
    return dialog


def get_api_settings_summary() -> str:
    """Get a brief summary of current API settings for display.

    Returns:
        String summarizing provider, model, and key status.
    """
    config = get_api_config()
    provider = config.get("provider", "openai")
    model = config.get("model", "unknown")
    has_key = bool(config.get("api_key", "").strip())
    key_status = "configured" if has_key else "NOT SET"
    return f"{provider}/{model} (Key: {key_status})"
