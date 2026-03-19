from __future__ import annotations

"""Wordwrap utilities and entry points for CherryAI.

This module provides:
- smart_wrap: core, sensible word wrapping
- manual_wrap_line: a simple, deterministic wrap by characters
- apply_wordwrap: batch apply based on a config object
- get_wordwrap_modes: metadata for UI to lock/unlock inputs per mode

Inputs mapping for 'manual' mode:
- in1: width (int, required)
- in2: break char (str, e.g., "\\n" or "newline"; optional, defaults to "\\n")
- in3: max_lines (int, optional; when exceeded, warns and truncates output to max_lines with overflow logged)
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union, Tuple, Pattern
import logging
import re
import json
from pathlib import Path


@dataclass
class WordwrapConfig:
    """Configuration for applying wordwrap to a list of lines.

    Attributes:
        mode: Name of the wordwrap mode (e.g., "manual").
        in1: Primary input (for manual: width in characters).
        in2: Secondary input (for manual: break char, e.g., "\\n" or "newline").
        in3: Tertiary input (for manual: max lines count; warn if exceeded).
        pretty_wrap: Enable CherryAI's balanced pretty-wrap behavior.
        prevent_orphan: Legacy compatibility alias for pretty-wrap orphan handling.
        prefer_punct_breaks: Legacy compatibility alias for pretty-wrap punctuation handling.
    """

    mode: str = "manual"
    in1: Optional[int] = None
    in2: Optional[str] = None
    in3: Optional[int] = None
    # New configuration fields (extensible without breaking prior callers)
    ignore_codes: Optional[Union[str, List[str]]] = None  # names referencing built-in ignore span patterns
    speaker_mode: Optional[str] = None  # IGNORE|SAMELINE|SAMELINEINDENT|NEWLINE
    speaker_names: Optional[List[str]] = None  # detected speaker names from analysis/parser
    modi: Optional[str] = None  # txt|json|tsv|csv|xlsx|RPGMAKERMV|RPGMAKERMZ
    project_dir: Optional[Union[str, Path]] = None  # base directory for RPG data lookups (Actors, system variables)
    pretty_wrap: bool = True
    prevent_orphan: bool = True
    prefer_punct_breaks: bool = True


def normalize_break_char(s: Optional[str]) -> str:
    """Normalize a human selection into an actual line break string.

    Accepts values like "\\n", "newline", "\n", and returns "\n".
    """
    if not s:
        return "\n"
    ls = s.strip().lower()
    if ls in {"\\n", "\n", "newline", "linebreak"}:
        return "\n"
    # Allow custom single-char separators, otherwise default to newline
    return s


def smart_wrap(text: str, width: int, break_char: str = "\n", max_lines: Optional[int] = None,
               ignore_patterns: Optional[List[Pattern[str]]] = None) -> str:
    """Wrap text to a width with preference to breaking on spaces, fallback to hard breaks.

    - Greedy line building: append words while the next word fits; else wrap.
    - If a single token exceeds width, hard-break the token.
    - If max_lines is set and exceeded, log a warning and include the overflowing tail in the log.
    """
    if width is None or width <= 0:
        return text
    if not text:
        return ""

    words: List[str] = []
    # Basic tokenization on spaces; preserve existing explicit breaks by splitting and rejoining per segment
    segments = text.splitlines() if "\n" in text else [text]
    out_lines: List[str] = []

    def _emit_line(line: str):
        nonlocal out_lines
        out_lines.append(line)

    for seg in segments:
        if not seg:
            _emit_line("")
            continue
        if _visible_len(seg, ignore_patterns) <= width:
            _emit_line(seg)
            continue
        indent, body = _split_indent(seg)
        if not body:
            _emit_line(seg)
            continue
        effective_width = max(1, width - _visible_len(indent, ignore_patterns))
        words = body.split(" ")
        cur = ""
        for w in words:
            add = (w if cur == "" else (" " + w))
            visible_len_add = _visible_len(add, ignore_patterns)
            if _visible_len(cur, ignore_patterns) + visible_len_add <= effective_width:
                cur += add
            else:
                if cur:
                    _emit_line(indent + cur)
                # If a single word is longer than width, hard-break it
                # For ignored spans we do not split inside the span; fallback to raw length slicing.
                while _visible_len(w, ignore_patterns) > effective_width and effective_width > 0:
                    # naive slice respecting visible budget; iterate char by char counting visible width
                    piece = _slice_visible(w, effective_width, ignore_patterns)
                    if not piece:
                        break
                    _emit_line(indent + piece)
                    w = w[len(piece):]
                cur = w
        _emit_line(indent + cur)

    if max_lines is not None and max_lines > 0 and len(out_lines) > max_lines:
        overflow = break_char.join(out_lines[max_lines:])
        logging.warning("Wordwrap overflow: produced %d lines (> %d). Overflow: %s", len(out_lines), max_lines, overflow)
        out_lines = out_lines[:max_lines]

    return break_char.join(out_lines)


def apply_new_textbox_injection(
    text: str,
    break_char: str = "\n",
    max_lines: Optional[int] = None,
    injection: str = "",
) -> str:
    """Insert an explicit textbox separator between wrapped line groups.

    This is used for engines such as LightVN where overflow beyond ``max_lines``
    must become a visible string marker in ``wordwr`` rather than being inferred
    later during injection.
    """
    if not text or not injection or max_lines is None or max_lines <= 0:
        return text

    logical_lines = text.split(break_char) if break_char else [text]
    if len(logical_lines) <= max_lines:
        return text

    chunks = [
        logical_lines[idx:idx + max_lines]
        for idx in range(0, len(logical_lines), max_lines)
    ]
    parts: List[str] = []

    for idx, chunk in enumerate(chunks):
        chunk_text = break_char.join(chunk)
        if idx < len(chunks) - 1:
            parts.append(chunk_text + injection)
            continue
        parts.append(chunk_text)

    return "".join(parts)


def manual_wrap_line(text: str, width: int, break_char: str = "\n", max_lines: Optional[int] = None,
                     ignore_patterns: Optional[List[Pattern[str]]] = None,
                     speaker_mode: Optional[str] = None,
                     speaker_names: Optional[List[str]] = None,
                     project_dir: Optional[Union[str, Path]] = None) -> str:
    """Manual wrap by characters with sensible word boundaries where possible.

    The speaker_mode affects only an initial speaker prefix (detected by a name + ':' pattern).
    """
    return _wrap_with_speaker(text, width, break_char, max_lines, speaker_mode, speaker_names,
                              lambda t: _wrap_core_with_codes(t, width, break_char, max_lines,
                                                              ignore_patterns, project_dir,
                                                              smart_wrap))


def apply_wordwrap(lines: List[str], config: Union[WordwrapConfig, Dict[str, Any], None]) -> List[str]:
    """Apply wordwrap to a list of lines according to the config.

    When config is None or invalid, returns a copy of input lines unchanged.
    """
    if not isinstance(lines, list):
        return []
    if config is None:
        return list(lines)
    if isinstance(config, dict):
        cfg = WordwrapConfig(
            mode=str(config.get("mode", "manual")),
            in1=config.get("in1"),
            in2=config.get("in2"),
            in3=config.get("in3"),
            ignore_codes=config.get("ignore_codes"),
            speaker_mode=config.get("speaker_mode"),
            speaker_names=config.get("speaker_names"),
            modi=config.get("modi"),
            project_dir=config.get("project_dir"),
            pretty_wrap=config.get(
                "pretty_wrap",
                config.get("prevent_orphan", True)
                or config.get("prefer_punct_breaks", True),
            ),
            prevent_orphan=config.get("prevent_orphan", True),
            prefer_punct_breaks=config.get("prefer_punct_breaks", True),
        )
    else:
        cfg = config

    mode = (cfg.mode or "manual").lower()
    out: List[str] = []

    # Prepare ignore patterns once per batch
    ignore_patterns = _build_ignore_patterns(cfg.ignore_codes)
    speaker_mode = (cfg.speaker_mode or "").upper() or None
    speaker_names = list(cfg.speaker_names or [])
    modi = (cfg.modi or "").upper() or None
    _validate_modi(modi)  # currently no behavioral difference; placeholder for future logic

    if mode == "manual":
        try:
            width = int(cfg.in1) if cfg.in1 is not None else 0
        except Exception:
            width = 0
        br = normalize_break_char(cfg.in2)
        maxl = None
        try:
            if cfg.in3 is not None:
                maxl = int(cfg.in3)
        except Exception:
            maxl = None
        if width <= 0:
            # no-op if invalid width
            return list(lines)
        use_pretty = bool(
            getattr(cfg, "pretty_wrap", None)
            if getattr(cfg, "pretty_wrap", None) is not None
            else (cfg.prevent_orphan or cfg.prefer_punct_breaks)
        )
        for ln in lines:
            if use_pretty:
                out.append(_wrap_with_speaker(
                    ln, width, br, maxl, speaker_mode, speaker_names,
                    lambda t: _wrap_core_with_codes(
                        t, width, br, maxl, ignore_patterns,
                        cfg.project_dir,
                        lambda inner, ew, bc, ml, ip: pretty_wrap(
                            inner, width=ew, break_char=bc,
                            max_lines=ml,
                            prevent_orphan=cfg.prevent_orphan,
                            prefer_punct_breaks=cfg.prefer_punct_breaks,
                            ignore_patterns=ip,
                        ),
                    ),
                ))
            else:
                out.append(manual_wrap_line(
                    ln, width=width, break_char=br, max_lines=maxl,
                    ignore_patterns=ignore_patterns,
                    speaker_mode=speaker_mode,
                    speaker_names=speaker_names,
                    project_dir=cfg.project_dir,
                ))
        return out

    if mode in ("rpgmaker", "rpgmaker_mv_mz", "rpgmaker_mz", "rpgmaker_mv"):
        # Character-based approximation with pretty wrapping rules (engine-agnostic core)
        try:
            width = int(cfg.in1) if cfg.in1 is not None else 0
        except Exception:
            width = 0
        br = normalize_break_char(cfg.in2)
        maxl = None
        try:
            if cfg.in3 is not None:
                maxl = int(cfg.in3)
        except Exception:
            maxl = None
        if width <= 0:
            return list(lines)
        out = []
        for ln in lines:
            out.append(rpgmaker_wrap_line(ln, width=width, break_char=br, max_lines=maxl,
                                          ignore_patterns=ignore_patterns, speaker_mode=speaker_mode,
                                          project_dir=cfg.project_dir))
        return out

    # Unknown mode -> no-op
    return list(lines)


def get_wordwrap_modes() -> Dict[str, Dict[str, Any]]:
    """Return UI metadata for wordwrap modes to control input enablement.

    Each entry describes which inputs are used and labels for UI.
    """
    return {
        "manual": {
            "label": "Manual by characters",
            "inputs": {
                "in1": {"label": "Characters per line", "required": True, "type": "int"},
                "in2": {"label": "Break", "required": False, "type": "choice", "choices": ["\\n", "newline"]},
                "in3": {"label": "Max lines", "required": False, "type": "int"},
                "ignore_codes": {"label": "Ignore codes", "required": False, "type": "multi-choice",
                                   "choices": ["angle", "square", "curly", "en"]},
                "speaker_mode": {"label": "Speaker Mode", "required": False, "type": "choice",
                                   "choices": ["IGNORE", "SAMELINE", "SAMELINEINDENT", "NEWLINE"]},
                "modi": {"label": "Mode/Format", "required": False, "type": "choice",
                          "choices": ["TXT", "JSON", "TSV", "CSV", "XLSX", "RPGMAKERMV", "RPGMAKERMZ"]},
            },
        },
        "rpgmaker": {
            "label": "RPGMaker MV/MZ (pretty)",
            "inputs": {
                "in1": {"label": "Characters per line", "required": True, "type": "int"},
                "in2": {"label": "Break", "required": False, "type": "choice", "choices": ["\\n", "newline"]},
                "in3": {"label": "Max lines", "required": False, "type": "int"},
                "ignore_codes": {"label": "Ignore codes", "required": False, "type": "multi-choice",
                                   "choices": ["angle", "square", "curly", "en"]},
                "speaker_mode": {"label": "Speaker Mode", "required": False, "type": "choice",
                                   "choices": ["IGNORE", "SAMELINE", "SAMELINEINDENT", "NEWLINE"]},
                "modi": {"label": "Mode/Format", "required": False, "type": "choice",
                          "choices": ["TXT", "JSON", "TSV", "CSV", "XLSX", "RPGMAKERMV", "RPGMAKERMZ"]},
            },
            "notes": "Uses punctuation-preferred breaks, anti-orphan, speaker hanging indent, bullet handling."
        }
    }


# ---------------- Pretty wrapping rules (engine-agnostic) ---------------- #

_PUNCT_PREF = set(list(",.;:!?、。；：！？"))
_SPEAKER_RE = re.compile(r"^(?P<name>[^:：]{1,100})\s*[:：]\s*([\"'“”‘’\(（「『])?")
_BULLET_RE = re.compile(r"^\s*(?:>|=>|\.|-|•|\*)\s")


def _find_hanging_indent(text: str) -> int:
    """Return hanging indent size (in spaces) after a speaker pattern or bullet marker."""
    # Speaker pattern: characters up to colon + following space/quote
    m = re.match(r"^\s*([^:：]{1,100})\s*[:：]\s*", text)
    if m:
        return len(m.group(0))
    # Bullet pattern: keep indentation after bullet and following space
    mb = _BULLET_RE.match(text)
    if mb:
        return len(mb.group(0))
    return 0


def _split_indent(text: str) -> Tuple[str, str]:
    """Split leading whitespace indentation from visible text."""
    match = re.match(r"^(\s*)(.*)$", text, re.DOTALL)
    if match is None:
        return "", text
    return match.group(1), match.group(2)


def _split_words_preserve(text: str) -> List[str]:
    """Split by spaces while preserving punctuation as part of tokens."""
    # Simple split; punctuation preference handled by backtracking later
    if not text:
        return []
    return text.split(" ")


def pretty_wrap(text: str, width: int, break_char: str = "\n", max_lines: Optional[int] = None,
                prevent_orphan: bool = True, prefer_punct_breaks: bool = True, hanging_indent: int = 0,
                ignore_patterns: Optional[List[Pattern[str]]] = None) -> str:
    """Wrap with punctuation preference, anti-orphan, and optional hanging indent.

    - prefer_punct_breaks: when exceeding width, backtrack to last token ending with punctuation if available.
    - prevent_orphan: ensure last line isn't a tiny orphan; if so, rebalance by moving one word.
    - hanging_indent: number of spaces to prefix on continuation lines.
    """
    if width <= 0 or not text:
        return text

    segments = text.splitlines() if "\n" in text else [text]
    out_lines: List[str] = []

    for segment in segments:
        if not segment:
            out_lines.append("")
            continue
        if _visible_len(segment, ignore_patterns) <= width:
            out_lines.append(segment)
            continue

        indent, body = _split_indent(segment)
        if not body:
            out_lines.append(segment)
            continue

        effective_width = max(1, width - _visible_len(indent, ignore_patterns))
        words = _split_words_preserve(body)
        segment_lines: List[str] = []
        cur = ""
        for w in words:
            add = (w if cur == "" else (" " + w))
            if _visible_len(cur + add, ignore_patterns) <= effective_width:
                cur += add
            else:
                if cur:
                    merged = cur + (" " if cur else "") + w
                    if prefer_punct_breaks and _visible_len(merged, ignore_patterns) > effective_width:
                        cut = _find_punct_visible_cut(merged, effective_width, ignore_patterns)
                        if cut is not None and cut > 0:
                            segment_lines.append(merged[:cut].rstrip())
                            cur = (" " * hanging_indent) + merged[cut:].lstrip()
                            continue
                    segment_lines.append(cur)
                cur = (" " * hanging_indent) + w
        segment_lines.append(cur)

        optimized_segment_lines = _rebalance_pretty_lines(
            words,
            effective_width=effective_width,
            line_count=len(segment_lines),
            hanging_indent=hanging_indent,
            ignore_patterns=ignore_patterns,
            prefer_punct_breaks=prefer_punct_breaks,
            prevent_orphan=prevent_orphan,
        )
        if optimized_segment_lines is not None:
            segment_lines = optimized_segment_lines

        if prevent_orphan and len(segment_lines) >= 2:
            last = segment_lines[-1]
            prev = segment_lines[-2]
            if _visible_len(last.strip(), ignore_patterns) <= max(2, int(effective_width * 0.2)):
                prev_words = prev.rstrip().split(" ")
                if len(prev_words) >= 2:
                    moved = prev_words.pop()
                    cand_prev = " ".join(prev_words)
                    cand_last = last if last.strip() else (" " * hanging_indent)
                    new_last = moved if cand_last.strip() == "" else moved + " " + cand_last.strip()
                    if (
                        _visible_len(cand_prev, ignore_patterns) <= effective_width
                        and _visible_len(new_last, ignore_patterns) <= effective_width
                    ):
                        segment_lines[-2] = cand_prev
                        segment_lines[-1] = (" " * hanging_indent) + new_last

        out_lines.extend(indent + line if line else indent for line in segment_lines)

    if max_lines is not None and max_lines > 0 and len(out_lines) > max_lines:
        overflow = break_char.join(out_lines[max_lines:])
        logging.warning("Wordwrap overflow: produced %d lines (> %d). Overflow: %s", len(out_lines), max_lines, overflow)
        out_lines = out_lines[:max_lines]

    return break_char.join(out_lines)


def _token_join_visible_len(
    tokens: List[str],
    ignore_patterns: Optional[List[Pattern[str]]],
) -> int:
    """Return the visible width of space-joined *tokens*."""
    if not tokens:
        return 0
    return sum(_visible_len(token, ignore_patterns) for token in tokens) + max(0, len(tokens) - 1)


def _score_pretty_line_break(
    used_width: int,
    capacity: int,
    last_token: str,
    *,
    is_last_line: bool,
    prefer_punct_breaks: bool,
    prevent_orphan: bool,
) -> float:
    """Return a raggedness score for a candidate wrapped line."""
    slack = max(0, capacity - used_width)
    score = float(slack * slack)

    if prefer_punct_breaks and last_token and last_token[-1] in _PUNCT_PREF:
        score -= 4.0

    if is_last_line and prevent_orphan:
        short_threshold = max(2, int(capacity * 0.25))
        if used_width <= short_threshold:
            score += float((short_threshold - used_width + 1) * 100)

    return score


def _rebalance_pretty_lines(
    words: List[str],
    *,
    effective_width: int,
    line_count: int,
    hanging_indent: int,
    ignore_patterns: Optional[List[Pattern[str]]],
    prefer_punct_breaks: bool,
    prevent_orphan: bool,
) -> Optional[List[str]]:
    """Repartition tokens into a better balanced layout using the same line count."""
    if line_count < 2 or len(words) < 2:
        return None

    continuation_width = max(1, effective_width - max(0, hanging_indent))
    capacities = [effective_width] + [continuation_width] * (line_count - 1)
    max_lines = len(capacities)
    cache: Dict[Tuple[int, int], Optional[Tuple[float, List[List[str]]]]] = {}

    def solve(start: int, line_idx: int) -> Optional[Tuple[float, List[List[str]]]]:
        key = (start, line_idx)
        if key in cache:
            return cache[key]

        remaining_words = len(words) - start
        remaining_lines = max_lines - line_idx
        if remaining_words < remaining_lines:
            cache[key] = None
            return None

        if line_idx == max_lines:
            result = (0.0, []) if start == len(words) else None
            cache[key] = result
            return result

        capacity = capacities[line_idx]
        best: Optional[Tuple[float, List[List[str]]]] = None
        for end in range(start + 1, len(words) + 1):
            tokens = words[start:end]
            used = _token_join_visible_len(tokens, ignore_patterns)
            if used > capacity:
                break
            tail = solve(end, line_idx + 1)
            if tail is None:
                continue
            line_score = _score_pretty_line_break(
                used,
                capacity,
                tokens[-1],
                is_last_line=(line_idx == max_lines - 1),
                prefer_punct_breaks=prefer_punct_breaks,
                prevent_orphan=prevent_orphan,
            )
            total_score = line_score + tail[0]
            candidate_lines = [tokens] + tail[1]
            if best is None or total_score < best[0]:
                best = (total_score, candidate_lines)

        cache[key] = best
        return best

    solved = solve(0, 0)
    if solved is None:
        return None

    result: List[str] = []
    for idx, tokens in enumerate(solved[1]):
        line = " ".join(tokens)
        if idx > 0 and hanging_indent > 0:
            line = (" " * hanging_indent) + line
        result.append(line)
    return result


def rpgmaker_wrap_line(text: str, width: int, break_char: str = "\n", max_lines: Optional[int] = None,
                       ignore_patterns: Optional[List[Pattern[str]]] = None,
                       speaker_mode: Optional[str] = None,
                       speaker_names: Optional[List[str]] = None,
                       project_dir: Optional[Union[str, Path]] = None) -> str:
    """Wrap a single line using RPGMaker MV/MZ-friendly rules (character-based approximation).

    - Hanging indent for speaker/bullet prefixes.
    - Prefer breaks at punctuation.
    - Anti-orphan handling.
    """
    hanging = _find_hanging_indent(text)
    return _wrap_with_speaker(text, width, break_char, max_lines, speaker_mode, speaker_names,
                              lambda t: _wrap_core_with_codes(t, width, break_char, max_lines,
                                                              ignore_patterns, project_dir,
                                                              lambda inner_text, eff_width, bc, ml, ip: pretty_wrap(inner_text, width=eff_width, break_char=bc, max_lines=ml,
                                                                                                                   prevent_orphan=True, prefer_punct_breaks=True,
                                                                                                                   hanging_indent=hanging, ignore_patterns=ip)))


def analyze_rpgmaker_project(path: Union[str, Path], window_padding: int = 18) -> Dict[str, Any]:
    """Analyze an RPG Maker MV/MZ project directory (or game executable path) and return rendering hints.

    The function searches for `data/system.json`, `js/plugins.js`, and `js/rmmz_scenes.js` to extract:
      - uiAreaWidth
      - mainFontFilename
      - fontSize
      - boxMargin (from rmmz_scenes.js)
      - plugin_override_window_width (if NRP_MessageWindow WindowWidth param found)
      - usable_pixel_width (uiAreaWidth - boxMargin*2 - window_padding*2)

    Returns a dict with the discovered values and sensible defaults when keys are missing.
    This does not require Pillow; it only extracts numeric/UI metadata for higher-level helpers.
    """
    p = Path(path)
    if p.is_file():
        project_dir = p.parent
    else:
        project_dir = p

    result: Dict[str, Any] = {
        "uiAreaWidth": None,
        "mainFontFilename": None,
        "fontSize": None,
        "boxMargin": None,
        "plugin_override_window_width": None,
        "usable_pixel_width": None,
        "source": str(project_dir),
    }

    # system.json
    sys_path = project_dir / "data" / "system.json"
    if sys_path.exists():
        try:
            raw = sys_path.read_bytes()
            try:
                s = raw.decode("utf-8-sig")
            except Exception:
                s = raw.decode("utf-8", errors="replace")
            sysdata = json.loads(s)
            settings = sysdata.get("advanced", sysdata)
            result["uiAreaWidth"] = int(settings.get("uiAreaWidth", 816))
            result["mainFontFilename"] = settings.get("mainFontFilename", "gamefont.ttf")
            result["fontSize"] = int(settings.get("fontSize", 26))
        except Exception:
            # leave defaults as None
            pass

    # rmmz_scenes.js -> boxMargin
    scenes_js = project_dir / "js" / "rmmz_scenes.js"
    if scenes_js.exists():
        try:
            txt = scenes_js.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"const\s+boxMargin\s*=\s*(\d+);", txt)
            if m:
                result["boxMargin"] = int(m.group(1))
        except Exception:
            pass

    # plugins.js -> look for NRP_MessageWindow WindowWidth
    plugins_js = project_dir / "js" / "plugins.js"
    if plugins_js.exists():
        try:
            content = plugins_js.read_text(encoding="utf-8", errors="ignore")
            # strip block comments and line comments for a best-effort JSON parse
            cleaned = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
            cleaned = re.sub(r"//.*", "", cleaned)
            m = re.search(r"var\s+\$plugins\s*=\s*(\[.*?\]);", cleaned, flags=re.DOTALL)
            if m:
                arr_text = m.group(1)
                try:
                    plugins = json.loads(arr_text)
                    for p in plugins:
                        if isinstance(p, dict) and p.get("name") == "NRP_MessageWindow" and p.get("status"):
                            params = p.get("parameters", {})
                            raw = params.get("WindowWidth")
                            if raw:
                                if isinstance(raw, (int, float)):
                                    result["plugin_override_window_width"] = int(raw)
                                else:
                                    raw_s = str(raw)
                                    digit_m = re.search(r"(\d+)", raw_s)
                                    if digit_m:
                                        result["plugin_override_window_width"] = int(digit_m.group(1))
                except Exception:
                    # fallback: scan for the string pattern WindowWidth
                    if "NRP_MessageWindow" in cleaned and "WindowWidth" in cleaned:
                        m2 = re.search(r'"WindowWidth"\s*:\s*"?([^",}]+)"?', cleaned)
                        if m2:
                            digit_m = re.search(r"(\d+)", m2.group(1))
                            if digit_m:
                                result["plugin_override_window_width"] = int(digit_m.group(1))
        except Exception:
            pass

    # Compute usable_pixel_width if possible
    ui = result.get("uiAreaWidth")
    box = result.get("boxMargin")
    plugin_w = result.get("plugin_override_window_width")
    try:
        if plugin_w:
            outer_width = plugin_w
            usable = outer_width - (window_padding * 2)
        elif ui is not None:
            bm = box if box is not None else 0
            outer_width = ui - (bm * 2)
            usable = outer_width - (window_padding * 2)
        else:
            usable = None
        result["usable_pixel_width"] = int(usable) if usable is not None else None
    except Exception:
        result["usable_pixel_width"] = None

    return result


def estimate_chars_per_line(pixel_width: Optional[int], avg_char_px: float = 10.0) -> Optional[int]:
    """Estimate characters-per-line given a pixel budget and average char pixel width.

    This provides a fallback for `rpgmaker` mode when precise font metrics (Pillow) aren't available.
    """
    if pixel_width is None:
        return None
    try:
        if avg_char_px <= 0:
            avg_char_px = 10.0
        return max(1, int(pixel_width / avg_char_px))
    except Exception:
        return None


def measure_font_avg_char_px(project_dir: Union[str, Path], font_filename: str, font_size: int) -> Optional[float]:
    """Measure average character pixel width using Pillow when available.

    Returns average pixel width per character (float) or None if Pillow or font file is not available.
    The function measures a sample string of repeated ASCII 'n' characters and divides.
    
    Note: Requires Pillow to be installed (pip install Pillow). Returns None if not available.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    
    proj = Path(project_dir)
    font_path = proj / "fonts" / font_filename
    if not font_path.exists():
        return None

    try:
        # Create a temporary image for measuring
        font = ImageFont.truetype(str(font_path), size=int(font_size))
        sample = "nnnnnnnnnn"  # 10 chars
        # Some ImageFont implementations prefer textlength/getlength
        try:
            # PIL >= 9.2 has getlength
            total = font.getlength(sample)
        except Exception:
            img = Image.new("RGB", (1000, 200))
            draw = ImageDraw.Draw(img)
            try:
                total = draw.textlength(sample, font=font)
            except Exception:
                # Fallback for older PIL versions: use textbbox to compute width
                try:
                    bbox = draw.textbbox((0, 0), sample, font=font)
                    total = (bbox[2] - bbox[0])
                except Exception:
                    # Last resort: assume average width ~ font size * 0.6
                    total = max(1.0, float(font_size) * 0.6 * len(sample))
        avg = float(total) / len(sample)
        return max(0.1, avg)
    except Exception:
        return None


