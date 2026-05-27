"""KiriKiri2 parser for scenario scripts and menu captions.

Supports:
- ``.ks`` scenario extraction/injection using block-based parsing.
- ``Menus.tjs`` caption extraction/injection preserving accelerator suffixes.
- Optional project-level ``MainWindow.tjs`` wordwrap patching.
"""

from __future__ import annotations

import codecs
import csv
import io
import json
import logging
import re
import struct
import unicodedata
import zlib
from enum import IntEnum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from CherryAI.functions.apply_patches import (
    ParserProjectPatch,
    PatchApplicationResult,
    PatchTestResult,
)
from CherryAI.functions.kirikiri_font_patch import (
    run_kirikiri_font_patch_workflow,
    run_kirikiri_standard_ui_translation_patch_workflow,
    stage_kirikiri_message_layer_template,
)

from .handshake import ExtractedLine, SpeakerInfo
from .parser_base import ParserScript, WordwrapConfig

logger = logging.getLogger(__name__)


KS_ENCODING_CANDIDATES: Tuple[str, ...] = ("cp932", "shift_jis", "utf-8")
MENU_ENCODING_CANDIDATES: Tuple[str, ...] = ("utf-8-sig", "utf-8", "cp932", "shift_jis")
CSV_ENCODING_CANDIDATES: Tuple[str, ...] = ("utf-8-sig", "utf-8", "cp932", "shift_jis")
MDAT_ENCODING_CANDIDATES: Tuple[str, ...] = (
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "utf-8-sig",
    "utf-8",
    "cp932",
    "shift_jis",
)
JAPANESE_RE = re.compile(
    r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF々〆ヵヶ"
    r"\u3040-\u309F"
    r"\u30A0-\u30FF\u31F0-\u31FF\uFF66-\uFF9Fー"
    r"\u3000-\u303F"
    r"\uFF00-\uFFEF"
    r"\u2000-\u206F]"
)
COMMENT_RE = re.compile(r"^\s*(?:;|//)")

# Encoding-safe transliteration for legacy encodings like cp932/shift_jis
ENCODING_SAFETY_TRANSLITERATION = str.maketrans(
    {
        "ō": "ou",
        "Ō": "Ou",
        "ū": "uu",
        "Ū": "Uu",
        "ē": "ee",
        "Ē": "Ee",
        "ī": "ii",
        "Ī": "Ii",
        "ā": "aa",
        "Ā": "Aa",
        "—": "-",  # em-dash
        "–": "-",  # en-dash
        "―": "-",  # horizontal bar
        "−": "-",  # minus sign
    }
)
LABEL_RE = re.compile(r"^\s*\*")
AT_COMMAND_RE = re.compile(r"^\s*@")
TAG_RE = re.compile(r"^\s*\[[^\]]*\]\s*$")
MULTI_TAG_RE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)+$")
BRACE_COMMAND_RE = re.compile(r"^\s*\{[^{}]*\}\s*$")
SPEAKER_RE = re.compile(
    r"^\s*(?:"
    r"【(?P<speaker1>[^】]+)】(?:\[(?P<voice_id>[^\]]+)\])?"
    r"|"
    r"(?:@talk\s+name=)(?P<speaker2>.+)"
    r")\s*$"
)
TALK_COMMAND_RE = re.compile(r"^\s*@talk(?:\s+(?P<args>.*?))?\s*$", re.IGNORECASE)
TALK_NAME_ARG_RE = re.compile(
    r"\bname\s*=\s*(?P<speaker>\[[^\]]+\][^\s]*|\"[^\"]+\"|[^\s]+)",
    re.IGNORECASE,
)
NAME_TAG_RE = re.compile(r'\[name\s+text\s*=\s*"([^"]+)"\]')
STRING_LITERAL_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
SPEAKER_DIALOGUE_RE = re.compile(r"^(.+?)(?:：|: )(.+)$", re.DOTALL)
NEW_KAG_MENU_ITEM_RE = re.compile(r"new\s+KAGMenuItem\s*\(", re.IGNORECASE)
NEW_MENU_ITEM_RE = re.compile(r"new\s+MenuItem\s*\(", re.IGNORECASE)
SELADD_TEXT_RE = re.compile(r'(\[seladd\b[^\]]*\btext\s*=\s*")((?:\\.|[^"\\])*)(")', re.IGNORECASE)
CHOICE_TEXT_ATTR_RE = re.compile(
    r'((?:\[[^\]\r\n]*?\bchoic\w*[^\]\r\n]*?\btext\s*=\s*")|'
    r'(?:@[^\r\n]*?\bchoic\w*[^\r\n]*?\btext\s*=\s*"))'
    r'((?:\\.|[^"\\])*)'
    r'(")',
    re.IGNORECASE,
)
LABEL_TITLE_RE = re.compile(r'^(\*[^|\r\n]+\|)([^\r\n]*)(\r?\n?)$')
CAPTION_LITERAL_RE = re.compile(r'(caption\s*:\s*")((?:\\.|[^"\\])*)(")', re.IGNORECASE)
DIALOG_MGR_LITERAL_RE = re.compile(
    r'((?:(?:[A-Za-z_][A-Za-z0-9_]*\.)*DialogMGR\.)?'
    r'(?:SetYesNo|SetOK|SetMessage|SetError|SetIDString)'
    r'\s*\(\s*'
    r'(?:[^"\r\n]*?\+\s*)*'  # allow concatenation pieces before the quoted literal
    r'[^"\r\n]*?")'
    r'((?:\\.|[^"\\])*)'
    r'(")'
)
KS_UI_FIELD_LITERAL_RE = re.compile(
    r'((?:\.\s*|[%\[{,]\s*)(?:caption|title)\s*(?::|=)\s*")'
    r'((?:\\.|[^"\\])*)'
    r'(")',
    re.IGNORECASE,
)
KS_DRAWTEXT_LITERAL_RE = re.compile(
    r'((?:[A-Za-z_][A-Za-z0-9_]*\.)?drawText(?:Ex)?\s*\(\s*[^,\r\n]+,\s*[^,\r\n]+,\s*")'
    r'((?:\\.|[^"\\])*)'
    r'(")',
    re.IGNORECASE,
)
PROCESS_CH_RE = re.compile(r"if\s*\(\s*current\.processCh\(\s*text\s*\)\s*\)\s*\{")
XP3_MAGIC = b"XP3\r\n \n\x1a\x8bg\x01"
XP3_SCAN_LIMIT = 4 * 1024 * 1024
XP3_FILE_PROTECTED = 1 << 31
CXDEC_CONTROL_BLOCK_SIGNATURE = b" Encryption control block"
DLC_CHECK_GUARD_RE = re.compile(
    r"Storages\.isExistentStorage\(\s*\"(?P<storage>[^\"]+)\"\s*\)"
    r"\s*&&\s*"
    r"Scripts\.CheckCompChunk\(\s*"
    r"Scripts\.readFileOctet\(\s*\"(?P<chunk>[^\"]+)\"\s*\)\s*"
    r"\)",
)

SOFT_BRIDGE_KINDS = {"tag", "brace_command", "at_command"}
HARD_BREAK_KINDS = {"blank", "comment", "label"}
SAFE_BRIDGE_TAG_TOKENS = {
    "br",
    "clickse",
    "cm",
    "delay",
    "er",
    "l",
    "name",
    "nowait",
    "p",
    "pcm",
    "pg",
    "playse",
    "playvoice",
    "r",
    "ruby",
    "se",
    "speed",
    "style",
    "voice",
    "vo",
    "wait",
    "wc",
    "wm",
}
TAG_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
KS_CODE_KEYWORD_RE = re.compile(
    r"^(?:"
    r"function|var|const|let|if|else|for|while|switch|case|break|continue|return|"
    r"try|catch|with|class|enum|debugger"
    r")\b",
    re.IGNORECASE,
)
KS_CODE_CALL_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*|\.[A-Za-z_][A-Za-z0-9_]*)\s*\(")
KS_CODE_ASSIGN_RE = re.compile(r"(?:^|\s)(?:[A-Za-z_][A-Za-z0-9_]*|\.[A-Za-z_][A-Za-z0-9_]*|\[[^\]]+\])\s*=")
KS_CODE_MEMBER_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*|\])\.[A-Za-z_][A-Za-z0-9_]*")
KS_CODE_INDEX_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\[[^\]]+\]")
KS_CODE_STRING_LINE_RE = re.compile(r'^"(?:\\.|[^"\\])*"\s*;\s*(?://.*)?$')
KS_SWITCH_LABEL_COMMENT_RE = re.compile(r"^(?:case\b[^:]*|default)\s*:\s*(?://.*)?$", re.IGNORECASE)
PATCH_NORMAL_CONTAINER_RE = re.compile(r"^patch(?P<num>\d*)$", re.IGNORECASE)
PATCH_SPECIAL_CONTAINER_RE = re.compile(
    r"^patch[_-](?P<name>[A-Za-z0-9_]+?)(?P<num>\d*)$",
    re.IGNORECASE,
)
RANDOMCOMMENT_CSV_RE = re.compile(r"^edit_randomcomment_[1-6]\.csv$", re.IGNORECASE)
TJS_RESOURCE_LITERAL_RE = re.compile(
    r"(?:^xx2_|^edit_|^htype_|/|\\\\|\.(?:tjs|ks|nei|csv|txt|dat|png|tlg|ogg|wav|mp3)$)",
    re.IGNORECASE,
)
RANDOMCOMMENT_OPEN_RE = re.compile(
    r"(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"sysorg\.csvOpen\(\s*\"edit_randomcomment_(?P<num>[1-6])\.nei\"\s*\)",
    re.IGNORECASE,
)
RANDOMCOMMENT_GETCELL_RE = re.compile(
    r"sysorg\.GetCell\(\s*(?P<col>[^,]+?)\s*,\s*(?P<row>[^,]+?)\s*,\s*"
    r"(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*\)",
    re.IGNORECASE,
)
LHS_ASSIGN_RE = re.compile(r"^\s*(?:var\s+)?(?P<lhs>[A-Za-z_][A-Za-z0-9_]*)\s*=")
TXT_VAR_RE = re.compile(r"\btxt_[A-Za-z0-9_]+\b")
TJS_TEXT_USE_RE = re.compile(
    r"\b(?:drawText(?:Ex)?|getTextWidth|getTextHeight)\b",
    re.IGNORECASE,
)
RAND_NAME_ARRAY_ASSIGN_RE = re.compile(
    r"(?:^|[\s;])(?:[A-Za-z_][A-Za-z0-9_]*\.)*Rand[A-Za-z]+Name\s*=\s*\[",
    re.IGNORECASE,
)
KIRIKIRI2_SIZE_WHITELIST_FILENAMES: Tuple[str, ...] = (
    "menus.tjs",
)
KIRIKIRI2_SIZE_WHITELIST_FILENAME_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"^scenario.*\.ks$", re.IGNORECASE),
)
KIRIKIRI2_SIZE_WHITELIST_SUFFIXES: Tuple[str, ...] = (
    ".ks",
    ".tjs",
    ".csv",
    ".mdat",
    ".xp3",
)
KIRIKIRI2_SUPPLEMENTAL_STAGE_FILENAMES: Tuple[str, ...] = (
    "version.dll",
    "CherryAI.KiriKiriPatch.json",
)
KIRIKIRI2_SUPPLEMENTAL_STAGE_RELATIVE_PATHS: Tuple[str, ...] = ()
CSV_ALLOWED_HEADER_TAGS: Dict[str, str] = {
    "概要テキスト": "summary",
    "発生条件テキスト": "condition",
    "デート場所(ゲームには無関係)": "place",
    "デートタイトル(20文字)": "title",
    "内容文章(72文字)": "body",
    "実行条件文章(72文字)": "condition",
    "施設効果文章(72文字)": "effect",
    "パーツ名": "part_name",
    "文章": "body",
    "スキル名": "skill_name",
    "カテゴリ": "category",
    "説明文": "description",
    "街の名称": "place_name",
    "エッチ": "h_text",
    "建設効果説明文": "construction_effect_description",
}
MDAT_ALLOWED_KEYS: Dict[str, str] = {
    "マップ名": "map_name",
    "グレード名": "grade_name",
}
CSV_NUMERIC_SYMBOL_RE = re.compile(
    r"^[\d\s○×△▲▼▽■□◆◇★☆※◎◯・,./:;!?+\-_=|&()\[\]{}<>％%０-９]*$"
)
MDAT_KEY_VALUE_RE = re.compile(r'("(?P<key>[^"]+)"=>(?P<spacing>\s*)")(?P<value>[^"]+)(")')

