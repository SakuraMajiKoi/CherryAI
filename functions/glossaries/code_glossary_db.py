"""TSV persistence layer for the CherryAI Code Database.

Phase 62: Replaces the legacy SQLite ``codeglossary.db`` with a plain-text
TSV file at ``user/codedatabase.tsv``.

Schema — 10 columns (tab-separated, UTF-8, with header row):

    Pattern  Type  RegEx  Notes  Visible  IsInvisible  IsCouple  IsNumber  IsWord  Active

Migration
---------
On first access the module will automatically:
1. Convert ``codeglossary.db`` (SQLite) → ``codedatabase.tsv`` if the DB exists
   and the TSV does not yet.
2. Migrate ``codeglossary.csv`` entries if present.
3. Merge ``global_codes.json`` entries (from the legacy GUI widget) if present.

Public API  (same surface as the old SQLite version)
----------
- :func:`get_db_path`            – canonical path to ``codedatabase.tsv``
- :func:`init_db`                – ensure file + header exist, run migrations
- :func:`read_all_rows`          – return rows as ``[[pattern, type, regex, notes], …]``
                                    (4-column compat view – columns 0-3 only)
- :func:`read_all_rows_extended` – return full 9-column rows (Phase 62)
- :func:`write_all_rows`         – overwrite entire table (accepts 4- or 9-column rows)
- :func:`upsert_rows`            – insert or update rows (key = Pattern column)
- :func:`delete_row`             – remove one entry by pattern key
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

HEADER: List[str] = [
    "Pattern", "Type", "RegEx", "Notes",
    "Visible", "IsInvisible", "IsCouple", "IsNumber", "IsWord", "Active",
]

_LEGACY_CSV_NAME = "codeglossary.csv"
_LEGACY_DB_NAME  = "codeglossary.db"
_TSV_NAME        = "codedatabase.tsv"

_NUM_COLS = len(HEADER)  # 10


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    """Return the canonical path to ``user/codedatabase.tsv``.

    Supports the ``CHERRYAI_TEST_CODEGLOSSARY_PATH`` environment variable for
    test isolation.
    """
    override = os.environ.get("CHERRYAI_TEST_CODEGLOSSARY_PATH", "").strip()
    if override:
        p = Path(override)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    here = Path(__file__).resolve()
    root = here.parent.parent.parent          # …/CherryAI
    user_dir = root / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / _TSV_NAME


# ---------------------------------------------------------------------------
# Low-level TSV I/O
# ---------------------------------------------------------------------------

def _read_tsv(path: Path) -> List[List[str]]:
    """Return all rows (including header) from a TSV file."""
    if not path.exists():
        return []
    rows: List[List[str]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            rows.append(row)
    return rows


def _write_tsv(path: Path, rows: List[List[str]]) -> None:
    """Write rows to a TSV file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerows(rows)


def _pad_row(row: List[str], target: int = _NUM_COLS) -> List[str]:
    """Return row padded to *target* columns (or truncated if too long)."""
    padded = list(row) + [""] * target
    return padded[:target]


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------

def _migrate_from_sqlite(db_path: Path, tsv_path: Path) -> None:
    """Migrate legacy SQLite ``codeglossary.db`` → ``codedatabase.tsv``."""
    try:
        import sqlite3
        con = sqlite3.connect(str(db_path))
        cur = con.execute("SELECT code, type, regex, notes FROM codes ORDER BY code")
        rows: List[List[str]] = [list(r) for r in cur.fetchall()]
        con.close()
    except Exception as exc:
        logger.warning("Cannot migrate SQLite DB '%s': %s", db_path, exc)
        return

    tsv_rows: List[List[str]] = [HEADER]
    for row in rows:
        while len(row) < 4:
            row.append("")
        tsv_rows.append(_pad_row(row[:4]))
    _write_tsv(tsv_path, tsv_rows)
    logger.info(
        "Migrated %d code entries: %s → %s", len(rows), db_path.name, tsv_path.name
    )


def _migrate_from_legacy_csv(csv_path: Path, tsv_path: Path) -> None:
    """Migrate legacy 4-column ``codeglossary.csv`` → ``codedatabase.tsv``."""
    rows: List[List[str]] = []
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            for i, row in enumerate(reader):
                if not row or not row[0].strip():
                    continue
                if i == 0 and row[0].strip().lower() in ("code", "pattern"):
                    continue
                rows.append(row)
    except Exception as exc:
        logger.warning("Cannot read legacy CSV '%s': %s", csv_path, exc)
        return

    tsv_rows: List[List[str]] = [HEADER]
    for row in rows:
        while len(row) < 4:
            row.append("")
        tsv_rows.append(_pad_row(row[:4]))
    _write_tsv(tsv_path, tsv_rows)
    logger.info(
        "Migrated %d code entries: %s → %s", len(rows), csv_path.name, tsv_path.name
    )


