"""Light VN Parser Script (Parser Handshake compliant).

Extracts and injects translatable text from Light VN visual novel scripts.
Handles dialogue, menu text, and variable assignment text with full code
recovery, speaker detection, and engine-specific wordwrap.

Extraction Tags:
    - ``"dialogue"``: Story dialogue (with optional speaker).
    - ``"menu"``: Menu/button text from ``~文字`` / ``~ボタン文字`` commands.
    - ``"variable"``: Translatable variable assignments (skill names, items).

Speaker Format:
    Dialogue keys use ``"Speaker: text"`` when a speaker is active.
    Narration (empty ``~【】``) has no speaker prefix.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .handshake import ExtractedLine, ParserError, SpeakerInfo
from .parser_base import (
    TagRules,
    ForbiddenChars,
    ParserScript,
    WordwrapConfig,
)


__all__ = ["LightVNParser"]

logger = logging.getLogger("cherryai.formats.lightvn")


# ---------------------------------------------------------------------------
# Tag constants (encouraged, not restricted)
# ---------------------------------------------------------------------------

TAG_DIALOGUE = "dialogue"
TAG_MENU = "menu"
TAG_VARIABLE = "variable"


# ---------------------------------------------------------------------------
# Parser implementation
# ---------------------------------------------------------------------------

class LightVNParser(ParserScript):
    """Parser for Light VN visual novel script files.

    Implements the Parser Handshake contract with:
        - M1: ``extract`` / ``extract_tagged``
        - M2: ``inject``
        - M3: ``can_handle``
        - O3: ``detect_encoding``
        - O4: ``detect_speakers``
        - O5: ``wordwrap_config``
        - O6: ``wordwrap`` (custom balanced wrapping)
        - O7: ``forbidden_chars``
        - O8: ``tag_rules``
    """

    # -- Patterns ----------------------------------------------------------

    SPEAKER_PATTERN = re.compile(r"^~【(.*?)】\s*$")

    VARIABLE_PATTERN = re.compile(
        r"^(臨時全域変数|保存変数)\s+"
        r"(\S+)\s*=\s*"
        r'"([^"]*)"'
    )

    TRANSLATABLE_VARS: Set[str] = {
        "スキル名",
        "スキル効果",
        "スキル追加",
        "道具名",
        "道具効果",
        "調合素材",
    }

    CODE_OPEN_BRACKETS: Set[str] = {
        "[", "［", "{", "｛", "<", "＜", "⟨", "⟪", "〈", "《",
    }
    CODE_CLOSE_BRACKETS: Set[str] = {
        "]", "］", "}", "｝", ">", "＞", "⟩", "⟫", "〉", "》",
    }
    BRACKET_PAIRS: Dict[str, str] = {
        "[": "]", "［": "］",
        "{": "}", "｛": "｝",
        "<": ">", "＜": "＞",
        "⟨": "⟩", "⟪": "⟫",
        "〈": "〉", "《": "》",
    }

    SCRIPT_COMMANDS: Set[str] = {
        "スクリプト", "保存変数", "臨時全域変数", "キーダウン", "待機",
        "アウト", "効果音", "絵", "文字", "文字窓", "文字窓0",
        "文字色", "文字陰", "文字進行", "ジャンプ", "栞", "ループ",
        "画面領域", "もし", "ボタン", "変数", "選択", "スクリプト終了",
    }

    # -- Defaults ----------------------------------------------------------

    DEFAULT_LINE_WIDTH = 60
    DEFAULT_MAX_LINES = 3
    ENCODING_CHAIN = (
        "utf-8", "utf-8-sig", "shift_jis", "cp932", "euc-jp", "utf-16",
    )

    # ======================================================================
    # Construction
    # ======================================================================

    def __init__(
        self,
        line_width: int = DEFAULT_LINE_WIDTH,
        max_lines: int = DEFAULT_MAX_LINES,
        exclude_code_only: bool = True,
    ) -> None:
        self._line_width = line_width
        self._max_lines = max_lines
        self._exclude_code_only = exclude_code_only

        # Mutable state reset per operation
        self._current_speaker = ""
        self._code_recovered = 0
        self._code_not_recovered = 0
        self._unrecovered_details: List[str] = []

    def _reset_state(self) -> None:
        """Reset mutable state before an extraction/injection pass."""
        self._current_speaker = ""
        self._code_recovered = 0
        self._code_not_recovered = 0
        self._unrecovered_details = []

    # ======================================================================
    # M3 — Identity
    # ======================================================================

    @property
    def name(self) -> str:  # noqa: D401
        return "LightVN"

    # Patterns that reliably identify a Light VN script.
    _DETECT_PATTERNS: Set[str] = {
        "~【", "~文字", "~ボタン", "~絵", "~効果音", "~選択",
    }
    _DETECT_LINE_PREFIXES: Tuple[str, ...] = ("栞 ",)

    def can_handle(self, file_path: Path) -> bool:
        """Probe whether *file_path* is a Light VN script.

        Heuristic: ``.txt`` file containing Light VN command patterns
        (``~【``, ``~文字``, ``~ボタン``, ``~絵``, ``~効果音``,
        ``~選択``, or ``栞``) anywhere in the file.  The entire file
        is scanned because characteristic patterns may appear late
        (e.g. ``chara_make.txt`` has ``~文字`` only after line 2600).
        """
        if file_path.suffix.lower() != ".txt":
            return False
        try:
            enc = self._detect_encoding_raw(file_path)
            with open(file_path, "r", encoding=enc) as fh:
                for line in fh:
                    if any(p in line for p in self._DETECT_PATTERNS):
                        return True
                    stripped = line.lstrip()
                    if any(stripped.startswith(pfx) for pfx in self._DETECT_LINE_PREFIXES):
                        return True
        except Exception:
            pass
        return False

    # ======================================================================
    # M1 — Extraction
    # ======================================================================

    def extract(self, file_path: Path) -> List[str]:
        """Extract translatable lines (flat list of strings)."""
        tagged = self.extract_tagged(file_path)
        if tagged is None:
            return []
        return [line.text for line in tagged]

    def extract_tagged(self, file_path: Path) -> List[ExtractedLine]:
        """Extract translatable lines with per-line tag and speaker info."""
        self._reset_state()
        enc = self._detect_encoding_raw(file_path)
        try:
            with open(file_path, "r", encoding=enc) as fh:
                content = fh.read()
        except Exception as exc:
            raise ParserError(
                f"Failed to read {file_path}: {exc}",
                parser_name=self.name,
                component="extract",
            ) from exc
        return self._extract_all_tagged(content)

    # ======================================================================
    # M2 — Injection
    # ======================================================================

    def inject(self, file_path: Path, lines: List[str]) -> None:
        """Inject translated lines back into a **copy** of the source file.

        The translated file is written next to the original with a
        ``_translated`` suffix.
        """
        self._reset_state()
        enc = self._detect_encoding_raw(file_path)
        try:
            with open(file_path, "r", encoding=enc) as fh:
                original_content = fh.read()
        except Exception as exc:
            raise ParserError(
                f"Failed to read {file_path}: {exc}",
                parser_name=self.name,
                component="inject",
            ) from exc

        # Build translation dict from the flat list.
        # Extraction order matches: we re-extract to get the keys, then zip.
        keys = self._extract_all_keys(original_content)
        translations: Dict[str, str] = {}
        for key, translated in zip(keys, lines):
            translations[key] = translated

        modified, _removals = self._inject_all(original_content, translations)

        out_path = file_path.with_stem(file_path.stem + "_translated")
        try:
            with open(out_path, "w", encoding=enc) as fh:
                fh.write(modified)
        except Exception as exc:
            raise ParserError(
                f"Failed to write {out_path}: {exc}",
                parser_name=self.name,
                component="inject",
            ) from exc

    # ======================================================================
    # O3 — Encoding detection
    # ======================================================================

    def detect_encoding(self, file_path: Path) -> Optional[str]:
        """Detect file encoding using a priority chain."""
        return self._detect_encoding_raw(file_path)

    def _detect_encoding_raw(self, file_path: Path) -> str:
        for enc in self.ENCODING_CHAIN:
            try:
                with open(file_path, "r", encoding=enc) as fh:
                    fh.read()
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "utf-8"

    # ======================================================================
    # O4 — Speaker detection
    # ======================================================================

    def detect_speakers(self, lines: List[str]) -> Optional[List[SpeakerInfo]]:
        """Detect speakers from extracted lines.

        Parses the ``"Speaker: text"`` format produced by extraction.
        """
        speakers: List[SpeakerInfo] = []
        seen: Set[str] = set()
        for idx, line in enumerate(lines):
            if ": " in line:
                name = line.split(": ", 1)[0]
                if name and name not in seen:
                    speakers.append(SpeakerInfo(name=name, line_idx=idx))
                    seen.add(name)
        return speakers if speakers else None

    # ======================================================================
    # O5 — Wordwrap config
    # ======================================================================

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(
            max_line_length=self._line_width,
            max_line_number=self._max_lines,
            wordwrap_command="\\n",
            new_textbox_injection="\\w",
        )

    def wordwrap_for_tag(self, tag: str) -> Optional[WordwrapConfig]:
        """Tag-specific wrapping: dialogue wraps, others do not."""
        if tag == TAG_DIALOGUE:
            return self.wordwrap_config
        # Menu and variable text should not be wrapped
        return WordwrapConfig(
            max_line_length=0,
            max_line_number=0,
            wordwrap_command="",
            new_textbox_injection="",
        )

    # ======================================================================
    # O6 — Custom wordwrap function
    # ======================================================================

    def wordwrap(
        self, line: str, config: Optional[WordwrapConfig] = None,
    ) -> Optional[List[str]]:
        """Balanced wrapping with orphan avoidance."""
        cfg = config or self.wordwrap_config
        if cfg is None or cfg.max_line_length <= 0:
            return [line] if line else []
        return self._pretty_wrap(line, cfg.max_line_length)

    def pretty_wrap(
        self, text: str, width: int, break_char: str = "\n",
        max_lines: Optional[int] = None,
    ) -> Optional[str]:
        """Engine-specific balanced wrap with orphan avoidance."""
        if width <= 0:
            return text
        lines = self._pretty_wrap(text, width)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
        return break_char.join(lines) if lines else text

    # ======================================================================
    # O7 — Forbidden chars
    # ======================================================================

    @property
    def forbidden_chars(self) -> Optional[ForbiddenChars]:
        return ForbiddenChars(
            characters=["\t", "\r"],
            logit_bias={},
            output_action="replace",
        )

    # ======================================================================
    # O8 — Tag rules
    # ======================================================================

    @property
    def tag_rules(self) -> Optional[TagRules]:
        return TagRules(
            scene_pattern=r"^~スクリプト\s+",
            dialogue_pattern=r'^["\-"]',
            menu_pattern=r"^~?(?:文字窓?0?|ボタン文字)\s+",
            choice_pattern=r"^~選択\s+",
        )

    # ======================================================================
    # Internal — text processing helpers
    # ======================================================================

    @staticmethod
    def _process_dialogue_text(text: str, strip_w: bool = True) -> str:
        """Clean raw dialogue text."""
        lines = text.split("\n")
        cleaned = [ln.strip() for ln in lines if ln.strip()]
        result = "\n".join(cleaned)
        if strip_w:
            result = re.sub(r"\\w+", "", result).strip()
        return result

    @staticmethod
    def _make_dialogue_key(text: str, speaker: str) -> str:
        """Create ``'Speaker: text'`` key."""
        if speaker:
            return f"{speaker}: {text}"
        return text

    @staticmethod
    def _parse_translation(translation: str) -> Tuple[str, str]:
        """Split ``'Speaker: dialogue'`` into ``(speaker, dialogue)``."""
        if ": " in translation:
            parts = translation.split(": ", 1)
            return parts[0], parts[1]
        return "", translation

    # -- Visible length (bracket-aware) ------------------------------------

    def _visible_length(self, text: str) -> int:
        visible = 0
        i = 0
        while i < len(text):
            ch = text[i]
            if ch in self.BRACKET_PAIRS:
                close = self.BRACKET_PAIRS[ch]
                depth = 1
                i += 1
                while i < len(text) and depth > 0:
                    if text[i] == ch:
                        depth += 1
                    elif text[i] == close:
                        depth -= 1
                    i += 1
            else:
                visible += 1
                i += 1
        return visible

    # -- Pretty wrap -------------------------------------------------------

    def _wrap_line_balanced(self, text: str, target: int) -> List[str]:
        if self._visible_length(text) <= target:
            return [text]
        words = text.split()
        if not words:
            return [text] if text else []
        lines: List[str] = []
        cur: List[str] = []
        cur_vl = 0
        for w in words:
            wl = self._visible_length(w)
            if cur and cur_vl + 1 + wl > target:
                lines.append(" ".join(cur))
                cur = [w]
                cur_vl = wl
            else:
                if cur:
                    cur_vl += 1
                cur.append(w)
                cur_vl += wl
        if cur:
            lines.append(" ".join(cur))
        return lines

    def _pretty_wrap(self, text: str, max_width: int | None = None) -> List[str]:
        if max_width is None:
            max_width = self._line_width
        text = text.strip()
        if not text:
            return []
        if self._visible_length(text) <= max_width:
            return [text]
        words = text.split()
        if not words:
            return [text]
        lines = self._wrap_line_balanced(text, max_width)
        if len(lines) > 1:
            avg = sum(self._visible_length(ln) for ln in lines) / len(lines)
            if self._visible_length(lines[-1]) < avg * 0.35:
                vt = self._visible_length(text)
                tw = max((vt + len(lines) - 1) // len(lines), max_width // 2)
                tw = min(tw, max_width)
                new = self._wrap_line_balanced(text, tw)
                if len(new) <= len(lines):
                    na = sum(self._visible_length(ln) for ln in new) / len(new)
                    if self._visible_length(new[-1]) >= na * 0.35:
                        lines = new
        return lines

    def _wrap_for_textbox(
        self, text: str, max_width: int | None = None,
        max_lines: int | None = None,
    ) -> List[List[str]]:
        if max_width is None:
            max_width = self._line_width
        if max_lines is None:
            max_lines = self._max_lines
        all_lines = self._pretty_wrap(text, max_width)
        if len(all_lines) <= max_lines:
            return [all_lines]
        total = len(all_lines)
        num_boxes = (total + max_lines - 1) // max_lines
        base = total // num_boxes
        extra = total % num_boxes
        boxes: List[List[str]] = []
        idx = 0
        for b in range(num_boxes):
            n = base + (1 if b < extra else 0)
            boxes.append(all_lines[idx:idx + n])
            idx += n
        if len(boxes) >= 2 and len(boxes[-1]) == 1:
            last = boxes[-1][0]
            if self._visible_length(last) < max_width // 2:
                combined = " ".join(" ".join(bx) for bx in boxes[-2:])
                cl = self._pretty_wrap(combined, max_width)
                first_half = (len(cl) + 1) // 2
                boxes[-2] = cl[:first_half]
                boxes[-1] = cl[first_half:]
                if not boxes[-1]:
                    boxes.pop()
        return boxes

    @staticmethod
    def _format_textboxes(
        textboxes: List[List[str]], prefix: str,
    ) -> List[str]:
        result: List[str] = []
        for box in textboxes:
            box_text = "\n".join(box)
            result.append(f"{prefix}{box_text}\\w")
        return result

    # -- Menu text detection -----------------------------------------------

    def _is_menu_text_line(self, line: str) -> bool:
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("~//"):
            return False
        stripped_nc = self._strip_conditional_prefix(stripped)
        return bool(re.search(r"~?(?:文字窓?0?|ボタン文字)\s+", stripped_nc))

    @staticmethod
    def _remove_parenthetical_content(text: str) -> str:
        result: List[str] = []
        depth = 0
        for ch in text:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            elif depth == 0:
                result.append(ch)
        return "".join(result)

    def _extract_menu_texts_from_line(self, line: str) -> List[str]:
        cleaned = self._remove_parenthetical_content(line)
        texts: List[str] = []
        for m in re.finditer(r'"([^"]+)"', cleaned):
            t = m.group(1)
            if re.match(r"^{{[^}]+}}$", t):
                continue
            if t.strip().isdigit() or not t.strip():
                continue
            texts.append(t)
        return texts

    # -- Variable assignment detection -------------------------------------

    def _is_variable_assignment_line(self, line: str) -> bool:
        stripped = line.strip()
        if stripped.startswith("//"):
            return False
        stripped = self._strip_conditional_prefix(stripped)
        m = self.VARIABLE_PATTERN.match(stripped)
        if not m:
            return False
        var_name = m.group(2)
        return any(var_name.startswith(tv) for tv in self.TRANSLATABLE_VARS)

    def _extract_variable_text(
        self, line: str,
    ) -> Optional[Tuple[str, str, str]]:
        stripped = self._strip_conditional_prefix(line.strip())
        m = self.VARIABLE_PATTERN.match(stripped)
        if not m:
            return None
        var_type, var_name, text = m.group(1), m.group(2), m.group(3)
        if not text or not text.strip():
            return None
        if re.match(r"^{{[^}]+}}$", text):
            return None
        if text.strip().isdigit():
            return None
        if text.strip() in ("-", ""):
            return None
        return var_type, var_name, text

    # -- Code detection ----------------------------------------------------

    def _is_code_only_text(self, text: str) -> bool:
        if not text or not text.strip():
            return True
        s = text.strip()
        starts = any(s.startswith(b) for b in self.CODE_OPEN_BRACKETS)
        ends = any(s.endswith(b) for b in self.CODE_CLOSE_BRACKETS)
        return starts and ends

    def _is_script_command(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped or stripped.startswith("~"):
            return False
        if stripped.startswith('"') or stripped.startswith('-"'):
            return False
        if stripped.startswith("//"):
            return False
        for cmd in self.SCRIPT_COMMANDS:
            if stripped.startswith(cmd):
                rest = stripped[len(cmd):]
                if cmd == "もし":
                    if rest.lstrip().startswith("("):
                        return True
                    continue
                if cmd == "待機":
                    rs = rest.lstrip()
                    if rs and rs[0].isdigit():
                        return True
                    continue
                if not rest or rest[0].isspace():
                    return True
        return False

    @staticmethod
    def _dialogue_ends_with_marker(dialogue_lines: List[str]) -> bool:
        if not dialogue_lines:
            return False
        return dialogue_lines[-1].strip().endswith("\\w")

    # -- Code segments / recovery ------------------------------------------

    def _extract_code_segments(self, text: str) -> List[str]:
        segments: List[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch in self.BRACKET_PAIRS:
                close = self.BRACKET_PAIRS[ch]
                depth = 1
                start = i
                i += 1
                while i < len(text) and depth > 0:
                    if text[i] == ch:
                        depth += 1
                    elif text[i] == close:
                        depth -= 1
                    i += 1
                if depth == 0:
                    segments.append(text[start:i])
                continue
            i += 1
        return segments

    def _find_bracket_positions(
        self, text: str,
    ) -> List[Tuple[int, int, str]]:
        positions: List[Tuple[int, int, str]] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch in self.BRACKET_PAIRS:
                close = self.BRACKET_PAIRS[ch]
                depth = 1
                start = i
                i += 1
                while i < len(text) and depth > 0:
                    if text[i] == ch:
                        depth += 1
                    elif text[i] == close:
                        depth -= 1
                    i += 1
                if depth == 0:
                    positions.append((start, i, ch))
                continue
            i += 1
        return positions

    def _recover_code_in_translation(
        self, original: str, translation: str, context: str = "",
    ) -> Tuple[str, int, int, List[str]]:
        orig_codes = self._extract_code_segments(original)
        if not orig_codes:
            return translation, 0, 0, []
        recovered = 0
        not_recovered = 0
        details: List[str] = []
        result = translation
        used: Set[int] = set()
        for oc in orig_codes:
            if oc in result:
                continue
            if not oc:
                continue
            ob = oc[0]
            if ob not in self.BRACKET_PAIRS:
                continue
            positions = self._find_bracket_positions(result)
            replaced = False
            for s, e, bt in positions:
                if bt != ob or s in used:
                    continue
                seg = result[s:e]
                if seg in orig_codes:
                    continue
                result = result[:s] + oc + result[e:]
                used.add(s)
                recovered += 1
                replaced = True
                break
            if not replaced:
                not_recovered += 1
                d = f"Code: {oc}"
                if context:
                    d += f" | Context: {context[:80]}..."
                details.append(d)
        return result, recovered, not_recovered, details

    def _make_angle_brackets_safe(
        self, original: str, translation: str,
    ) -> str:
        to = translation.count("<")
        tc = translation.count(">")
        if to == 0 and tc == 0:
            return translation
        oo = original.count("<")
        oc = original.count(">")
        if oo == 0 and oc == 0:
            return translation.replace("<", "＜").replace(">", "＞")
        if to == oo and tc == oc:
            return translation
        # Preserve original angle-code positions
        orig_angle: List[str] = []
        i = 0
        while i < len(original):
            if original[i] == "<":
                depth = 1
                start = i
                i += 1
                while i < len(original) and depth > 0:
                    if original[i] == "<":
                        depth += 1
                    elif original[i] == ">":
                        depth -= 1
                    i += 1
                if depth == 0:
                    orig_angle.append(original[start:i])
                continue
            i += 1
        preserved: Set[int] = set()
        for code in orig_angle:
            idx = 0
            while True:
                pos = translation.find(code, idx)
                if pos == -1:
                    break
                for p in range(pos, pos + len(code)):
                    preserved.add(p)
                idx = pos + 1
        non_angle = {
            k: v for k, v in self.BRACKET_PAIRS.items() if k not in ("<", "＜")
        }
        i = 0
        while i < len(translation):
            ch = translation[i]
            if ch in non_angle:
                close = non_angle[ch]
                depth = 1
                start = i
                i += 1
                while i < len(translation) and depth > 0:
                    if translation[i] == ch:
                        depth += 1
                    elif translation[i] == close:
                        depth -= 1
                    i += 1
                if depth == 0:
                    for p in range(start, i):
                        preserved.add(p)
                continue
            i += 1
        out: List[str] = []
        for i, ch in enumerate(translation):
            if i in preserved:
                out.append(ch)
            elif ch == "<":
                out.append("＜")
            elif ch == ">":
                out.append("＞")
            else:
                out.append(ch)
        return "".join(out)

    # -- Conditional prefix handling ---------------------------------------

    @staticmethod
    def _find_matching_paren(text: str, start: int) -> int:
        if start >= len(text) or text[start] != "(":
            return -1
        depth = 1
        i = start + 1
        while i < len(text) and depth > 0:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        return i - 1 if depth == 0 else -1

    @classmethod
    def _strip_conditional_prefix(cls, line: str) -> str:
        stripped = line.strip()
        while True:
            while stripped.startswith("~"):
                stripped = stripped[1:].lstrip()
            if not stripped.startswith("もし"):
                break
            rest = stripped[2:].lstrip()
            if not rest.startswith("("):
                break
            ci = cls._find_matching_paren(rest, 0)
            if ci == -1:
                break
            stripped = rest[ci + 1:].lstrip()
        return stripped

    @classmethod
    def _extract_conditional_prefix(cls, line: str) -> str:
        stripped = line.strip()
        nc = cls._strip_conditional_prefix(stripped)
        if stripped == nc:
            return ""
        idx = stripped.find(nc)
        return stripped[:idx] if idx > 0 else ""

    @classmethod
    def _has_conditional_prefix(cls, line: str) -> bool:
        stripped = line.strip()
        while stripped.startswith("~"):
            stripped = stripped[1:].lstrip()
        if not stripped.startswith("もし"):
            return False
        rest = stripped[2:].lstrip()
        if not rest.startswith("("):
            return False
        return cls._find_matching_paren(rest, 0) != -1

    # ======================================================================
    # Core extraction (document-order, interleaved)
    # ======================================================================

    def _extract_all_tagged(self, content: str) -> List[ExtractedLine]:
        """Extract all translatable lines in document order with tags.

        Every occurrence is returned, including duplicates.  CherryAI's
        manifest stores per-line entries so deduplication must NOT happen
        here — it is handled later by the Preprocessing step if enabled.
        """
        result: List[ExtractedLine] = []
        lines = content.split("\n")
        in_dialogue = False
        current_dialogue: List[str] = []
        self._current_speaker = ""
        dialogue_speaker = ""

        def _flush_dialogue() -> None:
            nonlocal in_dialogue, current_dialogue
            if in_dialogue and current_dialogue:
                dt = self._process_dialogue_text("\n".join(current_dialogue))
                if dt:
                    key = self._make_dialogue_key(dt, dialogue_speaker)
                    result.append(ExtractedLine(
                        text=key,
                        tag=TAG_DIALOGUE,
                        speaker=dialogue_speaker,
                    ))
                current_dialogue = []
                in_dialogue = False

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            stripped_nc = self._strip_conditional_prefix(stripped)

            # --- Speaker tag ---
            sm = self.SPEAKER_PATTERN.match(stripped)
            if not sm and stripped_nc:
                test = (
                    f"~{stripped_nc}"
                    if not stripped_nc.startswith("~")
                    else stripped_nc
                )
                sm = self.SPEAKER_PATTERN.match(test)
                if not sm and stripped_nc.startswith("【"):
                    sm = re.match(r"^【(.*?)】\s*$", stripped_nc)

            if sm:
                _flush_dialogue()
                self._current_speaker = sm.group(1)
                i += 1
                continue

            # --- Variable assignment ---
            if self._is_variable_assignment_line(stripped):
                _flush_dialogue()
                vr = self._extract_variable_text(stripped)
                if vr:
                    _vt, _vn, text = vr
                    if not (self._exclude_code_only and self._is_code_only_text(text)):
                        result.append(ExtractedLine(
                            text=text, tag=TAG_VARIABLE,
                        ))
                i += 1
                continue

            # --- Menu text ---
            if self._is_menu_text_line(stripped):
                _flush_dialogue()
                for mt in self._extract_menu_texts_from_line(stripped):
                    if self._exclude_code_only and self._is_code_only_text(mt):
                        continue
                    result.append(ExtractedLine(text=mt, tag=TAG_MENU))
                i += 1
                continue

            # --- ~ command (not speaker, not menu, not variable) ---
            if stripped.startswith("~") and not sm:
                if self._has_conditional_prefix(stripped):
                    if stripped_nc.startswith('-"') and in_dialogue and current_dialogue:
                        current_dialogue.append(stripped_nc[2:])
                        i += 1
                        continue
                    if stripped_nc.startswith('"'):
                        _flush_dialogue()
                        in_dialogue = True
                        dialogue_speaker = self._current_speaker
                        current_dialogue.append(stripped_nc[1:])
                        i += 1
                        continue
                _flush_dialogue()
                i += 1
                continue

            # --- Dialogue continuation -" ---
            if stripped.startswith('-"') and in_dialogue and current_dialogue:
                current_dialogue.append(stripped[2:])
                i += 1
                continue

            # --- Dialogue start " ---
            if stripped.startswith('"'):
                _flush_dialogue()
                in_dialogue = True
                dialogue_speaker = self._current_speaker
                current_dialogue.append(stripped[1:])
                i += 1
                continue

            # --- Conditional without ~ prefix ---
            if self._has_conditional_prefix(stripped):
                if stripped_nc.startswith('-"') and in_dialogue and current_dialogue:
                    current_dialogue.append(stripped_nc[2:])
                    i += 1
                    continue
                if stripped_nc.startswith('"'):
                    _flush_dialogue()
                    in_dialogue = True
                    dialogue_speaker = self._current_speaker
                    current_dialogue.append(stripped_nc[1:])
                    i += 1
                    continue

            # --- Dialogue end check ---
            if in_dialogue and current_dialogue:
                ended = self._dialogue_ends_with_marker(current_dialogue)
                is_cmd = self._is_script_command(stripped)
                is_empty = not stripped
                if ended and (is_cmd or is_empty):
                    _flush_dialogue()

            # --- Continue dialogue ---
            if in_dialogue:
                current_dialogue.append(line)
                i += 1
                continue

            i += 1

        # Flush remaining
        _flush_dialogue()

        return result

    def _extract_all_keys(self, content: str) -> List[str]:
        """Extract flat list of keys (used for injection mapping)."""
        return [el.text for el in self._extract_all_tagged(content)]

    # ======================================================================
    # Injection
    # ======================================================================

    def _inject_all(
        self, original_content: str, translations: Dict[str, str],
    ) -> Tuple[str, List[str]]:
        """Inject dialogue, menu, and variable translations."""
        modified, removals = self._inject_dialogue(original_content, translations)
        modified = self._inject_menu_text(modified, translations)
        modified = self._inject_variable_text(modified, translations)
        return modified, removals

    # -- Dialogue injection ------------------------------------------------

    def _inject_dialogue(
        self, original_content: str, translations: Dict[str, str],
    ) -> Tuple[str, List[str]]:
        lines = original_content.split("\n")
        result_lines: List[str] = []
        removals: List[str] = []
        in_dialogue = False
        current_dialogue_lines: List[str] = []
        self._current_speaker = ""
        dialogue_speaker = ""
        speaker_line_idx = -1
        speaker_cond_prefix = ""

        def _process_block() -> None:
            nonlocal in_dialogue, current_dialogue_lines
            if not (in_dialogue and current_dialogue_lines):
                return
            injected, new_sp = self._inject_dialogue_block(
                current_dialogue_lines, translations, removals, dialogue_speaker,
            )
            result_lines.extend(injected)
            if new_sp and speaker_line_idx >= 0:
                if speaker_cond_prefix:
                    if speaker_cond_prefix.rstrip().endswith("~"):
                        result_lines[speaker_line_idx] = (
                            f"{speaker_cond_prefix}【{new_sp}】"
                        )
                    else:
                        result_lines[speaker_line_idx] = (
                            f"{speaker_cond_prefix}~【{new_sp}】"
                        )
                else:
                    result_lines[speaker_line_idx] = f"~【{new_sp}】"
            current_dialogue_lines = []
            in_dialogue = False

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            stripped_nc = self._strip_conditional_prefix(stripped)

            sm = self.SPEAKER_PATTERN.match(stripped)
            if not sm and stripped_nc.startswith("【"):
                test = (
                    f"~{stripped_nc}"
                    if not stripped_nc.startswith("~")
                    else stripped_nc
                )
                sm = self.SPEAKER_PATTERN.match(test)
                if not sm:
                    sm = re.match(r"^【(.*?)】\s*$", stripped_nc)

            if sm:
                _process_block()
                self._current_speaker = sm.group(1)
                speaker_line_idx = len(result_lines)
                speaker_cond_prefix = self._extract_conditional_prefix(stripped)
                result_lines.append(line)
                i += 1
                continue

            if self._has_conditional_prefix(stripped):
                if stripped_nc.startswith('-"') and in_dialogue and current_dialogue_lines:
                    current_dialogue_lines.append(line)
                    i += 1
                    continue
                if stripped_nc.startswith('"'):
                    _process_block()
                    in_dialogue = True
                    dialogue_speaker = self._current_speaker
                    current_dialogue_lines.append(line)
                    i += 1
                    continue
                _process_block()
                result_lines.append(line)
                i += 1
                continue

            if stripped.startswith("~") and not sm:
                _process_block()
                result_lines.append(line)
                i += 1
                continue

            if stripped.startswith('-"') and in_dialogue and current_dialogue_lines:
                current_dialogue_lines.append(line)
                i += 1
                continue

            if stripped.startswith('"'):
                _process_block()
                in_dialogue = True
                dialogue_speaker = self._current_speaker
                current_dialogue_lines.append(line)
                i += 1
                continue

            if in_dialogue:
                current_dialogue_lines.append(line)
                i += 1
                continue

            result_lines.append(line)
            i += 1

        _process_block()
        return "\n".join(result_lines), removals

    def _inject_dialogue_block(
        self,
        dialogue_lines: List[str],
        translations: Dict[str, str],
        removals: List[str],
        speaker: str,
    ) -> Tuple[List[str], str]:
        first = dialogue_lines[0].strip()
        cond_prefix = self._extract_conditional_prefix(first)
        first_nc = self._strip_conditional_prefix(first)

        if first_nc.startswith('-"'):
            d_prefix = '-"'
            first_content = first_nc[2:]
        elif first_nc.startswith('"'):
            d_prefix = '"'
            first_content = first_nc[1:]
        else:
            return dialogue_lines, ""

        full: List[str] = [first_content]
        for dl in dialogue_lines[1:]:
            ls = dl.strip()
            lnc = self._strip_conditional_prefix(ls)
            if lnc.startswith('-"'):
                full.append(lnc[2:])
            else:
                full.append(lnc)

        dt = self._process_dialogue_text("\n".join(full), strip_w=True)
        key = self._make_dialogue_key(dt, speaker)
        translation = translations.get(key, "")

        if not translation and "\n" in dt:
            translation = self._try_combine_line_translations(
                dt, speaker, translations,
            )

        if translation:
            new_sp, translated = self._parse_translation(translation)
            translated, rc, nrc, det = self._recover_code_in_translation(
                dt, translated, f"Dialogue: {dt[:50]}",
            )
            self._code_recovered += rc
            self._code_not_recovered += nrc
            self._unrecovered_details.extend(det)
            translated = self._make_angle_brackets_safe(dt, translated)

            if cond_prefix:
                fmt = self._format_conditional_dialogue(
                    translated, d_prefix, cond_prefix,
                )
            else:
                boxes = self._wrap_for_textbox(translated)
                fmt = self._format_textboxes(boxes, d_prefix)
            return fmt, new_sp

        return dialogue_lines, ""

    def _try_combine_line_translations(
        self, dt: str, speaker: str, translations: Dict[str, str],
    ) -> str:
        lines = dt.split("\n")
        parts: List[str] = []
        combined_sp = ""
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            key = self._make_dialogue_key(ln, speaker)
            t = translations.get(key, "")
            if not t:
                return ""
            sp, dlg = self._parse_translation(t)
            if sp and not combined_sp:
                combined_sp = sp
            parts.append(dlg)
        if parts:
            combined = "\n".join(parts)
            return f"{combined_sp}: {combined}" if combined_sp else combined
        return ""

    @staticmethod
    def _format_conditional_dialogue(
        dialogue: str, d_prefix: str, cond_prefix: str,
    ) -> List[str]:
        lines = dialogue.split("\n")
        result: List[str] = []
        for idx, ln in enumerate(lines):
            ln = ln.strip()
            if not ln:
                continue
            if idx == 0:
                result.append(f'{cond_prefix}"{ln}')
            else:
                result.append(f'{cond_prefix}-"{ln}')
        if result and not result[-1].rstrip().endswith("\\w"):
            result[-1] = result[-1].rstrip() + "\\w"
        return result

    # -- Menu injection ----------------------------------------------------

    def _inject_menu_text(
        self, content: str, translations: Dict[str, str],
    ) -> str:
        lines = content.split("\n")
        out: List[str] = []
        for line in lines:
            if not self._is_menu_text_line(line):
                out.append(line)
                continue
            modified = line
            for m in re.finditer(r'"([^"]+)"', line):
                orig = m.group(1)
                if re.match(r"^{{[^}]+}}$", orig):
                    continue
                if orig.strip().isdigit() or not orig.strip():
                    continue
                t = translations.get(orig, "")
                if t:
                    t, rc, nrc, det = self._recover_code_in_translation(
                        orig, t, f"Menu: {orig[:50]}",
                    )
                    self._code_recovered += rc
                    self._code_not_recovered += nrc
                    self._unrecovered_details.extend(det)
                    t = self._make_angle_brackets_safe(orig, t)
                    modified = modified.replace(f'"{orig}"', f'"{t}"', 1)
            out.append(modified)
        return "\n".join(out)

    # -- Variable injection ------------------------------------------------

    def _inject_variable_text(
        self, content: str, translations: Dict[str, str],
    ) -> str:
        lines = content.split("\n")
        out: List[str] = []
        for line in lines:
            if not self._is_variable_assignment_line(line):
                out.append(line)
                continue
            vr = self._extract_variable_text(line)
            if not vr:
                out.append(line)
                continue
            _vt, _vn, orig = vr
            t = translations.get(orig, "")
            if t:
                t, rc, nrc, det = self._recover_code_in_translation(
                    orig, t, f"Variable {_vn}: {orig[:50]}",
                )
                self._code_recovered += rc
                self._code_not_recovered += nrc
                self._unrecovered_details.extend(det)
                t = self._make_angle_brackets_safe(orig, t)
                out.append(line.replace(f'"{orig}"', f'"{t}"', 1))
            else:
                out.append(line)
        return "\n".join(out)