_WRAP_VARS_SNIPPET = """
\tvar wrapNum = 0; // wordwrapping word counter
\tvar wrapPos = 0; // wordwrapping length
\tvar oldLine = void; // wordwrapping comparison line
\tvar splitLine = void; // wordwrapping split text variable
\tvar breakWrap = 0; // wrapping flag during check
\tvar newPage = 0; // wrapping flag for new page
"""

_WRAP_BLOCK_SNIPPET = """
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
                if(ch != '\\\\') tempStr += ch; // ignore escape leader
                i++;
            }
            if(tempStr.length < 1) {
                breakWrap = 1;
            } else {
                // Tokenize on consecutive non-whitespace sequences so contractions
                // (e.g., I'm) and attached punctuation (e.g., word”) stay together.
                // Avoid String.match() because some TJS runtimes do not implement it.
                splitLine = [];
                var _tok = "";
                for(var ti=0; ti<tempStr.length; ti++) {
                    var tch = tempStr[ti];
                    if(tch !== ' ' && tch !== '\\t' && tch !== '\\n' && tch !== '\\r') {
                        _tok += tch;
                    } else {
                        if(_tok.length > 0) { splitLine.push(_tok); _tok = ""; }
                    }
                }
                if(_tok.length > 0) { splitLine.push(_tok); }
                // Attach standalone opening quotes to the following token.
                var j = 0;
                while (j < splitLine.length) {
                    var tt = splitLine[j];
                    if (tt.length === 1 && (tt === '“' || tt === '「' || tt === '『' || tt === '（' || tt === '(' || tt === '"')) {
                        if (j + 1 < splitLine.length) {
                            splitLine[j+1] = tt + splitLine[j+1];
                            splitLine.splice(j, 1);
                            continue;
                        }
                    }
                    j++;
                }
                // Attach standalone closing quotes/apostrophes to the previous token.
                j = 1;
                while (j < splitLine.length) {
                    var tt2 = splitLine[j];
                    if (tt2.length === 1 && (tt2 === '”' || tt2 === '』' || tt2 === '」' || tt2 === '）' || tt2 === ')' || tt2 === '"' || tt2 === '’' || tt2 === "'")) {
                        splitLine[j-1] = splitLine[j-1] + tt2;
                        splitLine.splice(j, 1);
                        continue;
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
\t\t}
        // end: wordwrapping code
"""

_WRAP_SETMESTEXT_HELPER_SNIPPET = """
        function __CherryAIWrapMessageText(text)
        {
            if(text === void || text === null)
                return text;
            var normalized = "" + text;
            if(normalized == "")
                return normalized;
            var wrapLimit = 42;
            var sourceLines = normalized.split("\\n");
            var wrapped = [];
            for(var i = 0; i < sourceLines.count; i++)
            {
                var sourceLine = sourceLines[i];
                if(sourceLine == "")
                {
                    wrapped.push("");
                    continue;
                }
                var words = sourceLine.split(" ");
                var buffer = "";
                if(1 < words.count)
                {
                    for(var j = 0; j < words.count; j++)
                    {
                        var word = words[j];
                        if(word == "")
                            continue;
                        var candidate = (buffer == "") ? word : (buffer + " " + word);
                        if(buffer != "" && wrapLimit < candidate.length)
                        {
                            wrapped.push(buffer);
                            buffer = word;
                            continue;
                        }
                        if(buffer == "" && wrapLimit < word.length)
                        {
                            var rest = word;
                            while(wrapLimit < rest.length)
                            {
                                wrapped.push(rest.substr(0, wrapLimit));
                                rest = rest.substr(wrapLimit);
                            }
                            buffer = rest;
                            continue;
                        }
                        buffer = candidate;
                    }
                    if(buffer != "")
                        wrapped.push(buffer);
                    continue;
                }
                var restLine = sourceLine;
                while(wrapLimit < restLine.length)
                {
                    wrapped.push(restLine.substr(0, wrapLimit));
                    restLine = restLine.substr(wrapLimit);
                }
                wrapped.push(restLine);
            }
            return wrapped.join("\\n");
        }
    """

_CHOICE_FONT_SIZE_DEFAULT = 18
_CHOICE_TEXT_PADDING = 10
_CHOICE_VERTICAL_GAP = 8

_SELECT_BUTTON_HELPERS_SNIPPET = f"""
    var renderedMessage = "";
    var renderedFontHeight = 0;
    var renderedLineHeight = 0;
    var renderedStartY = 0;

    function _getChoiceAvailableWidth(buttonWidth) {{
        return buttonWidth - owner.choiceTextPadding * 2;
    }}

    function _getChoiceAvailableHeight(buttonHeight) {{
        return buttonHeight - owner.choiceTextPadding * 2;
    }}

    function _splitChoiceLines(message) {{
        var lines = [];
        var currentLine = "";
        for (var i = 0; i < message.length; i++) {{
            var ch = message[i];
            if (ch == '\\r') continue;
            if (ch == '\\n') {{
                lines.push(currentLine);
                currentLine = "";
                continue;
            }}
            currentLine += ch;
        }}
        lines.push(currentLine);
        return lines;
    }}

    function _wrapChoiceMessageByWord(message, maxWidth) {{
        if (!owner.choiceWordWrap || maxWidth <= 0 || message == "") return message;
        var _segments = [];
        var _segment = "";
        for (var si = 0; si < message.length; si++) {{
            var sch = message[si];
            if (sch == '\\r') continue;
            if (sch == '\\n') {{
                _segments.push(_segment);
                _segment = "";
                continue;
            }}
            _segment += sch;
        }}
        _segments.push(_segment);

        var _wrapped = [];
        for (var li = 0; li < _segments.length; li++) {{
            var segment = _segments[li];
            if (segment == "") {{
                _wrapped.push("");
                continue;
            }}

            var hasWhitespace = false;
            for (var wi = 0; wi < segment.length; wi++) {{
                var wch = segment[wi];
                if (wch == ' ' || wch == '\\t') {{
                    hasWhitespace = true;
                    break;
                }}
            }}
            if (!hasWhitespace) {{
                _wrapped.push(segment);
                continue;
            }}

            var currentLine = "";
            var currentWord = "";
            for (var ci = 0; ci <= segment.length; ci++) {{
                var ch = ci < segment.length ? segment[ci] : ' ';
                if (ch != ' ' && ch != '\\t') {{
                    currentWord += ch;
                    continue;
                }}
                if (currentWord == "") continue;
                var candidate = currentLine == "" ? currentWord : currentLine + " " + currentWord;
                if (currentLine != "" && font.getTextWidth(candidate) > maxWidth) {{
                    _wrapped.push(currentLine);
                    currentLine = currentWord;
                }} else {{
                    currentLine = candidate;
                }}
                currentWord = "";
            }}
            if (currentLine != "") _wrapped.push(currentLine);
        }}
        return _wrapped.join("\\n");
    }}

    function _resolveWrappedChoiceMessage(buttonWidth) {{
        var wrapWidth = _getChoiceAvailableWidth(buttonWidth);
        if (wrapWidth <= 0) return message;
        return _wrapChoiceMessageByWord(message, wrapWidth);
    }}

    function _resolveChoiceButtonHeight(wrappedMessage) {{
        var measuredHeight = font.getTextHeight(wrappedMessage) + owner.choiceTextPadding * 2;
        return measuredHeight > owner.selectHeight ? measuredHeight : owner.selectHeight;
    }}

    function _resolveChoiceTextLayout(buttonWidth, buttonHeight) {{
        var minFontHeight = 12;
        var fitFontHeight = owner.fontSize;
        var fitMessage = message;
        var fitLineHeight = owner.fontSize;
        var fitStartY = owner.choiceTextPadding;
        var availableWidth = _getChoiceAvailableWidth(buttonWidth);
        var availableHeight = _getChoiceAvailableHeight(buttonHeight);
        availableWidth = 1 if (availableWidth < 1);
        availableHeight = 1 if (availableHeight < 1);

        for (var tryFontHeight = owner.fontSize; tryFontHeight >= minFontHeight; tryFontHeight--) {{
            font.height = tryFontHeight;
            var tryMessage = _resolveWrappedChoiceMessage(buttonWidth);
            var lines = _splitChoiceLines(tryMessage);
            var lineHeight = font.getTextHeight("Ay");
            lineHeight = tryFontHeight if (lineHeight < tryFontHeight);
            lineHeight += 2;
            var totalHeight = lineHeight * lines.count;
            var maxWidth = 0;
            for (var li = 0; li < lines.count; li++) {{
                var lineWidth = font.getTextWidth(lines[li]);
                maxWidth = lineWidth if (lineWidth > maxWidth);
            }}
            fitFontHeight = tryFontHeight;
            fitMessage = tryMessage;
            fitLineHeight = lineHeight;
            fitStartY = (buttonHeight - totalHeight) >> 1;
            fitStartY = owner.choiceTextPadding if (fitStartY < owner.choiceTextPadding);
            if (totalHeight <= availableHeight && maxWidth <= availableWidth) break;
        }}

        return %[
            message: fitMessage,
            fontHeight: fitFontHeight,
            lineHeight: fitLineHeight,
            startY: fitStartY,
        ];
    }}

    function _drawWrappedChoiceMessage(message) {{
        if (message === void || message == "") return;
        font.height = renderedFontHeight if (renderedFontHeight > 0);
        var lines = _splitChoiceLines(message);
        var lineHeight = renderedLineHeight > 0 ? renderedLineHeight : owner.fontSize;
        var startY = renderedStartY;
        var cnt = Butt_imageLoaded ? (Butt_showFocusImage ? 4 : 3) : 1;
        for (var li = 0; li < lines.count; li++) {{
            var line = lines[li];
            var tw = font.getTextWidth(line);
            var dx = (width - tw) >> 1;
            for (var i = 0; i < cnt; i++) {{
                var x = (Butt_imageLoaded ? i * width : 0) + dx;
                owner.drawTextToLayer(this, x, startY + li * lineHeight, line, i, drawopt);
            }}
        }}
    }}

    function onPaint() {{
        super.onPaint(...);
        _drawWrappedChoiceMessage(renderedMessage);
    }}
"""

_SELECT_DEFAULTS_SNIPPET = f"""
    var selectWidth  = 400;
    var selectHeight = 50;
    var selectColor  = 0xffffff;
    var selectBaseColor = 0x888888;
    var choiceTextPadding = {_CHOICE_TEXT_PADDING};
    var choiceVerticalGap = {_CHOICE_VERTICAL_GAP};
    var choiceWordWrap = true;
    var fontSize     = {_CHOICE_FONT_SIZE_DEFAULT};
"""

_SELECT_REDRAW_SNIPPET = """
    function redraw() {
        // reset choice font state
        font.face   = owner.fontFace !== void ? owner.fontFace : owner.window.chDefaultFace;
        font.bold   = owner.fontBold;
        font.italic = owner.fontItalic;
        font.height = owner.fontSize;

        var hasimg = true;
        var wrappedMessage = message;
        with (owner) {
            // load button visuals when present
            if (.normalImage   != "") loadButtons(.normalImage, .overImage, .onImage, .focusImage);
            else if (.graphic  != "") loadImages(.graphic, .graphickey);
            else if (ui     !== void) loadUIInfo(ui);
            else hasimg = false;

            var buttonWidth = hasimg ? width : .selectWidth;
            var buttonHeight = hasimg ? height : .selectHeight;
            var layout = _resolveChoiceTextLayout(buttonWidth, buttonHeight);
            renderedMessage = layout.message;
            renderedFontHeight = layout.fontHeight;
            renderedLineHeight = layout.lineHeight;
            renderedStartY = layout.startY;
            if (hasimg) {
                modifyOpacity(.frameOpacity);
            } else {
                font.height = renderedFontHeight;
                buttonHeight = _resolveChoiceButtonHeight(renderedMessage);
                width        = .selectWidth;
                height       = buttonHeight;
                captionColor = .selectColor;
                color        = .selectBaseColor;
                caption      = "";
                var plainLayout = _resolveChoiceTextLayout(width, height);
                renderedMessage = plainLayout.message;
                renderedFontHeight = plainLayout.fontHeight;
                renderedLineHeight = plainLayout.lineHeight;
                renderedStartY = plainLayout.startY;
            }
        }
        update();
    }
"""

