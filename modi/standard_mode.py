# Includes many small operations deemed as standard:
# -Ellipsis compression/decompression
# -Empty-line placeholder insertion/restoration
# -De/compression of PROT runs
# -Deduplication of repeated lines
from __future__ import annotations

import re
import logging
from collections import deque
from typing import List, Tuple, Any, Dict, Optional
import sqlite3
import hashlib
import time
import unicodedata

# Import EMPTY_LINE_PLACEHOLDER constant from shared helpers with fallbacks
try:
    from CherryAI.functions.modehelper import EMPTY_LINE_PLACEHOLDER
except Exception:
    try:
        from CherryAI.functions.modehelper import EMPTY_LINE_PLACEHOLDER
    except Exception:
        EMPTY_LINE_PLACEHOLDER = "__EMPTY__"

NAME = "Standard Helpers"
PHASE = "Both"
PRIORITY = 50
USES_REGEX = False
INPUTS: List[str] = []

# Manifest key for runtime-configurable standard-mode options exposed to GUI later
STANDARD_CONFIG_KEY = "standard_mode_config"


# ─────────────────────────────────────────────────────────────────────────────
# v2.0 Manifest Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _add_prepro_op(processor, idx: int, op_data: Dict[str, Any]) -> None:
    """Add a preprocessing operation to a line's prepro_ops."""
    processor.manifest.add_prepro_op(idx, op_data)


def _get_prepro_ops(processor, idx: int, mode: str) -> List[Dict[str, Any]]:
    """Get preprocessing operations for a line filtered by mode."""
    return processor.manifest.get_prepro_ops(idx, mode) or []


# Human-facing tooltip/help texts for the GUI. The GUI will import this mapping
# and display the corresponding help when users hover the control. Keep the
# authoritative wording here so the UI stays in sync with the implementation.
STANDARD_HELPERS_TOOLTIPS = {
    "dedup_box": (
        "Deduplication controls how repeated lines are temporarily replaced. "
        "Threshold semantics:\n"
        "  - 0: no duplicate line gets replaced with a placeholder (feature disabled).\n"
        "  - 1: every repeated occurrence of a line is replaced (first occurrence kept).\n"
        "  - N>1: when N consecutive identical lines occur, subsequent lines are replaced."
    ),
    "dedup": (
        "When enabled, consecutive identical non-empty lines beyond the configured "
        "threshold are temporarily replaced with a placeholder during Pre-TL and "
        "restored during Post-TL. Lower the threshold to 0 to disable deduplication."
    ),
    "ellipsis": "Enables / Disables temporary compression of any long ellipsis to one ellipsis.",
    "prot": "Enables / Disables temporary compression of any consecutive and unnamed protected code.",
    "replace_speakers": "When enabled, replace leading 'NAME:' style speakers using speakers.analysis.tsv (second column). Empty translation means skip.",
    "code_spacing": "When enabled, enforce spacing rules around code based on code.analysis.tsv toggles (IsInvisible/IsWord/IsNumber/IsBoundary).",
    "symbol_conversion": (
        "Changes Symbols as per selected language (Language selection TBD. Currently "
        "Japanese to English only.)"
    ),
}


def get_standard_config(processor) -> Dict[str, Any]:
    """Return the standard-mode configuration dict persisted in the manifest.

    Defaults are provided when no config exists. GUI can edit this mapping later
    to enable/disable features (for example deduplication) and to configure
    thresholds (for example dedup_threshold).
    """
    defaults: Dict[str, Any] = {
        # deduplication controls
        "dedup_enabled": True,
        "dedup_threshold": getattr(processor, "DEDUP_THRESHOLD_DEFAULT", 1),
        # placeholder for future toggles (ellipsis, prot compression etc.)
        "ellipsis_enabled": True,
        "prot_enabled": True,
        # New toggles
        "replace_speakers": False,
        "code_spacing": False,
    # Symbol conversion (JP -> EN by default; extensible)
    "symbol_conversion_enabled": True,
    "symbol_conversion_src_lang": getattr(processor, "SRC_LANG", "ja"),
    "symbol_conversion_tgt_lang": getattr(processor, "TGT_LANG", "en"),
        # Commonlines DB matching/candidates
        "commonlines_enabled": False,
        "commonlines_add_candidates": True,
        # Language direction (default ja->en but configurable to support any pair)
        "commonlines_src_lang": getattr(processor, "SRC_LANG", "ja"),
        "commonlines_tgt_lang": getattr(processor, "TGT_LANG", "en"),
    }
    mm = processor.manifest.mappings.setdefault(STANDARD_CONFIG_KEY, {})
    # ensure defaults for any missing keys
    for k, v in defaults.items():
        mm.setdefault(k, v)
    return mm

# This module contains two utility operations used by the processor pipelines:
# 1) Empty-line safeguard: when pre-processing causes non-empty lines to become empty,
#    insert a sentinel token to preserve line structure and record indices in the manifest.
#    On post-processing, restore sentinel tokens back to empty lines or remove them when
#    content was inserted onto the same line.
# 2) Ellipsis compression/decompression: collapse runs of ellipsis characters into a compact
#    representation at pre-time and record triplet counts for later restoration. Post-time will
#    expand the recorded triplets back into repeated '...' sequences.


