"""
Conditional Prompt Instructions for CherryAI.

Provides a system for pattern-triggered instructions that are injected
into the system prompt only when relevant patterns are detected in the batch.

This reduces token usage and keeps prompts focused on what's actually present.

Dynamic Instructions (TASK 5):
- Instructions are generated dynamically based on detected patterns
- Only shows examples for patterns actually present in the batch
- Reduces token usage by omitting irrelevant examples
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# Default path for user customization
DEFAULT_CONDITIONS_FILE = "user/conditional_prompts.json"


@dataclass
class ConditionalPrompt:
    """A conditional prompt instruction triggered by pattern detection.
    
    Attributes:
        name: Unique identifier for this condition
        description: Human-readable description
        patterns: List of regex patterns that trigger this condition
        instruction: The prompt instruction to inject when triggered
        priority: Higher priority = appears earlier in prompt (default 50)
        enabled: Whether this condition is active
        category: Grouping category (code, format, content, etc.)
        pattern_examples: Dict mapping patterns to human-readable examples
    """
    name: str
    description: str
    patterns: List[str]
    instruction: str
    priority: int = 50
    enabled: bool = True
    category: str = "general"
    pattern_examples: Dict[str, str] = field(default_factory=dict)
    
    def matches(self, text: str) -> Tuple[bool, Set[str]]:
        """Check if any patterns match the text.
        
        Returns:
            Tuple of (matched: bool, matched_patterns: Set[str])
        """
        matched_patterns: Set[str] = set()
        for pattern in self.patterns:
            try:
                if re.search(pattern, text):
                    matched_patterns.add(pattern)
            except re.error:
                # Invalid regex, skip
                pass
        return len(matched_patterns) > 0, matched_patterns
    
    def get_dynamic_instruction(self, matched_patterns: Set[str]) -> str:
        """Generate a dynamic instruction with only relevant examples.
        
        Args:
            matched_patterns: Set of pattern strings that matched
        
        Returns:
            Instruction with relevant examples only
        """
        if not self.pattern_examples:
            return self.instruction
        
        # Collect examples for matched patterns
        examples = []
        for pattern in matched_patterns:
            if pattern in self.pattern_examples:
                examples.append(self.pattern_examples[pattern])
        
        if not examples:
            return self.instruction
        
        # Build instruction with examples
        examples_str = ", ".join(sorted(set(examples)))
        return f"{self.instruction} (e.g., {examples_str})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "name": self.name,
            "description": self.description,
            "patterns": self.patterns,
            "instruction": self.instruction,
            "priority": self.priority,
            "enabled": self.enabled,
            "category": self.category,
        }
        if self.pattern_examples:
            result["pattern_examples"] = self.pattern_examples
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConditionalPrompt:
        """Deserialize from dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            patterns=data.get("patterns", []),
            instruction=data.get("instruction", ""),
            priority=data.get("priority", 50),
            enabled=data.get("enabled", True),
            category=data.get("category", "general"),
            pattern_examples=data.get("pattern_examples", {}),
        )


# ============================================================================
# Built-in Conditional Prompts
# ============================================================================

# Code Protection Tokens
CONDITION_PROT_TOKEN = ConditionalPrompt(
    name="prot_token",
    description="Protected code tokens (__PROTECTED__, __COLOR__, __FONT__)",
    patterns=[
        r"__PROTECTED__",
        r"__PROTECTED_\d+__",
        r"__CODE_PROTECTED_\d+__",
        r"__COLOR__",
        r"__COLOR_\d+__",
        r"__FONT__",
        r"__FONT_\d+__",
    ],
    instruction="Protected tokens must be preserved exactly - same position, count, spelling.",
    priority=100,
    category="code",
    pattern_examples={
        r"__PROTECTED__": "__PROTECTED__",
        r"__PROTECTED_\d+__": "__PROTECTED_1__",
        r"__CODE_PROTECTED_\d+__": "__CODE_PROTECTED_5__",
        r"__COLOR__": "__COLOR__",
        r"__COLOR_\d+__": "__COLOR_2__",
        r"__FONT__": "__FONT__",
        r"__FONT_\d+__": "__FONT_1__",
    },
)