_SELECT_POSITIONS_SNIPPET = """
    function getSelectPositions(count) {
        var ret = [];
        if (uibutton !== void) {
            // prefer explicit UI layout positions when they exist
            for (var i=0; i<count; i++) {
                var info = uibutton[getUIName(i, count)];
                if (info === void) break;
                with (info) ret.add([ .x + .width/2, .y + .height/2 ]);
            }
            if (ret.count == count) return ret;
            ret.clear();
        }
        var x = left + width / 2;
        var totalHeight = 0;
        for (var i=0; i<count; i++) totalHeight += selects[i].height;
        totalHeight += choiceVerticalGap * (count - 1) if (count > 1);
        var y = top + (height - totalHeight) / 2;
        y = top if (y < top);
        for (var i=0; i<count; i++) {
            var selectHeight = selects[i].height;
            y += selectHeight / 2;
            ret.add([ x, y ]);
            y += selectHeight / 2 + choiceVerticalGap;
        }
        return ret;
    }
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


def _make_encoding_safe_fragment(text: str, encoding: str) -> str:
    safe_parts: List[str] = []
    for ch in text:
        try:
            ch.encode(encoding)
            safe_parts.append(ch)
            continue
        except UnicodeEncodeError:
            pass

        transliterated = ch.translate(ENCODING_SAFETY_TRANSLITERATION)
        normalized = unicodedata.normalize("NFKD", transliterated)
        stripped = "".join(part for part in normalized if not unicodedata.combining(part))
        if not stripped or stripped == ch:
            safe_parts.append("?")
            continue

        safe_parts.append(_make_encoding_safe_fragment(stripped, encoding))

    return "".join(safe_parts)


def _make_encoding_safe_text(text: str, encoding: str) -> str:
    """Convert only unencodable characters to legacy-safe replacements.

    NFC preserves already valid precomposed kana like バ or グ before we repair the
    specific characters that fail in the target legacy encoding.
    """
    normalized = unicodedata.normalize("NFC", text)
    return _make_encoding_safe_fragment(normalized, encoding)


def _write_text(path: Path, text: str, encoding: str) -> None:
    """Write text to file, applying encoding-safe transliteration if needed.
    
    For encodings like cp932/shift_jis, applies transliteration to convert
    incompatible characters (em-dashes, macron vowels, etc.) to ASCII equivalents.
    """
    if encoding == "utf-8-sig":
        path.write_bytes(codecs.BOM_UTF8 + text.encode("utf-8"))
        return
    
    try:
        path.write_text(text, encoding=encoding, newline="")
    except UnicodeEncodeError as exc:
        # For legacy encodings, try encoding-safe transliteration
        if encoding.lower() in ("cp932", "shift_jis"):
            safe_text = _make_encoding_safe_text(text, encoding)
            if safe_text != text:
                logger.warning(
                    f"Applied encoding-safe transliteration for {encoding} in {path.name} "
                    f"(converted {len(text)} → {len(safe_text)} chars)"
                )
                path.write_text(safe_text, encoding=encoding, newline="")
            else:
                raise
        else:
            raise


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
    speaker_style: str = ""
    raw_speaker_line: str = ""


@dataclass(slots=True)
class PendingSpeaker:
    speaker: str
    voice_id: str = ""
    line_number: int = 0
    speaker_style: str = ""
    raw_speaker_line: str = ""
    bridge_code_lines: List[Tuple[int, str, str]] = field(default_factory=list)


@dataclass(slots=True)
class KsBlock:
    file_path: str
    block_id: str
    tag: str
    speaker: str
    voice_id: str
    speaker_line_number: int
    speaker_style: str
    speaker_raw_line: str
    start_line: int
    end_line: int
    text_line_numbers: List[int] = field(default_factory=list)
    source_text_lines: List[str] = field(default_factory=list)
    bridge_code_lines: List[Tuple[int, str, str]] = field(default_factory=list)

    @property
    def joined_text(self) -> str:
        return "\n".join(self.source_text_lines)

    @property
    def extracted_text(self) -> str:
        return _format_extracted_text(self.joined_text, self.speaker)


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
class KsLiteralEntry:
    text: str
    line_number: int
    tag: str
    entry_kind: str
    literal_index: int = 0


@dataclass(slots=True)
class CaptionEntry:
    text: str
    line_index: int
    literal_index: int


@dataclass(slots=True)
class DialogLiteralEntry:
    text: str
    line_index: int
    literal_index: int


@dataclass(slots=True)
class TjsCodeLiteralEntry:
    text: str
    line_index: int
    literal_index: int
    tag: str


@dataclass(slots=True)
class CsvEntry:
    text: str
    row_index: int
    col_index: int
    header: str
    tag: str


@dataclass(slots=True)
class MdatEntry:
    text: str
    line_index: int
    key: str
    tag: str


@dataclass(slots=True)
class _CachedTaggedExtraction:
    mtime_ns: int
    size: int
    tagged: Tuple[ExtractedLine, ...]


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


def _annotate_extracted_line_locators(
    extracted: List[ExtractedLine],
    line_numbers: Sequence[int],
) -> List[ExtractedLine]:
    line_counts: Dict[int, int] = {}
    for line_number in line_numbers:
        line_counts[line_number] = line_counts.get(line_number, 0) + 1

    line_offsets: Dict[int, int] = {}
    for extracted_line, line_number in zip(extracted, line_numbers):
        extracted_line.ln = line_number
        if line_counts.get(line_number, 0) <= 1:
            continue
        next_offset = line_offsets.get(line_number, 0) + 1
        line_offsets[line_number] = next_offset
        extracted_line.f = next_offset
    return extracted


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
    talk_match = TALK_COMMAND_RE.match(stripped)
    if not stripped:
        return ClassifiedLine(number=number, text=text, newline=newline, kind="blank")
    if speaker_match:
        bracket_speaker = speaker_match.group("speaker1") or ""
        talk_speaker = speaker_match.group("speaker2") or ""
        return ClassifiedLine(
            number=number,
            text=text,
            newline=newline,
            kind="speaker",
            speaker=bracket_speaker or talk_speaker,
            voice_id=speaker_match.group("voice_id") or "",
            speaker_style="bracket" if bracket_speaker else "talk",
            raw_speaker_line=text,
        )
    if talk_match:
        args = talk_match.group("args") or ""
        name_match = TALK_NAME_ARG_RE.search(args)
        speaker = name_match.group("speaker") if name_match else ""
        if len(speaker) >= 2 and speaker.startswith('"') and speaker.endswith('"'):
            speaker = speaker[1:-1]
        return ClassifiedLine(
            number=number,
            text=text,
            newline=newline,
            kind="speaker" if speaker else "talk_command",
            speaker=speaker,
            speaker_style="talk",
            raw_speaker_line=text,
        )
    if COMMENT_RE.match(stripped):
        kind = "comment"
    elif LABEL_RE.match(stripped):
        kind = "label"
    elif AT_COMMAND_RE.match(stripped):
        kind = "at_command"
    elif MULTI_TAG_RE.match(stripped):
        kind = "tag"
    elif TAG_RE.match(stripped):
        kind = "tag"
    elif BRACE_COMMAND_RE.match(stripped):
        kind = "brace_command"
    elif _looks_like_ks_code_text(stripped):
        kind = "code"
    else:
        kind = "text"
    return ClassifiedLine(number=number, text=text, newline=newline, kind=kind)


def _looks_like_ks_code_text(stripped: str) -> bool:
    if not stripped:
        return False
    if stripped in {"{", "}", "};", "};", "]", "["}:
        return True
    if stripped.startswith("{//") or stripped.startswith("}//"):
        return True
    if KS_SWITCH_LABEL_COMMENT_RE.match(stripped):
        return True
    if stripped.startswith('"') and '";' in stripped:
        return True
    if KS_CODE_STRING_LINE_RE.match(stripped):
        return True
    if KS_CODE_KEYWORD_RE.match(stripped):
        return True
    if KS_CODE_CALL_RE.match(stripped):
        return True
    if stripped.startswith("."):
        return True

    code_signals = 0
    if KS_CODE_ASSIGN_RE.search(stripped):
        code_signals += 1
    if KS_CODE_MEMBER_RE.search(stripped):
        code_signals += 1
    if KS_CODE_INDEX_RE.search(stripped):
        code_signals += 1
    if any(token in stripped for token in ("==", "!=", ">=", "<=", "&&", "||", "?", "%=", "%[")):
        code_signals += 1
    if any(char in stripped for char in (";", "{", "}")):
        code_signals += 1
    if re.search(r"\b(?:true|false|void|new|typeof)\b", stripped):
        code_signals += 1
    if stripped.endswith(")") and "(" in stripped:
        code_signals += 1
    return code_signals >= 2


def _format_extracted_text(text: str, speaker: str) -> str:
    if speaker:
        return f"{speaker}: {text}"
    return text


def _split_extracted_text(text: str) -> Tuple[str, str]:
    match = SPEAKER_DIALOGUE_RE.match(text)
    if match:
        return match.group(1), match.group(2)
    return "", text


def _next_significant_kind(lines: Sequence[ClassifiedLine], start_index: int) -> Optional[str]:
    for index in range(start_index, len(lines)):
        kind = lines[index].kind
        if kind == "comment":
            continue
        return kind
    return None


def _is_bridge_safe_tag_line(text: str) -> bool:
    tag_payloads = re.findall(r"\[([^\]]*)\]", text)
    if not tag_payloads:
        return False

    for payload in tag_payloads:
        tokens = {token.lower() for token in TAG_TOKEN_RE.findall(payload)}
        if not tokens:
            return False
        if not tokens.intersection(SAFE_BRIDGE_TAG_TOKENS):
            return False

    return True


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
    if line.kind == "tag" and not _is_bridge_safe_tag_line(line.text):
        return False
    return _next_significant_kind(lines, index + 1) == "text"


def _read_classified_ks_lines(path: Path) -> List[ClassifiedLine]:
    text, _ = _read_text(path, KS_ENCODING_CANDIDATES)
    raw_lines = text.splitlines(keepends=True)
    return [_classify_line(index + 1, raw_line) for index, raw_line in enumerate(raw_lines)]


def _extract_ks_blocks_from_lines(path: Path, lines: Sequence[ClassifiedLine]) -> List[KsBlock]:
    blocks: List[KsBlock] = []
    current: Optional[KsBlock] = None
    pending_speaker: Optional[PendingSpeaker] = None
    block_number = 0
    rel_name = path.as_posix()

    for index, line in enumerate(lines):
        if line.kind in {"speaker", "talk_command"}:
            if current is not None and current.joined_text:
                blocks.append(current)
            current = None
            pending_speaker = PendingSpeaker(
                line.speaker,
                line.voice_id,
                line.number,
                speaker_style=line.speaker_style,
                raw_speaker_line=line.raw_speaker_line,
            )
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
                    speaker_line_number=(pending_speaker.line_number if pending_speaker else 0),
                    speaker_style=(pending_speaker.speaker_style if pending_speaker else ""),
                    speaker_raw_line=(pending_speaker.raw_speaker_line if pending_speaker else ""),
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
            continue

        if current is not None and current.joined_text:
            blocks.append(current)
        current = None

    if current is not None and current.joined_text:
        blocks.append(current)

    return [block for block in blocks if JAPANESE_RE.search(block.joined_text)]


def _extract_ks_blocks(path: Path) -> List[KsBlock]:
    return _extract_ks_blocks_from_lines(path, _read_classified_ks_lines(path))


def _extract_ks_units(path: Path) -> List[tuple[int, int, str, KsBlock | KsLiteralEntry]]:
    lines = _read_classified_ks_lines(path)
    units: List[tuple[int, int, str, KsBlock | KsLiteralEntry]] = []
    for block in _extract_ks_blocks_from_lines(path, lines):
        units.append((block.start_line, 1, "block", block))
    for entry in _extract_ks_literal_entries_from_lines(lines):
        units.append((entry.line_number, 0, entry.entry_kind, entry))
    units.sort(key=lambda item: (item[0], item[1]))
    return units


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


def _extract_ks_literal_entries_from_lines(
    lines: Sequence[ClassifiedLine],
) -> List[KsLiteralEntry]:
    entries: List[KsLiteralEntry] = []

    for line in lines:
        line_number = line.number
        raw_line = line.text + line.newline
        choice_match = SELADD_TEXT_RE.search(raw_line)
        if choice_match:
            choice_text = choice_match.group(2)
            if choice_text.strip():
                entries.append(
                    KsLiteralEntry(
                        text=choice_text,
                        line_number=line_number,
                        tag="choice",
                        entry_kind="seladd",
                        literal_index=0,
                    )
                )

        for literal_index, choice_match in enumerate(CHOICE_TEXT_ATTR_RE.finditer(raw_line)):
            choice_text = choice_match.group(2)
            if not choice_text.strip():
                continue
            entries.append(
                KsLiteralEntry(
                    text=choice_text,
                    line_number=line_number,
                    tag="choice",
                    entry_kind="choice_text_attr",
                    literal_index=literal_index,
                )
            )

        label_match = LABEL_TITLE_RE.match(raw_line)
        if label_match:
            title = label_match.group(2)
            if title.strip():
                entries.append(
                    KsLiteralEntry(
                        text=title,
                        line_number=line_number,
                        tag="SaveLocation",
                        entry_kind="label_title",
                        literal_index=0,
                    )
                )

        for entry in _extract_ks_code_literal_entries(raw_line, line_number):
            entries.append(entry)

    return entries


def _extract_ks_literal_entries(path: Path) -> List[KsLiteralEntry]:
    return _extract_ks_literal_entries_from_lines(_read_classified_ks_lines(path))


def _extract_ks_code_literal_entries(raw_line: str, line_number: int) -> List[KsLiteralEntry]:
    classified = _classify_line(line_number, raw_line)
    if classified.kind != "code":
        return []

    entries: List[KsLiteralEntry] = []
    for literal_index, match in enumerate(KS_UI_FIELD_LITERAL_RE.finditer(raw_line)):
        content = match.group(2)
        if content.strip() and JAPANESE_RE.search(content):
            entries.append(
                KsLiteralEntry(
                    text=content,
                    line_number=line_number,
                    tag="menu",
                    entry_kind="ui_field",
                    literal_index=literal_index,
                )
            )

    for literal_index, match in enumerate(KS_DRAWTEXT_LITERAL_RE.finditer(raw_line)):
        content = match.group(2)
        if content.strip() and JAPANESE_RE.search(content):
            entries.append(
                KsLiteralEntry(
                    text=content,
                    line_number=line_number,
                    tag="menu",
                    entry_kind="drawtext",
                    literal_index=literal_index,
                )
            )

    for literal_index, match in enumerate(DIALOG_MGR_LITERAL_RE.finditer(raw_line)):
        content = match.group(2)
        if content.strip():
            entries.append(
                KsLiteralEntry(
                    text=content,
                    line_number=line_number,
                    tag="dialog",
                    entry_kind="dialog_call",
                    literal_index=literal_index,
                )
            )

    return entries


def _extract_tjs_caption_entries(path: Path) -> List[CaptionEntry]:
    text, _ = _read_text(path, MENU_ENCODING_CANDIDATES)
    entries: List[CaptionEntry] = []

    for line_index, line in enumerate(text.splitlines(keepends=True)):
        literal_index = 0
        for match in CAPTION_LITERAL_RE.finditer(line):
            content = match.group(2)
            if content == "-" or not content.strip():
                continue
            entries.append(
                CaptionEntry(text=content, line_index=line_index, literal_index=literal_index)
            )
            literal_index += 1

    return entries


def _extract_tjs_dialog_entries(path: Path) -> List[DialogLiteralEntry]:
    text, _ = _read_text(path, MENU_ENCODING_CANDIDATES)
    entries: List[DialogLiteralEntry] = []

    for line_index, line in enumerate(text.splitlines(keepends=True)):
        literal_index = 0
        for match in DIALOG_MGR_LITERAL_RE.finditer(line):
            content = match.group(2)
            if not content.strip():
                continue
            entries.append(
                DialogLiteralEntry(
                    text=content,
                    line_index=line_index,
                    literal_index=literal_index,
                )
            )
            literal_index += 1

    return entries


def _is_tjs_resource_literal(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return True
    return bool(TJS_RESOURCE_LITERAL_RE.search(stripped))


def _extract_txt_vars(line: str) -> Set[str]:
    return set(TXT_VAR_RE.findall(line))


def _collect_tjs_txt_usage(lines: Sequence[str]) -> Tuple[Dict[str, int], Set[str]]:
    usage_count: Dict[str, int] = {}
    display_used: Set[str] = set()

    for line_index, raw_line in enumerate(lines):
        line_info = _classify_line(line_index + 1, raw_line)
        if line_info.kind in {"blank", "comment"}:
            continue
        txt_vars = _extract_txt_vars(raw_line)
        if not txt_vars:
            continue
        for txt_var in txt_vars:
            usage_count[txt_var] = usage_count.get(txt_var, 0) + 1
        if TJS_TEXT_USE_RE.search(raw_line) or re.search(r"\breturn\s+txt_[A-Za-z0-9_]+\b", raw_line):
            display_used.update(txt_vars)

    return usage_count, display_used


def _parse_int_literal(expr: str) -> Optional[int]:
    stripped = expr.strip()
    if not re.fullmatch(r"\d+", stripped):
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _is_randomcomment_visible_target(lhs: str) -> bool:
    # Only harvest randomized comment payloads that are explicitly routed to
    # runtime display variables. Exclude title/key variables (e.g. txt_Syougou)
    # because those are also used to build resource identifiers.
    return lhs.startswith("rnd_")


def _collect_randomcomment_runtime_usage(
    patch_dir: Path,
) -> Dict[int, Tuple[Set[Tuple[int, int]], Set[int]]]:
    usage: Dict[int, Tuple[Set[Tuple[int, int]], Set[int]]] = {
        index: (set(), set()) for index in range(1, 7)
    }
    if not patch_dir.exists():
        return usage

    for script_path in sorted(patch_dir.glob("*.tjs")):
        try:
            text, _encoding = _read_text(script_path, MENU_ENCODING_CANDIDATES)
        except Exception:
            continue

        lines = text.splitlines(keepends=True)
        file_var_to_index: Dict[str, int] = {}
        for line_index, raw_line in enumerate(lines):
            line_info = _classify_line(line_index + 1, raw_line)
            if line_info.kind in {"blank", "comment"}:
                continue
            for open_match in RANDOMCOMMENT_OPEN_RE.finditer(raw_line):
                file_var_to_index[open_match.group("var")] = int(open_match.group("num"))

        for line_index, raw_line in enumerate(lines):
            line_info = _classify_line(line_index + 1, raw_line)
            if line_info.kind in {"blank", "comment"}:
                continue
            lhs_match = LHS_ASSIGN_RE.match(raw_line)
            if lhs_match is None:
                continue
            lhs = lhs_match.group("lhs")
            if not _is_randomcomment_visible_target(lhs):
                continue

            for call_match in RANDOMCOMMENT_GETCELL_RE.finditer(raw_line):
                file_var = call_match.group("var")
                file_index = file_var_to_index.get(file_var)
                if file_index is None:
                    continue
                col = _parse_int_literal(call_match.group("col"))
                if col is None:
                    continue
                row = _parse_int_literal(call_match.group("row"))
                exact_cells, broad_columns = usage[file_index]
                if row is None:
                    broad_columns.add(col)
                else:
                    exact_cells.add((row, col))

    return usage


def _resolve_randomcomment_usage(path: Path) -> Tuple[Set[Tuple[int, int]], Set[int]]:
    file_index_match = re.search(r"([1-6])$", path.stem)
    if file_index_match is None:
        return set(), set()
    file_index = int(file_index_match.group(1))

    candidate_patch_dirs: List[Path] = []
    for parent in path.parents:
        candidate = parent / "patch"
        if candidate.exists() and candidate.is_dir() and candidate not in candidate_patch_dirs:
            candidate_patch_dirs.append(candidate)

    for patch_dir in candidate_patch_dirs:
        usage = _collect_randomcomment_runtime_usage(patch_dir)
        exact_cells, broad_columns = usage.get(file_index, (set(), set()))
        if exact_cells or broad_columns:
            return exact_cells, broad_columns

    return set(), set()


def _scan_tjs_bracket_delta(segment: str) -> int:
    delta = 0
    in_string = False
    escaped = False
    index = 0
    while index < len(segment):
        char = segment[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < len(segment) and segment[index + 1] == "/":
            break
        if char == "[":
            delta += 1
        elif char == "]":
            delta -= 1
        index += 1
    return delta


def _extract_tjs_rand_name_entries(path: Path) -> List[TjsCodeLiteralEntry]:
    text, _ = _read_text(path, MENU_ENCODING_CANDIDATES)
    lines = text.splitlines(keepends=True)
    entries: List[TjsCodeLiteralEntry] = []

    in_block = False
    depth = 0

    for line_index, raw_line in enumerate(lines):
        start_offset = 0
        if not in_block:
            match = RAND_NAME_ARRAY_ASSIGN_RE.search(raw_line)
            if match is None:
                continue
            start_offset = max(0, match.end() - 1)
            in_block = True

        for literal_index, literal_match in enumerate(STRING_LITERAL_RE.finditer(raw_line)):
            if literal_match.start() < start_offset:
                continue
            content = literal_match.group(1)
            if not content.strip():
                continue
            entries.append(
                TjsCodeLiteralEntry(
                    text=content,
                    line_index=line_index,
                    literal_index=literal_index,
                    tag="variable",
                )
            )

        depth += _scan_tjs_bracket_delta(raw_line[start_offset:])
        if depth <= 0:
            in_block = False
            depth = 0

    return entries


def _extract_tjs_code_literal_entries(path: Path) -> List[TjsCodeLiteralEntry]:
    text, _ = _read_text(path, MENU_ENCODING_CANDIDATES)
    lines = text.splitlines(keepends=True)
    usage_count, display_used = _collect_tjs_txt_usage(lines)
    entries: List[TjsCodeLiteralEntry] = []

    for line_index, raw_line in enumerate(lines):
        line_info = _classify_line(line_index + 1, raw_line)
        if line_info.kind in {"blank", "comment"}:
            continue
        # Skip dedicated handlers to avoid duplicate rows.
        if CAPTION_LITERAL_RE.search(raw_line) or DIALOG_MGR_LITERAL_RE.search(raw_line):
            continue
        txt_vars = _extract_txt_vars(raw_line)
        if not txt_vars:
            continue
        if "=" not in raw_line:
            continue

        supported_vars = {
            txt_var
            for txt_var in txt_vars
            if usage_count.get(txt_var, 0) > 1 and txt_var in display_used
        }
        if not supported_vars:
            continue

        literal_index = 0
        for match in STRING_LITERAL_RE.finditer(raw_line):
            content = match.group(1)
            if not content.strip() or not JAPANESE_RE.search(content):
                continue
            if _is_tjs_resource_literal(content):
                continue
            entries.append(
                TjsCodeLiteralEntry(
                    text=content,
                    line_index=line_index,
                    literal_index=literal_index,
                    tag="variable",
                )
            )
            literal_index += 1

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


def _replace_seladd_text(line: str, translated_text: str) -> Optional[str]:
    match = SELADD_TEXT_RE.search(line)
    if match is None:
        return None
    escaped = _escape_menu_content(translated_text)
    return line[:match.start(2)] + escaped + line[match.end(2):]


def _replace_label_title(line: str, translated_text: str) -> Optional[str]:
    match = LABEL_TITLE_RE.match(line)
    if match is None or not match.group(2).strip():
        return None
    return match.group(1) + translated_text + match.group(3)


def _replace_caption_literals(line: str, translated_texts: Sequence[str]) -> str:
    pieces: List[str] = []
    cursor = 0
    replacement_index = 0
    for match in CAPTION_LITERAL_RE.finditer(line):
        pieces.append(line[cursor:match.start(2)])
        content = match.group(2)
        if content == "-" or not content.strip() or not JAPANESE_RE.search(content):
            pieces.append(content)
        else:
            translated = (
                translated_texts[replacement_index]
                if replacement_index < len(translated_texts)
                else content
            )
            pieces.append(_escape_menu_content(translated))
            replacement_index += 1
        cursor = match.end(2)
    pieces.append(line[cursor:])
    return "".join(pieces)


def _replace_tjs_dialog_literals(line: str, translated_texts: Sequence[str]) -> str:
    pieces: List[str] = []
    cursor = 0
    replacement_index = 0
    for match in DIALOG_MGR_LITERAL_RE.finditer(line):
        pieces.append(line[cursor:match.start(2)])
        content = match.group(2)
        translated = (
            translated_texts[replacement_index]
            if replacement_index < len(translated_texts)
            else content
        )
        pieces.append(_escape_menu_content(translated))
        replacement_index += 1
        cursor = match.end(2)
    pieces.append(line[cursor:])
    return "".join(pieces)


def _replace_string_literal_by_index(
    line: str,
    translated_text: str,
    literal_index: int,
) -> Optional[str]:
    pieces: List[str] = []
    cursor = 0
    current_index = 0
    replaced = False
    escaped = _escape_menu_content(translated_text)
    for match in STRING_LITERAL_RE.finditer(line):
        pieces.append(line[cursor:match.start(1)])
        content = match.group(1)
        if current_index == literal_index:
            pieces.append(escaped)
            replaced = True
        else:
            pieces.append(content)
        cursor = match.end(1)
        current_index += 1
    if not replaced:
        return None
    pieces.append(line[cursor:])
    return "".join(pieces)


def _replace_pattern_literal_by_index(
    line: str,
    pattern: re.Pattern[str],
    translated_text: str,
    literal_index: int,
) -> Optional[str]:
    pieces: List[str] = []
    cursor = 0
    current_index = 0
    replaced = False
    escaped = _escape_menu_content(translated_text)
    for match in pattern.finditer(line):
        pieces.append(line[cursor:match.start(2)])
        content = match.group(2)
        if current_index == literal_index:
            pieces.append(escaped)
            replaced = True
        else:
            pieces.append(content)
        cursor = match.end(2)
        current_index += 1
    if not replaced:
        return None
    pieces.append(line[cursor:])
    return "".join(pieces)


def _escape_menu_content(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _detect_csv_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _read_csv_rows(path: Path) -> Tuple[List[List[str]], str, str]:
    text, encoding = _read_text(path, CSV_ENCODING_CANDIDATES)
    rows = list(csv.reader(io.StringIO(text, newline="")))
    return rows, encoding, _detect_csv_newline(text)


def _write_csv_rows(
    path: Path,
    rows: Sequence[Sequence[str]],
    encoding: str,
    newline: str,
) -> None:
    # Sanitize newline characters inside CSV cell values to avoid creating
    # additional physical lines in CSV-like outputs. Replace any CR/LF
    # occurrences with a single space to keep values single-line.
    sanitized_rows: List[List[str]] = []
    for row in rows:
        sanitized_row: List[str] = []
        for cell in row:
            if isinstance(cell, str):
                val = cell.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
            else:
                val = str(cell)
            sanitized_row.append(val)
        sanitized_rows.append(sanitized_row)

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator=newline)
    writer.writerows(sanitized_rows)
    _write_text(path, buffer.getvalue(), encoding)


def _looks_like_kirikiri_csv(path: Path) -> bool:
    if RANDOMCOMMENT_CSV_RE.match(path.name):
        return True
    try:
        rows, _encoding, _newline = _read_csv_rows(path)
    except Exception:
        return False
    if not rows:
        return False
    headers = {header.strip() for header in rows[0] if header.strip()}
    return any(header in CSV_ALLOWED_HEADER_TAGS for header in headers)


def _csv_header_to_tag(header: str) -> str:
    alias = CSV_ALLOWED_HEADER_TAGS.get(header, "text")
    return f"csv_{alias}"


def _is_translatable_csv_header(header: str) -> bool:
    stripped = header.strip()
    if not stripped:
        return False
    return stripped in CSV_ALLOWED_HEADER_TAGS


def _is_translatable_csv_value(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    # Keep whitelist-only column targeting, but skip pure symbol/number payloads.
    return not CSV_NUMERIC_SYMBOL_RE.fullmatch(stripped)


def _is_translatable_randomcomment_value(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped == "コメント":
        return False
    if "ｍａｘ" in stripped.lower() or "max" in stripped.lower():
        return False
    if "［" in stripped or "］" in stripped:
        return False
    if re.match(r"^[0-9０-９]+行目", stripped):
        return False
    return True


RANDOMCOMMENT_WORDWRAP_LIMIT = 42


def _normalize_randomcomment_profile_text(value: str) -> str:
    """Normalize randomcomment profile text for cleaner textbox rendering.

    The profile textbox expects plain text and performs character-based wrapping,
    so we pre-normalize translator output to avoid visible ASCII quotes,
    accidental comma gaps, and mid-word wrapping.
    """
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace('"', "")
    normalized = re.sub(r"([,，])[ \t]+", r"\1", normalized)

    wrapped_lines: List[str] = []
    for source_line in normalized.split("\n"):
        stripped = source_line.strip()
        if not stripped:
            wrapped_lines.append("")
            continue

        words = stripped.split()
        if len(words) <= 1:
            wrapped_lines.append(stripped)
            continue

        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if len(candidate) > RANDOMCOMMENT_WORDWRAP_LIMIT:
                wrapped_lines.append(current)
                current = word
            else:
                current = candidate
        wrapped_lines.append(current)

    return "\n".join(wrapped_lines)


def _extract_csv_entries(path: Path) -> List[CsvEntry]:
    rows, _encoding, _newline = _read_csv_rows(path)
    if not rows:
        return []

    if RANDOMCOMMENT_CSV_RE.match(path.name):
        exact_cells, broad_columns = _resolve_randomcomment_usage(path)
        entries: List[CsvEntry] = []
        for row_index, row in enumerate(rows):
            if row_index == 0:
                continue
            for col_index, value in enumerate(row):
                if (row_index, col_index) not in exact_cells and col_index not in broad_columns:
                    continue
                if not value.strip() or not JAPANESE_RE.search(value):
                    continue
                if not _is_translatable_csv_value(value):
                    continue
                if not _is_translatable_randomcomment_value(value):
                    continue
                entries.append(
                    CsvEntry(
                        text=value,
                        row_index=row_index,
                        col_index=col_index,
                        header=f"col{col_index}",
                        tag="csv_randomcomment",
                    )
                )
        return entries

    headers = rows[0]
    entries: List[CsvEntry] = []
    for col_index, raw_header in enumerate(headers):
        header = raw_header.strip()
        if not _is_translatable_csv_header(header):
            continue
        tag = _csv_header_to_tag(header)
        for row_index in range(1, len(rows)):
            row = rows[row_index]
            if col_index >= len(row):
                continue
            value = row[col_index]
            if not _is_translatable_csv_value(value):
                continue
            entries.append(
                CsvEntry(
                    text=row[col_index],
                    row_index=row_index,
                    col_index=col_index,
                    header=header,
                    tag=tag,
                )
            )
    return entries


def _looks_like_kirikiri_mdat(path: Path) -> bool:
    try:
        text, _encoding = _read_text(path, MDAT_ENCODING_CANDIDATES)
    except Exception:
        return False
    for match in MDAT_KEY_VALUE_RE.finditer(text):
        key = match.group("key")
        value = match.group("value")
        if key in MDAT_ALLOWED_KEYS and value.strip():
            return True
    return False


def _mdat_key_to_tag(key: str) -> str:
    alias = MDAT_ALLOWED_KEYS.get(key, "text")
    return f"mdat_{alias}"


def _extract_mdat_entries(path: Path) -> List[MdatEntry]:
    text, _encoding = _read_text(path, MDAT_ENCODING_CANDIDATES)
    entries: List[MdatEntry] = []
    for line_index, line in enumerate(text.splitlines(keepends=True)):
        for match in MDAT_KEY_VALUE_RE.finditer(line):
            key = match.group("key")
            value = match.group("value")
            if key not in MDAT_ALLOWED_KEYS or not value.strip():
                continue
            entries.append(
                MdatEntry(
                    text=value,
                    line_index=line_index,
                    key=key,
                    tag=_mdat_key_to_tag(key),
                )
            )
    return entries


def _replace_mdat_literals(line: str, translated_texts: Sequence[str]) -> str:
    pieces: List[str] = []
    cursor = 0
    replacement_index = 0
    for match in MDAT_KEY_VALUE_RE.finditer(line):
        pieces.append(line[cursor:match.start("value")])
        key = match.group("key")
        value = match.group("value")
        if key in MDAT_ALLOWED_KEYS and replacement_index < len(translated_texts):
            pieces.append(_escape_menu_content(translated_texts[replacement_index]))
            replacement_index += 1
        else:
            pieces.append(value)
        cursor = match.end("value")
    pieces.append(line[cursor:])
    return "".join(pieces)


def _serialize_ks_block(block: KsBlock, translated_text: str, line_endings: Dict[int, str]) -> Dict[int, str]:
    translated_lines = translated_text.split("\n") if translated_text else [""]
    replacements: Dict[int, str] = {}
    for offset, line_number in enumerate(block.text_line_numbers):
        content = translated_lines[offset] if offset < len(translated_lines) else ""
        replacements[line_number] = content + line_endings.get(line_number, "")
    return replacements


def _serialize_speaker_line(
    block: KsBlock,
    translated_speaker: str,
    line_endings: Dict[int, str],
) -> Dict[int, str]:
    if not translated_speaker or not block.speaker_line_number:
        return {}
    if block.speaker_style == "talk":
        raw_line = block.speaker_raw_line or "@talk"
        if TALK_NAME_ARG_RE.search(raw_line):
            line = TALK_NAME_ARG_RE.sub(rf"name={translated_speaker}", raw_line, count=1)
        else:
            line = f"{raw_line} name={translated_speaker}"
    else:
        line = f"【{translated_speaker}】"
        if block.voice_id:
            line += f"[{block.voice_id}]"
    return {block.speaker_line_number: line + line_endings.get(block.speaker_line_number, "")}


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


def _replace_first(text: str, pattern: str, replacement: str) -> str:
    return re.sub(pattern, lambda _match: replacement, text, count=1, flags=re.DOTALL)


def _replace_between(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return text
    end = text.find(end_marker, start)
    if end == -1:
        return text
    return text[:start] + replacement + text[end:]


def _already_has_wrap_vars(text: str) -> bool:
    if "__CherryAIWrapMessageText(" in text:
        return True
    return "var wrapNum" in text and "var wrapPos" in text and "var oldLine" in text


def _already_has_wrap_block(text: str) -> bool:
    if "\\t\\t/* Wordwrapping code" in text:
        return False
    return (
        "Wordwrapping code" in text
        or "oldLine != conductor.curLineStr" in text
        or "MesLayer.DrawText(__CherryAIWrapMessageText(text));" in text
    )


def _patch_add_wrap_vars(text: str) -> str:
    if _already_has_wrap_vars(text):
        return text
    insert_after = re.search(r"(class\s+KAGWindow\s+extends\s+Window\s*\{\s*)", text)
    if not insert_after:
        insert_after = re.search(r"(ch\s*:\s*function\s*\(\s*elm\s*\)\s*\{)", text)
    if not insert_after:
        set_mes_text = re.search(r"(function\s+SetMesText\s*\(\s*text\s*\)\s*\{\s*)", text)
        if set_mes_text:
            return text[:set_mes_text.start()] + _WRAP_SETMESTEXT_HELPER_SNIPPET + text[set_mes_text.start():]
    if not insert_after:
        return text
    return text[:insert_after.end()] + _WRAP_VARS_SNIPPET + text[insert_after.end():]


def _patch_add_wrap_block(text: str) -> str:
    set_mes_text_call = re.search(r"MesLayer\.DrawText\(\s*text\s*\)\s*;", text)
    if (
        "__CherryAIWrapMessageText(" in text
        and "MesLayer.DrawText(__CherryAIWrapMessageText(text));" not in text
        and set_mes_text_call is not None
    ):
        return (
            text[:set_mes_text_call.start()]
            + "MesLayer.DrawText(__CherryAIWrapMessageText(text));"
            + text[set_mes_text_call.end():]
        )

    escaped_block = re.compile(
        r"\\t\\t/\* Wordwrapping code.*?// end: wordwrapping code\s*",
        re.DOTALL,
    )
    if escaped_block.search(text):
        return escaped_block.sub(lambda _match: _WRAP_BLOCK_SNIPPET, text, count=1)
    existing_block = re.compile(
        r"[ \t]*/\* Wordwrapping code.*?// end: wordwrapping code\s*",
        re.DOTALL,
    )
    match = existing_block.search(text)
    if match:
        existing = match.group(0)
        if existing != _WRAP_BLOCK_SNIPPET:
            return existing_block.sub(lambda _match: _WRAP_BLOCK_SNIPPET, text, count=1)
        return text
    if _already_has_wrap_block(text):
        return text
    ch_start = re.search(r"(ch\s*:\s*function\s*\(\s*elm\s*\)\s*\{)", text)
    if not ch_start:
        return text
    start_idx = ch_start.end()
    ch_end_match = re.search(r"\}\s*incontextof\s+this", text[start_idx:])
    end_idx = start_idx + ch_end_match.start() if ch_end_match else len(text)

    region = text[start_idx:end_idx]
    insert_at: Optional[int] = None

    var_text = re.search(
        r"var\s+text\s*=\s*elm\.text(?:\s*,\s*repage\s*=\s*void)?\s*;",
        region,
    )
    if var_text:
        base = start_idx + var_text.end()
        current_with_back = re.search(
            r"if\s*\(\s*currentWithBack\s*\)\s*"
            r"(?:\{[^\}]*?\}|[^\n\r\{]*)?"
            r"current\.comp\.processCh\(\s*text\s*\)\s*;",
            text[base:end_idx],
            re.DOTALL,
        )
        if current_with_back:
            insert_at = base + current_with_back.end()
        else:
            insert_at = base
    else:
        process_call = re.search(
            r"(?:repage\s*=\s*)?current\.processCh\(\s*text(?:\s*,[^\)]*)?\)\s*;",
            region,
        )
        if process_call:
            insert_at = start_idx + process_call.start()
        else:
            legacy_if = PROCESS_CH_RE.search(region)
            if legacy_if:
                insert_at = start_idx + legacy_if.start()

    if insert_at is None:
        if set_mes_text_call:
            return (
                text[:set_mes_text_call.start()]
                + "MesLayer.DrawText(__CherryAIWrapMessageText(text));"
                + text[set_mes_text_call.end():]
            )
        return text
    return text[:insert_at] + _WRAP_BLOCK_SNIPPET + text[insert_at:]


def _patch_select_layer(text: str) -> str:
    patched = text

    defaults_pattern = (
        r"\s*var\s+selectWidth\s*=\s*400;\s*\n"
        r"\s*var\s+selectHeight\s*=\s*50;\s*\n"
        r"\s*var\s+selectColor\s*=\s*0xffffff;\s*\n"
        r"\s*var\s+selectBaseColor\s*=\s*0x888888;\s*\n"
        r"\s*(?:var\s+choiceTextPadding\s*=.*?\n)?"
        r"\s*(?:var\s+choiceVerticalGap\s*=.*?\n)?"
        r"\s*(?:var\s+choiceWordWrap\s*=.*?\n)?"
        r"\s*var\s+fontSize\s*=\s*\d+;"
    )
    if re.search(defaults_pattern, patched, re.DOTALL):
        patched = _replace_first(patched, defaults_pattern, _SELECT_DEFAULTS_SNIPPET.rstrip("\n"))

    if 'var renderedMessage = "";' in patched:
        patched = _replace_between(
            patched,
            'var renderedMessage = "";',
            "function redraw() {",
            _SELECT_BUTTON_HELPERS_SNIPPET.rstrip("\n") + "\n\n    ",
        )
    else:
        patched = _replace_between(
            patched,
            "function _wrapChoiceMessageByWord(message, maxWidth) {",
            "function redraw() {",
            _SELECT_BUTTON_HELPERS_SNIPPET.rstrip("\n") + "\n\n    ",
        )

    helper_marker = "function _wrapChoiceMessageByWord(message, maxWidth)"
    if helper_marker not in patched:
        patched = patched.replace(
            "\tfunction redraw() {",
            _SELECT_BUTTON_HELPERS_SNIPPET + "\n\tfunction redraw() {",
            1,
        )

    patched = _replace_between(
        patched,
        "function redraw() {",
        "function finalize() {",
        _SELECT_REDRAW_SNIPPET.rstrip("\n") + "\n\n    ",
    )

    patched = _replace_between(
        patched,
        "function getSelectPositions(count) {",
        "function start(parent, absolute) {",
        _SELECT_POSITIONS_SNIPPET.rstrip("\n") + "\n\n    ",
    )

    return patched


def _stage_or_resolve_project_file(
    project_root: Path,
    input_root: Optional[Path],
    candidates: Sequence[Path],
) -> Optional[Path]:
    for relative in candidates:
        candidate = project_root / relative
        if candidate.exists():
            return candidate
    if input_root is None:
        return None
    for relative in candidates:
        source_candidate = input_root / relative
        if source_candidate.exists():
            target = project_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source_candidate.read_bytes())
            return target
    return None


def _patch_project_script(
    project_root: Path,
    input_root: Optional[Path],
    candidates: Sequence[Path],
    patcher: Callable[[str], str],
) -> None:
    target = _stage_or_resolve_project_file(project_root, input_root, candidates)
    if target is None:
        return

    text, encoding, bom = _read_text_with_bom(target)
    patched = patcher(text)
    if patched == text:
        return
    if not _is_balanced(patched):
        return

    backup = target.with_suffix(target.suffix + ".bak")
    if not backup.exists():
        _write_text_with_bom(backup, text, encoding, bom)
    _write_text_with_bom(target, patched, encoding, bom)


def _apply_script_patch_target(
    target: Path,
    patcher: Callable[[str], str],
    log: Callable[[str], None],
) -> PatchApplicationResult:
    try:
        text, encoding, bom = _read_text_with_bom(target)
    except (OSError, UnicodeDecodeError) as exc:
        return PatchApplicationResult(
            status="failed",
            message=f"Failed to read {target}: {exc}",
            target_path=target,
        )

    patched = patcher(text)
    if patched == text:
        return PatchApplicationResult(
            status="unchanged",
            message=f"No changes were needed for {target.name}.",
            target_path=target,
        )
    if not _is_balanced(patched):
        return PatchApplicationResult(
            status="failed",
            message=f"Patch generated unbalanced script content for {target.name}.",
            target_path=target,
        )

    backup = target.with_suffix(target.suffix + ".bak")
    if not backup.exists():
        _write_text_with_bom(backup, text, encoding, bom)
        log(f"Created backup {backup}")

    _write_text_with_bom(target, patched, encoding, bom)
    return PatchApplicationResult(
        status="applied",
        message=f"Patched {target}",
        target_path=target,
    )


def _apply_mainwindow_wordwrap_target(
    target: Path,
    log: Callable[[str], None],
) -> PatchApplicationResult:
    return _apply_script_patch_target(
        target,
        lambda text: _patch_add_wrap_block(_patch_add_wrap_vars(text)),
        log,
    )


def _apply_selectlayer_choice_wrap_target(
    target: Path,
    log: Callable[[str], None],
) -> PatchApplicationResult:
    return _apply_script_patch_target(target, _patch_select_layer, log)


def _patch_fix_dlc_checks(text: str) -> str:
    """Relax brittle DLC gates that fail on loose override file chunk checks."""

    def _replace(match: re.Match[str]) -> str:
        storage_name = match.group("storage")
        return f'Storages.isExistentStorage("{storage_name}")'

    return DLC_CHECK_GUARD_RE.sub(_replace, text)


def _apply_fix_dlc_checks_target(
    target: Path,
    log: Callable[[str], None],
) -> PatchApplicationResult:
    return _apply_script_patch_target(target, _patch_fix_dlc_checks, log)


# ---------------------------------------------------------------------------
# Patch test callbacks
# ---------------------------------------------------------------------------

def _test_mainwindow_wordwrap_target(
    target: Path,
    log: Callable[[str], None],
) -> PatchTestResult:
    """Check whether the MainWindow wordwrap patch can be applied."""
    try:
        text, _enc, _bom = _read_text_with_bom(target)
    except (OSError, UnicodeDecodeError) as exc:
        return PatchTestResult(status="error", message=f"Cannot read {target.name}: {exc}")

    if _already_has_wrap_vars(text) or _already_has_wrap_block(text):
        return PatchTestResult(status="already_applied", message="Wordwrap patch is already applied.")

    # Look for patchable anchors
    has_ch = bool(re.search(r"ch\s*:\s*function\s*\(\s*elm\s*\)", text))
    has_set_mes = bool(re.search(r"function\s+SetMesText\s*\(\s*text\s*\)", text))
    has_mes_draw = bool(re.search(r"MesLayer\.DrawText\(\s*text\s*\)\s*;", text))

    if has_ch or has_set_mes or has_mes_draw:
        return PatchTestResult(status="ok", message="Patch can be applied.")
    return PatchTestResult(
        status="cannot_apply",
        message=(
            "No patchable anchor found (ch: function, SetMesText, or MesLayer.DrawText)."
        ),
    )


def _test_selectlayer_choice_wrap_target(
    target: Path,
    log: Callable[[str], None],
) -> PatchTestResult:
    """Check whether the SelectLayer choice-wrap patch can be applied."""
    try:
        text, _enc, _bom = _read_text_with_bom(target)
    except (OSError, UnicodeDecodeError) as exc:
        return PatchTestResult(status="error", message=f"Cannot read {target.name}: {exc}")

    patched = _patch_select_layer(text)
    if patched == text:
        # No change — either already applied or unsupported structure
        if "multiline" in text.lower() and "__CherryAI" in text:
            return PatchTestResult(status="already_applied", message="SelectLayer patch is already applied.")
        return PatchTestResult(
            status="cannot_apply",
            message="No patchable SelectLayer patterns found in this file.",
        )
    return PatchTestResult(status="ok", message="Patch can be applied.")


def _test_fix_dlc_checks_target(
    target: Path,
    log: Callable[[str], None],
) -> PatchTestResult:
    """Check whether the DLC check fix can be applied."""
    try:
        text, _enc, _bom = _read_text_with_bom(target)
    except (OSError, UnicodeDecodeError) as exc:
        return PatchTestResult(status="error", message=f"Cannot read {target.name}: {exc}")

    if DLC_CHECK_GUARD_RE.search(text):
        return PatchTestResult(status="ok", message="DLC check pattern found; patch can be applied.")
    return PatchTestResult(
        status="cannot_apply",
        message="No brittle DLC check pattern found; patch is not needed or already applied.",
    )


# ---------------------------------------------------------------------------
# MessageLayer wordwrap workflow (alternative to MainWindow approach)
# ---------------------------------------------------------------------------

def _run_messagelayer_wordwrap_workflow(
    mgr: object,
    patch_info: object,
    parent: object,
    log: Callable[[str], None],
) -> PatchApplicationResult:
    """Deploy the bundled CherryAI MessageLayer.tjs for pixel-based wordwrap.

    This is the kanotsuku2-style alternative to the KAG ``ch: function``
    wordwrap approach.  It copies the pre-built template from the library into
    ``patch/data/system/`` under the project's staged Translated tree.
    """
    try:
        project_dir = mgr.get_project_dir()  # type: ignore[union-attr]
        translated_dir = mgr.get_translated_dir()  # type: ignore[union-attr]
        original_dir = mgr.get_original_dir()  # type: ignore[union-attr]
    except Exception as exc:
        return PatchApplicationResult(
            status="failed",
            message=f"Cannot resolve project staging directories: {exc}",
        )

    try:
        dest = stage_kirikiri_message_layer_template(
            project_dir,
            translated_dir,
            source_roots=(translated_dir, original_dir),
        )
    except FileNotFoundError as exc:
        return PatchApplicationResult(status="failed", message=str(exc))
    except Exception as exc:
        return PatchApplicationResult(
            status="failed",
            message=f"Failed to stage MessageLayer.tjs: {exc}",
        )

    log(f"Staged MessageLayer.tjs with current font config values → {dest}")

    return PatchApplicationResult(
        status="applied",
        message=(
            f"Deployed pixel-based wordwrap MessageLayer.tjs to {dest}. "
            "This approach wraps text by pixel width instead of character count."
        ),
        target_path=dest,
    )


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


def _parse_patch_container_priority(name: str) -> Tuple[int, str, int]:
    """Return ``(category, special_name, number)`` for a root path segment."""
    normalized = name.strip().lower()
    normal_match = PATCH_NORMAL_CONTAINER_RE.match(normalized)
    if normal_match is not None:
        num_raw = normal_match.group("num") or ""
        return 1, "", int(num_raw) if num_raw else 0

    special_match = PATCH_SPECIAL_CONTAINER_RE.match(normalized)
    if special_match is not None:
        special_name = (special_match.group("name") or "").lower()
        num_raw = special_match.group("num") or ""
        return 2, special_name, int(num_raw) if num_raw else 0

    return 0, "", 0


def _build_kirikiri_overlay_key(relative_path: Path) -> str:
    """Build case-insensitive overlay key for KiriKiri2 input precedence.

    Matching is filename-only so duplicate filenames are treated as one target
    regardless of folder depth.
    """
    parts = relative_path.parts
    if not parts:
        return ""

    first = parts[0]
    base_name = first[:-4] if first.lower().endswith(".xp3") else first
    patch_category, _special_name, _number = _parse_patch_container_priority(base_name)

    if first.lower().endswith(".xp3") or patch_category != 0:
        payload_parts = parts[1:]
    else:
        payload_parts = parts

    if payload_parts:
        leaf_name = str(payload_parts[-1])
    else:
        leaf_name = Path(first).name

    return Path(leaf_name).name.lower()


def _build_kirikiri_priority_key(relative_path: Path) -> Tuple[int, str, int, str]:
    """Build deterministic sort key for KiriKiri2 patch/container precedence."""
    parts = relative_path.parts
    if not parts:
        return 0, "", 0, ""

    first = parts[0]
    base_name = first[:-4] if first.lower().endswith(".xp3") else first
    category, special_name, number = _parse_patch_container_priority(base_name)
    return category, special_name, number, relative_path.as_posix().lower()


class KiriKiri2Parser(ParserScript):
    """Parser for KiriKiri2/KAG `.ks`, `.tjs`, and schema-based `.csv` files."""

    def __init__(self) -> None:
        self._tagged_cache: Dict[str, _CachedTaggedExtraction] = {}

    @property
    def name(self) -> str:
        return "KiriKiri2"

    @property
    def tooltip(self) -> str:
        return "KiriKiri2/KAG scenario and menu parser"

    @property
    def size_whitelist_filenames(self) -> Sequence[str]:
        return KIRIKIRI2_SIZE_WHITELIST_FILENAMES

    @property
    def size_whitelist_filename_patterns(self) -> Sequence[re.Pattern[str]]:
        return KIRIKIRI2_SIZE_WHITELIST_FILENAME_PATTERNS

    @property
    def size_whitelist_suffixes(self) -> Sequence[str]:
        return KIRIKIRI2_SIZE_WHITELIST_SUFFIXES

    @property
    def supplemental_stage_filenames(self) -> Sequence[str]:
        return KIRIKIRI2_SUPPLEMENTAL_STAGE_FILENAMES

    @property
    def supplemental_stage_relative_paths(self) -> Sequence[str]:
        return KIRIKIRI2_SUPPLEMENTAL_STAGE_RELATIVE_PATHS

    @property
    def wordwrap_config(self) -> Optional[WordwrapConfig]:
        return WordwrapConfig(max_line_length=42, max_line_number=3, wordwrap_command="\n")

    def wordwrap_for_tag(self, tag: str) -> Optional[WordwrapConfig]:
        if tag in {"menu", "choice", "SaveLocation", "dialog"}:
            return WordwrapConfig(max_line_length=32, max_line_number=2, wordwrap_command="\n")
        return self.wordwrap_config

    @property
    def project_patches(self) -> Sequence[ParserProjectPatch]:
        return (
            # ---- Dialogue wordwrap: mutually exclusive alternatives ----
            ParserProjectPatch(
                patch_id="mainwindow_wordwrap",
                name="MainWindow Wordwrap Patch",
                description=(
                    "Patch MainWindow.tjs so KAG dialogue wraps by word rather "
                    "than per character.  Suitable for standard KiriKiri2/KAG games."
                ),
                file_label="MainWindow.tjs",
                relative_candidates=(
                    Path("data") / "system" / "MainWindow.tjs",
                    Path("system") / "MainWindow.tjs",
                ),
                apply_to_target=_apply_mainwindow_wordwrap_target,
                alternative_group="wordwrap",
                alternative_group_label="Text Wordwrap Method",
                test_target=_test_mainwindow_wordwrap_target,
            ),
            ParserProjectPatch(
                patch_id="messagelayer_wordwrap",
                name="MessageLayer Wordwrap Patch",
                description=(
                    "Deploy the CherryAI MessageLayer.tjs template which wraps "
                    "dialogue by pixel line-width instead of character count.  "
                    "Recommended for kanotsuku2-style games whose engine measures "
                    "text in pixels."
                ),
                file_label="MessageLayer.tjs",
                # No relative_candidates — file is deployed from the library, not patched
                relative_candidates=(),
                apply_to_target=lambda _target, _log: PatchApplicationResult(
                    status="failed",
                    message=(
                        "MessageLayer Wordwrap Patch must run through its "
                        "shared workflow."
                    ),
                ),
                apply_with_context=_run_messagelayer_wordwrap_workflow,
                alternative_group="wordwrap",
                alternative_group_label="Text Wordwrap Method",
            ),
            # ---- Choice / select layer ----
            ParserProjectPatch(
                patch_id="selectlayer_choice_wrap",
                name="SelectLayer Choice Wrap Patch",
                description=(
                    "Patch SelectLayer.tjs so choice buttons wrap and size text "
                    "more safely."
                ),
                file_label="SelectLayer.tjs",
                relative_candidates=(
                    Path("data") / "system" / "SelectLayer.tjs",
                    Path("system") / "SelectLayer.tjs",
                ),
                apply_to_target=_apply_selectlayer_choice_wrap_target,
                test_target=_test_selectlayer_choice_wrap_target,
            ),
            # ---- DLC compatibility ----
            ParserProjectPatch(
                patch_id="fix_dlc_checks",
                name="Fix DLC checks",
                description=(
                    "Patch brittle isExistentStorage + CheckCompChunk DLC gates "
                    "in ImportantData.tjs so loose overrides do not disable DLC "
                    "detection."
                ),
                file_label="ImportantData.tjs",
                relative_candidates=(
                    Path("ImportantData.tjs"),
                    Path("data") / "system" / "ImportantData.tjs",
                    Path("system") / "ImportantData.tjs",
                    Path("patch") / "ImportantData.tjs",
                ),
                apply_to_target=_apply_fix_dlc_checks_target,
                test_target=_test_fix_dlc_checks_target,
            ),
            # ---- UI translation (multiple required files) ----
            ParserProjectPatch(
                patch_id="standard_ui_translation",
                name="Standard UI Translation Patch",
                description=(
                    "Stage translated KiriKiri menu, folder, help, cache, and "
                    "version UI overlays under patch/data/."
                ),
                file_label="MenuItemManager.tjs",
                relative_candidates=(),
                apply_to_target=lambda _target, _log: PatchApplicationResult(
                    status="failed",
                    message=(
                        "Standard UI Translation Patch must run through its "
                        "shared workflow."
                    ),
                ),
                apply_with_context=run_kirikiri_standard_ui_translation_patch_workflow,
                # Demonstrates multi-file requirement (informational)
                required_companions=(
                    ("CacheWindow.tjs", (
                        Path("data") / "program" / "CacheWindow.tjs",
                        Path("program") / "CacheWindow.tjs",
                    )),
                    ("VersionWindow.tjs", (
                        Path("data") / "system" / "VersionWindow.tjs",
                        Path("system") / "VersionWindow.tjs",
                    )),
                ),
            ),
            # ---- Font patch (multi-file) ----
            ParserProjectPatch(
                patch_id="font_patch",
                name="Font Patch",
                description=(
                    "Stage a private-font version.dll patch, config, and bundled "
                    "fonts for KiriKiri projects."
                ),
                file_label="version.dll",
                relative_candidates=(),
                apply_to_target=lambda _target, _log: PatchApplicationResult(
                    status="failed",
                    message="Font Patch must run through its shared dialog workflow.",
                ),
                apply_with_context=run_kirikiri_font_patch_workflow,
                # Demonstrates combined multi-file + custom workflow
                required_companions=(
                    ("MessageLayer.tjs", (
                        Path("data") / "system" / "MessageLayer.tjs",
                        Path("system") / "MessageLayer.tjs",
                    )),
                    ("AffineLayer.tjs", (
                        Path("data") / "system" / "AffineLayer.tjs",
                        Path("system") / "AffineLayer.tjs",
                    )),
                    ("ButtonLayer.tjs", (
                        Path("data") / "system" / "ButtonLayer.tjs",
                        Path("system") / "ButtonLayer.tjs",
                    )),
                ),
            ),
        )

    def detect_encoding(self, file_path: Path) -> Optional[str]:
        if file_path.suffix.lower() == ".ks":
            _, encoding = _read_text(file_path, KS_ENCODING_CANDIDATES)
            return encoding
        if file_path.suffix.lower() == ".tjs":
            _, encoding = _read_text(file_path, MENU_ENCODING_CANDIDATES)
            return encoding
        if file_path.suffix.lower() == ".csv":
            _, encoding = _read_text(file_path, CSV_ENCODING_CANDIDATES)
            return encoding
        if file_path.suffix.lower() == ".mdat":
            _, encoding = _read_text(file_path, MDAT_ENCODING_CANDIDATES)
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
        if suffix == ".tjs":
            if not path.exists():
                return name == "menus.tjs"
            try:
                text, _ = _read_text(path, MENU_ENCODING_CANDIDATES)
            except Exception:
                return False
            lowered = text.lower()
            if name == "menus.tjs":
                return "kagmenuitem" in lowered or "menuitem" in lowered
            return (
                "caption:" in lowered
                or "setyesno(" in lowered
                or "setok(" in lowered
                or "setmessage(" in lowered
                or "seterror(" in lowered
            )
        if suffix == ".csv":
            if not path.exists():
                return False
            return _looks_like_kirikiri_csv(path)
        if suffix == ".mdat":
            if not path.exists():
                return False
            return _looks_like_kirikiri_mdat(path)
        return False

    def deduplicate_input_paths(
        self,
        paths: Sequence[Path],
        *,
        root: Optional[Path] = None,
    ) -> List[Path]:
        """Resolve KiriKiri2 file precedence across normal/patch/special containers.

        Load-order semantics:
        1. Non-patch containers
        2. ``patch``, ``patch2``, ...
        3. ``patch_<name>``, ``patch_<name>2``, ... sorted by ``<name>`` then number

        For matching overlay keys, later precedence wins. Returned paths are the
        surviving candidates sorted in precedence order.
        """
        if not paths:
            return []

        root_path = Path(root) if root is not None else None
        candidates: List[Tuple[Tuple[int, str, int, str], str, Path]] = []
        for raw_path in paths:
            candidate_path = Path(raw_path)
            relative_path = candidate_path
            if root_path is not None:
                try:
                    relative_path = candidate_path.relative_to(root_path)
                except ValueError:
                    relative_path = candidate_path

            priority_key = _build_kirikiri_priority_key(relative_path)
            overlay_key = _build_kirikiri_overlay_key(relative_path)
            candidates.append((priority_key, overlay_key, candidate_path))

        candidates.sort(key=lambda item: item[0])
        winner_by_overlay: Dict[str, Tuple[Tuple[int, str, int, str], str, Path]] = {}
        for candidate in candidates:
            winner_by_overlay[candidate[1]] = candidate

        winners = sorted(winner_by_overlay.values(), key=lambda item: item[0])
        return [item[2] for item in winners]

    def extract(self, file_path: Path) -> List[str]:
        tagged = self.extract_tagged(file_path)
        return [line.text for line in tagged] if tagged else []

    def extract_tagged(self, file_path: Path) -> Optional[List[ExtractedLine]]:
        cached = self._get_cached_tagged(file_path)
        if cached is not None:
            return cached

        tagged = self._build_tagged(file_path)
        if tagged is None:
            return None

        self._store_cached_tagged(file_path, tagged)
        return list(tagged)

    def _build_tagged(self, file_path: Path) -> Optional[List[ExtractedLine]]:
        path = Path(file_path)
        if path.suffix.lower() == ".ks":
            extracted: List[ExtractedLine] = []
            line_numbers: List[int] = []
            for line_number, _priority, unit_kind, unit in _extract_ks_units(path):
                if unit_kind == "block":
                    block = unit
                    assert isinstance(block, KsBlock)
                    extracted.append(
                        ExtractedLine(
                            text=block.extracted_text,
                            tag=block.tag,
                            speaker=block.speaker,
                            context=f"{path.name}:{block.start_line}",
                        )
                    )
                    line_numbers.append(block.start_line)
                    continue
                entry = unit
                assert isinstance(entry, KsLiteralEntry)
                extracted.append(
                    ExtractedLine(
                        text=entry.text,
                        tag=entry.tag,
                        context=f"{path.name}:{line_number}",
                    )
                )
                line_numbers.append(entry.line_number)
            return _annotate_extracted_line_locators(extracted, line_numbers)

        if path.name.lower() == "menus.tjs":
            entries = _extract_menu_literals(path)
            extracted = [
                ExtractedLine(text=entry.text, tag="menu", context=f"{path.name}:{entry.line_index + 1}")
                for entry in entries
            ]
            return _annotate_extracted_line_locators(
                extracted,
                [entry.line_index + 1 for entry in entries],
            )
        if path.suffix.lower() == ".tjs":
            extracted: List[ExtractedLine] = []
            line_numbers: List[int] = []
            for entry in _extract_tjs_caption_entries(path):
                extracted.append(
                    ExtractedLine(
                        text=entry.text,
                        tag="menu",
                        context=f"{path.name}:{entry.line_index + 1}",
                    )
                )
                line_numbers.append(entry.line_index + 1)
            for entry in _extract_tjs_dialog_entries(path):
                extracted.append(
                    ExtractedLine(
                        text=entry.text,
                        tag="dialog",
                        context=f"{path.name}:{entry.line_index + 1}",
                    )
                )
                line_numbers.append(entry.line_index + 1)
            for entry in _extract_tjs_code_literal_entries(path):
                extracted.append(
                    ExtractedLine(
                        text=entry.text,
                        tag=entry.tag,
                        context=f"{path.name}:{entry.line_index + 1}",
                    )
                )
                line_numbers.append(entry.line_index + 1)
            for entry in _extract_tjs_rand_name_entries(path):
                extracted.append(
                    ExtractedLine(
                        text=entry.text,
                        tag=entry.tag,
                        context=f"{path.name}:{entry.line_index + 1}",
                    )
                )
                line_numbers.append(entry.line_index + 1)
            return _annotate_extracted_line_locators(extracted, line_numbers)
        if path.suffix.lower() == ".csv":
            entries = _extract_csv_entries(path)
            extracted = [
                ExtractedLine(
                    text=entry.text,
                    tag=entry.tag,
                    context=f"{path.name}:{entry.row_index + 1}:{entry.header}",
                )
                for entry in entries
            ]
            return _annotate_extracted_line_locators(
                extracted,
                [entry.row_index + 1 for entry in entries],
            )
        if path.suffix.lower() == ".mdat":
            entries = _extract_mdat_entries(path)
            extracted = [
                ExtractedLine(
                    text=entry.text,
                    tag=entry.tag,
                    context=f"{path.name}:{entry.line_index + 1}:{entry.key}",
                )
                for entry in entries
            ]
            return _annotate_extracted_line_locators(
                extracted,
                [entry.line_index + 1 for entry in entries],
            )
        return None

    def _get_cached_tagged(self, file_path: Path) -> Optional[List[ExtractedLine]]:
        path = Path(file_path)
        try:
            stat = path.stat()
        except OSError:
            return None

        resolved = str(path.resolve())
        cached = self._tagged_cache.get(resolved)
        if cached is None:
            return None
        if cached.mtime_ns != stat.st_mtime_ns or cached.size != stat.st_size:
            self._tagged_cache.pop(resolved, None)
            return None
        return list(cached.tagged)

    def _store_cached_tagged(
        self,
        file_path: Path,
        tagged: Sequence[ExtractedLine],
    ) -> None:
        path = Path(file_path)
        try:
            stat = path.stat()
        except OSError:
            return

        self._tagged_cache[str(path.resolve())] = _CachedTaggedExtraction(
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
            tagged=tuple(tagged),
        )

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
            units = _extract_ks_units(path)
            search_keys = (
                orig_lines
                if orig_lines is not None
                else [
                    unit.extracted_text if unit_kind == "block" else unit.text
                    for _line, _priority, unit_kind, unit in units
                ]
            )
            line_endings = {
                index + 1: _split_line_ending(raw_line)[1]
                for index, raw_line in enumerate(raw_lines)
            }
            replacements: Dict[int, str] = {}
            failures: List[int] = []
            for index, translated in enumerate(lines):
                if index >= len(units):
                    failures.append(index)
                    continue
                _line_number, _priority, unit_kind, unit = units[index]
                search = (
                    search_keys[index]
                    if index < len(search_keys)
                    else unit.extracted_text if unit_kind == "block" else unit.text
                )
                if translated == search:
                    continue
                if unit_kind == "block":
                    block = unit
                    assert isinstance(block, KsBlock)
                    search_speaker, search_dialogue = _split_extracted_text(search)
                    translated_speaker, translated_dialogue = _split_extracted_text(translated)
                    if block.speaker:
                        if not search_dialogue:
                            search_dialogue = block.joined_text
                        if translated_speaker and translated_speaker != (search_speaker or block.speaker):
                            replacements.update(
                                _serialize_speaker_line(block, translated_speaker, line_endings)
                            )
                        replacements.update(
                            _serialize_ks_block(block, translated_dialogue, line_endings)
                        )
                    else:
                        replacements.update(_serialize_ks_block(block, translated, line_endings))
                    continue

                entry = unit
                assert isinstance(entry, KsLiteralEntry)
                line_index = entry.line_number - 1
                if line_index < 0 or line_index >= len(raw_lines):
                    failures.append(index)
                    continue
                if entry.entry_kind == "seladd":
                    replaced = _replace_seladd_text(raw_lines[line_index], translated)
                elif entry.entry_kind == "choice_text_attr":
                    replaced = _replace_pattern_literal_by_index(
                        raw_lines[line_index],
                        CHOICE_TEXT_ATTR_RE,
                        translated,
                        entry.literal_index,
                    )
                elif entry.entry_kind == "label_title":
                    replaced = _replace_label_title(raw_lines[line_index], translated)
                elif entry.entry_kind == "dialog_call":
                    replaced = _replace_pattern_literal_by_index(
                        raw_lines[line_index],
                        DIALOG_MGR_LITERAL_RE,
                        translated,
                        entry.literal_index,
                    )
                elif entry.entry_kind == "ui_field":
                    replaced = _replace_pattern_literal_by_index(
                        raw_lines[line_index],
                        KS_UI_FIELD_LITERAL_RE,
                        translated,
                        entry.literal_index,
                    )
                else:
                    replaced = _replace_pattern_literal_by_index(
                        raw_lines[line_index],
                        KS_DRAWTEXT_LITERAL_RE,
                        translated,
                        entry.literal_index,
                    )
                if replaced is None:
                    failures.append(index)
                    continue
                raw_lines[line_index] = replaced
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

        if path.suffix.lower() == ".tjs":
            text, encoding = _read_text(path, MENU_ENCODING_CANDIDATES)
            raw_lines = text.splitlines(keepends=True)
            entries = _extract_tjs_caption_entries(path)
            dialog_entries = _extract_tjs_dialog_entries(path)
            code_entries = _extract_tjs_code_literal_entries(path)
            rand_name_entries = _extract_tjs_rand_name_entries(path)
            grouped: Dict[int, List[str]] = {}
            dialog_grouped: Dict[int, List[str]] = {}
            code_grouped: Dict[int, List[Tuple[int, str]]] = {}
            failures: List[int] = []
            combined_entries: List[CaptionEntry | DialogLiteralEntry | TjsCodeLiteralEntry] = [
                *entries,
                *dialog_entries,
                *code_entries,
                *rand_name_entries,
            ]
            search_keys = (
                orig_lines
                if orig_lines is not None
                else [entry.text for entry in combined_entries]
            )
            for index, translated in enumerate(lines):
                if index >= len(combined_entries):
                    failures.append(index)
                    continue
                entry = combined_entries[index]
                search = search_keys[index] if index < len(search_keys) else entry.text
                if translated == search:
                    continue
                if isinstance(entry, CaptionEntry):
                    grouped.setdefault(entry.line_index, []).append(translated)
                elif isinstance(entry, DialogLiteralEntry):
                    dialog_grouped.setdefault(entry.line_index, []).append(translated)
                else:
                    code_grouped.setdefault(entry.line_index, []).append(
                        (entry.literal_index, translated)
                    )
            for line_index, translated_texts in grouped.items():
                raw_lines[line_index] = _replace_caption_literals(raw_lines[line_index], translated_texts)
            for line_index, translated_texts in dialog_grouped.items():
                raw_lines[line_index] = _replace_tjs_dialog_literals(
                    raw_lines[line_index],
                    translated_texts,
                )
            for line_index, replacements in code_grouped.items():
                current = raw_lines[line_index]
                for literal_index, translated_text in sorted(replacements, key=lambda item: item[0]):
                    replaced = _replace_string_literal_by_index(
                        current,
                        translated_text,
                        literal_index,
                    )
                    if replaced is not None:
                        current = replaced
                raw_lines[line_index] = current
            _write_text(output_path, "".join(raw_lines), encoding)
            return failures

        if path.suffix.lower() == ".csv":
            rows, encoding, newline = _read_csv_rows(path)
            entries = _extract_csv_entries(path)
            failures: List[int] = []
            is_randomcomment_file = RANDOMCOMMENT_CSV_RE.match(path.name) is not None
            search_keys = orig_lines if orig_lines is not None else [entry.text for entry in entries]
            for index, translated in enumerate(lines):
                if index >= len(entries):
                    failures.append(index)
                    continue
                entry = entries[index]
                search = search_keys[index] if index < len(search_keys) else entry.text
                if translated == search:
                    continue
                row = rows[entry.row_index]
                if entry.col_index >= len(row):
                    row.extend([""] * (entry.col_index + 1 - len(row)))
                if is_randomcomment_file and entry.tag == "csv_randomcomment":
                    translated = _normalize_randomcomment_profile_text(translated)
                row[entry.col_index] = translated
            _write_csv_rows(output_path, rows, encoding, newline)
            return failures

        if path.suffix.lower() == ".mdat":
            text, encoding = _read_text(path, MDAT_ENCODING_CANDIDATES)
            raw_lines = text.splitlines(keepends=True)
            entries = _extract_mdat_entries(path)
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
                grouped.setdefault(entry.line_index, []).append(translated)
            for line_index, translated_texts in grouped.items():
                raw_lines[line_index] = _replace_mdat_literals(raw_lines[line_index], translated_texts)
            _write_text(output_path, "".join(raw_lines), encoding)
            return failures

        text, encoding = _read_text(path, ("utf-8", "cp932", "shift_jis"))
        _write_text(output_path, text, encoding)
        return list(range(len(lines)))

    def post_inject_project(self, project_root: Path, *, input_root: Optional[Path] = None) -> None:
        pass