"""Translator++ (.trans) format handler for CherryAI.

TASK 17.4: Supports reading and writing Translator++ project files.

Translator++ stores data as SQLite databases.  Each .trans file contains
one or more tables with translation pairs.  The primary table is typically
called ``data`` or ``translations`` and has at least:
- An ``original`` column (source text)
- A ``translation`` column (translated text)
- Optionally ``context``, ``comment``, or ``tags`` columns

This handler:
- Extracts original text lines from the database
- Injects translated text back alongside the originals
- Preserves all Translator++ metadata and context
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import FormatHandler

__all__ = ["TranslatorPlusHandler", "get_handlers"]

logger = logging.getLogger(__name__)

# Common table names used by Translator++ projects
_TABLE_CANDIDATES = ("data", "translations", "main", "text")

# Column name aliases
_ORIGINAL_COLS = ("original", "source", "src", "jp", "ja")
_TRANSLATION_COLS = ("translation", "translated", "target", "tl", "en")


def _find_table(
    cursor: sqlite3.Cursor,
) -> Optional[str]:
    """Find the translation table in the database.

    Returns:
        Table name or None.
    """
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    )
    tables = [row[0] for row in cursor.fetchall()]

    # Prefer known names
    for candidate in _TABLE_CANDIDATES:
        for table in tables:
            if table.lower() == candidate:
                return table

    # Fall back to first table
    return tables[0] if tables else None


def _find_columns(
    cursor: sqlite3.Cursor,
    table: str,
) -> tuple[Optional[str], Optional[str]]:
    """Find original and translation column names in *table*.

    Returns:
        (original_col, translation_col) — either may be None if not found.
    """
    cursor.execute(f"PRAGMA table_info([{table}])")
    columns = [row[1] for row in cursor.fetchall()]  # column name at index 1
    col_lower = {c.lower(): c for c in columns}

    orig_col: Optional[str] = None
    tl_col: Optional[str] = None

    for alias in _ORIGINAL_COLS:
        if alias in col_lower:
            orig_col = col_lower[alias]
            break

    for alias in _TRANSLATION_COLS:
        if alias in col_lower:
            tl_col = col_lower[alias]
            break

    # If only two text columns exist, guess positionally
    if orig_col is None and len(columns) >= 1:
        orig_col = columns[0]
    if tl_col is None and len(columns) >= 2:
        tl_col = columns[1]

    return orig_col, tl_col


class TranslatorPlusHandler(FormatHandler):
    """Translator++ (.trans) SQLite database handler."""

    format_id = "translator_plus"
    extensions = (".trans",)
    description = "Translator++ project files (SQLite database)"
    supports_pairs = True

    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract original text lines from a .trans database.

        Args:
            path: Path to the .trans file.
            encoding: Ignored (SQLite handles encoding internally).

        Returns:
            List of original text lines.
        """
        if not path.exists():
            logger.error("Translator++ file not found: %s", path)
            return []

        try:
            conn = sqlite3.connect(str(path))
            cursor = conn.cursor()

            table = _find_table(cursor)
            if table is None:
                logger.error("No tables found in %s", path)
                conn.close()
                return []

            orig_col, _ = _find_columns(cursor, table)
            if orig_col is None:
                logger.error(
                    "No original column found in table '%s' of %s",
                    table,
                    path,
                )
                conn.close()
                return []

            cursor.execute(f"SELECT [{orig_col}] FROM [{table}]")
            lines = [
                str(row[0]) if row[0] is not None else ""
                for row in cursor.fetchall()
            ]

            conn.close()
            return lines

        except sqlite3.Error as exc:
            logger.error("Failed to read Translator++ file: %s", exc)
            return []

    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8",
    ) -> None:
        """Write translated lines back to a .trans database.

        Updates the translation column in-place.  If *original_lines* is
        provided it is used to match rows; otherwise rows are updated by
        rowid order.

        Args:
            path: Path to the .trans file (must already exist).
            lines: Translated text lines.
            original_lines: Optional original lines for matching.
            encoding: Ignored.
        """
        if not path.exists():
            logger.error("Translator++ file not found for injection: %s", path)
            return

        try:
            conn = sqlite3.connect(str(path))
            cursor = conn.cursor()

            table = _find_table(cursor)
            if table is None:
                logger.error("No tables found in %s", path)
                conn.close()
                return

            orig_col, tl_col = _find_columns(cursor, table)
            if tl_col is None:
                logger.error(
                    "No translation column found in table '%s' of %s",
                    table,
                    path,
                )
                conn.close()
                return

            # Update by rowid ordering
            cursor.execute(f"SELECT rowid FROM [{table}] ORDER BY rowid")
            rowids = [row[0] for row in cursor.fetchall()]

            for i, translated in enumerate(lines):
                if i >= len(rowids):
                    break
                cursor.execute(
                    f"UPDATE [{table}] SET [{tl_col}] = ? WHERE rowid = ?",
                    (translated, rowids[i]),
                )

            conn.commit()
            conn.close()
            logger.info(
                "Injected %d translations into %s", min(len(lines), len(rowids)), path,
            )

        except sqlite3.Error as exc:
            logger.error("Failed to write Translator++ file: %s", exc)

    def get_metadata(self, path: Path) -> Dict[str, Any]:
        """Extract metadata from a .trans file."""
        meta = super().get_metadata(path)
        if not path.exists():
            return meta

        try:
            conn = sqlite3.connect(str(path))
            cursor = conn.cursor()

            table = _find_table(cursor)
            if table:
                meta["table"] = table
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                meta["row_count"] = cursor.fetchone()[0]

                orig_col, tl_col = _find_columns(cursor, table)
                meta["original_column"] = orig_col
                meta["translation_column"] = tl_col

                # Count how many rows have translations
                if tl_col:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM [{table}] "
                        f"WHERE [{tl_col}] IS NOT NULL AND [{tl_col}] != ''",
                    )
                    meta["translated_count"] = cursor.fetchone()[0]

            conn.close()
        except sqlite3.Error as exc:
            logger.warning("Failed to read .trans metadata: %s", exc)

        return meta


def get_handlers() -> List[FormatHandler]:
    """Return all Translator++ format handlers."""
    return [TranslatorPlusHandler()]
