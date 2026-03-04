"""Code pattern detection and glossary functions for CherryAI.

This module contains all functions for:
- Code pattern detection (tags, escape sequences, brackets, etc.)
- Code normalization for similarity grouping
- Parenthesis-based code detection
- Code glossary updates
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

# Import constants from code_glossary_constants
from .code_glossary_constants import (
    CODE_PATTERNS,
    COLOR_NAMES,
    RPGM_VAR_RE,
    RPGM_ACTOR_RE,
    CODE_GLOSSARY_HEADER,
    TYPE_LINEBREAK,
    TYPE_VARIABLENAME,
    TYPE_VARIABLENUMBER,
    TYPE_VISIBLEVARIABLE,
    TYPE_COLOR,
    TYPE_FONT,
    TYPE_RUBY,
    TYPE_UNKNOWN,
)

# NOTE: Avoid importing heavyweight glossary module at import time to prevent
# circular imports. Import required symbols lazily inside functions that need them.
# Only import constants from code_glossary_constants at module load time.


# ---------------- Balanced bracket/tag detection ---------------- #


def _find_balanced_code(line: str, start_idx: int, open_char: str) -> Optional[int]:
    """Find the closing character for a bracket/tag starting at start_idx.
    
    Handles nested structures properly: <<>> and <[]> etc.
    
    Args:
        line: The line to search
        start_idx: Index of opening character
        open_char: Opening character ('<', '{', or '[')
        
    Returns:
        Index of matching closing character, or None if unbalanced
    """
    # Map opening to closing characters
    close_map = {'<': '>', '{': '}', '[': ']'}
    close_char = close_map.get(open_char)
    if not close_char:
        return None
    
    depth = 1
    i = start_idx + 1
    
    while i < len(line) and depth > 0:
        ch = line[i]
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    
    # Unbalanced - no matching close found
    return None


def _extract_all_balanced_code(line: str) -> List[Tuple[int, int, str]]:
    """Extract all balanced code segments from a line.
    
    Scans left to right for opening brackets/tags (<, {, [) and extracts
    complete balanced segments, skipping nested inner content.
    
    IMPORTANT: Escape sequences like \n are extracted as STANDALONE codes.
    They are NOT combined with following code (e.g., \n[font] becomes TWO codes: \n and [font]).
    
    Returns:
        List of (start, end, code_segment) tuples
    """
    results: List[Tuple[int, int, str]] = []
    i = 0
    
    while i < len(line):
        ch = line[i]
        
        # Check for escape sequences first (don't need balancing)
        if ch == '\\' and i + 1 < len(line):
            next_ch = line[i + 1]
            # RPG Maker style sequences like \V[123], \N[123], \C[123] - MUST come before simple escapes
            # NOTE: Only match UPPERCASE letters to avoid matching linebreak \n followed by [...]
            if next_ch in 'VNC' and i + 2 < len(line) and line[i + 2] == '[':
                # Find closing bracket for this specific escape
                close_idx = _find_balanced_code(line, i + 2, '[')
                if close_idx is not None:
                    results.append((i, close_idx + 1, line[i:close_idx + 1]))
                    i = close_idx + 1
                    continue
            # Common escape sequences (STANDALONE - not combined with following code)
            # \n, \r, \t (lowercase) are linebreak-style escapes - extracted as individual codes
            # \N, \R, \T (uppercase) without brackets are also single-char escapes
            if next_ch in 'nrtNRT':
                results.append((i, i + 2, line[i:i + 2]))
                i += 2
                continue
            # Hex escapes like \xAB
            elif next_ch == 'x' and i + 3 < len(line):
                if all(c in '0123456789ABCDEFabcdef' for c in line[i + 2:i + 4]):
                    results.append((i, i + 4, line[i:i + 4]))
                    i += 4
                    continue
            # Unicode escapes like \uABCD
            elif next_ch == 'u' and i + 5 < len(line):
                if all(c in '0123456789ABCDEFabcdef' for c in line[i + 2:i + 6]):
                    results.append((i, i + 6, line[i:i + 6]))
                    i += 6
                    continue
            # Font control sequences like \{ and \}
            elif next_ch in '{}':
                results.append((i, i + 2, line[i:i + 2]))
                i += 2
                continue
        
        # Check for opening brackets/tags
        if ch in '<{[':
            close_idx = _find_balanced_code(line, i, ch)
            if close_idx is not None:
                code_seg = line[i:close_idx + 1]
                results.append((i, close_idx + 1, code_seg))
                i = close_idx + 1
                continue
        
        i += 1
    
    return results


def _find_parenthesis_code(line: str) -> List[Tuple[int, int]]:
    """Return spans indicating likely code: alnum/JP char immediately followed by '('.

    This is a backwards-compatible helper used by older modules (e.g. analysis.py).
    It returns spans as (start, end) for the '(' character (length 1).
    """
    spans: List[Tuple[int, int]] = []
    if not line:
        return spans
    for i in range(len(line) - 1):
        ch = line[i]
        nxt = line[i + 1]
        if nxt != "(":
            continue
        o = ord(ch)
        if (
            (0x30 <= o <= 0x39)  # 0-9
            or (0x41 <= o <= 0x5A)  # A-Z
            or (0x61 <= o <= 0x7A)  # a-z
            or (0x3040 <= o <= 0x30FF)  # Hiragana/Katakana
            or (0x3400 <= o <= 0x4DBF)  # CJK Ext-A
            or (0x4E00 <= o <= 0x9FFF)  # CJK Unified
        ):
            spans.append((i + 1, i + 2))
    return spans


def classify_code_type(code: str) -> str:
    """Classify a code segment into one of the defined types.
    
    Types:
    - LINEBREAK: \\n (standalone only)
    - VARIABLENAME: \\N[<NUM>] or [n<NUM>] (single-letter n + number)
    - VARIABLENUMBER: Not used - reserved for future
    - VISIBLEVARIABLE: \\V[<NUM>]
    - COLOR: Color-related patterns (font_color, [font color=...], hex codes)
    - FONT: Font control sequences (\\{, \\}, [resetfont], [font_*] without color)
    - RUBY: Ruby annotations ([ruby text=...])
    - UNKNOWN: Everything else
    
    Classification priority:
    1. Linebreak (must be standalone \\n)
    2. RPG Maker escapes (\\N[...], \\V[...], \\C[...])
    3. Ruby annotations
    4. Color patterns (highest priority for [font_COLOR])
    5. Font patterns
    6. Variable names ([n<NUM>])
    7. Unknown fallback
    
    Args:
        code: The code segment to classify
        
    Returns:
        Type constant string
    """
    code_lower = code.lower()
    
    # LINEBREAK: \n ONLY (standalone, not combined with other code)
    if code == '\\n':
        return cast(str, TYPE_LINEBREAK)
    
    # VARIABLENAME: \N[123] (RPG Maker actor name) or [n123] (single-letter n + digits)
    # NOTE: [n123] patterns are generic variables, not RPG Maker specific
    if RPGM_ACTOR_RE.fullmatch(code):
        return cast(str, TYPE_VARIABLENAME)
    # Check for [n123] pattern - treat as UNKNOWN unless it's a special case
    # Only classify as VARIABLENAME if it's explicitly \N[...] (RPG Maker)
    # [n0], [n1], [n2] etc. are just generic variables -> UNKNOWN
    # (They'll normalize to [n<NUM>] for grouping)
    
    # VISIBLEVARIABLE: \V[123] (RPG Maker visible variable)
    if RPGM_VAR_RE.fullmatch(code):
        return cast(str, TYPE_VISIBLEVARIABLE)
    
    # COLOR: Check color patterns with HIGH PRIORITY
    # 1. RPG Maker color codes: \C[123]
    if re.fullmatch(r'\\[Cc]\[\d+\]', code):
        return cast(str, TYPE_COLOR)
    
    # 2. Font with color name: [font_red], [font_blue], etc.
    # Check if it's [font_COLORNAME] pattern
    font_color_match = re.match(r'\[font[_\-](\w+)\]', code, re.IGNORECASE)
    if font_color_match:
        color_part = font_color_match.group(1).lower()
        if color_part in COLOR_NAMES:
            return cast(str, TYPE_COLOR)
    
    # 3. Explicit font color attribute: [font color="..."] or <font color="...">
    if re.search(r'\bcolor\s*=', code_lower):
        return cast(str, TYPE_COLOR)
    
    # 4. Generic 'color' or 'colour' in code
    if 'color' in code_lower or 'colour' in code_lower:
        return cast(str, TYPE_COLOR)
    
    # 5. Linebreak combined with color code: \n[font_blue] etc.
    if code.startswith('\\n[font'):
        # Check if the font part has a color
        inner_match = re.search(r'\[font[_\-](\w+)\]', code, re.IGNORECASE)
        if inner_match:
            color_part = inner_match.group(1).lower()
            if color_part in COLOR_NAMES:
                return cast(str, TYPE_COLOR)
    
    # RUBY: Ruby annotations - [ruby text="..."]
    if 'ruby' in code_lower:
        return cast(str, TYPE_RUBY)
    
    # FONT: Font control sequences
    # 1. Escape sequences: \{ and \}
    if code in ('\\{', '\\}'):
        return cast(str, TYPE_FONT)
    
    # 2. [resetfont] and similar reset patterns
    if re.search(r'\[reset.*?font\]|\[/font\]', code_lower):
        return cast(str, TYPE_FONT)
    
    # 3. Generic [font ...] patterns (but NOT color-related, already handled above)
    if code_lower.startswith('[font') or 'font' in code_lower:
        return cast(str, TYPE_FONT)
    
    # UNKNOWN: Everything else (including [emb exp=...], [if exp=...], [p], [r], [l], [s], etc.)
    return cast(str, TYPE_UNKNOWN)


# ---------------- Code detection ---------------- #


def detect_code(line: str) -> Dict[str, Any]:
    """Detect code-like patterns in a line using balanced bracket detection.
    
    Searches for:
    - HTML/XML tags (balanced)
    - Escape sequences
    - Bracketed/braced segments (balanced)
    - RPG Maker variables
    
    Args:
        line: The line to scan for code patterns
        
    Returns:
        Dict with:
        - count: Total number of code patterns detected
        - spans: List of (start, end, code, type) tuples (up to 50)
        - has_code: Boolean indicating if any code was found
        - codes_by_type: Dict mapping type -> list of code strings
    """
    # Extract all balanced code segments
    code_segments = _extract_all_balanced_code(line)
    
    # Classify each code segment
    classified: List[Tuple[int, int, str, str]] = []
    codes_by_type: Dict[str, List[str]] = {}
    
    for start, end, code in code_segments:
        code_type = classify_code_type(code)
        classified.append((start, end, code, code_type))
        
        if code_type not in codes_by_type:
            codes_by_type[code_type] = []
        codes_by_type[code_type].append(code)
    
    return {
        "count": len(classified),
        "spans": classified[:50],  # Limit to 50 to avoid overwhelming output
        "has_code": bool(classified),
        "codes_by_type": codes_by_type,
    }


# ---------------- Code normalization (kept for similarity grouping) ---------------- #


def _normalize_code_segment(seg: str) -> str:
    """Return a normalized representation for similar code-like segments.

    Goals:
    - Normalize FIRST = in any code to key=VALUE (e.g., [emb exp="..."] -> [emb exp=VALUE])
    - Normalize [ruby text="..."] -> [ruby text=VALUE]
    - Normalize [font color="..."] -> [font color=VALUE]
    - Normalize [n1], [n2], [n3] -> [n<NUM>]
    - Map color-bearing tokens to canonical placeholders (e.g., [font_blue] -> [font_COLOR])
    - Preserve structure for similarity grouping in glossary
    
    Args:
        seg: The code segment to normalize
        
    Returns:
        Normalized code segment string
    """
    try:
        s = seg.strip()
        if not s:
            return s

        # Square brackets: [ ... ] - process BEFORE multi-bracket check
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            
            # Normalize FIRST = in any code to key=VALUE
            # This handles [emb exp=...], [ruby text=...], [if exp=...], [font color=...], etc.
            if "=" in inner:
                eq_pos = inner.index("=")
                key_part = inner[:eq_pos].strip()
                return f"[{key_part}=VALUE]"
            
            inner_l = inner.lower()
            
            # Font with color name: [font_red] -> [font_COLOR]
            m = re.match(r"^font[_\-](\w+)$", inner_l)
            if m:
                color_part = m.group(1)
                if color_part in COLOR_NAMES:
                    return "[font_COLOR]"
                # Not a color, keep as generic font
                return f"[font_{color_part}]"
            
            # Generic font patterns
            if inner_l.startswith("font"):
                return f"[{inner}]"
            
            # Normalize [n1], [n2], etc. to [n<NUM>] for variable pattern
            # Match single letter + digits (e.g., [n123], [v5], [x999])
            if re.fullmatch(r"[a-zA-Z]\d+", inner):
                letter = inner[0]
                return f"[{letter}<NUM>]"
            
            # Collapse other numeric patterns
            innern = re.sub(r"\d+", "<NUM>", inner)
            return f"[{innern}]"

        # Handle multi-bracket spans AFTER single bracket codes
        # Only match when there are TWO separate bracket codes (e.g. "[font_red]Text[resetfont]")
        # NOT when brackets are nested inside a single code (e.g. "[emb exp="...[]..."]")
        if re.search(r"\[[^\]]*?\]\s*[^\[]*\s*\[[^\]]*?\]", s, flags=re.DOTALL):
            m = re.search(r"\[([^\]]*?)\].*?\[([^\]]*?)\]", s, flags=re.DOTALL)
            if m:
                first = m.group(1).lower()
                second = m.group(2).lower()
                if re.match(r"^(font(?:color)?|color|fontcolor)([_\-:=#A-Za-z0-9]*)", first):
                    if re.search(r"#[0-9A-Fa-f]{3,8}", first) or any(n in first for n in COLOR_NAMES) or re.search(r"#[0-9A-Fa-f]{3,8}", second) or any(n in second for n in COLOR_NAMES):
                        return "[BRACKET_SPAN_COLOR]"
                    return "[BRACKET_SPAN]"
                return "[BRACKET_SPAN]"

        # Angle brackets: <tag ...>
        if s.startswith("<") and s.endswith(">"):
            inner = s[1:-1].strip()
            # Normalize FIRST = to key=VALUE
            if "=" in inner:
                eq_pos = inner.index("=")
                key_part = inner[:eq_pos].strip()
                return f"<{key_part}=VALUE>"
            m = re.match(r"^<\s*([A-Za-z0-9]+)([^>]*)>", s)
            if m:
                tag = m.group(1).lower()
                attrs = m.group(2) or ""
                if re.search(r"#[0-9A-Fa-f]{3,8}", attrs):
                    return f"<{tag}_COLOR>"
                for nm in COLOR_NAMES:
                    if re.search(fr"\b{re.escape(nm)}\b", attrs, flags=re.IGNORECASE):
                        return f"<{tag}_COLOR>"
                return f"<{tag}>"
            return "<TAG>"

        # Curly braces: { ... }
        if s.startswith("{") and s.endswith("}"):
            inner = s[1:-1].strip()
            # Normalize FIRST = to key=VALUE
            if "=" in inner:
                eq_pos = inner.index("=")
                key_part = inner[:eq_pos].strip()
                return f"{{{key_part}=VALUE}}"
            innern = re.sub(r"\d+", "<NUM>", inner)
            return "{" + innern + "}"

        # Escapes: keep literal for clarity (e.g., \n, \N[123])
        # But normalize \N[123] -> \N[<NUM>]
        if s.startswith("\\"):
            if len(s) >= 2 and s[1] in 'VNCvnc' and '[' in s:
                # RPG Maker escape with bracket: \N[123] -> \N[<NUM>]
                return re.sub(r"\d+", "<NUM>", s)
            # Simple escape like \n, \r, \t - keep as-is
            if re.fullmatch(r"\\[nrtNRT]", s):
                return s
            # Hex/unicode escapes
            if re.fullmatch(r"\\x[0-9A-Fa-f]{2}", s):
                return r"\x<HEX>"
            if re.fullmatch(r"\\u[0-9A-Fa-f]{4}", s):
                return r"\u<HEX>"

        return s
    except Exception:
        return seg


# ---------------- Regex generation for glossary ---------------- #


def generate_regex_pattern(code: str, code_type: str) -> str:
    """Generate a regex pattern that matches all variations of a normalized code.
    
    Handles:
    - COLOR placeholders: [font_COLOR] → matches [font_red], [font_blue], etc.
    - NUM placeholders: [n<NUM>] → matches [n1], [n2], [n123], etc.
    - VALUE placeholders: [key=VALUE] → matches content with nested brackets
    - Escape sequences: properly escaped for regex
    - Angle brackets: <tag> patterns
    - Curly braces: {key} patterns
    
    Special handling for =VALUE:
    - Matches content including nested brackets until outer closing bracket
    - Example: [emb exp=VALUE] matches [emb exp="f.status[1][10]"]
    
    Args:
        code: Normalized code segment (e.g., [font_COLOR], [emb exp=VALUE])
        code_type: Type classification (COLOR, UNKNOWN, etc.)
        
    Returns:
        Regex pattern string that matches all variations of the code
    """
    import re as regex_module  # Avoid name collision with 're' variable
    
    # Handle square bracket codes: [...]
    if code.startswith("[") and code.endswith("]"):
        inner = code[1:-1]
        
        # Pattern: [key=VALUE] - match content with nested brackets
        if "=VALUE" in inner:
            key_part = inner.split("=")[0]
            # Escape special regex chars in key
            key_escaped = regex_module.escape(key_part)
            # Pattern: match key= then any content including nested brackets
            # (?:[^\[\]]|\[[^\]]*\])* matches either:
            #   - Any char except [ or ]
            #   - OR a complete [...] bracket pair
            # This handles [emb exp="f.status[1][10]"] correctly
            return fr"\[{key_escaped}=(?:[^\[\]]|\[[^\]]*\])*\]"
        
        # Pattern: [font_COLOR] - match any color name
        if inner == "font_COLOR" or (code_type == TYPE_COLOR and "_COLOR" in inner):
            # Match [font_<any_color>] or [font-<any_color>]
            color_pattern = "|".join(regex_module.escape(c) for c in sorted(COLOR_NAMES, key=len, reverse=True))
            return fr"\[font[_\-](?:{color_pattern})\]"
        
        # Pattern: [letter<NUM>] - match letter + digits
        match = regex_module.match(r"^([a-zA-Z])<NUM>$", inner)
        if match:
            letter = match.group(1)
            letter_escaped = regex_module.escape(letter)
            return fr"\[{letter_escaped}\d+\]"
        
        # Pattern: Generic [<NUM>] placeholder - match any digits
        if "<NUM>" in inner:
            inner_escaped = regex_module.escape(inner).replace(r"\<NUM\>", r"\d+")
            return fr"\[{inner_escaped}\]"
        
        # Pattern: Literal bracket code - escape special chars
        inner_escaped = regex_module.escape(inner)
        return fr"\[{inner_escaped}\]"
    
    # Handle angle bracket codes: <...>
    if code.startswith("<") and code.endswith(">"):
        inner = code[1:-1]
        
        # Pattern: <key=VALUE>
        if "=VALUE" in inner:
            key_part = inner.split("=")[0]
            key_escaped = regex_module.escape(key_part)
            # For angle brackets, nested < > are rare, simpler pattern
            return fr"<{key_escaped}=[^>]*>"
        
        # Pattern: <tag_COLOR>
        if "_COLOR" in inner:
            tag_part = inner.split("_")[0]
            tag_escaped = regex_module.escape(tag_part)
            color_pattern = "|".join(regex_module.escape(c) for c in sorted(COLOR_NAMES, key=len, reverse=True))
            return fr"<{tag_escaped}[_\-](?:{color_pattern})[^>]*>"
        
        # Pattern: <NUM> placeholder
        if "<NUM>" in inner:
            inner_escaped = regex_module.escape(inner).replace(r"\<NUM\>", r"\d+")
            return fr"<{inner_escaped}>"
        
        # Pattern: Literal angle bracket code
        inner_escaped = regex_module.escape(inner)
        return fr"<{inner_escaped}>"
    
    # Handle curly brace codes: {...}
    if code.startswith("{") and code.endswith("}"):
        inner = code[1:-1]
        
        # Pattern: {key=VALUE}
        if "=VALUE" in inner:
            key_part = inner.split("=")[0]
            key_escaped = regex_module.escape(key_part)
            return fr"{{{key_escaped}=[^}}]*}}"
        
        # Pattern: {<NUM>} placeholder
        if "<NUM>" in inner:
            inner_escaped = regex_module.escape(inner).replace(r"\<NUM\>", r"\d+")
            return fr"{{{inner_escaped}}}"
        
        # Pattern: Literal curly brace code
        inner_escaped = regex_module.escape(inner)
        return fr"{{{inner_escaped}}}"
    
    # Handle escape sequences: \n, \N[<NUM>], \V[<NUM>], etc.
    if code.startswith("\\"):
        # Pattern: \N[<NUM>] or \V[<NUM>] or \C[<NUM>]
        if "<NUM>" in code:
            # Escape the backslash and other special chars, then replace <NUM> with \d+
            code_escaped = regex_module.escape(code).replace("<NUM>", r"\d+")
            return code_escaped
        
        # Pattern: Literal escape sequence
        return regex_module.escape(code)
    
    # Fallback: escape the entire code literally
    return regex_module.escape(code)


# ---------------- Glossary update functions ---------------- #


def update_code_in_glossary(
    code_counts: Dict[str, int],
    update_mode: str = "Add",  # Use literal string to avoid circular import at module load time
) -> Path:
    """Update code glossary with code entries from analysis.
    
    Writes to separate codeglossary.csv file with new 4-column format:
    Code, Type, Replacement, Notes
    
    Args:
        code_counts: Dict mapping code segment to occurrence count
        update_mode: One of UPDATE_MODE_ADD, UPDATE_MODE_UPDATE, UPDATE_MODE_OVERWRITE, or UPDATE_MODE_NEW
            - ADD: Only add new entries (preserve existing)
            - UPDATE: Add new + fill empty fields in existing
            - OVERWRITE: Add new + replace all fields in existing
            - NEW: Archive existing glossary and create fresh one
        
    Returns:
        Path to updated code glossary
    """
    # Lazy-import glossary symbols to avoid circular imports at module import time
    from ..glossary import (
        UPDATE_MODE_ADD,
        UPDATE_MODE_UPDATE,
        UPDATE_MODE_OVERWRITE,
        UPDATE_MODE_NEW,
        _code_glossary_path,
        diagnose_glossary_path,
    )
    from .code_glossary_db import read_all_rows as _db_read, write_all_rows as _db_write, init_db as _db_init

    # Task 75: lazy-import romanization helper
    _romanize_if_jp = None
    try:
        from ..romanization import romanize_if_japanese
        _romanize_if_jp = romanize_if_japanese
    except ImportError:
        pass

    def _auto_romanize_notes(pattern: str) -> str:
        """Return romanized pattern for Notes if it contains kana."""
        if _romanize_if_jp is None:
            return ""
        rom = _romanize_if_jp(pattern)
        return rom if rom != pattern else ""

    code_path = _code_glossary_path()
    _db_init(code_path)  # ensure schema exists / migrate from CSV if needed

    # Handle NEW mode: overwrite existing with fresh entries (no archiving)
    if update_mode == UPDATE_MODE_NEW:
        logging.info("NEW mode: Overwriting code glossary with fresh entries")
        # Create fresh code glossary with only new entries (4 columns)
        # Group by normalized codes to avoid duplicates
        normalized_groups: Dict[str, Tuple[str, int]] = {}
        for code, count in code_counts.items():
            normalized = _normalize_code_segment(code)
            if normalized in normalized_groups:
                # Accumulate counts for same normalized code
                _, existing_count = normalized_groups[normalized]
                normalized_groups[normalized] = (normalized, existing_count + count)
            else:
                normalized_groups[normalized] = (normalized, count)

        new_rows: List[List[str]] = []
        for normalized, (norm_code, total_count) in sorted(normalized_groups.items(), key=lambda x: x[1][1], reverse=True):
            code_type = classify_code_type(norm_code)
            regex_pattern = generate_regex_pattern(norm_code, code_type)
            notes = _auto_romanize_notes(norm_code)
            new_rows.append([norm_code, code_type, regex_pattern, notes])
        _db_write(new_rows, code_path)
        logging.info("Wrote fresh code glossary DB: %s (%d codes)", code_path, len(new_rows))
        return cast(Path, code_path)

    # Read existing code glossary entries
    # Use NORMALIZED codes as keys for grouping variations
    existing_codes: Dict[str, List[str]] = {}
    for row in _db_read(code_path):
        # Rows from DB are already 4-column, no header, no migration needed
        while len(row) < 4:
            row.append("")
        normalized_key = _normalize_code_segment(row[0])
        row[0] = normalized_key
        existing_codes[normalized_key] = row
    
    # Process codes based on update mode
    # Use NORMALIZED codes as keys to group variations
    appended_rows: List[List[str]] = []
    for code, count in sorted(code_counts.items(), key=lambda x: x[1], reverse=True):
        normalized_code = _normalize_code_segment(code)
        
        if normalized_code not in existing_codes:
            # New code: classify and add with normalized code as key
            code_type = classify_code_type(code)
            regex_pattern = generate_regex_pattern(normalized_code, code_type)
            notes = _auto_romanize_notes(normalized_code)
            appended_rows.append([normalized_code, code_type, regex_pattern, notes])
        elif update_mode == UPDATE_MODE_OVERWRITE:
            # Overwrite mode: reclassify and replace with fresh defaults
            code_type = classify_code_type(code)
            regex_pattern = generate_regex_pattern(normalized_code, code_type)
            notes = _auto_romanize_notes(normalized_code)
            existing_codes[normalized_code] = [normalized_code, code_type, regex_pattern, notes]
        elif update_mode == UPDATE_MODE_UPDATE:
            # Update mode: reclassify Type if empty, preserve Replacement/Notes
            existing_row = existing_codes[normalized_code]
            if not existing_row[1]:  # Type is empty
                existing_row[1] = classify_code_type(code)
            # Generate RegEx if empty
            if not existing_row[2]:  # RegEx is empty
                existing_row[2] = generate_regex_pattern(normalized_code, existing_row[1])
            # Strip legacy Count from notes if present
            if existing_row[3].startswith("Count:"):
                existing_row[3] = ""
            existing_codes[normalized_code] = existing_row
        # else: ADD mode, skip existing entries
    
    # Write code glossary: existing + new (no header; DB handles schema)
    all_data_rows: List[List[str]] = list(existing_codes.values()) + appended_rows

    try:
        _db_write(all_data_rows, code_path)
    except Exception as e:
        error_msg = f"Failed to write code glossary DB: {e}\nPath: {code_path}"
        logging.error(error_msg)
        raise RuntimeError(error_msg) from e

    logging.info("Wrote code glossary DB: %s (%d new entries)", code_path, len(appended_rows))
    return cast(Path, code_path)
