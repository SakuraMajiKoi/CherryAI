"""Translation style presets for CherryAI.

Pre-built style guides for common translation scenarios. Presets can be
applied via CLI or API to adjust translation tone, formality, and vocabulary.

Example:
    >>> preset = get_style_preset("fantasy_medieval")
    >>> print(preset.style_instructions)
    "Use medieval vocabulary and formal address..."
    
    >>> manager = StylePresetManager()
    >>> combined = manager.combine_presets(["fantasy_medieval", "archaic_english"])
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging


class StyleCategory(Enum):
    """Categories for style presets."""
    
    TIME_PERIOD = "time_period"
    CULTURAL = "cultural"
    GENRE = "genre"
    CHARACTER = "character"
    DIALECT = "dialect"


class Formality(Enum):
    """Formality levels for speech."""
    
    VERY_FORMAL = "very_formal"
    FORMAL = "formal"
    NEUTRAL = "neutral"
    CASUAL = "casual"
    VERY_CASUAL = "very_casual"


class HonorificHandling(Enum):
    """How to handle Japanese honorifics."""
    
    KEEP = "keep"           # Keep -san, -sama, -kun, etc.
    LOCALIZE = "localize"   # Convert to Mr., Miss, etc.
    REMOVE = "remove"       # Remove entirely


@dataclass
class StylePreset:
    """A translation style preset.
    
    Attributes:
        name: Unique preset identifier.
        display_name: Human-readable name.
        description: Brief description of the style.
        category: Category this preset belongs to.
        formality: Formality level.
        honorifics: How to handle honorifics.
        style_instructions: Main style guide text.
        vocabulary_notes: Specific vocabulary guidance.
        avoid_list: Things to avoid in translation.
        example_phrases: Example transformations.
    """
    name: str
    display_name: str
    description: str
    category: StyleCategory
    formality: Formality = Formality.NEUTRAL
    honorifics: HonorificHandling = HonorificHandling.LOCALIZE
    style_instructions: str = ""
    vocabulary_notes: List[str] = field(default_factory=list)
    avoid_list: List[str] = field(default_factory=list)
    example_phrases: Dict[str, str] = field(default_factory=dict)
    
    def to_prompt_text(self) -> str:
        """Convert preset to text suitable for inclusion in prompts.
        
        Returns:
            Formatted text block for system prompt.
        """
        sections = []
        
        # Main style header
        sections.append(f"TRANSLATION STYLE: {self.display_name}")
        sections.append(f"Formality: {self.formality.value.replace('_', ' ').title()}")
        
        if self.style_instructions:
            sections.append(f"\n{self.style_instructions}")
        
        # Vocabulary notes
        if self.vocabulary_notes:
            sections.append("\nVocabulary Guidelines:")
            for note in self.vocabulary_notes:
                sections.append(f"- {note}")
        
        # Things to avoid
        if self.avoid_list:
            sections.append("\nAvoid:")
            for item in self.avoid_list:
                sections.append(f"- {item}")
        
        # Example phrases
        if self.example_phrases:
            sections.append("\nExample Transformations:")
            for original, styled in self.example_phrases.items():
                sections.append(f"  \"{original}\" \u2192 \"{styled}\"")
        
        # Honorific handling note
        if self.honorifics != HonorificHandling.LOCALIZE:
            if self.honorifics == HonorificHandling.KEEP:
                sections.append("\nNote: Keep Japanese honorifics (-san, -sama, -kun, etc.)")
            elif self.honorifics == HonorificHandling.REMOVE:
                sections.append("\nNote: Remove honorifics entirely from names.")
        
        return "\n".join(sections)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category.value,
            "formality": self.formality.value,
            "honorifics": self.honorifics.value,
            "style_instructions": self.style_instructions,
            "vocabulary_notes": self.vocabulary_notes,
            "avoid_list": self.avoid_list,
            "example_phrases": self.example_phrases,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StylePreset":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            description=data.get("description", ""),
            category=StyleCategory(data.get("category", "genre")),
            formality=Formality(data.get("formality", "neutral")),
            honorifics=HonorificHandling(data.get("honorifics", "localize")),
            style_instructions=data.get("style_instructions", ""),
            vocabulary_notes=data.get("vocabulary_notes", []),
            avoid_list=data.get("avoid_list", []),
            example_phrases=data.get("example_phrases", {}),
        )


# ============================================================================
# Built-in Presets
# ============================================================================

BUILTIN_PRESETS: Dict[str, StylePreset] = {}


def _register_preset(preset: StylePreset) -> None:
    """Register a preset in the built-in registry."""
    BUILTIN_PRESETS[preset.name] = preset


# ----- Time Period Presets -----

_register_preset(StylePreset(
    name="archaic_english",
    display_name="Archaic English",
    description="Old English style with thee/thou and -eth verbs",
    category=StyleCategory.TIME_PERIOD,
    formality=Formality.VERY_FORMAL,
    style_instructions=(
        "Use Early Modern English conventions. Use 'thou/thee/thy' for singular "
        "informal address and 'you/your' for formal or plural. Apply '-eth' or '-est' "
        "verb endings where appropriate. Use 'hath', 'doth', 'art', 'dost'."
    ),
    vocabulary_notes=[
        "Use 'thou/thee/thy' for singular informal (friends, family, inferiors)",
        "Use 'you/your' for formal address or plural",
        "Replace 'has' with 'hath', 'does' with 'doth'",
        "Use 'art' for 'are' (thou art), 'dost' for 'do' (thou dost)",
        "Use '-eth' for third person singular (he goeth, she speaketh)",
        "Use 'wherefore' for 'why', 'whence' for 'from where'",
        "Use 'prithee' for 'please', 'methinks' for 'I think'",
    ],
    avoid_list=[
        "Modern contractions (don't, can't, won't)",
        "Contemporary slang",
        "Modern idioms",
    ],
    example_phrases={
        "Hello": "Hail",
        "What are you doing?": "What dost thou?",
        "He goes to the market": "He goeth to the market",
        "I think so": "Methinks it be so",
    },
))

_register_preset(StylePreset(
    name="victorian",
    display_name="Victorian English",
    description="Formal 19th century British style",
    category=StyleCategory.TIME_PERIOD,
    formality=Formality.FORMAL,
    style_instructions=(
        "Use formal Victorian-era English. Employ elaborate sentence structures, "
        "proper titles, and refined vocabulary. Maintain polite indirectness."
    ),
    vocabulary_notes=[
        "Use formal address: Sir, Madam, Miss, Master",
        "Use 'quite', 'rather', 'indeed' for emphasis",
        "Prefer longer, Latinate words over short Anglo-Saxon ones",
        "Use 'one' as impersonal pronoun where appropriate",
        "Employ passive voice for formality",
    ],
    avoid_list=[
        "Slang or colloquialisms",
        "Direct emotional expressions",
        "Modern technical terms",
    ],
    example_phrases={
        "Hey": "Good day",
        "That's cool": "How delightful",
        "I don't like it": "I find myself rather disinclined",
    },
))

_register_preset(StylePreset(
    name="modern_casual",
    display_name="Modern Casual",
    description="Contemporary informal speech",
    category=StyleCategory.TIME_PERIOD,
    formality=Formality.CASUAL,
    style_instructions=(
        "Use contemporary casual English. Include natural contractions, "
        "common expressions, and relaxed grammar typical of everyday speech."
    ),
    vocabulary_notes=[
        "Use contractions freely (don't, can't, it's)",
        "Use common expressions (you know, I mean, like)",
        "Keep sentences short and punchy",
        "Use active voice",
    ],
    avoid_list=[
        "Overly formal language",
        "Archaic terms",
        "Stiff or stilted phrasing",
    ],
    example_phrases={
        "I do not understand": "I don't get it",
        "That is very impressive": "That's really cool",
    },
))

# ----- Cultural/Regional Presets -----

_register_preset(StylePreset(
    name="british_english",
    display_name="British English",
    description="UK spellings and expressions",
    category=StyleCategory.CULTURAL,
    formality=Formality.NEUTRAL,
    style_instructions=(
        "Use British English conventions including spelling, idioms, and cultural references."
    ),
    vocabulary_notes=[
        "Use British spellings: colour, favour, honour, centre, theatre",
        "Use 'whilst' instead of 'while', 'amongst' for 'among'",
        "Use 'have got' instead of 'have'",
        "Use British terms: flat (apartment), lift (elevator), queue (line)",
        "Use British expressions: quite, rather, brilliant, cheers",
    ],
    avoid_list=[
        "American spellings (color, center, theater)",
        "American idioms",
    ],
))

_register_preset(StylePreset(
    name="american_english",
    display_name="American English",
    description="US spellings and expressions",
    category=StyleCategory.CULTURAL,
    formality=Formality.NEUTRAL,
    style_instructions=(
        "Use American English conventions including spelling, idioms, and cultural references."
    ),
    vocabulary_notes=[
        "Use American spellings: color, favor, honor, center, theater",
        "Use 'while' instead of 'whilst', 'among' for 'amongst'",
        "Use American terms: apartment, elevator, line, sidewalk",
        "Use American expressions: awesome, cool, totally",
    ],
    avoid_list=[
        "British spellings (colour, centre, theatre)",
        "British idioms (brilliant, cheers)",
    ],
))

_register_preset(StylePreset(
    name="formal_japanese",
    display_name="Formal Japanese Style",
    description="Preserve honorifics and formal speech patterns",
    category=StyleCategory.CULTURAL,
    formality=Formality.FORMAL,
    honorifics=HonorificHandling.KEEP,
    style_instructions=(
        "Maintain Japanese cultural formality. Keep honorific suffixes "
        "(-san, -sama, -kun, -chan, -sensei, -senpai). Preserve formal speech markers."
    ),
    vocabulary_notes=[
        "Keep -san, -sama, -kun, -chan, -sensei, -senpai intact",
        "Preserve 'Onii-chan', 'Onee-san', etc. for familial terms",
        "Keep formal greetings (bow references, formal apologies)",
        "Maintain humble/honorific speech distinctions where clear",
    ],
    avoid_list=[
        "Converting honorifics to Western equivalents",
        "Removing cultural context",
    ],
))

_register_preset(StylePreset(
    name="casual_japanese",
    display_name="Casual Japanese Style",
    description="Remove honorifics, casual speech",
    category=StyleCategory.CULTURAL,
    formality=Formality.CASUAL,
    honorifics=HonorificHandling.REMOVE,
    style_instructions=(
        "Translate in a natural casual English style. Remove Japanese honorifics "
        "and adapt cultural references for Western audiences."
    ),
    vocabulary_notes=[
        "Remove honorific suffixes entirely",
        "Convert familial terms to English equivalents",
        "Adapt cultural references for clarity",
        "Use natural English names without suffixes",
    ],
))

# ----- Genre Presets -----

_register_preset(StylePreset(
    name="fantasy_medieval",
    display_name="Fantasy Medieval",
    description="Medieval fantasy vocabulary and formal address",
    category=StyleCategory.GENRE,
    formality=Formality.FORMAL,
    style_instructions=(
        "Use vocabulary suitable for medieval fantasy settings. "
        "Include archaic terms for weapons, armor, and social structures."
    ),
    vocabulary_notes=[
        "Use 'sword', 'blade', 'steel' for weapons",
        "Use titles: Ser, Lord, Lady, Duke, Baron",
        "Use 'castle', 'keep', 'stronghold' appropriately",
        "Use 'quest', 'journey', 'pilgrimage' for travels",
        "Use 'gold', 'silver', 'coin' for currency",
        "Use 'aye' for 'yes', 'nay' for 'no' in dialogue",
    ],
    avoid_list=[
        "Modern technology references",
        "Contemporary slang",
        "Metric measurements (use leagues, hands, stone)",
    ],
    example_phrases={
        "Hello": "Well met",
        "Yes": "Aye",
        "No": "Nay",
        "friend": "comrade / companion",
    },
))

_register_preset(StylePreset(
    name="fantasy_eastern",
    display_name="Eastern Fantasy / Wuxia",
    description="Wuxia/Xianxia cultivation terminology",
    category=StyleCategory.GENRE,
    formality=Formality.FORMAL,
    style_instructions=(
        "Use terminology common in wuxia/xianxia fantasy. Include cultivation "
        "terms, martial arts vocabulary, and Eastern philosophical concepts."
    ),
    vocabulary_notes=[
        "Use cultivation terms: qi, meridians, dantian, realm",
        "Use rank terms: Junior Brother, Senior Sister, Elder, Patriarch",
        "Use sect terminology: outer/inner disciple, core formation",
        "Use martial terms: palm technique, sword intent, body cultivation",
        "Preserve or adapt cultivation realm names",
    ],
    avoid_list=[
        "Western fantasy terms (mana, knights)",
        "Modern technology",
    ],
    example_phrases={
        "power": "cultivation base",
        "magic": "qi / spiritual energy",
        "teacher": "master / shifu",
    },
))

_register_preset(StylePreset(
    name="noir_detective",
    display_name="Noir Detective",
    description="Hardboiled prose and period slang",
    category=StyleCategory.GENRE,
    formality=Formality.CASUAL,
    style_instructions=(
        "Use hardboiled detective fiction style. Short, punchy sentences. "
        "Cynical worldview. Period-appropriate slang from 1930s-50s."
    ),
    vocabulary_notes=[
        "Use period slang: dame, gumshoe, copper, gat",
        "Short, declarative sentences",
        "First-person cynical observations",
        "Metaphors involving shadows, rain, cigarettes",
    ],
    avoid_list=[
        "Flowery language",
        "Optimistic tone",
        "Modern slang",
    ],
    example_phrases={
        "woman": "dame",
        "detective": "gumshoe / private eye",
        "gun": "gat / piece / heater",
        "police": "cops / coppers",
    },
))

_register_preset(StylePreset(
    name="romance_flowery",
    display_name="Romance Flowery",
    description="Emotional, descriptive, poetic style",
    category=StyleCategory.GENRE,
    formality=Formality.NEUTRAL,
    style_instructions=(
        "Use emotionally evocative, descriptive language. Include sensory details, "
        "metaphors, and romantic imagery. Focus on feelings and atmosphere."
    ),
    vocabulary_notes=[
        "Use emotional vocabulary freely",
        "Include sensory descriptions (touch, scent, warmth)",
        "Use romantic metaphors (heart, soul, flame)",
        "Describe physical reactions to emotions (trembling, blushing)",
    ],
    avoid_list=[
        "Clinical or cold language",
        "Purely action-focused descriptions",
    ],
))

_register_preset(StylePreset(
    name="horror_gothic",
    display_name="Gothic Horror",
    description="Atmospheric, archaic, foreboding tone",
    category=StyleCategory.GENRE,
    formality=Formality.FORMAL,
    style_instructions=(
        "Use atmospheric horror language. Include archaic vocabulary, "
        "foreboding descriptions, and unsettling imagery."
    ),
    vocabulary_notes=[
        "Use words evoking dread: eldritch, miasma, sepulchral",
        "Describe darkness, shadows, decay",
        "Use formal, slightly archaic sentence structures",
        "Include sensory unease (cold, wet, rotting smells)",
    ],
    avoid_list=[
        "Modern slang",
        "Light or humorous tone",
        "Contemporary references",
    ],
))

# ----- Character Presets -----

_register_preset(StylePreset(
    name="noble_aristocrat",
    display_name="Noble Aristocrat",
    description="Refined, formal, occasionally condescending",
    category=StyleCategory.CHARACTER,
    formality=Formality.VERY_FORMAL,
    style_instructions=(
        "Speak as a refined aristocrat. Use formal address, elaborate vocabulary, "
        "and occasionally condescending or dismissive tone toward commoners."
    ),
    vocabulary_notes=[
        "Use 'one' as self-reference occasionally",
        "Use elaborate polite phrases",
        "Reference breeding, propriety, station",
        "Use subtle condescension markers",
    ],
    avoid_list=[
        "Slang or vulgar language",
        "Simple or direct phrasing",
        "Overly familiar address",
    ],
))

_register_preset(StylePreset(
    name="street_slang",
    display_name="Street Slang",
    description="Urban vernacular and colloquialisms",
    category=StyleCategory.CHARACTER,
    formality=Formality.VERY_CASUAL,
    style_instructions=(
        "Use urban street vernacular. Include slang, dropped letters, "
        "and casual speech patterns. Avoid overly specific regional markers."
    ),
    vocabulary_notes=[
        "Use contractions heavily",
        "Drop word endings (goin', nothin')",
        "Use general urban slang (yo, dude, man)",
        "Keep it natural, not stereotypical",
    ],
    avoid_list=[
        "Formal or academic language",
        "Complete/proper sentences always",
    ],
))

_register_preset(StylePreset(
    name="child_innocent",
    display_name="Child/Innocent",
    description="Simple words, curious tone",
    category=StyleCategory.CHARACTER,
    formality=Formality.CASUAL,
    style_instructions=(
        "Speak with childlike wonder and simplicity. Use simple vocabulary, "
        "ask questions, show curiosity, and express emotions directly."
    ),
    vocabulary_notes=[
        "Use simple, short words",
        "Ask questions frequently (Why? What's that?)",
        "Express emotions directly",
        "Mispronounce difficult words occasionally",
        "Use 'really', 'super', 'so' for emphasis",
    ],
    avoid_list=[
        "Complex vocabulary",
        "Cynical or jaded expressions",
        "Adult topics or references",
    ],
))

_register_preset(StylePreset(
    name="elderly_wise",
    display_name="Elderly Wise",
    description="Proverbs, measured speech, wisdom",
    category=StyleCategory.CHARACTER,
    formality=Formality.FORMAL,
    style_instructions=(
        "Speak with the measured wisdom of age. Use proverbs, offer advice, "
        "speak slowly and deliberately. Reference experience and the past."
    ),
    vocabulary_notes=[
        "Include proverbs and folk wisdom",
        "Speak of 'back in my day' experiences",
        "Use measured, thoughtful phrasing",
        "Offer gentle advice and warnings",
    ],
    avoid_list=[
        "Rushed or hurried speech",
        "Modern slang or trends",
        "Impatient expressions",
    ],
))

_register_preset(StylePreset(
    name="military_formal",
    display_name="Military Formal",
    description="Orders, ranks, protocol",
    category=StyleCategory.CHARACTER,
    formality=Formality.VERY_FORMAL,
    style_instructions=(
        "Use military speech patterns. Short, direct orders. Proper rank usage. "
        "Protocol and chain of command. Disciplined language."
    ),
    vocabulary_notes=[
        "Use ranks properly (Sir, Ma'am, Captain, Private)",
        "Give direct orders (Move out, Hold position)",
        "Use military time and terminology",
        "Report in structured format",
    ],
    avoid_list=[
        "Casual chitchat during operations",
        "Ignoring rank structure",
        "Emotional outbursts",
    ],
))

_register_preset(StylePreset(
    name="pirate_nautical",
    display_name="Pirate/Nautical",
    description="Nautical terms and pirate speech",
    category=StyleCategory.CHARACTER,
    formality=Formality.CASUAL,
    style_instructions=(
        "Use pirate and nautical speech patterns. Include 'arr' and 'me hearty' "
        "sparingly. Use nautical terminology authentically."
    ),
    vocabulary_notes=[
        "Use nautical terms: port, starboard, bow, stern",
        "Use 'ye' for 'you', 'me' for 'my'",
        "Use pirate expressions: arr, ahoy, avast, shiver me timbers",
        "Reference sea, ships, treasure, crew",
    ],
    avoid_list=[
        "Land-based metaphors",
        "Formal or aristocratic speech",
    ],
    example_phrases={
        "Hello": "Ahoy",
        "friend": "matey / me hearty",
        "money": "gold / doubloons / treasure",
        "yes": "aye",
    },
))

_register_preset(StylePreset(
    name="robot_mechanical",
    display_name="Robot/Mechanical",
    description="Precise, clinical, technical",
    category=StyleCategory.CHARACTER,
    formality=Formality.NEUTRAL,
    style_instructions=(
        "Speak in precise, mechanical patterns. Use technical terminology. "
        "No contractions. Logical, unemotional phrasing."
    ),
    vocabulary_notes=[
        "No contractions (do not, cannot, will not)",
        "Use precise numbers and measurements",
        "State probability and calculations",
        "Reference protocols and parameters",
        "Use 'Unit' or designation for self-reference",
    ],
    avoid_list=[
        "Contractions",
        "Emotional expressions",
        "Slang or idioms",
        "Imprecise language",
    ],
    example_phrases={
        "I think": "Analysis indicates",
        "Maybe": "Probability: 47%",
        "Hello": "Greetings. Unit designation: [name]",
    },
))


# ============================================================================
# StylePresetManager
# ============================================================================

class StylePresetManager:
    """Manager for loading and combining style presets.
    
    Handles built-in presets and user-defined presets from config folder.
    """
    
    def __init__(self, custom_preset_dir: Optional[str] = None):
        """Initialize the preset manager.
        
        Args:
            custom_preset_dir: Path to folder with custom preset files.
        """
        self.logger = logging.getLogger("cherryai.style_presets")
        self.custom_preset_dir = Path(custom_preset_dir) if custom_preset_dir else None
        self._custom_presets: Dict[str, StylePreset] = {}
        
        if self.custom_preset_dir and self.custom_preset_dir.exists():
            self._load_custom_presets()
    
    def _load_custom_presets(self) -> None:
        """Load custom presets from the custom preset directory."""
        if not self.custom_preset_dir or not self.custom_preset_dir.exists():
            return
        
        for file_path in self.custom_preset_dir.glob("*.txt"):
            try:
                preset = self._parse_preset_file(file_path)
                if preset:
                    self._custom_presets[preset.name] = preset
                    self.logger.debug(f"Loaded custom preset: {preset.name}")
            except Exception as e:
                self.logger.warning(f"Failed to load preset {file_path}: {e}")
    
    def _parse_preset_file(self, file_path: Path) -> Optional[StylePreset]:
        """Parse a preset from a text file.
        
        Expected format:
            name: preset_name
            display_name: Display Name
            description: Brief description
            category: genre
            formality: formal
            honorifics: keep
            ---
            style_instructions go here
            multiple lines allowed
            ---
            VOCABULARY:
            - Note 1
            - Note 2
            ---
            AVOID:
            - Item 1
            - Item 2
        """
        content = file_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        
        # Parse header
        header: Dict[str, str] = {}
        section_start = 0
        
        for i, line in enumerate(lines):
            if line.strip() == "---":
                section_start = i + 1
                break
            if ":" in line:
                key, value = line.split(":", 1)
                header[key.strip().lower()] = value.strip()
        
        if "name" not in header:
            return None
        
        # Parse remaining sections
        sections: Dict[str, List[str]] = {"style": [], "vocabulary": [], "avoid": []}
        current_section = "style"
        
        for line in lines[section_start:]:
            stripped = line.strip()
            if stripped == "---":
                continue
            elif stripped.upper() == "VOCABULARY:":
                current_section = "vocabulary"
            elif stripped.upper() == "AVOID:":
                current_section = "avoid"
            elif stripped.startswith("- "):
                sections[current_section].append(stripped[2:])
            elif stripped:
                sections[current_section].append(stripped)
        
        # Build preset
        category = StyleCategory.GENRE
        if header.get("category") in [c.value for c in StyleCategory]:
            category = StyleCategory(header["category"])
        
        formality = Formality.NEUTRAL
        if header.get("formality") in [f.value for f in Formality]:
            formality = Formality(header["formality"])
        
        honorifics = HonorificHandling.LOCALIZE
        if header.get("honorifics") in [h.value for h in HonorificHandling]:
            honorifics = HonorificHandling(header["honorifics"])
        
        return StylePreset(
            name=header["name"],
            display_name=header.get("display_name", header["name"]),
            description=header.get("description", ""),
            category=category,
            formality=formality,
            honorifics=honorifics,
            style_instructions="\n".join(sections["style"]),
            vocabulary_notes=sections["vocabulary"],
            avoid_list=sections["avoid"],
        )
    
    def get_preset(self, name: str) -> Optional[StylePreset]:
        """Get a preset by name.
        
        Checks custom presets first, then built-in presets.
        
        Args:
            name: Preset name (case-insensitive).
            
        Returns:
            StylePreset or None if not found.
        """
        name_lower = name.lower()
        
        # Check custom presets first
        if name_lower in self._custom_presets:
            return self._custom_presets[name_lower]
        
        # Check built-in presets
        if name_lower in BUILTIN_PRESETS:
            return BUILTIN_PRESETS[name_lower]
        
        return None
    
    def list_presets(self, category: Optional[StyleCategory] = None) -> List[StylePreset]:
        """List available presets.
        
        Args:
            category: Optional category filter.
            
        Returns:
            List of matching presets.
        """
        all_presets = {**BUILTIN_PRESETS, **self._custom_presets}
        
        if category:
            return [p for p in all_presets.values() if p.category == category]
        
        return list(all_presets.values())
    
    def list_preset_names(self) -> List[str]:
        """Get list of all preset names.
        
        Returns:
            Sorted list of preset names.
        """
        all_names = list(BUILTIN_PRESETS.keys()) + list(self._custom_presets.keys())
        return sorted(set(all_names))
    
    def combine_presets(self, names: List[str]) -> Optional[StylePreset]:
        """Combine multiple presets into one.
        
        Later presets override earlier ones. Instructions are concatenated.
        
        Args:
            names: List of preset names to combine.
            
        Returns:
            Combined StylePreset or None if no valid presets found.
        """
        presets = []
        for name in names:
            preset = self.get_preset(name)
            if preset:
                presets.append(preset)
        
        if not presets:
            return None
        
        if len(presets) == 1:
            return presets[0]
        
        # Combine presets
        combined_name = "_".join(p.name for p in presets)
        combined_display = " + ".join(p.display_name for p in presets)
        
        # Last preset wins for enum values
        final = presets[-1]
        
        # Combine instructions
        all_instructions = []
        for p in presets:
            if p.style_instructions:
                all_instructions.append(f"[{p.display_name}]\n{p.style_instructions}")
        
        # Combine vocabulary and avoid lists
        all_vocab: List[str] = []
        all_avoid: List[str] = []
        seen_vocab: Set[str] = set()
        seen_avoid: Set[str] = set()
        
        for p in presets:
            for v in p.vocabulary_notes:
                if v not in seen_vocab:
                    all_vocab.append(v)
                    seen_vocab.add(v)
            for a in p.avoid_list:
                if a not in seen_avoid:
                    all_avoid.append(a)
                    seen_avoid.add(a)
        
        # Combine example phrases
        all_examples: Dict[str, str] = {}
        for p in presets:
            all_examples.update(p.example_phrases)
        
        return StylePreset(
            name=combined_name,
            display_name=combined_display,
            description=f"Combined preset: {', '.join(p.name for p in presets)}",
            category=final.category,
            formality=final.formality,
            honorifics=final.honorifics,
            style_instructions="\n\n".join(all_instructions),
            vocabulary_notes=all_vocab,
            avoid_list=all_avoid,
            example_phrases=all_examples,
        )


# ============================================================================
# Helper Functions
# ============================================================================

def get_style_preset(name: str) -> Optional[StylePreset]:
    """Get a built-in style preset by name.
    
    Args:
        name: Preset name (case-insensitive).
        
    Returns:
        StylePreset or None if not found.
    """
    return BUILTIN_PRESETS.get(name.lower())


def list_style_presets() -> List[str]:
    """Get list of built-in preset names.
    
    Returns:
        Sorted list of preset names.
    """
    return sorted(BUILTIN_PRESETS.keys())


def list_presets_by_category() -> Dict[str, List[str]]:
    """Get presets grouped by category.
    
    Returns:
        Dictionary mapping category names to preset names.
    """
    result: Dict[str, List[str]] = {}
    for preset in BUILTIN_PRESETS.values():
        cat_name = preset.category.value
        if cat_name not in result:
            result[cat_name] = []
        result[cat_name].append(preset.name)
    
    # Sort each category
    for cat in result:
        result[cat] = sorted(result[cat])
    
    return result


def parse_style_preset_arg(arg: str) -> List[str]:
    """Parse style preset argument string.
    
    Args:
        arg: Comma-separated preset names (e.g., "fantasy_medieval,archaic_english").
        
    Returns:
        List of preset names.
    """
    if not arg:
        return []
    return [name.strip().lower() for name in arg.split(",") if name.strip()]


def get_preset_description(name: str) -> Optional[str]:
    """Get description for a preset.
    
    Args:
        name: Preset name.
        
    Returns:
        Description string or None if not found.
    """
    preset = get_style_preset(name)
    return preset.description if preset else None


def create_style_manager(custom_dir: Optional[str] = None) -> StylePresetManager:
    """Factory function to create a StylePresetManager.
    
    Args:
        custom_dir: Optional path to custom presets folder.
        
    Returns:
        Configured StylePresetManager instance.
    """
    return StylePresetManager(custom_preset_dir=custom_dir)
