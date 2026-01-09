"""Auto-tagging system for CherryAI Manifest v2.1.

This module provides automatic content classification and tagging for
translation lines. It detects content types, assigns severity levels,
and calculates quality scores.

Features:
- Content type detection (dialogue, system, item_name, quest, etc.)
- Status tracking (needs_review, approved, rejected, etc.)
- Severity level assignment based on content importance
- Quality scoring based on translation metrics
- Pattern-based auto-tagging rules

Usage:
    from CherryAI.functions.auto_tagger import AutoTagger, ContentTag, StatusTag
    
    tagger = AutoTagger()
    tags = tagger.analyze_line("Speaker: \"Hello!\"")
    # tags.content_type == ContentTag.DIALOGUE
    # tags.severity == SeverityLevel.LOW
    # tags.quality_score == 85
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


__all__ = [
    "ContentTag",
    "StatusTag",
    "SeverityLevel",
    "LineTag",
    "LineTags",
    "TagRule",
    "AutoTagger",
    "QualityMetrics",
    "create_auto_tagger",
    "get_content_tag_description",
    "get_status_tag_description",
    "get_severity_description",
    "list_content_tags",
    "list_status_tags",
    "list_severity_levels",
]


class ContentTag(Enum):
    """Content type classification for translation lines."""
    
    UNKNOWN = auto()  # Default / unclassified
    DIALOGUE = auto()  # Character speech, conversations
    SYSTEM = auto()  # System messages, UI text
    ITEM_NAME = auto()  # Item/weapon/equipment names
    ITEM_DESC = auto()  # Item/weapon descriptions
    SKILL_NAME = auto()  # Skill/ability/spell names
    SKILL_DESC = auto()  # Skill/ability descriptions
    QUEST_NAME = auto()  # Quest/mission titles
    QUEST_DESC = auto()  # Quest/mission descriptions
    LOCATION = auto()  # Place/area/region names
    CHARACTER = auto()  # Character/NPC names
    LORE = auto()  # Background lore, world-building
    TUTORIAL = auto()  # Tutorial/help text
    MENU = auto()  # Menu items, buttons, labels
    ERROR = auto()  # Error messages
    PLACEHOLDER = auto()  # Placeholder/template text
    CODE = auto()  # Code/technical content (should not translate)
    TITLE = auto()  # Game title, chapter titles


class StatusTag(Enum):
    """Translation status for workflow tracking."""
    
    PENDING = auto()  # Not yet translated
    IN_PROGRESS = auto()  # Currently being translated
    TRANSLATED = auto()  # Initial translation complete
    NEEDS_REVIEW = auto()  # Flagged for review
    REVIEWED = auto()  # Review complete
    APPROVED = auto()  # Final approval
    REJECTED = auto()  # Rejected, needs redo
    SKIPPED = auto()  # Intentionally skipped
    ERROR = auto()  # Translation failed
    LOCKED = auto()  # Locked, do not modify


class SeverityLevel(Enum):
    """Importance/priority level for translation lines."""
    
    TRIVIAL = 0  # Lowest priority (debug text, internal)
    LOW = 1  # Low priority (tooltips, flavor text)
    MEDIUM = 2  # Normal priority (standard content)
    HIGH = 3  # High priority (critical UI, quests)
    CRITICAL = 4  # Highest priority (story-critical)


# Content tag descriptions for display
CONTENT_TAG_DESCRIPTIONS: Dict[ContentTag, str] = {
    ContentTag.UNKNOWN: "Unclassified content",
    ContentTag.DIALOGUE: "Character speech and conversations",
    ContentTag.SYSTEM: "System messages and UI text",
    ContentTag.ITEM_NAME: "Item, weapon, or equipment names",
    ContentTag.ITEM_DESC: "Item or weapon descriptions",
    ContentTag.SKILL_NAME: "Skill, ability, or spell names",
    ContentTag.SKILL_DESC: "Skill or ability descriptions",
    ContentTag.QUEST_NAME: "Quest or mission titles",
    ContentTag.QUEST_DESC: "Quest or mission descriptions",
    ContentTag.LOCATION: "Place, area, or region names",
    ContentTag.CHARACTER: "Character or NPC names",
    ContentTag.LORE: "Background lore and world-building",
    ContentTag.TUTORIAL: "Tutorial and help text",
    ContentTag.MENU: "Menu items, buttons, and labels",
    ContentTag.ERROR: "Error messages",
    ContentTag.PLACEHOLDER: "Placeholder or template text",
    ContentTag.CODE: "Code or technical content",
    ContentTag.TITLE: "Game or chapter titles",
}

# Status tag descriptions
STATUS_TAG_DESCRIPTIONS: Dict[StatusTag, str] = {
    StatusTag.PENDING: "Awaiting translation",
    StatusTag.IN_PROGRESS: "Translation in progress",
    StatusTag.TRANSLATED: "Initial translation complete",
    StatusTag.NEEDS_REVIEW: "Flagged for review",
    StatusTag.REVIEWED: "Review completed",
    StatusTag.APPROVED: "Final approval granted",
    StatusTag.REJECTED: "Rejected, requires redo",
    StatusTag.SKIPPED: "Intentionally skipped",
    StatusTag.ERROR: "Translation failed",
    StatusTag.LOCKED: "Locked, do not modify",
}

# Severity level descriptions
SEVERITY_DESCRIPTIONS: Dict[SeverityLevel, str] = {
    SeverityLevel.TRIVIAL: "Lowest priority (debug, internal)",
    SeverityLevel.LOW: "Low priority (tooltips, flavor)",
    SeverityLevel.MEDIUM: "Normal priority (standard)",
    SeverityLevel.HIGH: "High priority (critical UI)",
    SeverityLevel.CRITICAL: "Highest priority (story-critical)",
}


@dataclass
class LineTag:
    """A single tag applied to a line.
    
    Attributes:
        name: Tag name/identifier.
        value: Optional value for the tag.
        source: How the tag was applied ("auto", "manual", "rule").
        confidence: Confidence level for auto-tags (0.0-1.0).
    """
    name: str
    value: Optional[str] = None
    source: str = "auto"
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {"name": self.name, "source": self.source}
        if self.value is not None:
            result["value"] = self.value
        if self.confidence < 1.0:
            result["confidence"] = self.confidence
        return result
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "LineTag":
        """Create from dictionary."""
        return LineTag(
            name=data.get("name", ""),
            value=data.get("value"),
            source=data.get("source", "auto"),
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class LineTags:
    """Complete tag set for a line entry.
    
    Attributes:
        content_type: Content classification tag.
        status: Translation workflow status.
        severity: Priority/importance level.
        quality_score: Quality rating (0-100).
        custom_tags: Additional custom tags.
        flags: Boolean flags (e.g., "has_code", "has_speaker").
    """
    content_type: ContentTag = ContentTag.UNKNOWN
    status: StatusTag = StatusTag.PENDING
    severity: SeverityLevel = SeverityLevel.MEDIUM
    quality_score: Optional[int] = None
    custom_tags: List[LineTag] = field(default_factory=list)
    flags: Set[str] = field(default_factory=set)
    
    def add_tag(self, name: str, value: Optional[str] = None,
                source: str = "manual", confidence: float = 1.0) -> None:
        """Add a custom tag."""
        self.custom_tags.append(LineTag(name, value, source, confidence))
    
    def add_flag(self, flag: str) -> None:
        """Add a boolean flag."""
        self.flags.add(flag)
    
    def has_flag(self, flag: str) -> bool:
        """Check if a flag is set."""
        return flag in self.flags
    
    def get_tag(self, name: str) -> Optional[LineTag]:
        """Get a custom tag by name."""
        for tag in self.custom_tags:
            if tag.name == name:
                return tag
        return None
    
    def remove_tag(self, name: str) -> bool:
        """Remove a custom tag by name. Returns True if removed."""
        for i, tag in enumerate(self.custom_tags):
            if tag.name == name:
                del self.custom_tags[i]
                return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary with sparse storage."""
        result: Dict[str, Any] = {}
        
        # Only include non-default values
        if self.content_type != ContentTag.UNKNOWN:
            result["content_type"] = self.content_type.name
        if self.status != StatusTag.PENDING:
            result["status"] = self.status.name
        if self.severity != SeverityLevel.MEDIUM:
            result["severity"] = self.severity.name
        if self.quality_score is not None:
            result["quality_score"] = self.quality_score
        if self.custom_tags:
            result["custom_tags"] = [t.to_dict() for t in self.custom_tags]
        if self.flags:
            result["flags"] = sorted(list(self.flags))
        
        return result
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "LineTags":
        """Create from dictionary."""
        content_type = ContentTag.UNKNOWN
        if "content_type" in data:
            try:
                content_type = ContentTag[data["content_type"]]
            except KeyError:
                pass
        
        status = StatusTag.PENDING
        if "status" in data:
            try:
                status = StatusTag[data["status"]]
            except KeyError:
                pass
        
        severity = SeverityLevel.MEDIUM
        if "severity" in data:
            try:
                severity = SeverityLevel[data["severity"]]
            except KeyError:
                pass
        
        custom_tags = []
        if "custom_tags" in data:
            custom_tags = [LineTag.from_dict(t) for t in data["custom_tags"]]
        
        flags = set(data.get("flags", []))
        
        return LineTags(
            content_type=content_type,
            status=status,
            severity=severity,
            quality_score=data.get("quality_score"),
            custom_tags=custom_tags,
            flags=flags,
        )


