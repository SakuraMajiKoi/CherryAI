"""CherryAI GUI v2 Information Step.

Third workflow tab for project metadata and LLM-assisted inference.
Provides fields for project name, summary, style, and character notes.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class InferenceStatus(Enum):
    """Status of LLM inference operation."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MetadataField(Enum):
    """Project metadata field types."""

    PROJECT_NAME = "project_name"
    GAME_TITLE = "game_title"
    SOURCE_LANGUAGE = "source_language"
    TARGET_LANGUAGE = "target_language"
    SUMMARY = "summary"
    STYLE = "style"
    TONE = "tone"
    GENRE = "genre"
    CHARACTER_NOTES = "character_notes"
    CUSTOM = "custom"


class StylePreset(Enum):
    """Translation style presets."""

    LITERAL = "literal"
    NATURAL = "natural"
    CREATIVE = "creative"
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    LITERARY = "literary"
    CUSTOM = "custom"


class TonePreset(Enum):
    """Translation tone presets."""

    NEUTRAL = "neutral"
    SERIOUS = "serious"
    HUMOROUS = "humorous"
    DRAMATIC = "dramatic"
    LIGHTHEARTED = "lighthearted"
    DARK = "dark"
    ROMANTIC = "romantic"
    ACTION = "action"
    CUSTOM = "custom"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class CharacterInfo:
    """Information about a character."""

    name: str
    original_name: str = ""
    gender: str = ""
    role: str = ""
    notes: str = ""
    speaking_style: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "original_name": self.original_name,
            "gender": self.gender,
            "role": self.role,
            "notes": self.notes,
            "speaking_style": self.speaking_style,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterInfo":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            original_name=data.get("original_name", ""),
            gender=data.get("gender", ""),
            role=data.get("role", ""),
            notes=data.get("notes", ""),
            speaking_style=data.get("speaking_style", ""),
        )


@dataclass
class CodePattern:
    """Information about a code pattern for glossary (TASK 18.5).
    
    Represents code patterns detected during Analysis that should be
    preserved during translation (e.g., variables, control codes).
    
    Attributes:
        pattern: The code pattern regex or string.
        category: Category like 'RPG Maker Variable', 'Ruby Code', etc.
        action: How to handle: 'preserve', 'translate', 'remove'.
        example: Example occurrence from the source text.
        notes: User notes about this pattern.
    """

    pattern: str
    category: str = ""
    action: str = "preserve"
    example: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern": self.pattern,
            "category": self.category,
            "action": self.action,
            "example": self.example,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodePattern":
        """Create from dictionary."""
        return cls(
            pattern=data.get("pattern", ""),
            category=data.get("category", ""),
            action=data.get("action", "preserve"),
            example=data.get("example", ""),
            notes=data.get("notes", ""),
        )