# ---------------- New helper utilities for ignore spans & speaker handling ---------------- #

_IGNORE_CODE_PATTERNS: Dict[str, Pattern[str]] = {
    "ANGLE": re.compile(r"<.*?>"),
    "SQUARE": re.compile(r"\[.*?]"),
    "CURLY": re.compile(r"\{.*?}"),
    "EN": re.compile(r"en\(.*?\)"),
}


def _build_ignore_patterns(selection: Optional[Union[str, List[str]]]) -> List[Pattern[str]]:
    if selection is None:
        return []
    if isinstance(selection, str):
        parts = [p.strip() for p in selection.replace(";", ",").split(",") if p.strip()]
    else:
        parts = [p for p in selection if str(p).strip()]
    out: List[Pattern[str]] = []
    for raw_part in parts:
        if hasattr(raw_part, "match") and callable(getattr(raw_part, "match", None)):
            out.append(raw_part)
            continue
        name = str(raw_part).strip()
        key = name.upper()
        pat = _IGNORE_CODE_PATTERNS.get(key)
        if pat:
            out.append(pat)
            continue
        try:
            out.append(re.compile(name))
        except re.error:
            out.append(re.compile(re.escape(name)))
    return out


def _visible_len(s: str, ignore_patterns: Optional[List[Pattern[str]]]) -> int:
    if not s:
        return 0
    if not ignore_patterns:
        return len(s)
    length = 0
    idx = 0
    while idx < len(s):
        matched = False
        for pat in ignore_patterns:
            m = pat.match(s, idx)
            if m:
                # zero width contribution
                idx = m.end()
                matched = True
                break
        if matched:
            continue
        length += 1
        idx += 1
    return length


