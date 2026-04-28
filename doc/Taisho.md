# Taisho KS Parsing Notes

## Verified File Structure

- The scenario files decode correctly as `cp932` / `ms-kanji`. Reading them as UTF-8 produces mojibake.
- Visible text is not identified by Japanese characters alone. Japanese also appears in:
	- tag lines such as `[列車の中 昼 univ rule=map02 time=500]`
	- labels such as `*a_01|旅立ちの日`
	- comments such as `; ムービー再生のsflagはパースモード時のみ有効`
- Speaker headers are visible text markers, not code. The main pattern is:

```text
^\s*【(?P<speaker>[^】]+)】(?:\[(?P<voice_id>[^\]]+)\])?\s*$
```

- Dedicated ruby delimiters were not found. No `《》`, `｜`, or `{...}` control syntax appears in this corpus, so regex-level “furigana” analysis must be treated as kana analysis rather than explicit ruby markup.

## Line Categories

The parser and audit script use these context regexes in order:

```text
Speaker:       ^\s*【(?P<speaker>[^】]+)】(?:\[(?P<voice_id>[^\]]+)\])?\s*$
Comment:       ^\s*;
Label:         ^\s*\*
At-command:    ^\s*@
Tag line:      ^\s*\[[^\]]*\]\s*$
Brace command: ^\s*\{[^{}]*\}\s*$
Fallback text: anything else
```

This ordering matters. A naive `contains Japanese` regex would misclassify more than twenty thousand Japanese-bearing code lines as visible text.

## Japanese Character Buckets

The audit script tracks Japanese characters with explicit regex ranges instead of `\w`.

```text
Kanji:     [\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF々〆ヵヶ]
Hiragana:  [\u3041-\u3096\u309D-\u309F]
Katakana:  [\u30A1-\u30FA\u30FD-\u30FF\u31F0-\u31FF\uFF66-\uFF9Fー]
Japanese:  union of the three sets above
```

Because there is no explicit ruby syntax in the files, kana is the only defensible regex bucket for furigana-like text at this stage.

## Extraction Strategy

- Extract only fallback text lines plus speaker headers.
- Ignore code lines even when they contain Japanese.
- Keep speaker metadata separate from spoken text so injection stays stable later.
- Join adjacent visible text lines with `\n`.
- Permit rare text-code-text bridges when the middle line is a soft command and the next significant line is still text.

Observed bridge examples:

```text
「役に立たなくてすまんね。
[伸彦伯父 基本]
そうだ、京一郎君、君に教えようと思っていた事がある。
```

```text
ミサキが掌を高く掲げる。
[se SE_a_140_1]
光の珠は風に乗ってふわりと浮いた。
```

That means a hard split on every tag line would lose valid continuous text blocks.

## Script Roles

- `ks_japanese_code_filter.py`
	- audits every Japanese-bearing line
	- counts Kanji, Hiragana, and Katakana by context
	- proves how much bleed a naive Japanese-character extractor would cause
- `ks_text_parser.py`
	- extracts visible text blocks
	- preserves speaker and voice ID metadata
	- records bridge code lines for review
	- includes a reinjection path that expects translated text to match original source line counts

## Current Conclusions

- Encoding must stay `cp932` unless the entire toolchain is intentionally migrated.
- Context regexes are mandatory. Character regexes alone are not enough.
- Speaker headers must be treated as UI-visible metadata.
- Kana counts are useful now; true furigana parsing will require a later pass only if ruby syntax appears in other assets.