def apply_pre(processor, lines: List[str], op, stats: Dict[str, int]) -> int:
    """Compress ellipsis-like runs on each line and record a mapping in the manifest.

    The processor's post-phase already performs final restoration, so this plugin's role
    is to normalize long runs of dots/ellipsis to a single '...' and record how many
    triplets to restore later. We record entries under manifest.mappings['ellipsis_lines']
    as dicts: {'line': int, 'triplets': List[int]} where triplets is a list of integers
    corresponding to each replacement occurrence on that line (left-to-right).
    """
    changes = 0
    # Symbol conversion should happen early (before ellipsis handling) so that
    # ellipsis compression can operate on unified '...'.
    try:
        cfg = get_standard_config(processor)
        if cfg.get("symbol_conversion_enabled", True):
            changes += _apply_symbol_conversion(lines, cfg, stats)
    except Exception:
        logging.exception("Standard mode: symbol conversion failed")

    # Only perform ellipsis compression if enabled in runtime config
    try:
        cfg = get_standard_config(processor)
        do_ellipsis = bool(cfg.get("ellipsis_enabled", True))
    except Exception:
        do_ellipsis = True
    if do_ellipsis:
        for idx, ln in enumerate(lines):
            new_ln, counts = compress_ellipsis_line(ln)
            if counts:
                lines[idx] = new_ln
                # Write to prepro_ops (primary storage)
                _add_prepro_op(
                    processor,
                    idx,
                    {
                        "mode": NAME,
                        "type": "ellipsis",
                        "triplets": counts,
                    },
                )
                changes += len(counts)

    # Empty-line safeguard: if the manifest has original lines, use them to detect
    # lines that became empty and record/insert a sentinel.
    try:
        # Use LineEntry.orig from manifest.lines if available
        if processor.manifest.lines and len(processor.manifest.lines) == len(lines):
            empty_added = 0
            for i, entry in enumerate(processor.manifest.lines):
                before = entry.orig
                after = lines[i]
                if before.strip() and not after.strip():
                    lines[i] = EMPTY_LINE_PLACEHOLDER
                    # Write to prepro_ops
                    _add_prepro_op(
                        processor,
                        i,
                        {
                            "mode": NAME,
                            "type": "empty_line",
                        },
                    )
                    empty_added += 1
            if empty_added:
                stats["empty_placeholder_added"] = stats.get("empty_placeholder_added", 0) + empty_added
    except Exception:
        # Be tolerant: this helper must not break processing
        pass

    # Note: deduplication is orchestrated centrally by the Processor and
    # runs before other Pre-mode plugins. Keep this helper focused on
    # ellipsis/empty-line responsibilities only to avoid double-calling.

    # Commonlines DB scan (optional) — does not mutate lines, only logs and records candidates
    try:
        cfg = get_standard_config(processor)
        if cfg.get("commonlines_enabled", False):
            found, candidates = _commonlines_scan_pre(processor, lines, cfg)
            if found:
                stats["commonlines_found"] = stats.get("commonlines_found", 0) + found
            if candidates:
                stats["commonlines_candidates"] = stats.get("commonlines_candidates", 0) + candidates
    except Exception:
        logging.exception("Standard mode: commonlines scan failed")

    return changes


def _deduplicate_pre(processor, lines: List[str], threshold: int) -> int:
    """Collapse consecutive identical non-empty lines beyond threshold.
    Records collapsed entries under manifest.mappings['dedup_lines'] as a list
    of records. New record format (backwards-compatible):
      - {'idx': <int>, 'text': '<original line text>'}
    Older manifests may contain a list of ints; the post-phase will accept both.
    Returns number of collapsed replacements made.
    """
        # NOTE: This is a thin wrapper used by the Standard Helpers pre-phase.
        # Called from: `CherryAI.functions.mainhelper.Processor.process_pre`
        #                 -> this module's `apply_pre` -> `_deduplicate_pre`
        # Delegates to: `CherryAI.functions.dedup.deduplicate_pre` when available.
        # Rationale: keep a local wrapper so the standard-mode API remains stable and
        # the implementation can be centralized in `functions/dedup.py`.
    dedup_entries: List[Any] = processor.manifest.mappings.setdefault("dedup_lines", [])
    changes = 0
    run_value = None
    run_count = 0
    run_start_idx: Optional[int] = None
    # Accept processor-provided sentinel, default to the canonical double-underscore form
    placeholder = getattr(processor, "DEDUP_PLACEHOLDER", "__DEDUP__")
    # Deduplication is now the responsibility of `functions.dedup` and is
    # orchestrated by the Processor. This wrapper is retained for API
    # compatibility but intentionally does nothing to avoid double-calling.
    return 0