@dataclass
class QualityMetrics:
    """Quality metrics for translation assessment.
    
    Attributes:
        placeholder_preserved: All placeholders intact.
        length_ratio: Translated length / original length.
        has_untranslated: Contains untranslated source text.
        has_repetition: Contains repetitive patterns.
        bracket_balanced: All brackets properly balanced.
        issues: List of identified issues.
    """
    placeholder_preserved: bool = True
    length_ratio: float = 1.0
    has_untranslated: bool = False
    has_repetition: bool = False
    bracket_balanced: bool = True
    issues: List[str] = field(default_factory=list)
    
    def calculate_score(self) -> int:
        """Calculate quality score from 0-100.
        
        Returns:
            Quality score with deductions for issues.
        """
        score = 100
        
        # Major deductions
        if not self.placeholder_preserved:
            score -= 30
        if self.has_untranslated:
            score -= 20
        if self.has_repetition:
            score -= 15
        if not self.bracket_balanced:
            score -= 10
        
        # Length ratio deduction (too long or too short)
        if self.length_ratio < 0.3 or self.length_ratio > 4.0:
            score -= 15
        elif self.length_ratio < 0.5 or self.length_ratio > 3.0:
            score -= 10
        elif self.length_ratio < 0.7 or self.length_ratio > 2.0:
            score -= 5
        
        # Per-issue deduction
        score -= len(self.issues) * 2
        
        return max(0, min(100, score))