# Deduplication Markers
CONDITION_DEDUP_TOKEN = ConditionalPrompt(
    name="dedup_token",
    description="Deduplication markers (__DEDUP__)",
    patterns=[r"__DEDUP__", r"_DEDUP__"],
    instruction="__DEDUP__ lines are duplicate placeholders. Output unchanged - filled automatically.",
    priority=95,
    category="code",
    pattern_examples={
        r"__DEDUP__": "__DEDUP__",
        r"_DEDUP__": "_DEDUP__",
    },
)

# Temporary Replacement Values
CONDITION_TEMPREPL = ConditionalPrompt(
    name="temp_replacement",
    description="Temporary replacement values (names like Steve)",
    patterns=[r"__TEMPREPL_\d+_\d+__"],
    instruction="__TEMPREPL_X_Y__ tokens are temp placeholders. Preserve exactly.",
    priority=90,
    category="code",
    pattern_examples={
        r"__TEMPREPL_\d+_\d+__": "__TEMPREPL_1_0__",
    },
)

# Bracket-based Anchors
CONDITION_BRACKETS = ConditionalPrompt(
    name="brackets",
    description="Square, curly, or angle brackets",
    patterns=[r"\[.*?\]", r"\{.*?\}", r"<[^>]+>"],
    instruction="Preserve bracketed content - keep code/variables unchanged.",
    priority=80,
    category="anchors",
    pattern_examples={
        r"\[.*?\]": "[name]",
        r"\{.*?\}": "{var}",
        r"<[^>]+>": "<tag>",
    },
)

# Japanese/Asian Brackets
CONDITION_JP_BRACKETS = ConditionalPrompt(
    name="jp_brackets",
    description="Japanese-style brackets (「」『』【】《》)",
    patterns=[r"「.*?」", r"『.*?』", r"【.*?】", r"《.*?》"],
    instruction='Convert JP brackets appropriately.',
    priority=75,
    category="format",
    pattern_examples={
        r"「.*?」": '「text」→"text"',
        r"『.*?』": '『text』→"text"',
        r"【.*?】": "【text】→[text]",
        r"《.*?》": "《text》→<text>",
    },
)

# Color Codes
CONDITION_COLOR_CODES = ConditionalPrompt(
    name="color_codes",
    description="Color formatting codes (\\c[N])",
    patterns=[r"\\c\[\d+\]", r"\\c\[#[0-9A-Fa-f]+\]"],
    instruction="Preserve color codes exactly in original positions.",
    priority=70,
    category="code",
    pattern_examples={
        r"\\c\[\d+\]": "\\c[4]",
        r"\\c\[#[0-9A-Fa-f]+\]": "\\c[#FF0000]",
    },
)

# Variable References
CONDITION_VARIABLES = ConditionalPrompt(
    name="variables",
    description="Variable references (\\v[N], \\n[N])",
    patterns=[r"\\v\[\d+\]", r"\\n\[\d+\]", r"\\N\[\d+\]", r"\\V\[\d+\]"],
    instruction="Preserve variable refs exactly - they display game data.",
    priority=70,
    category="code",
    pattern_examples={
        r"\\v\[\d+\]": "\\v[15]",
        r"\\n\[\d+\]": "\\n[1]",
        r"\\N\[\d+\]": "\\N[2]",
        r"\\V\[\d+\]": "\\V[10]",
    },
)

# Sound/Media Commands
CONDITION_MEDIA = ConditionalPrompt(
    name="media_commands",
    description="Sound and media commands (\\se[], \\pic[], etc.)",
    patterns=[r"\\se\[.*?\]", r"\\SE\[.*?\]", r"\\pic\[.*?\]", r"\\wait\[\d+\]", r"\\fadein\[\d+\]"],
    instruction="Preserve media commands exactly. Don't translate content.",
    priority=70,
    category="code",
    pattern_examples={
        r"\\se\[.*?\]": "\\se[sound]",
        r"\\SE\[.*?\]": "\\SE[beep]",
        r"\\pic\[.*?\]": "\\pic[image]",
        r"\\wait\[\d+\]": "\\wait[60]",
        r"\\fadein\[\d+\]": "\\fadein[30]",
    },
)

# Text Formatting
CONDITION_FORMATTING = ConditionalPrompt(
    name="text_formatting",
    description="Text formatting codes (\\fb, \\fr, \\i[], \\n, etc.)",
    patterns=[r"\\fb", r"\\fr", r"\\i\[\d+\]", r"\\b", r"\\n(?!\[\d+\])"],
    instruction="Preserve formatting codes exactly.",
    priority=65,
    category="code",
    pattern_examples={
        r"\\fb": "\\fb",
        r"\\fr": "\\fr",
        r"\\i\[\d+\]": "\\i[2]",
        r"\\b": "\\b",
        r"\\n(?!\[\d+\])": "\\n",
    },
)

