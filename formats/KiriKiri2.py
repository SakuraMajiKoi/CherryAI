"""KiriKiri2 parser for scenario scripts and menu captions.

Supports:
- ``.ks`` scenario extraction/injection using block-based parsing.
- ``Menus.tjs`` caption extraction/injection preserving accelerator suffixes.
- Optional project-level ``MainWindow.tjs`` wordwrap patching.
"""

from __future__ import annotations

import codecs
import json
import re
import struct
import zlib
from enum import IntEnum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .handshake import ExtractedLine, SpeakerInfo
from .parser_base import ParserScript, WordwrapConfig


KS_ENCODING_CANDIDATES: Tuple[str, ...] = ("cp932", "shift_jis", "utf-8")
MENU_ENCODING_CANDIDATES: Tuple[str, ...] = ("utf-8-sig", "utf-8", "cp932", "shift_jis")
JAPANESE_RE = re.compile(
    r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF々〆ヵヶ"
    r"\u3041-\u3096\u309D-\u309F"
    r"\u30A1-\u30FA\u30FD-\u30FF\u31F0-\u31FF\uFF66-\uFF9Fー]"
)
COMMENT_RE = re.compile(r"^\s*;")
LABEL_RE = re.compile(r"^\s*\*")
AT_COMMAND_RE = re.compile(r"^\s*@")
TAG_RE = re.compile(r"^\s*\[[^\]]*\]\s*$")
BRACE_COMMAND_RE = re.compile(r"^\s*\{[^{}]*\}\s*$")
SPEAKER_RE = re.compile(r"^\s*【(?P<speaker>[^】]+)】(?:\[(?P<voice_id>[^\]]+)\])?\s*$")
NAME_TAG_RE = re.compile(r'\[name\s+text\s*=\s*"([^"]+)"\]')
STRING_LITERAL_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
NEW_KAG_MENU_ITEM_RE = re.compile(r"new\s+KAGMenuItem\s*\(", re.IGNORECASE)
NEW_MENU_ITEM_RE = re.compile(r"new\s+MenuItem\s*\(", re.IGNORECASE)
PROCESS_CH_RE = re.compile(r"if\s*\(\s*current\.processCh\(\s*text\s*\)\s*\)\s*\{")
XP3_MAGIC = b"XP3\r\n \n\x1a\x8bg\x01"
XP3_SCAN_LIMIT = 4 * 1024 * 1024
XP3_FILE_PROTECTED = 1 << 31
CXDEC_CONTROL_BLOCK_SIGNATURE = b" Encryption control block"

SOFT_BRIDGE_KINDS = {"tag", "brace_command", "at_command"}
HARD_BREAK_KINDS = {"blank", "comment", "label"}

_WRAP_VARS_SNIPPET = """
\tvar wrapNum = 0; // wordwrapping word counter
\tvar wrapPos = 0; // wordwrapping length
\tvar oldLine = void; // wordwrapping comparison line
\tvar splitLine = void; // wordwrapping split text variable
\tvar breakWrap = 0; // wrapping flag during check
\tvar newPage = 0; // wrapping flag for new page
"""

_WRAP_BLOCK_SNIPPET = r"""
\t\t/* Wordwrapping code (auto line breaks)
\t\t   Simplified port, measures tokens and inserts line breaks when needed. */
\t\tif(oldLine != conductor.curLineStr) {
\t\t\tvar tempStr = "";
\t\t\toldLine = conductor.curLineStr;
\t\t\twrapNum = 0;
\t\t\twrapPos = 0;
\t\t\tbreakWrap = 0;
\t\t\tnewPage = 0;
\t\t}
"""


def _read_text(path: Path, candidates: Sequence[str]) -> Tuple[str, str]:
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig"), "utf-8-sig"
    if data.startswith(codecs.BOM_UTF16_LE):
        return data.decode("utf-16"), "utf-16"
    if data.startswith(codecs.BOM_UTF16_BE):
        return data.decode("utf-16"), "utf-16"
    for encoding in candidates:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode(candidates[0], errors="replace"), candidates[0]


def _write_text(path: Path, text: str, encoding: str) -> None:
    if encoding == "utf-8-sig":
        path.write_bytes(codecs.BOM_UTF8 + text.encode("utf-8"))
        return
    path.write_text(text, encoding=encoding, newline="")


def _split_line_ending(line: str) -> Tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


@dataclass(slots=True)
class ClassifiedLine:
    number: int
    text: str
    newline: str
    kind: str
    speaker: str = ""
    voice_id: str = ""


@dataclass(slots=True)
class PendingSpeaker:
    speaker: str
    voice_id: str = ""
    bridge_code_lines: List[Tuple[int, str, str]] = field(default_factory=list)


@dataclass(slots=True)
class KsBlock:
    file_path: str
    block_id: str
    tag: str
    speaker: str
    voice_id: str
    start_line: int
    end_line: int
    text_line_numbers: List[int] = field(default_factory=list)
    source_text_lines: List[str] = field(default_factory=list)
    bridge_code_lines: List[Tuple[int, str, str]] = field(default_factory=list)

    @property
    def joined_text(self) -> str:
        return "\n".join(self.source_text_lines)


@dataclass(slots=True)
class MenuLiteral:
    line_index: int
    start: int
    end: int
    left_text: str
    delimiter: str
    suffix: str


@dataclass(slots=True)
class MenuEntry:
    text: str
    line_index: int
    literal_index: int


@dataclass(slots=True)
class Xp3Segment:
    flags: int
    offset: int
    original_size: int
    packed_size: int


@dataclass(slots=True)
class Xp3Entry:
    name: str
    flags: int
    original_size: int
    packed_size: int
    file_hash: int
    segments: List[Xp3Segment] = field(default_factory=list)


@dataclass(slots=True)
class Xp3ArchiveSettings:
    custom_magic: str = ""
    header_offset: int = 0
    key: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "custom_magic": self.custom_magic,
            "header_offset": int(self.header_offset),
            "key": self.key,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, object]]) -> "Xp3ArchiveSettings":
        if not data:
            return cls()
        header_offset = 0
        try:
            header_offset = int(data.get("header_offset", 0))
        except (TypeError, ValueError):
            header_offset = 0
        return cls(
            custom_magic=str(data.get("custom_magic", "") or ""),
            header_offset=max(0, header_offset),
            key=str(data.get("key", "") or ""),
        )


@dataclass(slots=True)
class CxdecSettings:
    mask: int
    offset: int
    prolog_order: Tuple[int, ...]
    odd_branch_order: Tuple[int, ...]
    even_branch_order: Tuple[int, ...]
    control_block: Optional[Tuple[int, ...]] = None
    tpm: str = ""


class _CxOpcode(IntEnum):
    NOP = 0
    RETN = 1
    MOV_EDI_ARG = 2
    PUSH_EBX = 3
    POP_EBX = 4
    PUSH_ECX = 5
    POP_ECX = 6
    MOV_EAX_EBX = 7
    MOV_EBX_EAX = 8
    MOV_ECX_EBX = 9
    MOV_EAX_CONTROL_BLOCK = 10
    MOV_EAX_EDI = 11
    MOV_EAX_INDIRECT = 12
    ADD_EAX_EBX = 13
    SUB_EAX_EBX = 14
    IMUL_EAX_EBX = 15
    AND_ECX_0F = 16
    SHR_EBX_1 = 17
    SHL_EAX_1 = 18
    SHR_EAX_CL = 19
    SHL_EAX_CL = 20
    OR_EAX_EBX = 21
    NOT_EAX = 22
    NEG_EAX = 23
    DEC_EAX = 24
    INC_EAX = 25
    IMMED = 0x100
    MOV_EAX_IMMED = 0x101
    AND_EBX_IMMED = 0x102
    AND_EAX_IMMED = 0x103
    XOR_EAX_IMMED = 0x104
    ADD_EAX_IMMED = 0x105
    SUB_EAX_IMMED = 0x106