def _deduplicate_post(processor, lines: List[str]) -> int:
    """Expand placeholder entries recorded in manifest.mappings['dedup_lines'].

    This function is the post-phase companion to `_deduplicate_pre` and is
    intentionally a small delegating wrapper. It is invoked from:
      - This module's `apply_post` (called by the Processor post phase), and
      - Indirectly by `CherryAI.functions.mainhelper.Processor.process_post`.

    Implementation: delegate to `CherryAI.functions.dedup.deduplicate_post` if
    available; otherwise behave as a tolerant no-op (to avoid breaking processing).
    Returns the number of restored placeholders.
    """
    # Deduplication restore is handled centrally by the Processor (post).
    # Keep a no-op wrapper here for backward compatibility with code/tests
    # that may import the symbol, but the actual restore will have been
    # performed by Processor.process_post.
    return 0



def apply_post(processor, lines: List[str], op, stats: Dict[str, int]) -> int:
    """Restore ellipsis and empty-line placeholders from prepro_ops."""
    # First: ellipsis restoration from recorded triplets
    # Only restore ellipses when enabled in runtime config
    try:
        cfg = get_standard_config(processor)
        do_ellipsis = bool(cfg.get("ellipsis_enabled", True))
    except Exception:
        do_ellipsis = True
    if do_ellipsis:
        try:
            per_line: Dict[int, deque] = {}

            # Read from prepro_ops (primary storage)
            for idx in range(len(lines)):
                ops = _get_prepro_ops(processor, idx, NAME)
                for op_data in ops:
                    if op_data.get("type") == "ellipsis":
                        tlist = op_data.get("triplets", [])
                        if tlist:
                            per_line.setdefault(idx, deque()).extend(tlist)

            if per_line:
                dot_pattern = re.compile(r"\.\s*\.\s*\.")
                restored_total = 0
                for ln, dq in per_line.items():
                    if ln >= len(lines) or ln < 0:
                        continue
                    line = lines[ln]

                    def repl_post(m: re.Match[str]) -> str:
                        if not dq:
                            return m.group(0)
                        t = dq.popleft()
                        return "..." * t

                    new_line, c = dot_pattern.subn(repl_post, line)
                    lines[ln] = new_line
                    if dq:
                        # Do NOT append leftover triplets to the line. Only log the shortfall
                        # so restoration failures are visible; do not mutate content further.
                        logging.error(
                            "Ellipsis restore shortfall on line %d; %d triplet(s) left unresolved",
                            ln + 1,
                            len(dq),
                        )
                        stats["ellipsis_restore"] = stats.get("ellipsis_restore", 0) + len(dq)
                    restored_total += c
                if restored_total:
                    stats["ellipsis_restored"] = stats.get("ellipsis_restored", 0) + restored_total
        except Exception:
            logging.exception("Standard mode: ellipsis restoration failed")

    # Then: Attempt to restore any empty-line placeholders
    try:
        empty_indices: set = set()

        # Check prepro_ops for empty_line markers
        for idx in range(len(lines)):
            ops = _get_prepro_ops(processor, idx, NAME)
            for op_data in ops:
                if op_data.get("type") == "empty_line":
                    empty_indices.add(idx)

        restored = 0
        for idx in empty_indices:
            if 0 <= idx < len(lines) and lines[idx].strip() == EMPTY_LINE_PLACEHOLDER:
                lines[idx] = ""
                restored += 1
            elif 0 <= idx < len(lines) and EMPTY_LINE_PLACEHOLDER in lines[idx]:
                lines[idx] = lines[idx].replace(EMPTY_LINE_PLACEHOLDER, "")
                restored += 1
        if restored:
            stats["empty_placeholder_restored"] = stats.get("empty_placeholder_restored", 0) + restored
    except Exception:
        logging.exception("Standard mode: empty-line restoration failed")

    # Speaker replacement (at end of Post-TL before spacing)
    try:
        cfg = get_standard_config(processor)
        if cfg.get("replace_speakers", False):
            _apply_speaker_replacements(lines, stats)
    except Exception:
        logging.exception("Standard mode: speaker replacement failed")

    # Code spacing rules based on glossary toggles
    try:
        cfg = get_standard_config(processor)
        if cfg.get("code_spacing", False):
            _apply_code_spacing(lines, stats, processor=processor)
    except Exception:
        logging.exception("Standard mode: code spacing failed")

    # Deduplication restoration is performed centrally by the Processor.
    # This module no longer executes dedup restore to avoid duplicate work.

    return 0


# ---------------- Speaker replacement ---------------- #

def _read_tsv(path: str) -> List[List[str]]:
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            import csv
            rows = [row for row in csv.reader(f, delimiter="\t")]
            # Skip header rows when present
            if rows and rows[0]:
                h0 = str(rows[0][0]).strip().lower()
                if h0 in ("speaker", "code"):
                    rows = rows[1:]
            return rows
    except Exception:
        return []


def _speakers_glossary_path() -> str:
    from pathlib import Path
    here = Path(__file__).resolve()
    return str(here.parent.parent / "functions" / "glossaries" / "speakers.analysis.tsv")


