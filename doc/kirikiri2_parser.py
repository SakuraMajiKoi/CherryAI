#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purpose:
  Parser for KiriKiri2/KAG script files (.ks).
  Extracts in-game visible text and injects translations back.

Extracted text includes:
  - Speaker names from [name text="..."] tags
  - Dialogue inside Japanese quotes: 「...」
  - Narration/plain Japanese lines that are not comments or pure commands

Non-translatable content ignored:
  - Developer/SFX comments beginning with ';'
  - Engine commands in brackets without translatable attributes (except [name text])

XLSX format contract (handled by main parser):
  - Two columns only: Original (A), Translated (B)
  - This module emits rows as dicts with at least 'name'.
  - For context grouping, a context-marker row is inserted whenever context changes,
    with 'name' containing a marker string and 'Translated' prefilled with a human label.
    Prefilled B-cells are skipped by the translation API.
"""
from __future__ import annotations

import re

from pathlib import Path
from typing import Any, Dict, List
import re
import codecs
import shutil

# --- Module Configuration ---
# Only process .ks files; TJS is patched via a project-level hook, not via scanning.
FILE_TYPES = (".ks",)
MODULE_NAME = "KiriKiri2 KAG Script"
# Request UTF-16 LE with BOM for injected .ks files (KAG expects this on Windows)
OUTPUT_ENCODING = "utf-16-le"
OUTPUT_BOM = True
ENABLE_TJS_WORDWRAP_PATCH = True  # Optional: auto-patch MainWindow.tjs with word-wrapping (enabled by default)


# --- Regexes ---
RE_NAME_TAG = re.compile(r"\[name\s+text\s*=\s*\"(.*?)\"\]", re.IGNORECASE)
# Support Japanese quotes (「…」, 『…』), parentheses ((…), （…）), and smart/ASCII quotes (“…”, ")
# Group1=open bracket/quote, Group2=inner text, Group3=close bracket/quote
RE_DIALOG = re.compile(r'([「『（(“"])(.*?)([」』）)”"])')

# Match lines like: 【車掌】 or 【車掌】[A_車掌_001] — treat as speaker marker lines
RE_FULLWIDTH_NAME = re.compile(r'^[【「『](?P<name>.+?)[】」』]\s*(?:\[[^\]]+\])?$')

# --- Excel String Sanitizer ---
def sanitize_excel_string(s: str) -> str:
    # Remove all illegal control characters for Excel (except \t, \n, \r)
    return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", s)



def extract(data: Any, file_path: Path, **kwargs) -> Dict[str, List[Dict[str, str]]]:
    """Extracts translatable strings from a .ks script.

    - Speaker names are appended to dialogue lines as 'Speaker: Dialogue'.
    - Merges quoted dialogue split by engine tags/comments into a single row.
    - Narration lines (no speaker) are extracted as-is.
    """
    if not isinstance(data, str):
        return {}

    lines = data.splitlines()
    rows: List[Dict[str, str]] = []
    current_speaker: str | None = None

    OPENERS = ("「", "『", "（", "(", "“", '"')
    CLOSERS = ("」", "』", "）", ")", "”", '"')

    def _is_pure_tag_or_comment(s: str) -> bool:
        s = s.strip()
        return not s or s.startswith(";") or s.startswith("[") or s.startswith("{") \
            or s.startswith("*") or s.startswith("}")

    # Helpers for narration grouping
    def _ends_with_comma(s: str) -> bool:
        s = s.rstrip()
        return bool(s) and s.endswith(("、", "，", ","))

    def _ends_with_terminal(s: str) -> bool:
        s = s.rstrip()
        return bool(s) and s.endswith(("。", "！", "？", "!", "?", "…"))

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip("\n\r")
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        # Capture speaker name tag only when the entire line is exactly the tag
        m_name = RE_NAME_TAG.fullmatch(stripped)
        if m_name:
            current_speaker = m_name.group(1).strip()
            i += 1
            continue

        # Also accept fullwidth-bracket name lines that some scripts use
        # Speaker only if fullwidth brackets occur at the very start of the line
        m_fw = RE_FULLWIDTH_NAME.match(line) if line.startswith("【") else None
        if m_fw:
            # e.g., '【車掌】[A_車掌_001]' -> speaker = '車掌'
            current_speaker = m_fw.group('name').strip()
            i += 1
            continue

        # Skip manifest/meta rows
        if stripped.lower().startswith("__data_hash__"):
            i += 1
            continue

        # Skip code lines (e.g., System.inform(...))
        if re.match(r'^[A-Za-z_][A-Za-z0-9_\.]*\s*\(', stripped):
            i += 1
            continue

        # If line is a pure tag or comment, skip (but keep current speaker)
        if _is_pure_tag_or_comment(stripped):
            i += 1
            continue

        # Detect opening quote without a matching closing on same line -> accumulate block
        opener_pos = -1
        opener_char = ''
        for op in OPENERS:
            p = stripped.find(op)
            if p >= 0 and (opener_pos == -1 or p < opener_pos):
                opener_pos = p
                opener_char = op

        has_closer_after = False
        if opener_pos >= 0:
            for cl in CLOSERS:
                if stripped.find(cl, opener_pos + 1) >= 0:
                    has_closer_after = True
                    break

        if opener_pos >= 0 and not has_closer_after:
            # Start accumulation across following lines, skipping pure tags/comments
            buffer_parts: List[str] = [stripped]
            j = i + 1
            found_closer = False
            while j < len(lines):
                nxt = lines[j].rstrip("\n\r")
                nstr = nxt.strip()
                if not nstr:
                    j += 1
                    continue
                if RE_NAME_TAG.fullmatch(nstr):
                    # New speaker tag encountered before closing; stop here to avoid cross-speaker merge
                    break
                if _is_pure_tag_or_comment(nstr):
                    # Conservative: only record comments and explicit pauses as placeholders.
                    # Other bracketed engine tags should stop accumulation to avoid
                    # creating long runs of generic placeholders.
                    if nstr.startswith(";"):
                        buffer_parts.append("[COMMENT]")
                        j += 1
                        continue
                    if nstr.startswith("["):
                        # Only treat explicit wait/pause tags as pauses
                        if re.search(r"\bwait\b|\bpause\b", nstr, re.IGNORECASE):
                            buffer_parts.append("[PAUSE]")
                            j += 1
                            continue
                        # Other bracket commands: stop accumulation here
                        break
                    # Unknown pure tag/comment: skip conservatively
                    j += 1
                    continue
                buffer_parts.append(nstr)
                # Did we hit any closer on this content line?
                if any(cl in nstr for cl in CLOSERS):
                    found_closer = True
                    break
                j += 1

            combined = " ".join(p.strip() for p in buffer_parts if p.strip())
            if current_speaker:
                rows.append({"name": sanitize_excel_string(f"{current_speaker}: {combined}")})
                current_speaker = None
            else:
                rows.append({"name": sanitize_excel_string(combined)})
            # Advance to the line after j if we consumed it; otherwise just move one
            i = (j + 1) if found_closer else (i + 1)
            continue

        # Single-line dialogue or narration
        m_dialog = RE_DIALOG.fullmatch(stripped)
        if m_dialog:
            full_dialog = f"{m_dialog.group(1)}{m_dialog.group(2)}{m_dialog.group(3)}"
            if current_speaker:
                rows.append({"name": sanitize_excel_string(f"{current_speaker}: {full_dialog.strip()}")})
                current_speaker = None
            else:
                rows.append({"name": sanitize_excel_string(full_dialog.strip())})
            i += 1
            continue

        # Fallback: accumulate consecutive content lines into a single logical textbox.
        # New rules:
        # - A dialogue terminates the block if next line begins with a closing quote/bracket
        #   like 」, 』, ”, ", ) or fullwidth ） (we treat such lines as separate dialogue lines).
        # - Empty lines create a hard break and are skipped (no empty tokens).
        # - Only lines starting with 【...】 at column 0 are treated as speaker lines.
        # - A line that is just a bracketed engine command stops accumulation.
        block_lines: List[str] = [stripped]
        k = i + 1
        while k < len(lines):
            nxt = lines[k].rstrip("\n\r")
            nstr = nxt.strip()
            # Blank line => break (skip it, do not include token)
            if not nstr:
                break
            # Stop accumulation when a new speaker tag appears
            if RE_NAME_TAG.fullmatch(nstr) or (nxt.startswith("【") and RE_FULLWIDTH_NAME.match(nxt)):
                break
            # Treat bracket-only tag lines (engine commands) as placeholders
            # rather than hard-stopping the accumulation. This keeps surrounding
            # content joined while still indicating to translators where tags
            # or pauses were present.
            if nstr.startswith('['):
                # Conservative approach: only treat explicit pauses as placeholders.
                if re.search(r"\bwait\b|\bpause\b", nstr, re.IGNORECASE):
                    block_lines.append('[PAUSE]')
                    k += 1
                    continue
                # For other bracketed commands, stop accumulation to avoid huge blocks.
                break
            # Code/function call lines should stop accumulation
            if re.match(r'^[A-Za-z_][A-Za-z0-9_\.]*\s*\(', nstr):
                break
            # Pure comments still become tokens but do not break blocks
            if _is_pure_tag_or_comment(nstr):
                if nstr.startswith(';'):
                    block_lines.append('[COMMENT]')
                    k += 1
                    continue
                # For other pure tags, be conservative and stop accumulation
                break
            # If this next line starts with a closing dialogue mark, end the block here
            # Terminate the block if the next line begins with a closing quote/bracket.
            # Note: exclude ASCII ')' because it can be part of code; keep fullwidth '）'.
            if nstr and nstr[0] in ("】", "」", "』", "”", '"', "）"):
                break
            # Otherwise, include this content line and continue
            block_lines.append(nstr)
            k += 1

        combined_text = "\n".join(p for p in block_lines if p)
        if current_speaker:
            rows.append({"name": sanitize_excel_string(f"{current_speaker}: {combined_text}")})
            current_speaker = None
        else:
            rows.append({"name": sanitize_excel_string(combined_text)})
        i = k

    if not rows:
        return {}
    return {"main": rows}




def sanitize_for_kirikiri(s: str) -> str:
    # Remove all illegal/control characters except tab, newline, carriage return
    return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", s)


def automatic_engine_safe(line: str) -> str:
    """Transform a line to avoid engine rendering/syntax issues.

    - If a line starts with '*', the engine drops it; add a leading space so it renders.
      We don't change lines where '*' is not the first visible character.
    - Replace ASCII tilde '~' with fullwidth '〜' to avoid upper-bound rendering artifacts.
    - As a safety, sanitize control characters via sanitize_for_kirikiri.
    """
    if not isinstance(line, str):
        return line
    s = line
    # preserve leading whitespace, check the first non-space char
    leading = s[: len(s) - len(s.lstrip())]
    rest = s[len(leading):]
    if rest.startswith("*"):
        # Insert a single space before '*' so the line is preserved by the engine
        rest = " " + rest
    # Replace standalone tildes with fullwidth wave
    rest = rest.replace('~', '〜')
    return sanitize_for_kirikiri(leading + rest)

def inject(data: Any, trans_maps: Dict[str, Dict[str, str]], file_path: Path, **kwargs) -> Any:
    """Injects translations back into a .ks script.

    For lines extracted as 'Speaker: Dialogue', split and restore speaker name to [name text="..."] and dialogue to 「...」.
    Narration lines (no speaker) are injected as-is.
    Also, if the translation for a dialogue line is in 'Speaker: Dialogue' format, update the [name text] tag with the translated speaker name.
    """
    logger = kwargs.get('logger')
    if logger and hasattr(logger, 'debug'):
        try:
            logger.debug(f"[kirikiri2] inject start: {file_path.name}")
        except Exception:
            pass
    if not isinstance(data, str):
        if logger and hasattr(logger, 'debug'):
            try:
                logger.debug(f"[kirikiri2] inject early-exit (non-str): {file_path.name}")
            except Exception:
                pass
        return data

    main_map = trans_maps.get("main", {})
    if not main_map:
        if logger and hasattr(logger, 'debug'):
            try:
                logger.debug(f"[kirikiri2] inject early-exit (no map): {file_path.name}")
            except Exception:
                pass
        return data


    new_lines: List[str] = []
    current_speaker: str | None = None
    last_name_index: int | None = None  # index of last appended [name] line
    speaker_rename: Dict[str, str] = {}  # cache of discovered speaker translations
    lines = data.splitlines()

    # Helper: normalize quotes and whitespace for robust lookup
    def _norm_quotes(s: str) -> str:
        if not isinstance(s, str):
            return s
        # normalize smart quotes to standard double quotes, fullwidth parens to ASCII parens
        s = s.replace('“', '"').replace('”', '"')
        s = s.replace('（', '(').replace('）', ')')
        s = s.replace('「', '"').replace('」', '"')
        s = s.replace('『', '"').replace('』', '"')
        return s.strip()

    def _is_plausible_speaker(s: str) -> bool:
        """Return True if the candidate speaker name looks like a real name.

        Reject strings that are only punctuation (e.g., '！！') to avoid
        accidental speaker renames when translators place punctuation before ':'
        in their translation. Accept names containing letters, digits, or CJK
        characters.
        """
        if not isinstance(s, str):
            return False
        s = s.strip()
        # Accept ASCII word chars or common CJK ranges
        return bool(re.search(r"[A-Za-z0-9_\u4E00-\u9FFF\u3040-\u30FF\u3000-\u303F]", s))

    def _try_lookup(keys: List[str]) -> str | None:
        # Try exact, then normalized variants
        for k in keys:
            if k in main_map:
                return main_map[k]
        for k in keys:
            nk = _norm_quotes(k)
            if nk in main_map:
                return main_map[nk]
        # Fallback: match any key that ends with ': <text>' to tolerate different speaker labels
        for k in keys:
            suffix = f": {k}"
            for mk in main_map.keys():
                if mk.endswith(suffix):
                    return main_map[mk]
            # Also try normalized suffix
            nsuffix = f": {_norm_quotes(k)}"
            for mk in main_map.keys():
                if mk.endswith(nsuffix):
                    return main_map[mk]
                # Normalize both sides
                nmk = _norm_quotes(mk)
                if nmk.endswith(nsuffix):
                    return main_map[mk]
        return None
    # Helper: strip duplicate outer quotes/brackets from translated inner text
    QUOTE_OPENERS = ['"', '“', '「', '『', '（', '(']
    QUOTE_CLOSERS = ['"', '”', '」', '』', '）', ')']
    PAIRS = {
        '"': '"', '“': '”', '「': '」', '『': '』', '（': '）', '(': ')'
    }
    def _strip_duplicate_outer(translated_text: str, outer_open: str, outer_close: str) -> str:
        # Preserve any quotes or punctuation the translator included.
        # Historically we attempted to strip duplicate outer quotes/brackets to
        # avoid double-quoting, but the user asked that translator-provided
        # quotes be treated as literal text and not modified. Return text
        # unchanged except for stripping surrounding whitespace.
        if not translated_text:
            return translated_text
        return translated_text.strip()
    # Helpers for block reconstruction
    OPENERS = ['"', '“', '「', '『', '（', '(']
    CLOSERS = ['"', '”', '」', '』', '）', ')']

    def _is_pure_tag_or_comment(s: str) -> bool:
        s = s.strip()
        return not s or s.startswith(';') or s.startswith('[')

    def _sanitize_translated_dialogue(s: str) -> str:
        # Only trim leading/trailing whitespace and sanitize control characters.
        # We intentionally do not remove bracketed content here because we now
        # rely on explicit placeholders and whole-line mapping.
        if not isinstance(s, str):
            return s
        return sanitize_for_kirikiri(s.strip())

    def _split_approx(text: str, weights: List[int]) -> List[str]:
        if not weights:
            return [text]
        total_w = max(sum(weights), 1)
        n = len(weights)
        # Initial cut sizes
        sizes = [max(0, (len(text) * w) // total_w) for w in weights]
        # Adjust remainder to last segment
        used = sum(sizes)
        if used < len(text):
            sizes[-1] += len(text) - used
        # Now slice roughly at whitespace boundaries when possible
        segs: List[str] = []
        idx = 0
        for k, sz in enumerate(sizes):
            if k == n - 1:
                segs.append(text[idx:])
            else:
                cut = idx + sz
                # Move cut to nearest whitespace to the right (within +10), else left (within -10)
                r = re.search(r"\s", text[cut:cut+10])
                if r:
                    cut = cut + r.start()
                else:
                    wl = list(re.finditer(r"\s", text[max(0, cut-10):cut]))
                    if wl:
                        cut = max(0, cut-10) + wl[-1].start()
                segs.append(text[idx:cut].rstrip())
                idx = cut
        # Final trim
        return [s.strip() for s in segs]

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw
        stripped = line.strip()

        # Preserve and advance past empty/whitespace-only lines
        if not stripped:
            new_lines.append(automatic_engine_safe(line))
            i += 1
            continue

        # Skip comments as-is
        if stripped.startswith(";"):
            new_lines.append(automatic_engine_safe(line))
            i += 1
            continue

        # Safeguard: do not translate lines that are pure code/function calls like "System.exit();"
        # These should have been excluded during extraction but protect injection as a hard rule.
        if re.match(r'^[A-Za-z_][A-Za-z0-9_\.]*\s*\(.*\)\s*;?$', stripped):
            new_lines.append(automatic_engine_safe(line))
            # consume any pending speaker since code lines are not dialogue
            current_speaker = None
            last_name_index = None
            i += 1
            continue

        # Speaker name tag
        m_name = RE_NAME_TAG.fullmatch(stripped)
        if m_name:
            speaker = m_name.group(1).strip()
            translated_speaker = None
            # Prefer an exact speaker-only mapping (main_map[speaker])
            direct = main_map.get(speaker)
            if direct:
                translated_speaker = direct.strip()
            else:
                # Find keys that start with "Speaker:" (e.g., 'Erica: ...')
                matches = [k for k in main_map.keys() if k.strip().startswith(f"{speaker}:")]
                if len(matches) == 1:
                    mv = main_map[matches[0]]
                    if ':' in mv:
                        translated_speaker = mv.split(':', 1)[0].strip()

            # Replace the [name text=...] tag with the translated speaker when we have one.
            # We do not attempt to use commented hint lines; the speaker line must be an
            # exact [name text="..."] tag to be considered (extract() enforces this).
            # If we have a previously discovered rename for this speaker, use it
            if not translated_speaker and speaker in speaker_rename:
                translated_speaker = speaker_rename[speaker]

            if translated_speaker:
                if not (("？" in speaker or '?' in speaker)):
                    translated_speaker = sanitize_for_kirikiri(translated_speaker)
                    line = re.sub(r'(\[name\s+text\s*=\s*")([^\"]+)("\])', f'\\1{translated_speaker}\\3', line)

            # Keep the original speaker for lookup; do not look at commented hints.
            current_speaker = speaker
            last_name_index = len(new_lines)
            new_lines.append(automatic_engine_safe(line))
            i += 1
            continue

        # Try to detect multi-line quoted dialogue starting here
        # Find earliest opener
        earliest_open = None
        for op in OPENERS:
            pos = stripped.find(op)
            if pos != -1 and (earliest_open is None or pos < earliest_open[1]):
                earliest_open = (op, pos)

        # Determine if there's a closer after the opener on the same line
        started_block = False
        if earliest_open is not None:
            op_char, op_pos = earliest_open
            has_closer_same = any(stripped.find(cl, op_pos + 1) != -1 for cl in CLOSERS)
            if not has_closer_same:
                # Start block accumulation across following lines, preserving tags/comments
                text_lines_meta = []  # (index, leading_ws, text_part, is_first, is_last)
                # Extract text after opener
                leading_ws0 = line[: len(line) - len(line.lstrip())]
                text_after_op = stripped[op_pos + 1:]
                text_lines_meta.append((i, leading_ws0, text_after_op, True, False))

                j = i + 1
                closer_char = None
                while j < len(lines):
                    l2 = lines[j]
                    s2 = l2.strip()
                    if not s2:
                        j += 1
                        continue
                    if RE_NAME_TAG.fullmatch(s2):
                        break  # don't cross into next speaker
                    if _is_pure_tag_or_comment(s2):
                        j += 1
                        continue
                    # Content line; check for closer
                    close_hit = None
                    close_pos = -1
                    for cl in CLOSERS:
                        p = s2.find(cl)
                        if p != -1 and (close_pos == -1 or p < close_pos):
                            close_pos = p
                            close_hit = cl
                    if close_hit is not None:
                        closer_char = close_hit
                        leading_ws2 = l2[: len(l2) - len(l2.lstrip())]
                        text_lines_meta.append((j, leading_ws2, s2[:close_pos], False, True))
                        break
                    else:
                        leading_ws2 = l2[: len(l2) - len(l2.lstrip())]
                        text_lines_meta.append((j, leading_ws2, s2, False, False))
                    j += 1

                # Build original combined key (without placeholders)
                inner_text = " ".join(t for _, _, t, _, _ in text_lines_meta).strip()
                full_original = f"{op_char}{inner_text}{closer_char or ''}"
                # Also build a combined key that includes the placeholder tokens for
                # interleaved pure-tag/comment lines (extracted rows include tokens
                # like [PAUSE], [COMMENT], [PLACEHOLDER4CODE]). This allows the
                # manifest-based map (which was generated from the extractor) to
                # be found even though this injection path initially omits tag
                # lines when building the simple `full_original` key.
                meta_by_idx = {idx: txt for idx, _, txt, _, _ in text_lines_meta}
                parts_with_ph: List[str] = []
                for kscan in range(i, (j + 1) if j < len(lines) else (i + 1)):
                    if kscan in meta_by_idx:
                        t = meta_by_idx[kscan].strip()
                        if t:
                            parts_with_ph.append(t)
                        continue
                    # If this line was a pure tag/comment, use the same placeholder
                    # tokens the extractor used so the combined string matches the
                    # manifest key exactly.
                    if kscan < len(lines):
                        lscan = lines[kscan]
                        sscan = lscan.strip()
                        if _is_pure_tag_or_comment(sscan):
                            if sscan.startswith(";"):
                                ph = "[COMMENT]"
                            elif sscan.startswith("[") and re.search(r"\bwait\b", sscan, re.IGNORECASE):
                                ph = "[PAUSE]"
                            else:
                                ph = "[PLACEHOLDER4CODE]"
                            parts_with_ph.append(ph)
                combined_with_placeholders = f"{op_char}{' '.join(parts_with_ph).strip()}{closer_char or ''}"
                keys = [full_original, combined_with_placeholders]
                if current_speaker:
                    keys.insert(0, f"{current_speaker}: {full_original}")
                translated_whole = _try_lookup(keys)

                if translated_whole is not None:
                    # Optional speaker rename prefix
                    new_speaker = None
                    maybe = translated_whole
                    # Heuristic: treat prefix before first ':' as a speaker if it's short
                    if ':' in maybe:
                        cand_sp, rest = maybe.split(':', 1)
                        if len(cand_sp.strip()) <= 40 and any(q in rest for q in ['"', '“', '「', '『', '（', '(']):
                            new_speaker = cand_sp.strip()
                            maybe = rest
                    if new_speaker:
                        # Reject implausible speaker tokens (punctuation-only)
                        if not _is_plausible_speaker(new_speaker):
                            new_speaker = None
                        else:
                            new_speaker = sanitize_for_kirikiri(new_speaker)
                        if new_speaker and last_name_index is not None and 0 <= last_name_index < len(new_lines):
                            prev_name_line = new_lines[last_name_index]
                            prev_name_line = re.sub(r'(\[name\s+text\s*=\s*")([^\"]+)("\])', f'\\1{new_speaker}\\3', prev_name_line)
                            new_lines[last_name_index] = prev_name_line
                        if current_speaker:
                            speaker_rename[current_speaker] = new_speaker

                    translated_inner = _sanitize_translated_dialogue(maybe)

                    # If placeholders like [PAUSE], [PLACEHOLDER4CODE], [COMMENT] exist in
                    # translated_inner, use them to re-insert the original tag lines at those
                    # positions. Otherwise fall back to reinserting original tag/comment lines
                    # at their original places between the content lines.
                    ph_map = {}
                    # Build a map of placeholders -> list of original lines that produced them
                    # We recreate the original scan between i..j to find tag/comment lines
                    orig_tag_lines = []  # list of (pos_index, orig_line)
                    for kscan in range(i+1, j+1):
                        if kscan >= len(lines):
                            break
                        lscan = lines[kscan]
                        sscan = lscan.strip()
                        if _is_pure_tag_or_comment(sscan):
                            if sscan.startswith(";"):
                                token = "[COMMENT]"
                            elif sscan.startswith("[") and re.search(r"\bwait\b", sscan, re.IGNORECASE):
                                token = "[PAUSE]"
                            else:
                                token = "[PLACEHOLDER4CODE]"
                            orig_tag_lines.append((kscan - i, lscan, token))
                            ph_map.setdefault(token, []).append(lscan)

                    # Try to locate placeholders in the sanitized translated_inner text.
                    # Accept mangled variants (with or without surrounding brackets),
                    # case-insensitive. Build an ordered sequence of text and token markers.
                    token_names = ("PAUSE", "PLACEHOLDER4CODE", "COMMENT")
                    token_pattern = re.compile(r"(?:\[(?P<t1>PAUSE|PLACEHOLDER4CODE|COMMENT)\]|\b(?P<t2>PAUSE|PLACEHOLDER4CODE|COMMENT)\b)", re.IGNORECASE)
                    parts_seq: List[str] = []
                    last = 0
                    for m in token_pattern.finditer(translated_inner):
                        if m.start() > last:
                            parts_seq.append(translated_inner[last:m.start()])
                        token = (m.group('t1') or m.group('t2') or '').upper()
                        parts_seq.append(f"[{token}]")
                        last = m.end()
                    if last < len(translated_inner):
                        parts_seq.append(translated_inner[last:])

                    # Rebuild sequence mixing content parts and original tag lines
                    rebuilt_parts: List[str] = []
                    for part in parts_seq:
                        txt = part.strip()
                        if not txt:
                            continue
                        if txt.startswith('[') and txt.endswith(']') and txt[1:-1].upper() in token_names:
                            token = txt.upper()
                            bucket = ph_map.get(token, [])
                            if bucket:
                                rebuilt_parts.append(bucket.pop(0).rstrip('\n'))
                            else:
                                # token present but no original: keep the token as-is so we can fallback
                                rebuilt_parts.append(token)
                        else:
                            rebuilt_parts.append(part.strip())

                    # If no placeholders were present, fall back to proportional split
                    if len(rebuilt_parts) == 1 and orig_tag_lines:
                        # Proportional split: keep original interleaving of content and tags
                        weights = [max(1, len(t)) for _, _, t, _, _ in text_lines_meta]
                        parts = _split_approx(rebuilt_parts[0], weights)
                        k_meta = 0
                        for meta_idx, leading_ws2, _orig_text, is_first, is_last in text_lines_meta:
                            seg = parts[k_meta] if k_meta < len(parts) else ''
                            content = seg
                            if is_first:
                                content = f"{op_char}{content}"
                            if is_last and closer_char:
                                content = f"{content}{closer_char}"
                            new_lines.append(automatic_engine_safe(f"{leading_ws2}{content}"))
                            # Insert any original tag lines that followed this meta (simple heuristic)
                            for (relpos, orig_line, token) in [t for t in orig_tag_lines if t[0] == meta_idx+1]:
                                new_lines.append(automatic_engine_safe(orig_line))
                            k_meta += 1
                    else:
                        # Rebuilt_parts contains a mix of text fragments and original tag lines/tokens
                        # We'll map them back to the sequence of original lines between i..j
                        # First, create a queue of content-bearing meta entries
                        content_meta = [m for m in text_lines_meta]
                        cm_idx = 0
                        for part in rebuilt_parts:
                            if part.startswith("[") and part.endswith("]") and part in ("[PAUSE]","[PLACEHOLDER4CODE]","[COMMENT]"):
                                # token leftover -> if we have original lines for it, emit one; else emit token
                                bucket = ph_map.get(part, [])
                                if bucket:
                                    new_lines.append(automatic_engine_safe(bucket.pop(0)))
                                else:
                                    new_lines.append(automatic_engine_safe(part))
                            elif part.startswith("[") and part.endswith("]"):
                                # unknown bracket token, emit as-is
                                new_lines.append(automatic_engine_safe(part))
                            else:
                                if cm_idx < len(content_meta):
                                    idx_meta, leading_ws2, _orig_text, is_first, is_last = content_meta[cm_idx]
                                    content = part
                                    if is_first:
                                        content = f"{op_char}{content}"
                                    if is_last and closer_char:
                                        content = f"{content}{closer_char}"
                                    new_lines.append(automatic_engine_safe(f"{leading_ws2}{content}"))
                                    cm_idx += 1
                                else:
                                    # Extra text fragments at the end; append as a new line
                                    new_lines.append(automatic_engine_safe(part))

                    # Consume speaker after block
                    current_speaker = None
                    last_name_index = None
                    i = (j + 1) if j < len(lines) else (i + 1)
                    started_block = True
                    continue
                # No translation for combined block -> emit original lines as-is
                for k in range(i, (j + 1) if j < len(lines) else (i + 1)):
                    new_lines.append(automatic_engine_safe(lines[k]))
                current_speaker = None
                last_name_index = None
                i = (j + 1) if j < len(lines) else (i + 1)
                started_block = True
                continue

        # If not a multi-line block start, handle single-line dialogue
        m_dialog_full = RE_DIALOG.search(line)
        if m_dialog_full:
            open_b, inner, close_b = m_dialog_full.group(1), m_dialog_full.group(2), m_dialog_full.group(3)
            full_dialog = f"{open_b}{inner}{close_b}"

            translated_whole = None
            if current_speaker:
                key1 = f"{current_speaker}: {stripped}"
                translated_whole = main_map.get(key1)
                if translated_whole is None and stripped != full_dialog:
                    key2 = f"{current_speaker}: {full_dialog}"
                    translated_whole = main_map.get(key2)
            if translated_whole is None:
                if stripped in main_map:
                    translated_whole = main_map[stripped]
                else:
                    nstr = _norm_quotes(stripped)
                    for mk, mv in main_map.items():
                        mks = mk.strip()
                        if mks == stripped or mks == nstr:
                            translated_whole = mv
                            break
                    if translated_whole is None:
                        for mk, mv in main_map.items():
                            mks = mk.strip()
                            if mks.endswith(stripped) or mks.endswith(full_dialog) or mks.endswith(inner):
                                translated_whole = mv
                                break

            if translated_whole is not None:
                maybe = translated_whole
                new_speaker = None
                if ':' in maybe:
                    cand_sp, rest = maybe.split(':', 1)
                    if len(cand_sp.strip()) <= 40 and any(q in rest for q in ['"', '“', '「', '『', '（', '(']):
                        new_speaker = cand_sp.strip()
                        maybe = rest
                if new_speaker:
                    if not _is_plausible_speaker(new_speaker):
                        new_speaker = None
                    else:
                        new_speaker = sanitize_for_kirikiri(new_speaker)
                    if new_speaker and last_name_index is not None and 0 <= last_name_index < len(new_lines):
                        prev_name_line = new_lines[last_name_index]
                        prev_name_line = re.sub(r'(\[name\s+text\s*=\s*")([^\"]+)("\])', f'\\1{new_speaker}\\3', prev_name_line)
                        new_lines[last_name_index] = prev_name_line
                    if current_speaker:
                        speaker_rename[current_speaker] = new_speaker
                translated_text = _sanitize_translated_dialogue(maybe)
                leading_ws = line[: len(line) - len(line.lstrip())]
                line = f"{leading_ws}{translated_text}"
                current_speaker = None
                last_name_index = None
                new_lines.append(automatic_engine_safe(line))
                i += 1
                continue

            if current_speaker:
                current_speaker = None
            new_lines.append(automatic_engine_safe(line))
            i += 1
            continue

        # Bracketed command (non-[name]) — leave untouched for safety
        if stripped.startswith("["):
            new_lines.append(automatic_engine_safe(line))
            i += 1
            continue

        # Plain narration/prose line
        if stripped:
            translated = None
            used_speaker_prefixed = False
            if current_speaker:
                speaker_key = f"{current_speaker}: {stripped}"
                translated = main_map.get(speaker_key)
                if translated is not None and ':' in translated:
                    # Split into translated speaker and text, update the previous [name] line
                    new_speaker, translated_text_only = translated.split(':', 1)
                    new_speaker = new_speaker.strip()
                    if not _is_plausible_speaker(new_speaker):
                        new_speaker = None
                    else:
                        new_speaker = sanitize_for_kirikiri(new_speaker)
                    translated = translated_text_only
                    if last_name_index is not None and 0 <= last_name_index < len(new_lines):
                        prev_name_line = new_lines[last_name_index]
                        prev_name_line = re.sub(r'(\[name\s+text\s*=\s*")([^\"]+)("\])', f'\\1{new_speaker}\\3', prev_name_line)
                        new_lines[last_name_index] = prev_name_line
                    used_speaker_prefixed = True
                    # Remember this rename for subsequent [name] tags
                    speaker_rename[current_speaker] = new_speaker
            if translated is None:
                translated = main_map.get(stripped)
            if translated is not None:
                leading_ws = line[: len(line) - len(line.lstrip())]
                # Sanitize narration translation too (prevent tag injection)
                safe_trans = _sanitize_translated_dialogue(translated)
                line = f"{leading_ws}{safe_trans}"
            # Consume the speaker after first content line
            if current_speaker:
                current_speaker = None
                last_name_index = None
            new_lines.append(automatic_engine_safe(line))
            i += 1
            continue

    out = "\n".join(new_lines)
    if logger and hasattr(logger, 'debug'):
        try:
            logger.debug(f"[kirikiri2] inject end: {file_path.name}")
        except Exception:
            pass
    return out


def should_process_file(path: Path) -> bool:
    """Limit processing scope: only scenario .ks (accept any scenario subpath)."""
    p = str(path).replace("\\", "/").lower()
    return p.endswith('.ks') and '/scenario/' in p

def might_contain_translatables(content: str, trans_maps: Dict[str, Dict[str, str]], file_path: Path) -> bool:
    """Fast precheck to skip injection when no manifest keys could ever match the file.
    For .ks: look for at least one key suffix present.
    For TJS: always False (we don't inject TJS via map, we patch via post hook only).
    """
    p = str(file_path).replace("\\", "/").lower()
    # No TJS handling here (TJS is patched separately)
    mm = trans_maps.get('main') or {}
    if not mm:
        return False
    # Heuristic: if none of the short keys (<= 40 chars) occur in content, skip.
    # Use a small sample for speed.
    sample = 0
    for k in mm.keys():
        ks = k.strip()
        # Consider either the full key or the part after a ": " speaker prefix
        if ': ' in ks:
            ks = ks.split(': ', 1)[1]
        if len(ks) <= 40:
            sample += 1
            # Direct match
            if ks and ks in content:
                return True
            # Also try a cleaned version where placeholder tokens are removed
            # (extractor inserts tokens like [PAUSE], [COMMENT], [PLACEHOLDER4CODE]
            # that do not exist in the original file content). Remove these and
            # check for the remaining fragment in the file content.
            ks_clean = re.sub(r"\[(?:PAUSE|COMMENT|PLACEHOLDER4CODE)\]", "", ks, flags=re.IGNORECASE).strip()
            if ks_clean and ks_clean in content:
                return True
            # Try removing all square-bracket tokens entirely (in case placeholders
            # were adjacent to text with no spaces)
            ks_no_br = ks.replace('[', '').replace(']', '').strip()
            if ks_no_br and ks_no_br in content:
                return True
        if sample >= 100:
            break
    return False


# ---- Optional TJS word-wrapping patch (project-level) ----

def _read_text_preserve_encoding(path: Path) -> tuple[str, str, bytes]:
    """Read text preserving encoding. Returns (text, codec, bom_bytes)."""
    data = path.read_bytes()
    bom = b""
    # BOM sniff
    if data.startswith(codecs.BOM_UTF16_LE):
        return data[len(codecs.BOM_UTF16_LE):].decode('utf-16-le', errors='strict'), 'utf-16-le', codecs.BOM_UTF16_LE
    if data.startswith(codecs.BOM_UTF16_BE):
        return data[len(codecs.BOM_UTF16_BE):].decode('utf-16-be', errors='strict'), 'utf-16-be', codecs.BOM_UTF16_BE
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode('utf-8', errors='strict'), 'utf-8', codecs.BOM_UTF8
    # Try common encodings
    for enc in ("cp932", "utf-8", "utf-16-le", "utf-16-be"):
        try:
            return data.decode(enc, errors='strict'), enc, b""
        except UnicodeDecodeError:
            continue
    # Fallback (lossy)
    return data.decode("utf-8", errors='replace'), 'utf-8', b""

def _write_text_with_encoding(path: Path, text: str, enc: str, bom: bytes) -> None:
    payload = text.encode(enc, errors='strict')
    if bom:
        payload = bom + payload
    path.write_bytes(payload)

def _already_has_wrap_vars(tjs: str) -> bool:
    return ("var wrapNum" in tjs) and ("var wrapPos" in tjs) and ("var oldLine" in tjs)

def _already_has_wrap_block(tjs: str) -> bool:
    # Heuristics to avoid double-patching
    return ("Wordwrapping code" in tjs) or ("oldLine != conductor.curLineStr" in tjs)

_WRAP_VARS_SNIPPET = """
	var wrapNum = 0; // wordwrapping word counter
	var wrapPos = 0; // wordwrapping length
	var oldLine = void; // wordwrapping comparison line
	var splitLine = void; // wordwrapping split text variable
	var breakWrap = 0; // wrapping flag during check
	var newPage = 0; // wrapping flag for new page
"""

_WRAP_BLOCK_SNIPPET = r"""
		/* Wordwrapping code (auto line breaks)
		   Simplified port, measures tokens and inserts line breaks when needed. */
		if(oldLine != conductor.curLineStr) {
			var tempStr = "";
			oldLine = conductor.curLineStr;
			wrapNum = 0;
			breakWrap = 0;
			// Remove bracketed tags [ ... ] for width measurement
			var i=0; while(i<oldLine.length) {
				var ch = oldLine[i];
				if(ch == '[') {
					var depth = 1; i++;
					while(i<oldLine.length && depth>0) {
						if(oldLine[i] == '[') depth++;
						else if(oldLine[i] == ']') depth--;
						i++;
					}
					continue;
				}
				if(ch != '\\') tempStr += ch; // ignore escape leader
				i++;
			}
                    if(tempStr.length < 1) {
                        breakWrap = 1;
                    } else {
                        // Tokenize on consecutive non-whitespace sequences so contractions
                        // (e.g., I'm) and attached punctuation (e.g., word”) are kept
                        // as single tokens rather than being split apart.
                        // Avoid using String.match() because some TJS runtimes don't
                        // implement it; use a simple manual tokenizer instead.
                        splitLine = [];
                        var _tok = "";
                        for(var ti=0; ti<tempStr.length; ti++) {
                            var tch = tempStr[ti];
                            // Avoid using String.search (may be missing in TJS).
                            // Treat the common whitespace characters as separators.
                            if(tch !== ' ' && tch !== '\t' && tch !== '\n' && tch !== '\r') {
                                _tok += tch;
                            } else {
                                if(_tok.length > 0) { splitLine.push(_tok); _tok = ""; }
                            }
                        }
                        if(_tok.length > 0) { splitLine.push(_tok); }
                        // Post-process tokens: attach opening quotes to the following token
                        // and attach closing quotes/apostrophes to the previous token so
                        // punctuation doesn't become a standalone token that produces
                        // stray spaces when the engine renders.
                        var j = 0;
                        while (j < splitLine.length) {
                            var tt = splitLine[j];
                            if (tt.length === 1 && (tt === '“' || tt === '「' || tt === '『' || tt === '（' || tt === '(' || tt === '"')) {
                                if (j + 1 < splitLine.length) {
                                    splitLine[j+1] = tt + splitLine[j+1];
                                    splitLine.splice(j, 1);
                                    continue; // don't advance j, new element at this index
                                }
                            }
                            j++;
                        }
                        j = 1;
                        while (j < splitLine.length) {
                            var tt2 = splitLine[j];
                            if (tt2.length === 1 && (tt2 === '”' || tt2 === '』' || tt2 === '」' || tt2 === '）' || tt2 === ')' || tt2 === '"' || tt2 === '’' || tt2 === "'")) {
                                splitLine[j-1] = splitLine[j-1] + tt2;
                                splitLine.splice(j, 1);
                                continue; // remain at same j to inspect next element shifted into position
                            }
                            j++;
                        }
                    }
			wrapPos = current.vertical ? current.y + current.lineLayer.font.getTextWidth(" ") : current.x;
		}
		if(!breakWrap) {
			if(text == " ") {
				wrapNum++;
				wrapPos = current.vertical ? current.y + current.lineLayer.font.getTextWidth(" ") : current.x;
			}
			var word = splitLine[wrapNum];
			if(word !== void) {
				var word_sz = current.lineLayer.font.getTextWidth(" "+word) + current.pitch * (word.length);
				if(wrapPos + word_sz >= current.relinexpos) {
					if(current.marginL + word_sz <= current.relinexpos) {
						if(text == " ") text = "";
						if(historyLayer !== void) historyLayer.reline();
						if(currentWithBack) current.comp.processReturn();
						if(current.processReturn()) { return showPageBreakAndClear(); }
					}
					wrapPos = current.vertical ? current.y + current.lineLayer.font.getTextWidth(" ") : current.x;
				}
			}
		}
		// end: wordwrapping code
"""

def _patch_add_wrap_vars(tjs: str) -> str:
    m = re.search(r"(class\s+KAGWindow\s+extends\s+Window\s*\{\s*)", tjs)
    if not m or _already_has_wrap_vars(tjs):
        return tjs
    insert_at = m.end()
    return tjs[:insert_at] + _WRAP_VARS_SNIPPET + tjs[insert_at:]

def _patch_add_wrap_block_in_ch(tjs: str) -> str:
    if _already_has_wrap_block(tjs):
        return tjs
    ch_start = re.search(r"(ch\s*:\s*function\s*\(\s*elm\s*\)\s*\{)", tjs)
    if not ch_start:
        return tjs
    start_idx = ch_start.end()
    # Try to detect end of ch function region to limit our search (look for '} incontextof this')
    ch_end_m = re.search(r"\}\s*incontextof\s+this", tjs[start_idx:])
    end_idx = start_idx + ch_end_m.start() if ch_end_m else len(tjs)

    region = tjs[start_idx:end_idx]
    # Primary anchor: var text = elm.text;
    m_var_text = re.search(r"var\s+text\s*=\s*elm\.text\s*;", region)
    insert_at = None
    if m_var_text:
        base = start_idx + m_var_text.end()
        # Optional: if(currentWithBack) current.comp.processCh(text); (with or without braces)
        m_back = re.search(r"if\s*\(\s*currentWithBack\s*\)\s*(?:\{[^\}]*?\}|[^\n\r\{]*)?current\.comp\.processCh\(\s*text\s*\)\s*;", tjs[base:end_idx], re.DOTALL)
        if m_back:
            insert_at = base + m_back.end()
        else:
            insert_at = base
    else:
        # Secondary anchor: before full if(current.processCh(text)) { ... }
        if_stmt = re.search(r"if\s*\(\s*current\.processCh\(\s*text\s*\)\s*\)\s*\{", region)
        if if_stmt:
            insert_at = start_idx + if_stmt.start()
        else:
            # Tertiary: after current.processCh(text) token, moving past immediate ')'
            anchor = re.search(r"current\.processCh\(\s*text\s*\)", region)
            if anchor:
                pos = start_idx + anchor.end()
                # Skip whitespace
                while pos < len(tjs) and tjs[pos].isspace():
                    pos += 1
                if pos < len(tjs) and tjs[pos] == ')':
                    pos += 1
                insert_at = pos

    if insert_at is None:
        return tjs
    return tjs[:insert_at] + _WRAP_BLOCK_SNIPPET + tjs[insert_at:]

def post_inject_project(project_root: Path, **kwargs) -> None:
    """Module-level optional hook. Patch MainWindow.tjs with word-wrapping if enabled.
    Scans under the injected project root for a file named 'MainWindow.tjs'. If missing
    there, the function will look under the provided input_root (original game folder)
    for either '<input_root>/data/system/MainWindow.tjs' or '<input_root>/system/MainWindow.tjs'
    and copy it into the injected output before patching. This keeps behavior robust for
    both user-selected roots.
    """
    logger = kwargs.get('logger')
    input_root = kwargs.get('input_root') or kwargs.get('inputRoot')
    # Prepare fallback debug file
    debug_file = project_root / '.kirikiri_tjs_patch.log'
    def _dbg(msg: str) -> None:
        out = f"TJS patch: {msg}"
        try:
            if logger and hasattr(logger, 'debug'):
                logger.debug(out)
            else:
                with open(debug_file, 'a', encoding='utf-8') as f:
                    f.write(out + '\n')
        except Exception:
            pass

    if not ENABLE_TJS_WORDWRAP_PATCH:
        _dbg('TJS patch disabled by module flag')
        return

    candidates_rel = [Path('data') / 'system' / 'MainWindow.tjs', Path('system') / 'MainWindow.tjs']

    # 1) Look in output project
    found = None
    for rel in candidates_rel:
        p = project_root / rel
        _dbg(f'Checking output location: {p}')
        if p.exists():
            found = p
            _dbg(f'Found MainWindow.tjs in output at {p}')
            break

    # 2) If not found, look in input_root and copy into output
    if not found and input_root:
        for rel in candidates_rel:
            src = Path(input_root) / rel
            _dbg(f'Checking input location: {src}')
            if src.exists():
                dst = project_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copyfile(src, dst)
                    found = dst
                    _dbg(f'Copied MainWindow.tjs from {src} to {dst}')
                except Exception as e:
                    _dbg(f'Failed to copy MainWindow.tjs from {src} to {dst}: {e}')
                break

    if not found:
        _dbg(f'No MainWindow.tjs found in output or input (checked candidates).')
        return

    tjs_path = found
    try:
        _dbg(f'Opening {tjs_path}')
        text, enc, bom = _read_text_preserve_encoding(tjs_path)
        _dbg(f'Detected encoding {enc}, BOM present={bool(bom)}')
        orig = text
        has_vars = _already_has_wrap_vars(text)
        has_block = _already_has_wrap_block(text)
        _dbg(f'Existing wrap vars? {has_vars}, existing wrap block? {has_block}')
        patched = _patch_add_wrap_vars(text)
        if patched != text:
            _dbg('Injected wrap-vars snippet')
        else:
            _dbg('Did not inject wrap-vars (already present or anchor not found)')
        patched2 = _patch_add_wrap_block_in_ch(patched)
        if patched2 != patched:
            _dbg('Injected wrap-block into ch handler')
        else:
            _dbg('Did not inject wrap-block (already present or anchor not found)')
        patched = patched2
        if patched != orig:
            # Backup once
            bak = tjs_path.with_suffix(tjs_path.suffix + '.bak')
            if not bak.exists():
                _write_text_with_encoding(bak, orig, enc, bom)
                _dbg(f'Wrote backup {bak}')
            # Validate balance inside the ch : function(elm) block specifically
            def _is_balanced(s: str) -> bool:
                pairs = {')':'(', ']':'[', '}':'{'}
                stack: list[str] = []
                in_line_comment = False
                in_block_comment = False
                in_string = False
                string_quote = ''
                i = 0
                while i < len(s):
                    ch = s[i]
                    nxt = s[i+1] if i+1 < len(s) else ''
                    # Handle end of line comment
                    if in_line_comment:
                        if ch == '\n':
                            in_line_comment = False
                        i += 1
                        continue
                    # Handle end of block comment
                    if in_block_comment:
                        if ch == '*' and nxt == '/':
                            in_block_comment = False
                            i += 2
                        else:
                            i += 1
                        continue
                    # Start of comments
                    if not in_string and ch == '/' and nxt == '/':
                        in_line_comment = True
                        i += 2
                        continue
                    if not in_string and ch == '/' and nxt == '*':
                        in_block_comment = True
                        i += 2
                        continue
                    # Strings ("...") and ('...')
                    if not in_string and ch in ('"', "'"):
                        in_string = True
                        string_quote = ch
                        i += 1
                        continue
                    if in_string:
                        if ch == '\\':  # escape
                            i += 2
                            continue
                        if ch == string_quote:
                            in_string = False
                            string_quote = ''
                        i += 1
                        continue
                    # Count braces/parens when not in comments/strings
                    if ch in '([{':
                        stack.append(ch)
                    elif ch in ')]}':
                        if not stack or stack[-1] != pairs[ch]:
                            return False
                        stack.pop()
                    i += 1
                return not stack

            wrote = False
            ch_m = re.search(r"(ch\s*:\s*function\s*\(\s*elm\s*\)\s*\{)", patched)
            if ch_m:
                ch_start_idx = ch_m.end()
                ch_end_m = re.search(r"\}\s*incontextof\s+this", patched[ch_start_idx:])
                if ch_end_m:
                    ch_end_idx = ch_start_idx + ch_end_m.start()
                    block_ok = _is_balanced(patched[ch_start_idx:ch_end_idx])
                else:
                    block_ok = _is_balanced(patched[ch_start_idx:])
            else:
                block_ok = _is_balanced(patched)

            if not block_ok:
                _dbg('Patched ch-block appears unbalanced. Skipping write to avoid crashing engine.')
                # Write a sidecar preview of the ch-block for debugging
                try:
                    preview_path = tjs_path.with_suffix(tjs_path.suffix + '.ch_preview.txt')
                    ch_m2 = re.search(r"(ch\s*:\s*function\s*\(\s*elm\s*\)\s*\{)", patched)
                    if ch_m2:
                        cs = ch_m2.end()
                        ce_m = re.search(r"\}\s*incontextof\s+this", patched[cs:])
                        ce = cs + (ce_m.start() if ce_m else len(patched))
                        with open(preview_path, 'w', encoding='utf-8') as pf:
                            pf.write(patched[cs:ce])
                        _dbg(f'Wrote ch-block preview to {preview_path}')
                except Exception as e2:
                    _dbg(f'Failed to write ch-block preview: {e2}')
                if logger and hasattr(logger, 'warning'):
                    logger.warning(f'Would write broken MainWindow.tjs at {tjs_path}; skipped to avoid syntax error')
            else:
                _write_text_with_encoding(tjs_path, patched, enc, bom)
                wrote = True
                _dbg(f'Wrote patched file {tjs_path}')
                if logger and hasattr(logger, 'info'):
                    try:
                        logger.info(f'Patched word-wrapping into {tjs_path.relative_to(project_root)}')
                    except Exception:
                        logger.info(f'Patched word-wrapping into {tjs_path}')
        else:
            _dbg('No changes required after attempted patch')
    except Exception as e:
        _dbg(f'Exception while patching {tjs_path}: {e}')
        if logger and hasattr(logger, 'warning'):
            logger.warning(f'Failed to patch {tjs_path}: {e}')