def _slice_visible(s: str, budget: int, ignore_patterns: Optional[List[Pattern[str]]]) -> str:
    """Return a prefix of s whose visible length <= budget (greedy)."""
    if budget <= 0:
        return ""
    if not ignore_patterns:
        return s[:budget]
    out_chars: List[str] = []
    visible = 0
    idx = 0
    while idx < len(s) and visible < budget:
        for pat in ignore_patterns or []:
            m = pat.match(s, idx)
            if m:
                out_chars.append(m.group(0))
                idx = m.end()
                # no visible increment
                break
        else:
            out_chars.append(s[idx])
            visible += 1
            idx += 1
    return "".join(out_chars)


def _find_punct_visible_cut(merged: str, width: int, ignore_patterns: Optional[List[Pattern[str]]]) -> Optional[int]:
    """Find a cut index (string index) such that visible length <= width and ends at punctuation/space."""
    # iterate positions and track visible length
    vis = 0
    candidate = None
    i = 0
    L = len(merged)
    while i < L and vis <= width:
        # check ignore
        ign_hit = False
        if ignore_patterns:
            for pat in ignore_patterns:
                m = pat.match(merged, i)
                if m:
                    i = m.end()
                    ign_hit = True
                    break
        if ign_hit:
            continue
        ch = merged[i]
        if ch in _PUNCT_PREF or ch.isspace():
            candidate = i + 1  # past this char
        vis += 1
        if vis > width:
            break
        i += 1
    return candidate