def _code_glossary_path() -> str:
    from pathlib import Path
    here = Path(__file__).resolve()
    return str(here.parent.parent / "functions" / "glossaries" / "code.analysis.tsv")


def _apply_speaker_replacements(lines: List[str], stats: Dict[str, int]) -> None:
    rows = _read_tsv(_speakers_glossary_path())
    if not rows:
        return
    repl_map: Dict[str, str] = {}
    for r in rows:
        if not r:
            continue
        name = r[0].strip()
        # Column 1 is translation; ignore any trailing Comment column
        trans = (r[1].strip() if len(r) > 1 else "")
        if name and trans:
            repl_map[name] = trans
    if not repl_map:
        return
    # Replace only when a line starts with NAME: or NAME： (after optional whitespace)
    import re as _re
    # Build an alternation of names, escape for regex
    name_alt = "|".join(sorted((_re.escape(n) for n in repl_map.keys()), key=len, reverse=True))
    pat = _re.compile(rf"^(\s*)(?P<name>{name_alt})\s*[:：]")
    changed = 0
    for i, ln in enumerate(lines):
        m = pat.match(ln)
        if not m:
            continue
        new = f"{m.group(1)}{repl_map.get(m.group('name'), m.group('name'))}:" + ln[m.end():]
        if new != ln:
            lines[i] = new
            changed += 1
    if changed:
        stats["speakers_replaced"] = stats.get("speakers_replaced", 0) + changed


# ---------------- Code spacing ---------------- #

def _apply_code_spacing(
    lines: List[str],
    stats: Dict[str, int],
    processor: Any = None,
) -> None:
    rows = _read_tsv(_code_glossary_path())
    # TASK 42.7: Also read code_patterns from manifest for spacing tags
    manifest_spacing: Dict[str, str] = {}
    if processor is not None:
        try:
            code_pats = processor.manifest.mappings.get("code_patterns", [])
            if not code_pats:
                try:
                    code_pats = getattr(processor.manifest, "_manifest_data", {}).get(
                        "code_patterns", [],
                    )
                except Exception:
                    code_pats = []
            for cp in code_pats or []:
                if isinstance(cp, dict) and cp.get("pattern"):
                    pat = cp["pattern"]
                    if not cp.get("visible", True):
                        manifest_spacing[pat] = "invisible"
                    else:
                        spacing = cp.get("spacing", "preserve")
                        if spacing == "none":
                            manifest_spacing[pat] = "invisible"
                        elif spacing == "normalize":
                            manifest_spacing[pat] = "word"
                        # "preserve" means no modification
        except Exception:
            pass
    if not rows:
        return
    # Build classification map; skip if multiple TRUE flags set for a code item (warn once)
    import logging as _log
    cls_map: Dict[str, str] = {}  # code -> class: invisible|word|number|boundary
    warned_multi = 0
    for r in rows:
        if not r:
            continue
        code = r[0]
        # Columns 1..4 are flags; ignore any trailing Comment column
        flags = [(r[i].strip().upper() == "TRUE") if i < len(r) else False for i in range(1, 5)]
        if sum(1 for x in flags if x) == 1:
            if flags[0]:
                cls_map[code] = "invisible"
            elif flags[1]:
                cls_map[code] = "word"
            elif flags[2]:
                cls_map[code] = "number"
            elif flags[3]:
                cls_map[code] = "boundary"
        elif any(flags):
            if warned_multi < 5:
                _log.warning("Code glossary: multiple TRUE flags for %r — skipping", code)
                warned_multi += 1
    if not cls_map:
        # TASK 42.7: Use manifest spacing if TSV has no data
        cls_map = manifest_spacing
    else:
        # TASK 42.7: Merge manifest spacing (overrides TSV when present)
        cls_map.update(manifest_spacing)
    if not cls_map:
        return

    # Spacing rules
    import re as _re
    changed = 0
    # iterate lines and for each code key, normalize spacing around its occurrences
    # Always strip any space around the code first
    for i, ln in enumerate(lines):
        new_ln = ln
        for code, kind in cls_map.items():
            if not code:
                continue
            esc = _re.escape(code)
            # strip spaces around occurrences
            new_ln = _re.sub(rf"\s*({esc})\s*", r"\1", new_ln)
            if kind == "invisible":
                continue
            # helpers for context
            def is_word_char(ch: str) -> bool:
                return ch.isalnum()
            def is_punct_before(ch: str) -> bool:
                return ch in ") . : ! ? ,".split()
            matches = list(_re.finditer(esc, new_ln))
            if not matches:
                continue
            # apply per match with offset adjustments
            offset = 0
            for m in matches:
                s = m.start() + offset
                e = m.end() + offset
                before = new_ln[s - 1] if s > 0 else ""
                after = new_ln[e] if e < len(new_ln) else ""
                if kind in ("word", "number"):
                    # add one space after if next is letter/number
                    if after and is_word_char(after):
                        new_ln = new_ln[:e] + " " + new_ln[e:]
                        offset += 1
                    # add one space before if prev is letter/number or punctuation set
                    if before and (is_word_char(before) or is_punct_before(before)):
                        new_ln = new_ln[:s] + " " + new_ln[s:]
                        offset += 1
                elif kind == "boundary":
                    # First instance: space before if prev is letter/number or punctuation set
                    # Second instance: space after if next is letter/number
                    # We apply by counting occurrences per line per code
                    pass
            # boundary handling: re-run with index to apply first/second instance rules
            if kind == "boundary":
                matches = list(_re.finditer(esc, new_ln))
                offset = 0
                for idx_m, m in enumerate(matches, start=1):
                    s = m.start() + offset
                    e = m.end() + offset
                    before = new_ln[s - 1] if s > 0 else ""
                    after = new_ln[e] if e < len(new_ln) else ""
                    if idx_m == 1:
                        if before and (before.isalnum() or before in ") . : ! ? ,".split()):
                            new_ln = new_ln[:s] + " " + new_ln[s:]
                            offset += 1
                    elif idx_m == 2:
                        if after and after.isalnum():
                            new_ln = new_ln[:e] + " " + new_ln[e:]
                            offset += 1
        if new_ln != ln:
            lines[i] = new_ln
            changed += 1
    if changed:
        stats["code_spacing_applied"] = stats.get("code_spacing_applied", 0) + changed