@dataclass
class ProjectMetadata:
    """Project metadata for translation context."""

    project_name: str = ""
    game_title: str = ""
    source_language: str = "Japanese"
    target_language: str = "English"
    summary: str = ""
    style: str = ""
    style_preset: StylePreset = StylePreset.NATURAL
    tone: str = ""
    tone_preset: TonePreset = TonePreset.NEUTRAL
    genre: str = ""
    characters: List[CharacterInfo] = field(default_factory=list)
    code_patterns: List[CodePattern] = field(default_factory=list)  # TASK 18.5
    custom_notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "project_name": self.project_name,
            "game_title": self.game_title,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "summary": self.summary,
            "style": self.style,
            "style_preset": self.style_preset.value,
            "tone": self.tone,
            "tone_preset": self.tone_preset.value,
            "genre": self.genre,
            "characters": [c.to_dict() for c in self.characters],
            "code_patterns": [p.to_dict() for p in self.code_patterns],
            "custom_notes": self.custom_notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectMetadata":
        """Create from dictionary."""
        characters = [
            CharacterInfo.from_dict(c) for c in data.get("characters", [])
        ]
        code_patterns = [
            CodePattern.from_dict(p) for p in data.get("code_patterns", [])
        ]
        style_preset = StylePreset.NATURAL
        if "style_preset" in data:
            try:
                style_preset = StylePreset(data["style_preset"])
            except ValueError:
                pass
        tone_preset = TonePreset.NEUTRAL
        if "tone_preset" in data:
            try:
                tone_preset = TonePreset(data["tone_preset"])
            except ValueError:
                pass
        return cls(
            project_name=data.get("project_name", ""),
            game_title=data.get("game_title", ""),
            source_language=data.get("source_language", "Japanese"),
            target_language=data.get("target_language", "English"),
            summary=data.get("summary", ""),
            style=data.get("style", ""),
            style_preset=style_preset,
            tone=data.get("tone", ""),
            tone_preset=tone_preset,
            genre=data.get("genre", ""),
            characters=characters,
            code_patterns=code_patterns,
            custom_notes=data.get("custom_notes", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class InferenceOptions:
    """Options for LLM inference."""

    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    infer_summary: bool = True
    infer_tone: bool = True
    infer_characters: bool = True
    sample_lines: int = 50


@dataclass
class InferenceResult:
    """Result from LLM inference."""

    summary: str = ""
    tone: str = ""
    style: str = ""
    genre: str = ""
    characters: List[CharacterInfo] = field(default_factory=list)
    raw_response: str = ""
    status: InferenceStatus = InferenceStatus.IDLE
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "summary": self.summary,
            "tone": self.tone,
            "style": self.style,
            "genre": self.genre,
            "characters": [c.to_dict() for c in self.characters],
            "raw_response": self.raw_response,
            "status": self.status.value,
            "error": self.error,
        }


# ============================================================================
# Constants
# ============================================================================


STYLE_DESCRIPTIONS: Dict[StylePreset, str] = {
    StylePreset.LITERAL: "Word-for-word translation preserving original structure",
    StylePreset.NATURAL: "Fluent translation adapted to target language conventions",
    StylePreset.CREATIVE: "Liberal adaptation with creative interpretation",
    StylePreset.FORMAL: "Professional, formal language register",
    StylePreset.CASUAL: "Informal, conversational language",
    StylePreset.TECHNICAL: "Precise technical terminology",
    StylePreset.LITERARY: "Literary prose style with artistic flourishes",
    StylePreset.CUSTOM: "User-defined custom style",
}


TONE_DESCRIPTIONS: Dict[TonePreset, str] = {
    TonePreset.NEUTRAL: "Balanced, neutral tone without strong emotion",
    TonePreset.SERIOUS: "Grave, solemn atmosphere",
    TonePreset.HUMOROUS: "Light-hearted, comedic elements",
    TonePreset.DRAMATIC: "Intense, theatrical presentation",
    TonePreset.LIGHTHEARTED: "Cheerful, upbeat mood",
    TonePreset.DARK: "Grim, ominous atmosphere",
    TonePreset.ROMANTIC: "Warm, emotional romantic context",
    TonePreset.ACTION: "Fast-paced, energetic action sequences",
    TonePreset.CUSTOM: "User-defined custom tone",
}


COMMON_GENRES: List[str] = [
    "Visual Novel",
    "RPG",
    "Action",
    "Adventure",
    "Simulation",
    "Puzzle",
    "Horror",
    "Romance",
    "Fantasy",
    "Sci-Fi",
    "Historical",
    "Slice of Life",
    "Mystery",
    "Comedy",
    "Drama",
]


SOURCE_LANGUAGES: List[str] = [
    "Japanese",
    "Chinese (Simplified)",
    "Chinese (Traditional)",
    "Korean",
    "English",
    "Other",
]


TARGET_LANGUAGES: List[str] = [
    "English",
    "Japanese",
    "Chinese (Simplified)",
    "Chinese (Traditional)",
    "Korean",
    "Spanish",
    "French",
    "German",
    "Portuguese",
    "Russian",
    "Other",
]


# ============================================================================
# InformationStep Class
# ============================================================================


class InformationStep(BaseStep):
    """Information step for project metadata.

    Features:
    - Project name and game title fields
    - Source/target language selection
    - Summary text area (manual or LLM-inferred)
    - Style and tone presets with custom overrides
    - Character notes with add/edit/remove
    - LLM inference toggle for automatic metadata
    - Editable JSON view of all metadata
    - Persist to manifest
    """

    step_id = 3  # Moved from position 2
    step_name = "Information"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize Information step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables before super().__init__()
        self._metadata = ProjectMetadata()
        self._inference_options = InferenceOptions()
        self._inference_result = InferenceResult()
        self._is_inferring = False
        self._json_mode = False

        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the step UI."""
        self._build_header()
        self._build_content()

    def _build_header(self) -> None:
        """Build the header section."""
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # Title
        ttk.Label(
            header,
            text="Project Information",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        # Toggle JSON view
        self._json_btn = ttk.Button(
            header,
            text="JSON View",
            command=self._toggle_json_view,
        )
        self._json_btn.pack(side="right", padx=(5, 0))

        # Save button
        ttk.Button(
            header,
            text="Save",
            command=self._save_metadata,
        ).pack(side="right")

    def _build_content(self) -> None:
        """Build the main content area with 2-column layout.
        
        Layout:
        - Left column: Project Details, Languages, Summary, Style & Tone, Characters
        - Right column: Additional Notes, LLM Inference Options, JSON View
        """
        # Main container with scrolling
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._scrollable_frame = ttk.Frame(canvas)

        self._scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=self._scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )

        # Create 2-column layout container
        columns_frame = ttk.Frame(self._scrollable_frame)
        columns_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Configure grid columns with equal weight for responsive resizing
        columns_frame.columnconfigure(0, weight=1, minsize=350)
        columns_frame.columnconfigure(1, weight=1, minsize=300)

        # Left column: Primary content
        self._left_column = ttk.Frame(columns_frame)
        self._left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # Right column: Secondary content
        self._right_column = ttk.Frame(columns_frame)
        self._right_column.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # Build sections in their respective columns
        self._build_project_section()
        self._build_language_section()
        self._build_summary_section()
        self._build_style_section()
        self._build_character_section()
        self._build_glossary_settings_section()  # TASK 19 Phase 4
        self._build_code_glossary_section()  # TASK 18.5
        self._build_notes_section()
        self._build_inference_section()  # Variables only, UI removed (deprecated)
        self._build_json_section()

    def _build_project_section(self) -> None:
        """Build project name and title section."""
        frame = ttk.LabelFrame(self._left_column, text="Project Details")
        frame.pack(fill="x", padx=5, pady=5)

        # Project Name
        row1 = ttk.Frame(frame)
        row1.pack(fill="x", padx=10, pady=5)

        ttk.Label(row1, text="Project Name:", width=15, anchor="e").pack(
            side="left", padx=(0, 5)
        )
        self._project_name_var = tk.StringVar()
        self._project_name_entry = ttk.Entry(row1, textvariable=self._project_name_var)
        self._project_name_entry.pack(side="left", fill="x", expand=True)

        # Game Title
        row2 = ttk.Frame(frame)
        row2.pack(fill="x", padx=10, pady=5)

        ttk.Label(row2, text="Game Title:", width=15, anchor="e").pack(
            side="left", padx=(0, 5)
        )
        self._game_title_var = tk.StringVar()
        self._game_title_entry = ttk.Entry(row2, textvariable=self._game_title_var)
        self._game_title_entry.pack(side="left", fill="x", expand=True)

        # Genre
        row3 = ttk.Frame(frame)
        row3.pack(fill="x", padx=10, pady=5)

        ttk.Label(row3, text="Genre:", width=15, anchor="e").pack(
            side="left", padx=(0, 5)
        )
        self._genre_var = tk.StringVar()
        self._genre_entry = ttk.Entry(row3, textvariable=self._genre_var)
        self._genre_entry.pack(side="left", fill="x", expand=True)
        
        # Button to open multi-select dialog
        self._genre_btn = ttk.Button(
            row3,
            text="...",
            width=3,
            command=self._open_genre_dialog,
        )
        self._genre_btn.pack(side="left", padx=(5, 0))

    def _build_language_section(self) -> None:
        """Build language selection section."""
        frame = ttk.LabelFrame(self._left_column, text="Languages")
        frame.pack(fill="x", padx=5, pady=5)

        row = ttk.Frame(frame)
        row.pack(fill="x", padx=10, pady=5)

        # Source Language
        ttk.Label(row, text="Source:").pack(side="left", padx=(0, 5))
        self._source_lang_var = tk.StringVar(value="Japanese")
        self._source_lang_combo = ttk.Combobox(
            row,
            textvariable=self._source_lang_var,
            values=SOURCE_LANGUAGES,
            state="readonly",
            width=20,
        )
        self._source_lang_combo.pack(side="left", padx=(0, 20))

        # Arrow
        ttk.Label(row, text="→").pack(side="left", padx=10)

        # Target Language
        ttk.Label(row, text="Target:").pack(side="left", padx=(0, 5))
        self._target_lang_var = tk.StringVar(value="English")
        self._target_lang_combo = ttk.Combobox(
            row,
            textvariable=self._target_lang_var,
            values=TARGET_LANGUAGES,
            state="readonly",
            width=20,
        )
        self._target_lang_combo.pack(side="left")

    def _build_summary_section(self) -> None:
        """Build summary/description section."""
        frame = ttk.LabelFrame(self._left_column, text="Summary / Description")
        frame.pack(fill="x", padx=5, pady=5)

        # Summary text area
        self._summary_text = scrolledtext.ScrolledText(
            frame,
            height=5,
            wrap="word",
            font=("Consolas", 10),
        )
        self._summary_text.pack(fill="x", padx=10, pady=5)

        # Hint
        ttk.Label(
            frame,
            text="Provide a brief summary of the game/story for translation context.",
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(anchor="w", padx=10, pady=(0, 5))

    def _build_style_section(self) -> None:
        """Build style and tone section."""
        frame = ttk.LabelFrame(self._left_column, text="Translation Style & Tone")
        frame.pack(fill="x", padx=5, pady=5)

        # Style row
        style_row = ttk.Frame(frame)
        style_row.pack(fill="x", padx=10, pady=5)

        ttk.Label(style_row, text="Style Preset:").pack(side="left", padx=(0, 5))
        self._style_preset_var = tk.StringVar(value=StylePreset.NATURAL.value)
        self._style_preset_combo = ttk.Combobox(
            style_row,
            textvariable=self._style_preset_var,
            values=[s.value for s in StylePreset],
            state="readonly",
            width=15,
        )
        self._style_preset_combo.pack(side="left", padx=(0, 20))
        self._style_preset_combo.bind("<<ComboboxSelected>>", self._on_style_changed)

        # Style description
        self._style_desc_label = ttk.Label(
            style_row,
            text=STYLE_DESCRIPTIONS[StylePreset.NATURAL],
            font=("Segoe UI", 8),
            foreground="gray",
        )
        self._style_desc_label.pack(side="left")

        # Custom style entry
        style_custom_row = ttk.Frame(frame)
        style_custom_row.pack(fill="x", padx=10, pady=5)

        ttk.Label(style_custom_row, text="Custom Style:").pack(side="left", padx=(0, 5))
        self._style_var = tk.StringVar()
        self._style_entry = ttk.Entry(style_custom_row, textvariable=self._style_var)
        self._style_entry.pack(side="left", fill="x", expand=True)

        # Separator
        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=10, pady=5)

        # Tone row
        tone_row = ttk.Frame(frame)
        tone_row.pack(fill="x", padx=10, pady=5)

        ttk.Label(tone_row, text="Tone Preset:").pack(side="left", padx=(0, 5))
        self._tone_preset_var = tk.StringVar(value=TonePreset.NEUTRAL.value)
        self._tone_preset_combo = ttk.Combobox(
            tone_row,
            textvariable=self._tone_preset_var,
            values=[t.value for t in TonePreset],
            state="readonly",
            width=15,
        )
        self._tone_preset_combo.pack(side="left", padx=(0, 20))
        self._tone_preset_combo.bind("<<ComboboxSelected>>", self._on_tone_changed)

        # Tone description
        self._tone_desc_label = ttk.Label(
            tone_row,
            text=TONE_DESCRIPTIONS[TonePreset.NEUTRAL],
            font=("Segoe UI", 8),
            foreground="gray",
        )
        self._tone_desc_label.pack(side="left")

        # Custom tone entry
        tone_custom_row = ttk.Frame(frame)
        tone_custom_row.pack(fill="x", padx=10, pady=5)

        ttk.Label(tone_custom_row, text="Custom Tone:").pack(side="left", padx=(0, 5))
        self._tone_var = tk.StringVar()
        self._tone_entry = ttk.Entry(tone_custom_row, textvariable=self._tone_var)
        self._tone_entry.pack(side="left", fill="x", expand=True)

    def _build_character_section(self) -> None:
        """Build character notes section."""
        frame = ttk.LabelFrame(self._left_column, text="Character Notes")
        frame.pack(fill="x", padx=5, pady=5)

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=10, pady=5)

        ttk.Button(
            toolbar,
            text="+ Add Character",
            command=self._add_character,
        ).pack(side="left")

        ttk.Button(
            toolbar,
            text="Edit",
            command=self._edit_character,
        ).pack(side="left", padx=5)

        ttk.Button(
            toolbar,
            text="Remove",
            command=self._remove_character,
        ).pack(side="left")

        # Infer Gender button (Task: Link Gender Inference to Character Notes)
        ttk.Button(
            toolbar,
            text="🔍 Infer Gender",
            command=self._infer_character_genders,
        ).pack(side="left", padx=5)

        # Import from Analysis button (Task 18.4)
        ttk.Button(
            toolbar,
            text="↓ Import from Analysis",
            command=self._on_import_from_analysis,
        ).pack(side="right")

        # Character list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="x", padx=10, pady=5)

        # Column order: Original first, then Translation (formerly Name)
        columns = ("original", "translation", "gender", "role")
        self._char_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=5,
        )
        self._char_tree.heading("original", text="Original")
        self._char_tree.heading("translation", text="Translation")
        self._char_tree.heading("gender", text="Gender")
        self._char_tree.heading("role", text="Role")

        self._char_tree.column("original", width=120)
        self._char_tree.column("translation", width=120)
        self._char_tree.column("gender", width=80)
        self._char_tree.column("role", width=150)

        char_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self._char_tree.yview,
        )
        self._char_tree.configure(yscrollcommand=char_scroll.set)

        self._char_tree.pack(side="left", fill="x", expand=True)
        char_scroll.pack(side="right", fill="y")

        # Bind double-click for inline editing
        self._char_tree.bind("<Double-1>", self._on_char_double_click)
        # Bind Delete key for row removal
        self._char_tree.bind("<Delete>", lambda e: self._remove_character())

    def _build_glossary_settings_section(self) -> None:
        """Build Glossary Settings section (TASK 19 Phase 4).
        
        Controls glossary source:
        - Use Global Glossary checkbox (user/glossary.csv)
        - Copy from Global button (copies global entries to project)
        """
        frame = ttk.LabelFrame(self._right_column, text="Glossary Settings")
        frame.pack(fill="x", padx=5, pady=5)
        
        # Use Global Glossary checkbox
        self._use_global_glossary_var = tk.BooleanVar(value=True)
        use_global_cb = ttk.Checkbutton(
            frame,
            text="Use Global Glossary (user/glossary.csv)",
            variable=self._use_global_glossary_var,
            command=self._on_use_global_glossary_changed,
        )
        use_global_cb.pack(anchor="w", padx=10, pady=5)
        
        # Info text
        self._glossary_info_label = ttk.Label(
            frame,
            text="Global glossary entries will be applied during translation.",
            font=("Segoe UI", 8),
            foreground="gray",
        )
        self._glossary_info_label.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Button row
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", padx=10, pady=(0, 5))
        
        # Copy from Global button
        ttk.Button(
            btn_frame,
            text="↓ Copy from Global",
            command=self._on_copy_from_global_glossary,
        ).pack(side="left")
        
        # Project glossary count
        self._project_glossary_count_var = tk.StringVar(value="Project entries: 0")
        ttk.Label(
            btn_frame,
            textvariable=self._project_glossary_count_var,
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(side="right")

    def _build_code_glossary_section(self) -> None:
        """Build Code Glossary section in right column (TASK 18.5).
        
        Displays code patterns detected during Analysis that should be
        preserved during translation (e.g., variables, control codes).
        """
        frame = ttk.LabelFrame(self._right_column, text="Code Glossary")
        frame.pack(fill="x", padx=5, pady=5)

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=10, pady=5)

        ttk.Button(
            toolbar,
            text="+ Add Pattern",
            command=self._add_code_pattern,
        ).pack(side="left")

        ttk.Button(
            toolbar,
            text="Edit",
            command=self._edit_code_pattern,
        ).pack(side="left", padx=5)

        ttk.Button(
            toolbar,
            text="Remove",
            command=self._remove_code_pattern,
        ).pack(side="left")

        # Import from Analysis button
        ttk.Button(
            toolbar,
            text="↓ Import from Analysis",
            command=self._on_import_code_patterns,
        ).pack(side="right")

        # Code pattern list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="x", padx=10, pady=5)

        columns = ("pattern", "category", "action")
        self._code_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=4,
        )
        self._code_tree.heading("pattern", text="Pattern")
        self._code_tree.heading("category", text="Category")
        self._code_tree.heading("action", text="Action")

        self._code_tree.column("pattern", width=150)
        self._code_tree.column("category", width=100)
        self._code_tree.column("action", width=70)

        code_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self._code_tree.yview,
        )
        self._code_tree.configure(yscrollcommand=code_scroll.set)

        self._code_tree.pack(side="left", fill="x", expand=True)
        code_scroll.pack(side="right", fill="y")

        # Bind double-click for inline editing
        self._code_tree.bind("<Double-1>", self._on_code_double_click)
        # Bind Delete key for row removal
        self._code_tree.bind("<Delete>", lambda e: self._remove_code_pattern())

        # Hint
        ttk.Label(
            frame,
            text="Code patterns to preserve during translation.",
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(anchor="w", padx=10, pady=(0, 5))

    def _build_notes_section(self) -> None:
        """Build custom notes section (right column)."""
        frame = ttk.LabelFrame(self._right_column, text="Additional Notes")
        frame.pack(fill="x", padx=5, pady=5)

        self._notes_text = scrolledtext.ScrolledText(
            frame,
            height=4,
            wrap="word",
            font=("Consolas", 10),
        )
        self._notes_text.pack(fill="x", padx=10, pady=5)

        ttk.Label(
            frame,
            text="Any additional context or notes for the translator.",
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(anchor="w", padx=10, pady=(0, 5))

    def _build_inference_section(self) -> None:
        """Initialize LLM inference variables (UI section removed - deprecated).
        
        This method only initializes instance variables for backward compatibility
        with session persistence. The UI section has been removed for this release.
        """
        # Initialize variables for backward compatibility with session persistence
        self._infer_enabled_var = tk.BooleanVar(value=False)
        self._infer_summary_var = tk.BooleanVar(value=True)
        self._infer_tone_var = tk.BooleanVar(value=True)
        self._infer_chars_var = tk.BooleanVar(value=True)
        self._sample_lines_var = tk.IntVar(value=50)
        self._infer_status_var = tk.StringVar(value="")
        # Note: UI has been removed, variables kept for serialization

    def _build_json_section(self) -> None:
        """Build JSON view section (right column, initially hidden)."""
        self._json_frame = ttk.LabelFrame(
            self._right_column,
            text="JSON View (Editable)",
        )
        # Initially hidden, will be shown when toggled

        self._json_text = scrolledtext.ScrolledText(
            self._json_frame,
            height=20,
            wrap="none",
            font=("Consolas", 10),
        )
        self._json_text.pack(fill="both", expand=True, padx=10, pady=5)

        # Apply JSON button
        ttk.Button(
            self._json_frame,
            text="Apply JSON Changes",
            command=self._apply_json,
        ).pack(pady=5)

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def _on_style_changed(self, event: Optional[tk.Event] = None) -> None:
        """Handle style preset change."""
        try:
            preset = StylePreset(self._style_preset_var.get())
            self._style_desc_label.config(text=STYLE_DESCRIPTIONS[preset])
        except (ValueError, KeyError):
            pass

    def _on_tone_changed(self, event: Optional[tk.Event] = None) -> None:
        """Handle tone preset change."""
        try:
            preset = TonePreset(self._tone_preset_var.get())
            self._tone_desc_label.config(text=TONE_DESCRIPTIONS[preset])
        except (ValueError, KeyError):
            pass

    def _toggle_json_view(self) -> None:
        """Toggle JSON view visibility."""
        self._json_mode = not self._json_mode
        if self._json_mode:
            self._update_json_view()
            self._json_frame.pack(fill="x", padx=5, pady=5)
            self._json_btn.config(text="Form View")
        else:
            self._json_frame.pack_forget()
            self._json_btn.config(text="JSON View")

    def _update_json_view(self) -> None:
        """Update JSON text with current metadata."""
        self._collect_metadata()
        json_str = json.dumps(self._metadata.to_dict(), indent=2, ensure_ascii=False)
        self._json_text.delete("1.0", "end")
        self._json_text.insert("1.0", json_str)

    def _apply_json(self) -> None:
        """Apply JSON changes to form."""
        try:
            json_str = self._json_text.get("1.0", "end-1c")
            data = json.loads(json_str)
            self._metadata = ProjectMetadata.from_dict(data)
            self._populate_form()
            messagebox.showinfo("Success", "JSON changes applied successfully.")
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply JSON: {e}")

    # ========================================================================
    # Character Management
    # ========================================================================

    def _add_character(self) -> None:
        """Add a new character."""
        dialog = CharacterDialog(self, "Add Character")
        if dialog.result:
            self._metadata.characters.append(dialog.result)
            self._refresh_character_list()

    def _edit_character(self) -> None:
        """Edit selected character."""
        selection = self._char_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a character to edit.")
            return

        idx = self._char_tree.index(selection[0])
        if idx < len(self._metadata.characters):
            char = self._metadata.characters[idx]
            dialog = CharacterDialog(self, "Edit Character", char)
            if dialog.result:
                self._metadata.characters[idx] = dialog.result
                self._refresh_character_list()

    def _remove_character(self) -> None:
        """Remove selected character."""
        selection = self._char_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a character to remove.")
            return

        if messagebox.askyesno("Confirm", "Remove selected character?"):
            idx = self._char_tree.index(selection[0])
            if idx < len(self._metadata.characters):
                del self._metadata.characters[idx]
                self._refresh_character_list()

    def _infer_character_genders(self) -> None:
        """Infer gender for characters based on their original names.
        
        Uses name-based heuristics from the gender inference module to
        populate the gender field for characters that don't have one set.
        Only updates if inference confidence is >= 50%.
        """
        if not self._metadata.characters:
            messagebox.showinfo(
                "No Characters",
                "No characters to infer genders for. Add characters first.",
            )
            return

        # Try to import gender inference function
        try:
            from CherryAI.functions.glossaries.name_glossary_functions import (
                infer_gender_comprehensive,
            )
        except ImportError:
            messagebox.showerror(
                "Not Available",
                "Gender inference module not available.",
            )
            return

        # Infer genders for characters without one set
        updated_count = 0
        for char in self._metadata.characters:
            # Skip if gender already set
            if char.gender and char.gender != "Unknown":
                continue

            # Use original_name for inference
            name_to_check = char.original_name or char.name
            if not name_to_check:
                continue

            try:
                # Use name-based heuristics
                inferred, confidence, _, _, _ = infer_gender_comprehensive(
                    name=name_to_check,
                    pronouns={},
                    honorifics={},
                    full_text="",
                    confidence_threshold=0.5,
                )
                if inferred and inferred != "Unknown" and confidence >= 50:
                    char.gender = inferred
                    updated_count += 1
            except Exception as e:
                logger.debug(f"Gender inference failed for {name_to_check}: {e}")

        # Refresh display
        self._refresh_character_list()

        if updated_count > 0:
            messagebox.showinfo(
                "Gender Inference Complete",
                f"Inferred gender for {updated_count} character(s).",
            )
        else:
            messagebox.showinfo(
                "No Updates",
                "Could not infer gender for any characters.\n"
                "Characters either already have genders set or names are ambiguous.",
            )

    def _on_char_double_click(self, event: tk.Event) -> None:
        """Handle double-click on character tree for inline editing."""
        region = self._char_tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._char_tree.identify_column(event.x)
        item = self._char_tree.identify_row(event.y)
        if not item:
            return

        # Get column index (1-based from identify_column)
        col_idx = int(column.replace("#", "")) - 1
        # Column order: original, translation, gender, role
        columns = ("original", "translation", "gender", "role")
        # Map column names to dataclass fields
        field_map = {"original": "original_name", "translation": "name",
                     "gender": "gender", "role": "role"}
        if col_idx < 0 or col_idx >= len(columns):
            return

        col_key = columns[col_idx]
        field_key = field_map[col_key]
        idx = self._char_tree.index(item)
        if idx >= len(self._metadata.characters):
            return

        char = self._metadata.characters[idx]
        self._start_char_inline_edit(item, col_key, field_key, col_idx, char)

    def _start_char_inline_edit(
        self, item: str, col_key: str, field_key: str, col_idx: int, char: "CharacterInfo"
    ) -> None:
        """Start inline editing of a character cell.
        
        Args:
            item: Treeview item ID.
            col_key: Column key (original, translation, gender, role).
            field_key: Dataclass field key (original_name, name, gender, role).
            col_idx: Column index.
            char: Character being edited.
        """
        # Column order: original, translation, gender, role
        columns = ("original", "translation", "gender", "role")
        try:
            bbox = self._char_tree.bbox(item, columns[col_idx])
            if not bbox:
                return
        except tk.TclError:
            return

        x, y, width, height = bbox
        current_value = getattr(char, field_key, "")

        # Special handling for gender and role (dropdowns)
        if col_key == "gender":
            self._show_char_dropdown(item, field_key, char, x, y, width, height,
                                     ["", "Male", "Female", "Other", "Unknown"])
        elif col_key == "role":
            self._show_char_dropdown(item, field_key, char, x, y, width, height,
                                     ["", "Main Character", "Major Character", "Minor Character",
                                      "Side Character", "Villain", "Love Interest", "Mentor",
                                      "Narrator", "Speaker"])
        else:
            # Text entry for original and translation
            entry = ttk.Entry(self._char_tree)
            entry.insert(0, str(current_value))
            entry.select_range(0, "end")
            entry.place(x=x, y=y, width=width, height=height)
            entry.focus_set()

            def on_confirm(event=None):
                new_value = entry.get()
                entry.destroy()
                if new_value != str(current_value):
                    setattr(char, field_key, new_value)
                    self._refresh_character_list()

            def on_cancel(event=None):
                entry.destroy()

            entry.bind("<Return>", on_confirm)
            entry.bind("<Tab>", on_confirm)
            entry.bind("<Escape>", on_cancel)
            entry.bind("<FocusOut>", on_confirm)

    def _show_char_dropdown(
        self,
        item: str,
        col_key: str,
        char: "CharacterInfo",
        x: int,
        y: int,
        width: int,
        height: int,
        options: list,
    ) -> None:
        """Show a dropdown for selecting gender or role.
        
        Args:
            item: Treeview item ID.
            col_key: Column key.
            char: Character being edited.
            x, y, width, height: Cell coordinates.
            options: List of dropdown options.
        """
        current_value = getattr(char, col_key, "")
        combo = ttk.Combobox(self._char_tree, values=options, state="readonly")
        combo.set(current_value)
        combo.place(x=x, y=y, width=width, height=height)
        combo.focus_set()

        def on_select(event=None):
            new_value = combo.get()
            combo.destroy()
            if new_value != current_value:
                setattr(char, col_key, new_value)
                self._refresh_character_list()

        def on_cancel(event=None):
            combo.destroy()

        combo.bind("<<ComboboxSelected>>", on_select)
        combo.bind("<Return>", on_select)
        combo.bind("<Escape>", on_cancel)
        combo.bind("<FocusOut>", on_select)

    def _open_genre_dialog(self) -> None:
        """Open a dialog for multi-selecting genres."""
        dialog = tk.Toplevel(self)
        dialog.title("Select Genres")
        dialog.geometry("300x450")
        dialog.transient(self)
        dialog.grab_set()
        
        # Current genres (comma-separated)
        current_genres = [g.strip() for g in self._genre_var.get().split(",") if g.strip()]
        
        # Create checkbuttons for each genre
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)
        
        ttk.Label(frame, text="Select one or more genres:").pack(anchor="w", pady=(0, 10))
        
        # Scrollable frame for genres
        canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Genre checkbuttons with BooleanVars
        genre_vars: Dict[str, tk.BooleanVar] = {}
        for genre in COMMON_GENRES:
            var = tk.BooleanVar(value=genre in current_genres)
            genre_vars[genre] = var
            cb = ttk.Checkbutton(scrollable_frame, text=genre, variable=var)
            cb.pack(anchor="w", padx=5, pady=2)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Custom genre entry
        custom_frame = ttk.Frame(dialog, padding=10)
        custom_frame.pack(fill="x")
        
        ttk.Label(custom_frame, text="Custom Genre:").pack(side="left")
        custom_var = tk.StringVar()
        custom_entry = ttk.Entry(custom_frame, textvariable=custom_var)
        custom_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        # Buttons
        btn_frame = ttk.Frame(dialog, padding=10)
        btn_frame.pack(fill="x")
        
        def on_ok():
            selected = [g for g, v in genre_vars.items() if v.get()]
            # Add custom genre if specified
            custom = custom_var.get().strip()
            if custom and custom not in selected:
                selected.append(custom)
            self._genre_var.set(", ".join(selected))
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="right")
        
        # Center dialog on parent
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def _refresh_character_list(self) -> None:
        """Refresh character treeview."""
        for item in self._char_tree.get_children():
            self._char_tree.delete(item)

        for char in self._metadata.characters:
            # Column order: original, translation (name field), gender, role
            self._char_tree.insert(
                "",
                "end",
                values=(char.original_name, char.name, char.gender, char.role),
            )

    def _on_import_from_analysis(self) -> None:
        """Handle Import from Analysis button click.
        
        Imports speakers detected in Analysis step as characters.
        Unlike auto-import, this forces import even if characters exist.
        """
        try:
            # Get analysis results from session (stored under 'analysis_results')
            analysis_step_data = self.session.get_step(1).data
            analysis_results = analysis_step_data.get("analysis_results", {})
            speakers = analysis_results.get("speakers", {})
            
            if not speakers:
                messagebox.showinfo(
                    "No Speakers",
                    "No speakers were detected in Analysis.\n\n"
                    "Run Analysis first to detect speakers.",
                )
                return
            
            # Confirm import
            existing_count = len(self._metadata.characters)
            speaker_count = len(speakers)
            
            if existing_count > 0:
                response = messagebox.askyesno(
                    "Import Speakers",
                    f"Found {speaker_count} speakers in Analysis.\n\n"
                    f"You already have {existing_count} characters.\n\n"
                    "Add new speakers to existing characters?",
                )
                if not response:
                    return
            
            # Import speakers
            imported_count = 0
            existing_originals = {c.original_name for c in self._metadata.characters}
            
            # Sort by count, take top 20
            sorted_speakers = sorted(speakers.items(), key=lambda x: x[1], reverse=True)[:20]
            
            for speaker_name, count in sorted_speakers:
                if speaker_name in existing_originals:
                    continue
                    
                char = CharacterInfo(
                    name="",  # Translation left empty by default
                    original_name=speaker_name,
                    role="Speaker",
                    notes=f"Imported from Analysis ({count} occurrences)",
                )
                self._metadata.characters.append(char)
                existing_originals.add(speaker_name)
                imported_count += 1
            
            self._refresh_character_list()
            
            if imported_count > 0:
                messagebox.showinfo(
                    "Import Complete",
                    f"Imported {imported_count} new characters from Analysis.",
                )
            else:
                messagebox.showinfo(
                    "No New Characters",
                    "All detected speakers already exist in the character list.",
                )
                
        except (AttributeError, KeyError, IndexError):
            messagebox.showwarning(
                "Analysis Required",
                "Run Analysis first to detect speakers.",
            )
        except Exception as e:
            logger.error(f"Failed to import from analysis: {e}")
            messagebox.showerror("Import Error", f"Failed to import: {e}")

    # ========================================================================
    # Code Glossary Management (TASK 18.5)
    # ========================================================================

    def _add_code_pattern(self) -> None:
        """Add a new code pattern."""
        dialog = CodePatternDialog(self, "Add Code Pattern")
        if dialog.result:
            self._metadata.code_patterns.append(dialog.result)
            self._refresh_code_pattern_list()

    def _edit_code_pattern(self) -> None:
        """Edit selected code pattern."""
        selection = self._code_tree.selection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a pattern to edit."
            )
            return

        idx = self._code_tree.index(selection[0])
        if idx < len(self._metadata.code_patterns):
            pattern = self._metadata.code_patterns[idx]
            dialog = CodePatternDialog(self, "Edit Code Pattern", pattern)
            if dialog.result:
                self._metadata.code_patterns[idx] = dialog.result
                self._refresh_code_pattern_list()

    def _remove_code_pattern(self) -> None:
        """Remove selected code pattern."""
        selection = self._code_tree.selection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a pattern to remove."
            )
            return

        if messagebox.askyesno("Confirm", "Remove selected pattern?"):
            idx = self._code_tree.index(selection[0])
            if idx < len(self._metadata.code_patterns):
                del self._metadata.code_patterns[idx]
                self._refresh_code_pattern_list()

    def _on_code_double_click(self, event: tk.Event) -> None:
        """Handle double-click on code pattern tree for inline editing."""
        region = self._code_tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._code_tree.identify_column(event.x)
        item = self._code_tree.identify_row(event.y)
        if not item:
            return

        # Get column index (1-based from identify_column)
        col_idx = int(column.replace("#", "")) - 1
        columns = ("pattern", "category", "action")
        if col_idx < 0 or col_idx >= len(columns):
            return

        col_key = columns[col_idx]
        idx = self._code_tree.index(item)
        if idx >= len(self._metadata.code_patterns):
            return

        pattern = self._metadata.code_patterns[idx]
        self._start_code_inline_edit(item, col_key, col_idx, pattern)

    def _start_code_inline_edit(
        self, item: str, col_key: str, col_idx: int, pattern: "CodePattern"
    ) -> None:
        """Start inline editing of a code pattern cell.
        
        Args:
            item: Treeview item ID.
            col_key: Column key (pattern, category, action).
            col_idx: Column index.
            pattern: Code pattern being edited.
        """
        columns = ("pattern", "category", "action")
        try:
            bbox = self._code_tree.bbox(item, columns[col_idx])
            if not bbox:
                return
        except tk.TclError:
            return

        x, y, width, height = bbox
        current_value = getattr(pattern, col_key, "")

        # Special handling for category and action (dropdowns)
        if col_key == "category":
            self._show_code_dropdown(item, col_key, pattern, x, y, width, height,
                                     ["code", "variable", "control", "tag", "markup", "other"])
        elif col_key == "action":
            self._show_code_dropdown(item, col_key, pattern, x, y, width, height,
                                     ["preserve", "translate", "remove", "replace"])
        else:
            # Text entry for pattern
            entry = ttk.Entry(self._code_tree)
            entry.insert(0, str(current_value))
            entry.select_range(0, "end")
            entry.place(x=x, y=y, width=width, height=height)
            entry.focus_set()

            def on_confirm(event=None):
                new_value = entry.get()
                entry.destroy()
                if new_value != str(current_value):
                    setattr(pattern, col_key, new_value)
                    self._refresh_code_pattern_list()

            def on_cancel(event=None):
                entry.destroy()

            entry.bind("<Return>", on_confirm)
            entry.bind("<Tab>", on_confirm)
            entry.bind("<Escape>", on_cancel)
            entry.bind("<FocusOut>", on_confirm)

    def _show_code_dropdown(
        self,
        item: str,
        col_key: str,
        pattern: "CodePattern",
        x: int,
        y: int,
        width: int,
        height: int,
        options: list,
    ) -> None:
        """Show a dropdown for selecting category or action.
        
        Args:
            item: Treeview item ID.
            col_key: Column key.
            pattern: Code pattern being edited.
            x, y, width, height: Cell coordinates.
            options: List of dropdown options.
        """
        current_value = getattr(pattern, col_key, "")
        combo = ttk.Combobox(self._code_tree, values=options, state="readonly")
        combo.set(current_value)
        combo.place(x=x, y=y, width=width, height=height)
        combo.focus_set()

        def on_select(event=None):
            new_value = combo.get()
            combo.destroy()
            if new_value != current_value:
                setattr(pattern, col_key, new_value)
                self._refresh_code_pattern_list()

        def on_cancel(event=None):
            combo.destroy()

        combo.bind("<<ComboboxSelected>>", on_select)
        combo.bind("<Return>", on_select)
        combo.bind("<Escape>", on_cancel)
        combo.bind("<FocusOut>", on_select)

    def _refresh_code_pattern_list(self) -> None:
        """Refresh code pattern treeview."""
        for item in self._code_tree.get_children():
            self._code_tree.delete(item)

        for pattern in self._metadata.code_patterns:
            self._code_tree.insert(
                "",
                "end",
                values=(pattern.pattern, pattern.category, pattern.action),
            )

    def _on_import_code_patterns(self) -> None:
        """Import code patterns from Analysis step."""
        try:
            analysis_step_data = self.session.get_step(1).data
            analysis_results = analysis_step_data.get("analysis_results", {})
            code_patterns = analysis_results.get("code_patterns", {})

            if not code_patterns:
                messagebox.showinfo(
                    "No Patterns",
                    "No code patterns were detected in Analysis.\n\n"
                    "Run Analysis first to detect patterns.",
                )
                return

            # Confirm import
            existing_count = len(self._metadata.code_patterns)
            pattern_count = len(code_patterns)

            if existing_count > 0:
                response = messagebox.askyesno(
                    "Import Patterns",
                    f"Found {pattern_count} code patterns in Analysis.\n\n"
                    f"You already have {existing_count} patterns.\n\n"
                    "Add new patterns to existing list?",
                )
                if not response:
                    return

            # Import patterns
            imported_count = 0
            existing_patterns = {p.pattern for p in self._metadata.code_patterns}

            for category, count in code_patterns.items():
                # Create a generic pattern for each category
                if category in existing_patterns:
                    continue

                pattern = CodePattern(
                    pattern=category,
                    category=category,
                    action="preserve",
                    notes=f"Imported from Analysis ({count} occurrences)",
                )
                self._metadata.code_patterns.append(pattern)
                existing_patterns.add(category)
                imported_count += 1

            self._refresh_code_pattern_list()

            if imported_count > 0:
                messagebox.showinfo(
                    "Import Complete",
                    f"Imported {imported_count} new patterns from Analysis.",
                )
            else:
                messagebox.showinfo(
                    "No New Patterns",
                    "All detected patterns already exist in the list.",
                )

        except (AttributeError, KeyError, IndexError):
            messagebox.showwarning(
                "Analysis Required",
                "Run Analysis first to detect code patterns.",
            )
        except Exception as e:
            logger.error(f"Failed to import code patterns: {e}")
            messagebox.showerror("Import Error", f"Failed to import: {e}")

    def _on_use_global_glossary_changed(self) -> None:
        """Handle Use Global Glossary checkbox change (TASK 19 Phase 4)."""
        use_global = self._use_global_glossary_var.get()
        
        # Update ManifestManager if available
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.set_use_global_glossary(use_global)
        
        # Update info label
        if use_global:
            self._glossary_info_label.config(
                text="Global glossary entries will be applied during translation."
            )
        else:
            self._glossary_info_label.config(
                text="Only project-specific glossary entries will be used."
            )
        
        logger.debug("Use global glossary changed to: %s", use_global)

    def _on_copy_from_global_glossary(self) -> None:
        """Copy entries from global glossary to project glossary (TASK 19 Phase 4)."""
        try:
            from CherryAI.gui.helpers.glossary_adapter import load_glossary
            
            # Load global glossary
            global_entries = load_glossary()
            if not global_entries:
                messagebox.showinfo(
                    "No Global Glossary",
                    "No global glossary entries found.\n\n"
                    "Run Analysis on your files to populate the glossary.",
                )
                return
            
            # Get ManifestManager
            mgr = self.manifest_manager
            if mgr is None or not mgr.is_loaded:
                messagebox.showwarning(
                    "No Project",
                    "Load or create a project first before copying glossary entries.",
                )
                return
            
            # Copy entries to project glossary
            config = mgr.get_glossary_config()
            
            # Convert global entries to dict format
            copied_count = 0
            existing_terms = {e.get("source", "") for e in config.project_entries}
            
            for key, entry in global_entries.items():
                source = entry.original
                if source and source not in existing_terms:
                    config.project_entries.append({
                        "source": source,
                        "target": entry.translation or "",
                        "notes": entry.notes or "",
                        "gender": entry.gender or "",
                        "type": entry.entry_type or "term",
                    })
                    existing_terms.add(source)
                    copied_count += 1
            
            mgr.set_glossary_config(config)
            
            # Update count display
            self._project_glossary_count_var.set(
                f"Project entries: {len(config.project_entries)}"
            )
            
            if copied_count > 0:
                messagebox.showinfo(
                    "Copy Complete",
                    f"Copied {copied_count} new entries from global glossary.\n\n"
                    f"Project now has {len(config.project_entries)} entries.",
                )
            else:
                messagebox.showinfo(
                    "No New Entries",
                    "All global entries already exist in project glossary.",
                )
                
        except ImportError as e:
            logger.warning("Glossary adapter not available: %s", e)
            messagebox.showwarning(
                "Module Not Available",
                "Glossary module not loaded. Try running Analysis first.",
            )
        except Exception as e:
            logger.error(f"Failed to copy from global glossary: {e}")
            messagebox.showerror("Error", f"Failed to copy glossary: {e}")

    # ========================================================================
    # Data Management
    # ========================================================================

    def _collect_metadata(self) -> None:
        """Collect form data into metadata object."""
        self._metadata.project_name = self._project_name_var.get()
        self._metadata.game_title = self._game_title_var.get()
        self._metadata.genre = self._genre_var.get()
        self._metadata.source_language = self._source_lang_var.get()
        self._metadata.target_language = self._target_lang_var.get()
        self._metadata.summary = self._summary_text.get("1.0", "end-1c")
        self._metadata.style = self._style_var.get()
        try:
            self._metadata.style_preset = StylePreset(self._style_preset_var.get())
        except ValueError:
            self._metadata.style_preset = StylePreset.NATURAL
        self._metadata.tone = self._tone_var.get()
        try:
            self._metadata.tone_preset = TonePreset(self._tone_preset_var.get())
        except ValueError:
            self._metadata.tone_preset = TonePreset.NEUTRAL
        self._metadata.custom_notes = self._notes_text.get("1.0", "end-1c")
        self._metadata.updated_at = datetime.now().isoformat()
        if not self._metadata.created_at:
            self._metadata.created_at = self._metadata.updated_at

    def _populate_form(self) -> None:
        """Populate form fields from metadata object."""
        self._project_name_var.set(self._metadata.project_name)
        self._game_title_var.set(self._metadata.game_title)
        self._genre_var.set(self._metadata.genre)
        self._source_lang_var.set(self._metadata.source_language)
        self._target_lang_var.set(self._metadata.target_language)

        self._summary_text.delete("1.0", "end")
        self._summary_text.insert("1.0", self._metadata.summary)

        self._style_preset_var.set(self._metadata.style_preset.value)
        self._style_var.set(self._metadata.style)
        self._on_style_changed()

        self._tone_preset_var.set(self._metadata.tone_preset.value)
        self._tone_var.set(self._metadata.tone)
        self._on_tone_changed()

        self._notes_text.delete("1.0", "end")
        self._notes_text.insert("1.0", self._metadata.custom_notes)

        self._refresh_character_list()
        self._refresh_code_pattern_list()  # TASK 18.2: Also refresh code patterns
        self._refresh_glossary_settings()  # TASK 19 Phase 4

    def _refresh_glossary_settings(self) -> None:
        """Refresh glossary settings from ManifestManager (TASK 19 Phase 4)."""
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            config = mgr.get_glossary_config()
            self._use_global_glossary_var.set(config.use_global)
            self._project_glossary_count_var.set(
                f"Project entries: {len(config.project_entries)}"
            )
            # Update info label
            if config.use_global:
                self._glossary_info_label.config(
                    text="Global glossary entries will be applied during translation."
                )
            else:
                self._glossary_info_label.config(
                    text="Only project-specific glossary entries will be used."
                )

    def _save_metadata(self) -> None:
        """Save metadata to session state."""
        self._collect_metadata()
        data = self.get_step_data()
        data["metadata"] = self._metadata.to_dict()
        data["inference_options"] = {
            "enabled": self._infer_enabled_var.get(),
            "infer_summary": self._infer_summary_var.get(),
            "infer_tone": self._infer_tone_var.get(),
            "infer_characters": self._infer_chars_var.get(),
            "sample_lines": self._sample_lines_var.get(),
        }
        self.set_step_data(data)
        messagebox.showinfo("Saved", "Project information saved successfully.")

    def _load_metadata(self) -> None:
        """Load metadata from session state."""
        data = self.get_step_data()
        if "metadata" in data:
            self._metadata = ProjectMetadata.from_dict(data["metadata"])
            self._populate_form()
        if "inference_options" in data:
            opts = data["inference_options"]
            self._infer_enabled_var.set(opts.get("enabled", False))
            self._infer_summary_var.set(opts.get("infer_summary", True))
            self._infer_tone_var.set(opts.get("infer_tone", True))
            self._infer_chars_var.set(opts.get("infer_characters", True))
            self._sample_lines_var.set(opts.get("sample_lines", 50))

    # ========================================================================
    # LLM Inference
    # ========================================================================

    def _run_inference(self) -> None:
        """Run LLM inference for metadata.
        
        Note: UI button removed, but method kept for potential programmatic access.
        """
        if self._is_inferring:
            return

        if not self._infer_enabled_var.get():
            messagebox.showinfo(
                "Inference Disabled",
                "Enable LLM inference in the options section first.",
            )
            return

        # Get sample lines from input step
        lines = self._get_sample_lines()
        if not lines:
            messagebox.showwarning(
                "No Data",
                "No text lines available. Load files in the Input step first.",
            )
            return

        self._is_inferring = True
        # Note: _infer_btn removed (UI deprecated)
        self._infer_status_var.set("Running inference...")

        # Run in background thread
        thread = threading.Thread(target=self._inference_worker, args=(lines,))
        thread.daemon = True
        thread.start()

    def _get_sample_lines(self) -> List[str]:
        """Get sample lines from input step."""
        try:
            input_step_data = self.session.get_step(0).data
            all_lines = input_step_data.get("all_lines", [])
            sample_count = self._sample_lines_var.get()
            return all_lines[:sample_count]
        except Exception as e:
            logger.warning(f"Failed to get sample lines: {e}")
            return []

    def _inference_worker(self, lines: List[str]) -> None:
        """Background worker for LLM inference."""
        try:
            # Build a simple prompt for inference
            sample_text = "\n".join(lines[:50])
            result = self._mock_inference(sample_text)
            self._inference_result = result

            # Update UI on main thread
            self.after(0, self._inference_complete)
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            self._inference_result.status = InferenceStatus.FAILED
            self._inference_result.error = str(e)
            self.after(0, self._inference_failed)

    def _mock_inference(self, sample_text: str) -> InferenceResult:
        """Mock inference for testing (replace with actual API call)."""
        # This is a placeholder - in production, this would call the API
        result = InferenceResult()
        result.status = InferenceStatus.COMPLETED

        # Simple heuristics for mock inference
        if "魔王" in sample_text or "勇者" in sample_text:
            result.genre = "Fantasy"
            result.tone = "dramatic"
            result.style = "natural"
            result.summary = (
                "A fantasy story featuring a demon lord and hero. "
                "The narrative involves conflict between magical forces."
            )
        else:
            result.genre = "Visual Novel"
            result.tone = "neutral"
            result.style = "natural"
            result.summary = "A Japanese visual novel or game text."

        # Extract potential character names (simple heuristic)
        import re

        speaker_pattern = r"^([^:：]+)[:：]"
        speakers = set()
        for line in sample_text.split("\n"):
            match = re.match(speaker_pattern, line)
            if match:
                name = match.group(1).strip()
                if len(name) < 20:  # Reasonable name length
                    speakers.add(name)

        for name in list(speakers)[:5]:  # Limit to 5 characters
            result.characters.append(
                CharacterInfo(
                    name="",  # Translation left empty by default
                    original_name=name,
                    role="Speaker",
                )
            )

        return result

    def _inference_complete(self) -> None:
        """Handle successful inference completion."""
        self._is_inferring = False
        # Note: _infer_btn removed (UI deprecated)
        self._infer_status_var.set("Inference completed!")

        # Offer to apply results
        if messagebox.askyesno(
            "Apply Results",
            "Inference completed. Apply the results to the form?",
        ):
            self._apply_inference_results()

    def _apply_inference_results(self) -> None:
        """Apply inference results to form fields."""
        result = self._inference_result
        if result.summary and not self._metadata.summary:
            self._summary_text.delete("1.0", "end")
            self._summary_text.insert("1.0", result.summary)

        if result.genre and not self._metadata.genre:
            self._genre_var.set(result.genre)

        if result.tone:
            self._tone_var.set(result.tone)

        if result.style:
            self._style_var.set(result.style)

        # Add inferred characters (avoiding duplicates)
        existing_names = {c.name for c in self._metadata.characters}
        for char in result.characters:
            if char.name not in existing_names:
                self._metadata.characters.append(char)

        self._refresh_character_list()

    def _inference_failed(self) -> None:
        """Handle inference failure."""
        self._is_inferring = False
        # Note: _infer_btn removed (UI deprecated)
        self._infer_status_var.set(f"Inference failed: {self._inference_result.error}")

    # ========================================================================
    # BaseStep Interface
    # ========================================================================

    def on_enter(self) -> None:
        """Called when step is entered."""
        self._load_metadata()
        # Task 18.4: Import characters from Analysis step if available
        self._import_analysis_speakers()
        # Check for suggested project name from Input step
        self._apply_suggested_project_name()
        # Auto-import code patterns from Analysis if none exist
        self._auto_import_code_patterns()

    def _import_analysis_speakers(self) -> None:
        """Import detected speakers from Analysis step into Character Notes.
        
        This implements Task 18.4: Analysis to Information Glossary Integration.
        Transfers characters found during Analysis to the Character Notes widget,
        including gender inference based on speaker names.
        """
        try:
            # Get analysis results from session (stored under 'analysis_results')
            analysis_step_data = self.session.get_step(1).data
            analysis_results = analysis_step_data.get("analysis_results", {})
            speakers = analysis_results.get("speakers", {})
            
            if not speakers:
                return
            
            # Check if we should import (only if no characters exist yet)
            if self._metadata.characters:
                return  # Don't overwrite existing characters
            
            # Try to import gender inference function
            infer_gender_fn = None
            try:
                from CherryAI.functions.glossaries.name_glossary_functions import (
                    infer_gender_comprehensive,
                    GENDERED_PRONOUNS,
                    GENDERED_HONORIFICS,
                )
                infer_gender_fn = infer_gender_comprehensive
            except ImportError:
                logger.debug("Gender inference not available")
            
            # Import top speakers as characters
            imported_count = 0
            existing_originals = {c.original_name for c in self._metadata.characters}
            
            # Sort by count, take top 20
            sorted_speakers = sorted(speakers.items(), key=lambda x: x[1], reverse=True)[:20]
            
            for speaker_name, count in sorted_speakers:
                if speaker_name in existing_originals:
                    continue
                
                # Infer gender from speaker name if available
                gender = ""
                if infer_gender_fn:
                    try:
                        # Use name-based heuristics (honorific/pronoun data not available here)
                        inferred, confidence, _, _, _ = infer_gender_fn(
                            name=speaker_name,
                            pronouns={},
                            honorifics={},
                            full_text="",
                            confidence_threshold=0.7,
                        )
                        if inferred and inferred != "Unknown" and confidence >= 50:
                            gender = inferred
                    except Exception as e:
                        logger.debug(f"Gender inference failed for {speaker_name}: {e}")
                    
                # Create CharacterInfo from speaker
                # Translation (name) left empty by default
                char = CharacterInfo(
                    name="",  # Translation left empty by default
                    original_name=speaker_name,
                    role="Speaker",
                    gender=gender,
                    notes=f"Auto-imported from Analysis ({count} occurrences)",
                )
                self._metadata.characters.append(char)
                existing_originals.add(speaker_name)
                imported_count += 1
            
            if imported_count > 0:
                self._refresh_character_list()
                logger.info(f"Imported {imported_count} speakers from Analysis")
                
        except (AttributeError, KeyError, IndexError):
            # Analysis step data not available
            pass
        except Exception as e:
            logger.warning(f"Failed to import analysis speakers: {e}")

    def _apply_suggested_project_name(self) -> None:
        """Apply suggested project name from Input step if field is empty.
        
        Checks the Input step's step_data for a suggested_project_name and
        applies it to the project name field if the user hasn't entered one.
        """
        # Only apply if project name is empty
        if self._project_name_var.get().strip():
            return
            
        try:
            # Get suggested name from Input step (step 0)
            input_step_data = self.session.get_step(0).data
            suggested_name = input_step_data.get("suggested_project_name", "")
            
            if suggested_name:
                self._project_name_var.set(suggested_name)
                logger.debug(f"Applied suggested project name: {suggested_name}")
        except (AttributeError, KeyError, IndexError):
            # Input step data not available
            pass
        except Exception as e:
            logger.debug(f"Could not apply suggested project name: {e}")

    def _auto_import_code_patterns(self) -> None:
        """Auto-import code patterns from Analysis if none exist.
        
        Silently imports code patterns detected during Analysis to the
        Code Glossary if no patterns are currently defined.
        """
        # Only auto-import if no patterns exist
        if self._metadata.code_patterns:
            return
            
        try:
            # Get code patterns from Analysis step (step 1)
            analysis_step_data = self.session.get_step(1).data
            analysis_results = analysis_step_data.get("analysis_results", {})
            code_patterns = analysis_results.get("code_patterns", {})
            
            if not code_patterns:
                return
            
            # Import patterns silently
            imported_count = 0
            for category, count in code_patterns.items():
                pattern = CodePattern(
                    pattern=category,
                    category=category,
                    action="preserve",
                    notes=f"Auto-imported from Analysis ({count} occurrences)",
                )
                self._metadata.code_patterns.append(pattern)
                imported_count += 1
            
            if imported_count > 0:
                self._refresh_code_pattern_list()
                logger.info(f"Auto-imported {imported_count} code patterns from Analysis")
                
        except (AttributeError, KeyError, IndexError):
            # Analysis step data not available
            pass
        except Exception as e:
            logger.debug(f"Could not auto-import code patterns: {e}")

    def on_leave(self) -> None:
        """Called when leaving step."""
        self._collect_metadata()
        data = self.get_step_data()
        data["metadata"] = self._metadata.to_dict()
        self.set_step_data(data)

    # ========================================================================
    # Public API
    # ========================================================================

    def get_metadata(self) -> ProjectMetadata:
        """Get current project metadata.

        Returns:
            ProjectMetadata object.
        """
        self._collect_metadata()
        return self._metadata

    def get_inference_options(self) -> InferenceOptions:
        """Get current inference options.

        Returns:
            InferenceOptions object.
        """
        return InferenceOptions(
            enabled=self._infer_enabled_var.get(),
            infer_summary=self._infer_summary_var.get(),
            infer_tone=self._infer_tone_var.get(),
            infer_characters=self._infer_chars_var.get(),
            sample_lines=self._sample_lines_var.get(),
        )

    def get_inference_result(self) -> InferenceResult:
        """Get last inference result.

        Returns:
            InferenceResult object.
        """
        return self._inference_result


# ============================================================================
# Character Dialog
# ============================================================================


class CharacterDialog(tk.Toplevel):
    """Dialog for adding/editing character information."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        character: Optional[CharacterInfo] = None,
    ) -> None:
        """Initialize character dialog.

        Args:
            parent: Parent widget.
            title: Dialog title.
            character: Optional existing character to edit.
        """
        super().__init__(parent)
        self.title(title)
        self.result: Optional[CharacterInfo] = None
        self._character = character or CharacterInfo(name="")

        self.geometry("400x350")
        self.resizable(False, False)
        self.transient(parent)  # type: ignore[call-overload]
        self.grab_set()

        self._build_ui()

        if character:
            self._populate()

        self.wait_window()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        # Original Name (first - this is the source name)
        row1 = ttk.Frame(main)
        row1.pack(fill="x", pady=5)
        ttk.Label(row1, text="Original Name:", width=15).pack(side="left")
        self._orig_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self._orig_var).pack(side="left", fill="x", expand=True)

        # Translation (formerly Name - this is the translated name)
        row2 = ttk.Frame(main)
        row2.pack(fill="x", pady=5)
        ttk.Label(row2, text="Translation:", width=15).pack(side="left")
        self._name_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self._name_var).pack(side="left", fill="x", expand=True)

        # Gender
        row3 = ttk.Frame(main)
        row3.pack(fill="x", pady=5)
        ttk.Label(row3, text="Gender:", width=15).pack(side="left")
        self._gender_var = tk.StringVar()
        gender_combo = ttk.Combobox(
            row3,
            textvariable=self._gender_var,
            values=["Male", "Female", "Non-binary", "Unknown"],
            state="normal",
        )
        gender_combo.pack(side="left", fill="x", expand=True)

        # Role
        row4 = ttk.Frame(main)
        row4.pack(fill="x", pady=5)
        ttk.Label(row4, text="Role:", width=15).pack(side="left")
        self._role_var = tk.StringVar()
        role_combo = ttk.Combobox(
            row4,
            textvariable=self._role_var,
            values=[
                "Main Character",
                "Major Character",
                "Minor Character",
                "Side Character",
                "Villain",
                "Love Interest",
                "Mentor",
                "Narrator",
                "Speaker",
            ],
            state="normal",
        )
        role_combo.pack(side="left", fill="x", expand=True)

        # Speaking Style
        row5 = ttk.Frame(main)
        row5.pack(fill="x", pady=5)
        ttk.Label(row5, text="Speaking Style:", width=15).pack(side="left")
        self._style_var = tk.StringVar()
        ttk.Entry(row5, textvariable=self._style_var).pack(
            side="left", fill="x", expand=True
        )

        # Notes
        ttk.Label(main, text="Notes:").pack(anchor="w", pady=(10, 0))
        self._notes_text = scrolledtext.ScrolledText(main, height=4, wrap="word")
        self._notes_text.pack(fill="x", pady=5)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="right")

    def _populate(self) -> None:
        """Populate fields from character."""
        self._name_var.set(self._character.name)
        self._orig_var.set(self._character.original_name)
        self._gender_var.set(self._character.gender)
        self._role_var.set(self._character.role)
        self._style_var.set(self._character.speaking_style)
        self._notes_text.insert("1.0", self._character.notes)

    def _on_ok(self) -> None:
        """Handle OK button."""
        original_name = self._orig_var.get().strip()
        if not original_name:
            messagebox.showwarning("Required", "Original Name is required.")
            return

        self.result = CharacterInfo(
            name=self._name_var.get().strip(),  # Translation (may be empty)
            original_name=original_name,
            gender=self._gender_var.get().strip(),
            role=self._role_var.get().strip(),
            speaking_style=self._style_var.get().strip(),
            notes=self._notes_text.get("1.0", "end-1c").strip(),
        )
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.destroy()