def _validate_modi(modi: Optional[str]) -> None:
    if not modi:
        return
    allowed = {"TXT", "JSON", "TSV", "CSV", "XLSX", "RPGMAKERMV", "RPGMAKERMZ"}
    if modi not in allowed:
        logging.warning("Unknown modi '%s' ignored.", modi)


def _wrap_with_speaker(text: str, width: int, break_char: str, max_lines: Optional[int], speaker_mode: Optional[str],
                       speaker_names: Optional[List[str]],
                       core_wrap_fn: Callable[[str], str]) -> str:
    """Apply speaker handling modes then invoke core wrap.

    Modes:
        IGNORE: remove the speaker prefix entirely before wrapping.
        SAMELINE: keep prefix on first line only; continuation lines not indented.
        SAMELINEINDENT: prefix on first line; subsequent lines indented so first dialogue letter aligns.
        NEWLINE: speaker prefix output as its own line (no wrap), dialogue starts next line.
    """
    if not speaker_mode:
        return core_wrap_fn(text)
    speaker_mode = speaker_mode.upper()
    split = _split_speaker_prefix(text, speaker_names)
    if split is None:
        return core_wrap_fn(text)
    prefix, body = split
    if speaker_mode == "IGNORE":
        wrapped_body = core_wrap_fn(body)
        body_lines = wrapped_body.split(break_char)
        if not body_lines:
            return prefix.rstrip()
        body_lines[0] = prefix + body_lines[0].lstrip()
        return break_char.join(body_lines)
    if speaker_mode == "NEWLINE":
        wrapped = core_wrap_fn(body)
        return prefix.rstrip() + break_char + wrapped
    if speaker_mode == "SAMELINE":
        # simply wrap full text; then strip prefix from continuation lines if present via hanging indent removal
        wrapped = core_wrap_fn(text)
        lines = wrapped.split(break_char)
        if len(lines) <= 1:
            return wrapped
        # remove any indentation applied by pretty_wrap for continuation lines (only for rpgmaker path)
        lines[1:] = [ln.lstrip() for ln in lines[1:]]
        return break_char.join(lines)
    if speaker_mode == "SAMELINEINDENT":
        # Determine indent size so first actual letter aligns across lines (skip opening quotes/punct in body)
        body_stripped = body.lstrip()
        offset = len(prefix)
        # Find first alphabetic character in body (after potential opening quotes/punct)
        first_letter_idx = 0
        for i, ch in enumerate(body_stripped):
            if ch.isalnum():
                first_letter_idx = i
                break
        indent_len = offset + first_letter_idx
        wrapped = core_wrap_fn(prefix + body)
        lines = wrapped.split(break_char)
        if len(lines) <= 1:
            return wrapped
        # Apply computed indent to continuation lines and remove any existing inconsistent indentation
        desired_indent = " " * indent_len
        for i in range(1, len(lines)):
            lines[i] = desired_indent + lines[i].lstrip()
        return break_char.join(lines)
    return core_wrap_fn(text)