def _u32(value: int) -> int:
    return value & 0xFFFFFFFF


def _parse_u32(value: object) -> int:
    if isinstance(value, int):
        return _u32(value)
    if isinstance(value, str):
        return _u32(int(value.strip(), 0))
    raise ValueError(f"Unsupported 32-bit value: {value!r}")


def _parse_cxdec_order(value: object, *, expected_size: int, name: str) -> Tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"cxdec {name} must be a list")
    if len(value) < expected_size:
        raise ValueError(f"cxdec {name} must contain at least {expected_size} items")
    return tuple(int(item) for item in value)


def _parse_cxdec_control_block(value: object) -> Tuple[int, ...]:
    if isinstance(value, list):
        block = tuple(_parse_u32(item) for item in value)
    elif isinstance(value, str):
        payload = bytes.fromhex(value.replace(" ", ""))
        if len(payload) % 4 != 0:
            raise ValueError("cxdec control_block hex must be dword-aligned")
        block = tuple(struct.unpack(f"<{len(payload) // 4}I", payload))
    else:
        raise ValueError("cxdec control_block must be a list or hex string")
    if len(block) != 0x400:
        raise ValueError("cxdec control_block must contain exactly 0x400 dwords")
    return block


def _load_cxdec_control_block_from_tpm(archive_path: Path, tpm_name: str) -> Tuple[int, ...]:
    tpm_path = archive_path.parent / tpm_name
    raw = tpm_path.read_bytes()
    if len(raw) < 0x1000:
        raise ValueError(f"Invalid KiriKiri TPM plugin: {tpm_path}")

    limit = max(0, len(raw) - 0x1000)
    offset = 0
    while offset <= limit:
        if raw[offset:offset + len(CXDEC_CONTROL_BLOCK_SIGNATURE)] == CXDEC_CONTROL_BLOCK_SIGNATURE:
            if offset + (0x400 * 4) > len(raw):
                raise ValueError(f"Truncated cxdec control block in {tpm_path}")
            words = struct.unpack_from("<1024I", raw, offset)
            return tuple(_u32(~word) for word in words)
        offset += 4
    raise ValueError(f"No cxdec control block found in {tpm_path}")


def _parse_cxdec_key(key: str, archive_path: Optional[Path] = None) -> Optional[CxdecSettings]:
    raw = str(key or "").strip()
    if not raw.lower().startswith("cxdec:"):
        return None

    payload = raw[6:].strip()
    if not payload:
        raise ValueError("cxdec key is missing JSON payload")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("cxdec key payload must be a JSON object")

    control_block: Optional[Tuple[int, ...]] = None
    if "control_block" in data:
        control_block = _parse_cxdec_control_block(data["control_block"])
    tpm_name = str(data.get("tpm", "") or "")
    if control_block is None and tpm_name:
        if archive_path is None:
            raise ValueError("cxdec TPM-backed keys require the archive path")
        control_block = _load_cxdec_control_block_from_tpm(archive_path, tpm_name)

    return CxdecSettings(
        mask=_parse_u32(data.get("mask", 0)),
        offset=_parse_u32(data.get("offset", 0)),
        prolog_order=_parse_cxdec_order(data.get("prolog", []), expected_size=3, name="prolog"),
        odd_branch_order=_parse_cxdec_order(data.get("odd", []), expected_size=6, name="odd"),
        even_branch_order=_parse_cxdec_order(
            data.get("even", []), expected_size=8, name="even"
        ),
        control_block=control_block,
        tpm=tpm_name,
    )


class _CxProgram:
    LENGTH_LIMIT = 0x80

    def __init__(self, seed: int, control_block: Tuple[int, ...]) -> None:
        self._seed = _u32(seed)
        self._control_block = control_block
        self._length = 0
        self._code: List[int] = []

    def clear(self) -> None:
        self._seed = _u32(self._seed)
        self._length = 0
        self._code.clear()

    def emit_nop(self, count: int) -> bool:
        if self._length + count > self.LENGTH_LIMIT:
            return False
        self._length += count
        return True

    def emit(self, code: _CxOpcode, length: int = 1) -> bool:
        if self._length + length > self.LENGTH_LIMIT:
            return False
        self._length += length
        self._code.append(int(code))
        return True

    def emit_u32(self, value: int) -> bool:
        if self._length + 4 > self.LENGTH_LIMIT:
            return False
        self._length += 4
        self._code.append(_u32(value))
        return True

    def emit_random(self) -> bool:
        return self.emit_u32(self.get_random())

    def get_random(self) -> int:
        seed = self._seed
        self._seed = _u32(1103515245 * seed + 12345)
        return _u32(self._seed ^ (seed << 16) ^ (seed >> 16))

    def execute(self, value: int) -> int:
        eax = 0
        ebx = 0
        ecx = 0
        edi = 0
        stack: List[int] = []
        immed = 0
        index = 0
        while index < len(self._code):
            code = self._code[index]
            index += 1
            if code & int(_CxOpcode.IMMED):
                if index >= len(self._code):
                    raise ValueError("Incomplete cxdec immediate bytecode")
                immed = self._code[index]
                index += 1

            opcode = _CxOpcode(code)
            if opcode == _CxOpcode.NOP:
                continue
            if opcode == _CxOpcode.RETN:
                if stack:
                    raise ValueError("Imbalanced cxdec stack")
                return _u32(eax)
            if opcode == _CxOpcode.MOV_EDI_ARG:
                edi = _u32(value)
            elif opcode == _CxOpcode.PUSH_EBX:
                stack.append(_u32(ebx))
            elif opcode == _CxOpcode.POP_EBX:
                ebx = stack.pop()
            elif opcode == _CxOpcode.PUSH_ECX:
                stack.append(_u32(ecx))
            elif opcode == _CxOpcode.POP_ECX:
                ecx = stack.pop()
            elif opcode == _CxOpcode.MOV_EBX_EAX:
                ebx = _u32(eax)
            elif opcode == _CxOpcode.MOV_EAX_EDI:
                eax = _u32(edi)
            elif opcode == _CxOpcode.MOV_ECX_EBX:
                ecx = _u32(ebx)
            elif opcode == _CxOpcode.MOV_EAX_EBX:
                eax = _u32(ebx)
            elif opcode == _CxOpcode.AND_ECX_0F:
                ecx = _u32(ecx & 0x0F)
            elif opcode == _CxOpcode.SHR_EBX_1:
                ebx = _u32(ebx >> 1)
            elif opcode == _CxOpcode.SHL_EAX_1:
                eax = _u32(eax << 1)
            elif opcode == _CxOpcode.SHR_EAX_CL:
                eax = _u32(eax >> ecx)
            elif opcode == _CxOpcode.SHL_EAX_CL:
                eax = _u32(eax << ecx)
            elif opcode == _CxOpcode.OR_EAX_EBX:
                eax = _u32(eax | ebx)
            elif opcode == _CxOpcode.NOT_EAX:
                eax = _u32(~eax)
            elif opcode == _CxOpcode.NEG_EAX:
                eax = _u32(-eax)
            elif opcode == _CxOpcode.DEC_EAX:
                eax = _u32(eax - 1)
            elif opcode == _CxOpcode.INC_EAX:
                eax = _u32(eax + 1)
            elif opcode == _CxOpcode.ADD_EAX_EBX:
                eax = _u32(eax + ebx)
            elif opcode == _CxOpcode.SUB_EAX_EBX:
                eax = _u32(eax - ebx)
            elif opcode == _CxOpcode.IMUL_EAX_EBX:
                eax = _u32(eax * ebx)
            elif opcode == _CxOpcode.ADD_EAX_IMMED:
                eax = _u32(eax + immed)
            elif opcode == _CxOpcode.SUB_EAX_IMMED:
                eax = _u32(eax - immed)
            elif opcode == _CxOpcode.AND_EBX_IMMED:
                ebx = _u32(ebx & immed)
            elif opcode == _CxOpcode.AND_EAX_IMMED:
                eax = _u32(eax & immed)
            elif opcode == _CxOpcode.XOR_EAX_IMMED:
                eax = _u32(eax ^ immed)
            elif opcode == _CxOpcode.MOV_EAX_IMMED:
                eax = _u32(immed)
            elif opcode == _CxOpcode.MOV_EAX_INDIRECT:
                if eax >= len(self._control_block):
                    raise ValueError("cxdec control block index out of range")
                eax = _u32(~self._control_block[eax])
            else:
                raise ValueError(f"Unsupported cxdec opcode: {opcode}")
        raise ValueError("cxdec program missing RETN")


