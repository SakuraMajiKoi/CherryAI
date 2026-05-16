"""WOLF RPG parser formats for CherryAI.

Provides two ParserScript implementations based on Dazed's Wolf RPG modules:

- ``WolfRPGJsonParser`` for JSON exports containing ``events``, ``types``, or
  ``commands`` structures.
- ``WolfRPGTextParser`` for line-based WOLF script text files.

These parsers target exported or unpacked text data. Native ``.wolf`` archive
cryptography remains outside this module; the parser-level ``decrypt`` /
``encrypt`` hooks therefore act as transparent pass-throughs for already
decrypted content.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .handshake import ExtractedLine, ParserError, SpeakerInfo
from .parser_base import ForbiddenChars, ParserScript, WordwrapConfig


__all__ = ["WolfRPGJsonParser", "WolfRPGTextParser"]


TAG_CODE101 = "CODE101"
TAG_CODE102 = "CODE102"
TAG_CODE122 = "CODE122"
TAG_CODE150 = "CODE150"
TAG_CODE210 = "CODE210"
TAG_CODE250 = "CODE250"
TAG_CODE300 = "CODE300"

TAG_SCENARIO = "SCENARIOFLAG"
TAG_OPTIONS = "OPTIONSFLAG"
TAG_NPC = "NPCFLAG"
TAG_DBNAME = "DBNAMEFLAG"
TAG_DBVALUE = "DBVALUEFLAG"
TAG_ITEM = "ITEMFLAG"
TAG_STATE = "STATEFLAG"
TAG_ENEMY = "ENEMYFLAG"
TAG_ARMOR = "ARMORFLAG"
TAG_WEAPON = "WEAPONFLAG"
TAG_SKILL = "SKILLFLAG"

JSON_ENCODING_CHAIN: Tuple[str, ...] = (
    "utf-8",
    "utf-8-sig",
    "cp932",
    "shift_jis",
)
TEXT_ENCODING_CHAIN: Tuple[str, ...] = (
    "cp932",
    "shift_jis",
    "utf-8-sig",
    "utf-8",
)

TRANS_LATABLE_JA_RE = re.compile(r"[一-龠ぁ-ゔァ-ヴーａ-ｚＡ-Ｚ０-９\uFF61-\uFF9F]")
EVENT_MESSAGE_RE = re.compile(
    r"^(?:@\d+\r?\n)?(?:(?P<speaker>[^\r\n]+?)：?\r?\n)?(?P<body>[\s\S]+)$"
)
EVENT_MESSAGE_ALT_RE = re.compile(r"^(?P<speaker>[^\r\n]+?)：\r?\n(?P<body>[\s\S]+)$")
SCENARIO_SPEAKER_RE = re.compile(r"^(?P<speaker>[^\n：/]+)(?:：(?P<num>\d+))?\r?\n")
SCENARIO_COMMENT_RE = re.compile(r"^(?:(?://.*(?:\r?\n|$))+)")
DBVALUE_PREFIX_RE = re.compile(r"^(?P<prefix>(?:\\f\[\d+\].*?\r?\n)+)(?P<body>[\s\S]+)$")
TEXT_SPEAKER_RE = re.compile(r"^(?P<speaker>[^/@\r\n]+)：\s*$")


def _has_japanese(text: str) -> bool:
    return bool(TRANS_LATABLE_JA_RE.search(text))


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read_text_with_fallback(file_path: Path, encodings: Sequence[str]) -> Tuple[str, str]:
    for encoding in encodings:
        try:
            return file_path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding=encodings[-1], errors="ignore"), encodings[-1]


def _load_json_with_fallback(file_path: Path) -> Tuple[Dict[str, Any], str]:
    for encoding in JSON_ENCODING_CHAIN:
        try:
            return json.loads(file_path.read_text(encoding=encoding)), encoding
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ParserError(
        f"Failed to decode JSON WOLF file: {file_path}",
        parser_name="WolfRPGJson",
        component="extract",
    )


def _split_extracted_speaker(text: str) -> Tuple[str, str]:
    if ": " in text:
        speaker, body = text.split(": ", 1)
        return speaker, body
    return "", text


def _wrap_passthrough_lines(text: str) -> List[str]:
    normalized = _normalize_newlines(text)
    return normalized.split("\n") if normalized else [""]


def _get_nested(container: Dict[str, Any], path: Sequence[Any]) -> Any:
    value: Any = container
    for part in path:
        value = value[part]
    return value


def _set_nested(container: Dict[str, Any], path: Sequence[Any], value: Any) -> None:
    parent = _get_nested(container, path[:-1]) if path[:-1] else container
    parent[path[-1]] = value


def _clean_event_text(text: str) -> str:
    return _normalize_newlines(text).strip("\n")


def _parse_code101_payload(raw_text: str) -> Tuple[str, str]:
    normalized = _normalize_newlines(raw_text)
    match = EVENT_MESSAGE_ALT_RE.match(normalized)
    if not match:
        match = EVENT_MESSAGE_RE.match(normalized)
    if not match:
        return "", normalized.strip()
    speaker = (match.group("speaker") or "").strip()
    body = (match.group("body") or "").strip()
    if speaker and body:
        return speaker, body
    return "", normalized.strip()


def _compose_speaker_text(speaker: str, text: str) -> str:
    if speaker:
        return f"{speaker}: {text}"
    return text


def _is_event_string_literal(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if not _has_japanese(stripped):
        return False
    if re.search(r"\.[A-Za-z0-9_]+$", stripped):
        return False
    if "_" in stripped or "/" in stripped or '","' in stripped:
        return False
    return True


def _split_preserving_blank_lines(text: str) -> List[str]:
    normalized = _normalize_newlines(text)
    blocks = [block for block in re.split(r"\n\n+", normalized) if block.strip()]
    return blocks


def _parse_scenario_block(block: str) -> Tuple[str, str, str, str]:
    normalized = _normalize_newlines(block)
    prefix_match = SCENARIO_COMMENT_RE.match(normalized)
    prefix = prefix_match.group(0) if prefix_match else ""
    remainder = normalized[len(prefix):]

    if remainder.startswith("/b\n"):
        speaker_prefix = "/b\n"
        remainder = remainder[3:]
        return "NPC", remainder.strip(), prefix, speaker_prefix

    speaker_match = SCENARIO_SPEAKER_RE.match(remainder)
    if speaker_match:
        speaker = speaker_match.group("speaker").strip()
        number = speaker_match.group("num") or ""
        speaker_prefix = f"{speaker}：{number}\n" if number else f"{speaker}：\n"
        remainder = remainder[speaker_match.end():]
        return speaker, remainder.strip(), prefix, speaker_prefix

    return "", remainder.strip(), prefix, ""


def _render_scenario_block(translation: str, prefix: str, speaker_prefix: str) -> str:
    speaker, body = _split_extracted_speaker(translation)
    body = _normalize_newlines(body).strip("\n")
    if speaker_prefix.startswith("/b"):
        rendered_prefix = "/b\n"
    elif speaker_prefix:
        rendered_prefix = speaker_prefix
        if speaker:
            if re.search(r"：\d+\n$", speaker_prefix):
                number = re.search(r"：(?P<num>\d+)\n$", speaker_prefix)
                if number:
                    rendered_prefix = f"{speaker}：{number.group('num')}\n"
            else:
                rendered_prefix = f"{speaker}：\n"
    else:
        rendered_prefix = ""
    return f"{prefix}{rendered_prefix}{body}".strip("\n")


def _parse_dbvalue_payload(text: str) -> Tuple[str, str]:
    normalized = _normalize_newlines(text)
    match = DBVALUE_PREFIX_RE.match(normalized)
    if not match:
        return "", normalized.strip()
    return match.group("prefix"), match.group("body").strip()


@dataclass(frozen=True)
class _JsonUnit:
    text: str
    tag: str
    path: Tuple[Any, ...]
    unit_type: str
    speaker: str = ""
    extra: Tuple[Tuple[str, Any], ...] = ()

    def extra_dict(self) -> Dict[str, Any]:
        return dict(self.extra)


@dataclass(frozen=True)
class _TextUnit:
    text: str
    tag: str
    unit_type: str
    start_line: int
    end_line: int
    speaker_line: int = -1
    speaker: str = ""


class WolfRPGJsonParser(ParserScript):
    """Parser for WOLF RPG JSON exports based on Dazed's ``wolf.py``."""

    DIALOGUE_WRAP_TAGS = {
        TAG_CODE101,
        TAG_CODE210,
        TAG_CODE300,
        TAG_SCENARIO,
        TAG_NPC,
        TAG_OPTIONS,
        TAG_DBVALUE,
        TAG_ITEM,
        TAG_STATE,
        TAG_ENEMY,
        TAG_ARMOR,
        TAG_WEAPON,
        TAG_SKILL,
    }

    SIMPLE_DB_FIELDS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
        "アイドル": (TAG_NPC, ("出身", "説明")),
        "クイズ": (TAG_OPTIONS, ("問", "3", "4")),
        "道具": (TAG_ITEM, ("名前", "説明", "使用時文章[戦](人名~", "使用後文章[移動]")),
        "防具": (TAG_ARMOR, ("名前", "説明")),
        "敵": (TAG_ENEMY, ("敵キャラ名", "NULL")),
        "武器": (TAG_WEAPON, ("名前", "説明")),
        "技能": (TAG_SKILL, ("名前", "説明", "発動時文章", "使用時文章[戦闘](人名~", "失敗時文章[(対象)～]")),
        "ステート": (TAG_STATE, ("名前", "表示名", "付与時文章", "解除時文章", "回復時の文章[(人名)～]", "┣ ｶｳﾝﾀｰ発動文[対象～", "尻もち　行動不能　持続3ターン", "状態異常の説明")),
    }

    @property
    def name(self) -> str:
        return "WolfRPGJson"

    @property
    def display_name(self) -> str:
        return "WOLF RPG JSON"

    @property
    def tooltip(self) -> str:
        return "Parser for Dazed/WolfTL-style WOLF RPG JSON exports"

    def decrypt(self, file_path: Path) -> Path:
        return file_path

    def encrypt(self, file_path: Path) -> Path:
        return file_path

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".json" or not file_path.exists():
            return False
        try:
            data, _encoding = _load_json_with_fallback(file_path)
        except ParserError:
            return False
        return isinstance(data, dict) and any(key in data for key in ("events", "types", "commands"))

    def detect_encoding(self, file_path: Path) -> Optional[str]:
        try:
            _data, encoding = _load_json_with_fallback(file_path)
        except ParserError:
            return None
        return encoding

    @property
    def forbidden_chars(self) -> Optional[ForbiddenChars]:
        return ForbiddenChars(characters=["\t", "\r"], output_action="replace")

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(max_line_length=45, max_line_number=3, wordwrap_command="\n")

    def wordwrap_for_tag(self, tag: str) -> Optional[WordwrapConfig]:
        if tag in self.DIALOGUE_WRAP_TAGS:
            return self.wordwrap_config
        return WordwrapConfig(max_line_length=0, max_line_number=0, wordwrap_command="")

    def extract(self, file_path: Path) -> List[str]:
        return [unit.text for unit in self.extract_tagged(file_path) or []]

    def extract_tagged(self, file_path: Path) -> Optional[List[ExtractedLine]]:
        data, _encoding = _load_json_with_fallback(file_path)
        units = self._collect_units(data)
        return [
            ExtractedLine(text=unit.text, tag=unit.tag, speaker=unit.speaker)
            for unit in units
        ]

    def detect_speakers(self, lines: List[str]) -> Optional[List[SpeakerInfo]]:
        speakers: List[SpeakerInfo] = []
        seen: set[str] = set()
        for index, line in enumerate(lines):
            speaker, _body = _split_extracted_speaker(line)
            if speaker and speaker not in seen:
                speakers.append(SpeakerInfo(name=speaker, line_idx=index))
                seen.add(speaker)
        return speakers or None

    def inject(self, file_path: Path, lines: List[str]) -> None:
        self.inject_to(file_path, file_path.with_stem(file_path.stem + "_translated"), lines)

    def inject_to(
        self,
        source_path: Path,
        output_path: Path,
        lines: List[str],
        *,
        orig_lines: Optional[List[str]] = None,
    ) -> List[int]:
        data, encoding = _load_json_with_fallback(source_path)
        units = self._collect_units(data)
        search_keys = orig_lines if orig_lines is not None else [unit.text for unit in units]
        failures: List[int] = []

        for index, translated in enumerate(lines):
            if index >= len(units):
                failures.append(index)
                continue
            unit = units[index]
            search = search_keys[index] if index < len(search_keys) else unit.text
            if translated == search:
                continue
            try:
                self._apply_unit(data, unit, translated)
            except Exception as exc:
                raise ParserError(
                    f"Failed to inject WOLF JSON unit {index}: {exc}",
                    parser_name=self.name,
                    component="inject",
                ) from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=4) + "\n",
            encoding=encoding,
        )
        return failures

    def _collect_units(self, data: Dict[str, Any]) -> List[_JsonUnit]:
        units: List[_JsonUnit] = []
        if isinstance(data.get("events"), list):
            units.extend(self._collect_event_units(data["events"]))
        if isinstance(data.get("commands"), list):
            units.extend(self._collect_command_units(data["commands"], ("commands",)))
        if isinstance(data.get("types"), list):
            units.extend(self._collect_db_units(data["types"]))
        return units

    def _collect_event_units(self, events: List[Any]) -> List[_JsonUnit]:
        units: List[_JsonUnit] = []
        for event_index, event in enumerate(events):
            if not event:
                continue
            for page_index, page in enumerate(event.get("pages", [])):
                commands = page.get("list", []) if isinstance(page, dict) else []
                units.extend(
                    self._collect_command_units(
                        commands,
                        ("events", event_index, "pages", page_index, "list"),
                    )
                )
        return units

    def _collect_command_units(
        self,
        commands: List[Any],
        prefix: Tuple[Any, ...],
    ) -> List[_JsonUnit]:
        units: List[_JsonUnit] = []
        for command_index, command in enumerate(commands):
            if not isinstance(command, dict):
                continue
            code = command.get("code")
            string_args = command.get("stringArgs") or []
            int_args = command.get("intArgs") or []
            base_path = prefix + (command_index,)

            if code == 101 and string_args:
                speaker, body = _parse_code101_payload(str(string_args[0]))
                if body:
                    units.append(
                        _JsonUnit(
                            text=_compose_speaker_text(speaker, body),
                            tag=TAG_CODE101,
                            path=base_path + ("stringArgs", 0),
                            unit_type="code101",
                            speaker=speaker,
                        )
                    )
            elif code == 102:
                for choice_index, choice in enumerate(string_args):
                    if choice:
                        units.append(
                            _JsonUnit(
                                text=str(choice),
                                tag=TAG_CODE102,
                                path=base_path + ("stringArgs", choice_index),
                                unit_type="simple",
                            )
                        )
            elif code == 122 and string_args and _is_event_string_literal(str(string_args[0])):
                units.append(
                    _JsonUnit(
                        text=str(string_args[0]),
                        tag=TAG_CODE122,
                        path=base_path + ("stringArgs", 0),
                        unit_type="simple",
                    )
                )
            elif code == 150 and string_args and _has_japanese(str(string_args[0])):
                units.append(
                    _JsonUnit(
                        text=_clean_event_text(str(string_args[0])),
                        tag=TAG_CODE150,
                        path=base_path + ("stringArgs", 0),
                        unit_type="simple_multiline",
                    )
                )
            elif code == 210 and len(string_args) == 2:
                if int_args and int_args[0] == 500725:
                    units.append(
                        _JsonUnit(
                            text=_clean_event_text(str(string_args[1])),
                            tag=TAG_CODE210,
                            path=base_path + ("stringArgs", 1),
                            unit_type="simple_multiline",
                        )
                    )
                elif string_args[1]:
                    units.append(
                        _JsonUnit(
                            text=str(string_args[1]),
                            tag=TAG_CODE210,
                            path=base_path + ("stringArgs", 1),
                            unit_type="simple",
                        )
                    )
            elif code == 250 and len(string_args) == 4 and string_args[1] == "万能ｳｨﾝﾄﾞｳ一時DB" and string_args[0]:
                units.append(
                    _JsonUnit(
                        text=_clean_event_text(str(string_args[0])),
                        tag=TAG_CODE250,
                        path=base_path + ("stringArgs", 0),
                        unit_type="simple_multiline",
                    )
                )
            elif code == 300 and len(string_args) > 1:
                head = str(string_args[0])
                if head in {"[共]汎用ウィンドウ生成", "選択肢/確認"}:
                    choices = str(string_args[1]).split(",") if len(string_args) > 1 else []
                    for choice_index, choice in enumerate(choices):
                        if choice:
                            units.append(
                                _JsonUnit(
                                    text=choice,
                                    tag=TAG_CODE300,
                                    path=base_path + ("stringArgs", 1),
                                    unit_type="csv_choice",
                                    extra=(("choice_index", choice_index),),
                                )
                            )
                    if len(string_args) > 2 and string_args[2]:
                        units.append(
                            _JsonUnit(
                                text=_clean_event_text(str(string_args[2])),
                                tag=TAG_CODE300,
                                path=base_path + ("stringArgs", 2),
                                unit_type="simple_multiline",
                            )
                        )
                elif head in {"BTLメッセージ", "X[移]メニュー時文章表示"} and len(string_args) > 1 and string_args[1]:
                    units.append(
                        _JsonUnit(
                            text=_clean_event_text(str(string_args[1])),
                            tag=TAG_CODE300,
                            path=base_path + ("stringArgs", 1),
                            unit_type="simple_multiline",
                        )
                    )
                elif head == "援護文章" and len(string_args) > 1 and string_args[1]:
                    speaker, body = _parse_code101_payload(str(string_args[1]))
                    if body:
                        units.append(
                            _JsonUnit(
                                text=_compose_speaker_text(speaker, body),
                                tag=TAG_CODE300,
                                path=base_path + ("stringArgs", 1),
                                unit_type="code101",
                                speaker=speaker,
                            )
                        )
        return units

    def _collect_db_units(self, tables: List[Any]) -> List[_JsonUnit]:
        units: List[_JsonUnit] = []
        for table_index, table in enumerate(tables):
            if not isinstance(table, dict):
                continue
            table_name = str(table.get("name", ""))
            entries = table.get("data") or []

            if "デートキャラ" in table_name:
                units.extend(self._collect_scenario_units(entries, table_index))
                continue

            if table_name == "マップ設定":
                for entry_index, entry in enumerate(entries):
                    name_value = str(entry.get("name", ""))
                    if name_value:
                        units.append(
                            _JsonUnit(
                                text=name_value,
                                tag=TAG_DBNAME,
                                path=("types", table_index, "data", entry_index, "name"),
                                unit_type="simple",
                            )
                        )
                continue

            if table_name == "近況文章":
                for entry_index, entry in enumerate(entries):
                    for field_index, field in enumerate(entry.get("data", [])):
                        value = str(field.get("value", ""))
                        if not value:
                            continue
                        prefix, body = _parse_dbvalue_payload(value)
                        if body:
                            units.append(
                                _JsonUnit(
                                    text=body,
                                    tag=TAG_DBVALUE,
                                    path=("types", table_index, "data", entry_index, "data", field_index, "value"),
                                    unit_type="dbvalue",
                                    extra=(("prefix", prefix),),
                                )
                            )
                continue

            spec = self.SIMPLE_DB_FIELDS.get(table_name)
            if spec is None:
                continue
            tag, field_names = spec
            for entry_index, entry in enumerate(entries):
                for field_index, field in enumerate(entry.get("data", [])):
                    field_name = str(field.get("name", ""))
                    if field_name not in field_names:
                        continue
                    value = str(field.get("value", ""))
                    if value:
                        units.append(
                            _JsonUnit(
                                text=_clean_event_text(value),
                                tag=tag,
                                path=("types", table_index, "data", entry_index, "data", field_index, "value"),
                                unit_type="simple_multiline",
                            )
                        )
        return units

    def _collect_scenario_units(self, entries: List[Any], table_index: int) -> List[_JsonUnit]:
        units: List[_JsonUnit] = []
        field_names = {"NULL", "不正解会話", "正解会話"}
        for entry_index, entry in enumerate(entries):
            for field_index, field in enumerate(entry.get("data", [])):
                if str(field.get("name", "")) not in field_names:
                    continue
                value = str(field.get("value", ""))
                if not value:
                    continue
                for block_index, block in enumerate(_split_preserving_blank_lines(value)):
                    speaker, body, prefix, speaker_prefix = _parse_scenario_block(block)
                    if not body:
                        continue
                    units.append(
                        _JsonUnit(
                            text=_compose_speaker_text(speaker, body),
                            tag=TAG_SCENARIO,
                            path=("types", table_index, "data", entry_index, "data", field_index, "value"),
                            unit_type="scenario_block",
                            speaker=speaker,
                            extra=(("block_index", block_index), ("prefix", prefix), ("speaker_prefix", speaker_prefix)),
                        )
                    )
        return units

    def _apply_unit(self, data: Dict[str, Any], unit: _JsonUnit, translation: str) -> None:
        if unit.unit_type == "simple":
            _set_nested(data, unit.path, translation)
            return

        if unit.unit_type == "simple_multiline":
            _set_nested(data, unit.path, _normalize_newlines(translation))
            return

        if unit.unit_type == "code101":
            original = str(_get_nested(data, unit.path))
            original_speaker, _original_body = _parse_code101_payload(original)
            translated_speaker, translated_body = _split_extracted_speaker(translation)
            if not translated_speaker:
                translated_speaker = original_speaker
            if original.startswith("@") and "\n" in original:
                first_break = original.find("\n")
                prefix = original[: first_break + 1]
                rendered = prefix
            else:
                rendered = ""
            if translated_speaker:
                rendered += f"{translated_speaker}：\n{_normalize_newlines(translated_body)}"
            else:
                rendered += _normalize_newlines(translated_body)
            _set_nested(data, unit.path, rendered)
            return

        if unit.unit_type == "csv_choice":
            extra = unit.extra_dict()
            choice_index = int(extra.get("choice_index", 0))
            raw = str(_get_nested(data, unit.path))
            parts = raw.split(",")
            if choice_index < len(parts):
                parts[choice_index] = translation.replace(", ", "、")
                _set_nested(data, unit.path, ",".join(parts))
            return

        if unit.unit_type == "dbvalue":
            extra = unit.extra_dict()
            prefix = str(extra.get("prefix", ""))
            rendered = f"{prefix}{_normalize_newlines(translation)}" if prefix else _normalize_newlines(translation)
            _set_nested(data, unit.path, rendered)
            return

        if unit.unit_type == "scenario_block":
            extra = unit.extra_dict()
            block_index = int(extra.get("block_index", 0))
            prefix = str(extra.get("prefix", ""))
            speaker_prefix = str(extra.get("speaker_prefix", ""))
            raw_value = str(_get_nested(data, unit.path))
            blocks = _split_preserving_blank_lines(raw_value)
            if block_index < len(blocks):
                blocks[block_index] = _render_scenario_block(translation, prefix, speaker_prefix)
                _set_nested(data, unit.path, "\n\n".join(blocks))
            return

        raise ParserError(
            f"Unknown WOLF JSON unit type: {unit.unit_type}",
            parser_name=self.name,
            component="inject",
        )