def _split_speaker_prefix(
    text: str,
    speaker_names: Optional[List[str]],
) -> Optional[Tuple[str, str]]:
    """Return ``(prefix, body)`` when *text* starts with a valid speaker prefix."""
    match = re.match(
        r"^(?P<leading>\s*)(?P<name>[^:：]{1,100}?)(?P<sep>\s*[:：]\s*)(?P<body>.*)$",
        text,
        re.DOTALL,
    )
    if match is None:
        return None

    name = match.group("name").strip()
    if speaker_names:
        allowed = {speaker.strip() for speaker in speaker_names if speaker and speaker.strip()}
        if name not in allowed:
            return None

    prefix = f"{match.group('leading')}{match.group('name')}{match.group('sep')}"
    return prefix, match.group("body")


# ---------------- Backslash code preprocessing ---------------- #

_RPG_CONTEXT_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_rpg_context(project_dir: Optional[Union[str, Path]]) -> Dict[str, Any]:
    if not project_dir:
        return {"actors": {}, "variables": [], "fontSize": 26}
    p = Path(project_dir)
    key = str(p.resolve())
    if key in _RPG_CONTEXT_CACHE:
        return _RPG_CONTEXT_CACHE[key]
    ctx: Dict[str, Any] = {"actors": {}, "variables": [], "fontSize": 26}
    try:
        # system.json for variables & fontSize
        sys_path = p / "data" / "system.json"
        if sys_path.exists():
            raw = sys_path.read_bytes()
            try:
                s = raw.decode("utf-8-sig")
            except Exception:
                s = raw.decode("utf-8", errors="replace")
            sysdata = json.loads(s)
            settings = sysdata.get("advanced", sysdata)
            ctx["variables"] = settings.get("variables", [])
            try:
                ctx["fontSize"] = int(settings.get("fontSize", 26))
            except Exception:
                pass
        # Actors.json
        actors_path = p / "data" / "Actors.json"
        if actors_path.exists():
            raw = actors_path.read_bytes()
            try:
                s = raw.decode("utf-8-sig")
            except Exception:
                s = raw.decode("utf-8", errors="replace")
            actors = json.loads(s)
            # actors is list with entries that have 'name'
            actors_map = {}
            if isinstance(actors, list):
                for a in actors:
                    if isinstance(a, dict):
                        aid = a.get("id") or a.get("_id") or a.get("actorId")
                        if aid is None and "name" in a:
                            # fallback to index
                            aid = a.get("name")
                        if isinstance(aid, int):
                            actors_map[aid] = a.get("name", "")
            ctx["actors"] = actors_map
    except Exception:
        pass
    _RPG_CONTEXT_CACHE[key] = ctx
    return ctx