@dataclass
class TagRule:
    """Rule for automatic content tagging.
    
    Attributes:
        name: Rule identifier.
        pattern: Regex pattern to match.
        content_type: Content type to assign on match.
        severity: Severity level to assign (optional).
        flags: Flags to set on match.
        priority: Rule priority (higher = checked first).
    """
    name: str
    pattern: str
    content_type: ContentTag
    severity: Optional[SeverityLevel] = None
    flags: List[str] = field(default_factory=list)
    priority: int = 0
    _compiled: Optional[re.Pattern] = field(default=None, repr=False)
    
    def __post_init__(self):
        """Compile the regex pattern."""
        try:
            self._compiled = re.compile(self.pattern, re.IGNORECASE | re.UNICODE)
        except re.error:
            self._compiled = None
    
    def matches(self, text: str) -> bool:
        """Check if the rule matches the text."""
        if self._compiled is None:
            return False
        return bool(self._compiled.search(text))


# Default tagging rules
DEFAULT_RULES: List[TagRule] = [
    # Dialogue patterns
    TagRule(
        name="speaker_dialogue",
        pattern=r'^[「『【\[]?[\w\s]+[」』】\]]?\s*[:：]\s*[「『"""\'「].+[」』"""\'」]?$',
        content_type=ContentTag.DIALOGUE,
        severity=SeverityLevel.MEDIUM,
        flags=["has_speaker"],
        priority=100,
    ),
    TagRule(
        name="quoted_text",
        pattern=r'^[「『"""].+[」』"""]$',
        content_type=ContentTag.DIALOGUE,
        priority=90,
    ),
    
    # System/UI patterns
    TagRule(
        name="system_message",
        pattern=r'(セーブ|ロード|設定|オプション|終了|戻る|確認|キャンセル)',
        content_type=ContentTag.SYSTEM,
        severity=SeverityLevel.LOW,
        priority=80,
    ),
    TagRule(
        name="menu_item",
        pattern=r'^(New Game|Load|Save|Options|Settings|Exit|Quit|Back|OK|Cancel|Yes|No)$',
        content_type=ContentTag.MENU,
        severity=SeverityLevel.LOW,
        priority=85,
    ),
    
    # Item patterns
    TagRule(
        name="item_name_jp",
        pattern=r'(のアイテム|を手に入れた|を入手|を獲得)',
        content_type=ContentTag.ITEM_NAME,
        severity=SeverityLevel.HIGH,
        priority=70,
    ),
    TagRule(
        name="item_received",
        pattern=r'(received|obtained|acquired)\s+.+',
        content_type=ContentTag.ITEM_NAME,
        priority=70,
    ),
    
    # Quest patterns
    TagRule(
        name="quest_start",
        pattern=r'(クエスト|ミッション|依頼).*(開始|受注|発生)',
        content_type=ContentTag.QUEST_NAME,
        severity=SeverityLevel.HIGH,
        priority=75,
    ),
    TagRule(
        name="quest_complete",
        pattern=r'(Quest|Mission)\s+(Start|Complete|Failed)',
        content_type=ContentTag.QUEST_NAME,
        priority=75,
    ),
    
    # Tutorial patterns
    TagRule(
        name="tutorial_jp",
        pattern=r'(チュートリアル|操作説明|使い方|ヘルプ)',
        content_type=ContentTag.TUTORIAL,
        severity=SeverityLevel.MEDIUM,
        priority=60,
    ),
    TagRule(
        name="tutorial_en",
        pattern=r'^(Tutorial|Help|How to|Instructions):',
        content_type=ContentTag.TUTORIAL,
        priority=60,
    ),
    
    # Error patterns
    TagRule(
        name="error_message",
        pattern=r'(Error|エラー|失敗|Failed|Invalid)',
        content_type=ContentTag.ERROR,
        severity=SeverityLevel.LOW,
        flags=["is_error"],
        priority=65,
    ),
    
    # Code/technical patterns
    TagRule(
        name="has_code",
        pattern=r'(__\w+__|<[^>]+>|\$\{[^}]+\}|%[sd]|\\[nrt])',
        content_type=ContentTag.UNKNOWN,  # Don't override content type
        flags=["has_code"],
        priority=50,
    ),
    
    # Location patterns
    TagRule(
        name="location_jp",
        pattern=r'(町|村|城|森|洞窟|山|海|湖|神殿|塔)$',
        content_type=ContentTag.LOCATION,
        priority=40,
    ),
    
    # Placeholder patterns
    TagRule(
        name="placeholder_text",
        pattern=r'^(\?\?\?|XXX|TBD|TODO|FIXME|N/A)$',
        content_type=ContentTag.PLACEHOLDER,
        severity=SeverityLevel.TRIVIAL,
        priority=95,
    ),
]