def _merge_json_codes(json_path: Path, tsv_path: Path) -> None:
    """Merge ``global_codes.json`` into ``codedatabase.tsv``.

    JSON format: list of {\"col1\": pattern, \"col2\": type, \"col3\": notes}
    Entries already present (by pattern) are skipped.
    """
    import json as _json
    try:
        with json_path.open("r", encoding="utf-8") as fh:
            data = _json.load(fh)
    except Exception:
        return
    if not isinstance(data, list):
        return

    existing_keys = {r[0] for r in read_all_rows_extended(tsv_path) if r[0]}
    new_entries: List[List[str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("col1", "")).strip()
        if not pattern or pattern.lower() in ("pattern", "code"):
            continue
        if pattern in existing_keys:
            continue
        new_entries.append(_pad_row([
            pattern,
            str(item.get("col2", "")),
            "",
            str(item.get("col3", "")),
        ]))

    if new_entries:
        tsv_rows = _read_tsv(tsv_path) or [HEADER]
        tsv_rows.extend(new_entries)
        _write_tsv(tsv_path, tsv_rows)
        logger.info("Merged %d entries from global_codes.json", len(new_entries))


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db(db_path: Optional[Path] = None) -> Path:
    """Ensure the TSV file and header exist.  Run one-time migrations if needed.

    Migration order (only executes when the target TSV does not yet exist):
    1. ``codeglossary.db``   (SQLite) → ``codedatabase.tsv``
    2. ``codeglossary.csv``  (CSV)    → ``codedatabase.tsv``
    3. ``global_codes.json`` (widget) merged in

    Returns the resolved path to the TSV file.
    """
    path = db_path or get_db_path()

    if not path.exists():
        parent = path.parent

        # 1. Migrate from SQLite
        legacy_db = parent / _LEGACY_DB_NAME
        if legacy_db.exists():
            _migrate_from_sqlite(legacy_db, path)

        # 2. Migrate from legacy CSV
        if not path.exists():
            legacy_csv = parent / _LEGACY_CSV_NAME
            if legacy_csv.exists():
                _migrate_from_legacy_csv(legacy_csv, path)

        # 3. Create empty TSV with header if still missing
        if not path.exists():
            _write_tsv(path, [HEADER])

        # 4. Merge global_codes.json if present
        json_legacy = parent / "global_codes.json"
        if json_legacy.exists():
            try:
                _merge_json_codes(json_legacy, path)
                json_legacy.rename(json_legacy.with_suffix(".json.migrated"))
            except Exception as exc:
                logger.warning("global_codes.json merge failed: %s", exc)

    else:
        # File exists — ensure header row is present
        existing = _read_tsv(path)
        if not existing or existing[0] != HEADER:
            data_rows = [r for r in existing if r and r[0].strip() and r[0].strip().lower() not in ("pattern", "code")]
            _write_tsv(path, [HEADER] + data_rows)

    return path


# ---------------------------------------------------------------------------
# Read / Write (public API)
# ---------------------------------------------------------------------------

def read_all_rows(db_path: Optional[Path] = None) -> List[List[str]]:
    """Return every data row as ``[pattern, type, regex, notes]`` (4-column compat).

    The header row is excluded.  Backward-compatible with the old SQLite API.
    """
    return [row[:4] for row in read_all_rows_extended(db_path)]


def read_all_rows_extended(db_path: Optional[Path] = None) -> List[List[str]]:
    """Return every data row with all 10 columns (Phase 76).

    The header row is excluded.  Each row is guaranteed 10 elements.
    The 10th column (Active) defaults to empty string (= active) for
    backward compatibility with 9-column TSV files.
    """
    path = init_db(db_path)
    rows: List[List[str]] = []
    for row in _read_tsv(path):
        if not row or not row[0].strip():
            continue
        # Skip header row
        if row[0].strip().lower() in ("pattern", "code"):
            continue
        rows.append(_pad_row(row))
    return rows


def write_all_rows(rows: List[List[str]], db_path: Optional[Path] = None) -> None:
    """Overwrite the entire code database with *rows*.

    *rows* must NOT include a header row.  Each element may be 4-column
    (legacy compat) or 9-column.  Empty / header rows are silently skipped.
    """
    path = init_db(db_path)
    tsv_rows: List[List[str]] = [HEADER]
    for row in rows:
        if not row or not row[0].strip():
            continue
        if row[0].strip().lower() in ("pattern", "code"):
            continue
        tsv_rows.append(_pad_row(row))
    _write_tsv(path, tsv_rows)
    logger.debug("write_all_rows: wrote %d entries to %s", len(tsv_rows) - 1, path)


def upsert_rows(rows: List[List[str]], db_path: Optional[Path] = None) -> None:
    """Insert or update rows; key = Pattern (column 0)."""
    path = init_db(db_path)
    existing: dict[str, List[str]] = {
        r[0]: r for r in read_all_rows_extended(path) if r[0]
    }
    for row in rows:
        if not row or not row[0].strip():
            continue
        key = row[0].strip()
        existing[key] = _pad_row(row)
    tsv_rows: List[List[str]] = [HEADER] + list(existing.values())
    _write_tsv(path, tsv_rows)


def delete_row(code: str, db_path: Optional[Path] = None) -> bool:
    """Remove a single entry by its pattern key.  Returns True if it existed."""
    path = init_db(db_path)
    existing = read_all_rows_extended(path)
    new_rows = [r for r in existing if r[0] != code]
    if len(new_rows) == len(existing):
        return False
    _write_tsv(path, [HEADER] + new_rows)
    return True
