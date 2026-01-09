"""Constants for code pattern detection and glossary management.

This module contains all constants related to:
- Code pattern regex
- Color name normalization
- RPG Maker variables
- Code glossary CSV structure
"""

from __future__ import annotations

import re

# ---------------- Code detection patterns ---------------- #

# Regex patterns for code-like abnormalities in dialogue
# Note: Underscore-wrapped text (_text_) is NOT treated as code
CODE_PATTERNS = [
    re.compile(r"<[^>]*?>"),          # HTML/XML tags
    re.compile(r"\\(n|r|t|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|N|R|T)"),  # Escape sequences
    re.compile(r"\[[^\]]*?\]"),        # [bracketed] text
    re.compile(r"\{[^}]*?\}"),         # {braced} text
]

# ---------------- Color names for normalization ---------------- #

# Color name dictionary for normalizing code segments that encode colors.
# Expanded to catch common game text colors including Japanese color names.
COLOR_NAMES = {
    # English color names (priority colors)
    "red",
    "blue",
    "green",
    "yellow",
    "black",
    "white",
    "pink",
    "grey",
    "gray",
    # Additional common colors
    "cyan",
    "magenta",
    "orange",
    "purple",
    "brown",
    "violet",
    "indigo",
    "teal",
    "maroon",
    "navy",
    "silver",
    "gold",
    "beige",
    "ivory",
    "lavender",
    "olive",
    "lime",
    "aqua",
    "fuchsia",
}

# ---------------- RPG Maker patterns ---------------- #

# RPG Maker variable and actor tokens (case-sensitive): \V[<NUM>] and \N[<NUM>]
RPGM_VAR_RE = re.compile(r"\\V\[(\d+)\]")
RPGM_ACTOR_RE = re.compile(r"\\N\[(\d+)\]")

# ---------------- CSV headers ---------------- #

# Header for code glossary CSV
CODE_GLOSSARY_HEADER = [
    "Code",
    "Type",
    "RegEx",
    "Notes",
]

# ---------------- Code type constants ---------------- #

# Code type classifications for glossary
TYPE_LINEBREAK = "LINEBREAK"
TYPE_VARIABLENAME = "VARIABLENAME"
TYPE_VARIABLENUMBER = "VARIABLENUMBER"
TYPE_VISIBLEVARIABLE = "VISIBLEVARIABLE"
TYPE_COLOR = "COLOR"
TYPE_FONT = "FONT"
TYPE_RUBY = "RUBY"
TYPE_UNKNOWN = "UNKNOWN"