# Ruby Text / Furigana
CONDITION_RUBY = ConditionalPrompt(
    name="ruby_text",
    description="Ruby text / Furigana (\\rb[text,reading])",
    patterns=[r"\\rb\[.*?,.*?\]"],
    instruction="Preserve \\rb[] furigana structure. May translate base text.",
    priority=60,
    category="code",
    pattern_examples={
        r"\\rb\[.*?,.*?\]": "\\rb[漢字,かんじ]",
    },
)

# Ellipsis Patterns
CONDITION_ELLIPSIS = ConditionalPrompt(
    name="ellipsis",
    description="Ellipsis patterns (…, ……, ...)",
    patterns=[r"…+", r"\.\.\.+"],
    instruction="Preserve ellipsis patterns in their positions.",
    priority=40,
    category="format",
    pattern_examples={
        r"…+": "…",
        r"\.\.\.+": "...",
    },
)

# Speaker Tags
CONDITION_SPEAKER = ConditionalPrompt(
    name="speaker_tags",
    description="Speaker name prefixes (Name: or Name：)",
    patterns=[r"^[^\s:：]+[:：]\s*", r"「[^」]+」"],
    instruction="Translate speaker names from glossary. Keep Name: format.",
    priority=30,
    category="content",
    pattern_examples={
        r"^[^\s:：]+[:：]\s*": "Name:",
        r"「[^」]+」": "「dialogue」",
    },
)

# Speaker Dialogue Format Preservation
CONDITION_SPEAKER_FORMAT = ConditionalPrompt(
    name="speaker_dialogue_format",
    description="Speaker: \"Dialogue\" format with balanced quotes",
    patterns=[
        # Name followed by colon (or fullwidth), then quote
        r"^[^\s:：]+[:：]\s*[\"'「『""'（(]",
        # Fullwidth colon variant
        r"^[^\s:：]+：\s*「",
    ],
    instruction="Preserve Speaker: \"Dialogue\" format. Keep colon between name and quote. Maintain balanced quotes.",
    priority=32,
    category="format",
    pattern_examples={
        r"^[^\s:：]+[:：]\s*[\"'「『""'（(]": 'Name: "text"',
        r"^[^\s:：]+：\s*「": "名前：「text」",
    },
)

# Line Break Tags (HTML-style)
CONDITION_BR_TAGS = ConditionalPrompt(
    name="br_tags",
    description="HTML line break tags (<br>, <br/>, <br />)",
    patterns=[r"<br\s*/?\s*>", r"<BR\s*/?\s*>"],
    instruction="Preserve line break tags exactly. Keep count and position. Don't add/remove.",
    priority=85,
    category="code",
    pattern_examples={
        r"<br\s*/?\s*>": "<br>",
        r"<BR\s*/?\s*>": "<BR/>",
    },
)

# Newline escape sequences
CONDITION_NEWLINE = ConditionalPrompt(
    name="newline_escape",
    description="Newline escape sequences (\\n literal)",
    patterns=[r"(?<!\\)\\n(?!\[)"],
    instruction="Preserve \\n newline escapes exactly in position.",
    priority=84,
    category="code",
    pattern_examples={
        r"(?<!\\)\\n(?!\[)": "\\n",
    },
)


# ============================================================================
# Merged Request Instruction (Step 5 — Efficient Mode)
# ============================================================================