class AutoTagger:
    """Automatic content tagger for translation lines.
    
    Analyzes text and assigns appropriate tags, severity levels,
    and quality scores based on content patterns.
    
    Attributes:
        rules: List of TagRule objects for pattern matching.
        enable_quality: Whether to calculate quality scores.
    """
    
    def __init__(
        self,
        rules: Optional[List[TagRule]] = None,
        enable_quality: bool = True
    ):
        """Initialize the auto-tagger.
        
        Args:
            rules: Custom rules (uses defaults if None).
            enable_quality: Enable quality score calculation.
        """
        self.rules = sorted(
            rules if rules is not None else DEFAULT_RULES,
            key=lambda r: -r.priority
        )
        self.enable_quality = enable_quality
    
    def analyze_line(
        self,
        original: str,
        translated: Optional[str] = None,
        existing_tags: Optional[LineTags] = None
    ) -> LineTags:
        """Analyze a line and generate tags.
        
        Args:
            original: Original source text.
            translated: Translated text (optional).
            existing_tags: Existing tags to update (optional).
            
        Returns:
            LineTags with detected tags and scores.
        """
        tags = existing_tags or LineTags()
        
        # Apply rules in priority order
        for rule in self.rules:
            if rule.matches(original):
                # Set content type if not UNKNOWN
                if rule.content_type != ContentTag.UNKNOWN:
                    if tags.content_type == ContentTag.UNKNOWN:
                        tags.content_type = rule.content_type
                
                # Set severity if specified
                if rule.severity is not None:
                    tags.severity = rule.severity
                
                # Add flags
                for flag in rule.flags:
                    tags.add_flag(flag)
        
        # Detect additional patterns
        self._detect_patterns(original, tags)
        
        # Calculate quality if translated text provided
        if translated is not None and self.enable_quality:
            metrics = self._calculate_quality_metrics(original, translated)
            tags.quality_score = metrics.calculate_score()
            
            # Add issues as tags
            for issue in metrics.issues:
                tags.add_tag(f"issue:{issue}", source="auto", confidence=0.9)
            
            # Set needs_review if quality is low
            if tags.quality_score < 60:
                tags.status = StatusTag.NEEDS_REVIEW
        
        return tags
    
    def _detect_patterns(self, text: str, tags: LineTags) -> None:
        """Detect additional patterns in text."""
        # Detect speaker format
        if re.search(r'^[^:：]+[:：]\s*[「『"""]', text):
            tags.add_flag("has_speaker")
        
        # Detect placeholders
        if re.search(r'__\w+__', text):
            tags.add_flag("has_placeholder")
        
        # Detect HTML/XML
        if re.search(r'<[^>]+>', text):
            tags.add_flag("has_markup")
        
        # Detect special characters
        if re.search(r'[♪♡♥★☆●○■□▲△]', text):
            tags.add_flag("has_symbols")
        
        # Detect numbers
        if re.search(r'\d+', text):
            tags.add_flag("has_numbers")
        
        # Detect Japanese (hiragana/katakana)
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
            tags.add_flag("has_japanese")
        
        # Detect line breaks
        if '<br>' in text.lower() or '\\n' in text:
            tags.add_flag("has_linebreak")
    
    def _calculate_quality_metrics(
        self,
        original: str,
        translated: str
    ) -> QualityMetrics:
        """Calculate quality metrics for translation."""
        metrics = QualityMetrics()
        
        # Check placeholder preservation
        orig_placeholders = set(re.findall(r'__\w+__', original))
        trans_placeholders = set(re.findall(r'__\w+__', translated))
        if orig_placeholders and orig_placeholders != trans_placeholders:
            metrics.placeholder_preserved = False
            metrics.issues.append("placeholder_mismatch")
        
        # Calculate length ratio
        if len(original) > 0:
            metrics.length_ratio = len(translated) / len(original)
        
        # Check for untranslated Japanese in "translated" text
        if self._has_significant_japanese(original):
            jp_ratio = self._japanese_ratio(translated)
            if jp_ratio > 0.3:
                metrics.has_untranslated = True
                metrics.issues.append("untranslated_content")
        
        # Check for repetition
        if self._has_repetition(translated):
            metrics.has_repetition = True
            metrics.issues.append("repetitive_pattern")
        
        # Check bracket balance
        if not self._check_brackets(translated):
            metrics.bracket_balanced = False
            metrics.issues.append("unbalanced_brackets")
        
        return metrics
    
    def _has_significant_japanese(self, text: str) -> bool:
        """Check if text has significant Japanese content."""
        jp_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))
        return jp_chars / max(len(text), 1) > 0.3
    
    def _japanese_ratio(self, text: str) -> float:
        """Calculate ratio of Japanese characters."""
        jp_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))
        return jp_chars / max(len(text), 1)
    
    def _has_repetition(self, text: str) -> bool:
        """Check for repetitive patterns."""
        # Check for repeated characters
        if re.search(r'(.)\1{5,}', text):
            return True
        # Check for repeated words
        if re.search(r'\b(\w+)\s+\1\s+\1\b', text):
            return True
        return False
    
    def _check_brackets(self, text: str) -> bool:
        """Check if brackets are balanced."""
        pairs = [('(', ')'), ('[', ']'), ('{', '}'), ('「', '」'), ('『', '』')]
        for open_b, close_b in pairs:
            if text.count(open_b) != text.count(close_b):
                return False
        return True
    
    def analyze_batch(
        self,
        lines: List[Tuple[str, Optional[str]]]
    ) -> List[LineTags]:
        """Analyze a batch of lines.
        
        Args:
            lines: List of (original, translated) tuples.
            
        Returns:
            List of LineTags for each line.
        """
        return [self.analyze_line(orig, trans) for orig, trans in lines]
    
    def add_rule(self, rule: TagRule) -> None:
        """Add a new tagging rule."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)
    
    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name. Returns True if removed."""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                del self.rules[i]
                return True
        return False
    
    def get_rule(self, name: str) -> Optional[TagRule]:
        """Get a rule by name."""
        for rule in self.rules:
            if rule.name == name:
                return rule
        return None


