"""Japanese script romanization (Modified Hepburn).

Provides a lightweight, dependency-free conversion of Japanese hiragana
and katakana into Latin-letter (rōmaji) equivalents using the Modified
Hepburn romanization system.

Usage::

    from functions.romanization import romanize

    romanize("こんにちは")    # → "konnichiha"
    romanize("カタカナ")      # → "katakana"
    romanize("火山ABC")       # → "ABC"  (kanji/latin passed through)

The function **only** converts kana characters.  Kanji, Latin,
punctuation, and other scripts are passed through unchanged.

Task 75 — Phase 75.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

# ============================================================================
# Hepburn Romanization Tables
# ============================================================================

# fmt: off

# --- Hiragana → Rōmaji (Modified Hepburn) ---
_HIRAGANA: Dict[str, str] = {
    # Basic vowels
    "あ": "a",  "い": "i",  "う": "u",  "え": "e",  "お": "o",
    # K-row
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    # S-row
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    # T-row
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    # N-row
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    # H-row
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    # M-row
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    # Y-row
    "や": "ya",             "ゆ": "yu",             "よ": "yo",
    # R-row
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    # W-row + N
    "わ": "wa", "ゐ": "wi",             "ゑ": "we", "を": "wo",
    "ん": "n",
    # Dakuten (voiced)
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "di", "づ": "du", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    # Handakuten (p-sounds)
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    # Small kana (yōon combos — handled as digraphs below)
    "ゃ": "ya", "ゅ": "yu", "ょ": "yo",
    "ぁ": "a",  "ぃ": "i",  "ぅ": "u",  "ぇ": "e",  "ぉ": "o",
    # Rare / archaic
    "ゔ": "vu",
}

# --- Katakana → Rōmaji ---
_KATAKANA: Dict[str, str] = {
    # Basic vowels
    "ア": "a",  "イ": "i",  "ウ": "u",  "エ": "e",  "オ": "o",
    # K-row
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    # S-row
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    # T-row
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    # N-row
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    # H-row
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    # M-row
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    # Y-row
    "ヤ": "ya",             "ユ": "yu",             "ヨ": "yo",
    # R-row
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    # W-row + N
    "ワ": "wa", "ヰ": "wi",             "ヱ": "we", "ヲ": "wo",
    "ン": "n",
    # Dakuten (voiced)
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "ダ": "da", "ヂ": "di", "ヅ": "du", "デ": "de", "ド": "do",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    # Handakuten (p-sounds)
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    # Small kana
    "ャ": "ya", "ュ": "yu", "ョ": "yo",
    "ァ": "a",  "ィ": "i",  "ゥ": "u",  "ェ": "e",  "ォ": "o",
    # Katakana-specific
    "ヴ": "vu",
}

# --- Digraph combinations (yōon) ---
# Two-character kana sequences that romanize differently from the
# concatenation of their individual characters.
_HIRAGANA_DIGRAPHS: Dict[str, str] = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
    "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "じゃ": "ja",  "じゅ": "ju",  "じょ": "jo",
    "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "ぢゃ": "dya", "ぢゅ": "dyu", "ぢょ": "dyo",
}

_KATAKANA_DIGRAPHS: Dict[str, str] = {
    "キャ": "kya", "キュ": "kyu", "キョ": "kyo",
    "シャ": "sha", "シュ": "shu", "ショ": "sho",
    "チャ": "cha", "チュ": "chu", "チョ": "cho",
    "ニャ": "nya", "ニュ": "nyu", "ニョ": "nyo",
    "ヒャ": "hya", "ヒュ": "hyu", "ヒョ": "hyo",
    "ミャ": "mya", "ミュ": "myu", "ミョ": "myo",
    "リャ": "rya", "リュ": "ryu", "リョ": "ryo",
    "ギャ": "gya", "ギュ": "gyu", "ギョ": "gyo",
    "ジャ": "ja",  "ジュ": "ju",  "ジョ": "jo",
    "ビャ": "bya", "ビュ": "byu", "ビョ": "byo",
    "ピャ": "pya", "ピュ": "pyu", "ピョ": "pyo",
    "ヂャ": "dya", "ヂュ": "dyu", "ヂョ": "dyo",
    # Extended katakana digraphs (foreign loan-words)
    "ファ": "fa",  "フィ": "fi",  "フェ": "fe",  "フォ": "fo",
    "ティ": "ti",  "ディ": "di",
    "ウィ": "wi",  "ウェ": "we",  "ウォ": "wo",
    "ヴァ": "va",  "ヴィ": "vi",  "ヴェ": "ve",  "ヴォ": "vo",
    "ツァ": "tsa", "ツィ": "tsi", "ツェ": "tse", "ツォ": "tso",
    "デュ": "dyu",
    "トゥ": "tu",  "ドゥ": "du",
}

# fmt: on

# Merged lookup for single-char kana
_SINGLE_KANA: Dict[str, str] = {**_HIRAGANA, **_KATAKANA}

# Merged lookup for two-char kana digraphs
_DIGRAPH_KANA: Dict[str, str] = {**_HIRAGANA_DIGRAPHS, **_KATAKANA_DIGRAPHS}

# Small tsu (っ / ッ) — doubles the following consonant
_SMALL_TSU = {"っ", "ッ"}

# Long vowel mark (ー) — extends previous vowel
_LONG_VOWEL = "ー"

# Regex for detecting any kana character (hiragana U+3040‒U+309F,
# katakana U+30A0‒U+30FF, katakana-hw U+FF65‒U+FF9F)
_KANA_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\uFF65-\uFF9F]")

# Regex for detecting CJK Unified Ideographs (kanji)
_KANJI_RE = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]")


# ============================================================================
# Public API
# ============================================================================


def romanize(text: str) -> str:
    """Convert Japanese kana in *text* to Modified Hepburn rōmaji.

    - Hiragana and katakana are converted; kanji, Latin letters,
      digits, and punctuation pass through unchanged.
    - Digraphs (yōon like きゃ → kya) are handled before single kana.
    - Small tsu (っ / ッ) doubles the following consonant.
    - Long vowel mark (ー) extends the preceding vowel.

    Args:
        text: Input string, may contain mixed scripts.

    Returns:
        Romanized string.
    """
    if not text:
        return ""

    result: list[str] = []
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        # --- Small tsu: double the next consonant ---
        if ch in _SMALL_TSU:
            # Look ahead for the next kana's consonant
            nxt = _peek_next_romaji(text, i + 1)
            if nxt and nxt[0] not in "aeioun":
                result.append(nxt[0])
            else:
                result.append("t")  # fallback: standalone っ → "t"
            i += 1
            continue

        # --- Long vowel mark: extend previous vowel ---
        if ch == _LONG_VOWEL:
            if result:
                last = result[-1]
                if last and last[-1] in "aeiou":
                    result.append(last[-1])
                else:
                    result.append("-")
            i += 1
            continue

        # --- Two-character digraph ---
        if i + 1 < length:
            pair = text[i : i + 2]
            if pair in _DIGRAPH_KANA:
                result.append(_DIGRAPH_KANA[pair])
                i += 2
                continue

        # --- Single kana ---
        if ch in _SINGLE_KANA:
            result.append(_SINGLE_KANA[ch])
            i += 1
            continue

        # --- Non-kana character: pass through ---
        result.append(ch)
        i += 1

    return "".join(result)


def contains_kana(text: str) -> bool:
    """Return ``True`` if *text* contains any hiragana or katakana character."""
    return bool(_KANA_RE.search(text))


def contains_kanji(text: str) -> bool:
    """Return ``True`` if *text* contains any CJK ideograph (kanji)."""
    return bool(_KANJI_RE.search(text))


def romanize_if_japanese(text: str) -> str:
    """Romanize *text* only if it contains kana and no kanji.

    Terms containing kanji mixed with kana cannot be fully romanized
    (kanji pass through unchanged, producing garbled output like
    ``釣ri好kinoojisan``).  Such terms are returned unchanged so that
    MTL or LLM modes can handle them instead.

    Args:
        text: Input string.

    Returns:
        Romanized string if only kana was detected, otherwise the
        original string unchanged.
    """
    if contains_kana(text) and not contains_kanji(text):
        return romanize(text)
    return text


def capitalize_name(text: str) -> str:
    """Capitalize only the first letter of a romanized name.

    Args:
        text: Romanized text to capitalize.

    Returns:
        String with only the first letter uppercased.
    """
    if not text:
        return ""
    return text[0].upper() + text[1:]


# ============================================================================
# Internal helpers
# ============================================================================


def _peek_next_romaji(text: str, pos: int) -> Optional[str]:
    """Return the romaji for the kana at *pos* (digraph-aware).

    Used by the small-tsu handler to determine the leading consonant of
    the following syllable.
    """
    if pos >= len(text):
        return None

    if pos + 1 < len(text):
        pair = text[pos : pos + 2]
        if pair in _DIGRAPH_KANA:
            return _DIGRAPH_KANA[pair]

    ch = text[pos]
    return _SINGLE_KANA.get(ch)
