"""CherryAI GUI v2 Information Step.

Third workflow tab for project metadata and LLM-assisted inference.
Provides fields for project name, summary, style, and character notes.

TASK 23.1: Basic Metadata Fields bound to manifest.
TASK 23.2: Style and Tone Fields bound to manifest.
TASK 23.3: Character Notes and Code Database bound to manifest.
TASK 23.4: System Instructions field (renamed Prompt←Additional Notes) bound to manifest.
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
from tkinter import ttk, messagebox, scrolledtext, simpledialog

from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME
from CherryAI.gui.helpers.confirmations import confirm_action
from CherryAI.gui.helpers.manifest_binding import (
    BindingInfo,
    bind_entry_to_field,
    bind_entry_to_info_field,
    bind_checkbox_to_field,
    bind_combobox_to_field,
    bind_combobox_to_info_field,
    bind_text_to_field,
    bind_scrolledtext_to_info_field,
    load_all_bindings,
)
from CherryAI.functions.manifest_fields import (
    save_character_notes,
    load_character_notes,
    save_code_glossary,
    load_code_glossary,
)
from CherryAI.functions import ini_manager

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
    """Information about a character.

    Attributes:
        original_name: Source-language name (lookup key).
        translation: Translated name in target language.
        notes: Free-form notes (gender, role, speaking style, etc.).
        count: Occurrence count from analysis speaker detection.
    """

    original_name: str = ""
    translation: str = ""
    notes: str = ""
    count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "original_name": self.original_name,
            "translation": self.translation,
            "notes": self.notes,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterInfo":
        """Create from dictionary."""
        return cls(
            original_name=data.get("original_name", ""),
            translation=data.get("translation", ""),
            notes=data.get("notes", ""),
            count=int(data.get("count", 0)),
        )


@dataclass
class CodePattern:
    """Information about a code pattern for glossary (TASK 18.5).

    Represents code patterns detected during Analysis that should be
    preserved during translation (e.g., variables, control codes).

    Attributes:
        pattern: The code pattern regex or string.
        translation: Translated term for this pattern.
        category: Category like 'RPG Maker Variable', 'Ruby Code', etc.
        action: How to handle: 'preserve', 'provides_context', 'custom_placeholder',
            'protect', 'strip_with_anchor', 'part_of_span'.
        example: Example occurrence from the source text.
        notes: User notes about this pattern.
        count: Total occurrence count from analysis.
        raw_type: Internal type constant from detection engine.
        instances: Concrete instances for aggregated patterns.
        instance_counts: Per-instance occurrence counts (parallel to instances).
    """

    pattern: str
    translation: str = ""
    category: str = ""
    action: str = "preserve"
    example: str = ""
    notes: str = ""
    count: int = 0
    raw_type: str = ""
    instances: List[str] = field(default_factory=list)
    instance_counts: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        When instances exist, ``count`` is serialized as
        ``[total, inst1_count, inst2_count, ...]``.
        """
        result: Dict[str, Any] = {
            "pattern": self.pattern,
            "translation": self.translation,
            "category": self.category,
            "action": self.action,
            "example": self.example,
            "notes": self.notes,
            "raw_type": self.raw_type,
        }
        if self.instance_counts:
            result["count"] = [self.count] + list(self.instance_counts)
        else:
            result["count"] = self.count
        if self.instances:
            result["instances"] = list(self.instances)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodePattern":
        """Create from dictionary."""
        instances = data.get("instances", [])
        if not isinstance(instances, list):
            instances = []
        # count can be int or [total, inst1_count, inst2_count, ...]
        count_val = data.get("count", 0)
        if isinstance(count_val, list):
            count = int(count_val[0]) if count_val else 0
            instance_counts = [int(c) for c in count_val[1:]]
        else:
            count = int(count_val)
            instance_counts = []
        # Migrate legacy action values
        raw_action = data.get("action", "preserve")
        if raw_action == "remove":
            raw_action = "preserve"
        elif raw_action == "translate":
            raw_action = "provides_context"
        elif raw_action == "replace":
            raw_action = "protect"
        return cls(
            pattern=data.get("pattern", ""),
            translation=data.get("translation", ""),
            category=data.get("category", ""),
            action=raw_action,
            example=data.get("example", ""),
            notes=data.get("notes", ""),
            count=count,
            raw_type=str(data.get("raw_type", "")),
            instances=instances,
            instance_counts=instance_counts,
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
    style_preset: str = "Natural"
    tone: str = ""
    tone_preset: str = "Neutral"
    genre: str = ""
    characters: List[CharacterInfo] = field(default_factory=list)
    code_patterns: List[CodePattern] = field(default_factory=list)  # TASK 18.5
    system_instructions: str = ""
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
            "style_preset": self.style_preset,
            "tone": self.tone,
            "tone_preset": self.tone_preset,
            "genre": self.genre,
            "characters": [c.to_dict() for c in self.characters],
            "code_patterns": [p.to_dict() for p in self.code_patterns],
            "system_instructions": self.system_instructions,
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
        style_preset = data.get("style_preset", "Natural")
        tone_preset = data.get("tone_preset", "Neutral")
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
            system_instructions=data.get("system_instructions", ""),
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
# Preset System — Style and Tone
# ============================================================================

# Default style presets: name → prompt text that gets sent to the LLM.
DEFAULT_STYLE_PRESETS: Dict[str, str] = {
    "Literal": (
        "Translate as literally as possible. Preserve the original sentence "
        "structure, word order, and phrasing. Prioritize accuracy over "
        "natural flow in the target language."
    ),
    "Natural": (
        "Translate naturally and fluently. Adapt sentence structure and "
        "phrasing to feel native in the target language while preserving "
        "the original meaning. Prioritize readability."
    ),
    "Creative": (
        "Translate with creative liberty. Adapt idioms, humor, and cultural "
        "references for the target audience. You may rephrase freely to "
        "capture the spirit of the original rather than the exact words."
    ),
    "Formal": (
        "Use a formal, professional register. Choose polished vocabulary "
        "and structured phrasing. Avoid colloquialisms, contractions, and "
        "slang."
    ),
    "Casual": (
        "Use an informal, conversational tone. Employ natural contractions, "
        "colloquial expressions, and relaxed phrasing as spoken language."
    ),
    "Technical": (
        "Use precise, technical language. Maintain exact terminology and "
        "avoid ambiguity. Prefer established translations for domain-specific "
        "terms."
    ),
    "Literary": (
        "Translate with literary finesse. Use rich vocabulary, varied "
        "sentence rhythm, and artistic phrasing. Preserve poetic devices "
        "and narrative voice."
    ),
}

# Default tone presets: name → prompt text.
DEFAULT_TONE_PRESETS: Dict[str, str] = {
    "Neutral": (
        "Maintain a balanced, neutral tone throughout the translation. "
        "Do not add emotional emphasis or dramatic flair beyond what is "
        "present in the source."
    ),
    "Serious": (
        "Convey a grave, solemn atmosphere. Use measured, weighty phrasing "
        "appropriate for serious subject matter."
    ),
    "Humorous": (
        "Preserve and enhance comedic timing and humor. Adapt jokes and "
        "wordplay for the target language while keeping the light-hearted "
        "spirit."
    ),
    "Dramatic": (
        "Emphasize dramatic tension and intensity. Use impactful phrasing, "
        "strong verbs, and theatrical delivery to heighten emotional moments."
    ),
    "Lighthearted": (
        "Keep the mood cheerful and upbeat. Use bright, positive language "
        "and breezy phrasing that feels warm and inviting."
    ),
    "Dark": (
        "Convey a grim, ominous atmosphere. Use foreboding language, "
        "heavy imagery, and tense phrasing appropriate for dark themes."
    ),
    "Romantic": (
        "Use warm, emotionally resonant language. Convey tenderness, "
        "affection, and intimacy through gentle phrasing and evocative "
        "word choices."
    ),
    "Action": (
        "Use punchy, fast-paced language. Keep sentences short and energetic. "
        "Emphasize motion, impact, and urgency to match action sequences."
    ),
}

# "Custom" is the sentinel name — always present, never deletable.
CUSTOM_PRESET_NAME = "Custom"

# Default text for the Summary widget.
# ---------------------------------------------------------------------------
# Preset loading / saving — all delegate to ini_manager
# ---------------------------------------------------------------------------


def _get_default_summary() -> str:
    """Return the default Summary text from INI [defaults] or built-in fallback."""
    return ini_manager.get_default_text("Summary")


def _get_default_system_instructions() -> str:
    """Return the default System Instructions text from INI [defaults] or built-in."""
    return ini_manager.get_default_text("SystemInstruction")


# Module-level constants populated from INI (or built-ins) at import time.
DEFAULT_SUMMARY_TEXT: str = _get_default_summary()
DEFAULT_SYSTEM_INSTRUCTIONS: str = _get_default_system_instructions()

# SI presets directory.
_USER_PRESETS_DIR = ini_manager.get_user_dir() / "presets"

# Default SI preset dict shown in the SI preset combobox.
DEFAULT_SI_PRESETS: Dict[str, str] = {
    "Default": DEFAULT_SYSTEM_INSTRUCTIONS,
}


def _unique_preset_name(name: str, existing: Dict[str, str]) -> str:
    """Return *name* if unique in *existing*, otherwise append the lowest free number."""
    if name not in existing:
        return name
    n = 1
    while f"{name}{n}" in existing:
        n += 1
    return f"{name}{n}"


def _load_si_presets() -> Dict[str, str]:
    """Load System Instructions presets from INI (via ini_manager).

    Returns ordered dict: Custom first, Default second, then alphabetical
    user presets.
    """
    return ini_manager.get_all_si_presets()


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
    
    TASK 23: Manifest Integration
    - All fields auto-save to manifest on change
    - All fields auto-load from manifest on step enter
    """

    step_id = 2
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

        # Collapsible widget state (right column widgets)
        self._collapsible_state: Dict[str, bool] = {
            "glossary": True,
            "code_database": True,
            "knowledge_base": True,
        }
        self._collapsible_content: Dict[str, ttk.Frame] = {}
        self._collapsible_buttons: Dict[str, ttk.Button] = {}

        # TASK 23: Manifest bindings for auto-save/load
        self._manifest_bindings: List[BindingInfo] = []

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

    def _build_content(self) -> None:
        """Build the main content area with 2-column layout.

        Layout:
        - Left column: Project Details, Languages, Summary, Style & Tone,
          System Instructions
        - Right column: Glossary, Glossary Settings, Code Database,
          Global Glossary/Database (all collapsible), JSON View

        TASK 23.4: Prompt field moved from right column to left column
                   before Characters.
        Glossary (characters) moved to right column with other
        glossary/database widgets.  All right-column widgets are
        collapsible and expand to fill the window height when maximized.
        """
        # Main container with scrolling
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._scrollable_frame = ttk.Frame(canvas)

        self._scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        self._canvas_window = canvas.create_window(
            (0, 0), window=self._scrollable_frame, anchor="nw",
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y")
        self._canvas = canvas

        # Stretch inner frame to fill viewport height so right-column
        # collapsible widgets can expand vertically when maximized.
        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfig(self._canvas_window, width=event.width)
            req_height = self._scrollable_frame.winfo_reqheight()
            if req_height < event.height:
                canvas.itemconfig(self._canvas_window, height=event.height)

        canvas.bind("<Configure>", _on_canvas_configure)

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
        columns_frame.rowconfigure(0, weight=1)

        # Left column: Primary content
        self._left_column = ttk.Frame(columns_frame)
        self._left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # Right column: Collapsible glossary/database widgets
        self._right_column = ttk.Frame(columns_frame)
        self._right_column.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._right_column.columnconfigure(0, weight=1)
        for i in range(3):
            self._right_column.rowconfigure(i, weight=1)

        # Build sections in their respective columns
        # Left column sections:
        self._build_project_section()
        self._build_language_section()
        self._build_summary_section()
        self._build_style_section()
        self._build_notes_section()
        # Right column sections (all collapsible):
        self._build_character_section()
        self._build_code_glossary_section()
        self._build_knowledge_base_section()
        self._build_inference_section()  # Variables only, UI removed
        self._build_json_section()

    # ------------------------------------------------------------------
    # Collapsible Widget Helpers
    # ------------------------------------------------------------------

    def _toggle_collapsible(self, widget_name: str) -> None:
        """Toggle collapsed/expanded state of a right-column widget.

        When collapsed, the body frame is grid-removed so the section
        shrinks to just the header bar (button + title + separator line).
        When expanded, the body is shown and row weights are reconfigured.

        Args:
            widget_name: Key in ``_collapsible_state`` dict.
        """
        expanded = not self._collapsible_state.get(widget_name, True)
        self._collapsible_state[widget_name] = expanded

        content = self._collapsible_content.get(widget_name)
        button = self._collapsible_buttons.get(widget_name)

        if content is not None:
            if expanded:
                content.grid()
            else:
                content.grid_remove()

        if button:
            button.config(text="▾" if expanded else "▸")

        self._reconfigure_right_column_weights()

    def _reconfigure_right_column_weights(self) -> None:
        """Reconfigure right-column grid row weights based on collapse state.

        Expanded widgets get ``weight=1`` so they share extra vertical
        space evenly.  Collapsed widgets get ``weight=0`` so they only
        take the height of their header bar.
        """
        name_to_row = {
            "glossary": 0,
            "code_database": 1,
            "knowledge_base": 2,
        }
        for name, row in name_to_row.items():
            expanded = self._collapsible_state.get(name, True)
            self._right_column.rowconfigure(
                row, weight=1 if expanded else 0,
            )

    def _build_collapsible_labelframe(
        self,
        parent: ttk.Frame,
        title: str,
        widget_name: str,
        row: int,
        extra_header_widgets: Optional[Callable[["ttk.Frame"], None]] = None,
    ) -> ttk.Frame:
        """Create a collapsible section with a thin header bar and body.

        Structure:
            wrapper (grid in parent at *row*)
              ├── header  (row 0, always visible: ▾ button + title + separator)
              └── body    (row 1, hidden when collapsed)

        When collapsed the body is ``grid_remove``-d so only the
        header bar remains — no empty LabelFrame borders.

        Args:
            parent: Parent frame (typically ``self._right_column``).
            title: Section title text.
            widget_name: Key used in ``_collapsible_state``.
            row: Grid row in the parent.
            extra_header_widgets: Optional callable that receives the
                header frame and can pack additional widgets (e.g. an
                Enabled/Disabled button) into it.

        Returns:
            The body ``Frame`` where callers should place content.
        """
        # Outer wrapper sits in the parent grid
        wrapper = ttk.Frame(parent)
        wrapper.grid(row=row, column=0, sticky="nsew", padx=5, pady=2)
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(1, weight=1)

        # Header bar (always visible)
        header = ttk.Frame(wrapper)
        header.grid(row=0, column=0, sticky="ew")

        collapse_btn = ttk.Button(
            header,
            text="▾",
            width=2,
            command=lambda: self._toggle_collapsible(widget_name),
        )
        collapse_btn.pack(side="left", padx=(0, 4))
        ttk.Label(header, text=title, font=("", 9, "bold")).pack(
            side="left",
        )

        # Allow callers to inject extra widgets into the header
        if extra_header_widgets is not None:
            extra_header_widgets(header)

        # Horizontal separator extending to fill remaining width
        ttk.Separator(header, orient="horizontal").pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=6,
        )

        self._collapsible_buttons[widget_name] = collapse_btn

        # Body frame (collapsible)
        body = ttk.Frame(wrapper)
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self._collapsible_content[widget_name] = body

        return body

    def _build_project_section(self) -> None:
        """Build project name and title section.
        
        TASK 23.1: Fields bound to manifest for auto-save/load.
        """
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
        
        # TASK 23.1: Bind to manifest
        self._manifest_bindings.append(
            bind_entry_to_info_field(
                entry=self._project_name_entry,
                var=self._project_name_var,
                manager_getter=lambda: self.manifest_manager,
                meta_key="project_name",
                default="",
            )
        )

        # Title (renamed from "Game Title" per TASK 23.1)
        row2 = ttk.Frame(frame)
        row2.pack(fill="x", padx=10, pady=5)

        ttk.Label(row2, text="Title:", width=15, anchor="e").pack(
            side="left", padx=(0, 5)
        )
        self._game_title_var = tk.StringVar()
        self._game_title_entry = ttk.Entry(row2, textvariable=self._game_title_var)
        self._game_title_entry.pack(side="left", fill="x", expand=True)
        
        # TASK 23.1: Bind to manifest
        self._manifest_bindings.append(
            bind_entry_to_info_field(
                entry=self._game_title_entry,
                var=self._game_title_var,
                manager_getter=lambda: self.manifest_manager,
                meta_key="game_title",
                default="",
            )
        )

        # Genre
        row3 = ttk.Frame(frame)
        row3.pack(fill="x", padx=10, pady=5)

        ttk.Label(row3, text="Genre:", width=15, anchor="e").pack(
            side="left", padx=(0, 5)
        )
        self._genre_var = tk.StringVar()
        self._genre_entry = ttk.Entry(row3, textvariable=self._genre_var)
        self._genre_entry.pack(side="left", fill="x", expand=True)
        
        # TASK 23.1: Bind to manifest
        self._manifest_bindings.append(
            bind_entry_to_info_field(
                entry=self._genre_entry,
                var=self._genre_var,
                manager_getter=lambda: self.manifest_manager,
                meta_key="genre",
                default="",
            )
        )
        
        # Button to open multi-select dialog
        self._genre_btn = ttk.Button(
            row3,
            text="...",
            width=3,
            command=self._open_genre_dialog,
        )
        self._genre_btn.pack(side="left", padx=(5, 0))

        # Enable/Disable toggle for Genre
        self._genre_enabled_var = tk.BooleanVar(value=False)
        self._genre_toggle_btn = ttk.Button(
            row3, text="Disabled", width=8,
            command=self._toggle_genre_enabled,
        )
        self._genre_toggle_btn.pack(side="left", padx=(5, 0))

    def _build_language_section(self) -> None:
        """Build language selection section.
        
        TASK 23.1: Language fields bound to manifest for auto-save/load.
        TASK 41.3: 'Other' selection prompts for custom language name.
        """
        frame = ttk.LabelFrame(self._left_column, text="Languages")
        frame.pack(fill="x", padx=5, pady=5)

        row = ttk.Frame(frame)
        row.pack(fill="x", padx=10, pady=5)

        # Track previous selections for revert on cancel
        self._prev_source_lang = "Japanese"
        self._prev_target_lang = "English"

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
        self._source_lang_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._on_language_change("source"),
        )
        
        # TASK 23.1: Bind to manifest
        self._manifest_bindings.append(
            bind_combobox_to_info_field(
                combobox=self._source_lang_combo,
                var=self._source_lang_var,
                manager_getter=lambda: self.manifest_manager,
                meta_key="source_language",
                default="Japanese",
            )
        )

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
        self._target_lang_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._on_language_change("target"),
        )
        
        # TASK 23.1: Bind to manifest
        self._manifest_bindings.append(
            bind_combobox_to_info_field(
                combobox=self._target_lang_combo,
                var=self._target_lang_var,
                manager_getter=lambda: self.manifest_manager,
                meta_key="target_language",
                default="English",
            )
        )

    def _build_summary_section(self) -> None:
        """Build summary section.
        
        TASK 23.1: Summary field bound to manifest for auto-save/load.
        TASK 41.1: Renamed from 'Summary / Description' to 'Summary'.
        """
        frame = ttk.LabelFrame(self._left_column, text="Summary")
        frame.pack(fill="x", padx=5, pady=5)

        # Summary text area
        self._summary_text = scrolledtext.ScrolledText(
            frame,
            height=2,
            wrap="word",
            font=("Consolas", 10),
        )
        self._summary_text.pack(fill="x", padx=10, pady=5)
        
        # TASK 23.1: Bind to manifest (auto-saves on focus out)
        self._manifest_bindings.append(
            bind_scrolledtext_to_info_field(
                text_widget=self._summary_text,
                manager_getter=lambda: self.manifest_manager,
                meta_key="summary",
                default="",
            )
        )

        # Restore default button + Enable/Disable toggle
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", padx=10, pady=(0, 5))
        self._summary_enabled_var = tk.BooleanVar(value=False)
        self._summary_toggle_btn = ttk.Button(
            btn_row, text="Disabled", width=8,
            command=self._toggle_summary_enabled,
        )
        self._summary_toggle_btn.pack(side="right", padx=(5, 0))
        ttk.Button(
            btn_row, text="🔄 Restore Default", width=16,
            command=self._restore_summary_default,
        ).pack(side="right")

    def _build_style_section(self) -> None:
        """Build style and tone section with preset management.

        Each widget has:
        - A dropdown listing all preset names (Custom always first)
        - A writable Text field showing the prompt text
        - Save and Delete buttons for preset management

        Manifest stores: ``StylePreset`` (name) + ``CustomStyle`` (prompt text),
        ``TonePreset`` (name) + ``CustomTone`` (prompt text).
        """
        frame = ttk.LabelFrame(self._left_column, text="Translation Style & Tone")
        frame.pack(fill="x", padx=5, pady=5)

        # --- Load presets from INI ---
        self._style_presets = ini_manager.get_all_presets("style")
        self._tone_presets = ini_manager.get_all_presets("tone")

        # ---- Style ----
        style_header = ttk.Frame(frame)
        style_header.pack(fill="x", padx=10, pady=(5, 0))

        ttk.Label(style_header, text="Style Preset:").pack(side="left", padx=(0, 5))
        self._style_preset_var = tk.StringVar(value="Natural")
        self._style_preset_combo = ttk.Combobox(
            style_header,
            textvariable=self._style_preset_var,
            values=list(self._style_presets.keys()),
            state="readonly",
            width=18,
        )
        self._style_preset_combo.pack(side="left", padx=(0, 5))
        self._style_preset_combo.bind(
            "<<ComboboxSelected>>", self._on_style_changed,
        )

        # TASK 23.2: Bind preset name to manifest
        self._manifest_bindings.append(
            bind_combobox_to_info_field(
                combobox=self._style_preset_combo,
                var=self._style_preset_var,
                manager_getter=lambda: self.manifest_manager,
                meta_key="style_preset",
                default="Natural",
            )
        )

        ttk.Button(
            style_header, text="💾 Save", width=7,
            command=self._save_style_preset,
        ).pack(side="left", padx=2)
        ttk.Button(
            style_header, text="🗑 Delete", width=10,
            command=self._delete_style_preset,
        ).pack(side="left", padx=2)

        # Enable/Disable toggle for Style
        self._style_enabled_var = tk.BooleanVar(value=False)
        self._style_toggle_btn = ttk.Button(
            style_header, text="Disabled", width=8,
            command=self._toggle_style_enabled,
        )
        self._style_toggle_btn.pack(side="left", padx=(5, 0))

        # Prompt text field (writable) — this is what goes into the prompt
        self._style_var = tk.StringVar()
        self._style_text = scrolledtext.ScrolledText(
            frame, height=1, wrap="word", font=("Consolas", 9),
        )
        self._style_text.pack(fill="x", padx=10, pady=(2, 5))

        # Bind prompt text to manifest (auto-saves on focus out)
        self._manifest_bindings.append(
            bind_scrolledtext_to_info_field(
                text_widget=self._style_text,
                manager_getter=lambda: self.manifest_manager,
                meta_key="custom_style",
                default="",
            )
        )

        # Populate on first build
        self._on_style_changed()

        # ---- Separator ----
        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=10, pady=3)

        # ---- Tone ----
        tone_header = ttk.Frame(frame)
        tone_header.pack(fill="x", padx=10, pady=(5, 0))

        ttk.Label(tone_header, text="Tone Preset:").pack(side="left", padx=(0, 5))
        self._tone_preset_var = tk.StringVar(value="Neutral")
        self._tone_preset_combo = ttk.Combobox(
            tone_header,
            textvariable=self._tone_preset_var,
            values=list(self._tone_presets.keys()),
            state="readonly",
            width=18,
        )
        self._tone_preset_combo.pack(side="left", padx=(0, 5))
        self._tone_preset_combo.bind(
            "<<ComboboxSelected>>", self._on_tone_changed,
        )

        # TASK 23.2: Bind preset name to manifest
        self._manifest_bindings.append(
            bind_combobox_to_info_field(
                combobox=self._tone_preset_combo,
                var=self._tone_preset_var,
                manager_getter=lambda: self.manifest_manager,
                meta_key="tone_preset",
                default="Neutral",
            )
        )

        ttk.Button(
            tone_header, text="💾 Save", width=7,
            command=self._save_tone_preset,
        ).pack(side="left", padx=2)
        ttk.Button(
            tone_header, text="🗑 Delete", width=10,
            command=self._delete_tone_preset,
        ).pack(side="left", padx=2)

        # Enable/Disable toggle for Tone
        self._tone_enabled_var = tk.BooleanVar(value=False)
        self._tone_toggle_btn = ttk.Button(
            tone_header, text="Disabled", width=8,
            command=self._toggle_tone_enabled,
        )
        self._tone_toggle_btn.pack(side="left", padx=(5, 0))

        # Prompt text field (writable)
        self._tone_var = tk.StringVar()
        self._tone_text = scrolledtext.ScrolledText(
            frame, height=1, wrap="word", font=("Consolas", 9),
        )
        self._tone_text.pack(fill="x", padx=10, pady=(2, 5))

        # Bind prompt text to manifest
        self._manifest_bindings.append(
            bind_scrolledtext_to_info_field(
                text_widget=self._tone_text,
                manager_getter=lambda: self.manifest_manager,
                meta_key="custom_tone",
                default="",
            )
        )

        # Populate on first build
        self._on_tone_changed()

    def _build_character_section(self) -> None:
        """Build Glossary section (character glossary for the project).

        Placed in right column (row 0) with collapse/expand support.
        Table expands vertically to fill available space.
        """
        self._glossary_enabled_var = tk.BooleanVar(value=True)

        def _add_glossary_enabled_btn(header: ttk.Frame) -> None:
            """Pack the Enabled/Disabled toggle into the header bar."""
            self._glossary_toggle_btn = ttk.Button(
                header, text="Enabled", width=8,
                command=self._toggle_glossary_enabled,
            )
            self._glossary_toggle_btn.pack(side="left", padx=(8, 0))

        content = self._build_collapsible_labelframe(
            self._right_column, "Glossary", "glossary", row=0,
            extra_header_widgets=_add_glossary_enabled_btn,
        )
        content.rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ttk.Frame(content)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        ttk.Button(
            toolbar,
            text="+Add",
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

        # Infer Gender button
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

        # Character list (expanded table)
        list_frame = ttk.Frame(content)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        # Column order: Original, Translation, Notes
        columns = ("original", "translation", "notes")
        self._char_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=8,
            selectmode="extended",
        )
        self._char_tree.heading("original", text="Original")
        self._char_tree.heading("translation", text="Translation")
        self._char_tree.heading("notes", text="Notes")

        self._char_tree.column("original", width=120)
        self._char_tree.column("translation", width=120)
        self._char_tree.column("notes", width=230)

        char_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self._char_tree.yview,
        )
        self._char_tree.configure(yscrollcommand=char_scroll.set)

        self._char_tree.grid(row=0, column=0, sticky="nsew")
        char_scroll.grid(row=0, column=1, sticky="ns")

        # Bind double-click for inline editing
        self._char_tree.bind("<Double-1>", self._on_char_double_click)
        # Bind Delete key for row removal
        self._char_tree.bind("<Delete>", lambda e: self._remove_character())
        # Bind right-click for context menu
        self._char_tree.bind("<Button-3>", self._on_char_context_menu)

    def _build_glossary_settings_section(self) -> None:
        """Build Glossary Settings section (TASK 19 Phase 4).

        TASK 41.5: Added editable 3-column Treeview for project glossary
        entries with inline editing, Add/Remove buttons.
        Placed in right column (row 1) with collapse/expand support.
        Table expands vertically to fill available space.
        """
        content = self._build_collapsible_labelframe(
            self._right_column, "Glossary Settings", "glossary_settings",
            row=1,
        )
        content.rowconfigure(2, weight=1)  # table row expands

        # Use Global Glossary checkbox
        self._use_global_glossary_var = tk.BooleanVar(value=True)
        use_global_cb = ttk.Checkbutton(
            content,
            text="Use Global Glossary (user/GlobalGlossary.csv)",
            variable=self._use_global_glossary_var,
            command=self._on_use_global_glossary_changed,
        )
        use_global_cb.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Info text
        self._glossary_info_label = ttk.Label(
            content,
            text="Global glossary entries will be applied during translation.",
            font=("Segoe UI", 8),
            foreground="gray",
        )
        self._glossary_info_label.grid(
            row=0, column=0, sticky="w", padx=10, pady=(25, 0),
        )

        # Button row
        btn_frame = ttk.Frame(content)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))

        # Copy from Global button
        ttk.Button(
            btn_frame,
            text="↓ Copy from Global",
            command=self._on_copy_from_global_glossary,
        ).pack(side="left")

        # Import from Analysis (speakers)
        ttk.Button(
            btn_frame,
            text="↓ Import from Analysis",
            command=self._on_import_glossary_from_analysis,
        ).pack(side="left", padx=5)

        # Project glossary count
        self._project_glossary_count_var = tk.StringVar(value="Project entries: 0")
        ttk.Label(
            btn_frame,
            textvariable=self._project_glossary_count_var,
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(side="right")

        # Editable glossary entries table with Active column
        table_frame = ttk.Frame(content)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 5))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        gloss_cols = ("active", "original", "translation", "notes")
        self._glossary_tree = ttk.Treeview(
            table_frame,
            columns=gloss_cols,
            show="headings",
            height=8,
        )
        self._glossary_tree.heading("active", text="Active")
        self._glossary_tree.heading("original", text="Original")
        self._glossary_tree.heading("translation", text="Translation")
        self._glossary_tree.heading("notes", text="Notes")

        self._glossary_tree.column("active", width=45, anchor="center")
        self._glossary_tree.column("original", width=105)
        self._glossary_tree.column("translation", width=105)
        self._glossary_tree.column("notes", width=105)

        gloss_scroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self._glossary_tree.yview,
        )
        self._glossary_tree.configure(yscrollcommand=gloss_scroll.set)

        self._glossary_tree.grid(row=0, column=0, sticky="nsew")
        gloss_scroll.grid(row=0, column=1, sticky="ns")

        # Inline editing on double-click
        self._glossary_tree.bind(
            "<Double-1>", self._on_glossary_double_click
        )
        # TASK 41.10: Single click toggles Active column
        self._glossary_tree.bind(
            "<Button-1>", self._on_glossary_click
        )
        self._glossary_tree.bind(
            "<Delete>", lambda _e: self._remove_glossary_entry()
        )

        # Add / Remove buttons for glossary entries
        gloss_btn_frame = ttk.Frame(content)
        gloss_btn_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))

        ttk.Button(
            gloss_btn_frame,
            text="+Add",
            command=self._add_glossary_entry,
        ).pack(side="left")

        ttk.Button(
            gloss_btn_frame,
            text="Remove",
            command=self._remove_glossary_entry,
        ).pack(side="left", padx=5)

    def _build_code_glossary_section(self) -> None:
        """Build Code Database section in right column (TASK 18.5).

        TASK 41.1: Renamed from 'Code Glossary' to 'Code Database'.
        Placed in right column (row 1) with collapse/expand support.
        Table expands vertically to fill available space.
        """
        self._code_db_enabled_var = tk.BooleanVar(value=True)

        def _add_code_db_enabled_btn(header: ttk.Frame) -> None:
            """Pack the Enabled/Disabled toggle into the header bar."""
            self._code_db_toggle_btn = ttk.Button(
                header, text="Enabled", width=8,
                command=self._toggle_code_db_enabled,
            )
            self._code_db_toggle_btn.pack(side="left", padx=(8, 0))

        content = self._build_collapsible_labelframe(
            self._right_column, "Code Database", "code_database", row=1,
            extra_header_widgets=_add_code_db_enabled_btn,
        )
        content.rowconfigure(1, weight=1)  # table row expands

        # Toolbar
        toolbar = ttk.Frame(content)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        ttk.Button(
            toolbar,
            text="+Add",
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

        # Code pattern list (expanded table)
        list_frame = ttk.Frame(content)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        columns = ("pattern", "translation", "category", "action")
        self._code_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=8,
            selectmode="extended",
        )
        self._code_tree.heading("pattern", text="Pattern")
        self._code_tree.heading("translation", text="Translation")
        self._code_tree.heading("category", text="Category")
        self._code_tree.heading("action", text="Action")

        self._code_tree.column("pattern", width=130)
        self._code_tree.column("translation", width=110)
        self._code_tree.column("category", width=90)
        self._code_tree.column("action", width=70)

        code_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self._code_tree.yview,
        )
        self._code_tree.configure(yscrollcommand=code_scroll.set)

        self._code_tree.grid(row=0, column=0, sticky="nsew")
        code_scroll.grid(row=0, column=1, sticky="ns")

        # Bind double-click for inline editing
        self._code_tree.bind("<Double-1>", self._on_code_double_click)
        # Bind Delete key for row removal
        self._code_tree.bind("<Delete>", lambda e: self._remove_code_pattern())

        # Instance expansion state for code database
        self._code_expanded: set = set()

        # Hint
        ttk.Label(
            content,
            text=(
                "Code patterns to preserve during translation.\n"
                "Temporary Replacement and Removal options are in "
                "Preprocessing → Custom Placeholders."
            ),
            font=("Segoe UI", 8),
            foreground="gray",
            wraplength=350,
            justify="left",
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 5))

    def _build_global_database_section(self) -> None:
        """Build Global Glossary and Database widget (TASK 41.9).

        Placed in right column (row 3) with collapse/expand support.
        Table expands vertically to fill available space.
        """
        content = self._build_collapsible_labelframe(
            self._right_column, "Global Glossary and Database",
            "global_database", row=3,
        )
        content.rowconfigure(1, weight=1)  # table row expands

        # Top row: Mode switch, search, import/export
        top_row = ttk.Frame(content)
        top_row.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        ttk.Label(top_row, text="Mode:").pack(side="left", padx=(0, 5))
        self._global_db_mode_var = tk.StringVar(value="Glossary")
        mode_combo = ttk.Combobox(
            top_row,
            textvariable=self._global_db_mode_var,
            values=["Glossary", "Code Database"],
            state="readonly",
            width=14,
        )
        mode_combo.pack(side="left", padx=(0, 10))
        mode_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._refresh_global_database(),
        )

        ttk.Label(top_row, text="Search:").pack(side="left", padx=(0, 5))
        self._global_db_search_var = tk.StringVar()
        search_entry = ttk.Entry(
            top_row, textvariable=self._global_db_search_var, width=14,
        )
        search_entry.pack(side="left", padx=(0, 10))
        self._global_db_search_var.trace_add(
            "write", lambda *_a: self._refresh_global_database()
        )

        ttk.Button(
            top_row, text="Import", command=self._import_global_database,
        ).pack(side="right", padx=2)
        ttk.Button(
            top_row, text="Export", command=self._export_global_database,
        ).pack(side="right", padx=2)

        # Treeview (expanded table)
        table_frame = ttk.Frame(content)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 5))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        gdb_cols = ("col1", "col2", "col3")
        self._global_db_tree = ttk.Treeview(
            table_frame, columns=gdb_cols, show="headings", height=8,
        )
        self._global_db_tree.heading("col1", text="Original")
        self._global_db_tree.heading("col2", text="Translation")
        self._global_db_tree.heading("col3", text="Notes")
        self._global_db_tree.column("col1", width=110)
        self._global_db_tree.column("col2", width=110)
        self._global_db_tree.column("col3", width=110)

        gdb_scroll = ttk.Scrollbar(
            table_frame, orient="vertical",
            command=self._global_db_tree.yview,
        )
        self._global_db_tree.configure(yscrollcommand=gdb_scroll.set)
        self._global_db_tree.grid(row=0, column=0, sticky="nsew")
        gdb_scroll.grid(row=0, column=1, sticky="ns")

        self._global_db_tree.bind(
            "<Double-1>", self._on_global_db_double_click,
        )
        self._global_db_tree.bind(
            "<Delete>", lambda _e: self._remove_global_db_entry(),
        )

        # Button row
        btn_row = ttk.Frame(content)
        btn_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))

        ttk.Button(
            btn_row, text="+Add",
            command=self._add_global_db_entry,
        ).pack(side="left")
        ttk.Button(
            btn_row, text="Remove",
            command=self._remove_global_db_entry,
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_row, text="Clear All",
            command=self._clear_global_database,
        ).pack(side="left")

    def _build_knowledge_base_section(self) -> None:
        """Build Knowledge Base widget (replaces Glossary Settings + Global Database).

        Manages global glossary (globalglossary.tsv) and global code database
        (codedatabase.tsv) with Active/Inactive per-entry state stored in TSV.

        Layout:
            Header: Collapse ▾ — Knowledge Base — Enabled|Disabled — separator
            Row 0: Mode dropdown — Search entry — Column Filter dropdown
            Row 1: Treeview table (flexible, mode-dependent columns)
            Row 2: +Add — Remove — Activate|Deactivate
            Row 3: Copy {Glossary|Code} from Project to Global

        Placed in right column (row 2) with collapse/expand support.
        """
        # State variables
        self._kb_enabled_var = tk.BooleanVar(value=True)
        self._kb_mode_var = tk.StringVar(value="Glossary")
        self._kb_search_var = tk.StringVar()
        self._kb_col_filter_var = tk.StringVar(value="Default")

        def _add_enabled_btn(header: ttk.Frame) -> None:
            """Pack the Enabled/Disabled toggle into the header bar."""
            self._kb_enabled_btn = ttk.Button(
                header, text="Enabled", width=8,
                command=self._toggle_kb_enabled,
            )
            self._kb_enabled_btn.pack(side="left", padx=(8, 0))

        content = self._build_collapsible_labelframe(
            self._right_column, "Knowledge Base", "knowledge_base",
            row=2, extra_header_widgets=_add_enabled_btn,
        )
        content.rowconfigure(1, weight=1)   # table expands

        # --- Row 0: Mode + Search + Column Filter ---
        top_row = ttk.Frame(content)
        top_row.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        ttk.Label(top_row, text="Mode:").pack(side="left", padx=(0, 3))
        mode_combo = ttk.Combobox(
            top_row, textvariable=self._kb_mode_var,
            values=["Glossary", "Code Database"],
            state="readonly", width=13,
        )
        mode_combo.pack(side="left", padx=(0, 8))
        mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_kb())

        ttk.Label(top_row, text="Search:").pack(side="left", padx=(0, 3))
        search_entry = ttk.Entry(
            top_row, textvariable=self._kb_search_var, width=12,
        )
        search_entry.pack(side="left", padx=(0, 8))
        self._kb_search_var.trace_add("write", lambda *_a: self._refresh_kb())

        ttk.Label(top_row, text="Columns:").pack(side="left", padx=(0, 3))
        self._kb_col_combo = ttk.Combobox(
            top_row, textvariable=self._kb_col_filter_var,
            values=["Default", "All", "Active Only"],
            state="readonly", width=10,
        )
        self._kb_col_combo.pack(side="left")
        self._kb_col_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._refresh_kb(),
        )

        # --- Row 1: Treeview ---
        table_frame = ttk.Frame(content)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 5))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Glossary default columns
        kb_cols = ("active", "original", "translation", "notes")
        self._kb_tree = ttk.Treeview(
            table_frame, columns=kb_cols, show="headings", height=8,
            selectmode="extended",
        )
        self._kb_tree.heading("active", text="Active")
        self._kb_tree.heading("original", text="Original")
        self._kb_tree.heading("translation", text="Translation")
        self._kb_tree.heading("notes", text="Notes")

        self._kb_tree.column("active", width=45, anchor="center")
        self._kb_tree.column("original", width=100)
        self._kb_tree.column("translation", width=100)
        self._kb_tree.column("notes", width=100)

        kb_scroll = ttk.Scrollbar(
            table_frame, orient="vertical", command=self._kb_tree.yview,
        )
        self._kb_tree.configure(yscrollcommand=kb_scroll.set)
        self._kb_tree.grid(row=0, column=0, sticky="nsew")
        kb_scroll.grid(row=0, column=1, sticky="ns")

        # Bindings
        self._kb_tree.bind("<Button-1>", self._on_kb_click)
        self._kb_tree.bind("<Double-1>", self._on_kb_double_click)
        self._kb_tree.bind("<Delete>", lambda _e: self._remove_kb_entry())

        # Entry count label
        self._kb_count_var = tk.StringVar(value="Entries: 0")
        ttk.Label(
            content, textvariable=self._kb_count_var,
            font=("Segoe UI", 8), foreground="gray",
        ).grid(row=1, column=0, sticky="se", padx=20, pady=0)

        # --- Row 2: +Add / Remove / Activate|Deactivate ---
        btn_row = ttk.Frame(content)
        btn_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 3))

        ttk.Button(
            btn_row, text="+Add", command=self._add_kb_entry,
        ).pack(side="left")
        ttk.Button(
            btn_row, text="Remove", command=self._remove_kb_entry,
        ).pack(side="left", padx=5)

        self._kb_activate_btn = ttk.Button(
            btn_row, text="Activate", command=self._toggle_kb_active,
        )
        self._kb_activate_btn.pack(side="left", padx=5)

        # --- Row 3: Copy to Global ---
        copy_row = ttk.Frame(content)
        copy_row.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))

        self._kb_copy_btn = ttk.Button(
            copy_row, text="Copy Glossary from Project to Global",
            command=self._copy_project_to_global,
        )
        self._kb_copy_btn.pack(side="left")

        # Initial load
        self._refresh_kb()

    # ------------------------------------------------------------------
    # Knowledge Base helpers
    # ------------------------------------------------------------------

    def _toggle_kb_enabled(self) -> None:
        """Toggle the Enabled/Disabled state of the Knowledge Base.

        Controls whether global databases are used in API request building.
        Persists the setting via ManifestManager.set_use_global_glossary().
        When disabled, collapses the section and disables the collapse button.
        """
        enabled = not self._kb_enabled_var.get()
        self._kb_enabled_var.set(enabled)
        self._kb_enabled_btn.config(text="Enabled" if enabled else "Disabled")

        # When disabled, collapse and disable collapse button
        collapse_btn = self._collapsible_buttons.get("knowledge_base")
        if enabled:
            if collapse_btn:
                collapse_btn.configure(state="normal")
        else:
            if self._collapsible_state.get("knowledge_base", True):
                self._toggle_collapsible("knowledge_base")
            if collapse_btn:
                collapse_btn.configure(state="disabled")

        # Persist to manifest
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.set_use_global_glossary(enabled)
        logger.debug("Knowledge Base enabled: %s", enabled)

    # ------------------------------------------------------------------
    # Section toggle helpers
    # ------------------------------------------------------------------

    def _toggle_section_enabled(
        self,
        var: tk.BooleanVar,
        btn: ttk.Button,
        meta_key: str,
        widgets: Optional[list] = None,
    ) -> None:
        """Generic toggle handler for section enable/disable.

        Updates the BooleanVar, button text, persists to manifest, and
        optionally greys out associated widgets.

        Args:
            var: The BooleanVar tracking the toggle state.
            btn: The toggle button widget.
            meta_key: Manifest metadata key (e.g. ``genre_enabled``).
            widgets: Optional list of widgets to enable/disable visually.
        """
        enabled = not var.get()
        var.set(enabled)
        btn.config(text="Enabled" if enabled else "Disabled")

        # Grey out / restore associated widgets
        if widgets:
            state = "normal" if enabled else "disabled"
            for w in widgets:
                try:
                    w.configure(state=state)
                except tk.TclError:
                    pass

        # Persist to manifest
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.set_info_metadata_field(meta_key, enabled)
        logger.debug("Section %s enabled: %s", meta_key, enabled)

    def _toggle_genre_enabled(self) -> None:
        """Toggle Genre section enabled/disabled."""
        self._toggle_section_enabled(
            self._genre_enabled_var,
            self._genre_toggle_btn,
            "genre_enabled",
            widgets=[self._genre_entry, self._genre_btn],
        )

    def _toggle_summary_enabled(self) -> None:
        """Toggle Summary section enabled/disabled."""
        self._toggle_section_enabled(
            self._summary_enabled_var,
            self._summary_toggle_btn,
            "summary_enabled",
            widgets=[self._summary_text],
        )

    def _toggle_style_enabled(self) -> None:
        """Toggle Style section enabled/disabled."""
        self._toggle_section_enabled(
            self._style_enabled_var,
            self._style_toggle_btn,
            "style_enabled",
            widgets=[self._style_text, self._style_preset_combo],
        )

    def _toggle_tone_enabled(self) -> None:
        """Toggle Tone section enabled/disabled."""
        self._toggle_section_enabled(
            self._tone_enabled_var,
            self._tone_toggle_btn,
            "tone_enabled",
            widgets=[self._tone_text, self._tone_preset_combo],
        )

    def _toggle_si_enabled(self) -> None:
        """Toggle System Instructions section enabled/disabled."""
        self._toggle_section_enabled(
            self._si_enabled_var,
            self._si_toggle_btn,
            "system_instructions_enabled",
            widgets=[self._notes_text, self._si_preset_combo],
        )

    def _toggle_glossary_enabled(self) -> None:
        """Toggle Glossary section enabled/disabled.

        When disabled, collapses the section and disables the collapse button.
        """
        enabled = not self._glossary_enabled_var.get()
        self._glossary_enabled_var.set(enabled)
        self._glossary_toggle_btn.config(
            text="Enabled" if enabled else "Disabled",
        )

        # When disabled, collapse and disable collapse button
        collapse_btn = self._collapsible_buttons.get("glossary")
        if enabled:
            if collapse_btn:
                collapse_btn.configure(state="normal")
        else:
            if self._collapsible_state.get("glossary", True):
                self._toggle_collapsible("glossary")
            if collapse_btn:
                collapse_btn.configure(state="disabled")

        # Persist to manifest
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.set_info_metadata_field("glossary_enabled", enabled)
        logger.debug("Glossary enabled: %s", enabled)

    def _toggle_code_db_enabled(self) -> None:
        """Toggle Code Database section enabled/disabled.

        When disabled, collapses the section and disables the collapse button.
        """
        enabled = not self._code_db_enabled_var.get()
        self._code_db_enabled_var.set(enabled)
        self._code_db_toggle_btn.config(
            text="Enabled" if enabled else "Disabled",
        )

        # When disabled, collapse and disable collapse button
        collapse_btn = self._collapsible_buttons.get("code_database")
        if enabled:
            if collapse_btn:
                collapse_btn.configure(state="normal")
        else:
            if self._collapsible_state.get("code_database", True):
                self._toggle_collapsible("code_database")
            if collapse_btn:
                collapse_btn.configure(state="disabled")

        # Persist to manifest
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            mgr.set_info_metadata_field("code_database_enabled", enabled)
        logger.debug("Code Database enabled: %s", enabled)

    def _refresh_kb(self) -> None:
        """Reload the Knowledge Base treeview based on current mode and search."""
        for child in self._kb_tree.get_children():
            self._kb_tree.delete(child)

        mode = self._kb_mode_var.get()
        search = self._kb_search_var.get().strip().lower()
        col_filter = self._kb_col_filter_var.get()

        # Update Copy button text
        label = "Glossary" if mode == "Glossary" else "Code"
        self._kb_copy_btn.config(text=f"Copy {label} from Project to Global")

        # Configure columns based on mode and filter
        self._configure_kb_columns(mode, col_filter)

        # Load entries
        entries = self._load_kb_entries(mode)
        count = 0
        for entry in entries:
            if search:
                combined = " ".join(str(v) for v in entry.values()).lower()
                if search not in combined:
                    continue
            active_str = entry.get("active", "true")
            is_active = str(active_str).lower() != "false"

            if col_filter == "Active Only" and not is_active:
                continue

            active_display = "✓" if is_active else "✗"

            if mode == "Code Database":
                vals = (
                    active_display,
                    entry.get("pattern", ""),
                    entry.get("translation", entry.get("type", "")),
                    entry.get("notes", ""),
                )
            else:
                vals = (
                    active_display,
                    entry.get("original", ""),
                    entry.get("translation", ""),
                    entry.get("notes", ""),
                )
            self._kb_tree.insert("", "end", values=vals)
            count += 1

        self._kb_count_var.set(f"Entries: {count}")

    def _configure_kb_columns(self, mode: str, col_filter: str) -> None:
        """Reconfigure Treeview columns for the current mode/filter."""
        if mode == "Code Database":
            self._kb_tree.heading("original", text="Pattern")
            self._kb_tree.heading("translation", text="Translation")
            self._kb_tree.heading("notes", text="Notes")
        else:
            self._kb_tree.heading("original", text="Original")
            self._kb_tree.heading("translation", text="Translation")
            self._kb_tree.heading("notes", text="Notes")

        # Show/hide columns based on filter
        if col_filter == "All":
            self._kb_tree["displaycolumns"] = ("active", "original",
                                                "translation", "notes")
        elif col_filter == "Active Only":
            self._kb_tree["displaycolumns"] = ("active", "original",
                                                "translation", "notes")
        else:  # Default
            self._kb_tree["displaycolumns"] = ("active", "original",
                                                "translation")

    def _load_kb_entries(self, mode: str) -> List[Dict[str, str]]:
        """Load entries from the global TSV file for Knowledge Base display.

        Args:
            mode: ``"Glossary"`` or ``"Code Database"``.

        Returns:
            List of dicts with keys: original/pattern, translation/type,
            notes, active.
        """
        try:
            if mode == "Code Database":
                from CherryAI.functions.glossaries import code_glossary_db
                rows = code_glossary_db.read_all_rows_extended()
                return [
                    {
                        "pattern": r[0] if len(r) > 0 else "",
                        "category": r[2] if len(r) > 2 else "",
                        "translation": r[1] if len(r) > 1 else "",
                        "notes": r[4] if len(r) > 4 else "",
                        "active": r[10] if len(r) > 10 else "true",
                    }
                    for r in rows
                ]
            else:
                from CherryAI.functions.glossary import read_unified_glossary
                glossary = read_unified_glossary()
                return [
                    {
                        "original": e.original,
                        "translation": e.translation,
                        "notes": e.notes,
                        "active": "true" if e.active else "false",
                    }
                    for e in glossary.values()
                ]
        except Exception as exc:
            logger.warning("Failed to load KB entries (%s): %s", mode, exc)
            return []

    def _save_kb_entries(self) -> None:
        """Persist current KB Treeview contents to the global TSV file."""
        mode = self._kb_mode_var.get()
        try:
            if mode == "Code Database":
                from CherryAI.functions.glossaries import code_glossary_db
                # Read full extended rows, update active flag
                all_rows = code_glossary_db.read_all_rows_extended()
                # Build pattern → active map from tree
                active_map: Dict[str, bool] = {}
                for child in self._kb_tree.get_children():
                    vals = self._kb_tree.item(child, "values")
                    pattern = vals[1] if len(vals) > 1 else ""
                    is_active = (vals[0] == "✓") if vals else True
                    if pattern:
                        active_map[pattern] = is_active

                # Update rows
                updated: List[List[str]] = []
                for row in all_rows:
                    row = list(row)
                    while len(row) < 11:
                        row.append("")
                    pattern = row[0]
                    if pattern in active_map:
                        row[10] = "true" if active_map[pattern] else "false"
                    updated.append(row)

                # Also add new entries that aren't in the original
                existing = {r[0] for r in all_rows}
                for child in self._kb_tree.get_children():
                    vals = self._kb_tree.item(child, "values")
                    pattern = vals[1] if len(vals) > 1 else ""
                    if pattern and pattern not in existing:
                        is_active = (vals[0] == "✓") if vals else True
                        translation = vals[2] if len(vals) > 2 else ""
                        notes = vals[3] if len(vals) > 3 else ""
                        new_row = [""] * 11
                        new_row[0] = pattern
                        new_row[1] = translation
                        new_row[10] = "true" if is_active else "false"
                        updated.append(new_row)

                code_glossary_db.write_all_rows(updated)
            else:
                from CherryAI.functions.glossary import (
                    read_unified_glossary,
                    write_unified_glossary,
                    GlossaryEntry,
                )
                existing = read_unified_glossary()
                new_glossary: dict[str, GlossaryEntry] = {}
                for child in self._kb_tree.get_children():
                    vals = self._kb_tree.item(child, "values")
                    is_active = (vals[0] == "✓") if vals else True
                    original = vals[1] if len(vals) > 1 else ""
                    translation = vals[2] if len(vals) > 2 else ""
                    notes = vals[3] if len(vals) > 3 else ""
                    if not original.strip():
                        continue
                    if original in existing:
                        e = existing[original]
                        e.translation = translation
                        e.notes = notes
                        e.active = is_active
                        new_glossary[original] = e
                    else:
                        new_glossary[original] = GlossaryEntry(
                            original=original,
                            translation=translation,
                            notes=notes,
                            active=is_active,
                        )
                write_unified_glossary(new_glossary)
        except Exception as exc:
            logger.error("Failed to save KB entries (%s): %s", mode, exc)

    def _add_kb_entry(self) -> None:
        """Add a blank entry to the Knowledge Base."""
        self._kb_tree.insert("", "end", values=("✓", "", "", ""))
        children = self._kb_tree.get_children()
        if children:
            last = children[-1]
            self._kb_tree.selection_set(last)
            self._kb_tree.see(last)
        self._save_kb_entries()
        self._refresh_kb()

    def _remove_kb_entry(self) -> None:
        """Remove selected entries from the Knowledge Base."""
        selection = self._kb_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select entries to remove.")
            return
        count = len(selection)
        msg = f"Remove {count} selected entries?" if count > 1 else "Remove selected entry?"
        if not confirm_action(self, "remove_kb_entry", "Confirm", msg):
            return
        for item in selection:
            self._kb_tree.delete(item)
        self._save_kb_entries()
        self._refresh_kb()

    def _on_kb_click(self, event: tk.Event) -> None:
        """Handle single click in KB treeview (toggle Active column).

        Also updates the Activate/Deactivate button text based on selection.
        """
        region = self._kb_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self._kb_tree.identify_column(event.x)
            item = self._kb_tree.identify_row(event.y)
            if item:
                col_idx = int(column.replace("#", "")) - 1
                if col_idx == 0:  # Active column
                    vals = list(self._kb_tree.item(item, "values"))
                    vals[0] = "✗" if vals[0] == "✓" else "✓"
                    self._kb_tree.item(item, values=vals)
                    self._save_kb_entries()

        # Schedule button text update after click processes
        self.after(50, self._update_kb_activate_btn)

    def _on_kb_double_click(self, event: tk.Event) -> None:
        """Handle double-click for inline editing in KB treeview.

        Skips Active column (col 0) — toggled by single click.
        """
        region = self._kb_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self._kb_tree.identify_column(event.x)
        item = self._kb_tree.identify_row(event.y)
        if not item:
            return
        col_idx = int(column.replace("#", "")) - 1
        if col_idx <= 0:
            return  # Skip Active column

        col_keys = ("active", "original", "translation", "notes")
        if col_idx >= len(col_keys):
            return

        mode = self._kb_mode_var.get()
        # For Code Database, column 2 is "Type" but same edit behavior
        self._start_kb_inline_edit(item, col_keys[col_idx], col_idx, mode)

    def _start_kb_inline_edit(
        self, item: str, col_key: str, col_idx: int, mode: str,
    ) -> None:
        """Start inline editing of a Knowledge Base cell.

        For Code Database Type/Action columns, uses a dropdown.
        For everything else, uses a text entry.
        """
        columns = ("active", "original", "translation", "notes")
        try:
            bbox = self._kb_tree.bbox(item, columns[col_idx])
            if not bbox:
                return
        except tk.TclError:
            return

        x, y, width, height = bbox
        current_values = self._kb_tree.item(item, "values")
        current = current_values[col_idx] if col_idx < len(current_values) else ""

        # For code db Type column, show dropdown
        if mode == "Code Database" and col_key == "translation":
            options = ["code", "variable", "control", "tag", "markup", "other"]
            combo = ttk.Combobox(self._kb_tree, values=options, state="readonly")
            combo.set(current)
            combo.place(x=x, y=y, width=width, height=height)
            combo.focus_set()

            def on_select(event: Optional[tk.Event] = None) -> None:
                new_val = combo.get()
                combo.destroy()
                if new_val != current:
                    vals = list(self._kb_tree.item(item, "values"))
                    while len(vals) <= col_idx:
                        vals.append("")
                    vals[col_idx] = new_val
                    self._kb_tree.item(item, values=vals)
                    self._save_kb_entries()

            combo.bind("<<ComboboxSelected>>", on_select)
            combo.bind("<Return>", on_select)
            combo.bind("<Escape>", lambda _: combo.destroy())
            combo.bind("<FocusOut>", on_select)
            return

        entry = ttk.Entry(self._kb_tree)
        entry.insert(0, str(current))
        entry.select_range(0, "end")
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()

        def on_confirm(event: Optional[tk.Event] = None) -> None:
            new_value = entry.get()
            entry.destroy()
            if new_value != str(current):
                vals = list(self._kb_tree.item(item, "values"))
                while len(vals) <= col_idx:
                    vals.append("")
                vals[col_idx] = new_value
                self._kb_tree.item(item, values=vals)
                self._save_kb_entries()

        def on_cancel(event: Optional[tk.Event] = None) -> None:
            entry.destroy()

        entry.bind("<Return>", on_confirm)
        entry.bind("<Tab>", on_confirm)
        entry.bind("<Escape>", on_cancel)
        entry.bind("<FocusOut>", on_confirm)

    def _update_kb_activate_btn(self) -> None:
        """Update the Activate/Deactivate button text based on selection."""
        selection = self._kb_tree.selection()
        if not selection:
            self._kb_activate_btn.config(text="Activate")
            return

        has_active = False
        has_inactive = False
        for item in selection:
            vals = self._kb_tree.item(item, "values")
            if vals and vals[0] == "✓":
                has_active = True
            else:
                has_inactive = True

        if has_active and has_inactive:
            self._kb_activate_btn.config(text="Activate | Deactivate")
        elif has_active:
            self._kb_activate_btn.config(text="Deactivate")
        else:
            self._kb_activate_btn.config(text="Activate")

    def _toggle_kb_active(self) -> None:
        """Toggle Active state for selected KB entries.

        When selection contains both active and inactive entries,
        shows a popup with Activate All / Deactivate All / Invert / Cancel.
        """
        selection = self._kb_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select entries first.")
            return

        # Check if Enabled is on
        if not self._kb_enabled_var.get():
            messagebox.showinfo(
                "Disabled",
                "Knowledge Base is disabled. Enable it first.",
            )
            return

        has_active = False
        has_inactive = False
        for item in selection:
            vals = self._kb_tree.item(item, "values")
            if vals and vals[0] == "✓":
                has_active = True
            else:
                has_inactive = True

        if has_active and has_inactive:
            # Mixed selection — show popup
            self._show_mixed_activate_popup(selection)
        elif has_active:
            # All active → deactivate
            for item in selection:
                vals = list(self._kb_tree.item(item, "values"))
                vals[0] = "✗"
                self._kb_tree.item(item, values=vals)
            self._save_kb_entries()
        else:
            # All inactive → activate
            for item in selection:
                vals = list(self._kb_tree.item(item, "values"))
                vals[0] = "✓"
                self._kb_tree.item(item, values=vals)
            self._save_kb_entries()

        self._update_kb_activate_btn()

    def _show_mixed_activate_popup(self, selection: tuple) -> None:
        """Show popup for mixed active/inactive selection.

        Four buttons: Activate All, Deactivate All, Invert Selection, Cancel.
        """
        popup = tk.Toplevel(self)
        popup.title("Activate / Deactivate")
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

        ttk.Label(
            popup,
            text="Selection contains both active and inactive entries.",
            wraplength=280,
        ).pack(padx=15, pady=(10, 5))

        btn_frame = ttk.Frame(popup, padding=10)
        btn_frame.pack(fill="x")

        def activate_all() -> None:
            for item in selection:
                vals = list(self._kb_tree.item(item, "values"))
                vals[0] = "✓"
                self._kb_tree.item(item, values=vals)
            self._save_kb_entries()
            popup.destroy()
            self._update_kb_activate_btn()

        def deactivate_all() -> None:
            for item in selection:
                vals = list(self._kb_tree.item(item, "values"))
                vals[0] = "✗"
                self._kb_tree.item(item, values=vals)
            self._save_kb_entries()
            popup.destroy()
            self._update_kb_activate_btn()

        def invert() -> None:
            for item in selection:
                vals = list(self._kb_tree.item(item, "values"))
                vals[0] = "✗" if vals[0] == "✓" else "✓"
                self._kb_tree.item(item, values=vals)
            self._save_kb_entries()
            popup.destroy()
            self._update_kb_activate_btn()

        ttk.Button(btn_frame, text="Activate All", command=activate_all).pack(
            side="left", padx=3,
        )
        ttk.Button(btn_frame, text="Deactivate All", command=deactivate_all).pack(
            side="left", padx=3,
        )
        ttk.Button(btn_frame, text="Invert", command=invert).pack(
            side="left", padx=3,
        )
        ttk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(
            side="left", padx=3,
        )

        # Center popup
        popup.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - popup.winfo_width()) // 2
        py = self.winfo_rooty() + (self.winfo_height() - popup.winfo_height()) // 2
        popup.geometry(f"+{max(px, 0)}+{max(py, 0)}")

    def _copy_project_to_global(self) -> None:
        """Copy project glossary/code data to the global TSV database.

        Writes manifest characters (original_name, translation, notes) to
        globalglossary.tsv, or manifest code_patterns to codedatabase.tsv,
        depending on current mode.
        """
        mode = self._kb_mode_var.get()
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            messagebox.showwarning(
                "No Project",
                "Load or create a project first.",
            )
            return

        try:
            if mode == "Code Database":
                from CherryAI.functions.glossaries import code_glossary_db
                patterns = self._metadata.code_patterns
                if not patterns:
                    messagebox.showinfo(
                        "No Patterns",
                        "No code patterns in the current project to copy.",
                    )
                    return

                existing_rows = code_glossary_db.read_all_rows_extended()
                existing_keys = {r[0] for r in existing_rows}
                added = 0
                for p in patterns:
                    if p.pattern not in existing_keys:
                        new_row = [""] * 11
                        new_row[0] = p.pattern
                        new_row[2] = p.category
                        new_row[4] = p.notes
                        new_row[10] = "true"
                        existing_rows.append(new_row)
                        added += 1

                code_glossary_db.write_all_rows(existing_rows)
                self._refresh_kb()
                messagebox.showinfo(
                    "Copy Complete",
                    f"Copied {added} new patterns to Global Code Database.",
                )
            else:
                from CherryAI.functions.glossary import (
                    read_unified_glossary,
                    write_unified_glossary,
                    GlossaryEntry,
                )
                characters = self._metadata.characters
                if not characters:
                    messagebox.showinfo(
                        "No Characters",
                        "No characters in the current project to copy.",
                    )
                    return

                existing = read_unified_glossary()
                added = 0
                for ch in characters:
                    key = ch.original_name
                    if not key:
                        continue
                    if key not in existing:
                        existing[key] = GlossaryEntry(
                            original=key,
                            translation=ch.translation,
                            notes=ch.notes,
                            active=True,
                        )
                        added += 1
                    else:
                        # Update translation/notes for existing entries
                        e = existing[key]
                        if ch.translation:
                            e.translation = ch.translation
                        if ch.notes:
                            e.notes = ch.notes

                write_unified_glossary(existing)
                self._refresh_kb()
                messagebox.showinfo(
                    "Copy Complete",
                    f"Copied {added} new entries to Global Glossary.",
                )
        except Exception as exc:
            logger.error("Failed to copy to global: %s", exc)
            messagebox.showerror("Error", f"Copy failed: {exc}")

    def _build_notes_section(self) -> None:
        """Build System Instructions section with preset management.

        Provides a dropdown listing all presets (Default + Custom + user
        presets), a writable Text field showing the prompt text, and
        Save/Delete buttons.  Default always populates the instructions.
        Custom prompts the user for a name before saving.

        Manifest stores: ``SIPreset`` (name) + ``Prompt`` (text).
        """
        frame = ttk.LabelFrame(self._left_column, text="System Instructions")
        frame.pack(fill="x", padx=5, pady=5)

        # --- Load presets ---
        self._si_presets = _load_si_presets()

        # ---- Header with preset dropdown and buttons ----
        si_header = ttk.Frame(frame)
        si_header.pack(fill="x", padx=10, pady=(5, 0))

        ttk.Label(si_header, text="Preset:").pack(side="left", padx=(0, 5))
        self._si_preset_var = tk.StringVar(value="Default")
        self._si_preset_combo = ttk.Combobox(
            si_header,
            textvariable=self._si_preset_var,
            values=list(self._si_presets.keys()),
            state="readonly",
            width=18,
        )
        self._si_preset_combo.pack(side="left", padx=(0, 5))
        self._si_preset_combo.bind(
            "<<ComboboxSelected>>", self._on_si_preset_changed,
        )

        # Bind preset name to manifest
        self._manifest_bindings.append(
            bind_combobox_to_info_field(
                combobox=self._si_preset_combo,
                var=self._si_preset_var,
                manager_getter=lambda: self.manifest_manager,
                meta_key="si_preset",
                default="Default",
            )
        )

        ttk.Button(
            si_header, text="💾 Save", width=7,
            command=self._save_si_preset,
        ).pack(side="left", padx=2)
        ttk.Button(
            si_header, text="🗑 Delete", width=10,
            command=self._delete_si_preset,
        ).pack(side="left", padx=2)

        # Enable/Disable toggle for System Instructions
        self._si_enabled_var = tk.BooleanVar(value=True)
        self._si_toggle_btn = ttk.Button(
            si_header, text="Enabled", width=8,
            command=self._toggle_si_enabled,
        )
        self._si_toggle_btn.pack(side="left", padx=(5, 0))

        # Prompt text field (writable)
        self._notes_text = scrolledtext.ScrolledText(
            frame,
            height=4,
            wrap="word",
            font=("Consolas", 10),
        )
        self._notes_text.pack(fill="x", padx=10, pady=(2, 5))

        # Bind prompt text to manifest
        self._manifest_bindings.append(
            bind_scrolledtext_to_info_field(
                text_widget=self._notes_text,
                manager_getter=lambda: self.manifest_manager,
                meta_key="system_instructions",
                default="",
            )
        )

        # Populate on first build
        self._on_si_preset_changed()

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
        """Build JSON view section (right column, initially hidden).

        Uses grid row 4 in the right column.  Shown/hidden via
        ``grid``/``grid_remove`` to coexist with the grid layout.
        """
        self._json_frame = ttk.LabelFrame(
            self._right_column,
            text="JSON View (Editable)",
        )
        # Initially hidden — do NOT grid it yet

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

    def _on_language_change(self, which: str) -> None:
        """Handle language combobox selection.

        TASK 41.3: When 'Other' is chosen, prompt for a custom language
        name via ``simpledialog``.  If the user cancels the dialog the
        previous selection is restored.

        Args:
            which: ``"source"`` or ``"target"``.
        """
        if which == "source":
            var = self._source_lang_var
            combo = self._source_lang_combo
            prev_attr = "_prev_source_lang"
            options = SOURCE_LANGUAGES
        else:
            var = self._target_lang_var
            combo = self._target_lang_combo
            prev_attr = "_prev_target_lang"
            options = TARGET_LANGUAGES

        current = var.get()
        if current == "Other":
            custom = simpledialog.askstring(
                f"Custom {which.title()} Language",
                f"Enter custom {which} language name:",
                parent=self,
            )
            if custom and custom.strip():
                # Temporarily allow editing to set non-list value
                combo.configure(state="normal")
                var.set(custom.strip())
                combo.configure(state="readonly")
            else:
                # User cancelled — revert
                var.set(getattr(self, prev_attr))
                return
        setattr(self, prev_attr, var.get())

    def _restore_summary_default(self) -> None:
        """Restore the Summary field to its default text (always re-reads INI)."""
        self._summary_text.delete("1.0", "end")
        self._summary_text.insert("1.0", ini_manager.get_default_text("Summary"))

    def _toggle_preset_state(
        self,
        custom_var: tk.StringVar,
        preset_combo: ttk.Combobox,
    ) -> None:
        """Legacy stub — no longer needed with new preset layout.

        Kept so old code paths referencing it don't crash.
        """
        pass  # pragma: no cover

    def _on_style_changed(self, event: Optional[tk.Event] = None) -> None:
        """Handle style preset selection — populate the prompt text field.

        Always reads the preset text fresh from INI so changes made in
        Global Options are reflected immediately without restarting the app.
        Custom preset clears the field so the user can type freely.
        """
        name = self._style_preset_var.get()
        if name == CUSTOM_PRESET_NAME:
            self._style_text.delete("1.0", "end")
            return
        prompt_text = ini_manager.get_all_presets("style").get(name, "")
        self._style_text.delete("1.0", "end")
        self._style_text.insert("1.0", prompt_text)

    def _on_tone_changed(self, event: Optional[tk.Event] = None) -> None:
        """Handle tone preset selection — populate the prompt text field.

        Always reads the preset text fresh from INI so changes made in
        Global Options are reflected immediately without restarting the app.
        Custom preset clears the field so the user can type freely.
        """
        name = self._tone_preset_var.get()
        if name == CUSTOM_PRESET_NAME:
            self._tone_text.delete("1.0", "end")
            return
        prompt_text = ini_manager.get_all_presets("tone").get(name, "")
        self._tone_text.delete("1.0", "end")
        self._tone_text.insert("1.0", prompt_text)

    # ---- Preset save / delete helpers ----

    def _save_style_preset(self) -> None:
        """Save the current style prompt text as a preset."""
        name = self._style_preset_var.get()
        text = self._style_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Empty", "Enter prompt text before saving.")
            return
        if name == CUSTOM_PRESET_NAME:
            new_name = simpledialog.askstring(
                "Save Style Preset", "Enter a name for this preset:",
            )
            if not new_name or not new_name.strip():
                return
            name = _unique_preset_name(new_name.strip(), self._style_presets)
        self._style_presets[name] = text
        ini_manager.set_preset_text("style", name, text)
        self._style_preset_combo["values"] = list(self._style_presets.keys())
        self._style_preset_var.set(name)
        logger.info("Saved style preset: %s", name)

    def _delete_style_preset(self) -> None:
        """Delete the currently selected style preset."""
        name = self._style_preset_var.get()
        if name == CUSTOM_PRESET_NAME:
            messagebox.showinfo(
                "Cannot Delete", "The 'Custom' preset cannot be deleted.",
            )
            return
        if not confirm_action(
            self, "delete_preset", "Confirm",
            f"Delete style preset '{name}'?",
        ):
            return
        self._style_presets.pop(name, None)
        ini_manager.delete_preset("style", name)
        self._style_preset_combo["values"] = list(self._style_presets.keys())
        self._style_preset_var.set(CUSTOM_PRESET_NAME)
        self._on_style_changed()
        logger.info("Deleted style preset: %s", name)

    def _save_tone_preset(self) -> None:
        """Save the current tone prompt text as a preset."""
        name = self._tone_preset_var.get()
        text = self._tone_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Empty", "Enter prompt text before saving.")
            return
        if name == CUSTOM_PRESET_NAME:
            new_name = simpledialog.askstring(
                "Save Tone Preset", "Enter a name for this preset:",
            )
            if not new_name or not new_name.strip():
                return
            name = _unique_preset_name(new_name.strip(), self._tone_presets)
        self._tone_presets[name] = text
        ini_manager.set_preset_text("tone", name, text)
        self._tone_preset_combo["values"] = list(self._tone_presets.keys())
        self._tone_preset_var.set(name)
        logger.info("Saved tone preset: %s", name)

    def _delete_tone_preset(self) -> None:
        """Delete the currently selected tone preset."""
        name = self._tone_preset_var.get()
        if name == CUSTOM_PRESET_NAME:
            messagebox.showinfo(
                "Cannot Delete", "The 'Custom' preset cannot be deleted.",
            )
            return
        if not confirm_action(
            self, "delete_preset", "Confirm",
            f"Delete tone preset '{name}'?",
        ):
            return
        self._tone_presets.pop(name, None)
        ini_manager.delete_preset("tone", name)
        self._tone_preset_combo["values"] = list(self._tone_presets.keys())
        self._tone_preset_var.set(CUSTOM_PRESET_NAME)
        self._on_tone_changed()
        logger.info("Deleted tone preset: %s", name)

    # ---- System Instructions preset save / delete helpers ----

    def _on_si_preset_changed(
        self, event: Optional[tk.Event] = None,
    ) -> None:
        """Handle System Instructions preset selection.

        Populates the text field with the preset content read fresh from INI.
        Custom preset clears the field so the user can type freely.
        """
        name = self._si_preset_var.get()
        if name == CUSTOM_PRESET_NAME:
            self._notes_text.delete("1.0", "end")
            return
        prompt_text = ini_manager.get_si_preset(name) or ""
        self._notes_text.delete("1.0", "end")
        self._notes_text.insert("1.0", prompt_text)

    def _save_si_preset(self) -> None:
        """Save current System Instructions text as a preset.

        Default can be overwritten directly.  Custom prompts the user
        for a name.
        """
        name = self._si_preset_var.get()
        text = self._notes_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning(
                "Empty", "Enter instructions text before saving.",
            )
            return
        if name == CUSTOM_PRESET_NAME:
            new_name = simpledialog.askstring(
                "Save SI Preset",
                "Enter a name for this preset:",
            )
            if not new_name or not new_name.strip():
                return
            name = _unique_preset_name(
                new_name.strip(), self._si_presets,
            )
        self._si_presets[name] = text
        ini_manager.set_si_preset(name, text)
        self._si_preset_combo["values"] = list(self._si_presets.keys())
        self._si_preset_var.set(name)
        logger.info("Saved SI preset: %s", name)

    def _delete_si_preset(self) -> None:
        """Delete the currently selected System Instructions preset.

        Custom and Default cannot be deleted.
        """
        name = self._si_preset_var.get()
        if name == CUSTOM_PRESET_NAME:
            messagebox.showinfo(
                "Cannot Delete", "The 'Custom' preset cannot be deleted.",
            )
            return
        if name == "Default":
            messagebox.showinfo(
                "Cannot Delete", "The 'Default' preset cannot be deleted.",
            )
            return
        if not confirm_action(
            self, "delete_preset", "Confirm",
            f"Delete SI preset '{name}'?",
        ):
            return
        self._si_presets.pop(name, None)
        ini_manager.delete_si_preset(name)
        self._si_preset_combo["values"] = list(self._si_presets.keys())
        self._si_preset_var.set("Default")
        self._on_si_preset_changed()
        logger.info("Deleted SI preset: %s", name)

    def _toggle_json_view(self) -> None:
        """Toggle JSON view visibility (grid-based)."""
        self._json_mode = not self._json_mode
        if self._json_mode:
            self._update_json_view()
            self._json_frame.grid(
                row=4, column=0, sticky="nsew", padx=5, pady=5,
            )
            self._json_btn.config(text="Form View")
        else:
            self._json_frame.grid_remove()
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
            self._save_characters_to_manifest()  # TASK 23.3

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
                self._save_characters_to_manifest()  # TASK 23.3

    def _remove_character(self) -> None:
        """Remove selected character(s).

        Supports multi-select: when multiple rows are selected via
        Ctrl+Click or Shift+Click, all selected characters are removed
        at once after a single confirmation.
        """
        selection = self._char_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a character to remove.")
            return

        count = len(selection)
        msg = (
            "Remove selected character?"
            if count == 1
            else f"Remove {count} selected characters?"
        )
        if not confirm_action(
            self, "remove_character", "Confirm", msg,
        ):
            return
        # Collect indices in reverse order to avoid index shifting
        indices = sorted(
            [self._char_tree.index(item) for item in selection],
            reverse=True,
        )
        for idx in indices:
            if idx < len(self._metadata.characters):
                del self._metadata.characters[idx]
        self._refresh_character_list()
        self._save_characters_to_manifest()

    def _infer_character_genders(self) -> None:
        """Infer gender for characters using analysis context.

        Reads mode from utility settings:
        - **Script only** — built-in script analysis (pronouns, honorifics).
        - **Script + LLM** — runs script first, then LLM for unknowns.

        Confidence spinbox settings control the inference thresholds.
        Only updates characters whose gender is empty or 'Unknown'.
        Shows a progress dialog for visibility during long operations.
        """
        if not self._metadata.characters:
            messagebox.showinfo(
                "No Characters",
                "No characters to infer genders for. Add characters first.",
            )
            return

        # Import gender inference function
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

        # Read utility settings
        from CherryAI.functions import ini_manager
        gi_mode = ini_manager.get_user_default(
            "utility", "gender_inference_mode",
        ) or "Script only"
        script_min = int(
            ini_manager.get_user_default(
                "utility", "gender_script_minimum",
            ) or "30"
        )
        script_max = int(
            ini_manager.get_user_default(
                "utility", "gender_script_maximum",
            ) or "50"
        )
        script_ign = ini_manager.get_user_default(
            "utility", "gender_script_ignore_unknown",
        )
        script_ignore_unknown = script_ign not in ("false", "False", "0", "")
        script_doall_str = ini_manager.get_user_default(
            "utility", "gender_script_do_all",
        )
        script_do_all = script_doall_str not in ("false", "False", "0", "")

        # Confidence threshold from script spinboxes
        if script_do_all:
            # Absolute: need script_min of script_max to agree
            confidence_threshold = (
                (script_min / script_max) * 100 if script_max else 50
            )
        else:
            confidence_threshold = 50

        # --- Gather context data ---
        all_lines: List[str] = []
        try:
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                all_lines = mgr.get_all_orig_lines()
        except Exception:
            pass

        full_text = "\n".join(all_lines) if all_lines else ""

        speaker_counts: Dict[str, int] = {}
        try:
            analysis_data = self._get_analysis_step_data()
            analysis_results = analysis_data.get("analysis_results", {})
            characters_data = analysis_results.get("characters", [])
            if isinstance(characters_data, list):
                for entry in characters_data:
                    if isinstance(entry, dict):
                        name = entry.get("original_name", "")
                        cnt = entry.get("count", 0)
                        if name and cnt > 0:
                            speaker_counts[name] = cnt
        except Exception:
            pass

        # --- Build list of characters to check ---
        chars_to_check = []
        for char in self._metadata.characters:
            notes_lower = char.notes.lower() if char.notes else ""
            has_gender = any(
                g in notes_lower for g in ("male", "female", "non-binary")
            )
            if has_gender:
                continue
            name_to_check = char.original_name or char.translation
            if name_to_check:
                chars_to_check.append((char, name_to_check))

        if not chars_to_check:
            messagebox.showinfo(
                "No Updates",
                "All characters already have genders set.",
            )
            return

        # --- Create progress dialog ---
        total = len(chars_to_check)
        progress_dialog = tk.Toplevel(self)
        progress_dialog.title("Inferring Gender...")
        progress_dialog.transient(self.winfo_toplevel())
        progress_dialog.grab_set()
        progress_dialog.resizable(False, False)
        progress_dialog.geometry("420x130")
        progress_dialog.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 420) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 130) // 2
        progress_dialog.geometry(f"+{max(px, 0)}+{max(py, 0)}")
        progress_dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        pframe = ttk.Frame(progress_dialog, padding=15)
        pframe.pack(fill="both", expand=True)

        progress_label = ttk.Label(
            pframe, text="Preparing...", wraplength=390, anchor="w",
        )
        progress_label.pack(fill="x", pady=(0, 5))

        progress_bar = ttk.Progressbar(
            pframe, orient="horizontal", length=390, mode="determinate",
        )
        progress_bar["maximum"] = total
        progress_bar.pack(fill="x", pady=(0, 5))

        count_label = ttk.Label(pframe, text=f"0 / {total}")
        count_label.pack(anchor="w")

        progress_dialog.update_idletasks()

        # --- Run inference ---
        updated_count = 0
        llm_needed: List[tuple] = []

        for i, (char, name_to_check) in enumerate(chars_to_check):
            progress_label.configure(text=f"Script: '{name_to_check}'")
            progress_bar["value"] = i
            count_label.configure(text=f"{i} / {total}")
            progress_dialog.update_idletasks()

            try:
                inferred, confidence, _, _, _ = infer_gender_comprehensive(
                    name=name_to_check,
                    pronouns={},
                    honorifics={},
                    full_text=full_text,
                    lines=all_lines if all_lines else None,
                    speaker_counts=speaker_counts if speaker_counts else None,
                    confidence_threshold=confidence_threshold / 100,
                )
                if inferred and inferred != "Unknown" and confidence >= confidence_threshold:
                    parts = [
                        p.strip()
                        for p in char.notes.split(",") if p.strip()
                    ]
                    if inferred not in parts:
                        parts.insert(0, inferred)
                    char.notes = ", ".join(parts)
                    updated_count += 1
                elif gi_mode == "Script + LLM":
                    llm_needed.append((char, name_to_check))
            except Exception as e:
                logger.debug(
                    "Gender inference failed for %s: %s", name_to_check, e,
                )
                if gi_mode == "Script + LLM":
                    llm_needed.append((char, name_to_check))

        # --- LLM pass for remaining unknowns ---
        if llm_needed and gi_mode == "Script + LLM" and all_lines:
            llm_min = int(
                ini_manager.get_user_default(
                    "utility", "gender_llm_minimum",
                ) or "3"
            )
            llm_max = int(
                ini_manager.get_user_default(
                    "utility", "gender_llm_maximum",
                ) or "5"
            )
            llm_ign = ini_manager.get_user_default(
                "utility", "gender_llm_ignore_unknown",
            )
            llm_ignore = llm_ign not in ("false", "False", "0", "")
            llm_doall_str = ini_manager.get_user_default(
                "utility", "gender_llm_do_all",
            )
            llm_do_all = llm_doall_str not in ("false", "False", "0", "")

            try:
                from CherryAI.functions.API2Glossary import infer_gender_llm
            except ImportError:
                logger.warning("LLM gender inference not available")
                llm_needed = []

            for j, (char, name_to_check) in enumerate(llm_needed):
                idx = total - len(llm_needed) + j
                progress_label.configure(text=f"LLM: '{name_to_check}'")
                progress_bar["value"] = idx
                count_label.configure(
                    text=f"{idx} / {total} (LLM pass)",
                )
                progress_dialog.update_idletasks()

                try:
                    gender, conf = infer_gender_llm(
                        name_to_check,
                        all_lines,
                        minimum=llm_min,
                        maximum=llm_max,
                        ignore_unknown=llm_ignore,
                        do_all=llm_do_all,
                    )
                    if gender and gender != "Unknown" and conf >= 50:
                        parts = [
                            p.strip()
                            for p in char.notes.split(",") if p.strip()
                        ]
                        if gender not in parts:
                            parts.insert(0, gender)
                        char.notes = ", ".join(parts)
                        updated_count += 1
                except RuntimeError as exc:
                    logger.error("LLM gender inference error: %s", exc)
                    try:
                        progress_dialog.grab_release()
                        progress_dialog.destroy()
                    except tk.TclError:
                        pass
                    messagebox.showerror(
                        "Gender Inference Failed",
                        str(exc),
                    )
                    return
                except Exception as e:
                    logger.debug(
                        "LLM gender for %s failed: %s", name_to_check, e,
                    )

        # Close progress dialog
        try:
            progress_dialog.grab_release()
            progress_dialog.destroy()
        except tk.TclError:
            pass

        # Refresh display
        self._refresh_character_list()

        if updated_count > 0:
            self._save_characters_to_manifest()

        if updated_count > 0:
            messagebox.showinfo(
                "Gender Inference Complete",
                f"Inferred gender for {updated_count} character(s).",
            )
        else:
            messagebox.showinfo(
                "No Updates",
                "Could not infer gender for any characters.\n"
                "Characters either already have genders set or names "
                "are ambiguous.",
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
        # Column order: original, translation, notes
        columns = ("original", "translation", "notes")
        # Map column names to dataclass fields
        field_map = {"original": "original_name", "translation": "translation",
                     "notes": "notes"}
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
            col_key: Column key (original, translation, notes).
            field_key: Dataclass field key (original_name, name, notes).
            col_idx: Column index.
            char: Character being edited.
        """
        # Column order: original, translation, notes
        columns = ("original", "translation", "notes")
        try:
            bbox = self._char_tree.bbox(item, columns[col_idx])
            if not bbox:
                return
        except tk.TclError:
            return

        x, y, width, height = bbox

        if col_key == "notes":
            current_value = char.notes
        else:
            current_value = getattr(char, field_key, "")

        # All columns use text entry editing
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
            self._save_characters_to_manifest()

        def on_cancel(event=None):
            entry.destroy()

        entry.bind("<Return>", on_confirm)
        entry.bind("<Tab>", on_confirm)
        entry.bind("<Escape>", on_cancel)
        entry.bind("<FocusOut>", on_confirm)

    def _open_genre_dialog(self) -> None:
        """Open a dialog for multi-selecting genres.
        
        TASK 41.2: ADD behavior — selections are merged with existing
        genres rather than overwriting them.  Custom genres typed
        directly into the field are preserved.
        """
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
            # TASK 41.2: Preserve custom genres already in field that
            # are not part of COMMON_GENRES (user-typed entries).
            existing = [
                g.strip()
                for g in self._genre_var.get().split(",")
                if g.strip()
            ]
            non_common = [
                g for g in existing
                if g not in COMMON_GENRES and g not in selected
            ]
            merged = selected + non_common
            self._genre_var.set(", ".join(merged))
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
            # Column order: original, translation, notes
            self._char_tree.insert(
                "",
                "end",
                values=(char.original_name, char.translation, char.notes),
            )

    def _on_char_context_menu(self, event: tk.Event) -> None:
        """Show context menu on right-click in character treeview."""
        item = self._char_tree.identify_row(event.y)
        if not item:
            return

        # Select the item under cursor
        self._char_tree.selection_set(item)

        menu = tk.Menu(self._char_tree, tearoff=0)
        menu.add_command(
            label="Clear Notes",
            command=lambda: self._clear_character_notes(item),
        )
        menu.add_separator()
        menu.add_command(
            label="Edit...",
            command=lambda: self._on_char_double_click(event),
        )
        menu.add_command(
            label="Remove",
            command=self._remove_character,
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _clear_character_notes(self, item: str) -> None:
        """Clear the notes field for the selected character."""
        idx = self._char_tree.index(item)
        if idx >= len(self._metadata.characters):
            return
        self._metadata.characters[idx].notes = ""
        self._refresh_character_list()
        self._save_characters_to_manifest()

    # ------------------------------------------------------------------
    # Analysis data access helper
    # ------------------------------------------------------------------

    def _get_analysis_step_data(self) -> Dict[str, Any]:
        """Read the Analysis step's stored data from ManifestManager.

        Returns:
            Analysis step data dictionary.
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            try:
                return mgr.get_step_data(1)
            except Exception:
                pass
        return {}

    def _on_import_from_analysis(self) -> None:
        """Handle Import from Analysis button click.

        Imports speakers detected in Analysis step as characters.
        Reads from the unified ``characters`` list which contains
        per-speaker counts.  Shows a dialog letting the user choose
        how many to import (non-destructive: existing entries are never
        overwritten).
        """
        try:
            analysis_step_data = self._get_analysis_step_data()
            analysis_results = analysis_step_data.get("analysis_results", {})
            characters_data = analysis_results.get("characters", [])

            # Build list from unified characters (list of dicts with count)
            items_list: list = []
            if isinstance(characters_data, list):
                for entry in characters_data:
                    if isinstance(entry, dict) and entry.get("count", 0) > 0:
                        items_list.append((
                            entry.get("original_name", ""),
                            entry.get("count", 0),
                        ))

            if not items_list:
                messagebox.showinfo(
                    "No Speakers",
                    "No speakers were detected in Analysis.\n\n"
                    "Run Analysis first to detect speakers.",
                )
                return

            items_list.sort(key=lambda x: x[1], reverse=True)
            speaker_count = len(items_list)

            # --- choice dialog ---
            dlg = tk.Toplevel(self)
            dlg.title("Import Speakers")
            dlg.resizable(False, False)
            dlg.transient(self)
            dlg.grab_set()

            ttk.Label(
                dlg,
                text=f"{speaker_count} speakers found. Import how many?",
                wraplength=300,
            ).pack(padx=15, pady=(10, 5))

            choice_var = tk.StringVar(value="top")
            top_frame = ttk.Frame(dlg)
            top_frame.pack(fill="x", padx=15, pady=2)
            ttk.Radiobutton(
                top_frame, text="Top", variable=choice_var, value="top",
            ).pack(side="left")
            spin_var = tk.IntVar(value=min(20, speaker_count))
            spin = ttk.Spinbox(
                top_frame, from_=1, to=speaker_count,
                textvariable=spin_var, width=5,
            )
            spin.pack(side="left", padx=5)
            ttk.Label(top_frame, text="most common").pack(side="left")

            ttk.Radiobutton(
                dlg, text="All speakers", variable=choice_var, value="all",
            ).pack(anchor="w", padx=15, pady=2)

            result: Dict[str, Any] = {}

            def _ok() -> None:
                if choice_var.get() == "all":
                    result["n"] = speaker_count
                else:
                    result["n"] = spin_var.get()
                dlg.destroy()

            btn_row = ttk.Frame(dlg)
            btn_row.pack(pady=10)
            ttk.Button(btn_row, text="Import", command=_ok).pack(
                side="left", padx=5,
            )
            ttk.Button(
                btn_row, text="Cancel", command=dlg.destroy,
            ).pack(side="left", padx=5)

            dlg.wait_window()
            if "n" not in result:
                return
            # --- end dialog ---

            n = result["n"]
            imported_count = 0
            existing_originals = {
                c.original_name for c in self._metadata.characters
            }

            for speaker_name, count in items_list[:n]:
                if speaker_name in existing_originals:
                    continue

                char = CharacterInfo(
                    original_name=speaker_name,
                    count=count,
                )
                self._metadata.characters.append(char)
                existing_originals.add(speaker_name)
                imported_count += 1

            self._refresh_character_list()

            if imported_count > 0:
                self._save_characters_to_manifest()
                messagebox.showinfo(
                    "Import Complete",
                    f"Imported {imported_count} new characters from Analysis.",
                )
            else:
                messagebox.showinfo(
                    "No New Characters",
                    "All selected speakers already exist in the character list.",
                )

        except (AttributeError, KeyError, IndexError):
            messagebox.showwarning(
                "Analysis Required",
                "Run Analysis first to detect speakers.",
            )
        except Exception as e:
            logger.error("Failed to import from analysis: %s", e)
            messagebox.showerror("Import Error", f"Failed to import: {e}")

    # ========================================================================
    # Code Database Management (TASK 18.5, TASK 41.1)
    # ========================================================================

    def _add_code_pattern(self) -> None:
        """Add a new code pattern."""
        dialog = CodePatternDialog(self, "Add Code Pattern")
        if dialog.result:
            self._metadata.code_patterns.append(dialog.result)
            self._refresh_code_pattern_list()
            self._save_code_patterns_to_manifest()  # TASK 23.3

    def _get_code_pattern_idx(self, item: str) -> int:
        """Extract code pattern index from treeview item tags.

        Returns -1 if the item is an instance sub-row or has no valid tag.
        """
        for tag in self._code_tree.item(item, "tags"):
            if isinstance(tag, str) and tag.startswith("pat_"):
                try:
                    return int(tag[4:])
                except ValueError:
                    pass
        return -1

    def _edit_code_pattern(self) -> None:
        """Edit selected code pattern."""
        selection = self._code_tree.selection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a pattern to edit."
            )
            return

        idx = self._get_code_pattern_idx(selection[0])
        if 0 <= idx < len(self._metadata.code_patterns):
            pattern = self._metadata.code_patterns[idx]
            dialog = CodePatternDialog(self, "Edit Code Pattern", pattern)
            if dialog.result:
                self._metadata.code_patterns[idx] = dialog.result
                self._refresh_code_pattern_list()
                self._save_code_patterns_to_manifest()  # TASK 23.3

    def _remove_code_pattern(self) -> None:
        """Remove selected code pattern(s).

        Supports multi-select via Ctrl/Shift click.  Deletes in
        reverse index order to avoid index shifting.  Instance sub-rows
        are ignored.
        """
        selection = self._code_tree.selection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a pattern to remove.",
            )
            return

        indices = sorted(
            {self._get_code_pattern_idx(s) for s in selection} - {-1},
            reverse=True,
        )
        if not indices:
            return

        count = len(indices)
        msg = (
            f"Remove {count} selected patterns?"
            if count > 1
            else "Remove selected pattern?"
        )
        if not confirm_action(self, "remove_code_pattern", "Confirm", msg):
            return

        for idx in indices:
            if idx < len(self._metadata.code_patterns):
                self._code_expanded.discard(idx)
                del self._metadata.code_patterns[idx]
        self._refresh_code_pattern_list()
        self._save_code_patterns_to_manifest()  # TASK 23.3

    def _on_code_double_click(self, event: tk.Event) -> None:
        """Handle double-click on code pattern tree for inline editing.

        If the clicked row is an instance sub-row, ignore.  If it is an
        expandable parent row on the pattern column, toggle expansion.
        Otherwise proceed with inline editing.
        """
        region = self._code_tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._code_tree.identify_column(event.x)
        item = self._code_tree.identify_row(event.y)
        if not item:
            return

        # Skip instance sub-rows
        item_tags = self._code_tree.item(item, "tags")
        if "instance_row" in item_tags:
            return

        # Get column index (1-based from identify_column)
        col_idx = int(column.replace("#", "")) - 1
        columns = ("pattern", "translation", "category", "action")
        if col_idx < 0 or col_idx >= len(columns):
            return

        # Find pattern index from tags
        idx = -1
        for tag in item_tags:
            if isinstance(tag, str) and tag.startswith("pat_"):
                try:
                    idx = int(tag[4:])
                except ValueError:
                    pass
                break
        if idx < 0 or idx >= len(self._metadata.code_patterns):
            return

        pattern = self._metadata.code_patterns[idx]

        # Toggle expansion when clicking pattern column of expandable row
        col_key = columns[col_idx]
        if col_key == "pattern" and pattern.instances:
            if idx in self._code_expanded:
                self._code_expanded.discard(idx)
            else:
                self._code_expanded.add(idx)
            self._refresh_code_pattern_list()
            return

        self._start_code_inline_edit(item, col_key, col_idx, pattern)

    def _start_code_inline_edit(
        self, item: str, col_key: str, col_idx: int, pattern: "CodePattern"
    ) -> None:
        """Start inline editing of a code pattern cell.
        
        Args:
            item: Treeview item ID.
            col_key: Column key (pattern, translation, category, action).
            col_idx: Column index.
            pattern: Code pattern being edited.
        """
        columns = ("pattern", "translation", "category", "action")
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
                                     ["preserve", "provides_context", "custom_placeholder",
                                      "protect", "strip_with_anchor", "part_of_span"])
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
                    self._save_code_patterns_to_manifest()  # TASK 23.3

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
                self._save_code_patterns_to_manifest()  # TASK 23.3

        def on_cancel(event=None):
            combo.destroy()

        combo.bind("<<ComboboxSelected>>", on_select)
        combo.bind("<Return>", on_select)
        combo.bind("<Escape>", on_cancel)
        combo.bind("<FocusOut>", on_select)

    def _refresh_code_pattern_list(self) -> None:
        """Refresh code pattern treeview with collapsible instances.

        Patterns that have instances are prefixed with [+] or [-] in the
        pattern column.  When expanded, instance sub-rows are shown indented
        below the parent.  Patterns with instances sort before those without.
        """
        for item in self._code_tree.get_children():
            self._code_tree.delete(item)

        # Sort: patterns with instances first, then alphabetical
        patterns = list(enumerate(self._metadata.code_patterns))
        patterns.sort(
            key=lambda x: (
                0 if x[1].instances else 1,
                -x[1].count,
                x[1].pattern,
            )
        )

        for idx, pattern in patterns:
            has_inst = bool(pattern.instances)
            expanded = idx in self._code_expanded
            if has_inst:
                prefix = "[-] " if expanded else "[+] "
            else:
                prefix = ""
            self._code_tree.insert(
                "",
                "end",
                tags=(f"pat_{idx}",),
                values=(
                    prefix + pattern.pattern,
                    pattern.translation,
                    pattern.category,
                    pattern.action,
                ),
            )
            if has_inst and expanded:
                for i, inst in enumerate(pattern.instances):
                    inst_count = (
                        pattern.instance_counts[i]
                        if i < len(pattern.instance_counts) else 0
                    )
                    self._code_tree.insert(
                        "",
                        "end",
                        tags=("instance_row",),
                        values=(
                            f"    {inst}",
                            f"({inst_count})" if inst_count else "",
                            "",
                            "",
                        ),
                    )

    def _on_import_code_patterns(self) -> None:
        """Import code patterns from Analysis step.

        Reads from the unified ``code_patterns`` list which contains
        per-pattern detail with counts.  Shows a choice dialog for how
        many to import (non-destructive).
        """
        try:
            analysis_step_data = self._get_analysis_step_data()
            analysis_results = analysis_step_data.get("analysis_results", {})
            code_patterns = analysis_results.get("code_patterns", [])

            # Build list: [(pattern_text, count, type_label)]
            items_list: list = []
            if isinstance(code_patterns, list):
                for entry in code_patterns:
                    if isinstance(entry, dict) and entry.get("count", 0) > 0:
                        items_list.append((
                            entry.get("pattern", ""),
                            entry.get("count", 0),
                            entry.get("category", "Detected"),
                        ))

            if not items_list:
                messagebox.showinfo(
                    "No Patterns",
                    "No code patterns were detected in Analysis.\n\n"
                    "Run Analysis first to detect patterns.",
                )
                return

            items_list.sort(key=lambda x: x[1], reverse=True)
            total = len(items_list)

            # --- choice dialog ---
            dlg = tk.Toplevel(self)
            dlg.title("Import Code Patterns")
            dlg.resizable(False, False)
            dlg.transient(self)
            dlg.grab_set()

            ttk.Label(
                dlg,
                text=f"{total} code patterns found. Import how many?",
                wraplength=300,
            ).pack(padx=15, pady=(10, 5))

            choice_var = tk.StringVar(value="top")
            top_frame = ttk.Frame(dlg)
            top_frame.pack(fill="x", padx=15, pady=2)
            ttk.Radiobutton(
                top_frame, text="Top", variable=choice_var, value="top",
            ).pack(side="left")
            spin_var = tk.IntVar(value=min(20, total))
            ttk.Spinbox(
                top_frame, from_=1, to=total,
                textvariable=spin_var, width=5,
            ).pack(side="left", padx=5)
            ttk.Label(top_frame, text="most common").pack(side="left")

            ttk.Radiobutton(
                dlg, text="All patterns", variable=choice_var, value="all",
            ).pack(anchor="w", padx=15, pady=2)

            result: Dict[str, Any] = {}

            def _ok() -> None:
                result["n"] = (
                    total if choice_var.get() == "all" else spin_var.get()
                )
                dlg.destroy()

            btn_row = ttk.Frame(dlg)
            btn_row.pack(pady=10)
            ttk.Button(btn_row, text="Import", command=_ok).pack(
                side="left", padx=5,
            )
            ttk.Button(
                btn_row, text="Cancel", command=dlg.destroy,
            ).pack(side="left", padx=5)

            dlg.wait_window()
            if "n" not in result:
                return
            # --- end dialog ---

            n = result["n"]
            imported_count = 0
            existing_patterns = {
                p.pattern for p in self._metadata.code_patterns
            }

            for pat_text, count, type_label in items_list[:n]:
                if pat_text in existing_patterns:
                    continue

                pattern = CodePattern(
                    pattern=pat_text,
                    category=type_label,
                    action="preserve",
                    count=count,
                    notes=f"Imported from Analysis ({count} occurrences)",
                )
                self._metadata.code_patterns.append(pattern)
                existing_patterns.add(pat_text)
                imported_count += 1

            self._refresh_code_pattern_list()

            if imported_count > 0:
                self._save_code_patterns_to_manifest()
                messagebox.showinfo(
                    "Import Complete",
                    f"Imported {imported_count} new patterns from Analysis.",
                )
            else:
                messagebox.showinfo(
                    "No New Patterns",
                    "All selected patterns already exist in the list.",
                )

        except (AttributeError, KeyError, IndexError):
            messagebox.showwarning(
                "Analysis Required",
                "Run Analysis first to detect code patterns.",
            )
        except Exception as e:
            logger.error("Failed to import code patterns: %s", e)
            messagebox.showerror("Import Error", f"Failed to import: {e}")

    def _on_use_global_glossary_changed(self) -> None:
        """Handle Use Global Glossary change — delegated to KB toggle.

        Legacy method kept for backward compatibility.  Delegates to
        ``_toggle_kb_enabled`` if the Knowledge Base widget is built.
        """
        if hasattr(self, "_kb_enabled_var"):
            self._toggle_kb_enabled()
        else:
            logger.debug("KB not built yet; use_global change ignored.")

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

        # TASK 41.5: Refresh table after copy
        self._refresh_glossary_entries()

    # ========================================================================
    # Glossary Entry Management (TASK 41.5)
    # ========================================================================

    def _add_glossary_entry(self) -> None:
        """Add an empty glossary entry row (active by default)."""
        self._glossary_tree.insert(
            "", "end", values=("✓", "", "", "")
        )
        # Auto-start editing on the new row's first cell
        children = self._glossary_tree.get_children()
        if children:
            last = children[-1]
            self._glossary_tree.selection_set(last)
            self._glossary_tree.see(last)
        self._sync_glossary_tree_to_manifest()

    def _remove_glossary_entry(self) -> None:
        """Remove the selected glossary entry."""
        selection = self._glossary_tree.selection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select an entry to remove."
            )
            return
        for item in selection:
            self._glossary_tree.delete(item)
        self._sync_glossary_tree_to_manifest()

    def _on_glossary_click(self, event: tk.Event) -> None:
        """Toggle Active column on single click (TASK 41.10)."""
        region = self._glossary_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self._glossary_tree.identify_column(event.x)
        item = self._glossary_tree.identify_row(event.y)
        if not item:
            return
        col_idx = int(column.replace("#", "")) - 1
        if col_idx != 0:
            return  # only handle Active column
        vals = list(self._glossary_tree.item(item, "values"))
        vals[0] = "✗" if vals[0] == "✓" else "✓"
        self._glossary_tree.item(item, values=vals)
        self._sync_glossary_tree_to_manifest()

    def _on_glossary_double_click(self, event: tk.Event) -> None:
        """Handle double-click on glossary table for inline editing.

        TASK 41.5: Same pattern as code tree inline edit.
        TASK 41.10: Skips Active column (col 0) — toggled by single click.
        """
        region = self._glossary_tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._glossary_tree.identify_column(event.x)
        item = self._glossary_tree.identify_row(event.y)
        if not item:
            return

        col_idx = int(column.replace("#", "")) - 1
        col_keys = ("active", "original", "translation", "notes")
        if col_idx <= 0 or col_idx >= len(col_keys):
            return  # skip active column and out-of-range

        self._start_glossary_inline_edit(item, col_keys[col_idx], col_idx)

    def _start_glossary_inline_edit(
        self, item: str, col_key: str, col_idx: int,
    ) -> None:
        """Start inline editing of a glossary cell.

        Args:
            item: Treeview item id.
            col_key: Column key name.
            col_idx: Column index (1-3, skipping 0=active).
        """
        columns = ("active", "original", "translation", "notes")
        try:
            bbox = self._glossary_tree.bbox(item, columns[col_idx])
            if not bbox:
                return
        except tk.TclError:
            return

        x, y, width, height = bbox
        current_values = self._glossary_tree.item(item, "values")
        current_value = current_values[col_idx] if col_idx < len(current_values) else ""

        entry = ttk.Entry(self._glossary_tree)
        entry.insert(0, str(current_value))
        entry.select_range(0, "end")
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()

        def on_confirm(event: Optional[tk.Event] = None) -> None:
            new_value = entry.get()
            entry.destroy()
            if new_value != str(current_value):
                vals = list(self._glossary_tree.item(item, "values"))
                while len(vals) <= col_idx:
                    vals.append("")
                vals[col_idx] = new_value
                self._glossary_tree.item(item, values=vals)
                self._sync_glossary_tree_to_manifest()

        def on_cancel(event: Optional[tk.Event] = None) -> None:
            entry.destroy()

        entry.bind("<Return>", on_confirm)
        entry.bind("<Tab>", on_confirm)
        entry.bind("<Escape>", on_cancel)
        entry.bind("<FocusOut>", on_confirm)

    def _sync_glossary_tree_to_manifest(self) -> None:
        """Persist current glossary tree contents to manifest.

        TASK 41.5 / 41.10: Reads all rows from the Treeview (including
        the Active flag) and writes them to the manifest.
        """
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        entries: List[Dict[str, Any]] = []
        for child in self._glossary_tree.get_children():
            vals = self._glossary_tree.item(child, "values")
            active = (vals[0] == "✓") if len(vals) > 0 else True
            source = vals[1] if len(vals) > 1 else ""
            target = vals[2] if len(vals) > 2 else ""
            notes = vals[3] if len(vals) > 3 else ""
            if source or target:
                entries.append({
                    "source": source,
                    "target": target,
                    "notes": notes,
                    "category": "",
                    "context": "",
                    "active": active,
                })

        from CherryAI.functions.manifest_fields import save_glossary_entries
        save_glossary_entries(mgr, entries)
        self._project_glossary_count_var.set(
            f"Project entries: {len(entries)}"
        )
        logger.debug("Synced %d glossary entries to manifest", len(entries))

    def _refresh_glossary_entries(self) -> None:
        """Reload glossary Treeview from manifest data.

        TASK 41.5 / 41.10: Populates the inline-editable table
        including the Active checkbox column.
        """
        for item in self._glossary_tree.get_children():
            self._glossary_tree.delete(item)

        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        from CherryAI.functions.manifest_fields import load_glossary_entries
        entries = load_glossary_entries(mgr)
        for entry in entries:
            active = "✓" if entry.get("active", True) else "✗"
            self._glossary_tree.insert("", "end", values=(
                active,
                entry.get("source", ""),
                entry.get("target", ""),
                entry.get("notes", ""),
            ))
        self._project_glossary_count_var.set(
            f"Project entries: {len(entries)}"
        )

    def _on_import_glossary_from_analysis(self) -> None:
        """Import detected speakers from Analysis as glossary entries.

        Shows a dialog letting the user choose how many of the most
        common speakers to import.  Existing entries (matched by source
        column) are never overwritten.
        """
        try:
            analysis_step_data = self._get_analysis_step_data()
            analysis_results = analysis_step_data.get("analysis_results", {})
            characters_data = analysis_results.get("characters", [])

            # Build sorted list: [(name, count)]
            # Filter out below-threshold speakers
            go = getattr(self.session, "global_options", None)
            threshold = 10
            if go is not None:
                threshold = getattr(
                    getattr(go, "utility", None), "speaker_threshold", 10
                )
            items_list: list = []
            if isinstance(characters_data, list):
                for entry in characters_data:
                    count = entry.get("count", 0) if isinstance(entry, dict) else 0
                    if isinstance(entry, dict) and count >= threshold:
                        items_list.append((
                            entry.get("original_name", ""),
                            count,
                        ))

            if not items_list:
                messagebox.showinfo(
                    "No Speakers",
                    "No speakers were detected in Analysis.\n\n"
                    "Run Analysis first to detect speakers.",
                )
                return

            items_list.sort(key=lambda x: x[1], reverse=True)
            speaker_count = len(items_list)

            # --- choice dialog ---
            dlg = tk.Toplevel(self)
            dlg.title("Import Speakers to Glossary")
            dlg.resizable(False, False)
            dlg.transient(self)
            dlg.grab_set()

            ttk.Label(
                dlg,
                text=f"{speaker_count} speakers found. Import how many?",
                wraplength=300,
            ).pack(padx=15, pady=(10, 5))

            choice_var = tk.StringVar(value="top")
            top_frame = ttk.Frame(dlg)
            top_frame.pack(fill="x", padx=15, pady=2)
            ttk.Radiobutton(
                top_frame, text="Top", variable=choice_var, value="top",
            ).pack(side="left")
            spin_var = tk.IntVar(value=min(20, speaker_count))
            ttk.Spinbox(
                top_frame, from_=1, to=speaker_count,
                textvariable=spin_var, width=5,
            ).pack(side="left", padx=5)
            ttk.Label(top_frame, text="most common").pack(side="left")

            ttk.Radiobutton(
                dlg, text="All speakers", variable=choice_var, value="all",
            ).pack(anchor="w", padx=15, pady=2)

            result: Dict[str, Any] = {}

            def _ok() -> None:
                result["n"] = (
                    speaker_count
                    if choice_var.get() == "all"
                    else spin_var.get()
                )
                dlg.destroy()

            btn_row = ttk.Frame(dlg)
            btn_row.pack(pady=10)
            ttk.Button(btn_row, text="Import", command=_ok).pack(
                side="left", padx=5,
            )
            ttk.Button(
                btn_row, text="Cancel", command=dlg.destroy,
            ).pack(side="left", padx=5)

            dlg.wait_window()
            if "n" not in result:
                return
            # --- end dialog ---

            n = result["n"]

            # Collect existing source terms to avoid dupes
            existing: set[str] = set()
            for child in self._glossary_tree.get_children():
                vals = self._glossary_tree.item(child, "values")
                if len(vals) > 1:
                    existing.add(str(vals[1]))

            imported_count = 0
            for name, count in items_list[:n]:
                if name in existing:
                    continue
                self._glossary_tree.insert("", "end", values=(
                    "✓", name, "", f"Speaker ({count} occurrences)",
                ))
                existing.add(name)
                imported_count += 1

            self._sync_glossary_tree_to_manifest()

            if imported_count > 0:
                messagebox.showinfo(
                    "Import Complete",
                    f"Imported {imported_count} speakers as glossary entries.",
                )
            else:
                messagebox.showinfo(
                    "No New Entries",
                    "All selected speakers already exist in the glossary.",
                )

        except (AttributeError, KeyError, IndexError):
            messagebox.showwarning(
                "Analysis Required",
                "Run Analysis first to detect speakers.",
            )
        except Exception as e:
            logger.error("Failed to import glossary from analysis: %s", e)
            messagebox.showerror("Import Error", f"Failed to import: {e}")

    # ========================================================================
    # Global Glossary / Database Management (TASK 41.9 — Phase 62 unified)
    # ========================================================================

    @staticmethod
    def _global_db_path(mode: str) -> Path:
        """Return the canonical file path for a global database mode.

        Phase 62: Both modes now use TSV files in user/.
          - Glossary      → user/globalglossary.tsv
          - Code Database → user/codedatabase.tsv

        Args:
            mode: ``"Glossary"`` or ``"Code Database"``.

        Returns:
            Absolute path to the TSV file.
        """
        from CherryAI.functions.glossary import (
            _unified_glossary_path,
            _code_glossary_path,
        )
        if mode == "Code Database":
            return _code_glossary_path()
        return _unified_glossary_path()

    def _load_global_db(self, mode: str) -> List[Dict[str, str]]:
        """Load entries from the global TSV file.

        Phase 62: Glossary reads from globalglossary.tsv via
        ``read_unified_glossary()``.  Code Database reads from
        codedatabase.tsv via ``code_glossary_db.read_all_rows()``.

        Args:
            mode: ``"Glossary"`` or ``"Code Database"``.

        Returns:
            List of entry dicts with keys ``col1``/``col2``/``col3``.
        """
        try:
            if mode == "Code Database":
                from CherryAI.functions.glossaries import code_glossary_db
                rows = code_glossary_db.read_all_rows()
                return [
                    {"col1": r[0] if len(r) > 0 else "",
                     "col2": r[1] if len(r) > 1 else "",
                     "col3": r[2] if len(r) > 2 else ""}  # Pattern, Translation, Category
                    for r in rows
                ]
            else:  # Glossary
                from CherryAI.functions.glossary import read_unified_glossary
                glossary = read_unified_glossary()
                return [
                    {"col1": e.original, "col2": e.translation, "col3": e.notes}
                    for e in glossary.values()
                ]
        except Exception as exc:
            logger.warning("Failed to load global DB (%s): %s", mode, exc)
            return []

    def _save_global_db(
        self, mode: str, entries: List[Dict[str, str]]
    ) -> None:
        """Persist entries to the global TSV file.

        Phase 62: Glossary writes through ``write_unified_glossary()``.
        Code Database writes through ``code_glossary_db.write_all_rows()``.

        Args:
            mode: ``"Glossary"`` or ``"Code Database"``.
            entries: List of entry dicts with keys ``col1``/``col2``/``col3``.
        """
        try:
            if mode == "Code Database":
                from CherryAI.functions.glossaries import code_glossary_db
                rows = [
                    [e.get("col1", ""), e.get("col2", ""), e.get("col3", "")]
                    for e in entries
                ]
                code_glossary_db.write_all_rows(rows)
            else:  # Glossary
                from CherryAI.functions.glossary import (
                    read_unified_glossary,
                    write_unified_glossary,
                    GlossaryEntry,
                )
                # Preserve existing metadata (source, type, gender etc.) for
                # entries that had it; new entries get plain Notes only.
                existing = read_unified_glossary()
                new_glossary: dict[str, "GlossaryEntry"] = {}
                for item in entries:
                    original = item.get("col1", "").strip()
                    if not original:
                        continue
                    if original in existing:
                        # Update only translation & notes; keep metadata
                        e = existing[original]
                        e.translation = item.get("col2", "")
                        e.notes = item.get("col3", "")
                        new_glossary[original] = e
                    else:
                        new_glossary[original] = GlossaryEntry(
                            original=original,
                            translation=item.get("col2", ""),
                            notes=item.get("col3", ""),
                        )
                write_unified_glossary(new_glossary)
        except Exception as exc:
            logger.error("Failed to save global DB (%s): %s", mode, exc)

    def _refresh_global_database(self) -> None:
        """Reload the Global Glossary / Database treeview.

        Applies the current search filter.
        """
        for child in self._global_db_tree.get_children():
            self._global_db_tree.delete(child)

        mode = self._global_db_mode_var.get()
        search = self._global_db_search_var.get().strip().lower()

        # Adjust headings per mode
        if mode == "Code Database":
            self._global_db_tree.heading("col1", text="Pattern")
            self._global_db_tree.heading("col2", text="Translation")
            self._global_db_tree.heading("col3", text="Category")
        else:
            self._global_db_tree.heading("col1", text="Original")
            self._global_db_tree.heading("col2", text="Translation")
            self._global_db_tree.heading("col3", text="Notes")

        entries = self._load_global_db(mode)
        for entry in entries:
            c1 = entry.get("col1", "")
            c2 = entry.get("col2", "")
            c3 = entry.get("col3", "")
            if search:
                combined = f"{c1} {c2} {c3}".lower()
                if search not in combined:
                    continue
            self._global_db_tree.insert("", "end", values=(c1, c2, c3))

    def _add_global_db_entry(self) -> None:
        """Add a blank entry to the global database."""
        self._global_db_tree.insert("", "end", values=("", "", ""))
        self._sync_global_db_tree()

    def _remove_global_db_entry(self) -> None:
        """Remove selected entries from the global database."""
        selection = self._global_db_tree.selection()
        if not selection:
            return
        for item in selection:
            self._global_db_tree.delete(item)
        self._sync_global_db_tree()

    def _clear_global_database(self) -> None:
        """Clear all entries in the current global database mode."""
        mode = self._global_db_mode_var.get()
        if not messagebox.askyesno(
            "Confirm Clear",
            f"Remove all entries from Global {mode}?",
        ):
            return
        for child in self._global_db_tree.get_children():
            self._global_db_tree.delete(child)
        self._sync_global_db_tree()

    def _on_global_db_double_click(self, event: tk.Event) -> None:
        """Inline-edit a cell in the global database Treeview."""
        region = self._global_db_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self._global_db_tree.identify_column(event.x)
        item = self._global_db_tree.identify_row(event.y)
        if not item:
            return
        col_idx = int(column.replace("#", "")) - 1
        if col_idx < 0 or col_idx > 2:
            return
        self._start_global_db_inline_edit(item, col_idx)

    def _start_global_db_inline_edit(
        self, item: str, col_idx: int
    ) -> None:
        """Show an Entry widget over a global database cell.

        Args:
            item: Treeview item id.
            col_idx: Column index (0-2).
        """
        col_names = ("col1", "col2", "col3")
        try:
            bbox = self._global_db_tree.bbox(item, col_names[col_idx])
            if not bbox:
                return
        except tk.TclError:
            return

        x, y, width, height = bbox
        vals = self._global_db_tree.item(item, "values")
        current = vals[col_idx] if col_idx < len(vals) else ""

        entry = ttk.Entry(self._global_db_tree)
        entry.insert(0, str(current))
        entry.select_range(0, "end")
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()

        def on_confirm(event: Optional[tk.Event] = None) -> None:
            new_val = entry.get()
            entry.destroy()
            if new_val != str(current):
                new_vals = list(self._global_db_tree.item(item, "values"))
                while len(new_vals) <= col_idx:
                    new_vals.append("")
                new_vals[col_idx] = new_val
                self._global_db_tree.item(item, values=new_vals)
                self._sync_global_db_tree()

        def on_cancel(event: Optional[tk.Event] = None) -> None:
            entry.destroy()

        entry.bind("<Return>", on_confirm)
        entry.bind("<Tab>", on_confirm)
        entry.bind("<Escape>", on_cancel)
        entry.bind("<FocusOut>", on_confirm)

    def _sync_global_db_tree(self) -> None:
        """Persist current Treeview contents to the global JSON file."""
        mode = self._global_db_mode_var.get()
        entries: List[Dict[str, str]] = []
        for child in self._global_db_tree.get_children():
            vals = self._global_db_tree.item(child, "values")
            entries.append({
                "col1": vals[0] if len(vals) > 0 else "",
                "col2": vals[1] if len(vals) > 1 else "",
                "col3": vals[2] if len(vals) > 2 else "",
            })
        self._save_global_db(mode, entries)

    def _import_global_database(self) -> None:
        """Import entries from a TSV, JSON or CSV file into the global DB."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Import Global Database",
            filetypes=[("TSV files", "*.tsv"), ("JSON files", "*.json"), ("CSV files", "*.csv")],
            parent=self,
        )
        if not path:
            return
        try:
            file_path = Path(path)
            entries: List[Dict[str, str]] = []
            suffix = file_path.suffix.lower()
            if suffix in (".csv", ".tsv"):
                import csv
                delim = "\t" if suffix == ".tsv" else ","
                with open(file_path, "r", encoding="utf-8") as fh:
                    reader = csv.DictReader(fh, delimiter=delim)
                    for row in reader:
                        keys = list(row.keys())
                        entries.append({
                            "col1": row.get(keys[0], "") if keys else "",
                            "col2": row.get(keys[1], "") if len(keys) > 1 else "",
                            "col3": row.get(keys[2], "") if len(keys) > 2 else "",
                        })
            else:
                with open(file_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            entries.append({
                                "col1": str(item.get("col1", item.get("original", item.get("pattern", "")))),
                                "col2": str(item.get("col2", item.get("translation", item.get("category", "")))),
                                "col3": str(item.get("col3", item.get("notes", item.get("action", "")))),
                            })
            mode = self._global_db_mode_var.get()
            existing = self._load_global_db(mode)
            existing.extend(entries)
            self._save_global_db(mode, existing)
            self._refresh_global_database()
            messagebox.showinfo(
                "Import Complete",
                f"Imported {len(entries)} entries.",
            )
        except Exception as e:
            logger.error("Failed to import global DB: %s", e)
            messagebox.showerror("Import Error", str(e))

    def _export_global_database(self) -> None:
        """Export current global database to a TSV, JSON or CSV file."""
        from tkinter import filedialog
        mode = self._global_db_mode_var.get()
        default_name = (
            "codedatabase" if mode == "Code Database" else "globalglossary"
        )
        path = filedialog.asksaveasfilename(
            title="Export Global Database",
            defaultextension=".tsv",
            initialfile=default_name,
            filetypes=[("TSV files", "*.tsv"), ("CSV files", "*.csv"), ("JSON files", "*.json")],
            parent=self,
        )
        if not path:
            return
        try:
            entries = self._load_global_db(mode)
            file_path = Path(path)
            suffix = file_path.suffix.lower()
            if suffix in (".csv", ".tsv"):
                import csv
                delim = "\t" if suffix == ".tsv" else ","
                with open(file_path, "w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=["col1", "col2", "col3"], delimiter=delim)
                    writer.writeheader()
                    writer.writerows(entries)
            else:
                with open(file_path, "w", encoding="utf-8") as fh:
                    json.dump(entries, fh, ensure_ascii=False, indent=2)
            messagebox.showinfo(
                "Export Complete",
                f"Exported {len(entries)} entries to {file_path.name}.",
            )
        except Exception as e:
            logger.error("Failed to export global DB: %s", e)
            messagebox.showerror("Export Error", str(e))

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
        self._metadata.style = self._style_text.get("1.0", "end-1c")
        self._metadata.style_preset = self._style_preset_var.get()
        self._metadata.tone = self._tone_text.get("1.0", "end-1c")
        self._metadata.tone_preset = self._tone_preset_var.get()
        self._metadata.system_instructions = self._notes_text.get("1.0", "end-1c")
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

        # Populate style preset name and prompt text
        preset_name = self._metadata.style_preset
        if preset_name in self._style_presets:
            self._style_preset_var.set(preset_name)
        else:
            self._style_preset_var.set(CUSTOM_PRESET_NAME)
        self._style_text.delete("1.0", "end")
        style_text = self._metadata.style
        if not style_text and preset_name != CUSTOM_PRESET_NAME:
            style_text = self._style_presets.get(preset_name, "")
        self._style_text.insert("1.0", style_text)

        # Populate tone preset name and prompt text
        tone_name = self._metadata.tone_preset
        if tone_name in self._tone_presets:
            self._tone_preset_var.set(tone_name)
        else:
            self._tone_preset_var.set(CUSTOM_PRESET_NAME)
        self._tone_text.delete("1.0", "end")
        tone_text = self._metadata.tone
        if not tone_text and tone_name != CUSTOM_PRESET_NAME:
            tone_text = self._tone_presets.get(tone_name, "")
        self._tone_text.insert("1.0", tone_text)

        self._notes_text.delete("1.0", "end")
        self._notes_text.insert("1.0", self._metadata.system_instructions)

        self._refresh_character_list()
        self._refresh_code_pattern_list()  # TASK 18.2: Also refresh code patterns
        self._refresh_glossary_settings()  # TASK 19 Phase 4

    def _refresh_glossary_settings(self) -> None:
        """Refresh glossary settings from manifest and reload Knowledge Base.

        TASK 76: Reads ``use_global_glossary`` from manifest and syncs
        the Knowledge Base Enabled/Disabled button.  Then reloads the KB
        treeview from the global TSV files.
        """
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            config = mgr.get_glossary_config()
            if hasattr(self, "_kb_enabled_var"):
                self._kb_enabled_var.set(config.use_global)
                self._kb_enabled_btn.config(
                    text="Enabled" if config.use_global else "Disabled",
                )
        if hasattr(self, "_kb_tree"):
            self._refresh_kb()

    def _save_metadata(self) -> None:
        """Save metadata to session state (internal helper).

        Includes section toggle states so they survive the full
        metadata dict replacement.  No user-facing messagebox — the
        manifest auto-saves on tab change.
        """
        self._collect_metadata()
        data = self.get_step_data()
        meta_dict = self._metadata.to_dict()
        meta_dict["genre_enabled"] = self._genre_enabled_var.get()
        meta_dict["summary_enabled"] = self._summary_enabled_var.get()
        meta_dict["style_enabled"] = self._style_enabled_var.get()
        meta_dict["tone_enabled"] = self._tone_enabled_var.get()
        meta_dict["system_instructions_enabled"] = self._si_enabled_var.get()
        meta_dict["glossary_enabled"] = self._glossary_enabled_var.get()
        meta_dict["code_database_enabled"] = self._code_db_enabled_var.get()
        data["metadata"] = meta_dict
        data["inference_options"] = {
            "enabled": self._infer_enabled_var.get(),
            "infer_summary": self._infer_summary_var.get(),
            "infer_tone": self._infer_tone_var.get(),
            "infer_characters": self._infer_chars_var.get(),
            "sample_lines": self._sample_lines_var.get(),
        }
        self.set_step_data(data)

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
        """Get sample lines from manifest."""
        try:
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                all_lines = mgr.get_all_orig_lines()
            else:
                all_lines = []
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
                    original_name=name,
                    notes="Speaker",
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
        existing_names = {
            c.original_name or c.translation
            for c in self._metadata.characters
        }
        for char in result.characters:
            char_key = char.original_name or char.translation
            if char_key and char_key not in existing_names:
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

    def on_new_project(self) -> None:
        """Reset cached state for a fresh project."""
        super().on_new_project()
        self._is_inferring = False
        self._json_mode = False
        self._manifest_bindings.clear()

        # Reset section toggles to defaults
        for var, btn, default in [
            (self._genre_enabled_var, self._genre_toggle_btn, False),
            (self._summary_enabled_var, self._summary_toggle_btn, False),
            (self._style_enabled_var, self._style_toggle_btn, False),
            (self._tone_enabled_var, self._tone_toggle_btn, False),
            (self._si_enabled_var, self._si_toggle_btn, True),
            (self._glossary_enabled_var, self._glossary_toggle_btn, True),
            (self._code_db_enabled_var, self._code_db_toggle_btn, True),
        ]:
            var.set(default)
            btn.config(text="Enabled" if default else "Disabled")

        logger.debug("Information step reset for new project")

    def on_enter(self) -> None:
        """Called when step is entered.
        
        TASK 23.1: Load manifest bindings first, then legacy metadata.
        TASK 23.3: Load characters and code patterns from manifest.
        """
        # Refresh preset dicts from INI so all handlers always have current
        # data (reflects edits made in Global Options without a restart).
        self._style_presets = ini_manager.get_all_presets("style")
        self._tone_presets = ini_manager.get_all_presets("tone")
        self._si_presets = ini_manager.get_all_si_presets()
        self._style_preset_combo["values"] = list(self._style_presets.keys())
        self._tone_preset_combo["values"] = list(self._tone_presets.keys())
        self._si_preset_combo["values"] = list(self._si_presets.keys())

        # TASK 23.1: Load all manifest-bound fields
        self._load_from_manifest_bindings()
        
        # TASK 23.3: Load characters and code patterns from manifest
        self._load_characters_from_manifest()
        self._load_code_patterns_from_manifest()
        
        # Legacy: Load from session state (for backward compatibility)
        self._load_metadata()
        # Task 18.4: Import characters from Analysis step if available
        self._import_analysis_speakers()
        # Check for suggested project name from Input step
        self._apply_suggested_project_name()
        # Auto-import code patterns from Analysis if none exist
        self._auto_import_code_patterns()
        # Ensure style/tone text fields show preset content if empty
        self._ensure_style_tone_text()
        # Ensure summary and system instructions show defaults if empty
        self._ensure_default_texts()
        # Restore section toggle states from manifest
        self._load_section_toggles()
    
    def _load_from_manifest_bindings(self) -> None:
        """Load all manifest-bound fields from manifest.
        
        TASK 23.1: Uses binding system to populate widgets from manifest.
        """
        if self.manifest_manager is None or not self.manifest_manager.is_loaded:
            logger.debug("No manifest loaded, skipping binding load")
            return
        
        load_all_bindings(self._manifest_bindings)
        logger.debug("Loaded %d manifest bindings", len(self._manifest_bindings))

    def _load_section_toggles(self) -> None:
        """Restore section Enabled/Disabled toggle states from manifest.

        Reads ``*_enabled`` boolean flags from Information metadata and
        applies them to the corresponding BooleanVars, button labels, and
        widget states.  Also handles collapsible section collapse/expand.
        """
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return

        # Map: (meta_key, default, BooleanVar, Button, widgets_to_grey)
        simple_toggles: list[tuple] = [
            (
                "genre_enabled", False,
                self._genre_enabled_var, self._genre_toggle_btn,
                [self._genre_entry, self._genre_btn],
            ),
            (
                "summary_enabled", False,
                self._summary_enabled_var, self._summary_toggle_btn,
                [self._summary_text],
            ),
            (
                "style_enabled", False,
                self._style_enabled_var, self._style_toggle_btn,
                [self._style_text, self._style_preset_combo],
            ),
            (
                "tone_enabled", False,
                self._tone_enabled_var, self._tone_toggle_btn,
                [self._tone_text, self._tone_preset_combo],
            ),
            (
                "system_instructions_enabled", True,
                self._si_enabled_var, self._si_toggle_btn,
                [self._notes_text, self._si_preset_combo],
            ),
        ]

        for meta_key, default, var, btn, widgets in simple_toggles:
            val = mgr.get_info_metadata_field(meta_key, default)
            enabled = bool(val) if not isinstance(val, bool) else val
            var.set(enabled)
            btn.config(text="Enabled" if enabled else "Disabled")
            state = "normal" if enabled else "disabled"
            for w in widgets:
                try:
                    w.configure(state=state)
                except tk.TclError:
                    pass

        # Collapsible sections: Glossary, Code Database
        for meta_key, default, var, btn, widget_name in [
            (
                "glossary_enabled", True,
                self._glossary_enabled_var, self._glossary_toggle_btn,
                "glossary",
            ),
            (
                "code_database_enabled", True,
                self._code_db_enabled_var, self._code_db_toggle_btn,
                "code_database",
            ),
        ]:
            val = mgr.get_info_metadata_field(meta_key, default)
            enabled = bool(val) if not isinstance(val, bool) else val
            var.set(enabled)
            btn.config(text="Enabled" if enabled else "Disabled")

            collapse_btn = self._collapsible_buttons.get(widget_name)
            if enabled:
                if collapse_btn:
                    collapse_btn.configure(state="normal")
            else:
                if self._collapsible_state.get(widget_name, True):
                    self._toggle_collapsible(widget_name)
                if collapse_btn:
                    collapse_btn.configure(state="disabled")

        # Knowledge Base: also handle collapse on disable
        if hasattr(self, "_kb_enabled_var"):
            kb_val = self._kb_enabled_var.get()
            collapse_btn = self._collapsible_buttons.get("knowledge_base")
            if not kb_val:
                if self._collapsible_state.get("knowledge_base", True):
                    self._toggle_collapsible("knowledge_base")
                if collapse_btn:
                    collapse_btn.configure(state="disabled")
            else:
                if collapse_btn:
                    collapse_btn.configure(state="normal")

    def _ensure_style_tone_text(self) -> None:
        """Populate style, tone, and SI text fields with the selected preset.

        Called from ``on_enter`` after manifest bindings are loaded.
        For named (non-Custom) presets the text field is **always** overwritten
        with the current INI value so the user sees up-to-date preset content
        even when the manifest or session state stored a different string.
        Custom presets are not touched — the user's typed text is preserved.
        """
        # Style
        name = self._style_preset_var.get()
        if name and name != CUSTOM_PRESET_NAME:
            prompt_text = ini_manager.get_all_presets("style").get(name, "")
            self._style_text.delete("1.0", "end")
            if prompt_text:
                self._style_text.insert("1.0", prompt_text)

        # Tone
        name = self._tone_preset_var.get()
        if name and name != CUSTOM_PRESET_NAME:
            prompt_text = ini_manager.get_all_presets("tone").get(name, "")
            self._tone_text.delete("1.0", "end")
            if prompt_text:
                self._tone_text.insert("1.0", prompt_text)

        # System Instructions
        si_name = self._si_preset_var.get()
        if si_name and si_name != CUSTOM_PRESET_NAME:
            prompt_text = ini_manager.get_si_preset(si_name) or ""
            self._notes_text.delete("1.0", "end")
            if prompt_text:
                self._notes_text.insert("1.0", prompt_text)

    def _ensure_default_texts(self) -> None:
        """Populate Summary and System Instructions with defaults if empty.

        Called from ``on_enter`` after all loading is complete.
        """
        # Summary default — always read fresh from INI so user edits propagate.
        summary_text = self._summary_text.get("1.0", "end-1c").strip()
        if not summary_text:
            self._summary_text.delete("1.0", "end")
            self._summary_text.insert("1.0", ini_manager.get_default_text("Summary"))

        # System Instructions default — always read fresh from INI.
        notes_text = self._notes_text.get("1.0", "end-1c").strip()
        if not notes_text:
            self._notes_text.delete("1.0", "end")
            self._notes_text.insert("1.0", ini_manager.get_default_text("SystemInstruction"))
    
    def _save_characters_to_manifest(self) -> None:
        """Save character notes to manifest.
        
        TASK 23.3: Persist characters to manifest for project persistence.
        """
        if self.manifest_manager is None or not self.manifest_manager.is_loaded:
            return
        
        characters_data = [c.to_dict() for c in self._metadata.characters]
        save_character_notes(self.manifest_manager, characters_data)
        logger.debug("Saved %d characters to manifest", len(characters_data))
    
    def _load_characters_from_manifest(self) -> None:
        """Load character notes from manifest.
        
        TASK 23.3: Restore characters from manifest on step enter.
        """
        if self.manifest_manager is None or not self.manifest_manager.is_loaded:
            return
        
        characters_data = load_character_notes(self.manifest_manager)
        if characters_data:
            self._metadata.characters = [
                CharacterInfo.from_dict(c) for c in characters_data
            ]
            self._refresh_character_list()
            logger.debug("Loaded %d characters from manifest", len(characters_data))
    
    def _save_code_patterns_to_manifest(self) -> None:
        """Save code database patterns to manifest.
        
        TASK 23.3: Persist code patterns to manifest for project persistence.
        """
        if self.manifest_manager is None or not self.manifest_manager.is_loaded:
            return
        
        patterns_data = [p.to_dict() for p in self._metadata.code_patterns]
        save_code_glossary(self.manifest_manager, patterns_data)
        logger.debug("Saved %d code patterns to manifest", len(patterns_data))
    
    def _load_code_patterns_from_manifest(self) -> None:
        """Load code database patterns from manifest.
        
        TASK 23.3: Restore code patterns from manifest on step enter.
        """
        if self.manifest_manager is None or not self.manifest_manager.is_loaded:
            return
        
        patterns_data = load_code_glossary(self.manifest_manager)
        if patterns_data:
            self._metadata.code_patterns = [
                CodePattern.from_dict(p) for p in patterns_data
            ]
            self._refresh_code_pattern_list()
            logger.debug("Loaded %d code patterns from manifest", len(patterns_data))

    def _import_analysis_speakers(self) -> None:
        """Import detected speakers from Analysis step into Character Notes.

        This implements Task 18.4: Analysis to Information Glossary Integration.
        Transfers characters found during Analysis to the Character Notes widget,
        including gender inference based on speaker names.
        """
        try:
            # Get analysis results (prefers manifest, falls back to session)
            analysis_step_data = self._get_analysis_step_data()
            analysis_results = analysis_step_data.get("analysis_results", {})
            characters_data = analysis_results.get("characters", [])

            # Build speaker list from unified characters
            speaker_items: list = []
            if isinstance(characters_data, list):
                for entry in characters_data:
                    if isinstance(entry, dict) and entry.get("count", 0) > 0:
                        speaker_items.append((
                            entry.get("original_name", ""),
                            entry.get("count", 0),
                        ))

            if not speaker_items:
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
            speaker_items.sort(key=lambda x: x[1], reverse=True)

            for speaker_name, count in speaker_items[:20]:
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
                char = CharacterInfo(
                    original_name=speaker_name,
                    notes=gender,
                    count=count,
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
        """Apply project name from manifest or Input step if field is empty.

        Prefers the project_name in Information metadata (set during
        project creation) over the folder-name-based suggestion from
        Input step data.
        """
        # Only apply if project name is empty
        if self._project_name_var.get().strip():
            return

        try:
            # Prefer Information metadata project_name
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                manifest_name = mgr.get_info_metadata_field("project_name", "")
                if manifest_name and manifest_name.strip():
                    self._project_name_var.set(manifest_name.strip())
                    logger.debug(
                        "Applied manifest project name: %s", manifest_name,
                    )
                    return

            # Fallback: use suggested name from Input step (step 0)
            input_step_data = self.session.get_step(0).data
            suggested_name = input_step_data.get("suggested_project_name", "")

            if suggested_name:
                self._project_name_var.set(suggested_name)
                logger.debug(
                    "Applied suggested project name: %s", suggested_name,
                )
        except (AttributeError, KeyError, IndexError):
            pass
        except Exception as e:
            logger.debug(f"Could not apply suggested project name: {e}")

    def _auto_import_code_patterns(self) -> None:
        """Auto-import code patterns from Analysis if none exist.

        Silently imports code patterns detected during Analysis to the
        Code Database when no patterns are currently defined.  Reads
        from the unified ``code_patterns`` list.
        """
        # Only auto-import if no patterns exist
        if self._metadata.code_patterns:
            return

        try:
            # Get code patterns from Analysis step (step 1)
            analysis_step_data = self._get_analysis_step_data()
            analysis_results = analysis_step_data.get("analysis_results", {})
            code_patterns = analysis_results.get("code_patterns", [])

            imported_count = 0
            if isinstance(code_patterns, list):
                for entry in code_patterns:
                    if isinstance(entry, dict) and entry.get("count", 0) > 0:
                        pattern = CodePattern(
                            pattern=entry.get("pattern", ""),
                            category=entry.get("category", "Detected"),
                            action="preserve",
                            count=entry.get("count", 0),
                            raw_type=entry.get("raw_type", ""),
                            notes="",
                        )
                        self._metadata.code_patterns.append(pattern)
                        imported_count += 1

            if imported_count > 0:
                self._refresh_code_pattern_list()
                logger.info(
                    "Auto-imported %d code patterns from Analysis",
                    imported_count,
                )

        except (AttributeError, KeyError, IndexError):
            # Analysis step data not available
            pass
        except Exception as e:
            logger.debug("Could not auto-import code patterns: %s", e)

    def on_leave(self) -> None:
        """Called when leaving step.

        Collects form data and persists it together with section toggle
        states so that the ``*_enabled`` flags survive the full metadata
        dict replacement performed by ``set_step_data()``.
        """
        self._collect_metadata()
        data = self.get_step_data()
        meta_dict = self._metadata.to_dict()
        # Preserve section toggle states — these live in the manifest
        # metadata dict but are not part of ProjectMetadata.
        meta_dict["genre_enabled"] = self._genre_enabled_var.get()
        meta_dict["summary_enabled"] = self._summary_enabled_var.get()
        meta_dict["style_enabled"] = self._style_enabled_var.get()
        meta_dict["tone_enabled"] = self._tone_enabled_var.get()
        meta_dict["system_instructions_enabled"] = self._si_enabled_var.get()
        meta_dict["glossary_enabled"] = self._glossary_enabled_var.get()
        meta_dict["code_database_enabled"] = self._code_db_enabled_var.get()
        data["metadata"] = meta_dict
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
        self._character = character or CharacterInfo()

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

        # Notes (combined: gender, role, freeform)
        ttk.Label(main, text="Notes (gender, role, other info):").pack(
            anchor="w", pady=(10, 0),
        )
        self._notes_text = scrolledtext.ScrolledText(main, height=4, wrap="word")
        self._notes_text.pack(fill="x", pady=5)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="right")

    def _populate(self) -> None:
        """Populate fields from character."""
        self._name_var.set(self._character.translation)
        self._orig_var.set(self._character.original_name)
        if self._character.notes:
            self._notes_text.insert("1.0", self._character.notes)

    def _on_ok(self) -> None:
        """Handle OK button."""
        original_name = self._orig_var.get().strip()
        if not original_name:
            messagebox.showwarning("Required", "Original Name is required.")
            return

        self.result = CharacterInfo(
            translation=self._name_var.get().strip(),
            original_name=original_name,
            notes=self._notes_text.get("1.0", "end-1c").strip(),
        )
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.destroy()


class CodePatternDialog(tk.Toplevel):
    """Dialog for adding/editing code pattern information (TASK 18.5)."""

    # Common code pattern actions
    ACTIONS = [
        "preserve", "provides_context", "custom_placeholder",
        "protect", "strip_with_anchor", "part_of_span",
    ]

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

        # Translation
        row1b = ttk.Frame(main)
        row1b.pack(fill="x", pady=5)
        ttk.Label(row1b, text="Translation:", width=15).pack(side="left")
        self._translation_var = tk.StringVar()
        ttk.Entry(row1b, textvariable=self._translation_var).pack(
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
        self._translation_var.set(self._pattern.translation)
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
            translation=self._translation_var.get().strip(),
            category=self._category_var.get().strip(),
            action=self._action_var.get().strip() or "preserve",
            example=self._example_var.get().strip(),
            notes=self._notes_text.get("1.0", "end-1c").strip(),
        )
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.destroy()