def build_merged_request_instruction(merge_boundaries: List[int]) -> str:
    """Build a conditional instruction describing line relatedness in a
    merged request.

    When Efficient mode merges small requests across file boundaries
    (Step 5), the resulting request contains blocks of lines from
    different files.  This function generates a human-readable
    description so the model understands the block structure.

    Args:
        merge_boundaries: List of line counts for each original block,
            e.g. ``[2, 1, 3]`` means three merged blocks of 2, 1, and
            3 lines.

    Returns:
        Instruction string, or empty string when not a merged request.

    Examples:
        >>> build_merged_request_instruction([1, 1, 1])
        'All lines are unrelated to each other.'
        >>> build_merged_request_instruction([3, 2])
        ('This request has lines unrelated to each other. '
         'The first block ends with line 3. '
         'The next block starts at line 4.')
    """
    if not merge_boundaries or len(merge_boundaries) < 2:
        return ""

    # All single-line blocks → every line is unrelated
    if all(b == 1 for b in merge_boundaries):
        return "All lines are unrelated to each other."

    # Mixed: describe block boundaries with relative line numbers
    parts: List[str] = [
        "This request has lines unrelated to each other.",
    ]
    offset = 0
    for idx, size in enumerate(merge_boundaries):
        block_start = offset + 1
        block_end = offset + size
        if idx == 0:
            parts.append(f"The first block ends with line {block_end}.")
        elif idx == len(merge_boundaries) - 1:
            parts.append(
                f"The last block starts at line {block_start}.",
            )
        else:
            parts.append(
                f"The next block is lines {block_start}\u2013{block_end}.",
            )
        offset += size

    return " ".join(parts)


# ============================================================================
# Built-in Conditions Registry
# ============================================================================

BUILTIN_CONDITIONS: List[ConditionalPrompt] = [
    CONDITION_PROT_TOKEN,
    CONDITION_DEDUP_TOKEN,
    CONDITION_TEMPREPL,
    CONDITION_BRACKETS,
    CONDITION_JP_BRACKETS,
    CONDITION_BR_TAGS,
    CONDITION_NEWLINE,
    CONDITION_COLOR_CODES,
    CONDITION_VARIABLES,
    CONDITION_MEDIA,
    CONDITION_FORMATTING,
    CONDITION_RUBY,
    CONDITION_ELLIPSIS,
    CONDITION_SPEAKER,
    CONDITION_SPEAKER_FORMAT,
]


# ============================================================================
# Conditional Prompt Manager
# ============================================================================