def create_auto_tagger(
    rules: Optional[List[TagRule]] = None,
    enable_quality: bool = True
) -> AutoTagger:
    """Factory function to create an AutoTagger.
    
    Args:
        rules: Custom rules (uses defaults if None).
        enable_quality: Enable quality score calculation.
        
    Returns:
        Configured AutoTagger instance.
    """
    return AutoTagger(rules=rules, enable_quality=enable_quality)


def get_content_tag_description(tag: ContentTag) -> str:
    """Get human-readable description for a content tag."""
    return CONTENT_TAG_DESCRIPTIONS.get(tag, "Unknown tag")


def get_status_tag_description(tag: StatusTag) -> str:
    """Get human-readable description for a status tag."""
    return STATUS_TAG_DESCRIPTIONS.get(tag, "Unknown status")


def get_severity_description(level: SeverityLevel) -> str:
    """Get human-readable description for a severity level."""
    return SEVERITY_DESCRIPTIONS.get(level, "Unknown level")


def list_content_tags() -> List[Dict[str, str]]:
    """List all content tags with descriptions."""
    return [
        {"name": tag.name, "description": CONTENT_TAG_DESCRIPTIONS.get(tag, "")}
        for tag in ContentTag
    ]


def list_status_tags() -> List[Dict[str, str]]:
    """List all status tags with descriptions."""
    return [
        {"name": tag.name, "description": STATUS_TAG_DESCRIPTIONS.get(tag, "")}
        for tag in StatusTag
    ]


def list_severity_levels() -> List[Dict[str, Any]]:
    """List all severity levels with descriptions."""
    return [
        {
            "name": level.name,
            "value": level.value,
            "description": SEVERITY_DESCRIPTIONS.get(level, ""),
        }
        for level in SeverityLevel
    ]
