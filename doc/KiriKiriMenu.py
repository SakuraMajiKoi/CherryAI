#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KiriKiriMenu: Extract and inject menu captions from KiriKiri/KAG Menus.tjs.

What it extracts (safe to translate):
- The caption strings passed to new KAGMenuItem(this, "Caption", ...) as the 2nd arg.
- The caption strings passed to new MenuItem(this, "...") as the 2nd arg (excluding "-").

Rules:
- If a caption contains an accelerator suffix like "\tShift+F4", only the left part (before \t) is extracted.
- During injection, the original accelerator suffix is preserved unless the translation also includes a "\t...".
- Mnemonics (&X) remain part of the translatable left text; translators can reassign them.

Notes:
- Handles ternary expressions inside the 2nd argument (e.g., cond ? "A" : "B") by extracting both "A" and "B".
- Limits processing to Menus.tjs by default.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Iterable

FILE_TYPES = (".tjs",)
MODULE_NAME = "KiriKiri Menu Captions"

# Write TJS with UTF-8 BOM for KiriKiri compatibility
OUTPUT_ENCODING = "utf-8"
OUTPUT_BOM = True


def _decode_bytes_with_bom(b: bytes) -> Tuple[str, str, bytes]:
    """
    Decode bytes preferring BOM if present. Returns (text, encoding_name, bom_bytes).
    Recognizes utf-8, utf-16-le, utf-16-be BOMs. Falls back to utf-8.
    """
    if not b:
        return "", "utf-8", b""
    # BOMs
    if b.startswith(b"\xff\xfe"):
        try:
            return b.decode("utf-16-le"), "utf-16-le", b"\xff\xfe"
        except Exception:
            pass
    if b.startswith(b"\xfe\xff"):
        try:
            return b.decode("utf-16-be"), "utf-16-be", b"\xfe\xff"
        except Exception:
            pass
    if b.startswith(b"\xef\xbb\xbf"):
        try:
            return b.decode("utf-8"), "utf-8", b"\xef\xbb\xbf"
        except Exception:
            pass
    # No BOM: try utf-8 then utf-16-le as fallback
    try:
        return b.decode("utf-8"), "utf-8", b""
    except Exception:
        try:
            # Some TJS files may actually be utf-16-le without BOM
            return b.decode("utf-16-le"), "utf-16-le", b""
        except Exception:
            # Last resort: replace errors
            return b.decode("utf-8", errors="replace"), "utf-8", b""


def should_process_file(path: Path) -> bool:
    """Restrict to Menus.tjs by default."""
    name = path.name.lower()
    return name == "menus.tjs"


def might_contain_translatables(content: str, trans_maps: Dict[str, Dict[str, str]], file_path: Path) -> bool:
    """Quick precheck: true if the file looks like it has menu items and at least one short key is present."""
    if "KAGMenuItem" not in content and "MenuItem" not in content:
        return False
    mm = trans_maps.get("main") or {}
    if not mm:
        return True  # extracting or generic presence
    sample = 0
    for k in mm.keys():
        kk = k.strip()
        if len(kk) <= 40 and kk and kk in content:
            return True
        sample += 1
        if sample >= 100:
            break
    return False


# ---------- Low-level parsing helpers (lenient, string/paren aware) ----------