class CodePatternDialog(tk.Toplevel):
    """Dialog for adding/editing code pattern information (TASK 18.5)."""

    # Common code pattern actions
    ACTIONS = ["preserve", "translate", "remove"]

    # Common code pattern categories
    CATEGORIES = [
        "RPG Maker Variable",
        "RPG Maker Switch",
        "Ruby Code",
        "Control Code",
        "HTML Tag",
        "Placeholder",
        "Custom",
    ]

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        pattern: Optional[CodePattern] = None,
    ) -> None:
        """Initialize code pattern dialog.

        Args:
            parent: Parent widget.
            title: Dialog title.
            pattern: Optional existing pattern to edit.
        """
        super().__init__(parent)
        self.title(title)
        self.result: Optional[CodePattern] = None
        self._pattern = pattern or CodePattern(pattern="")

        self.geometry("450x400")  # TASK 18.3: Increased from 350 to 400 for visible buttons
        self.resizable(False, False)
        self.transient(parent)  # type: ignore[call-overload]
        self.grab_set()

        self._build_ui()

        if pattern:
            self._populate()

        self.wait_window()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        # Pattern
        row1 = ttk.Frame(main)
        row1.pack(fill="x", pady=5)
        ttk.Label(row1, text="Pattern:", width=15).pack(side="left")
        self._pattern_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self._pattern_var).pack(
            side="left", fill="x", expand=True
        )

        # Category
        row2 = ttk.Frame(main)
        row2.pack(fill="x", pady=5)
        ttk.Label(row2, text="Category:", width=15).pack(side="left")
        self._category_var = tk.StringVar()
        category_combo = ttk.Combobox(
            row2,
            textvariable=self._category_var,
            values=self.CATEGORIES,
            state="normal",
        )
        category_combo.pack(side="left", fill="x", expand=True)

        # Action
        row3 = ttk.Frame(main)
        row3.pack(fill="x", pady=5)
        ttk.Label(row3, text="Action:", width=15).pack(side="left")
        self._action_var = tk.StringVar(value="preserve")
        action_combo = ttk.Combobox(
            row3,
            textvariable=self._action_var,
            values=self.ACTIONS,
            state="readonly",
        )
        action_combo.pack(side="left", fill="x", expand=True)

        # Example
        row4 = ttk.Frame(main)
        row4.pack(fill="x", pady=5)
        ttk.Label(row4, text="Example:", width=15).pack(side="left")
        self._example_var = tk.StringVar()
        ttk.Entry(row4, textvariable=self._example_var).pack(
            side="left", fill="x", expand=True
        )

        # Notes
        ttk.Label(main, text="Notes:").pack(anchor="w", pady=(10, 0))
        self._notes_text = scrolledtext.ScrolledText(main, height=4, wrap="word")
        self._notes_text.pack(fill="x", pady=5)

        # Action descriptions
        desc_frame = ttk.LabelFrame(main, text="Action Guide")
        desc_frame.pack(fill="x", pady=5)
        ttk.Label(
            desc_frame,
            text="• preserve: Keep pattern unchanged in translation\n"
            "• translate: Include in translation context\n"
            "• remove: Strip pattern from output",
            font=("Segoe UI", 8),
            foreground="gray",
            justify="left",
        ).pack(padx=5, pady=5)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(
            side="right", padx=5
        )
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(
            side="right"
        )

    def _populate(self) -> None:
        """Populate fields from pattern."""
        self._pattern_var.set(self._pattern.pattern)
        self._category_var.set(self._pattern.category)
        self._action_var.set(self._pattern.action)
        self._example_var.set(self._pattern.example)
        self._notes_text.insert("1.0", self._pattern.notes)

    def _on_ok(self) -> None:
        """Handle OK button."""
        pattern = self._pattern_var.get().strip()
        if not pattern:
            messagebox.showwarning("Required", "Pattern is required.")
            return

        self.result = CodePattern(
            pattern=pattern,
            category=self._category_var.get().strip(),
            action=self._action_var.get().strip() or "preserve",
            example=self._example_var.get().strip(),
            notes=self._notes_text.get("1.0", "end-1c").strip(),
        )
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.destroy()