class _CxdecCipher:
    def __init__(self, settings: CxdecSettings) -> None:
        if settings.control_block is None:
            raise ValueError("cxdec control block is required")
        self._mask = _u32(settings.mask)
        self._offset = _u32(settings.offset)
        self._prolog = settings.prolog_order
        self._odd = settings.odd_branch_order
        self._even = settings.even_branch_order
        self._control_block = settings.control_block
        self._programs: Dict[int, _CxProgram] = {}

    def decrypt(self, file_hash: int, data: bytes) -> bytes:
        result = bytearray(data)
        offset = 0
        count = len(result)
        key = _u32(file_hash)
        base_offset = _u32((key & self._mask) + self._offset)

        if offset < base_offset:
            base_length = min(base_offset - offset, count)
            self._decode(key, offset, result, 0, base_length)
            offset += base_length
            count -= base_length
        if count > 0:
            self._decode(_u32((key >> 16) ^ key), offset, result, len(result) - count, count)
        return bytes(result)

    def _decode(
        self,
        key: int,
        offset: int,
        buffer: bytearray,
        pos: int,
        count: int,
    ) -> None:
        ret1, ret2 = self._execute_xcode(key)
        key1 = _u32(ret2 >> 16)
        key2 = _u32(ret2 & 0xFFFF)
        key3 = ret1 & 0xFF
        if key1 == key2:
            key2 = _u32(key2 + 1)
        if key3 == 0:
            key3 = 1

        if offset <= key2 < offset + count:
            buffer[pos + key2 - offset] ^= (ret1 >> 16) & 0xFF
        if offset <= key1 < offset + count:
            buffer[pos + key1 - offset] ^= (ret1 >> 8) & 0xFF
        for index in range(count):
            buffer[pos + index] ^= key3

    def _execute_xcode(self, value: int) -> Tuple[int, int]:
        seed = value & 0x7F
        if seed not in self._programs:
            self._programs[seed] = self._generate_program(seed)
        program = self._programs[seed]
        hashed = _u32(value >> 7)
        return program.execute(hashed), program.execute(_u32(~hashed))

    def _generate_program(self, seed: int) -> _CxProgram:
        program = _CxProgram(seed, self._control_block)
        for stage in range(5, 0, -1):
            if self._emit_code(program, stage):
                return program
            program.clear()
        raise ValueError("cxdec bytecode exceeds length limit")

    def _emit_code(self, program: _CxProgram, stage: int) -> bool:
        return (
            program.emit_nop(5)
            and program.emit(_CxOpcode.MOV_EDI_ARG, 4)
            and self._emit_body(program, stage)
            and program.emit_nop(5)
            and program.emit(_CxOpcode.RETN)
        )

    def _emit_body(self, program: _CxProgram, stage: int) -> bool:
        if stage == 1:
            return self._emit_prolog(program)
        if not program.emit(_CxOpcode.PUSH_EBX):
            return False
        if program.get_random() & 1:
            if not self._emit_body(program, stage - 1):
                return False
        elif not self._emit_body2(program, stage - 1):
            return False
        if not program.emit(_CxOpcode.MOV_EBX_EAX, 2):
            return False
        if program.get_random() & 1:
            if not self._emit_body(program, stage - 1):
                return False
        elif not self._emit_body2(program, stage - 1):
            return False
        return self._emit_odd_branch(program) and program.emit(_CxOpcode.POP_EBX)

    def _emit_body2(self, program: _CxProgram, stage: int) -> bool:
        if stage == 1:
            return self._emit_prolog(program)
        if program.get_random() & 1:
            ok = self._emit_body(program, stage - 1)
        else:
            ok = self._emit_body2(program, stage - 1)
        return ok and self._emit_even_branch(program)

    def _emit_prolog(self, program: _CxProgram) -> bool:
        branch = self._prolog[program.get_random() % 3]
        if branch == 2:
            return (
                program.emit_nop(5)
                and program.emit(_CxOpcode.MOV_EAX_IMMED, 2)
                and program.emit_u32(program.get_random() & 0x3FF)
                and program.emit(_CxOpcode.MOV_EAX_INDIRECT)
            )
        if branch == 1:
            return program.emit(_CxOpcode.MOV_EAX_EDI, 2)
        if branch == 0:
            return program.emit(_CxOpcode.MOV_EAX_IMMED) and program.emit_random()
        raise ValueError(f"Unsupported cxdec prolog branch: {branch}")

    def _emit_even_branch(self, program: _CxProgram) -> bool:
        branch = self._even[program.get_random() & 7]
        if branch == 0:
            return program.emit(_CxOpcode.NOT_EAX, 2)
        if branch == 1:
            return program.emit(_CxOpcode.DEC_EAX)
        if branch == 2:
            return program.emit(_CxOpcode.NEG_EAX, 2)
        if branch == 3:
            return program.emit(_CxOpcode.INC_EAX)
        if branch == 4:
            return (
                program.emit_nop(5)
                and program.emit(_CxOpcode.AND_EAX_IMMED)
                and program.emit_u32(0x3FF)
                and program.emit(_CxOpcode.MOV_EAX_INDIRECT, 3)
            )
        if branch == 5:
            return (
                program.emit(_CxOpcode.PUSH_EBX)
                and program.emit(_CxOpcode.MOV_EBX_EAX, 2)
                and program.emit(_CxOpcode.AND_EBX_IMMED, 2)
                and program.emit_u32(0xAAAAAAAA)
                and program.emit(_CxOpcode.AND_EAX_IMMED)
                and program.emit_u32(0x55555555)
                and program.emit(_CxOpcode.SHR_EBX_1, 2)
                and program.emit(_CxOpcode.SHL_EAX_1, 2)
                and program.emit(_CxOpcode.OR_EAX_EBX, 2)
                and program.emit(_CxOpcode.POP_EBX)
            )
        if branch == 6:
            return program.emit(_CxOpcode.XOR_EAX_IMMED) and program.emit_random()
        if branch == 7:
            opcode = _CxOpcode.ADD_EAX_IMMED if program.get_random() & 1 else _CxOpcode.SUB_EAX_IMMED
            return program.emit(opcode) and program.emit_random()
        raise ValueError(f"Unsupported cxdec even branch: {branch}")

    def _emit_odd_branch(self, program: _CxProgram) -> bool:
        branch = self._odd[program.get_random() % 6]
        if branch == 0:
            return (
                program.emit(_CxOpcode.PUSH_ECX)
                and program.emit(_CxOpcode.MOV_ECX_EBX, 2)
                and program.emit(_CxOpcode.AND_ECX_0F, 3)
                and program.emit(_CxOpcode.SHR_EAX_CL, 2)
                and program.emit(_CxOpcode.POP_ECX)
            )
        if branch == 1:
            return (
                program.emit(_CxOpcode.PUSH_ECX)
                and program.emit(_CxOpcode.MOV_ECX_EBX, 2)
                and program.emit(_CxOpcode.AND_ECX_0F, 3)
                and program.emit(_CxOpcode.SHL_EAX_CL, 2)
                and program.emit(_CxOpcode.POP_ECX)
            )
        if branch == 2:
            return program.emit(_CxOpcode.ADD_EAX_EBX, 2)
        if branch == 3:
            return program.emit(_CxOpcode.NEG_EAX, 2) and program.emit(_CxOpcode.ADD_EAX_EBX, 2)
        if branch == 4:
            return program.emit(_CxOpcode.IMUL_EAX_EBX, 3)
        if branch == 5:
            return program.emit(_CxOpcode.SUB_EAX_EBX, 2)
        raise ValueError(f"Unsupported cxdec odd branch: {branch}")


