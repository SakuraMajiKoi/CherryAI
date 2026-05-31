"""RPG Maker MV/MZ parser and format handlers for CherryAI.

The MV and MZ JSON handlers parse standard data files plus event command
lists.  Dialogue is extracted as ``Speaker: Dialogue`` when the speaker is
known and injected back into the original speaker representation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import FormatHandler
from .handshake import ExtractedLine, ParserError, SpeakerInfo
from .parser_base import ForbiddenChars, ParserScript, TagRules, WordwrapConfig


__all__ = [
    "RpgMakerMVHandler",
    "RpgMakerMZHandler",
    "RpgMakerMVParser",
    "RpgMakerMZParser",
    "RpgMakerPluginHandler",
    "get_handlers",
]


JSON_ENCODING_CHAIN: Tuple[str, ...] = (
    "utf-8",
    "utf-8-sig",
    "cp932",
    "shift_jis",
)

STANDARD_FIELD_TAGS: Dict[str, str] = {
    "name": "name",
    "nickname": "nickname",
    "profile": "profile",
    "description": "description",
    "message1": "message1",
    "message2": "message2",
    "message3": "message3",
    "message4": "message4",
    "displayName": "displayName",
    "text": "text",
}

COMMAND_TEXT_PARAM: Dict[int, int] = {
    320: 1,  # Change Name
    324: 1,  # Change Nickname
    325: 1,  # Change Profile
}

QUOTE_RE = re.compile(
    r"(?P<quote>['\"])(?P<value>(?:\\.|(?!\1).)*?)(?P=quote)"
)
PLUGIN_ANNOTATION_RE = re.compile(
    r"(?m)^(?P<prefix>\s*\*\s*@(?P<kind>text|desc|default)\s+)(?P<value>.+?)\s*$"
)
PLUGIN_ASSIGNMENT_RE = re.compile(
    r"(?P<prefix>\b(?:name|text|title|description|message|caption|label)\b\s*[:=]\s*)"
    r"(?P<quote>['\"])(?P<value>(?:\\.|(?!\2).)*?)(?P=quote)",
    re.IGNORECASE,
)
SPEAKER_PREFIX_RE = re.compile(
    r"^(?P<prefix>\\[Nn](?:ame|c)?<(?P<speaker>[^>]+)>)(?P<body>[\s\S]*)$"
)
COLON_SPEAKER_RE = re.compile(
    r"^(?P<speaker>[^\n:：]{1,48})(?P<sep>\s*[:：]\s*)(?P<body>[\s\S]+)$"
)
BRACKET_SPEAKER_RE = re.compile(
    r"^(?P<open>[【\[])(?P<speaker>[^】\]\n]{1,48})(?P<close>[】\]])"
    r"(?P<sep>\s*)(?P<body>[\s\S]*)$"
)
TEXTY_RE = re.compile(r"[A-Za-z\u00C0-\uFFFF]")

SCENE_PATTERN = r"^={3,}|^---\s*(?:Scene|Map)\b"
DIALOGUE_PATTERN = r"^\\[Nn]\[[^\]]+\]"
MENU_PATTERN = r"^\\[Cc]\[\d+\]"
CHOICE_PATTERN = r"^\d+[\.\)]\s"

PLUGIN_357_KEYS: Dict[str, Tuple[str, ...]] = {
    "LL_InfoPopupWIndow": ("messageText",),
    "QuestSystem": ("DetailNote",),
    "BalloonInBattle": ("text",),
    "MNKR_CommonPopupCoreMZ": ("text",),
    "DestinationWindow": ("destination",),
    "_TMLogWindowMZ": ("text",),
    "TorigoyaMZ_NotifyMessage": ("message",),
    "SoR_GabWindow": ("arg1",),
    "DarkPlasma_CharacterText": ("text",),
    "DTextPicture": ("text",),
    "TextPicture": ("text",),
    "TRP_SkitMZ": ("name",),
    "LogWindow": ("text",),
    "BattleLogOutput": ("message",),
    "TorigoyaMZ_NotifyMessage_CommandMessage": ("message",),
    "NUUN_SaveScreen": ("AnyName",),
    "build/ARPG_Core": ("Text", "SkillByName"),
    "EventLabel": ("text",),
    "KN_MapBattle": ("enemyName",),
    "KN_Shop": ("goodsType",),
    "KN_StillManager": ("label",),
    "Mano_CurrencyUnit": ("unit",),
    "SceneGlossary": ("category",),
}

CODE108_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("info", re.compile(r"info:([^,]+)")),
    ("ActiveMessage", re.compile(r"<ActiveMessage:([^>]*)>?")),
    ("event_text", re.compile(r"event_text\s*:\s*(.*)")),
    ("Menu", re.compile(r"Menu\sName\s*:\s*(.*)>")),
    ("text_indicator", re.compile(r"text_indicator\s?:\s?(.+)")),
    ("NW", re.compile(r"NW名前指定\s+(.+)")),
)

CODE356_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("dtext", re.compile(r"D_TEXT\s*(.+?)(?:\s+\d+)?$")),
    ("showinfo", re.compile(r"ShowInfo\s(.*)")),
    ("pushgab", re.compile(r"PushGab\s(.*)")),
    ("addlog", re.compile(r"addLog\s(.*)")),
    ("dw", re.compile(r"DW_.*\s\d+\s(.+)")),
    ("commonpopup", re.compile(r"CommonPopup\sadd\stext:(.+?)(?=\s+count:|\s*$)")),
    ("customchoice", re.compile(r"AddCustomChoice\s\d+\s(.+)\s\d")),
    ("namepop", re.compile(r"<namePop:\s*([^>]+)>")),
    ("namepop", re.compile(r"\bnamePop\b\s*(?:-?\d+)?\s*([^\r\n<>]+)")),
    ("infopopup", re.compile(r"LL_InfoPopupWIndowMV\sshowWindow\s(.+?) .+")),
    ("origin", re.compile(r"OriginMenuStatus\sSetParam\sparam[\d]\s(.*)")),
    ("galge", re.compile(r"LL_GalgeChoiceWindowMV setMessageText (.+)")),
)

CODE355_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("テキスト", re.compile(r"テキスト-(.+)")),
    ("equals", re.compile(r'=\s?(.*)",')),
    ("vartext", re.compile(r'var\stext\d+\s=\s\"(.+)\"')),
    ("logtxt", re.compile(r"logtxt\s=\s'(.+)'")),
    ("nickname", re.compile(r'.setNickname\(\\?"(.+?)\\?"\)')),
    ("subject", re.compile(r'_subject=(.+?)(?=[_\\"\]])')),
    ("text", re.compile(r"text\s*=\s*'(.+[^\\])'")),
    ("const", re.compile(r'const\stext\s?=\s?"(.+)";?')),
    ("exaname", re.compile(r'ex_a_name\(\d+,"(.+)"\)')),
    ("gamevariables", re.compile(r'\$gameVariables\.setValue\(\d+,\s*"([^"]*)"\)')),
    ("gamevariables", re.compile(r"\$gameVariables\._data(?:\[[^\]]+\])+\s*=\s*['\"]((?:\\.|[^'\"\\])*)['\"]")),
    ("message", re.compile(r"\$gameMessage\.add\(.+?\)(.+?)")),
    ("battlelog", re.compile(r"BattleManager\._logWindow\.push\('addText',\s'(.+)'\)")),
    ("battlelog", re.compile(r"BattleManager\._logWindow\.addText\(\s*(?:(?:[^()]|\([^)]*\))*\+\s*)?(['\"])((?:\\.|(?!\1).)*)\1\s*\)")),
    ("out", re.compile(r"let\s+out\d+\s*=\s*\(.+?\)(.+?)")),
    ("moji", re.compile(r"(?:let\s+)?moji\s*\+?=\s*(.+)")),
    ("blog", re.compile(r'this\.BLogAdd\?.*?\\?"(.+?)\\?"\)')),
    ("fuki", re.compile(r'Fuki_Set\([\s,\d\w\W]+?"(.+?)",')),
    ("eventsetting", re.compile(r'_EventSetting[\s,\d\w\W]+?"(.+?)";')),
    ("menu", re.compile(r'this\.Menu_SexTxtSet\((.+)\)')),
    ("result", re.compile(r"Rn_RsltTxtArr.+?\"(.+)\"")),
    ("chapter", re.compile(r'_章切り替えStart\(\s*\\?"\s?,?.+?\\?"\s?,?\s?\\?"(.+?)\\?"')),
    ("skilllog", re.compile(r'SkillLogAdd\((?:.+?\+\s*)?\\?"(?:\\\\+[A-Za-z]\[\d+\])?(.+?)\\?"')),
    ("mobname", re.compile(r'MobNameSet\(\\?"(.+?)\\?"\)')),
    ("address", re.compile(r'AddAddress\(\d+,\s*\\?"(.+?)\\?"')),
)

PLUGIN_JS_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("questname", re.compile(r'[\\]+"QuestName[\\]+":[\\]+"(.*?)[\\]+"')),
    ("questclient", re.compile(r'QuestClientName[\\]+":[\\]+"(.*?)[\\]+"')),
    ("questlocation", re.compile(r'QuestLocation[\\]+":[\\]+"(.*?)[\\]+"')),
    ("place", re.compile(r'PlaceInformation[\\]+":[\\]+"(.*?)[\\]+"')),
    ("questcontent", re.compile(r'[\\]+"QuestContent[\\]+":[\\]+"[\\]+"(.*?)[\\]+"[\\]+"')),
    ("objective", re.compile(r'ObjectiveContent[\\]+":[\\]+"[\\]+"(.*?)[\\]+"')),
    ("text", re.compile(r'[\\]+"Text[\\]+":[\\]+"(.+?)[\\]+"')),
    ("commonhelp", re.compile(r'[\\]+"CommonHelpText[\\]+":[\\]+"(.+?)[\\]+"')),
    ("help", re.compile(r'[\\]+"HelpText[\\]+":[\\]+"(.+?)[\\]+"')),
    ("param", re.compile(r'[\\]+"ParamName[\\]+":[\\]+"(.+?)[\\]+"')),
    ("subject", re.compile(r'txtSubject.+?"(.+)"')),
    ("drawlabel", re.compile(r'[\\]+\}(.+?)[\\]+\{')),
    ("stat", re.compile(r'C\[\d+\]([^C\\,`\[\]]+?)[\\]+C\[0\]')),
)

NOTE_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("note", re.compile(r"<note:(.*?)>", re.DOTALL)),
    ("pe", re.compile(r"<PE拡張:(.*?)>", re.DOTALL)),
    ("hint", re.compile(r"<[Hh]int:(.*?)>", re.DOTALL)),
    ("sg", re.compile(r"<SGDescription:(.*?)>", re.DOTALL)),
    ("sg", re.compile(r"<SG説明:\n?(.*?)>", re.DOTALL)),
    ("sg2", re.compile(r"<SG説明2:\n?(.*?)>", re.DOTALL)),
    ("sg3", re.compile(r"<SG説明3:\n?(.*?)>", re.DOTALL)),
    ("sg4", re.compile(r"<SG説明4:\n?(.*?)>", re.DOTALL)),
    ("category", re.compile(r"<SGカテゴリ:(.*?)>", re.DOTALL)),
    ("switchshop", re.compile(r"<Switch Shop Description>\n(.*)\n", re.DOTALL)),
    ("maptext", re.compile(r"<MapText:(.*?)>", re.DOTALL)),
    ("wats", re.compile(r"WATs:(.+?)>", re.DOTALL)),
    ("adts", re.compile(r"ADTs?:(.+?)>", re.DOTALL)),
    ("detail", re.compile(r"<detail:(.*?)>", re.DOTALL)),
    ("name", re.compile(r"<Name:(.*?)>", re.DOTALL)),
    ("sub1", re.compile(r"<sub_1:([^>]+)", re.DOTALL)),
    ("sub2", re.compile(r"<sub_2:([^>]+)", re.DOTALL)),
    ("sub3", re.compile(r"<sub_3:([^>]+)", re.DOTALL)),
    ("infowindow", re.compile(r"<infowindow:(.*?)>", re.DOTALL)),
    ("extenddesc", re.compile(r"<ExtendDesc:(.*?)>", re.DOTALL)),
    ("desc", re.compile(r"<desc\d:(.*?)>", re.DOTALL)),
    ("extenddesc", re.compile(r"<拡張説明:(.+?)>", re.DOTALL)),
    ("sts", re.compile(r"<STS DESC>\n(.+?)\n<", re.DOTALL)),
    ("text", re.compile(r"text:(.+)>", re.DOTALL)),
    ("skill", re.compile(r"<Skill\d+:(?:\d+,)?([^,>\d][^,>]*)", re.DOTALL)),
    ("classmessage", re.compile(r"<ClassMessage>\n?(.*?)</ClassMessage>", re.DOTALL)),
    ("comment", re.compile(r"<コメント:\n?(.*?)>", re.DOTALL)),
)


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read_json_with_fallback(path: Path, encoding: str = "utf-8") -> Tuple[Any, str]:
    if not path.exists():
        raise ParserError(
            f"RPG Maker JSON file not found: {path}",
            parser_name="RPGMaker",
            component="extract",
        )
    encodings = (encoding,) + tuple(e for e in JSON_ENCODING_CHAIN if e != encoding)
    last_error: Optional[Exception] = None
    for enc in encodings:
        try:
            return json.loads(path.read_text(encoding=enc)), enc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
    raise ParserError(
        f"Failed to decode RPG Maker JSON file {path}: {last_error}",
        parser_name="RPGMaker",
        component="extract",
    )


def _get_nested(container: Any, path: Sequence[Any]) -> Any:
    value = container
    for part in path:
        value = value[part]
    return value


def _set_nested(container: Any, path: Sequence[Any], value: Any) -> None:
    parent = _get_nested(container, path[:-1]) if path[:-1] else container
    parent[path[-1]] = value


def _is_translatable_string(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if not TEXTY_RE.search(stripped):
        return False
    if re.fullmatch(r"[\w./:-]+\.(?:png|jpg|ogg|m4a|json|js|rpgmvp|rpgmvo)", stripped, re.I):
        return False
    return True


def _plugin_word(*parts: str) -> str:
    for part in parts:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", part).strip("_")
        if cleaned:
            return cleaned.split("_", 1)[0].lower()
    return "plugin"


def _compose_speaker_text(speaker: str, body: str) -> str:
    return f"{speaker}: {body}" if speaker else body


def _split_speaker_text(text: str) -> Tuple[str, str]:
    match = COLON_SPEAKER_RE.match(text)
    if match:
        return match.group("speaker").strip(), match.group("body")
    return "", text


@dataclass(frozen=True)
class _SpeakerStyle:
    kind: str = ""
    prefix: str = ""
    sep: str = ""
    open_bracket: str = ""
    close_bracket: str = ""


@dataclass
class _JsonUnit:
    text: str
    tag: str
    unit_type: str
    path: Tuple[Any, ...] = ()
    speaker: str = ""
    speaker_path: Tuple[Any, ...] = ()
    line_paths: List[Tuple[Any, ...]] = field(default_factory=list)
    style: _SpeakerStyle = field(default_factory=_SpeakerStyle)
    quote_index: int = 0
    choice_index: int = -1
    plugin_name: str = ""
    pattern: str = ""


def _parse_speaker(body: str, fallback: str = "") -> Tuple[str, str, _SpeakerStyle]:
    text = _normalize_newlines(body)
    match = SPEAKER_PREFIX_RE.match(text)
    if match:
        return (
            match.group("speaker").strip(),
            match.group("body").lstrip("\n"),
            _SpeakerStyle(kind="prefix", prefix=match.group("prefix")),
        )

    match = BRACKET_SPEAKER_RE.match(text)
    if match:
        return (
            match.group("speaker").strip(),
            match.group("body").lstrip(),
            _SpeakerStyle(
                kind="bracket",
                sep=match.group("sep"),
                open_bracket=match.group("open"),
                close_bracket=match.group("close"),
            ),
        )

    match = COLON_SPEAKER_RE.match(text)
    if match and "\\" not in match.group("speaker"):
        return (
            match.group("speaker").strip(),
            match.group("body"),
            _SpeakerStyle(kind="colon", sep=match.group("sep")),
        )

    if fallback:
        return fallback.strip(), text, _SpeakerStyle(kind="param")
    return "", text, _SpeakerStyle()


def _render_dialogue_text(
    unit: _JsonUnit,
    translation: str,
) -> Tuple[str, str]:
    translated_speaker, translated_body = _split_speaker_text(translation)
    speaker = translated_speaker or unit.speaker
    body = _normalize_newlines(translated_body if translated_speaker else translation)

    if unit.style.kind == "prefix":
        return speaker, f"{unit.style.prefix}{body}"
    if unit.style.kind == "bracket":
        return speaker, (
            f"{unit.style.open_bracket}{speaker}{unit.style.close_bracket}"
            f"{unit.style.sep}{body}"
        )
    if unit.style.kind == "colon":
        return speaker, f"{speaker}{unit.style.sep}{body}"
    return speaker, body


def _split_for_existing_lines(text: str, count: int) -> List[str]:
    parts = _normalize_newlines(text).split("\n")
    if count <= 1:
        return ["\n".join(parts)]
    if len(parts) <= count:
        return parts + [""] * (count - len(parts))
    return parts[: count - 1] + ["\n".join(parts[count - 1:])]


def _decode_js_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except Exception:
        return value


def _encode_js_string(value: str, quote: str) -> str:
    encoded = json.dumps(value, ensure_ascii=False)[1:-1]
    if quote == "'":
        encoded = encoded.replace("'", "\\'")
    return encoded


class _RpgMakerJsonCore:
    parser_name = "RPGMaker"

    def _collect_units(self, data: Any) -> List[_JsonUnit]:
        units: List[_JsonUnit] = []
        self._walk(data, (), units)
        return units

    def _walk(self, value: Any, path: Tuple[Any, ...], units: List[_JsonUnit]) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("list"), list):
                self._collect_command_list(value["list"], path + ("list",), units)

            for key, item in value.items():
                if key == "list":
                    continue
                child_path = path + (key,)
                if isinstance(item, str) and key == "note":
                    self._collect_note_units(item, child_path, units)
                elif isinstance(item, str) and key in STANDARD_FIELD_TAGS and _is_translatable_string(item):
                    units.append(
                        _JsonUnit(
                            text=item,
                            tag=STANDARD_FIELD_TAGS[key],
                            unit_type="simple",
                            path=child_path,
                        )
                    )
                elif isinstance(item, (dict, list)):
                    self._walk(item, child_path, units)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if item is not None:
                    self._walk(item, path + (index,), units)

    def _collect_note_units(
        self,
        note: str,
        path: Tuple[Any, ...],
        units: List[_JsonUnit],
    ) -> None:
        matched = False
        for tag, pattern in NOTE_PATTERNS:
            for match in pattern.finditer(note):
                text = match.group(1)
                if isinstance(text, tuple):
                    text = text[0]
                if _is_translatable_string(str(text)):
                    units.append(
                        _JsonUnit(
                            text=str(text),
                            tag=tag,
                            unit_type="string_replace",
                            path=path,
                        )
                    )
                    matched = True
        if not matched and _is_translatable_string(note):
            units.append(_JsonUnit(text=note, tag="note", unit_type="simple", path=path))

    def _collect_command_list(
        self,
        commands: List[Any],
        path: Tuple[Any, ...],
        units: List[_JsonUnit],
    ) -> None:
        index = 0
        recent_choices: set[str] = set()
        while index < len(commands):
            command = commands[index]
            if not isinstance(command, dict):
                index += 1
                continue
            code = command.get("code")
            params = command.get("parameters") or []

            if code in (101, 401):
                index = self._collect_dialogue(commands, path, index, units)
                continue

            if code == 102 and params and isinstance(params[0], list):
                recent_choices = {str(choice) for choice in params[0]}
                for choice_index, choice in enumerate(params[0]):
                    if _is_translatable_string(str(choice)):
                        units.append(
                            _JsonUnit(
                                text=str(choice),
                                tag="102",
                                unit_type="choice_array",
                                path=path + (index, "parameters", 0),
                                choice_index=choice_index,
                            )
                        )
            elif code == 402 and len(params) > 1 and str(params[1]) not in recent_choices:
                if _is_translatable_string(str(params[1])):
                    units.append(
                        _JsonUnit(
                            text=str(params[1]),
                            tag="402",
                            unit_type="simple",
                            path=path + (index, "parameters", 1),
                        )
                    )
            elif code == 405:
                line_paths: List[Tuple[Any, ...]] = []
                lines: List[str] = []
                start = index
                while index < len(commands):
                    current = commands[index]
                    current_params = current.get("parameters") if isinstance(current, dict) else None
                    if not isinstance(current, dict) or current.get("code") != 405 or not current_params:
                        break
                    lines.append(str(current_params[0]))
                    line_paths.append(path + (index, "parameters", 0))
                    index += 1
                text = "\n".join(lines)
                if _is_translatable_string(text):
                    units.append(
                        _JsonUnit(
                            text=text,
                            tag="405",
                            unit_type="multiline",
                            line_paths=line_paths,
                        )
                    )
                if index > start:
                    continue
            elif code == 408 and params:
                line_paths: List[Tuple[Any, ...]] = []
                lines: List[str] = []
                start = index
                while index < len(commands):
                    current = commands[index]
                    current_params = current.get("parameters") if isinstance(current, dict) else None
                    if not isinstance(current, dict) or current.get("code") != 408 or not current_params:
                        break
                    lines.append(str(current_params[0]))
                    line_paths.append(path + (index, "parameters", 0))
                    index += 1
                text = "\n".join(lines)
                if _is_translatable_string(text):
                    units.append(
                        _JsonUnit(
                            text=text,
                            tag="408",
                            unit_type="multiline",
                            line_paths=line_paths,
                        )
                    )
                if index > start:
                    continue
            elif code == 122 and len(params) > 4:
                self._collect_quoted_assignment(
                    str(params[4]),
                    path + (index, "parameters", 4),
                    "122",
                    units,
                )
            elif code in COMMAND_TEXT_PARAM:
                param_index = COMMAND_TEXT_PARAM[int(code)]
                if len(params) > param_index and _is_translatable_string(str(params[param_index])):
                    units.append(
                        _JsonUnit(
                            text=str(params[param_index]),
                            tag=str(code),
                            unit_type="simple",
                            path=path + (index, "parameters", param_index),
                        )
                    )
            elif code in (355, 655) and params:
                self._collect_script_patterns(
                    str(params[0]),
                    path + (index, "parameters", 0),
                    str(code),
                    units,
                )
            elif code == 356 and params:
                self._collect_command_356(
                    str(params[0]),
                    path + (index, "parameters", 0),
                    units,
                )
            elif code == 357 and len(params) > 3:
                plugin = str(params[0] or "")
                command_name = str(params[1] or "")
                args = params[3]
                if isinstance(args, dict):
                    self._collect_plugin_args(args, path + (index, "parameters", 3), _plugin_word(plugin, command_name), units, plugin)
                if (
                    plugin == "KN_StillManager"
                    and len(params) > 2
                    and params[1] == "OPEN_GALLERY"
                    and isinstance(params[2], str)
                    and _is_translatable_string(params[2])
                ):
                    units.append(
                        _JsonUnit(
                            text=params[2],
                            tag="kn",
                            unit_type="simple",
                            path=path + (index, "parameters", 2),
                        )
                    )
            elif code == 657 and params:
                self._collect_code_657(
                    str(params[0]),
                    path + (index, "parameters", 0),
                    units,
                )
            elif code == 108 and params:
                self._collect_command_108(
                    str(params[0]),
                    path + (index, "parameters", 0),
                    units,
                )
            elif code == 111 and params:
                for param_index, param in enumerate(params):
                    if isinstance(param, str) and "$gameVariables" in param:
                        self._collect_script_quotes(
                            param,
                            path + (index, "parameters", param_index),
                            "111",
                            units,
                        )

            recent_choices = set() if code not in (102, 402) else recent_choices
            index += 1

    def _collect_dialogue(
        self,
        commands: List[Any],
        path: Tuple[Any, ...],
        index: int,
        units: List[_JsonUnit],
    ) -> int:
        header = commands[index] if isinstance(commands[index], dict) else {}
        header_params = header.get("parameters") or []
        speaker = str(header_params[4]).strip() if header.get("code") == 101 and len(header_params) > 4 else ""
        speaker_path = path + (index, "parameters", 4) if speaker else ()

        if header.get("code") == 101:
            index += 1

        line_paths: List[Tuple[Any, ...]] = []
        lines: List[str] = []
        while index < len(commands):
            current = commands[index]
            current_params = current.get("parameters") if isinstance(current, dict) else None
            if not isinstance(current, dict) or current.get("code") != 401 or not current_params:
                break
            lines.append(str(current_params[0]))
            line_paths.append(path + (index, "parameters", 0))
            index += 1

        if not lines:
            return index

        raw_text = "\n".join(lines)
        parsed_speaker, body, style = _parse_speaker(raw_text, speaker)
        if _is_translatable_string(body):
            units.append(
                _JsonUnit(
                    text=_compose_speaker_text(parsed_speaker, body),
                    tag="401",
                    unit_type="dialogue",
                    speaker=parsed_speaker,
                    speaker_path=speaker_path,
                    line_paths=line_paths,
                    style=style,
                )
            )
        return index

    def _collect_plugin_args(
        self,
        value: Any,
        path: Tuple[Any, ...],
        tag: str,
        units: List[_JsonUnit],
        plugin: str = "",
    ) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                if (
                    key_text == "Text:json"
                    and isinstance(item, str)
                    and self._collect_text_json(item, path + (key,), tag, units)
                ):
                    continue
                if plugin in PLUGIN_357_KEYS and key_text not in PLUGIN_357_KEYS[plugin]:
                    if isinstance(item, (dict, list)):
                        self._collect_plugin_args(item, path + (key,), tag, units, plugin)
                    continue
                self._collect_plugin_args(item, path + (key,), tag, units, plugin)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                self._collect_plugin_args(item, path + (index,), tag, units, plugin)
        elif isinstance(value, str) and _is_translatable_string(value):
            units.append(_JsonUnit(text=value, tag=tag, unit_type="simple", path=path))

    def _collect_text_json(
        self,
        raw: str,
        path: Tuple[Any, ...],
        tag: str,
        units: List[_JsonUnit],
    ) -> bool:
        inner_match = re.match(r'^"(.*)"$', raw, re.DOTALL)
        inner = inner_match.group(1) if inner_match else raw
        prefix_match = re.match(r'^((?:\\\\[{}])+)', inner)
        prefix = prefix_match.group(1) if prefix_match else ""
        remaining = inner[len(prefix):]
        suffix_match = re.search(r'((?:\\\\[{}])+)$', remaining)
        suffix = suffix_match.group(1) if suffix_match else ""
        text = remaining[: len(remaining) - len(suffix)] if suffix else remaining
        if not _is_translatable_string(text):
            return False
        units.append(_JsonUnit(text=text, tag=tag, unit_type="string_replace", path=path))
        return True

    def _collect_quoted_assignment(
        self,
        text: str,
        path: Tuple[Any, ...],
        tag: str,
        units: List[_JsonUnit],
    ) -> None:
        match = re.search(r"[\'\"\`](.*)[\'\"\`]", text)
        if match and _is_translatable_string(match.group(1)):
            units.append(
                _JsonUnit(
                    text=match.group(1),
                    tag=tag,
                    unit_type="string_replace",
                    path=path,
                )
            )

    def _collect_code_657(
        self,
        text: str,
        path: Tuple[Any, ...],
        units: List[_JsonUnit],
    ) -> None:
        match = re.match(r"^'?([^=]+?)\s*=\s*(.*?)'?$", text, re.DOTALL)
        if not match:
            return
        key = match.group(1).strip()
        value = re.sub(r"^'(.*)'$", r"\1", match.group(2).strip())
        if key == "メッセージ" and _is_translatable_string(value):
            units.append(_JsonUnit(text=value, tag="657", unit_type="string_replace", path=path))

    def _collect_command_108(
        self,
        text: str,
        path: Tuple[Any, ...],
        units: List[_JsonUnit],
    ) -> None:
        for label, pattern in CODE108_PATTERNS:
            if label.lower() not in text.lower() and label not in {"NW", "Menu"}:
                continue
            match = pattern.search(text)
            if match and _is_translatable_string(match.group(1)):
                units.append(_JsonUnit(text=match.group(1), tag="108", unit_type="string_replace", path=path))
                return

    def _collect_command_356(
        self,
        text: str,
        path: Tuple[Any, ...],
        units: List[_JsonUnit],
    ) -> None:
        if "Tachie showName" in text:
            match = re.search(r"Tachie showName (.+)", text)
            if match and _is_translatable_string(match.group(1)):
                units.append(_JsonUnit(text=match.group(1), tag="tachie", unit_type="string_replace", path=path))
            return
        if "LL_GalgeChoiceWindowMV setChoices" in text:
            match = re.search(r"LL_GalgeChoiceWindowMV setChoices (.+)", text)
            if match:
                for choice in [part.strip() for part in match.group(1).split(",")]:
                    if _is_translatable_string(choice):
                        units.append(_JsonUnit(text=choice, tag="galge", unit_type="string_replace", path=path))
                return
        for label, pattern in CODE356_PATTERNS:
            match = pattern.search(text)
            if match and _is_translatable_string(match.group(1)):
                units.append(
                    _JsonUnit(
                        text=match.group(1).replace("_", " "),
                        tag=label,
                        unit_type="string_replace",
                        path=path,
                    )
                )
                return
        if _is_translatable_string(text):
            units.append(_JsonUnit(text=text, tag=_plugin_word(text), unit_type="simple", path=path))

    def _collect_script_patterns(
        self,
        script: str,
        path: Tuple[Any, ...],
        tag: str,
        units: List[_JsonUnit],
    ) -> None:
        matched = False
        for label, pattern in CODE355_PATTERNS:
            match = pattern.search(script)
            if not match:
                continue
            text = match.group(match.lastindex or 1)
            if _is_translatable_string(text):
                units.append(
                    _JsonUnit(
                        text=text,
                        tag=label,
                        unit_type="string_replace",
                        path=path,
                    )
                )
                matched = True
        if not matched:
            self._collect_script_quotes(script, path, tag, units)

    def _collect_script_quotes(
        self,
        script: str,
        path: Tuple[Any, ...],
        tag: str,
        units: List[_JsonUnit],
    ) -> None:
        quote_index = 0
        for match in QUOTE_RE.finditer(script):
            value = _decode_js_string(match.group("value"))
            if _is_translatable_string(value):
                units.append(
                    _JsonUnit(
                        text=value,
                        tag=tag,
                        unit_type="script_quote",
                        path=path,
                        quote_index=quote_index,
                    )
                )
            quote_index += 1

    def _apply_unit(self, data: Any, unit: _JsonUnit, translation: str) -> None:
        if unit.unit_type == "simple":
            _set_nested(data, unit.path, translation)
        elif unit.unit_type == "choice_array":
            choices = list(_get_nested(data, unit.path))
            if 0 <= unit.choice_index < len(choices):
                choices[unit.choice_index] = translation
                _set_nested(data, unit.path, choices)
        elif unit.unit_type == "multiline":
            for line_path, part in zip(unit.line_paths, _split_for_existing_lines(translation, len(unit.line_paths))):
                _set_nested(data, line_path, part)
        elif unit.unit_type == "dialogue":
            rendered_speaker, rendered = _render_dialogue_text(unit, translation)
            if unit.speaker_path and rendered_speaker:
                _set_nested(data, unit.speaker_path, rendered_speaker)
            for line_path, part in zip(unit.line_paths, _split_for_existing_lines(rendered, len(unit.line_paths))):
                _set_nested(data, line_path, part)
        elif unit.unit_type == "script_quote":
            script = str(_get_nested(data, unit.path))
            replacement = self._replace_script_quote(script, unit.quote_index, translation)
            _set_nested(data, unit.path, replacement)
        elif unit.unit_type == "string_replace":
            raw = str(_get_nested(data, unit.path))
            _set_nested(data, unit.path, raw.replace(unit.text, translation, 1))
        else:
            raise ParserError(
                f"Unknown RPG Maker unit type: {unit.unit_type}",
                parser_name=self.parser_name,
                component="inject",
            )

    def _replace_script_quote(self, script: str, quote_index: int, translation: str) -> str:
        seen = 0
        chunks: List[str] = []
        last = 0
        for match in QUOTE_RE.finditer(script):
            if seen == quote_index:
                quote = match.group("quote")
                chunks.append(script[last:match.start("value")])
                chunks.append(_encode_js_string(translation, quote))
                chunks.append(script[match.end("value"):])
                return "".join(chunks)
            seen += 1
        return script


class _BaseRpgMakerHandler(FormatHandler, _RpgMakerJsonCore):
    extensions = (".rpgjson",)
    supports_pairs = False

    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        return [line.text for line in self.extract_tagged(path, encoding) or []]

    def extract_tagged(self, path: Path, encoding: str = "utf-8") -> List[ExtractedLine]:
        try:
            data, _detected = _read_json_with_fallback(path, encoding)
        except ParserError as exc:
            exc.parser_name = self.parser_name
            exc.component = "extract"
            raise
        units = self._collect_units(data)
        return [
            ExtractedLine(text=unit.text, tag=unit.tag, speaker=unit.speaker)
            for unit in units
        ]

    def detect_speakers(self, lines: List[str]) -> Optional[List[SpeakerInfo]]:
        speakers: List[SpeakerInfo] = []
        seen: set[str] = set()
        for index, line in enumerate(lines):
            speaker, _body = _split_speaker_text(line)
            if speaker and speaker not in seen:
                speakers.append(SpeakerInfo(name=speaker, line_idx=index))
                seen.add(speaker)
        return speakers or None

    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8",
    ) -> None:
        self.inject_to(path, path, lines, orig_lines=original_lines, encoding=encoding)

    def inject_to(
        self,
        source_path: Path,
        output_path: Path,
        lines: List[str],
        *,
        orig_lines: Optional[List[str]] = None,
        encoding: str = "utf-8",
    ) -> List[int]:
        try:
            data, detected_encoding = _read_json_with_fallback(source_path, encoding)
        except ParserError as exc:
            exc.parser_name = self.parser_name
            exc.component = "inject"
            raise
        units = self._collect_units(data)
        failures: List[int] = []
        search_keys = orig_lines if orig_lines is not None else [unit.text for unit in units]

        for index, translation in enumerate(lines):
            if index >= len(units):
                failures.append(index)
                continue
            if index < len(search_keys) and translation == search_keys[index]:
                continue
            self._apply_unit(data, units[index], translation)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding=detected_encoding,
            newline="",
        )
        return failures

    def get_metadata(self, path: Path) -> Dict[str, Any]:
        meta = super().get_metadata(path)
        try:
            data, encoding = _read_json_with_fallback(path)
            meta["encoding"] = encoding
            meta["line_count"] = len(self._collect_units(data))
        except Exception as exc:
            meta["error"] = str(exc)
        return meta


class RpgMakerMVHandler(_BaseRpgMakerHandler):
    """RPG Maker MV JSON data file handler."""

    format_id = "rpgmaker_mv"
    description = "RPG Maker MV data files (JSON)"
    parser_name = "RPGMakerMV"


class RpgMakerMZHandler(_BaseRpgMakerHandler):
    """RPG Maker MZ JSON data file handler."""

    format_id = "rpgmaker_mz"
    description = "RPG Maker MZ data files (JSON)"
    parser_name = "RPGMakerMZ"


@dataclass(frozen=True)
class _JsUnit:
    text: str
    tag: str
    start: int
    end: int
    quote: str = ""


class RpgMakerPluginHandler(FormatHandler):
    """RPG Maker plugin JavaScript metadata/string handler."""

    format_id = "rpgmaker_plugin"
    extensions = (".js", ".rpgjs")
    description = "RPG Maker plugin files (JavaScript)"
    supports_pairs = False

    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        return [line.text for line in self.extract_tagged(path, encoding) or []]

    def extract_tagged(self, path: Path, encoding: str = "utf-8") -> List[ExtractedLine]:
        if not path.exists():
            raise ParserError(
                f"RPG Maker plugin file not found: {path}",
                parser_name="RPGMakerPlugin",
                component="extract",
            )
        text = path.read_text(encoding=encoding)
        units = self._collect_units(path, text)
        return [ExtractedLine(text=unit.text, tag=unit.tag) for unit in units]

    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8",
    ) -> None:
        if not path.exists():
            raise ParserError(
                f"RPG Maker plugin file not found: {path}",
                parser_name="RPGMakerPlugin",
                component="inject",
            )
        text = path.read_text(encoding=encoding)
        units = self._collect_units(path, text)
        for unit, translation in reversed(list(zip(units, lines))):
            if unit.quote:
                replacement = _encode_js_string(translation, unit.quote)
            else:
                replacement = translation
            text = text[:unit.start] + replacement + text[unit.end:]
        path.write_text(text, encoding=encoding, newline="")

    def _collect_units(self, path: Path, text: str) -> List[_JsUnit]:
        tag = _plugin_word(path.stem)
        units: List[_JsUnit] = []
        occupied: List[Tuple[int, int]] = []

        for match in PLUGIN_ANNOTATION_RE.finditer(text):
            value = match.group("value")
            if _is_translatable_string(value):
                units.append(_JsUnit(value, f"{tag}_{match.group('kind')}", match.start("value"), match.end("value")))
                occupied.append((match.start(), match.end()))

        for match in PLUGIN_ASSIGNMENT_RE.finditer(text):
            if any(start <= match.start() < end for start, end in occupied):
                continue
            value = _decode_js_string(match.group("value"))
            if _is_translatable_string(value):
                units.append(
                    _JsUnit(
                        value,
                        tag,
                        match.start("value"),
                        match.end("value"),
                        match.group("quote"),
                    )
                )
                occupied.append((match.start("value"), match.end("value")))

        for tag_suffix, pattern in PLUGIN_JS_PATTERNS:
            for match in pattern.finditer(text):
                start, end = match.start(1), match.end(1)
                if any(existing_start <= start < existing_end for existing_start, existing_end in occupied):
                    continue
                value = match.group(1).replace("\\n", " ")
                if _is_translatable_string(value):
                    units.append(
                        _JsUnit(
                            value,
                            f"{tag}_{tag_suffix}",
                            start,
                            end,
                        )
                    )
                    occupied.append((start, end))

        for match in re.finditer(r'(?:data_map_name_list|disp_list)[\s\S]*?(?=^\s*};|\Z)', text, re.MULTILINE):
            block = match.group(0)
            for string_match in QUOTE_RE.finditer(block):
                value = _decode_js_string(string_match.group("value"))
                start = match.start() + string_match.start("value")
                end = match.start() + string_match.end("value")
                if any(existing_start <= start < existing_end for existing_start, existing_end in occupied):
                    continue
                if _is_translatable_string(value):
                    units.append(
                        _JsUnit(
                            value,
                            f"{tag}_disp",
                            start,
                            end,
                            string_match.group("quote"),
                        )
                    )
                    occupied.append((start, end))

        units.sort(key=lambda unit: unit.start)
        return units


class _BaseRpgMakerParser(ParserScript):
    handler_cls: type[_BaseRpgMakerHandler]
    _name = "RPGMaker"
    _max_line_length = 52

    @property
    def name(self) -> str:
        return self._name

    def _handler(self) -> _BaseRpgMakerHandler:
        return self.handler_cls()

    def extract(self, file_path: Path) -> List[str]:
        return self._handler().extract(file_path)

    def extract_tagged(self, file_path: Path) -> Optional[List[ExtractedLine]]:
        return self._handler().extract_tagged(file_path)

    def detect_speakers(self, lines: List[str]) -> Optional[List[SpeakerInfo]]:
        return self._handler().detect_speakers(lines)

    def inject(self, file_path: Path, lines: List[str]) -> None:
        self._handler().inject(file_path, lines)

    def inject_to(
        self,
        source_path: Path,
        output_path: Path,
        lines: List[str],
        *,
        orig_lines: Optional[List[str]] = None,
    ) -> List[int]:
        return self._handler().inject_to(
            source_path,
            output_path,
            lines,
            orig_lines=orig_lines,
        )

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(
            max_line_length=self._max_line_length,
            max_line_number=4,
            wordwrap_command="\\n",
            new_textbox_injection="\\^",
        )

    @property
    def forbidden_chars(self) -> Optional[ForbiddenChars]:
        return ForbiddenChars(
            characters=["\t", "\r"],
            logit_bias={},
            output_action="replace",
        )

    @property
    def tag_rules(self) -> Optional[TagRules]:
        return TagRules(
            scene_pattern=SCENE_PATTERN,
            dialogue_pattern=DIALOGUE_PATTERN,
            menu_pattern=MENU_PATTERN,
            choice_pattern=CHOICE_PATTERN,
        )

    def _has_rpgmaker_json_shape(self, file_path: Path) -> bool:
        if not file_path.exists() or file_path.stat().st_size >= 50_000_000:
            return False
        try:
            data, _encoding = _read_json_with_fallback(file_path)
        except ParserError:
            return False
        if isinstance(data, list) and len(data) > 1 and data[0] is None:
            return True
        return isinstance(data, dict) and any(
            key in data for key in ("events", "pages", "list")
        )


class RpgMakerMVParser(_BaseRpgMakerParser):
    """ParserScript for RPG Maker MV game files."""

    handler_cls = RpgMakerMVHandler
    _name = "RPGMakerMV"
    _max_line_length = 52

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".json":
            return False
        parts = [part.lower() for part in file_path.parts]
        if "www" in parts and "data" in parts:
            return True
        return self._has_rpgmaker_json_shape(file_path)


class RpgMakerMZParser(_BaseRpgMakerParser):
    """ParserScript for RPG Maker MZ game files."""

    handler_cls = RpgMakerMZHandler
    _name = "RPGMakerMZ"
    _max_line_length = 56

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".json":
            return False
        parts = [part.lower() for part in file_path.parts]
        if "data" in parts and "www" not in parts:
            return self._has_rpgmaker_json_shape(file_path)
        return False


def get_handlers() -> List[FormatHandler]:
    """Get all RPG Maker format handlers."""
    return [
        RpgMakerMVHandler(),
        RpgMakerMZHandler(),
        RpgMakerPluginHandler(),
    ]