def _expand_and_adjust_width(
    text: str,
    width: int,
    project_dir: Optional[Union[str, Path]],
) -> Tuple[str, int]:
    r"""Expand RPG-style backslash codes and compute an adjusted width.

    Supported codes (subset):
        \n -> stripped
        \n[#] -> actor name (# index/id)
        \V[#] -> variable value (# index)
        \I[#] -> icon (zero-width placeholder)
        \{ -> increase font size by +4 (affects width scaling)
        \} -> decrease font size by -4
        \fs[#] -> set font size to #

    Unknown codes are treated as zero-width.
    Width scaling heuristic:
        effective_width = int(width * base_font_size / avg_font_size_used)
    """
    ctx = _load_rpg_context(project_dir)
    base_fs = ctx.get("fontSize") or 26
    cur_fs = base_fs
    total_visible_fs = 0
    visible_chars = 0
    out: List[str] = []
    i = 0
    L = len(text)
    code_re = re.compile(r"\\(fs\[(\d+)\]|n\[(\d+)\]|V\[(\d+)\]|I\[(\d+)\]|n|\{|\}|.)")
    while i < L:
        m = code_re.match(text, i)
        if m:
            full = m.group(0)
            fs_set = m.group(2)
            actor_id = m.group(3)
            var_id = m.group(4)
            icon_id = m.group(5)
            code_body = full[1:]  # strip leading backslash
            if fs_set is not None:
                try:
                    cur_fs = int(fs_set)
                except Exception:
                    pass
            elif actor_id is not None:
                try:
                    aid = int(actor_id)
                    name = ctx.get("actors", {}).get(aid, "")
                    out.append(name)
                    for ch in name:
                        visible_chars += 1
                        total_visible_fs += cur_fs
                except Exception:
                    pass
            elif var_id is not None:
                try:
                    vidx = int(var_id)
                    vars_list = ctx.get("variables", [])
                    val = ""
                    if isinstance(vars_list, list) and 0 <= vidx < len(vars_list):
                        v = vars_list[vidx]
                        if v is None:
                            val = ""
                        else:
                            val = str(v)
                    out.append(val)
                    for ch in val:
                        visible_chars += 1
                        total_visible_fs += cur_fs
                except Exception:
                    pass
            elif icon_id is not None:
                # zero-width placeholder for icon
                pass
            elif code_body == 'n':
                # stripped newline control code
                pass
            elif code_body == '{':
                cur_fs += 4
            elif code_body == '}':
                cur_fs = max(4, cur_fs - 4)
            else:
                # unknown code -> ignore
                pass
            i += len(full)
            continue
        # normal character
        ch = text[i]
        out.append(ch)
        if not ch.isspace() or ch == ' ':
            visible_chars += 1
            total_visible_fs += cur_fs
        else:
            # treat whitespace as visible char for width purposes
            visible_chars += 1
            total_visible_fs += cur_fs
        i += 1
    avg_fs = (total_visible_fs / visible_chars) if visible_chars > 0 else base_fs
    try:
        eff_width = int(max(1, round(width * (base_fs / avg_fs))))
    except Exception:
        eff_width = width
    return ("".join(out), eff_width)