def _xp3_magic_to_manifest_value(magic: bytes) -> str:
    return f"hex:{magic.hex()}"


def _xp3_magic_from_manifest_value(value: str) -> bytes:
    raw = str(value or "").strip()
    if not raw:
        return XP3_MAGIC
    if raw.lower().startswith("hex:"):
        payload = raw[4:].replace(" ", "")
        if len(payload) % 2 != 0:
            raise ValueError("XP3 custom magic hex payload must have an even number of digits")
        return bytes.fromhex(payload)
    return raw.encode("latin-1")


def _xp3_normalize_settings(
    settings: Optional[Xp3ArchiveSettings | Dict[str, object]],
) -> Xp3ArchiveSettings:
    if isinstance(settings, Xp3ArchiveSettings):
        return settings
    if isinstance(settings, dict):
        return Xp3ArchiveSettings.from_dict(settings)
    return Xp3ArchiveSettings()


def _xp3_parse_xor_key(key: str) -> Optional[int]:
    raw = str(key or "").strip().lower()
    if not raw:
        return None
    if raw in {"xor1", "xor:1", "xor:0x01"}:
        return 1
    if raw.startswith("xor:"):
        payload = raw[4:].strip()
        try:
            return int(payload, 0) & 0xFF
        except ValueError:
            return None
    try:
        return int(raw, 0) & 0xFF
    except ValueError:
        return None


def _xp3_apply_xor_filter(data: bytes, value: int) -> bytes:
    return bytes(byte ^ value for byte in data)


def _xp3_score_text_candidate(name: str, data: bytes) -> float:
    lowered_name = name.lower()
    if lowered_name.endswith(".ks"):
        encodings = KS_ENCODING_CANDIDATES
        markers = ("[", "]", "@", "*", ";", "【", "】", "「", "」", "\r", "\n")
    elif lowered_name.endswith(".tjs"):
        encodings = MENU_ENCODING_CANDIDATES
        markers = ("//", "var ", "function", "if", "global.", "=", "{", "}", "(", ")")
    else:
        encodings = KS_ENCODING_CANDIDATES + MENU_ENCODING_CANDIDATES
        markers = ("\r", "\n", "[", "]", "@", "{", "}")

    sample = data[:4096]
    best_score = float("-inf")
    for encoding in encodings:
        text = sample.decode(encoding, errors="replace")
        if not text:
            best_score = max(best_score, 0.0)
            continue

        printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
        control = sum(ord(ch) < 32 and ch not in "\r\n\t" for ch in text)
        replacements = text.count("\ufffd")
        nulls = text.count("\x00")
        japanese = len(JAPANESE_RE.findall(text))
        marker_hits = sum(text.count(marker) for marker in markers)
        high_ascii = sum(1 for ch in text if 0x7F <= ord(ch) <= 0x9F)
        score = (
            (printable * 1.5)
            + (japanese * 2.0)
            + (marker_hits * 12.0)
            - (control * 18.0)
            - (replacements * 24.0)
            - (nulls * 40.0)
            - (high_ascii * 12.0)
        )
        best_score = max(best_score, score)
    return best_score


def _xp3_looks_like_text_payload(name: str, data: bytes) -> bool:
    sample = data[:2048]
    for encoding in KS_ENCODING_CANDIDATES + MENU_ENCODING_CANDIDATES:
        try:
            text = sample.decode(encoding)
        except UnicodeDecodeError:
            continue
        if not text:
            return True

        printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
        ratio = printable / max(len(text), 1)
        lowered_name = name.lower()
        if lowered_name.endswith(".tjs") and any(
            token in text for token in ("//", "var ", "global.", "function", "if (")
        ):
            return True
        if lowered_name.endswith(".ks") and any(
            token in text for token in ("[", "@", "【", "「", ";")
        ):
            return True
        if ratio >= 0.85 and "\x00" not in text:
            return True
    return False


def _xp3_looks_like_decoded_payload(name: str, data: bytes) -> bool:
    lowered_name = name.lower()
    if lowered_name.endswith(".png"):
        return data.startswith(bytes.fromhex("89504e470d0a1a0a"))
    if lowered_name.endswith(".ogg"):
        return data.startswith(b"OggS")
    if lowered_name.endswith(".wmv") or lowered_name.endswith(".asf"):
        return data.startswith(bytes.fromhex("3026b2758e66cf11"))
    if lowered_name.endswith((".tjs", ".ks", ".txt", ".json", ".csv")):
        return _xp3_looks_like_text_payload(name, data)
    return False


def _decode_xp3_protected_payload(
    entry: Xp3Entry,
    data: bytes,
    key: str = "",
    archive_path: Optional[Path] = None,
) -> bytes:
    cxdec_settings = _parse_cxdec_key(key, archive_path=archive_path)
    if cxdec_settings is not None:
        return _CxdecCipher(cxdec_settings).decrypt(entry.file_hash, data)

    xor_value = _xp3_parse_xor_key(key)
    if xor_value is not None:
        return _xp3_apply_xor_filter(data, xor_value)

    if not (entry.flags & XP3_FILE_PROTECTED):
        return data

    xor1_candidate = _xp3_apply_xor_filter(data, 1)
    if _xp3_looks_like_decoded_payload(entry.name, xor1_candidate):
        return xor1_candidate
    return data


