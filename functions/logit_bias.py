"""Logit bias / token banning for LLM output control.

Allows forbidding or discouraging specific characters/tokens in LLM output.
Uses tiktoken for token ID lookup (same encoding as chunker).

Common use cases:
- Suppress EM-dash (—) when hyphen (-) preferred
- Suppress smart quotes (" ") when straight quotes preferred
- Prevent specific unwanted tokens/characters

Note: logit_bias is an OpenAI API feature. Other providers may not support it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .config import MODEL_ENCODINGS, DEFAULT_ENCODING, get_encoding_for_model

# Try to import tiktoken for token ID lookup
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None  # type: ignore
    TIKTOKEN_AVAILABLE = False


# Backward compatibility: These are now imported from config.py
# MODEL_ENCODINGS and DEFAULT_ENCODING are available via the import above


@dataclass
class LogitBiasConfig:
    """Configuration for logit bias / token banning.
    
    Attributes:
        enabled: Whether logit bias is enabled.
        banned_chars: Characters to completely ban (bias -100).
        discouraged_chars: Characters to discourage (bias -10 to -50).
        discourage_strength: Negative bias for discouraged chars (-1 to -100).
        model: Model name for encoding selection.
        preset: Optional preset name to load.
    """
    enabled: bool = False
    banned_chars: List[str] = field(default_factory=list)
    discouraged_chars: List[str] = field(default_factory=list)
    discourage_strength: int = -50  # -1 (mild) to -100 (strong)
    model: str = "gpt-4o"
    preset: Optional[str] = None


# Pre-defined presets for common use cases
# Using unicode escapes for reliability across different file encodings
EM_DASH_CHAR = "\u2014"  # —
EN_DASH_CHAR = "\u2013"  # –
SMART_QUOTE_OPEN_CHAR = "\u201c"  # "
SMART_QUOTE_CLOSE_CHAR = "\u201d"  # "
SMART_SINGLE_OPEN_CHAR = "\u2018"  # '
SMART_SINGLE_CLOSE_CHAR = "\u2019"  # '
ELLIPSIS_CHAR = "\u2026"  # …
BULLET_CHAR = "\u2022"  # •
MIDDOT_CHAR = "\u00b7"  # ·
DEGREE_CHAR = "\u00b0"  # °

LOGIT_BIAS_PRESETS: Dict[str, Dict[str, Any]] = {
    "no_fancy_punctuation": {
        "description": "Replace fancy punctuation with plain ASCII",
        "banned_chars": [EM_DASH_CHAR, EN_DASH_CHAR, SMART_QUOTE_OPEN_CHAR, 
                        SMART_QUOTE_CLOSE_CHAR, SMART_SINGLE_OPEN_CHAR, 
                        SMART_SINGLE_CLOSE_CHAR, ELLIPSIS_CHAR],
    },
    "no_em_dash": {
        "description": "Ban EM-dash, prefer regular hyphen",
        "banned_chars": [EM_DASH_CHAR, EN_DASH_CHAR],
    },
    "no_smart_quotes": {
        "description": "Ban curly/smart quotes, prefer straight quotes",
        "banned_chars": [SMART_QUOTE_OPEN_CHAR, SMART_QUOTE_CLOSE_CHAR, 
                        SMART_SINGLE_OPEN_CHAR, SMART_SINGLE_CLOSE_CHAR],
    },
    "ascii_only_punctuation": {
        "description": "Discourage all non-ASCII punctuation",
        "discouraged_chars": [EM_DASH_CHAR, EN_DASH_CHAR, SMART_QUOTE_OPEN_CHAR, 
                             SMART_QUOTE_CLOSE_CHAR, SMART_SINGLE_OPEN_CHAR, 
                             SMART_SINGLE_CLOSE_CHAR, ELLIPSIS_CHAR, BULLET_CHAR, 
                             MIDDOT_CHAR, DEGREE_CHAR],
        "discourage_strength": -30,
    },
    "japanese_ellipsis_safe": {
        "description": "Don't interfere with Japanese ellipsis handling",
        # No bans - just a marker preset
        "banned_chars": [],
    },
}


class LogitBiasManager:
    """Manages logit bias for LLM API requests.
    
    Uses tiktoken to convert characters to token IDs, then generates
    a logit_bias dict for the OpenAI API.
    
    Example:
        manager = LogitBiasManager(LogitBiasConfig(
            enabled=True,
            banned_chars=["—", "–"],
        ))
        bias = manager.get_logit_bias()
        # Use with API: response = client.chat.completions.create(..., logit_bias=bias)
    """

    def __init__(self, config: Optional[LogitBiasConfig] = None) -> None:
        """Initialize the logit bias manager.
        
        Args:
            config: Configuration for logit bias. Uses defaults if not provided.
        """
        self.config = config or LogitBiasConfig()
        self.logger = logging.getLogger(__name__)
        self._encoder: Optional[object] = None
        self._token_cache: Dict[str, List[int]] = {}  # char -> token IDs
        
        # Apply preset if specified
        if self.config.preset:
            self.apply_preset(self.config.preset)
        
        # Initialize encoder if enabled
        if self.config.enabled:
            self._init_encoder()

    def _init_encoder(self) -> None:
        """Initialize tiktoken encoder for token ID lookup."""
        if not TIKTOKEN_AVAILABLE:
            self.logger.warning(
                "tiktoken not installed - logit bias requires tiktoken. "
                "Install with: pip install tiktoken"
            )
            return
        
        try:
            if self.config.model in MODEL_ENCODINGS:
                encoding_name = MODEL_ENCODINGS[self.config.model]
                self._encoder = tiktoken.get_encoding(encoding_name)
            else:
                try:
                    self._encoder = tiktoken.encoding_for_model(self.config.model)
                except KeyError:
                    self._encoder = tiktoken.get_encoding(DEFAULT_ENCODING)
                    self.logger.debug(
                        f"No specific encoding for model '{self.config.model}', "
                        f"using {DEFAULT_ENCODING}"
                    )
        except Exception as e:
            self.logger.warning(f"Failed to initialize tiktoken encoder: {e}")
            self._encoder = None

    def apply_preset(self, preset_name: str) -> bool:
        """Apply a logit bias preset.
        
        Args:
            preset_name: Name of the preset to apply.
            
        Returns:
            True if preset was applied, False if not found.
        """
        if preset_name not in LOGIT_BIAS_PRESETS:
            self.logger.warning(f"Logit bias preset not found: {preset_name}")
            return False
        
        preset = LOGIT_BIAS_PRESETS[preset_name]
        
        # Merge preset values into config (don't replace existing)
        if "banned_chars" in preset:
            # Add preset chars to existing
            existing = set(self.config.banned_chars)
            existing.update(preset["banned_chars"])
            self.config.banned_chars = list(existing)
        
        if "discouraged_chars" in preset:
            existing = set(self.config.discouraged_chars)
            existing.update(preset["discouraged_chars"])
            self.config.discouraged_chars = list(existing)
        
        if "discourage_strength" in preset:
            self.config.discourage_strength = preset["discourage_strength"]
        
        self.logger.debug(f"Applied logit bias preset: {preset_name}")
        return True

    def get_token_ids(self, char: str) -> List[int]:
        """Get token ID(s) for a character.
        
        A single character may map to multiple token IDs depending on context,
        but we focus on the standalone token.
        
        Args:
            char: Character to look up.
            
        Returns:
            List of token IDs for this character.
        """
        if char in self._token_cache:
            return self._token_cache[char]
        
        if self._encoder is None:
            self._token_cache[char] = []
            return []
        
        try:
            # Encode the character (tiktoken encoder)
            tokens: List[int] = self._encoder.encode(char)  # type: ignore[attr-defined]
            self._token_cache[char] = tokens
            return tokens
        except Exception as e:
            self.logger.debug(f"Failed to encode character '{char}': {e}")
            self._token_cache[char] = []
            return []

    def get_logit_bias(self) -> Dict[str, int]:
        """Generate logit_bias dict for OpenAI API.
        
        Returns:
            Dictionary mapping token ID (as string) to bias value.
            Empty dict if logit bias is disabled or no tokens configured.
        """
        if not self.config.enabled:
            return {}
        
        if self._encoder is None:
            self.logger.warning("Cannot generate logit bias: tiktoken not available")
            return {}
        
        bias: Dict[str, int] = {}
        
        # Process banned characters (bias -100 = effectively banned)
        for char in self.config.banned_chars:
            token_ids = self.get_token_ids(char)
            for tid in token_ids:
                bias[str(tid)] = -100
        
        # Process discouraged characters
        for char in self.config.discouraged_chars:
            token_ids = self.get_token_ids(char)
            for tid in token_ids:
                # Don't override banned tokens
                if str(tid) not in bias:
                    bias[str(tid)] = self.config.discourage_strength
        
        return bias

    def get_summary(self) -> str:
        """Get human-readable summary of logit bias configuration.
        
        Returns:
            Summary string describing what's banned/discouraged.
        """
        if not self.config.enabled:
            return "Logit bias: disabled"
        
        parts = ["Logit bias: enabled"]
        
        if self.config.banned_chars:
            chars = ", ".join(f"'{c}'" for c in self.config.banned_chars[:5])
            if len(self.config.banned_chars) > 5:
                chars += f" +{len(self.config.banned_chars) - 5} more"
            parts.append(f"  Banned: {chars}")
        
        if self.config.discouraged_chars:
            chars = ", ".join(f"'{c}'" for c in self.config.discouraged_chars[:5])
            if len(self.config.discouraged_chars) > 5:
                chars += f" +{len(self.config.discouraged_chars) - 5} more"
            parts.append(f"  Discouraged ({self.config.discourage_strength}): {chars}")
        
        return "\n".join(parts)

    def is_available(self) -> bool:
        """Check if logit bias functionality is available.
        
        Returns:
            True if tiktoken is installed and encoder initialized.
        """
        return TIKTOKEN_AVAILABLE and self._encoder is not None

    @staticmethod
    def list_presets() -> List[str]:
        """Get list of available preset names.
        
        Returns:
            List of preset names.
        """
        return list(LOGIT_BIAS_PRESETS.keys())

    @staticmethod
    def get_preset_description(preset_name: str) -> Optional[str]:
        """Get description for a preset.
        
        Args:
            preset_name: Name of preset.
            
        Returns:
            Description string or None if not found.
        """
        if preset_name in LOGIT_BIAS_PRESETS:
            return LOGIT_BIAS_PRESETS[preset_name].get("description")
        return None


def create_logit_bias_manager(
    enabled: bool = False,
    banned_chars: Optional[List[str]] = None,
    discouraged_chars: Optional[List[str]] = None,
    discourage_strength: int = -50,
    model: str = "gpt-4o",
    preset: Optional[str] = None,
) -> LogitBiasManager:
    """Factory function to create a LogitBiasManager.
    
    Args:
        enabled: Whether logit bias is enabled.
        banned_chars: Characters to completely ban.
        discouraged_chars: Characters to discourage.
        discourage_strength: Negative bias for discouraged chars.
        model: Model name for encoding selection.
        preset: Optional preset name to load.
        
    Returns:
        Configured LogitBiasManager instance.
    """
    config = LogitBiasConfig(
        enabled=enabled,
        banned_chars=banned_chars or [],
        discouraged_chars=discouraged_chars or [],
        discourage_strength=discourage_strength,
        model=model,
        preset=preset,
    )
    return LogitBiasManager(config)


def is_tiktoken_available() -> bool:
    """Check if tiktoken is available for token ID lookup.
    
    Returns:
        True if tiktoken is installed.
    """
    return TIKTOKEN_AVAILABLE


def parse_ban_tokens_arg(arg: str) -> List[str]:
    """Parse --ban-tokens CLI argument.
    
    Handles comma-separated characters/tokens.
    
    Args:
        arg: CLI argument string, e.g., "—,–" or "em_dash,en_dash"
        
    Returns:
        List of characters to ban.
    """
    if not arg:
        return []
    
    # Named token aliases - use the module constants for consistency
    ALIASES = {
        "em_dash": EM_DASH_CHAR,
        "en_dash": EN_DASH_CHAR,
        "smart_quote_open": SMART_QUOTE_OPEN_CHAR,
        "smart_quote_close": SMART_QUOTE_CLOSE_CHAR,
        "smart_single_open": SMART_SINGLE_OPEN_CHAR,
        "smart_single_close": SMART_SINGLE_CLOSE_CHAR,
        "ellipsis": ELLIPSIS_CHAR,
        "bullet": BULLET_CHAR,
        "middot": MIDDOT_CHAR,
    }
    
    result = []
    for part in arg.split(","):
        part = part.strip()
        if not part:
            continue
        
        # Check for alias
        if part in ALIASES:
            result.append(ALIASES[part])
        else:
            # Treat as literal character(s)
            result.append(part)
    
    return result
