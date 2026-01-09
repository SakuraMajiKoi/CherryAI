"""Constants for name and speaker glossary management.

This module contains all constants related to:
- Japanese honorific suffixes
- Pronoun patterns and labels
- Gender inference mappings
- Romanization tables
- Script type detection (hiragana/katakana/kanji)
- RPG Maker name placeholders
- Speaker validation thresholds
"""

from __future__ import annotations

import re

# ---------------- Honorific patterns and suffixes ---------------- #

# Japanese honorific suffixes for detection
HONORIFIC_SUFFIXES = ["さん", "ちゃん", "くん", "君", "さま", "様", "先生", "せんせい"]

# Build regex for honorific detection
# Captures: Group 1 = base token, Group 2 = suffix
HONORIFIC_ALTERNATION = "|".join(map(re.escape, HONORIFIC_SUFFIXES))
HONORIFIC_RE = re.compile(
    r"([^\s\[\]{}()<>\"'：:,，。！？!?]+)(" + HONORIFIC_ALTERNATION + r")"
)

# Extended honorific list for romanization (includes family terms)
HONORIFIC_ROMANIZATION = {
    "さん": "san",
    "ちゃん": "chan",
    "くん": "kun",
    "君": "kun",
    "さま": "sama",
    "様": "sama",
    "先生": "sensei",
    "せんせい": "sensei",
    "お兄": "onii",
    "おにい": "onii",
    "オニイ": "onii",
    "兄": "nii",
    "にい": "nii",
    "ニイ": "nii",
    "お姉": "onee",
    "おねえ": "onee",
    "オネエ": "onee",
    "姉": "nee",
    "ねえ": "nee",
    "ネエ": "nee",
}

# Gender inference for honorific suffixes
# Values: male, female, unknown
HONORIFIC_GENDER = {
    "san": "unknown",      # Neutral honorific
    "chan": "female",
    "kun": "male",
    "sama": "unknown",     # Neutral honorific
    "sensei": "unknown",   # Neutral title
    "onii": "male",        # Older brother
    "nii": "male",         # Older brother (casual)
    "onee": "female",      # Older sister
    "nee": "female",       # Older sister (casual)
}

# Honorific suffixes with English labels (for gender/style inference)
SUFFIX_LABELS = {
    "ちゃん": "Female/Diminutive",
    "先生": "Teacher",
    "せんせい": "Teacher",
    "くん": "Male",
    "君": "Male",
}

# ---------------- Pronoun patterns and labels ---------------- #

# Japanese pronouns with romanization
PRONOUN_ROMANIZATION = {
    "私": "watashi",
    "わたし": "watashi",
    "ワタシ": "watashi",
    "わたくし": "watakushi",
    "ワタクシ": "watakushi",
    "あたし": "atashi",
    "アタシ": "atashi",
    "うち": "uchi",
    "ウチ": "uchi",
    "僕": "boku",
    "ぼく": "boku",
    "ボク": "boku",
    "俺": "ore",
    "おれ": "ore",
    "オレ": "ore",
    "自分": "jibun",
    "じぶん": "jibun",
    "ジブン": "jibun",
}

# Gender inference for pronouns
# Values: male, female, unknown
PRONOUN_GENDER = {
    "watashi": "female",   # Rarely male
    "watakushi": "female",
    "atashi": "female",
    "uchi": "female",
    "boku": "male",        # Rarely boyish female
    "ore": "male",
    "jibun": "male",
}

# Pronouns with English labels (Japanese token -> style description)
PRONOUN_LABELS = {
    "私": "Female/Neutral Professional",
    "わたし": "Female/Neutral Professional",
    "ワタシ": "Female/Neutral Professional",
    "わたくし": "Lady",
    "ワタクシ": "Lady",
    "あたし": "Female",
    "アタシ": "Female",
    "うち": "Female/Homely",
    "ウチ": "Female/Homely",
    "僕": "Boy/Boyish",
    "ぼく": "Boy/Boyish",
    "ボク": "Boy/Boyish",
    "俺": "Male/Manly",
    "おれ": "Male/Manly",
    "オレ": "Male/Manly",
    "自分": "Male",
    "じぶん": "Male",
    "ジブン": "Male",
}

# ---------------- Explicit Gender Markers ---------------- #

# Patterns to detect explicit gender statements in text
# Format: "名前：X、性別：女性" or similar status card patterns
EXPLICIT_GENDER_PATTERNS = {
    # Status card format: 名前：NAME、性別：GENDER
    r"名前[：:](.+?)[、,]性別[：:](女性|男性|女|男)": "status_card",
    # Direct statement: NAMEは女性/男性
    r"(.+?)は(女性|男性)になった": "transformation",
    # 女の子/男の子 reference
    r"(.+?)(?:ちゃん)?は女の子": "girl_reference",
    r"(.+?)(?:くん)?は男の子": "boy_reference",
}

# Gender value mappings from Japanese
EXPLICIT_GENDER_VALUES = {
    "女性": "female",
    "男性": "male",
    "女": "female",
    "男": "male",
    "女の子": "female",
    "男の子": "male",
}

# ---------------- Honorific Reference Tracking ---------------- #

# Honorifics used BY OTHERS to refer to a speaker (stronger gender signal)
# These override self-pronoun when there's a conflict
REFERRED_BY_OTHERS_WEIGHT = 3.0  # Multiplier for honorifics used by others

# Suffixes that strongly indicate gender when used by others
STRONG_GENDER_HONORIFICS = {
    "ちゃん": "female",  # Very strong female indicator when used by others
    "くん": "male",       # Strong male indicator
    "君": "male",
    "嬢": "female",       # Young lady (ojou)
    "姫": "female",       # Princess (hime)
}

# ---------------- Script type detection ---------------- #

# Unicode ranges for Japanese scripts
HIRAGANA_RANGE = (0x3040, 0x309F)  # ぁ-ん
KATAKANA_RANGE = (0x30A0, 0x30FF)  # ァ-ン
KANJI_RANGE = (0x4E00, 0x9FFF)     # 一-龯

# ---------------- Name validation patterns ---------------- #

# Regex for placeholder names like [n1], \N[1], {name}, etc.
PLACEHOLDER_NAME_RE = re.compile(r"^[\[\{\\].*?[\]\}]$|^\\[A-Z]\[\d+\]$")

# ---------------- RPG Maker patterns ---------------- #

# RPG Maker variable and actor tokens (case-sensitive): \V[<NUM>] and \N[<NUM>]
RPGM_VAR_RE = re.compile(r"\\V\[(\d+)\]")
RPGM_ACTOR_RE = re.compile(r"\\N\[(\d+)\]")

# ---------------- Speaker validation thresholds ---------------- #

# Minimum times a speaker must appear to be included in glossary
MIN_SPEAKER_OCCURRENCES = 2

# Maximum character length for a valid speaker name
MAX_SPEAKER_LENGTH = 50

# Confidence threshold for automatic gender assignment (0-100%)
DEFAULT_GENDER_CONFIDENCE_THRESHOLD = 75.0

# ---------------- CSV headers ---------------- #

# Header for speakers.tsv (legacy format)
SPEAKERS_HEADER = ["Speaker", "Translation", "Comment"]
