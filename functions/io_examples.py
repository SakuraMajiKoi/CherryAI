"""I/O example generator for system prompt enrichment.

Generates input/output translation example pairs that demonstrate
correct handling of code patterns, placeholders, formatting, and
speaker:dialogue conventions. Examples are injected into the prompt
between System Instructions (slot 2) and Style (slot 3) following
§5.2 injection order.

The generator builds examples from a static bank of multilingual pairs
(keyed by language code, e.g. ``jp``, ``en``), prioritising lines that
contain code patterns actually present in the project manifest.  Source
and target language are resolved from the manifest; when a language has
no matching key the fallback is ``en`` (or ``jp`` when English is
already source or target).  Token budget is respected: lines are added
until the target is reached.

Modes:
    ``"disabled"`` — No examples generated.
    ``"1500"``     — Generate ~1500 tokens of examples.
    ``"2500"``     — Generate ~2500 tokens of examples.
    ``"fill"``     — Fill remaining cache-aligned budget (see caller).
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token estimation helper
# ---------------------------------------------------------------------------

_encoder = None
_encoder_loaded = False


def _get_encoder():
    """Try to load tiktoken encoder (cached)."""
    global _encoder, _encoder_loaded
    if _encoder_loaded:
        return _encoder
    _encoder_loaded = True
    try:
        import tiktoken
        _encoder = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _encoder = None
    return _encoder


def estimate_tokens(text: str) -> int:
    """Estimate token count for *text*.

    Uses tiktoken when available; otherwise applies a character-based
    heuristic (len/1.7 for Japanese, len/4 for Latin).
    """
    if not text:
        return 0
    enc = _get_encoder()
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    if re.search(r"[\u3000-\u9fff\uff00-\uffef]", text):
        return math.ceil(len(text) / 1.7)
    return math.ceil(len(text) / 4)


# ---------------------------------------------------------------------------
# Example line bank
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Example:
    """One translation example with text keyed by language code."""
    jp: str
    en: str
    tags: Tuple[str, ...]  # pattern categories demonstrated
    priority: int = 10     # lower = higher priority


# Each pair is tagged with the code-pattern categories it demonstrates.
# Tags mirror the categories from code detection: PLACEHOLDER, VARIABLE,
# COLOR, LINEBREAK, MEDIA, ICON, FONT, SPEAKER, PRESERVE, RUBY, SPAN.
#
# Priority: 1 = must-have, 5 = important, 10 = nice-to-have

_EXAMPLE_BANK: Tuple[_Example, ...] = (
    # ---- PLACEHOLDER ----
    _Example(
        jp=(
            '"Line1": "「音楽が__PROTECTED_0__流れています」",'
            '\n    "Line2": "「そして__PROTECTED_1__効果音も鳴ります」"'
        ),
        en=(
            '"Line1": "\\"The music __PROTECTED_0__ is playing.\\"",\n'
            '    "Line2": "\\"And the __PROTECTED_1__ sound effect is '
            'also playing.\\""'
        ),
        tags=("PLACEHOLDER",),
        priority=1,
    ),
    _Example(
        jp='"Line1": "__PROTECTED_0__を持って行きなさい"',
        en='"Line1": "Take __PROTECTED_0__ with you."',
        tags=("PLACEHOLDER",),
        priority=5,
    ),

    # ---- VARIABLE ----
    _Example(
        jp='"Line1": "\\\\v[0]がお前に手を焼いてるみたいだったよ"',
        en=(
            '"Line1": "It seems like \\\\v[0] is having a hard time '
            'with you."'
        ),
        tags=("VARIABLE",),
        priority=1,
    ),
    _Example(
        jp='"Line1": "\\\\N[1]を探しに街へ出かけた"',
        en='"Line1": "I went to town to look for \\\\N[1]."',
        tags=("VARIABLE",),
        priority=5,
    ),
    _Example(
        jp='"Line1": "\\\\N[3]は\\\\v[12]ゴールドを手に入れた"',
        en=(
            '"Line1": "\\\\N[3] obtained \\\\v[12] gold."'
        ),
        tags=("VARIABLE",),
        priority=8,
    ),

    # ---- COLOR ----
    _Example(
        jp=(
            '"Line1": "他はどうでも良いけど、\\\\n\\"\\\\c[10]私の'
            '標的\\\\c\\"に余計な事しないでくれない？"'
        ),
        en=(
            '"Line1": "I don\'t care about the others,\\\\nbut could '
            'you not interfere with \\"\\\\c[10]my target\\\\c\\"?"'
        ),
        tags=("COLOR", "LINEBREAK"),
        priority=1,
    ),
    _Example(
        jp='"Line1": "\\\\c[18]どウかお許シを"',
        en='"Line1": "\\\\c[18]please forgive me."',
        tags=("COLOR",),
        priority=5,
    ),

    # ---- LINEBREAK ----
    _Example(
        jp='"Line1": "ここは危険だ。\\\\n先に進むか？"',
        en='"Line1": "This place is dangerous.\\\\nShall we proceed?"',
        tags=("LINEBREAK",),
        priority=3,
    ),
    _Example(
        jp='"Line1": "\\\\n\\\\n--- 第３章 ---\\\\n\\\\n"',
        en='"Line1": "\\\\n\\\\n--- Chapter 3 ---\\\\n\\\\n"',
        tags=("LINEBREAK",),
        priority=8,
    ),

    # ---- MEDIA (SE, ME, picture) ----
    _Example(
        jp=(
            '"Line1": "\\\\SE[ライター]クロネ様に永久ニ服従しまスから'
            '...\\\\n\\\\c[18]どウかお許シを"'
        ),
        en=(
            '"Line1": "\\\\SE[ライター]I will serve you forever, '
            'Kurone-sama...\\\\n\\\\c[18]please forgive me."'
        ),
        tags=("MEDIA", "LINEBREAK", "COLOR"),
        priority=2,
    ),
    _Example(
        jp='"Line1": "\\\\ME[bgm_battle]戦闘開始！"',
        en='"Line1": "\\\\ME[bgm_battle]Battle start!"',
        tags=("MEDIA",),
        priority=8,
    ),

    # ---- ICON ----
    _Example(
        jp='"Line1": "Kurone: ...\\\\i[100]"',
        en='"Line1": "Kurone: ...\\\\i[100]"',
        tags=("ICON", "SPEAKER", "PRESERVE"),
        priority=3,
    ),
    _Example(
        jp='"Line1": "\\\\i[312]体力が回復した！"',
        en='"Line1": "\\\\i[312]HP has been restored!"',
        tags=("ICON",),
        priority=8,
    ),

    # ---- FONT ----
    _Example(
        jp='"Line1": "\\\\FS[28]重要なお知らせ\\\\FS[20]"',
        en='"Line1": "\\\\FS[28]Important Notice\\\\FS[20]"',
        tags=("FONT",),
        priority=5,
    ),

    # ---- SPEAKER:DIALOGUE ----
    _Example(
        jp=(
            '"Line1": "Defense Member E: ...",'
            '\n    "Line2": "Kurone: あのさ",'
            '\n    "Line3": "Kurone: 殺すよ",'
            '\n    "Line4": "Defense Member E: ひっ...!も…申し訳ございません"'
        ),
        en=(
            '"Line1": "Defense Member E: ...",'
            '\n    "Line2": "Kurone: Hey.",'
            '\n    "Line3": "Kurone: I\'ll kill you.",'
            '\n    "Line4": "Defense Member E: Eek...! I-\'m so sorry."'
        ),
        tags=("SPEAKER", "PRESERVE"),
        priority=1,
    ),
    _Example(
        jp=(
            '"Line1": "村人A: この先は森だよ",'
            '\n    "Line2": "村人A: 気をつけてね"'
        ),
        en=(
            '"Line1": "Villager A: The forest is up ahead.",'
            '\n    "Line2": "Villager A: Be careful."'
        ),
        tags=("SPEAKER",),
        priority=5,
    ),

    # ---- PRESERVE (untranslatable / ellipsis) ----
    _Example(
        jp=(
            '"Line1": "...",'
            '\n    "Line2": "............",'
            '\n    "Line3": "！？"'
        ),
        en=(
            '"Line1": "...",'
            '\n    "Line2": "............",'
            '\n    "Line3": "!?"'
        ),
        tags=("PRESERVE",),
        priority=3,
    ),

    # ---- RUBY ----
    _Example(
        jp='"Line1": "\\\\rb[紅蓮,ぐれん]の炎が燃え上がった"',
        en='"Line1": "\\\\rb[紅蓮,ぐれん] flames blazed up."',
        tags=("RUBY",),
        priority=5,
    ),

    # ---- SPAN (color/font spans) ----
    _Example(
        jp=(
            '"Line1": "\\\\C[5]警告：\\\\C[0]この先は立入禁止です"'
        ),
        en=(
            '"Line1": "\\\\C[5]Warning:\\\\C[0] Entry is prohibited '
            'beyond this point."'
        ),
        tags=("SPAN", "COLOR"),
        priority=3,
    ),
    _Example(
        jp=(
            '"Line1": "\\\\FS[24]クエスト完了\\\\FS[20]\\\\n報酬を'
            '受け取りました"'
        ),
        en=(
            '"Line1": "\\\\FS[24]Quest Complete\\\\FS[20]\\\\nYou have '
            'received your reward."'
        ),
        tags=("SPAN", "FONT", "LINEBREAK"),
        priority=5,
    ),

    # ---- COMPLEX (multiple patterns combined) ----
    _Example(
        jp=(
            '"Line1": "\\\\SE[Chime]\\\\C[2]\\\\N[1]\\\\C[0]は'
            '\\\\v[5]個のアイテムを手に入れた！"'
        ),
        en=(
            '"Line1": "\\\\SE[Chime]\\\\C[2]\\\\N[1]\\\\C[0] obtained '
            '\\\\v[5] items!"'
        ),
        tags=("COMPLEX", "MEDIA", "COLOR", "VARIABLE"),
        priority=2,
    ),
    _Example(
        jp=(
            '"Line1": "\\\\c[6]\\\\N[2]\\\\c[0]: 私の力を見せてあげる'
            '\\\\n\\\\i[156]スキル【烈火】を発動！"'
        ),
        en=(
            '"Line1": "\\\\c[6]\\\\N[2]\\\\c[0]: I\'ll show you my '
            'power.\\\\n\\\\i[156]Skill [Blaze] activated!"'
        ),
        tags=("COMPLEX", "COLOR", "VARIABLE", "LINEBREAK", "ICON"),
        priority=4,
    ),
    _Example(
        jp=(
            '"Line1": "店主: いらっしゃい\\\\nなにをお探しで？",'
            '\n    "Line2": "店主: \\\\i[236]薬草は\\\\v[20]ゴールドだよ"'
        ),
        en=(
            '"Line1": "Shopkeeper: Welcome.\\\\nWhat are you looking for?",'
            '\n    "Line2": "Shopkeeper: \\\\i[236]Herbs cost \\\\v[20] '
            'gold."'
        ),
        tags=("COMPLEX", "SPEAKER", "LINEBREAK", "ICON", "VARIABLE"),
        priority=4,
    ),

    # ---- Additional variety ----
    _Example(
        jp='"Line1": "セーブしますか？"',
        en='"Line1": "Would you like to save?"',
        tags=("PLAIN",),
        priority=10,
    ),
    _Example(
        jp=(
            '"Line1": "はい",'
            '\n    "Line2": "いいえ",'
            '\n    "Line3": "キャンセル"'
        ),
        en=(
            '"Line1": "Yes",'
            '\n    "Line2": "No",'
            '\n    "Line3": "Cancel"'
        ),
        tags=("PLAIN",),
        priority=10,
    ),
    _Example(
        jp=(
            '"Line1": "盗賊: \\\\C[4]金を出せ！\\\\C[0]\\\\nさもないと'
            '\\\\c[2]痛い目\\\\c[0]にあうぞ"'
        ),
        en=(
            '"Line1": "Thief: \\\\C[4]Hand over your money!\\\\C[0]'
            '\\\\nOtherwise you\'ll be in for \\\\c[2]a world of '
            'pain\\\\c[0]."'
        ),
        tags=("COMPLEX", "SPEAKER", "COLOR", "LINEBREAK", "SPAN"),
        priority=6,
    ),
    _Example(
        jp='"Line1": "\\\\>{冒険者ギルド}\\\\<"',
        en='"Line1": "\\\\>{Adventurer\'s Guild}\\\\<"',
        tags=("PRESERVE",),
        priority=8,
    ),
    _Example(
        jp=(
            '"Line1": "魔王: ふはは…この世界は我のものだ",'
            '\n    "Line2": "勇者: そうはさせない！",'
            '\n    "Line3": "魔王: 愚かな…来い！"'
        ),
        en=(
            '"Line1": "Demon Lord: Hahaha... This world is mine.",'
            '\n    "Line2": "Hero: I won\'t let that happen!",'
            '\n    "Line3": "Demon Lord: Fool... Come!"'
        ),
        tags=("SPEAKER",),
        priority=7,
    ),
    _Example(
        jp=(
            '"Line1": "\\\\fb太字のテスト\\\\fr",'
            '\n    "Line2": "\\\\{大きい文字\\\\}と\\\\{小さい文字\\\\}"'
        ),
        en=(
            '"Line1": "\\\\fbBold text test\\\\fr",'
            '\n    "Line2": "\\\\{Large text\\\\} and \\\\{small text\\\\}"'
        ),
        tags=("FONT",),
        priority=7,
    ),
    _Example(
        jp='"Line1": "\\\\pic[castle_bg]遠くに城が見える…"',
        en='"Line1": "\\\\pic[castle_bg]A castle can be seen in the distance..."',
        tags=("MEDIA",),
        priority=9,
    ),

    # ---- Extra examples for 2500 mode ----
    _Example(
        jp=(
            '"Line1": "兵士: おい、止まれ！\\\\n通行許可証を見せろ",'
            '\n    "Line2": "兵士: \\\\c[2]不審者\\\\c[0]め…ここは通さん"'
        ),
        en=(
            '"Line1": "Soldier: Hey, halt!\\\\nShow your travel permit.",'
            '\n    "Line2": "Soldier: You \\\\c[2]suspicious\\\\c[0]'
            ' person... I won\'t let you pass."'
        ),
        tags=("SPEAKER", "LINEBREAK", "COLOR"),
        priority=6,
    ),
    _Example(
        jp=(
            '"Line1": "\\\\SE[heal]\\\\i[64]\\\\N[1]のHPが\\\\v[10]回復した！"'
        ),
        en=(
            '"Line1": "\\\\SE[heal]\\\\i[64]\\\\N[1]\'s HP recovered '
            'by \\\\v[10]!"'
        ),
        tags=("COMPLEX", "MEDIA", "ICON", "VARIABLE"),
        priority=5,
    ),
    _Example(
        jp=(
            '"Line1": "老人: 昔、この地にはドラゴンが住んでいたんじゃ",'
            '\n    "Line2": "老人: だがある日、勇者がやってきてな…",'
            '\n    "Line3": "老人: まぁ、あとは察してくれ"'
        ),
        en=(
            '"Line1": "Old Man: Long ago, dragons used to live in this '
            'land.",'
            '\n    "Line2": "Old Man: But one day, a hero came along...",'
            '\n    "Line3": "Old Man: Well, you can figure out the rest."'
        ),
        tags=("SPEAKER",),
        priority=7,
    ),
    _Example(
        jp=(
            '"Line1": "\\\\FS[32]第一章\\\\FS[20]\\\\n\\\\C[6]始まりの村'
            '\\\\C[0]"'
        ),
        en=(
            '"Line1": "\\\\FS[32]Chapter 1\\\\FS[20]\\\\n\\\\C[6]'
            'Village of Beginnings\\\\C[0]"'
        ),
        tags=("FONT", "LINEBREAK", "COLOR", "SPAN"),
        priority=6,
    ),
    _Example(
        jp=(
            '"Line1": "【選択肢】",'
            '\n    "Line2": "戦う",'
            '\n    "Line3": "逃げる",'
            '\n    "Line4": "話し合う"'
        ),
        en=(
            '"Line1": "【Choices】",'
            '\n    "Line2": "Fight",'
            '\n    "Line3": "Run",'
            '\n    "Line4": "Negotiate"'
        ),
        tags=("PLAIN",),
        priority=9,
    ),
    _Example(
        jp=(
            '"Line1": "姫: \\\\C[5]お願い\\\\C[0]…\\\\N[1]、'
            '私を助けて",'
            '\n    "Line2": "姫: \\\\v[3]日以内に来てください"'
        ),
        en=(
            '"Line1": "Princess: \\\\C[5]Please\\\\C[0]... \\\\N[1], '
            'save me.",'
            '\n    "Line2": "Princess: Please come within \\\\v[3] days."'
        ),
        tags=("SPEAKER", "COLOR", "SPAN", "VARIABLE"),
        priority=5,
    ),
    _Example(
        jp='"Line1": "\\\\rb[魔法陣,まほうじん]が光り始めた"',
        en='"Line1": "The \\\\rb[魔法陣,まほうじん] started to glow."',
        tags=("RUBY",),
        priority=7,
    ),
    _Example(
        jp=(
            '"Line1": "商人: \\\\i[320]伝説の剣……\\\\v[50]ゴールドだ",'
            '\n    "Line2": "商人: 高いと思うかい？\\\\n'
            '\\\\c[14]一生に一度の買い物\\\\c[0]だよ"'
        ),
        en=(
            '"Line1": "Merchant: \\\\i[320]The Legendary Sword...'
            '\\\\v[50] gold.",'
            '\n    "Line2": "Merchant: Think it\'s expensive?\\\\n'
            'It\'s \\\\c[14]a once-in-a-lifetime purchase\\\\c[0]."'
        ),
        tags=("COMPLEX", "SPEAKER", "ICON", "VARIABLE", "LINEBREAK", "COLOR"),
        priority=5,
    ),
    _Example(
        jp=(
            '"Line1": "\\\\SE[alarm]\\\\C[2]警告！\\\\C[0]'
            '\\\\n敵の増援が接近中！\\\\n残り時間: \\\\v[99]秒"'
        ),
        en=(
            '"Line1": "\\\\SE[alarm]\\\\C[2]Warning!\\\\C[0]'
            '\\\\nEnemy reinforcements approaching!\\\\nTime remaining: '
            '\\\\v[99] seconds."'
        ),
        tags=("COMPLEX", "MEDIA", "COLOR", "LINEBREAK", "VARIABLE"),
        priority=4,
    ),
    _Example(
        jp=(
            '"Line1": "少女: あ、__PROTECTED_0__さん！\\\\n'
            'お久しぶりです"'
        ),
        en=(
            '"Line1": "Girl: Oh, __PROTECTED_0__!\\\\n'
            'It\'s been a while."'
        ),
        tags=("PLACEHOLDER", "SPEAKER", "LINEBREAK"),
        priority=4,
    ),
    _Example(
        jp=(
            '"Line1": "■ステータス■",'
            '\n    "Line2": "攻撃力: \\\\v[21]",'
            '\n    "Line3": "防御力: \\\\v[22]",'
            '\n    "Line4": "素早さ: \\\\v[23]"'
        ),
        en=(
            '"Line1": "■Status■",'
            '\n    "Line2": "Attack: \\\\v[21]",'
            '\n    "Line3": "Defense: \\\\v[22]",'
            '\n    "Line4": "Speed: \\\\v[23]"'
        ),
        tags=("VARIABLE", "PRESERVE"),
        priority=7,
    ),
    _Example(
        jp=(
            '"Line1": "ナレーション: かくして、長い旅が始まった…"'
        ),
        en=(
            '"Line1": "Narration: And so, a long journey began..."'
        ),
        tags=("SPEAKER",),
        priority=9,
    ),
)

# Pattern tag → regex patterns that identify code in text
_TAG_PATTERNS: Dict[str, re.Pattern] = {
    "PLACEHOLDER": re.compile(r"__PROTECTED_?\d*__", re.IGNORECASE),
    "VARIABLE": re.compile(r"\\\\[vVnN]\[\d+\]"),
    "COLOR": re.compile(r"\\\\[cC]\[?\d*\]?"),
    "LINEBREAK": re.compile(r"\\\\n"),
    "MEDIA": re.compile(r"\\\\(?:SE|ME|pic)\[", re.IGNORECASE),
    "ICON": re.compile(r"\\\\i\[\d+\]", re.IGNORECASE),
    "FONT": re.compile(r"\\\\(?:FS\[\d+\]|fb|fr|[{}])", re.IGNORECASE),
    "RUBY": re.compile(r"\\\\rb\["),
    "SPAN": re.compile(r"\\\\[CF]S?\[\d+\].*?\\\\[CF]S?\[0?\]"),
}


# ---------------------------------------------------------------------------
# Language key resolution
# ---------------------------------------------------------------------------

_LANG_TO_KEY: Dict[str, str] = {
    "japanese": "jp",
    "english": "en",
}


def _resolve_example_keys(
    source_language: str,
    target_language: str,
) -> Tuple[str, str]:
    """Resolve which ``_Example`` fields to use for source and target.

    Maps language names to example keys (``jp``, ``en``).  When a
    language has no matching key the fallback is ``en`` unless English
    is already the source or target language (then ``jp``).

    Returns:
        ``(source_key, target_key)`` — field names on ``_Example``.
    """
    src = _LANG_TO_KEY.get(source_language.lower().strip())
    tgt = _LANG_TO_KEY.get(target_language.lower().strip())

    english_in_use = (
        source_language.lower().strip() == "english"
        or target_language.lower().strip() == "english"
    )
    fallback = "jp" if english_in_use else "en"

    if src is None:
        src = fallback
    if tgt is None:
        tgt = fallback

    # Ensure distinct keys
    if src == tgt:
        tgt = "jp" if src == "en" else "en"

    return src, tgt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_io_examples(
    code_patterns: Optional[List[Dict[str, Any]]] = None,
    source_language: str = "Japanese",
    target_language: str = "English",
    target_tokens: int = 1500,
) -> Tuple[str, int]:
    """Generate I/O example text for prompt injection.

    Builds a set of input/output JSON translation pairs from the
    example bank, prioritising lines that demonstrate code patterns
    present in the project manifest.  Source and target language are
    resolved to example-bank keys (``jp``, ``en``) with fallback.

    Args:
        code_patterns: Code patterns from manifest metadata. Each dict
            should have at least ``raw_type`` and ``pattern`` keys.
            Used to boost priority of matching examples.
        source_language: Source language name (from manifest).
        target_language: Target language name (from manifest).
        target_tokens: Approximate token budget for the example block.

    Returns:
        Tuple of ``(formatted_text, estimated_token_count)``.
        When the bank is empty or target is ≤0, returns ``("", 0)``.
    """
    if target_tokens <= 0:
        return "", 0

    # Resolve which _Example fields to use as source / target
    source_key, target_key = _resolve_example_keys(
        source_language, target_language,
    )

    # Determine which pattern tags are present in the project
    project_tags = _detect_project_tags(code_patterns or [])

    # Score and sort examples
    scored = _score_examples(project_tags)

    # Build formatted output within token budget
    return _build_output(scored, target_tokens, source_key, target_key)


def calculate_fill_target(
    static_prompt_tokens: int,
    model_id: str = "",
    provider: str = "openai",
) -> int:
    """Calculate how many I/O example tokens to generate for ``"fill"`` mode.

    Computes: ``optimal_cache_size − static_prompt_tokens``.
    Returns 0 when the static prompt already meets or exceeds the target.

    Args:
        static_prompt_tokens: Current token count of the static prompt
            (slots 1-7b, excluding I/O examples).
        model_id: Model ID for per-model override lookup.
        provider: Provider name for default threshold.

    Returns:
        Number of tokens to fill with I/O examples (≥0).
    """
    try:
        from CherryAI.functions.api_config import get_optimal_cache_size
    except ImportError:
        try:
            from functions.api_config import get_optimal_cache_size
        except ImportError:
            return max(0, 1536 - static_prompt_tokens)
    optimal = get_optimal_cache_size(model_id, provider)
    return max(0, optimal - static_prompt_tokens)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_project_tags(
    code_patterns: List[Dict[str, Any]],
) -> set:
    """Map project code patterns to example bank tags.

    Examines ``raw_type`` and ``pattern`` fields to determine which
    tag categories the project uses.
    """
    tags: set = set()
    type_map = {
        "LINEBREAK": "LINEBREAK",
        "VARIABLENAME": "VARIABLE",
        "VISIBLEVARIABLE": "VARIABLE",
        "COLOR": "COLOR",
        "FONT": "FONT",
        "RUBY": "RUBY",
        "ICON": "ICON",
        "MEDIA": "MEDIA",
    }
    for cp in code_patterns:
        raw_type = (cp.get("raw_type") or "").upper()
        if raw_type in type_map:
            tags.add(type_map[raw_type])
        # Also check the pattern string itself
        pattern_str = cp.get("pattern", "")
        for tag, regex in _TAG_PATTERNS.items():
            if regex.search(pattern_str):
                tags.add(tag)
    # PLACEHOLDER and SPEAKER are always relevant
    tags.add("PLACEHOLDER")
    tags.add("SPEAKER")
    return tags


def _score_examples(
    project_tags: set,
) -> List[Tuple[float, _Example]]:
    """Score and sort example pairs by relevance.

    Scoring: lower score = higher priority.
    - Base priority from the example itself (1-10)
    - Bonus (−5) for each tag matching project patterns
    - Penalty (+3) for examples with no matching tags

    Returns:
        Sorted list of (score, example) tuples.
    """
    scored: List[Tuple[float, _Example]] = []
    for ex in _EXAMPLE_BANK:
        score = float(ex.priority)
        matches = sum(1 for t in ex.tags if t in project_tags)
        if matches > 0:
            score -= 5.0 * matches
        else:
            score += 3.0
        scored.append((score, ex))
    scored.sort(key=lambda x: x[0])
    return scored


_LINE_KEY_RE = re.compile(r'"Line\d+"')


def _renumber_lines(text: str, start: int) -> Tuple[str, int]:
    """Renumber ``"LineN"`` keys in *text* starting from *start*.

    Returns (renumbered_text, next_available_number).
    """
    counter = start

    def _repl(m: re.Match) -> str:
        nonlocal counter
        result = f'"Line{counter}"'
        counter += 1
        return result

    return _LINE_KEY_RE.sub(_repl, text), counter


def _build_output(
    scored_examples: List[Tuple[float, _Example]],
    target_tokens: int,
    source_key: str = "jp",
    target_key: str = "en",
) -> Tuple[str, int]:
    """Assemble formatted I/O examples within token budget.

    Groups selected examples into JSON-style input/output blocks
    with sequential ``LineN`` keys.  Each line number is unique
    across the entire output and matched between its Input/Output
    pair.

    Args:
        scored_examples: Scored and sorted example list.
        target_tokens: Token budget.
        source_key: ``_Example`` field name for source text.
        target_key: ``_Example`` field name for target text.

    Returns:
        Tuple of (formatted_text, estimated_tokens).
    """
    # Reserve tokens for structural framing
    frame_overhead = estimate_tokens(
        "# Output Examples\n\nInput:\n{\n}\nOutput:\n{\n}\n"
    )
    budget = target_tokens - frame_overhead
    if budget <= 0:
        return "", 0

    # Per-block overhead (the Input:/Output: wrappers between blocks)
    block_frame = estimate_tokens("\n\nInput:\n{\n}\nOutput:\n{\n}")

    # Select examples that fit within budget
    selected: List[_Example] = []
    used_tokens = 0

    for _score, ex in scored_examples:
        src_text = getattr(ex, source_key)
        tgt_text = getattr(ex, target_key)
        pair_text = f"    {src_text}\n    {tgt_text}"
        pair_tokens = estimate_tokens(pair_text)
        # First block doesn't need extra framing, subsequent do
        extra = block_frame if selected and len(selected) % 3 == 0 else 0
        total_needed = pair_tokens + extra

        if used_tokens + total_needed > budget:
            # If we have reached 85% or more of budget, stop
            if used_tokens > budget * 0.85:
                break
            continue

        selected.append(ex)
        used_tokens += total_needed

    if not selected:
        return "", 0

    # Format the output as JSON input/output blocks
    parts: List[str] = ["# Output Examples"]

    # Group examples into blocks of 2-4 for readability
    block_size = 3 if len(selected) > 6 else 2
    line_counter = 1

    for i in range(0, len(selected), block_size):
        block = selected[i:i + block_size]

        # Track where this block's numbering starts
        block_start = line_counter

        # Renumber source lines
        raw_source_lines = []
        for ex in block:
            src_text = getattr(ex, source_key)
            renumbered, line_counter = _renumber_lines(
                src_text, line_counter,
            )
            raw_source_lines.append(f"    {renumbered}")

        # Renumber target lines from same starting point so
        # Input LineN ↔ Output LineN within the block
        out_counter = block_start
        raw_target_lines = []
        for ex in block:
            tgt_text = getattr(ex, target_key)
            renumbered, out_counter = _renumber_lines(
                tgt_text, out_counter,
            )
            raw_target_lines.append(f"    {renumbered}")

        # Advance counter for next block
        line_counter = max(line_counter, out_counter)

        parts.append(
            "Input:\n{\n" + ",\n".join(raw_source_lines) + "\n}"
        )
        parts.append(
            "Output:\n{\n" + ",\n".join(raw_target_lines) + "\n}"
        )

    result = "\n\n".join(parts)
    total_tokens = estimate_tokens(result)
    return result, total_tokens
