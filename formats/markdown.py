"""Markdown format handler for CherryAI.

TASK 17.4: Supports reading and writing Markdown (.md) files for translation.

Features:
- Preserves fenced code blocks (```) as protected markers
- Preserves inline code (`code`) as protected markers
- Preserves YAML frontmatter (---) untouched
- Translates only prose text content
- Maintains heading structure and formatting
- Preserves blank lines, lists, and block quotes
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import FormatHandler

__all__ = ["MarkdownHandler", "get_handlers"]

logger = logging.getLogger(__name__)

# Regex patterns
_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})")
_FRONTMATTER_DELIM = re.compile(r"^---\s*$")
_INLINE_CODE = re.compile(r"`[^`]+`")

# Placeholder template for protected content
_CODE_PLACEHOLDER = "\x00CODE{idx}\x00"
_CODE_RESTORE = re.compile(r"\x00CODE(\d+)\x00")


class MarkdownHandler(FormatHandler):
    """Markdown file handler.

    Extracts translatable prose lines while preserving code blocks,
    inline code, and YAML frontmatter.
    """

    format_id = "markdown"
    extensions = (".md",)
    description = "Markdown files (preserves code blocks and frontmatter)"
    supports_pairs = False

    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract translatable lines from a Markdown file.

        Code blocks and frontmatter are replaced with placeholder markers
        so they are not sent for translation.

        Args:
            path: Path to the Markdown file.
            encoding: Text encoding.

        Returns:
            List of text lines with code blocks replaced by markers.
        """
        if not path.exists():
            logger.error("Markdown file not found: %s", path)
            return []

        raw = path.read_text(encoding=encoding)
        lines = raw.splitlines()
        result: List[str] = []

        in_frontmatter = False
        in_code_block = False
        fence_marker = ""
        frontmatter_started = False

        for i, line in enumerate(lines):
            # --- Handle YAML frontmatter (only at the very start) ---
            if i == 0 and _FRONTMATTER_DELIM.match(line):
                in_frontmatter = True
                frontmatter_started = True
                result.append(f"[FRONTMATTER_START]")
                continue

            if in_frontmatter:
                if _FRONTMATTER_DELIM.match(line) and frontmatter_started:
                    in_frontmatter = False
                    result.append("[FRONTMATTER_END]")
                    continue
                # Store frontmatter lines inside placeholder
                result.append(f"[FM]{line}")
                continue

            # --- Handle fenced code blocks ---
            fence_match = _FENCE_OPEN.match(line)
            if fence_match and not in_code_block:
                in_code_block = True
                fence_marker = fence_match.group(1)[0]  # ` or ~
                result.append(f"[CODEBLOCK_START]{line}")
                continue

            if in_code_block:
                # Check for closing fence
                close_match = _FENCE_OPEN.match(line)
                if close_match and close_match.group(1)[0] == fence_marker:
                    in_code_block = False
                    fence_marker = ""
                    result.append(f"[CODEBLOCK_END]{line}")
                else:
                    result.append(f"[CODE]{line}")
                continue

            # --- Normal line: protect inline code ---
            result.append(_protect_inline_code(line))

        return result

    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8",
    ) -> None:
        """Write translated lines back to a Markdown file.

        Restores code blocks, frontmatter, and inline code from markers.

        Args:
            path: Path to write the file.
            lines: Translated/processed lines with markers.
            original_lines: Ignored (Markdown doesn't support pairs).
            encoding: Text encoding.
        """
        output: List[str] = []

        for line in lines:
            if line == "[FRONTMATTER_START]":
                output.append("---")
            elif line == "[FRONTMATTER_END]":
                output.append("---")
            elif line.startswith("[FM]"):
                output.append(line[4:])
            elif line.startswith("[CODEBLOCK_START]"):
                output.append(line[len("[CODEBLOCK_START]"):])
            elif line.startswith("[CODEBLOCK_END]"):
                output.append(line[len("[CODEBLOCK_END]"):])
            elif line.startswith("[CODE]"):
                output.append(line[6:])
            else:
                # Restore inline code placeholders
                output.append(_restore_inline_code(line))

        content = "\n".join(output)
        path.write_text(content, encoding=encoding, newline="")

    def get_metadata(self, path: Path) -> Dict[str, Any]:
        """Extract Markdown-specific metadata."""
        meta = super().get_metadata(path)
        if not path.exists():
            return meta

        try:
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            meta["total_lines"] = len(lines)
            meta["has_frontmatter"] = bool(
                lines and _FRONTMATTER_DELIM.match(lines[0]),
            )
            # Count headings
            heading_count = sum(
                1 for ln in lines if ln.lstrip().startswith("#")
            )
            meta["heading_count"] = heading_count
        except Exception as exc:
            logger.warning("Failed to read Markdown metadata: %s", exc)

        return meta


# ---- inline-code protection helpers ----

# Global store for inline-code snippets during a single extract pass.
_inline_store: List[str] = []


def _protect_inline_code(line: str) -> str:
    """Replace inline code spans with numbered placeholders."""
    if "`" not in line:
        return line

    def _replacer(m: re.Match) -> str:  # type: ignore[type-arg]
        idx = len(_inline_store)
        _inline_store.append(m.group(0))
        return _CODE_PLACEHOLDER.format(idx=idx)

    return _INLINE_CODE.sub(_replacer, line)


def _restore_inline_code(line: str) -> str:
    """Restore inline code spans from numbered placeholders."""
    if "\x00" not in line:
        return line

    def _replacer(m: re.Match) -> str:  # type: ignore[type-arg]
        idx = int(m.group(1))
        if idx < len(_inline_store):
            return _inline_store[idx]
        return m.group(0)  # leave as-is if index out of range

    return _CODE_RESTORE.sub(_replacer, line)


def reset_inline_store() -> None:
    """Clear the inline-code store (call between files)."""
    _inline_store.clear()


def get_handlers() -> List[FormatHandler]:
    """Return all Markdown format handlers."""
    return [MarkdownHandler()]