class WolfRPGTextParser(ParserScript):
    """Parser for line-based WOLF text scripts based on Dazed's ``wolf2.py``."""

    TAG_DIALOGUE = "WOLF2_DIALOGUE"
    TAG_CHOICE = "WOLF2_CHOICE"

    @property
    def name(self) -> str:
        return "WolfRPGText"

    @property
    def display_name(self) -> str:
        return "WOLF RPG Text"

    @property
    def tooltip(self) -> str:
        return "Parser for Dazed-style line-based WOLF text scripts"

    def decrypt(self, file_path: Path) -> Path:
        return file_path

    def encrypt(self, file_path: Path) -> Path:
        return file_path

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".txt" or not file_path.exists():
            return False
        text, _encoding = _read_text_with_fallback(file_path, TEXT_ENCODING_CHAIN)
        lines = _normalize_newlines(text).split("\n")
        if any(line.startswith("//選択肢") for line in lines):
            return True
        if any(TEXT_SPEAKER_RE.match(line) for line in lines):
            return True
        return False

    def detect_encoding(self, file_path: Path) -> Optional[str]:
        _text, encoding = _read_text_with_fallback(file_path, TEXT_ENCODING_CHAIN)
        return encoding

    @property
    def forbidden_chars(self) -> Optional[ForbiddenChars]:
        return ForbiddenChars(characters=["\t", "\r"], output_action="replace")

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(max_line_length=45, max_line_number=3, wordwrap_command="\n")

    def wordwrap_for_tag(self, tag: str) -> Optional[WordwrapConfig]:
        if tag == self.TAG_DIALOGUE:
            return self.wordwrap_config
        return WordwrapConfig(max_line_length=0, max_line_number=0, wordwrap_command="")

    def extract(self, file_path: Path) -> List[str]:
        return [unit.text for unit in self.extract_tagged(file_path) or []]

    def extract_tagged(self, file_path: Path) -> Optional[List[ExtractedLine]]:
        text, _encoding = _read_text_with_fallback(file_path, TEXT_ENCODING_CHAIN)
        units = self._collect_units(_normalize_newlines(text).split("\n"))
        return [
            ExtractedLine(text=unit.text, tag=unit.tag, speaker=unit.speaker)
            for unit in units
        ]

    def detect_speakers(self, lines: List[str]) -> Optional[List[SpeakerInfo]]:
        speakers: List[SpeakerInfo] = []
        seen: set[str] = set()
        for index, line in enumerate(lines):
            speaker, _body = _split_extracted_speaker(line)
            if speaker and speaker not in seen:
                speakers.append(SpeakerInfo(name=speaker, line_idx=index))
                seen.add(speaker)
        return speakers or None

    def inject(self, file_path: Path, lines: List[str]) -> None:
        self.inject_to(file_path, file_path.with_stem(file_path.stem + "_translated"), lines)

    def inject_to(
        self,
        source_path: Path,
        output_path: Path,
        lines: List[str],
        *,
        orig_lines: Optional[List[str]] = None,
    ) -> List[int]:
        text, encoding = _read_text_with_fallback(source_path, TEXT_ENCODING_CHAIN)
        raw_lines = _normalize_newlines(text).split("\n")
        units = self._collect_units(raw_lines)
        search_keys = orig_lines if orig_lines is not None else [unit.text for unit in units]
        failures: List[int] = []

        for index, translated in enumerate(lines):
            if index >= len(units):
                failures.append(index)
                continue
            unit = units[index]
            search = search_keys[index] if index < len(search_keys) else unit.text
            if translated == search:
                continue
            if unit.unit_type == "choice":
                raw_lines[unit.start_line] = f"//{translated}"
                continue

            translated_speaker, translated_body = _split_extracted_speaker(translated)
            if unit.speaker_line >= 0 and translated_speaker:
                raw_lines[unit.speaker_line] = f"{translated_speaker}："
            body_lines = _wrap_passthrough_lines(translated_body if translated_body or translated_speaker else translated)
            replacement = [line for line in body_lines if line != ""] or [""]
            raw_lines[unit.start_line : unit.end_line + 1] = replacement

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(raw_lines), encoding=encoding, errors="ignore")
        return failures

    def _collect_units(self, lines: List[str]) -> List[_TextUnit]:
        units: List[_TextUnit] = []
        index = 0
        current_speaker = ""
        current_speaker_line = -1

        while index < len(lines):
            line = lines[index]
            speaker_match = TEXT_SPEAKER_RE.match(line)
            if speaker_match:
                current_speaker = speaker_match.group("speaker").strip()
                current_speaker_line = index
                index += 1
                continue

            if line == "//選択肢":
                index += 1
                while index < len(lines) and lines[index].startswith("//") and "の場合" not in lines[index]:
                    units.append(
                        _TextUnit(
                            text=lines[index][2:],
                            tag=self.TAG_CHOICE,
                            unit_type="choice",
                            start_line=index,
                            end_line=index,
                        )
                    )
                    index += 1
                current_speaker = ""
                current_speaker_line = -1
                continue

            if line and "/" not in line and "@" not in line:
                start = index
                body_lines = [line]
                index += 1
                while index < len(lines) and lines[index] and "/" not in lines[index] and "@" not in lines[index]:
                    body_lines.append(lines[index])
                    index += 1
                body = "\n".join(body_lines)
                units.append(
                    _TextUnit(
                        text=_compose_speaker_text(current_speaker, body) if current_speaker else body,
                        tag=self.TAG_DIALOGUE,
                        unit_type="dialogue",
                        start_line=start,
                        end_line=index - 1,
                        speaker_line=current_speaker_line,
                        speaker=current_speaker,
                    )
                )
                continue

            if not line.strip():
                current_speaker = ""
                current_speaker_line = -1
            index += 1

        return units