class ConditionalPromptManager:
    """Manages conditional prompt detection and injection.
    
    Loads built-in conditions and user customizations, then evaluates
    text batches to determine which instructions to inject.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the manager.
        
        Args:
            config_dir: Directory containing conditional_prompts.json (optional)
        """
        self.logger = logging.getLogger("cherryai.conditional_prompts")
        self.config_dir = config_dir or Path("user")
        self.conditions: Dict[str, ConditionalPrompt] = {}
        
        self._load_builtin_conditions()
        self._load_user_conditions()
    
    def _load_builtin_conditions(self) -> None:
        """Load built-in conditional prompts."""
        import copy
        for condition in BUILTIN_CONDITIONS:
            # Deep copy to avoid modifying global defaults
            self.conditions[condition.name] = copy.deepcopy(condition)
        self.logger.debug(f"Loaded {len(BUILTIN_CONDITIONS)} built-in conditions")
    
    def _load_user_conditions(self) -> None:
        """Load user-defined conditions from JSON file."""
        config_path = self.config_dir / "conditional_prompts.json"
        if not config_path.exists():
            return
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Handle overrides for built-in conditions
            overrides = data.get("overrides", {})
            for name, override in overrides.items():
                if name in self.conditions:
                    # Apply overrides (enabled, priority, instruction, etc.)
                    condition = self.conditions[name]
                    if "enabled" in override:
                        condition.enabled = override["enabled"]
                    if "priority" in override:
                        condition.priority = override["priority"]
                    if "instruction" in override:
                        condition.instruction = override["instruction"]
                    if "patterns" in override:
                        condition.patterns = override["patterns"]
            
            # Load custom conditions
            custom = data.get("custom", [])
            for item in custom:
                condition = ConditionalPrompt.from_dict(item)
                self.conditions[condition.name] = condition
            
            self.logger.info(
                f"Loaded user conditions: {len(overrides)} overrides, {len(custom)} custom"
            )
        except Exception as e:
            self.logger.warning(f"Failed to load user conditions: {e}")
    
    def save_user_conditions(self) -> None:
        """Save current conditions to user config file."""
        config_path = self.config_dir / "conditional_prompts.json"
        
        # Separate built-in (with overrides) from custom
        overrides = {}
        custom = []
        
        builtin_names = {c.name for c in BUILTIN_CONDITIONS}
        
        for name, condition in self.conditions.items():
            if name in builtin_names:
                # Check if this differs from default
                default = next((c for c in BUILTIN_CONDITIONS if c.name == name), None)
                if default:
                    override: Dict[str, Any] = {}
                    if condition.enabled != default.enabled:
                        override["enabled"] = condition.enabled
                    if condition.priority != default.priority:
                        override["priority"] = condition.priority
                    if condition.instruction != default.instruction:
                        override["instruction"] = condition.instruction
                    if condition.patterns != default.patterns:
                        override["patterns"] = condition.patterns
                    if override:
                        overrides[name] = override
            else:
                # Custom condition
                custom.append(condition.to_dict())
        
        data = {
            "_description": "Conditional prompt customizations for CherryAI",
            "_instructions": (
                "Use 'overrides' to modify built-in conditions (enabled, priority, instruction, patterns). "
                "Use 'custom' to add your own conditions."
            ),
            "overrides": overrides,
            "custom": custom,
        }
        
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved conditions to {config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save conditions: {e}")
    
    def evaluate_batch(self, lines: List[str]) -> List[Tuple[ConditionalPrompt, Set[str]]]:
        """Evaluate which conditions match a batch of text.
        
        Args:
            lines: List of text lines to evaluate
        
        Returns:
            List of (condition, matched_patterns) tuples, sorted by priority (highest first)
        """
        batch_text = "\n".join(lines)
        matches: List[Tuple[ConditionalPrompt, Set[str]]] = []
        
        for condition in self.conditions.values():
            if not condition.enabled:
                continue
            matched, patterns = condition.matches(batch_text)
            if matched:
                matches.append((condition, patterns))
        
        # Sort by priority (highest first)
        matches.sort(key=lambda x: x[0].priority, reverse=True)
        return matches
    
    def build_conditional_instructions(self, lines: List[str]) -> str:
        """Build the conditional instructions block for a batch.
        
        Args:
            lines: List of text lines
        
        Returns:
            Formatted instruction block to append to system prompt
        """
        matches = self.evaluate_batch(lines)
        
        if not matches:
            return ""
        
        # Group by category for organized output
        by_category: Dict[str, List[Tuple[ConditionalPrompt, Set[str]]]] = {}
        for condition, patterns in matches:
            category = condition.category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((condition, patterns))
        
        # Build instruction block
        parts: List[str] = ["\n\n# Special Handling Instructions\n"]
        parts.append("The following patterns were detected in this batch:\n")
        
        # Group similar instructions to reduce token usage
        grouped_instructions = self._group_similar_instructions(matches)
        
        # Order categories: code first, then format, then content, then general
        category_order = ["code", "anchors", "format", "content", "general"]
        sorted_categories = sorted(
            grouped_instructions.keys(),
            key=lambda c: category_order.index(c) if c in category_order else len(category_order)
        )
        
        for category in sorted_categories:
            groups = grouped_instructions[category]
            for group_name, instruction, examples in groups:
                if examples:
                    examples_str = ", ".join(sorted(set(examples)))
                    parts.append(f"\n**{group_name}**: {instruction} (e.g., {examples_str})\n")
                else:
                    parts.append(f"\n**{group_name}**: {instruction}\n")
        
        return "".join(parts)
    
    def _group_similar_instructions(
        self, matches: List[Tuple[ConditionalPrompt, Set[str]]]
    ) -> Dict[str, List[Tuple[str, str, List[str]]]]:
        """Group similar instructions to reduce token usage.
        
        Combines conditions with similar instructions (e.g., "preserve exactly")
        into single grouped instructions.
        
        Args:
            matches: List of (condition, matched_patterns) tuples
            
        Returns:
            Dict mapping category to list of (group_name, instruction, examples)
        """
        # Define grouping rules for similar instructions
        PRESERVE_EXACTLY_KEYWORDS = ["preserve", "exactly", "unchanged", "keep"]
        
        by_category: Dict[str, List[Tuple[ConditionalPrompt, Set[str]]]] = {}
        for condition, patterns in matches:
            category = condition.category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((condition, patterns))
        
        result: Dict[str, List[Tuple[str, str, List[str]]]] = {}
        
        for category, items in by_category.items():
            # Sort by priority within category
            items.sort(key=lambda x: x[0].priority, reverse=True)
            
            # Try to group "preserve exactly" type instructions for code category
            if category == "code":
                preserve_group: List[Tuple[ConditionalPrompt, Set[str]]] = []
                other_items: List[Tuple[ConditionalPrompt, Set[str]]] = []
                
                for condition, patterns in items:
                    instr_lower = condition.instruction.lower()
                    # Check if this is a "preserve exactly" type instruction
                    if any(kw in instr_lower for kw in PRESERVE_EXACTLY_KEYWORDS):
                        preserve_group.append((condition, patterns))
                    else:
                        other_items.append((condition, patterns))
                
                category_groups: List[Tuple[str, str, List[str]]] = []
                
                # If we have multiple preserve-type items, combine them
                if len(preserve_group) >= 2:
                    all_examples: List[str] = []
                    group_names: List[str] = []
                    for condition, patterns in preserve_group:
                        group_names.append(condition.name.upper())
                        for pattern in patterns:
                            if pattern in condition.pattern_examples:
                                all_examples.append(condition.pattern_examples[pattern])
                    
                    # Create combined instruction
                    combined_name = "CODE_TOKENS"
                    combined_instruction = (
                        "These tokens must be preserved exactly - same position, count, spelling. "
                        "Do not translate, modify, or remove them."
                    )
                    category_groups.append((combined_name, combined_instruction, all_examples))
                else:
                    # Not enough to group, add individually
                    for condition, patterns in preserve_group:
                        instruction = condition.get_dynamic_instruction(patterns)
                        category_groups.append((condition.name.upper(), instruction, []))
                
                # Add non-grouped items
                for condition, patterns in other_items:
                    instruction = condition.get_dynamic_instruction(patterns)
                    category_groups.append((condition.name.upper(), instruction, []))
                
                result[category] = category_groups
            else:
                # For other categories, don't group, just output individually
                category_groups = []
                for condition, patterns in items:
                    instruction = condition.get_dynamic_instruction(patterns)
                    category_groups.append((condition.name.upper(), instruction, []))
                result[category] = category_groups
        
        return result
    
    def get_condition(self, name: str) -> Optional[ConditionalPrompt]:
        """Get a condition by name."""
        return self.conditions.get(name)
    
    def set_condition_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a condition.
        
        Returns:
            True if condition exists and was updated
        """
        if name in self.conditions:
            self.conditions[name].enabled = enabled
            return True
        return False
    
    def add_custom_condition(self, condition: ConditionalPrompt) -> None:
        """Add or replace a custom condition."""
        self.conditions[condition.name] = condition
    
    def remove_condition(self, name: str) -> bool:
        """Remove a custom condition.
        
        Built-in conditions cannot be removed, only disabled.
        
        Returns:
            True if condition was removed
        """
        builtin_names = {c.name for c in BUILTIN_CONDITIONS}
        if name in builtin_names:
            self.logger.warning(f"Cannot remove built-in condition '{name}'. Use disable instead.")
            return False
        if name in self.conditions:
            del self.conditions[name]
            return True
        return False
    
    def list_conditions(self, category: Optional[str] = None, enabled_only: bool = False) -> List[ConditionalPrompt]:
        """List all conditions, optionally filtered.
        
        Args:
            category: Filter by category (code, format, content, etc.)
            enabled_only: Only return enabled conditions
        
        Returns:
            List of conditions sorted by priority
        """
        result = list(self.conditions.values())
        
        if category:
            result = [c for c in result if c.category == category]
        if enabled_only:
            result = [c for c in result if c.enabled]
        
        result.sort(key=lambda c: c.priority, reverse=True)
        return result


# ============================================================================
# Convenience Functions
# ============================================================================

def create_default_config(config_dir: Path = Path("user")) -> Path:
    """Create a default conditional_prompts.json file with documentation.
    
    Returns:
        Path to the created file
    """
    config_path = config_dir / "conditional_prompts.json"
    
    data = {
        "_description": "Conditional prompt customizations for CherryAI",
        "_instructions": (
            "This file allows you to customize how CherryAI instructs the AI based on "
            "detected patterns in the text. Use 'overrides' to modify built-in conditions "
            "(enabled, priority, instruction, patterns). Use 'custom' to add your own conditions."
        ),
        "_builtin_conditions": [c.name for c in BUILTIN_CONDITIONS],
        "overrides": {
            "_example": {
                "_comment": "Example: disable the ellipsis condition",
                "enabled": False,
            }
        },
        "custom": [
            {
                "_comment": "Example custom condition",
                "name": "my_custom_pattern",
                "description": "My custom pattern detection",
                "patterns": ["\\[MY_TAG\\]"],
                "instruction": "Preserve [MY_TAG] tokens exactly.",
                "priority": 85,
                "enabled": False,
                "category": "code",
            }
        ],
    }
    
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return config_path
