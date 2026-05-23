"""Eushully script parser.

Primary flow uses decompiled AGE txt scripts as source of truth:
- extraction: read translatable quoted strings from opcode-filtered txt lines
- injection: rewrite those strings in txt, then assemble back into BIN

Legacy opcode byte-run logic is preserved below for rollback/debug only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Dict, Iterable, List, Optional, Tuple

from .handshake import ExtractedLine, ParserError
from .parser_base import ParserScript, WordwrapConfig


MIN_CHARS_PER_RUN = 8
MAX_BYTES_PER_RUN = 160
MAX_STRING_BYTES = 400
HEADER_SIZE = 0x3C
_MAX_SPEAKER_SCAN_BACK = 0xA0

_SPEAKER_OPCODES = {
    0x0A26,
    0x0A43,
    0x0A79,
    0x0C40,
    0x0C5D,
}

_SPEAKER_ALIASES = {
    (0x0A43, 0x01D5): "Demon king",
    (0x0C5D, 0x01D5): "Syphie",
}

_SPEAKER_NAME_ALIASES = {
    "devil king": "Demon king",
    "demon king": "Demon king",
    "sylphine": "Syphie",
    "sylphine.": "Syphie",
}

_TXT_OPCODE_ALLOWLIST = {
    "set-string",
    "show-text",
    "concat",
    "draw-string",
    "display-furigana",
    "comment",
    "u0041F9C0",
}

_TXT_OPCODE_RE = re.compile(r"^([A-Za-z0-9_\-]+)\b")
_TXT_QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_MOV_GLOBAL_INT_RE = re.compile(r"^mov\s+\(global-int\s+([0-9a-fA-F]+)\)\s+([0-9a-fA-F]+)\s*$")
_SET_GLOBAL_STRING_RE = re.compile(
    r"^set-string\s+\(global-string\s+([0-9a-fA-F]+)\)\s+\"((?:[^\"\\]|\\.)*)\""
)
_LOOKUP_ARRAY_RE = re.compile(
    r"^lookup-array\s+\((local-(?:string-ptr|ptr|int)\s+[0-9a-fA-F]+)\)\s+"
    r"\((global-(?:string|int)\s+[0-9a-fA-F]+)\)\s+(.+)$"
)
_DRAW_LOCAL_STRING_PTR_RE = re.compile(r"\(local-string-ptr\s+([0-9a-fA-F]+)\)")
_WAIT_INPUT_RE = re.compile(r"^wait-for-input\b")
_END_TEXT_LINE_RE = re.compile(r"^end-text-line\b")

# Based on known AGE/Eushully bytecode patterns used by community tools.
# None entries are wildcards. "offset_indices" points to DWORD operands that store
# string pointer values as ((byte_offset - HEADER_SIZE) / 4).
_STRING_ENTRY_PATTERNS = (
    {
        "pattern": (
            0x6E,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0x02,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
        ),
        "offset_indices": (16,),
    },
    {
        "pattern": (
            0xA7,
            0x01,
            0x00,
            0x00,
            0x02,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
        ),
        "offset_indices": (8,),
    },
    {
        "pattern": (
            0x96,
            0x01,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0x02,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
            0x02,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
        ),
        "offset_indices": (16, 24),
    },
    {
        "pattern": (
            0x40,
            0x01,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0x02,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
            0x02,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        "offset_indices": (16, 24),
    },
    {
        "pattern": (
            0x92,
            0x01,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0x02,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
        ),
        "offset_indices": (16,),
    },
    {
        "pattern": (
            0xFE,
            0x07,
            0x00,
            0x00,
            0x02,
            0x00,
            0x00,
            0x00,
            None,
            None,
            None,
            None,
        ),
        "offset_indices": (8,),
    },
)


@dataclass(frozen=True)
class EushullyRun:
    """A printable Shift-JIS byte run inside a binary file."""

    start: int
    end: int
    text: str
    xor_mode: bool = False

    @property
    def byte_length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class EushullyPointerRef:
    """Resolved pointer reference from bytecode to a string offset."""

    pos: int
    opcode: int
    offset: int


@dataclass(frozen=True)
class EushullySpeakerMarker:
    """Speaker state marker command near dialogue."""

    pos: int
    opcode: int
    arg: int


@dataclass(frozen=True)
class TxtStringUnit:
    """Quoted text unit found in a decompiled AGE txt script."""

    opcode: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class TxtDialogueUnit:
    """Extracted textbox unit with one or more quoted segments."""

    text: str
    segments: Tuple[TxtStringUnit, ...]
    speaker: Optional[str] = None


class EushullyParser(ParserScript):
    """Parser for loose Eushully ``.BIN`` script resources."""

    @property
    def name(self) -> str:
        return "Eushully"

    @property
    def display_name(self) -> str:
        return "Eushully BIN"

    @property
    def tooltip(self) -> str:
        return (
            "Extracts opcode-filtered quoted strings from Eushully AGE txt scripts "
            "and assembles edited txt back into .BIN."
        )

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(max_line_length=42, max_line_number=3, wordwrap_command="\\n")

    @property
    def size_whitelist_suffixes(self) -> List[str]:
        return [".bin"]

    def can_handle(self, file_path: Path) -> bool:
        if not file_path.exists() or file_path.suffix.lower() != ".bin":
            return False
        try:
            header = file_path.read_bytes()[:16]
        except OSError:
            return False
        # Typical AGE script container marker in Himegari scenario resources.
        return header.startswith(b"SYS4422") or file_path.name.upper().startswith("SC")

    def detect_encoding(self, file_path: Path) -> Optional[str]:
        return "cp932"

    def extract(self, file_path: Path) -> List[str]:
        tagged = self.extract_tagged(file_path) or []
        return [line.text for line in tagged]

    def extract_tagged(self, file_path: Path) -> Optional[List[ExtractedLine]]:
        seeded_strings = self._load_name_seed_strings(file_path)
        txt_path = self._ensure_txt_for_bin(file_path)
        units: List[TxtDialogueUnit] = []
        if txt_path is not None:
            content = txt_path.read_text(encoding="utf-8", errors="ignore")
            units = self._collect_txt_dialogue_units(content, seeded_strings=seeded_strings)
            if not units:
                units = self._collect_flat_txt_units(content)

        if not units:
            # Old binary opcode extraction fallback for non-decompilable test fixtures.
            data = file_path.read_bytes()
            runs = self._extract_pointer_runs(data, assemble_dialogue=True)
            if not runs:
                runs = self._scan_runs(data)
            units = [
                TxtDialogueUnit(
                    text=run.text,
                    segments=(
                        TxtStringUnit(
                            opcode="legacy",
                            start=run.start,
                            end=run.end,
                            text=run.text,
                        ),
                    ),
                    speaker=None,
                )
                for run in runs
            ]

        return [
            ExtractedLine(text=unit.text, tag="dialogue", ln=index + 1)
            for index, unit in enumerate(units)
        ]

    def inject(self, file_path: Path, lines: List[str]) -> None:
        translated_path = file_path.with_stem(file_path.stem + "_translated")
        self.inject_to(file_path, translated_path, lines)

    def inject_to(
        self,
        source_path: Path,
        output_path: Path,
        lines: List[str],
        *,
        orig_lines: Optional[List[str]] = None,
    ) -> List[int]:
        seeded_strings = self._load_name_seed_strings(source_path)
        txt_path = self._ensure_txt_for_bin(source_path)
        if txt_path is None:
            return self._inject_legacy_binary(source_path, output_path, lines, orig_lines=orig_lines)

        txt_content = txt_path.read_text(encoding="utf-8", errors="ignore")
        units = self._collect_txt_dialogue_units(txt_content, seeded_strings=seeded_strings)
        if not units:
            units = self._collect_flat_txt_units(txt_content)
        if not units:
            return self._inject_legacy_binary(source_path, output_path, lines, orig_lines=orig_lines)
        search_keys = orig_lines if orig_lines is not None else [unit.text for unit in units]

        failures: List[int] = []
        replacements: list[tuple[int, int, str]] = []
        for index, translated in enumerate(lines):
            if index >= len(units):
                failures.append(index)
                continue

            source_text = search_keys[index] if index < len(search_keys) else units[index].text
            if translated == source_text:
                continue

            unit = units[index]
            replacement_text = translated
            if unit.speaker is not None:
                speaker_prefix = f"{unit.speaker}: "
                if replacement_text.startswith(speaker_prefix):
                    replacement_text = replacement_text[len(speaker_prefix) :]

            segments = self._split_text_for_segments(replacement_text, unit)
            for segment, part in zip(unit.segments, segments):
                escaped = self._escape_txt_string(part)
                replacements.append((segment.start, segment.end, escaped))

        if failures:
            return failures

        for start, end, value in sorted(replacements, key=lambda item: item[0], reverse=True):
            txt_content = txt_content[:start] + value + txt_content[end:]

        temp_txt = output_path.with_suffix(".txt")
        temp_txt.parent.mkdir(parents=True, exist_ok=True)
        try:
            temp_txt.write_text(txt_content, encoding="utf-8")
        except OSError as exc:
            raise ParserError(
                f"Failed to write intermediate txt file {temp_txt}: {exc}",
                parser_name=self.name,
                component="inject_to",
            ) from exc

        self._assemble_txt_to_bin(temp_txt, output_path)
        return failures

    def _ensure_txt_for_bin(self, bin_path: Path) -> Optional[Path]:
        txt_path = bin_path.with_suffix(".txt")
        if txt_path.exists():
            return txt_path

        exe = self._decompiler_exe_path()
        try:
            subprocess.run(
                [str(exe), "-d", str(bin_path), str(txt_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, OSError):
            return None
        return txt_path

    def _assemble_txt_to_bin(self, txt_path: Path, output_bin_path: Path) -> None:
        exe = self._decompiler_exe_path()
        output_bin_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [str(exe), "-a", str(txt_path), str(output_bin_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            raise ParserError(
                f"Failed to assemble {txt_path} into {output_bin_path} via {exe}: {exc}",
                parser_name=self.name,
                component="_assemble_txt_to_bin",
            ) from exc

    @staticmethod
    def _collect_flat_txt_units(content: str) -> List[TxtDialogueUnit]:
        units: List[TxtStringUnit] = []
        cursor = 0
        for line in content.splitlines(keepends=True):
            stripped = line.strip()
            op_match = _TXT_OPCODE_RE.match(stripped)
            if not op_match:
                cursor += len(line)
                continue

            opcode = op_match.group(1)
            if opcode not in _TXT_OPCODE_ALLOWLIST:
                cursor += len(line)
                continue

            for quoted in _TXT_QUOTED_RE.finditer(line):
                raw = quoted.group(1)
                decoded = EushullyParser._decode_txt_string(raw)
                if decoded:
                    units.append(
                        TxtStringUnit(
                            opcode=opcode,
                            start=cursor + quoted.start(1),
                            end=cursor + quoted.end(1),
                            text=decoded,
                        )
                    )
            cursor += len(line)
        return [TxtDialogueUnit(text=unit.text, segments=(unit,), speaker=None) for unit in units]

    def _collect_txt_dialogue_units(
        self,
        content: str,
        *,
        seeded_strings: Optional[Dict[int, str]] = None,
    ) -> List[TxtDialogueUnit]:
        units: List[TxtDialogueUnit] = []
        global_ints: Dict[int, int] = {}
        global_strings: Dict[int, str] = dict(seeded_strings or {})
        local_ptrs: Dict[int, int] = {}
        local_ints: Dict[int, int] = {}
        local_string_ptrs: Dict[int, str] = {}

        current_speaker: Optional[str] = None
        current_parts: List[str] = []
        current_segments: List[TxtStringUnit] = []
        line_open = False
        cursor = 0

        for line in content.splitlines(keepends=True):
            stripped = line.strip()

            mov_match = _MOV_GLOBAL_INT_RE.match(stripped)
            if mov_match:
                key = self._parse_hex_number(mov_match.group(1))
                value = self._parse_hex_number(mov_match.group(2))
                global_ints[key] = value
                cursor += len(line)
                continue

            set_match = _SET_GLOBAL_STRING_RE.match(stripped)
            if set_match:
                key = self._parse_hex_number(set_match.group(1))
                global_strings[key] = self._decode_txt_string(set_match.group(2))
                cursor += len(line)
                continue

            lookup_match = _LOOKUP_ARRAY_RE.match(stripped)
            if lookup_match:
                self._resolve_lookup_array(
                    lookup_match.group(1),
                    lookup_match.group(2),
                    lookup_match.group(3),
                    global_ints,
                    global_strings,
                    local_ints,
                    local_ptrs,
                    local_string_ptrs,
                )
                cursor += len(line)
                continue

            if stripped.startswith("draw-string"):
                draw_match = _DRAW_LOCAL_STRING_PTR_RE.search(stripped)
                if draw_match:
                    ptr_id = self._parse_hex_number(draw_match.group(1))
                    speaker_text = local_string_ptrs.get(ptr_id)
                    if speaker_text:
                        current_speaker = self._normalize_speaker_name(speaker_text)
                cursor += len(line)
                continue

            show_match = _TXT_OPCODE_RE.match(stripped)
            if show_match and show_match.group(1) == "show-text":
                quoted = _TXT_QUOTED_RE.search(line)
                if quoted:
                    raw = quoted.group(1)
                    text = self._decode_txt_string(raw)
                    current_segments.append(
                        TxtStringUnit(
                            opcode="show-text",
                            start=cursor + quoted.start(1),
                            end=cursor + quoted.end(1),
                            text=text,
                        )
                    )
                    self._append_dialogue_fragment(current_parts, text, line_open)
                    line_open = True
                cursor += len(line)
                continue

            if _END_TEXT_LINE_RE.match(stripped):
                if current_parts:
                    line_open = False
                cursor += len(line)
                continue

            if _WAIT_INPUT_RE.match(stripped):
                if current_segments:
                    text = "".join(current_parts).strip()
                    if text:
                        if current_speaker is not None:
                            text = f"{current_speaker}: {text}"
                        units.append(
                            TxtDialogueUnit(
                                text=text,
                                segments=tuple(current_segments),
                                speaker=current_speaker,
                            )
                        )
                current_parts = []
                current_segments = []
                line_open = False
                cursor += len(line)
                continue

            cursor += len(line)

        if current_segments:
            text = "".join(current_parts).strip()
            if text:
                if current_speaker is not None:
                    text = f"{current_speaker}: {text}"
                units.append(
                    TxtDialogueUnit(
                        text=text,
                        segments=tuple(current_segments),
                        speaker=current_speaker,
                    )
                )

        return units

    @staticmethod
    def _decode_txt_string(text: str) -> str:
        if "\\" not in text:
            return text

        out: List[str] = []
        idx = 0
        while idx < len(text):
            char = text[idx]
            if char != "\\" or idx + 1 >= len(text):
                out.append(char)
                idx += 1
                continue

            token = text[idx + 1]
            if token == "n":
                out.append("\n")
            elif token == "r":
                out.append("\r")
            elif token == "t":
                out.append("\t")
            elif token == '"':
                out.append('"')
            elif token == "\\":
                out.append("\\")
            else:
                out.append("\\")
                out.append(token)
            idx += 2

        return "".join(out)

    @staticmethod
    def _escape_txt_string(text: str) -> str:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        escaped = escaped.replace("\n", "\\n").replace("\r", "")
        return escaped

    def _split_text_for_segments(self, translated: str, unit: TxtDialogueUnit) -> List[str]:
        segment_count = len(unit.segments)
        if segment_count <= 1:
            return [translated]

        parts = translated.split("\n")
        if len(parts) == segment_count:
            return parts

        compact = translated.replace("\n", " ").strip()
        if not compact:
            return [""] * segment_count

        words = compact.split()
        if len(words) <= segment_count:
            return words + ([""] * (segment_count - len(words)))

        target_lengths = [max(len(seg.text), 1) for seg in unit.segments]
        total_target = sum(target_lengths)
        output: List[str] = []
        used_words = 0

        for index, target in enumerate(target_lengths):
            remaining_segments = segment_count - index
            remaining_words = len(words) - used_words
            if remaining_segments == 1:
                chunk_words = words[used_words:]
            else:
                ratio = target / total_target if total_target else 1 / segment_count
                chunk_size = max(1, round(len(words) * ratio))
                max_chunk = remaining_words - (remaining_segments - 1)
                chunk_size = min(chunk_size, max_chunk)
                chunk_words = words[used_words : used_words + chunk_size]
            output.append(" ".join(chunk_words))
            used_words += len(chunk_words)

        return output

    def _inject_legacy_binary(
        self,
        source_path: Path,
        output_path: Path,
        lines: List[str],
        *,
        orig_lines: Optional[List[str]],
    ) -> List[int]:
        data = bytearray(source_path.read_bytes())
        runs = self._extract_pointer_runs(bytes(data), assemble_dialogue=False)
        if not runs:
            runs = self._scan_runs(bytes(data))
        search_keys = orig_lines if orig_lines is not None else [run.text for run in runs]

        failures: List[int] = []
        for index, translated in enumerate(lines):
            if index >= len(runs):
                failures.append(index)
                continue

            source_text = search_keys[index] if index < len(search_keys) else runs[index].text
            if translated == source_text:
                continue

            run = runs[index]
            try:
                encoded = translated.encode("cp932")
            except UnicodeEncodeError:
                failures.append(index)
                continue

            if len(encoded) > run.byte_length:
                failures.append(index)
                continue

            if run.xor_mode:
                encoded = bytes((byte ^ 0xFF) for byte in encoded)
                padded = encoded + (b"\xFF" * (run.byte_length - len(encoded)))
            else:
                padded = encoded + (b" " * (run.byte_length - len(encoded)))
            data[run.start:run.end] = padded

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            output_path.write_bytes(data)
        except OSError as exc:
            raise ParserError(
                f"Failed to write injected file {output_path}: {exc}",
                parser_name=self.name,
                component="inject_to",
            ) from exc

        return failures

    @staticmethod
    def _normalize_speaker_name(name: str) -> str:
        stripped = name.strip()
        key = stripped.lower()
        return _SPEAKER_NAME_ALIASES.get(key, stripped)

    @staticmethod
    def _append_dialogue_fragment(parts: List[str], fragment: str, line_open: bool) -> None:
        if not parts:
            parts.append(fragment)
            return

        previous = parts[-1]
        if previous.endswith("-") and fragment[:1].isascii() and fragment[:1].isalpha():
            parts[-1] = previous[:-1] + fragment
            return
        if line_open:
            parts[-1] = previous + fragment
            return
        if fragment.startswith(("。", "、", "」", "』", ",", ".", "!", "?", ":", ";")):
            parts[-1] = previous + fragment
            return
        parts[-1] = previous.rstrip() + " " + fragment.lstrip()

    def _resolve_lookup_array(
        self,
        target_expr: str,
        source_expr: str,
        index_expr: str,
        global_ints: Dict[int, int],
        global_strings: Dict[int, str],
        local_ints: Dict[int, int],
        local_ptrs: Dict[int, int],
        local_string_ptrs: Dict[int, str],
    ) -> None:
        target_kind, target_id = self._parse_typed_expr(target_expr)
        source_kind, source_id = self._parse_typed_expr(source_expr)
        index_value = self._resolve_value(index_expr, global_ints, local_ints, local_ptrs)
        if index_value is None:
            return

        if source_kind == "global-int":
            value = global_ints.get(source_id + index_value)
            if value is None:
                return
            if target_kind == "local-ptr":
                local_ptrs[target_id] = value
            elif target_kind == "local-int":
                local_ints[target_id] = value
            return

        if source_kind == "global-string" and target_kind == "local-string-ptr":
            value = global_strings.get(source_id + index_value)
            if value is not None:
                local_string_ptrs[target_id] = value

    @staticmethod
    def _parse_typed_expr(expr: str) -> tuple[str, int]:
        cleaned = expr.strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = cleaned[1:-1].strip()
        parts = cleaned.split()
        if len(parts) != 2:
            raise ValueError(f"Unsupported expression: {expr}")
        return parts[0], EushullyParser._parse_hex_number(parts[1])

    @staticmethod
    def _resolve_value(
        expr: str,
        global_ints: Dict[int, int],
        local_ints: Dict[int, int],
        local_ptrs: Dict[int, int],
    ) -> Optional[int]:
        token = expr.strip()
        try:
            return EushullyParser._parse_hex_number(token)
        except ValueError:
            pass

        if not (token.startswith("(") and token.endswith(")")):
            return None
        kind, key = EushullyParser._parse_typed_expr(token)
        if kind == "global-int":
            return global_ints.get(key)
        if kind == "local-int":
            return local_ints.get(key)
        if kind == "local-ptr":
            return local_ptrs.get(key)
        return None

    @staticmethod
    def _parse_hex_number(token: str) -> int:
        cleaned = token.strip()
        return int(cleaned, 16)

    def _load_name_seed_strings(self, source_path: Path) -> Dict[int, str]:
        if source_path.name.upper().endswith("CNINIT.BIN"):
            return {}

        candidates = sorted(source_path.parent.glob("*CNINIT*.txt"))
        if not candidates:
            bin_candidates = sorted(source_path.parent.glob("*CNINIT*.BIN"))
            for bin_path in bin_candidates:
                txt_path = self._ensure_txt_for_bin(bin_path)
                if txt_path is not None:
                    candidates.append(txt_path)

        if not candidates:
            return {}

        seeds: Dict[int, str] = {}
        for txt_path in candidates:
            try:
                content = txt_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in content.splitlines():
                match = _SET_GLOBAL_STRING_RE.match(line.strip())
                if not match:
                    continue
                key = self._parse_hex_number(match.group(1))
                seeds[key] = self._decode_txt_string(match.group(2))
        return seeds

    @staticmethod
    def _decompiler_exe_path() -> Path:
        return Path("dev") / "Eushully-Decompiler-master" / "x64" / "Release" / "Decompiler.exe"

    def _scan_runs(self, data: bytes) -> List[EushullyRun]:
        runs: List[EushullyRun] = []
        idx = 0
        length = len(data)

        while idx < length:
            start = idx
            cursor = idx
            chars = 0

            while cursor < length:
                byte = data[cursor]
                if 0x20 <= byte <= 0x7E:
                    chars += 1
                    cursor += 1
                    continue
                if self._is_shift_jis_pair(data, cursor):
                    chars += 1
                    cursor += 2
                    continue
                break

            byte_len = cursor - start
            if chars >= MIN_CHARS_PER_RUN and 0 < byte_len <= MAX_BYTES_PER_RUN:
                payload = data[start:cursor]
                try:
                    text = payload.decode("cp932").strip()
                except UnicodeDecodeError:
                    text = ""
                if text:
                    runs.append(EushullyRun(start=start, end=cursor, text=text))

            idx = cursor + 1 if cursor > start else idx + 1

        return runs

    def _extract_pointer_runs(self, data: bytes, *, assemble_dialogue: bool) -> List[EushullyRun]:
        refs = self._collect_string_pointer_refs(data)
        if not refs:
            return []

        runs_by_ref: List[tuple[EushullyPointerRef, EushullyRun]] = []
        for ref in refs:
            run = self._decode_pointer_string(data, ref.offset)
            if run is not None:
                runs_by_ref.append((ref, run))

        if not assemble_dialogue:
            seen: set[int] = set()
            runs: List[EushullyRun] = []
            for _, run in runs_by_ref:
                if run.start in seen:
                    continue
                seen.add(run.start)
                runs.append(run)
            runs.sort(key=lambda item: item.start)
            return runs

        return self._assemble_dialogue_runs(data, runs_by_ref)

    def _collect_string_pointer_refs(self, data: bytes) -> List[EushullyPointerRef]:
        refs: List[EushullyPointerRef] = []
        if len(data) <= HEADER_SIZE:
            return refs

        for pos in range(HEADER_SIZE, len(data) - 4, 4):
            for entry in _STRING_ENTRY_PATTERNS:
                pattern = entry["pattern"]
                if pos + len(pattern) > len(data):
                    continue
                if not self._matches_pattern(data, pos, pattern):
                    continue
                for rel in entry["offset_indices"]:
                    ptr_pos = pos + rel
                    ptr = int.from_bytes(data[ptr_pos : ptr_pos + 4], "little", signed=False)
                    string_pos = HEADER_SIZE + (ptr * 4)
                    if HEADER_SIZE <= string_pos < len(data):
                        refs.append(
                            EushullyPointerRef(pos=pos, opcode=data[pos], offset=string_pos)
                        )
        return refs

    def _assemble_dialogue_runs(
        self,
        data: bytes,
        runs_by_ref: List[tuple[EushullyPointerRef, EushullyRun]],
    ) -> List[EushullyRun]:
        assembled: List[EushullyRun] = []
        cursor = 0
        while cursor < len(runs_by_ref):
            ref, run = runs_by_ref[cursor]
            if ref.opcode != 0x6E:
                assembled.append(run)
                cursor += 1
                continue

            group: List[EushullyRun] = [run]
            next_cursor = cursor + 1
            while next_cursor < len(runs_by_ref):
                prev_ref, _ = runs_by_ref[next_cursor - 1]
                next_ref, next_run = runs_by_ref[next_cursor]
                if next_ref.opcode != 0x6E:
                    break
                if not self._can_merge_dialogue_refs(data, prev_ref.pos, next_ref.pos):
                    break
                group.append(next_run)
                next_cursor += 1

            merged_text = self._join_dialogue_fragments([item.text for item in group])
            marker = self._find_preceding_speaker_marker(data, ref.pos)
            if marker is not None:
                speaker = self._format_speaker_label(marker)
                merged_text = f"{speaker}: {merged_text}"

            assembled.append(
                EushullyRun(
                    start=group[0].start,
                    end=group[-1].end,
                    text=merged_text,
                    xor_mode=group[0].xor_mode,
                )
            )
            cursor = next_cursor

        return assembled

    @staticmethod
    def _can_merge_dialogue_refs(data: bytes, prev_pos: int, next_pos: int) -> bool:
        gap = next_pos - prev_pos
        if gap <= 0 or gap > 0x24:
            return False
        tail_opcode_pos = prev_pos + 20
        if tail_opcode_pos + 4 > len(data):
            return False
        tail_opcode = int.from_bytes(data[tail_opcode_pos : tail_opcode_pos + 4], "little")
        if tail_opcode not in (0x6F, 0x70):
            return False

        start = prev_pos + 20
        if next_pos <= start:
            return True
        for pos in range(start, next_pos, 4):
            opcode = int.from_bytes(data[pos : pos + 4], "little", signed=False)
            if opcode in (0x71, 0x72):
                return False
        return True

    @staticmethod
    def _join_dialogue_fragments(fragments: List[str]) -> str:
        if not fragments:
            return ""
        joined = fragments[0].strip()
        for fragment in fragments[1:]:
            current = fragment.strip()
            if not current:
                continue
            if joined.endswith("-") and current[:1].isascii() and current[:1].isalpha():
                joined = joined[:-1] + current
                continue
            if current.startswith(("。", "、", "」", "』", ",", ".", "!", "?", ":", ";")):
                joined += current
                continue
            joined += f" {current}"
        return joined.strip()

    def _find_preceding_speaker_marker(
        self,
        data: bytes,
        command_pos: int,
    ) -> Optional[EushullySpeakerMarker]:
        start = max(HEADER_SIZE, command_pos - _MAX_SPEAKER_SCAN_BACK)
        pos = command_pos - 4
        while pos >= start:
            opcode = int.from_bytes(data[pos : pos + 4], "little", signed=False)
            if opcode in _SPEAKER_OPCODES:
                arg = int.from_bytes(data[pos + 4 : pos + 8], "little", signed=False)
                return EushullySpeakerMarker(pos=pos, opcode=opcode, arg=arg)
            if opcode in (0x6E, 0x71, 0x72):
                return None
            pos -= 4
        return None

    @staticmethod
    def _format_speaker_label(marker: EushullySpeakerMarker) -> str:
        alias = _SPEAKER_ALIASES.get((marker.opcode, marker.arg))
        if alias:
            return alias
        return f"SPK[{marker.opcode:04X}:{marker.arg:04X}]"

    @staticmethod
    def _matches_pattern(data: bytes, pos: int, pattern: Iterable[Optional[int]]) -> bool:
        for idx, expected in enumerate(pattern):
            if expected is None:
                continue
            if data[pos + idx] != expected:
                return False
        return True

    def _decode_pointer_string(self, data: bytes, offset: int) -> Optional[EushullyRun]:
        plain = self._decode_string_variant(data, offset, xor_mode=False)
        xor_ff = self._decode_string_variant(data, offset, xor_mode=True)

        candidates = [item for item in (plain, xor_ff) if item is not None]
        if not candidates:
            return None

        return max(candidates, key=lambda item: self._decode_variant_score(item.text, item.xor_mode))

    def _decode_string_variant(
        self,
        data: bytes,
        offset: int,
        *,
        xor_mode: bool,
    ) -> Optional[EushullyRun]:
        if offset < 0 or offset >= len(data):
            return None

        cursor = offset
        raw = bytearray()
        while cursor < len(data) and len(raw) < MAX_STRING_BYTES:
            if xor_mode:
                if cursor + 1 < len(data) and data[cursor] == 0xFF and data[cursor + 1] == 0xFF:
                    break
                raw.append(data[cursor] ^ 0xFF)
                cursor += 1
                continue

            if data[cursor] == 0x00:
                break
            raw.append(data[cursor])
            cursor += 1

        if not raw:
            return None

        try:
            text = bytes(raw).decode("cp932").strip()
        except UnicodeDecodeError:
            return None

        return EushullyRun(start=offset, end=cursor, text=text, xor_mode=xor_mode)

    @staticmethod
    def _decode_variant_score(text: str, xor_mode: bool) -> float:
        if not text:
            return -1.0
        printable = sum(ch.isprintable() for ch in text) / len(text)
        # Prefer longer, mostly printable payloads; XOR mode gets a tiny nudge because
        # AGE strings are usually XOR-FF terminated.
        return (len(text) * 0.01) + printable + (0.02 if xor_mode else 0.0)

    @staticmethod
    def _is_shift_jis_pair(data: bytes, offset: int) -> bool:
        if offset + 1 >= len(data):
            return False
        lead = data[offset]
        trail = data[offset + 1]
        if not ((0x81 <= lead <= 0x9F) or (0xE0 <= lead <= 0xFC)):
            return False
        return (0x40 <= trail <= 0x7E) or (0x80 <= trail <= 0xFC)