# ---------------- Commonlines DB helpers ---------------- #

# ---------------- Symbol conversion (extensible) ---------------- #

# Normalize language identifiers to compact keys
_LANG_ALIASES: Dict[str, str] = {
    # Japanese
    "ja": "jpn", "jpn": "jpn", "jap": "jpn", "jp": "jpn",
    # English
    "en": "eng", "eng": "eng", "english": "eng",
    # German
    "de": "ger", "ger": "ger", "deu": "ger", "german": "ger",
    # French
    "fr": "fra", "fra": "fra", "fre": "fra", "french": "fra",
    # Spanish
    "es": "spa", "spa": "spa", "spanish": "spa",
}


# Symbol sets grouped by semantic category; values list multiple languages that
# share the same glyph to keep the mapping short and maintainable.
_SYMBOL_SETS: Dict[str, Dict[str, str]] = {
    # Quotes
    "Opening_Quote": {"jpn": "「", "eng": '"', "ger": '"', "fra": '"', "spa": '"'},
    "Closing_Quote": {"jpn": "」", "eng": '"', "ger": '"', "fra": '"', "spa": '"'},
    "Alt_Opening_Quote": {"jpn": "『", "eng": "'", "ger": "'", "fra": "'", "spa": "'"},
    "Alt_Closing_Quote": {"jpn": "』", "eng": "'", "ger": "'", "fra": "'", "spa": "'"},
    # Punctuation
    "Comma": {"jpn": "、", "eng": ",", "ger": ",", "fra": ",", "spa": ","},
    "Period": {"jpn": "。", "eng": ".", "ger": ".", "fra": ".", "spa": "."},
    "Exclamation": {"jpn": "！", "eng": "!", "ger": "!", "fra": "!", "spa": "!"},
    "Question": {"jpn": "？", "eng": "?", "ger": "?", "fra": "?", "spa": "?"},
    "Colon": {"jpn": "：", "eng": ":", "ger": ":", "fra": ":", "spa": ":"},
    "Semicolon": {"jpn": "；", "eng": ";", "ger": ";", "fra": ";", "spa": ";"},
    # Parentheses
    "LParen": {"jpn": "（", "eng": "(", "ger": "(", "fra": "(", "spa": "("},
    "RParen": {"jpn": "）", "eng": ")", "ger": ")", "fra": ")", "spa": ")"},
    # Special Brackets
    "LBracket_Black": {"jpn": "【", "eng": "[", "ger": "[", "fra": "[", "spa": "["},
    "RBracket_Black": {"jpn": "】", "eng": "]", "ger": "]", "fra": "]", "spa": "]"},
    "LBracket_Double": {"jpn": "《", "eng": "<", "ger": "<", "fra": "<", "spa": "<"},
    "RBracket_Double": {"jpn": "》", "eng": ">", "ger": ">", "fra": ">", "spa": ">"},
    # Percent
    "Percent": {"jpn": "％", "eng": "%", "ger": "%", "fra": "%", "spa": "%"},
    # Operators
    "Equals": {"jpn": "＝", "eng": "=", "ger": "=", "fra": "=", "spa": "="},
    "Plus": {"jpn": "＋", "eng": "+", "ger": "+", "fra": "+", "spa": "+"},
    "Minus": {"jpn": "－", "eng": "-", "ger": "-", "fra": "-", "spa": "-"},
    # Misc
    "Tilde": {"jpn": "～", "eng": "~", "ger": "~", "fra": "~", "spa": "~"},
    "Slash": {"jpn": "／", "eng": "/", "ger": "/", "fra": "/", "spa": "/"},
    "Ampersand": {"jpn": "＆", "eng": "&", "ger": "&", "fra": "&", "spa": "&"},
    "At": {"jpn": "＠", "eng": "@", "ger": "@", "fra": "@", "spa": "@"},
    "Asterisk": {"jpn": "＊", "eng": "*", "ger": "*", "fra": "*", "spa": "*"},
    # Ellipsis (map the single-glyph ellipsis to three dots)
    "Ellipsis": {"jpn": "…", "eng": "...", "ger": "...", "fra": "...", "spa": "..."},
}