def _reconstruct_xp3_entry_bytes(handle, entry: Xp3Entry) -> bytes:
    content = bytearray()
    for segment in entry.segments:
        handle.seek(segment.offset)
        chunk = handle.read(segment.packed_size)
        if segment.flags & 0x1:
            chunk = zlib.decompress(chunk)
        if len(chunk) != segment.original_size:
            raise ValueError(
                f"XP3 segment size mismatch for {entry.name}: "
                f"{len(chunk)} != {segment.original_size}"
            )
        content.extend(chunk)
    return bytes(content)


def _read_xp3_entry_bytes(
    handle,
    entry: Xp3Entry,
    *,
    key: str = "",
    archive_path: Optional[Path] = None,
) -> bytes:
    content = _reconstruct_xp3_entry_bytes(handle, entry)
    return _decode_xp3_protected_payload(
        entry,
        bytes(content),
        key=key,
        archive_path=archive_path,
    )


def infer_xp3_archive_key(
    path: Path,
    settings: Optional[Xp3ArchiveSettings | Dict[str, object]] = None,
    *,
    sample_entries: int = 32,
) -> str:
    resolved = _xp3_normalize_settings(settings)
    if resolved.key:
        return resolved.key

    entries = list_xp3_entries(path, settings=resolved)
    if not entries:
        return ""

    with path.open("rb") as handle:
        for entry in entries[:sample_entries]:
            if not (entry.flags & XP3_FILE_PROTECTED):
                continue
            raw = _reconstruct_xp3_entry_bytes(handle, entry)
            xor1_candidate = _xp3_apply_xor_filter(raw, 1)
            if _xp3_looks_like_decoded_payload(entry.name, xor1_candidate):
                return "xor:1"

    return ""


def detect_xp3_archive_settings(
    path: Path,
    *,
    scan_limit: int = XP3_SCAN_LIMIT,
) -> Optional[Xp3ArchiveSettings]:
    probe = path.read_bytes()[:max(0, scan_limit)]
    if probe.startswith(XP3_MAGIC):
        return Xp3ArchiveSettings(
            custom_magic=_xp3_magic_to_manifest_value(XP3_MAGIC),
            header_offset=0,
            key="",
        )

    offset = probe.find(XP3_MAGIC)
    if offset >= 0:
        return Xp3ArchiveSettings(
            custom_magic=_xp3_magic_to_manifest_value(XP3_MAGIC),
            header_offset=offset,
            key="",
        )

    return None


def _xp3_find_header_offset(
    path: Path,
    *,
    magic: bytes = XP3_MAGIC,
    max_probe_bytes: int = XP3_SCAN_LIMIT,
) -> int:
    probe = path.read_bytes()[:max(0, max_probe_bytes)]
    offset = probe.find(magic)
    if offset < 0:
        raise ValueError(f"Not an XP3 archive: {path}")
    return offset


def _xp3_read_index_data(
    path: Path,
    settings: Optional[Xp3ArchiveSettings | Dict[str, object]] = None,
) -> bytes:
    resolved = _xp3_normalize_settings(settings)
    magic = _xp3_magic_from_manifest_value(resolved.custom_magic)
    if resolved.custom_magic:
        header_offset = resolved.header_offset
    else:
        header_offset = _xp3_find_header_offset(path, magic=magic)
    with path.open("rb") as handle:
        handle.seek(header_offset + len(magic))
        info_offset = struct.unpack("<Q", handle.read(8))[0]
        table_pointer = header_offset + info_offset
        handle.seek(table_pointer)
        marker = handle.read(1)
        if not marker:
            raise ValueError(f"XP3 header is truncated: {path}")
        if marker[0] == 0x80:
            handle.seek(8, 1)
            table_offset = header_offset + struct.unpack("<Q", handle.read(8))[0]
        else:
            table_offset = table_pointer

        handle.seek(table_offset)
        compression_flag = handle.read(1)
        if not compression_flag:
            raise ValueError(f"XP3 table is truncated: {path}")
        mode = compression_flag[0]
        if mode == 0:
            size = struct.unpack("<Q", handle.read(8))[0]
            return handle.read(size)
        if mode == 1:
            packed_size = struct.unpack("<Q", handle.read(8))[0]
            unpacked_size = struct.unpack("<Q", handle.read(8))[0]
            data = zlib.decompress(handle.read(packed_size))
            if len(data) != unpacked_size:
                raise ValueError(
                    f"XP3 index size mismatch for {path}: {len(data)} != {unpacked_size}"
                )
            return data
        raise ValueError(f"Unsupported XP3 index compression mode {mode} for {path}")


def list_xp3_entries(
    path: Path,
    settings: Optional[Xp3ArchiveSettings | Dict[str, object]] = None,
) -> List[Xp3Entry]:
    """List entries in a standard XP3 archive."""
    index_data = _xp3_read_index_data(path, settings=settings)
    entries: List[Xp3Entry] = []
    position = 0

    while position + 12 <= len(index_data):
        signature = index_data[position:position + 4]
        position += 4
        entry_size = struct.unpack("<Q", index_data[position:position + 8])[0]
        position += 8
        entry_end = position + entry_size
        if signature != b"File":
            position = entry_end
            continue

        name = ""
        flags = 0
        original_size = 0
        packed_size = 0
        file_hash = 0
        segments: List[Xp3Segment] = []

        while position + 12 <= entry_end:
            chunk_sig = index_data[position:position + 4]
            position += 4
            chunk_size = struct.unpack("<Q", index_data[position:position + 8])[0]
            position += 8
            chunk = index_data[position:position + chunk_size]
            position += chunk_size

            if chunk_sig == b"info":
                flags = struct.unpack("<I", chunk[:4])[0]
                original_size = struct.unpack("<Q", chunk[4:12])[0]
                packed_size = struct.unpack("<Q", chunk[12:20])[0]
                name_length = struct.unpack("<H", chunk[20:22])[0]
                name = chunk[22:22 + (name_length * 2)].decode("utf-16le")
            elif chunk_sig == b"segm":
                seg_pos = 0
                while seg_pos + 28 <= len(chunk):
                    segments.append(
                        Xp3Segment(
                            flags=struct.unpack("<I", chunk[seg_pos:seg_pos + 4])[0],
                            offset=struct.unpack("<Q", chunk[seg_pos + 4:seg_pos + 12])[0],
                            original_size=struct.unpack("<Q", chunk[seg_pos + 12:seg_pos + 20])[0],
                            packed_size=struct.unpack("<Q", chunk[seg_pos + 20:seg_pos + 28])[0],
                        )
                    )
                    seg_pos += 28
            elif chunk_sig == b"adlr" and len(chunk) >= 4:
                file_hash = struct.unpack("<I", chunk[:4])[0]

        if name and segments:
            entries.append(
                Xp3Entry(
                    name=name.replace("\\", "/"),
                    flags=flags,
                    original_size=original_size,
                    packed_size=packed_size,
                    file_hash=file_hash,
                    segments=segments,
                )
            )
        position = entry_end

    return entries