def _find_matching_paren(s: str, open_idx: int) -> int:
    """Find matching ')' for '(' at open_idx, respecting strings and escapes."""
    depth = 0
    i = open_idx
    in_str = False
    quote = ""
    while i < len(s):
        ch = s[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            quote = ch
            i += 1
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_args_top_level(s: str) -> List[Tuple[int, int]]:
    """Return list of (start,end) spans of comma-separated arguments at top level in s."""
    spans: List[Tuple[int, int]] = []
    depth = 0
    in_str = False
    quote = ""
    start = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            quote = ch
            i += 1
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth > 0:
                depth -= 1
        elif ch == ',' and depth == 0:
            spans.append((start, i))
            start = i + 1
        i += 1
    # last arg
    if start < len(s):
        spans.append((start, len(s)))
    return spans


def _iter_string_literals(s: str, base_offset: int = 0) -> Iterable[Tuple[str, int, int]]:
    """
    Iterate over double-quoted string literals in s.
    Yields (content_inside_quotes, start_index_of_content, end_index_of_content) absolute to the outer text.
    """
    i = 0
    while i < len(s):
        if s[i] == '"':
            start_quote = i
            i += 1
            j = i
            while j < len(s):
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == '"':
                    # content between i..j
                    yield (s[i:j], base_offset + i, base_offset + j)
                    i = j + 1
                    break
                j += 1
            else:
                # unterminated string
                break
        else:
            i += 1


def _content_left_and_suffix(content: str) -> Tuple[str, str, str]:
    """
    Split string-literal content into (left, delim, suffix).
    delim is either '\\t', '\t', or '' (the exact form used in source).
    """
    if "\\t" in content:
        a, b = content.split("\\t", 1)
        return a, "\\t", b
    if "\t" in content:
        a, b = content.split("\t", 1)
        return a, "\t", b
    return content, "", ""


def _escape_for_tjs(s: str) -> str:
    """Escape backslashes and quotes for TJS double-quoted string literal content."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ---------- Extraction ----------

def extract(data: Any, file_path: Path, **kwargs) -> Dict[str, List[Dict[str, str]]]:
    """
    Extract translatable menu captions:
    - KAGMenuItem second argument – capture all string literals within (handles ternary).
    - MenuItem second argument when it's a string literal and not "-" (separator).
    Only the left part (before \t) is extracted for translation.
    """
    # Accept either decoded text (str) or raw bytes (file contents)
    bom: bytes = b""
    encoding: str = OUTPUT_ENCODING
    if isinstance(data, (bytes, bytearray)):
        text, encoding, bom = _decode_bytes_with_bom(bytes(data))
    elif isinstance(data, str):
        text = data
        encoding = "utf-8"
    else:
        return {}
    rows: List[Dict[str, str]] = []
    seen: set[str] = set()

    def _process_caption_literal(lit_content: str):
        left, _delim, _suffix = _content_left_and_suffix(lit_content)
        left = left.strip()
        if not left or left == "-":
            return
        if left not in seen:
            seen.add(left)
            rows.append({"name": left})

    # Find new KAGMenuItem(...) calls
    for m in re.finditer(r"\bnew\s+KAGMenuItem\s*\(", text):
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(text, open_idx)
        if close_idx == -1:
            continue
        arg_region = text[open_idx + 1:close_idx]
        spans = _split_args_top_level(arg_region)
        if len(spans) >= 2:
            a1, a2 = spans[1]
            second_arg = arg_region[a1:a2]
            base = (open_idx + 1) + a1
            # Capture all string literals that appear anywhere in the second arg expression
            for content, cstart, cend in _iter_string_literals(text[base:base + len(second_arg)], base_offset=base):
                _process_caption_literal(content)

    # Find new MenuItem(this, "...") two-arg calls
    for m in re.finditer(r"\bnew\s+MenuItem\s*\(", text):
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(text, open_idx)
        if close_idx == -1:
            continue
        arg_region = text[open_idx + 1:close_idx]
        spans = _split_args_top_level(arg_region)
        # Only consider patterns like: MenuItem(this, "...")
        if len(spans) == 2:
            a1, a2 = spans[1]
            second_arg = arg_region[a1:a2]
            base = (open_idx + 1) + a1
            for content, cstart, cend in _iter_string_literals(text[base:base + len(second_arg)], base_offset=base):
                if content.strip() == "-":
                    continue
                _process_caption_literal(content)

    if not rows:
        return {}
    # Return the extracted rows; keep no-encoding metadata here (main map consumers don't need it)
    return {"main": rows}


# ---------- Injection ----------

def inject(data: Any, trans_maps: Dict[str, Dict[str, str]], file_path: Path, **kwargs) -> Any:
    """
    Inject translations back:
    - For each KAGMenuItem second argument, replace string literals using the map built from extraction.
    - For each MenuItem two-arg call, replace second-arg literal unless it is "-".
    - If original had a \t suffix and the translation does NOT include "\t", preserve the original suffix and delim kind.
    """
    logger = kwargs.get("logger")
    # detect input type (bytes/str) and decode preserving BOM/encoding to be able to re-encode
    bom: bytes = b""
    original_encoding: str = OUTPUT_ENCODING
    if isinstance(data, (bytes, bytearray)):
        text, original_encoding, bom = _decode_bytes_with_bom(bytes(data))
    elif isinstance(data, str):
        text = data
        original_encoding = "utf-8"
    else:
        return data

    main_map = trans_maps.get("main", {})
    if not main_map:
        return data

    text = data
    modifications: List[Tuple[int, int, str]] = []  # (start_content_idx, end_content_idx, replacement_content)

    def _maybe_translate_literal(lit_content: str) -> str | None:
        # lit_content: raw content inside quotes as in source, includes backslash escapes
        left, delim, suffix = _content_left_and_suffix(lit_content)
        key = left.strip()
        if not key:
            return None
        trans = main_map.get(key)
        if trans is None:
            return None
        trans = trans.strip()
        # If translator already provided a \t accelerator, use it fully; else keep the original suffix
        if ("\\t" in trans) or ("\t" in trans):
            new_inner = trans
        else:
            if delim:
                new_inner = f"{trans}{delim}{suffix}"
            else:
                new_inner = trans
        # Escape for TJS string literal
        return _escape_for_tjs(new_inner)

    # Helper to scan a call and enqueue literal replacements within the given argument index (0-based)
    def _process_call_at(open_idx: int, arg_index: int, max_args_needed: int | None = None):
        close_idx = _find_matching_paren(text, open_idx)
        if close_idx == -1:
            return
        arg_region = text[open_idx + 1:close_idx]
        spans = _split_args_top_level(arg_region)
        if len(spans) <= arg_index:
            return
        if max_args_needed is not None and len(spans) != max_args_needed:
            return
        a1, a2 = spans[arg_index]
        region_start = (open_idx + 1) + a1
        region_text = text[region_start: (open_idx + 1) + a2]
        for content, cstart, cend in _iter_string_literals(region_text, base_offset=region_start):
            # Skip separators
            if content.strip() == "-":
                continue
            repl_inner = _maybe_translate_literal(content)
            if repl_inner is not None:
                # Replace only the inner content between quotes
                modifications.append((cstart, cend, repl_inner))

    # KAGMenuItem second arg (index 1), any arg count >= 2
    for m in re.finditer(r"\bnew\s+KAGMenuItem\s*\(", text):
        open_idx = m.end() - 1
        _process_call_at(open_idx, arg_index=1, max_args_needed=None)

    # MenuItem two-arg, second arg index=1 and exactly two args
    for m in re.finditer(r"\bnew\s+MenuItem\s*\(", text):
        open_idx = m.end() - 1
        _process_call_at(open_idx, arg_index=1, max_args_needed=2)

    if not modifications:
        # No changes: return original input in same type
        return data

    # Apply from end to start to avoid offset issues
    modifications.sort(key=lambda t: t[0], reverse=True)
    out = list(text)
    for start, end, inner in modifications:
        out[start:end] = list(inner)

    new_text = "".join(out)
    # Re-encode to original encoding, preserving BOM if present
    if isinstance(data, (bytes, bytearray)):
        enc = original_encoding or "utf-8"
        if enc.lower().replace('-', '') in ("utf16le", "utf16be"):
            # encode to utf-16-le/be without adding an extra BOM; we'll prefix bom if original had one
            encoded = new_text.encode(enc)
        else:
            encoded = new_text.encode(enc)
        if bom:
            return bom + encoded.lstrip(bom)
        return encoded
    else:
        return new_text