def _wrap_core_with_codes(text: str, width: int, break_char: str, max_lines: Optional[int],
                          ignore_patterns: Optional[List[Pattern[str]]], project_dir: Optional[Union[str, Path]],
                          core_fn: Optional[Callable[..., str]]) -> str:
    if project_dir is None:
        expanded = _replace_literal_break_commands(text)
        eff_width = width
    else:
        expanded, eff_width = _expand_and_adjust_width(text, width, project_dir)
    # core_fn may be smart_wrap or a lambda wrapping pretty_wrap
    if callable(core_fn):
        try:
            # If core_fn expects (text, width,...), allow adapter style
            result = core_fn(expanded, eff_width, break_char, max_lines, ignore_patterns)
            return str(result) if result is not None else ""
        except TypeError:
            # Fallback to smart_wrap signature
            return smart_wrap(expanded, eff_width, break_char, max_lines, ignore_patterns)
    return smart_wrap(expanded, eff_width, break_char, max_lines, ignore_patterns)


def _replace_literal_break_commands(text: str) -> str:
    """Convert literal line-break commands into actual newlines for wrapping.

    Only unescaped ``\n`` and ``\r\n`` sequences are converted. Escaped
    backslashes such as ``\\n`` remain literal text.
    """
    if "\\" not in text:
        return text

    out: List[str] = []
    idx = 0
    while idx < len(text):
        if text[idx] != "\\":
            out.append(text[idx])
            idx += 1
            continue

        run_start = idx
        while idx < len(text) and text[idx] == "\\":
            idx += 1
        slash_run = idx - run_start
        out.append("\\" * (slash_run // 2))

        if slash_run % 2 == 0:
            continue

        if text.startswith("r\\n", idx):
            out.append("\n")
            idx += 3
            continue
        if idx < len(text) and text[idx] == "n":
            out.append("\n")
            idx += 1
            continue

        out.append("\\")

    return "".join(out)