def unpack_xp3_archive(
    archive_path: Path,
    output_dir: Path,
    *,
    include_protected_notice: bool = False,
    settings: Optional[Xp3ArchiveSettings | Dict[str, object]] = None,
) -> List[Path]:
    """Extract a standard XP3 archive into *output_dir*."""
    entries = list_xp3_entries(archive_path, settings=settings)
    extracted_paths: List[Path] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    with archive_path.open("rb") as handle:
        for entry in entries:
            if (
                not include_protected_notice
                and entry.name.startswith("$$$ This is a protected archive")
            ):
                continue

            parts = [part for part in entry.name.split("/") if part not in {"", "."}]
            target_path = output_dir.joinpath(*parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = _read_xp3_entry_bytes(
                handle,
                entry,
                key=_xp3_normalize_settings(settings).key,
                archive_path=archive_path,
            )
            target_path.write_bytes(content)
            extracted_paths.append(target_path)

    return extracted_paths


def _build_xp3_chunk(signature: bytes, payload: bytes) -> bytes:
    return signature + struct.pack("<Q", len(payload)) + payload


def pack_xp3_archive(
    source_dir: Path,
    archive_path: Path,
    *,
    compress_contents: bool = True,
    settings: Optional[Xp3ArchiveSettings | Dict[str, object]] = None,
) -> Path:
    """Pack *source_dir* into a standard XP3 archive at *archive_path*."""
    source_dir = Path(source_dir)
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    entries: List[Tuple[str, int, int, int, Xp3Segment]] = []
    resolved = _xp3_normalize_settings(settings)
    magic = _xp3_magic_from_manifest_value(resolved.custom_magic)
    header_offset = max(0, resolved.header_offset)
    header_size = len(magic) + 29

    with archive_path.open("wb") as handle:
        handle.write(b"\x00" * (header_offset + header_size))
        for file_path in files:
            raw = file_path.read_bytes()
            packed = raw
            segment_flags = 0
            if compress_contents and raw:
                compressed = zlib.compress(raw)
                if len(compressed) < len(raw):
                    packed = compressed
                    segment_flags = 1

            offset = handle.tell()
            handle.write(packed)
            entries.append(
                (
                    file_path.relative_to(source_dir).as_posix(),
                    len(raw),
                    len(packed),
                    zlib.adler32(raw) & 0xFFFFFFFF,
                    Xp3Segment(
                        flags=segment_flags,
                        offset=offset,
                        original_size=len(raw),
                        packed_size=len(packed),
                    ),
                )
            )

        index_parts: List[bytes] = []
        for rel_name, original_size, packed_size, file_hash, segment in entries:
            encoded_name = rel_name.encode("utf-16le")
            info_payload = struct.pack("<IQQH", 0, original_size, packed_size, len(rel_name)) + encoded_name
            segm_payload = struct.pack(
                "<IQQQ",
                segment.flags,
                segment.offset,
                segment.original_size,
                segment.packed_size,
            )
            entry_payload = b"".join(
                (
                    _build_xp3_chunk(b"adlr", struct.pack("<I", file_hash)),
                    _build_xp3_chunk(b"segm", segm_payload),
                    _build_xp3_chunk(b"info", info_payload),
                )
            )
            index_parts.append(b"File" + struct.pack("<Q", len(entry_payload)) + entry_payload)

        index_data = b"".join(index_parts)
        compressed_index = zlib.compress(index_data)
        directory_offset = handle.tell()
        handle.write(b"\x01")
        handle.write(struct.pack("<Q", len(compressed_index)))
        handle.write(struct.pack("<Q", len(index_data)))
        handle.write(compressed_index)

        handle.seek(header_offset)
        handle.write(magic)
        handle.write(struct.pack("<Q", len(magic) + 12))
        handle.write(struct.pack("<I", 1))
        handle.write(b"\x80")
        handle.write(b"\x00" * 8)
        handle.write(struct.pack("<Q", directory_offset - header_offset))

    return archive_path


def _classify_line(number: int, raw_line: str) -> ClassifiedLine:
    text, newline = _split_line_ending(raw_line)
    stripped = text.strip()
    speaker_match = SPEAKER_RE.match(stripped)
    if not stripped:
        return ClassifiedLine(number=number, text=text, newline=newline, kind="blank")
    if speaker_match:
        return ClassifiedLine(
            number=number,
            text=text,
            newline=newline,
            kind="speaker",
            speaker=speaker_match.group("speaker") or "",
            voice_id=speaker_match.group("voice_id") or "",
        )
    if COMMENT_RE.match(stripped):
        kind = "comment"
    elif LABEL_RE.match(stripped):
        kind = "label"
    elif AT_COMMAND_RE.match(stripped):
        kind = "at_command"
    elif TAG_RE.match(stripped):
        kind = "tag"
    elif BRACE_COMMAND_RE.match(stripped):
        kind = "brace_command"
    else:
        kind = "text"
    return ClassifiedLine(number=number, text=text, newline=newline, kind=kind)


def _next_significant_kind(lines: Sequence[ClassifiedLine], start_index: int) -> Optional[str]:
    for index in range(start_index, len(lines)):
        kind = lines[index].kind
        if kind == "comment":
            continue
        return kind
    return None


def _should_keep_as_bridge(
    line: ClassifiedLine,
    lines: Sequence[ClassifiedLine],
    index: int,
    *,
    has_open_block: bool,
    pending_speaker: Optional[PendingSpeaker],
) -> bool:
    if line.kind not in SOFT_BRIDGE_KINDS:
        return False
    if not has_open_block and pending_speaker is None:
        return False
    return _next_significant_kind(lines, index + 1) == "text"


def _extract_ks_blocks(path: Path) -> List[KsBlock]:
    text, _ = _read_text(path, KS_ENCODING_CANDIDATES)
    raw_lines = text.splitlines(keepends=True)
    lines = [_classify_line(index + 1, raw_line) for index, raw_line in enumerate(raw_lines)]
    blocks: List[KsBlock] = []
    current: Optional[KsBlock] = None
    pending_speaker: Optional[PendingSpeaker] = None
    block_number = 0
    rel_name = path.as_posix()

    for index, line in enumerate(lines):
        if line.kind == "speaker":
            if current is not None and current.joined_text:
                blocks.append(current)
            current = None
            pending_speaker = PendingSpeaker(line.speaker, line.voice_id)
            continue

        if line.kind == "text":
            if current is None:
                block_number += 1
                speaker = pending_speaker.speaker if pending_speaker else ""
                voice_id = pending_speaker.voice_id if pending_speaker else ""
                bridges = list(pending_speaker.bridge_code_lines) if pending_speaker else []
                current = KsBlock(
                    file_path=rel_name,
                    block_id=f"{rel_name}:{block_number:05d}",
                    tag="dialogue" if speaker else "narration",
                    speaker=speaker,
                    voice_id=voice_id,
                    start_line=line.number,
                    end_line=line.number,
                    bridge_code_lines=bridges,
                )
                pending_speaker = None
            current.text_line_numbers.append(line.number)
            current.source_text_lines.append(line.text)
            current.end_line = line.number
            continue

        if _should_keep_as_bridge(
            line,
            lines,
            index,
            has_open_block=current is not None,
            pending_speaker=pending_speaker,
        ):
            bridge = (line.number, line.text, line.kind)
            if current is not None:
                current.bridge_code_lines.append(bridge)
            elif pending_speaker is not None:
                pending_speaker.bridge_code_lines.append(bridge)
            continue

        if line.kind in HARD_BREAK_KINDS or line.kind in SOFT_BRIDGE_KINDS:
            if current is not None and current.joined_text:
                blocks.append(current)
            current = None
            if line.kind in HARD_BREAK_KINDS:
                pending_speaker = None
            continue

        if current is not None and current.joined_text:
            blocks.append(current)
        current = None

    if current is not None and current.joined_text:
        blocks.append(current)

    return [block for block in blocks if JAPANESE_RE.search(block.joined_text)]


def _iter_string_literals(segment: str, base_offset: int = 0) -> Iterable[Tuple[str, int, int]]:
    for match in STRING_LITERAL_RE.finditer(segment):
        yield match.group(1), base_offset + match.start(1), base_offset + match.end(1)


def _find_matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    index = open_idx
    in_string = False
    quote = ""
    while index < len(text):
        char = text[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                in_string = False
            index += 1
            continue
        if char in ('"', "'"):
            in_string = True
            quote = char
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _split_args_top_level(segment: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    depth = 0
    in_string = False
    quote = ""
    start = 0
    index = 0
    while index < len(segment):
        char = segment[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                in_string = False
            index += 1
            continue
        if char in ('"', "'"):
            in_string = True
            quote = char
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            spans.append((start, index))
            start = index + 1
        index += 1
    if start < len(segment):
        spans.append((start, len(segment)))
    return spans


def _split_left_and_suffix(content: str) -> Tuple[str, str, str]:
    if "\\t" in content:
        left, suffix = content.split("\\t", 1)
        return left, "\\t", suffix
    if "\t" in content:
        left, suffix = content.split("\t", 1)
        return left, "\t", suffix
    return content, "", ""


def _extract_menu_literals(path: Path) -> List[MenuEntry]:
    text, _ = _read_text(path, MENU_ENCODING_CANDIDATES)
    lines = text.splitlines(keepends=True)
    entries: List[MenuEntry] = []

    for line_index, line in enumerate(lines):
        lowered = line.lower()
        if "kagmenuitem" not in lowered and "menuitem" not in lowered:
            continue
        open_idx = line.find("(")
        if open_idx == -1:
            continue
        close_idx = _find_matching_paren(line, open_idx)
        if close_idx == -1:
            continue
        args_segment = line[open_idx + 1:close_idx]
        arg_spans = _split_args_top_level(args_segment)
        if len(arg_spans) < 2:
            continue
        second_arg_start, second_arg_end = arg_spans[1]
        arg_text = args_segment[second_arg_start:second_arg_end]
        base_offset = open_idx + 1 + second_arg_start
        for literal_index, (content, _start, _end) in enumerate(
            _iter_string_literals(arg_text, base_offset)
        ):
            left, _delimiter, _suffix = _split_left_and_suffix(content)
            if left == "-" or not left.strip():
                continue
            entries.append(MenuEntry(text=left, line_index=line_index, literal_index=literal_index))

    return entries


def _replace_menu_literals(line: str, translated_texts: Sequence[str]) -> str:
    lowered = line.lower()
    if "kagmenuitem" not in lowered and "menuitem" not in lowered:
        return line
    open_idx = line.find("(")
    if open_idx == -1:
        return line
    close_idx = _find_matching_paren(line, open_idx)
    if close_idx == -1:
        return line
    args_segment = line[open_idx + 1:close_idx]
    arg_spans = _split_args_top_level(args_segment)
    if len(arg_spans) < 2:
        return line
    second_arg_start, second_arg_end = arg_spans[1]
    arg_text = args_segment[second_arg_start:second_arg_end]
    literal_matches = list(STRING_LITERAL_RE.finditer(arg_text))
    if not literal_matches:
        return line

    pieces: List[str] = []
    cursor = 0
    replacement_index = 0
    for match in literal_matches:
        pieces.append(arg_text[cursor:match.start(1)])
        content = match.group(1)
        left, delimiter, suffix = _split_left_and_suffix(content)
        if left == "-" or not left.strip():
            pieces.append(content)
        else:
            translated = translated_texts[replacement_index] if replacement_index < len(translated_texts) else left
            replacement_index += 1
            if delimiter and delimiter not in translated:
                translated = f"{translated}{delimiter}{suffix}"
            pieces.append(translated)
        cursor = match.end(1)
    pieces.append(arg_text[cursor:])
    new_arg_text = "".join(pieces)
    rebuilt_args = args_segment[:second_arg_start] + new_arg_text + args_segment[second_arg_end:]
    return line[:open_idx + 1] + rebuilt_args + line[close_idx:]


def _escape_menu_content(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _serialize_ks_block(block: KsBlock, translated_text: str, line_endings: Dict[int, str]) -> Dict[int, str]:
    translated_lines = translated_text.split("\n") if translated_text else [""]
    replacements: Dict[int, str] = {}
    for offset, line_number in enumerate(block.text_line_numbers):
        content = translated_lines[offset] if offset < len(translated_lines) else ""
        replacements[line_number] = content + line_endings.get(line_number, "")
    return replacements


def _read_text_with_bom(path: Path) -> Tuple[str, str, bytes]:
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF16_LE):
        return data[len(codecs.BOM_UTF16_LE):].decode("utf-16-le"), "utf-16-le", codecs.BOM_UTF16_LE
    if data.startswith(codecs.BOM_UTF16_BE):
        return data[len(codecs.BOM_UTF16_BE):].decode("utf-16-be"), "utf-16-be", codecs.BOM_UTF16_BE
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8"), "utf-8", codecs.BOM_UTF8
    for encoding in ("cp932", "utf-8", "utf-16-le", "utf-16-be"):
        try:
            return data.decode(encoding), encoding, b""
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8", b""


def _write_text_with_bom(path: Path, text: str, encoding: str, bom: bytes) -> None:
    payload = text.encode(encoding)
    if bom:
        payload = bom + payload
    path.write_bytes(payload)


def _already_has_wrap_vars(text: str) -> bool:
    return "var wrapNum" in text and "var wrapPos" in text and "var oldLine" in text


def _already_has_wrap_block(text: str) -> bool:
    return "Wordwrapping code" in text or "oldLine != conductor.curLineStr" in text


def _patch_add_wrap_vars(text: str) -> str:
    if _already_has_wrap_vars(text):
        return text
    anchor = re.search(r"var\s+newPage\s*=\s*0\s*;", text)
    if anchor:
        return text
    insert_after = re.search(r"(ch\s*:\s*function\s*\(\s*elm\s*\)\s*\{)", text)
    if not insert_after:
        return text
    return text[:insert_after.end()] + _WRAP_VARS_SNIPPET + text[insert_after.end():]


def _patch_add_wrap_block(text: str) -> str:
    if _already_has_wrap_block(text):
        return text
    match = PROCESS_CH_RE.search(text)
    if not match:
        return text
    return text[:match.start()] + _WRAP_BLOCK_SNIPPET + text[match.start():]


def _is_balanced(text: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: List[str] = []
    in_line_comment = False
    in_block_comment = False
    in_string = False
    quote = ""
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and nxt == "/":
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue
        if not in_string and char == "/" and nxt == "/":
            in_line_comment = True
            index += 2
            continue
        if not in_string and char == "/" and nxt == "*":
            in_block_comment = True
            index += 2
            continue
        if not in_string and char in ('"', "'"):
            in_string = True
            quote = char
            index += 1
            continue
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                in_string = False
                quote = ""
            index += 1
            continue
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                return False
            stack.pop()
        index += 1
    return not stack


class KiriKiri2Parser(ParserScript):
    """Parser for KiriKiri2/KAG `.ks` scripts and `Menus.tjs` captions."""

    @property
    def name(self) -> str:
        return "KiriKiri2"

    @property
    def tooltip(self) -> str:
        return "KiriKiri2/KAG scenario and menu parser"

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(max_line_length=42, max_line_number=3, wordwrap_command="\n")

    def wordwrap_for_tag(self, tag: str) -> Optional[WordwrapConfig]:
        if tag == "menu":
            return WordwrapConfig(max_line_length=32, max_line_number=2, wordwrap_command="\n")
        return self.wordwrap_config

    def detect_encoding(self, file_path: Path) -> Optional[str]:
        if file_path.suffix.lower() == ".ks":
            _, encoding = _read_text(file_path, KS_ENCODING_CANDIDATES)
            return encoding
        if file_path.name.lower() == "menus.tjs":
            _, encoding = _read_text(file_path, MENU_ENCODING_CANDIDATES)
            return encoding
        return None

    def can_handle(self, file_path: Path) -> bool:
        path = Path(file_path)
        suffix = path.suffix.lower()
        name = path.name.lower()
        if suffix == ".xp3":
            return True
        if suffix == ".ks":
            if not path.exists():
                return "scenario" in {part.lower() for part in path.parts} or True
            try:
                text, _ = _read_text(path, KS_ENCODING_CANDIDATES)
            except Exception:
                return False
            for raw_line in text.splitlines():
                stripped = raw_line.strip()
                if not stripped:
                    continue
                if SPEAKER_RE.match(stripped):
                    return True
                if TAG_RE.match(stripped):
                    return True
                if AT_COMMAND_RE.match(stripped):
                    return True
            return False
        if name == "menus.tjs":
            if not path.exists():
                return True
            try:
                text, _ = _read_text(path, MENU_ENCODING_CANDIDATES)
            except Exception:
                return False
            return "KAGMenuItem" in text or "MenuItem" in text
        return False

    def extract(self, file_path: Path) -> List[str]:
        tagged = self.extract_tagged(file_path)
        return [line.text for line in tagged] if tagged else []

    def extract_tagged(self, file_path: Path) -> Optional[List[ExtractedLine]]:
        path = Path(file_path)
        if path.suffix.lower() == ".ks":
            blocks = _extract_ks_blocks(path)
            return [
                ExtractedLine(
                    text=block.joined_text,
                    tag=block.tag,
                    speaker=block.speaker,
                    context=f"{path.name}:{block.start_line}",
                )
                for block in blocks
            ]
        if path.name.lower() == "menus.tjs":
            entries = _extract_menu_literals(path)
            return [
                ExtractedLine(text=entry.text, tag="menu", context=f"{path.name}:{entry.line_index + 1}")
                for entry in entries
            ]
        return None

    def detect_speakers(self, lines: List[str]) -> Optional[List[SpeakerInfo]]:
        speakers: List[SpeakerInfo] = []
        for index, line in enumerate(lines):
            if ": " in line:
                speaker, _dialogue = line.split(": ", 1)
                if speaker:
                    speakers.append(SpeakerInfo(name=speaker, line_idx=index))
        return speakers or None

    def inject(self, file_path: Path, lines: List[str]) -> None:
        translated_path = file_path.with_stem(file_path.stem + "_translated")
        self.inject_to(file_path, translated_path, lines)

    def unpack_archive(
        self,
        archive_path: Path,
        output_dir: Path,
        *,
        settings: Optional[Xp3ArchiveSettings | Dict[str, object]] = None,
    ) -> List[Path]:
        """Unpack a standard XP3 archive into *output_dir*."""
        return unpack_xp3_archive(archive_path, output_dir, settings=settings)

    def pack_archive(
        self,
        source_dir: Path,
        archive_path: Path,
        *,
        settings: Optional[Xp3ArchiveSettings | Dict[str, object]] = None,
    ) -> Path:
        """Pack *source_dir* into a standard XP3 archive."""
        return pack_xp3_archive(source_dir, archive_path, settings=settings)

    def inject_to(
        self,
        source_path: Path,
        output_path: Path,
        lines: List[str],
        *,
        orig_lines: Optional[List[str]] = None,
    ) -> List[int]:
        path = Path(source_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if path.suffix.lower() == ".ks":
            text, encoding = _read_text(path, KS_ENCODING_CANDIDATES)
            raw_lines = text.splitlines(keepends=True)
            blocks = _extract_ks_blocks(path)
            search_keys = orig_lines if orig_lines is not None else [block.joined_text for block in blocks]
            line_endings = {
                index + 1: _split_line_ending(raw_line)[1]
                for index, raw_line in enumerate(raw_lines)
            }
            replacements: Dict[int, str] = {}
            failures: List[int] = []
            for index, translated in enumerate(lines):
                if index >= len(blocks):
                    failures.append(index)
                    continue
                block = blocks[index]
                search = search_keys[index] if index < len(search_keys) else block.joined_text
                if translated == search:
                    continue
                replacements.update(_serialize_ks_block(block, translated, line_endings))
            for line_number, replacement in replacements.items():
                raw_lines[line_number - 1] = replacement
            _write_text(output_path, "".join(raw_lines), encoding)
            return failures

        if path.name.lower() == "menus.tjs":
            text, encoding = _read_text(path, MENU_ENCODING_CANDIDATES)
            raw_lines = text.splitlines(keepends=True)
            entries = _extract_menu_literals(path)
            grouped: Dict[int, List[str]] = {}
            failures: List[int] = []
            search_keys = orig_lines if orig_lines is not None else [entry.text for entry in entries]
            for index, translated in enumerate(lines):
                if index >= len(entries):
                    failures.append(index)
                    continue
                entry = entries[index]
                search = search_keys[index] if index < len(search_keys) else entry.text
                if translated == search:
                    continue
                grouped.setdefault(entry.line_index, []).append(_escape_menu_content(translated))
            for line_index, translated_texts in grouped.items():
                raw_lines[line_index] = _replace_menu_literals(raw_lines[line_index], translated_texts)
            _write_text(output_path, "".join(raw_lines), encoding)
            return failures

        text, encoding = _read_text(path, ("utf-8", "cp932", "shift_jis"))
        _write_text(output_path, text, encoding)
        return list(range(len(lines)))

    def post_inject_project(self, project_root: Path, *, input_root: Optional[Path] = None) -> None:
        candidates = [
            Path("data") / "system" / "MainWindow.tjs",
            Path("system") / "MainWindow.tjs",
        ]
        target: Optional[Path] = None
        for relative in candidates:
            candidate = project_root / relative
            if candidate.exists():
                target = candidate
                break
        if target is None and input_root is not None:
            for relative in candidates:
                source_candidate = input_root / relative
                if source_candidate.exists():
                    target = project_root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source_candidate.read_bytes())
                    break
        if target is None:
            return

        text, encoding, bom = _read_text_with_bom(target)
        patched = _patch_add_wrap_block(_patch_add_wrap_vars(text))
        if patched == text:
            return
        if not _is_balanced(patched):
            return
        backup = target.with_suffix(target.suffix + ".bak")
        if not backup.exists():
            _write_text_with_bom(backup, text, encoding, bom)
        _write_text_with_bom(target, patched, encoding, bom)