def _normalize_lang(code: str) -> str:
    try:
        return _LANG_ALIASES.get(str(code).strip().lower(), str(code).strip().lower())
    except Exception:
        return str(code or "").strip().lower()


def _build_symbol_replacements(src_lang: str, tgt_lang: str) -> Dict[str, str]:
    src = _normalize_lang(src_lang)
    tgt = _normalize_lang(tgt_lang)
    repl: Dict[str, str] = {}
    if not src or not tgt or src == tgt:
        return repl
    # Category-based mappings
    for _cat, values in _SYMBOL_SETS.items():
        s = values.get(src)
        t = values.get(tgt)
        if s and t and s != t:
            repl[s] = t
    # Full-width characters -> ASCII when source is Japanese and target uses Latin
    if src == "jpn" and tgt in {"eng", "ger", "fra", "spa"}:
        # Fullwidth digits
        fw_digits = "０１２３４５６７８９"
        hw_digits = "0123456789"
        for a, b in zip(fw_digits, hw_digits):
            if a != b:
                repl[a] = b
        # Fullwidth uppercase letters (Ａ-Ｚ)
        fw_upper = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
        hw_upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for a, b in zip(fw_upper, hw_upper):
            repl[a] = b
        # Fullwidth lowercase letters (ａ-ｚ)
        fw_lower = "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
        hw_lower = "abcdefghijklmnopqrstuvwxyz"
        for a, b in zip(fw_lower, hw_lower):
            repl[a] = b
    return repl


def _apply_symbol_conversion(lines: List[str], cfg: Dict[str, Any], stats: Dict[str, int]) -> int:
    src = str(cfg.get("symbol_conversion_src_lang", "ja"))
    tgt = str(cfg.get("symbol_conversion_tgt_lang", "en"))
    table = _build_symbol_replacements(src, tgt)
    if not table:
        return 0
    # Compile alternation of all source tokens, longest-first to avoid partial overlaps
    keys = sorted(table.keys(), key=len, reverse=True)
    pat = re.compile("|".join(re.escape(k) for k in keys))

    total_replacements = 0
    lines_changed = 0
    for i, ln in enumerate(lines):
        if not ln:
            continue
        # Count matches then substitute
        matches = pat.findall(ln)
        if not matches:
            continue
        new_ln = pat.sub(lambda m: table[m.group(0)], ln)
        if new_ln != ln:
            lines[i] = new_ln
            lines_changed += 1
            total_replacements += len(matches)
    if lines_changed:
        stats["symbol_conversion_lines"] = stats.get("symbol_conversion_lines", 0) + lines_changed
        stats["symbol_conversion_replacements"] = stats.get("symbol_conversion_replacements", 0) + total_replacements
    return total_replacements


def _commonlines_db_path() -> str:
    # Fixed location next to this module: CherryAI/modi/commonlines.db
    from pathlib import Path
    here = Path(__file__).resolve()
    return str(here.parent / "commonlines.db")


