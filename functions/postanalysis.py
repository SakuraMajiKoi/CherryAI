from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from .mainhelper import Manifest
from .modehelper import ANCHOR_EQUIVS, get_equivs
from .validation import (
    detect_speaker_dialogue_format,
    validate_speaker_format_preserved,
    should_retry_for_speaker_format,
    SpeakerFormatInfo,
)


def _load_manifest_obj(man: Union[Manifest, Dict[str, Any], Path]) -> Manifest:
    if isinstance(man, Manifest):
        return man
    if isinstance(man, Path):
        data = man.read_text(encoding="utf-8")
        obj = __import__("json").loads(data)
        return Manifest.from_dict(obj)
    if isinstance(man, dict):
        return Manifest.from_dict(man)
    raise TypeError("manifest must be a Manifest, dict or Path")


def _load_text(txt: Union[str, Path]) -> str:
    if isinstance(txt, Path):
        return txt.read_text(encoding="utf-8")
    return str(txt)


def compare_manifest_and_final(manifest: Union[Manifest, Dict[str, Any], Path], final_text: Union[str, Path]) -> Dict[str, Any]:
    """Compare original lines stored in a manifest against the final post-TL output.

    Returns a dictionary with:
      - total_lines: int
      - identical_lines: int
      - differing_lines: int
      - diffs: list of {line: int, original: str, final: str}

    This function is designed to be invoked by a GUI button; it keeps the
    payload lightweight and returns structured data the GUI can render.
    """
    man = _load_manifest_obj(manifest)
    final = _load_text(final_text)

    # Primary source is manifest.lines array
    orig_lines: List[str] = []
    if man.lines:
        # Sort by idx to ensure correct order
        sorted_lines = sorted(man.lines, key=lambda x: x.idx)
        orig_lines = [line.orig for line in sorted_lines]

    # Ensure we have a list of strings
    orig_lines = [str(x) for x in orig_lines]
    final_lines = final.splitlines()

    total = max(len(orig_lines), len(final_lines))
    identical = 0
    diffs: List[Dict[str, Any]] = []

    # Use central ANCHOR_EQUIVS from modehelper

    # Get quote equivalents and colon equivalents from modehelper helpers
    QUOTE_EQS = set(get_equivs('"'))
    COLON_EQS = get_equivs(":")

    # Characters considered 'code' for the code-structure check
    CODE_CHARS = list("<{[]}>|=\\;#^*/")

    def _contains_speaker_quote(s: str) -> bool:
        """Return True if the string contains a colon-equivalent followed by a quote-equivalent."""
        if not s:
            return False
        # search for any colon variant
        col_variants = COLON_EQS or [":"]
        for col in col_variants:
            idx = s.find(col)
            while idx != -1:
                # find next non-space character after colon
                j = idx + len(col)
                while j < len(s) and s[j].isspace():
                    j += 1
                if j < len(s) and s[j] in QUOTE_EQS:
                    return True
                # look for next occurrence
                idx = s.find(col, idx + 1)
        return False

    def _code_sequence(s: str) -> List[str]:
        """Return the sequence of code characters in s in-order (no equiv mapping)."""
        seq: List[str] = []
        for ch in s:
            if ch in CODE_CHARS:
                seq.append(ch)
        return seq

    def _try_code_recover(o: str, f: str) -> Tuple[str, bool]:
        """Attempt to recover missing code characters from original into final.

        Strategy:
        - Determine code characters present in original but missing or out-of-order in final.
        - For each missing code char, try to locate the following or previous significant
          neighbour (non-space) from the original in the final. If found, insert the
          missing char before next neighbour or after previous neighbour.
        - Discount spaces when locating neighbours in final, but preserve a single space
          around insertion according to surrounding final text.
        """
        try:
            orig_seq = [ch for ch in o if ch in CODE_CHARS]
            final_seq = [ch for ch in f if ch in CODE_CHARS]
            if orig_seq == final_seq:
                return f, False
            # Build mapping of final significant chars to indices (allow multiple occurrences)
            final_nonspace = [ (i,ch) for i,ch in enumerate(f) if not f[i].isspace() ]
            # Helper to find index of a character occurrence in final_nonspace
            def find_char_pos_in_final(ch: str, prefer_after: bool=True):
                for idx, (pos, c) in enumerate(final_nonspace):
                    if c == ch:
                        return pos, idx
                return None, None

            newf = f
            changed = False
            # iterate through orig characters with neighbours
            for k, ch in enumerate(orig_seq):
                # If ch appears in final_seq at same relative order, skip
                # Otherwise attempt to insert
                try:
                    # if ch not in final_seq or order differs
                    # simple check: presence
                    if ch in final_seq:
                        continue
                except Exception:
                    pass
                # determine neighbours from orig
                prev_ch = orig_seq[k-1] if k-1 >= 0 else None
                next_ch = orig_seq[k+1] if k+1 < len(orig_seq) else None

                inserted = False
                # Try to find next_ch in final and insert before it
                if next_ch is not None:
                    pos, _idx = find_char_pos_in_final(next_ch)
                    if pos is not None:
                        # find insertion index in raw string before pos, skipping backward over spaces
                        insert_at = pos
                        while insert_at > 0 and newf[insert_at-1].isspace():
                            insert_at -= 1
                        newf = newf[:insert_at] + ch + newf[insert_at:]
                        final_seq.insert(_idx, ch)
                        changed = True
                        inserted = True
                if inserted:
                    continue
                # Try to find prev_ch in final and insert after it
                if prev_ch is not None:
                    pos, idxp = find_char_pos_in_final(prev_ch)
                    if pos is not None:
                        insert_at = pos + 1
                        # skip spaces forward
                        while insert_at < len(newf) and newf[insert_at].isspace():
                            insert_at += 1
                        newf = newf[:insert_at] + ch + newf[insert_at:]
                        # update final_seq approximation
                        if idxp is None:
                            final_seq.append(ch)
                        else:
                            final_seq.insert(idxp+1, ch)
                        changed = True
                        inserted = True
                # if couldn't insert, skip
            return newf, changed
        except Exception:
            return f, False

    def _try_speaker_fix(o: str, f: str) -> Tuple[str, bool]:
        """Attempt to insert missing quotes after colon and at end of line based on original.

        Returns (new_final, changed).
        """
        try:
            # find colon in original
            col_pos = None
            col_tok = None
            for col in COLON_EQS:
                idx = o.find(col)
                if idx != -1:
                    col_pos = idx
                    col_tok = col
                    break
            if col_pos is None:
                return f, False

            # After colon in original, find first quote (opening) if any
            open_quote = None
            open_pos = None
            # Guard Optional col_tok for typing; if None, bail out
            if col_tok is None:
                return f, False
            for j in range(col_pos + len(col_tok), len(o)):
                if o[j] in QUOTE_EQS:
                    open_quote = o[j]
                    open_pos = j
                    break

            # Determine if original had a closing quote later (a quote after open_pos)
            close_quote = None
            if open_pos is not None:
                for j in range(open_pos + 1, len(o)):
                    if o[j] in QUOTE_EQS:
                        close_quote = o[j]
                        break

            # In final, find colon
            final_col_pos = None
            final_col_tok = None
            for col in COLON_EQS:
                idx = f.find(col)
                if idx != -1:
                    final_col_pos = idx
                    final_col_tok = col
                    break
            if final_col_pos is None:
                # can't reliably fix if final lacks colon; give up
                return f, False

            newf = f
            changed = False
            # check for opening quote after colon in final (skip spaces)
            # Guard Optional final_col_tok for typing; if None, bail out
            if final_col_tok is None:
                return f, False
            j = final_col_pos + len(final_col_tok)
            while j < len(newf) and newf[j].isspace():
                j += 1
            has_open = (j < len(newf) and newf[j] in QUOTE_EQS)
            if not has_open and open_quote is not None:
                # insert opening quote at position j
                newf = newf[:j] + open_quote + newf[j:]
                changed = True

            # check for closing quote at end of line if original had it
            if close_quote is not None:
                # find last non-space character in newf
                k = len(newf) - 1
                while k >= 0 and newf[k].isspace():
                    k -= 1
                if k >= 0 and newf[k] not in QUOTE_EQS:
                    # append closing quote after last non-space char
                    insert_at = k + 1
                    newf = newf[:insert_at] + close_quote + newf[insert_at:]
                    changed = True

            return newf, changed
        except Exception:
            return f, False

    def _try_br_recovery(o: str, f: str, orig_count: int, final_count: int) -> Tuple[str, bool]:
        """Attempt to recover missing <br> tags from original into final.

        Strategy:
        - Find positions of <br> tags in original (relative to text length)
        - If final is missing <br> tags, try to insert them at similar relative positions
        - Preserve any existing <br> tags in final

        Returns:
            Tuple of (recovered_string, changed_flag)
        """
        import re as _re
        try:
            br_pattern = r"<br\s*/?\s*>"
            
            if final_count >= orig_count:
                return f, False  # No recovery needed
            
            # Find all <br> positions and content in original
            orig_matches = list(_re.finditer(br_pattern, o, _re.IGNORECASE))
            final_matches = list(_re.finditer(br_pattern, f, _re.IGNORECASE))
            
            if not orig_matches:
                return f, False
            
            # Simple strategy: if final has fewer <br> tags, try to insert missing ones
            # based on relative position in the string
            missing_count = orig_count - final_count
            if missing_count <= 0:
                return f, False
            
            newf = f
            changed = False
            
            # Calculate relative positions of <br> in original
            orig_len = len(o) if len(o) > 0 else 1
            orig_br_positions = []
            for m in orig_matches:
                rel_pos = m.start() / orig_len
                br_text = m.group(0)  # Preserve exact <br> format
                orig_br_positions.append((rel_pos, br_text))
            
            # Find which <br> are already in final (by relative position approximation)
            final_len = len(f) if len(f) > 0 else 1
            final_br_rel_positions = set()
            for m in final_matches:
                rel_pos = m.start() / final_len
                # Mark as "covered" if within 0.2 relative distance
                final_br_rel_positions.add(round(rel_pos, 1))
            
            # Insert missing <br> tags at approximate positions
            insertions = []
            for rel_pos, br_text in orig_br_positions:
                rounded = round(rel_pos, 1)
                if rounded not in final_br_rel_positions:
                    # Calculate insertion position in final
                    insert_at = int(rel_pos * len(newf))
                    # Adjust to not break words - find nearest space or punctuation
                    while insert_at > 0 and insert_at < len(newf) and not newf[insert_at - 1].isspace() and newf[insert_at - 1] not in ".,!?;:":
                        insert_at += 1
                        if insert_at >= len(newf):
                            break
                    insertions.append((insert_at, br_text))
                    final_br_rel_positions.add(rounded)
            
            # Sort insertions by position (descending) to avoid offset issues
            insertions.sort(key=lambda x: x[0], reverse=True)
            
            for insert_at, br_text in insertions:
                if insert_at >= len(newf):
                    insert_at = len(newf)
                newf = newf[:insert_at] + br_text + newf[insert_at:]
                changed = True
            
            return newf, changed
        except Exception:
            return f, False

    # We'll build potentially corrected final_lines so that fixes can be persisted
    corrected_final_lines: List[str] = list(final_lines)

    for i in range(total):
        o = orig_lines[i] if i < len(orig_lines) else ""
        f = corrected_final_lines[i] if i < len(corrected_final_lines) else (final_lines[i] if i < len(final_lines) else "")
        # Basic equality
        if o == f:
            identical += 1
            continue

        diff_rec: Dict[str, Any] = {"line": i + 1, "original": o, "final": f}

        # Attempt code recovery first (user requested code recovery before speaker fix)
        try:
            f_after_code, code_changed = _try_code_recover(o, f)
            if code_changed:
                f = f_after_code
                diff_rec.setdefault("auto_fixed", {})["code_recovered"] = True
        except Exception:
            pass

        # Speaker format validation using new detection system
        try:
            orig_info = detect_speaker_dialogue_format(o)
            final_info = detect_speaker_dialogue_format(f)
            
            if orig_info.has_speaker_format:
                # Original has speaker format - validate preservation
                format_valid, format_errors, format_warnings = validate_speaker_format_preserved(
                    o, f, strict=False
                )
                
                if not format_valid:
                    # Try to auto-fix speaker structure
                    f_after_speaker, sp_changed = _try_speaker_fix(o, f)
                    if sp_changed:
                        diff_rec.setdefault("auto_fixed", {})["speaker_fixed"] = True
                        f = f_after_speaker
                        # Re-validate after fix
                        format_valid, format_errors, format_warnings = validate_speaker_format_preserved(
                            o, f, strict=False
                        )
                    
                    if not format_valid:
                        # Still invalid after fix attempt - log and tag
                        diff_rec["speaker_format_error"] = {
                            "original_format": orig_info.to_dict(),
                            "errors": format_errors,
                            "warnings": format_warnings,
                            "needs_retranslation": should_retry_for_speaker_format(o, f),
                        }
                        # Add to line's log if manifest has line entries
                        if man.lines and i < len(man.lines):
                            line_entry = man.get_line(i)
                            if line_entry:
                                log_msg = f"Speaker format lost: {'; '.join(format_errors)}"
                                if line_entry.log:
                                    line_entry.log += f"\n{log_msg}"
                                else:
                                    line_entry.log = log_msg
                                # Add tag if available
                                if hasattr(line_entry, 'tags') and line_entry.tags is not None:
                                    if "speaker_format_error" not in line_entry.tags:
                                        line_entry.tags.append("speaker_format_error")
                                elif hasattr(line_entry, 'tags'):
                                    line_entry.tags = ["speaker_format_error"]
                        logging.warning(
                            "Line %d: Speaker format validation failed - %s",
                            i + 1, "; ".join(format_errors)
                        )
                
                if format_warnings:
                    diff_rec.setdefault("speaker_format_warnings", format_warnings)
        except Exception as e:
            logging.debug("Speaker format check error at line %d: %s", i + 1, e)

        # Code-structure check: ensure same sequence of code characters appears in same order
        try:
            orig_code_seq = _code_sequence(o)
            final_code_seq = _code_sequence(f)
            if orig_code_seq != final_code_seq:
                # attempt recovery if not yet tried
                if not diff_rec.get("auto_fixed", {}).get("code_recovered"):
                    f_after_code, code_changed = _try_code_recover(o, f)
                    if code_changed:
                        diff_rec.setdefault("auto_fixed", {})["code_recovered"] = True
                        f = f_after_code
                        final_code_seq = _code_sequence(f)
                if orig_code_seq != final_code_seq:
                    diff_rec["code_sequence_mismatch"] = {
                        "original_seq": orig_code_seq,
                        "final_seq": final_code_seq,
                    }
        except Exception:
            pass

        # <br> tag count validation: ensure same number of <br> tags in original and final
        try:
            br_pattern = r"<br\s*/?\s*>"
            import re as _re
            orig_br_count = len(_re.findall(br_pattern, o, _re.IGNORECASE))
            final_br_count = len(_re.findall(br_pattern, f, _re.IGNORECASE))
            if orig_br_count != final_br_count and orig_br_count > 0:
                # Attempt recovery: if original has more <br> tags, try to restore them
                f_after_br, br_changed = _try_br_recovery(o, f, orig_br_count, final_br_count)
                if br_changed:
                    diff_rec.setdefault("auto_fixed", {})["br_recovered"] = True
                    f = f_after_br
                    final_br_count = len(_re.findall(br_pattern, f, _re.IGNORECASE))
                if orig_br_count != final_br_count:
                    diff_rec["br_count_mismatch"] = {
                        "original_count": orig_br_count,
                        "final_count": final_br_count,
                    }
        except Exception:
            pass

        # If anything was auto-fixed, update the corrected buffer and log
        if "auto_fixed" in diff_rec and diff_rec["auto_fixed"]:
            corrected_final_lines[i] = f
            try:
                import logging as _log
                flags = ",".join(sorted([k for k,v in diff_rec["auto_fixed"].items() if v]))
                _log.info("PostAnalysis auto-fix applied at line %d: %s", i+1, flags)
            except Exception:
                pass

        diffs.append(diff_rec)

    # If corrections were applied, update manifest (v2.0 lines array + legacy mappings)
    try:
        if corrected_final_lines != final_lines:
            # v2.0: Update lines array fields
            if man.lines:
                for i, corrected in enumerate(corrected_final_lines):
                    line = man.get_line(i)
                    if line is not None:
                        line.postpro = corrected
                        line.wordwr = corrected  # Copy to wordwrap
                        line.overwrite = corrected  # Copy to overwrite

            # Legacy: Update mappings for backwards compatibility
            maps = getattr(man, "mappings", {}) or {}
            maps["final_lines"] = list(corrected_final_lines)
            try:
                from .wordwrap import apply_wordwrap, WordwrapConfig
                # default: no wrapping unless configured; we will copy final to wordwrap when no config
                # For now, just copy final to wordwrap per current spec request
                # If later there's a UI-driven config, replace below with apply_wordwrap(...)
                wordw = list(corrected_final_lines)
                maps["wordwrap_lines"] = wordw
                maps["overwrite_lines"] = list(wordw)
            except Exception:
                maps["wordwrap_lines"] = list(corrected_final_lines)
                maps["overwrite_lines"] = list(corrected_final_lines)
    except Exception:
        pass

    return {
        "total_lines": total,
        "identical_lines": identical,
        "differing_lines": len(diffs),
        "diffs": diffs,
    }