def _commonlines_init_db() -> None:
    con = sqlite3.connect(_commonlines_db_path())
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_hash TEXT NOT NULL,
                src_lang TEXT NOT NULL,
                src_text TEXT NOT NULL,
                tgt_lang TEXT NOT NULL,
                tgt_text TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_seen REAL NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(src_hash, src_lang, tgt_lang)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_hash TEXT NOT NULL,
                src_lang TEXT NOT NULL,
                src_text TEXT NOT NULL,
                rule TEXT,
                seen_count INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                last_seen REAL NOT NULL,
                UNIQUE(src_hash, src_lang)
            )
            """
        )
        con.commit()
    finally:
        con.close()


def _normalize_for_commonlines(text: str, lang: str) -> str:
    # Unicode normalization
    s = unicodedata.normalize("NFKC", text or "")
    # Normalize ellipsis-like runs via existing helper
    s, _ = compress_ellipsis_line(s)
    # Collapse 3+ repeating non-space chars to two occurrences
    s = re.sub(r"([^\s])\1{2,}", r"\1\1", s)
    # Collapse whitespace to single space; trim
    s = re.sub(r"\s+", " ", s).strip()
    # Case-fold for scripts using Latin letters to improve matching across casing
    if re.search(r"[A-Za-z]", s):
        s = s.lower()
    # Remove zero-width characters
    s = s.replace("\u200b", "").replace("\ufeff", "")
    return s


def _hash_for_commonlines(norm: str, lang: str) -> str:
    key = f"{lang}:{norm}".encode("utf-8")
    return hashlib.sha256(key).hexdigest()


def _line_is_candidate(text: str) -> bool:
    if not text or not text.strip():
        return False
    t = text.strip()
    # Skip internal placeholders and pure punctuation lines
    if t == EMPTY_LINE_PLACEHOLDER or t == getattr(__import__(__name__), 'PROT_TOKEN', '__PROT__'):
        return False
    # If after removing common punctuation and all Cc,Cf, and spaces nothing remains, skip
    def _is_meaningful(ch: str) -> bool:
        cat = unicodedata.category(ch)
        if cat.startswith("L") or cat.startswith("N"):  # letters or numbers
            return True
        # keep some symbols often used as words in JP (e.g., kana/kanji already covered by L)
        return False
    if not any(_is_meaningful(ch) for ch in t):
        return False
    return True


def _commonlines_scan_pre(processor, lines: List[str], cfg: Dict[str, Any]) -> Tuple[int, int]:
    """Scan lines against the commonlines DB.

    Returns (found_matches, candidates_recorded). Does not mutate lines.
    Records details into manifest.mappings['commonlines_found'] as a list of dicts.
    """
    _commonlines_init_db()
    src_lang = str(cfg.get("commonlines_src_lang", getattr(processor, "SRC_LANG", "ja")))
    tgt_lang = str(cfg.get("commonlines_tgt_lang", getattr(processor, "TGT_LANG", "en")))
    add_candidates = bool(cfg.get("commonlines_add_candidates", True))

    found = 0
    cand = 0
    found_list: List[Dict[str, Any]] = processor.manifest.mappings.setdefault("commonlines_found", [])

    now = time.time()
    con = sqlite3.connect(_commonlines_db_path())
    try:
        cur = con.cursor()
        for idx, ln in enumerate(lines):
            if not _line_is_candidate(ln):
                continue
            norm = _normalize_for_commonlines(ln, src_lang)
            h = _hash_for_commonlines(norm, src_lang)
            # Query for a known target
            cur.execute(
                "SELECT tgt_text FROM entries WHERE src_hash=? AND src_lang=? AND tgt_lang=?",
                (h, src_lang, tgt_lang),
            )
            row = cur.fetchone()
            if row and row[0]:
                found += 1
                found_list.append({
                    "line": idx,
                    "hash": h,
                    "src": ln,
                    "norm": norm,
                    "tgt": row[0],
                    "src_lang": src_lang,
                    "tgt_lang": tgt_lang,
                })
                # Bump last_seen/used_count lightly (used_count indicates reuse potential)
                try:
                    cur.execute(
                        "UPDATE entries SET last_seen=?, used_count=used_count+1 WHERE src_hash=? AND src_lang=? AND tgt_lang=?",
                        (now, h, src_lang, tgt_lang),
                    )
                except Exception:
                    pass
                continue

            if add_candidates:
                # Record or bump candidate
                try:
                    cur.execute(
                        """
                        INSERT INTO candidates (src_hash, src_lang, src_text, rule, seen_count, created_at, last_seen)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(src_hash, src_lang) DO UPDATE SET
                            src_text=excluded.src_text,
                            last_seen=excluded.last_seen,
                            seen_count=seen_count+1
                        """,
                        (h, src_lang, ln, "default", 1, now, now),
                    )
                    cand += 1
                except Exception:
                    # Ignore failures recording candidates
                    pass
        con.commit()
    finally:
        con.close()

    return found, cand


def _commonlines_import_tsv(tsv_path: str, src_lang: str = "ja", tgt_lang: str = "en") -> int:
    """Import pairs from a TSV file into the commonlines DB.

    Expects two columns: source<TAB>target. Returns number of upserts.
    """
    _commonlines_init_db()
    count = 0
    now = time.time()
    con = sqlite3.connect(_commonlines_db_path())
    try:
        cur = con.cursor()
        with open(tsv_path, "r", encoding="utf-8", newline="") as f:
            for raw in f:
                line = raw.strip("\n\r")
                if not line.strip():
                    continue
                # Split by tab first; if no tab, split by 2+ spaces
                if "\t" in line:
                    parts = [p.strip() for p in line.split("\t")]
                else:
                    parts = [p.strip() for p in re.split(r"\s{2,}", line)]
                if len(parts) < 2:
                    # Fallback: split once on first whitespace
                    parts = [p.strip() for p in re.split(r"\s+", line, maxsplit=1)]
                if len(parts) < 2:
                    continue
                src, tgt = parts[0], parts[1]
                if not src or not tgt:
                    continue
                norm = _normalize_for_commonlines(src, src_lang)
                h = _hash_for_commonlines(norm, src_lang)
                cur.execute(
                    """
                    INSERT INTO entries (src_hash, src_lang, src_text, tgt_lang, tgt_text, created_at, last_seen, used_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(src_hash, src_lang, tgt_lang) DO UPDATE SET
                        src_text=excluded.src_text,
                        tgt_text=excluded.tgt_text,
                        last_seen=excluded.last_seen
                    """,
                    (h, src_lang, src, tgt_lang, tgt, now, now),
                )
                count += 1
        con.commit()
    finally:
        con.close()
    return count


# Additionally, provide helper functions that other plugins or tests can import.

ELLIPSIS_PATTERN = re.compile(r"(\.{3,}|(?:\.{1}(?:\s*\.){2,}))")


def compress_ellipsis_line(line: str) -> Tuple[str, List[int]]:
    """Compress runs of ellipsis-like sequences into a normalized '...' and return a list
    of triplet counts per match. Each integer indicates how many '...' groups the original
    run represents (so 1 means a single '...' originally, 3 means '.........' -> 3 triplets).
    """
    matches = list(ELLIPSIS_PATTERN.finditer(line))
    if not matches:
        return line, []
    new_line = line
    counts: List[int] = []
    # Replace from right to left to preserve indices
    for m in reversed(matches):
        s = m.group(0)
        # Count dots ignoring spaces
        dots = len([c for c in s if c == "."])
        triplets = dots // 3
        if triplets <= 0:
            triplets = 1
        counts.insert(0, triplets)
        start, end = m.start(), m.end()
        new_line = new_line[:start] + "..." + new_line[end:]
    return new_line, counts


def decompress_ellipsis_line(line: str, counts: List[int]) -> str:
    """Expand normalized '...' tokens back into repeated '...' segments according to counts.

    counts is a list of integers corresponding to each replacement occurrence in left-to-right
    order.
    """
    if not counts:
        return line
    # find current occurrences of '...'
    pattern = re.compile(re.escape("..."))
    matches = list(pattern.finditer(line))
    if not matches:
        return line
    new_line = line
    # Expand from right to left using counts reversed
    for idx, cnt in sorted(enumerate(counts), key=lambda x: x[0], reverse=True):
        if idx < 0 or idx >= len(matches):
            continue
        m = matches[idx]
        insert_at = m.end()
        new_line = new_line[:insert_at] + ("..." * (cnt - 1)) + new_line[insert_at:]
    return new_line


# ---------------------------- PROT helpers (moved here) ---------------------------- #
PROT_PATTERN = re.compile(r"__\s*PROT\s*__")
PROT_TOKEN = "__PROT__"


def compress_prot_line(line: str) -> Tuple[str, List[Tuple[int, int]]]:
    matches = list(PROT_PATTERN.finditer(line))
    if not matches:
        return line, []
    spans = [(m.start(), m.end()) for m in matches]
    clusters: List[Tuple[int, int]] = []
    i = 0
    n = len(spans)
    while i < n:
        j = i
        while j + 1 < n and line[spans[j][1]:spans[j + 1][0]].strip() == "":
            j += 1
        run_len = j - i + 1
        if run_len > 1:
            clusters.append((i, run_len))
        i = j + 1
    if not clusters:
        return line, []
    new_line = line
    for occ_idx, count in reversed(clusters):
        start = spans[occ_idx][0]
        end = spans[occ_idx + count - 1][1]
        new_line = new_line[:start] + PROT_TOKEN + new_line[end:]
    return new_line, clusters


def decompress_prot_line(line: str, clusters: List[Tuple[int, int]]) -> str:
    if not clusters:
        return line
    new_line = line
    for occ_idx, count in sorted(clusters, key=lambda x: x[0], reverse=True):
        if count <= 1:
            continue
        cur_matches = [m for m in PROT_PATTERN.finditer(new_line)]
        if occ_idx < 0 or occ_idx >= len(cur_matches):
            continue
        m = cur_matches[occ_idx]
        insert_at = m.end()
        insertion = PROT_TOKEN * (count - 1)
        new_line = new_line[:insert_at] + insertion + new_line[insert_at:]
    return new_line


def compress_all_prot_lines(processor, lines: List[str]) -> int:
    """Compress PROT runs on all lines and record prot_clusters in manifest."""
    # Respect runtime config
    try:
        cfg = get_standard_config(processor)
        if not bool(cfg.get("prot_enabled", True)):
            return 0
    except Exception:
        pass
    changed = 0
    prot_clusters = processor.manifest.mappings.setdefault("prot_clusters", {})
    for i, ln in enumerate(lines):
        new_ln, clusters = compress_prot_line(ln)
        if clusters:
            lines[i] = new_ln
            prot_clusters[str(i)] = clusters
            changed += len(clusters)
    return changed


def decompress_all_prot_lines(processor, lines: List[str]) -> int:
    """Decompress recorded PROT clusters into the current lines using manifest data."""
    # Respect runtime config
    try:
        cfg = get_standard_config(processor)
        if not bool(cfg.get("prot_enabled", True)):
            return 0
    except Exception:
        pass
    changed = 0
    prot_clusters_map: Dict[str, List[Tuple[int, int]]] = processor.manifest.mappings.get("prot_clusters", {})
    if not isinstance(prot_clusters_map, dict):
        return 0
    for k, clusters in prot_clusters_map.items():
        try:
            ln_idx = int(k)
            if 0 <= ln_idx < len(lines):
                lines[ln_idx] = decompress_prot_line(lines[ln_idx], clusters)
                changed += 1
        except Exception:
            pass
    return changed
 
