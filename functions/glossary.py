from __future__ import annotations

"""Unified glossary helpers for CherryAI.

This module manages a centralized glossary at CherryAI/user/globalglossary.tsv with:
- Column 1: Original  (mandatory key)
- Column 2: Translation  (optional, language-dependent)
- Column 3: Notes  (optional context; extended metadata encoded as key=value pairs)

Extended metadata (source, type, gender, pronouns, honorifics) is stored inside
the Notes column as a semicolon-separated suffix in parentheses, e.g.:
    "Main character (source=Analysis; type=Name; gender=Female)"

Legacy 8-column CSV files (GlobalGlossary.csv, glossary.csv) are automatically
migrated to the 3-column TSV format on first access.

Functions preserve existing entries and append new ones without deletion.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import csv
import logging
import os

# IO helpers
from .mainhelper import (
    read_text,
    read_table,
    read_json_pairs,
    read_xlsx_pairs,
)

# Import only constants from glossaries package to avoid circular imports
from .glossaries.name_glossary_constants import (
    PRONOUN_ROMANIZATION,
    HONORIFIC_ROMANIZATION,
    PRONOUN_GENDER,
    HONORIFIC_GENDER,
    DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
    MIN_SPEAKER_OCCURRENCES,
    MAX_SPEAKER_LENGTH,
    SPEAKERS_HEADER,
)
from .glossaries.code_glossary_constants import (
    CODE_GLOSSARY_HEADER,
)


# ---------------- Unified glossary paths and constants ---------------- #

# Header for unified glossary TSV (3-column design — Phase 62)
UNIFIED_HEADER = [
    "Original",
    "Translation",
    "Notes",
]

# Legacy 8-column CSV header retained for backward-compat migration only
_LEGACY_CSV_HEADER = [
    "Original",
    "Translation",
    "Notes",
    "Source",
    "Type",
    "Gender",
    "Refers_to_themself_as",
    "Referred_to_as",
]

# Type values
TYPE_NAME = "Name"
TYPE_LOCATION = "Location"
TYPE_TERM = "Term"
TYPE_CODE = "Code"

# Gender values
GENDER_MALE = "Male"
GENDER_FEMALE = "Female"
GENDER_NEUTRAL = "Neutral"
GENDER_NONBINARY = "Non-Binary"
GENDER_TRANSWOMAN = "Transwoman"
GENDER_TRANSMAN = "Transman"
GENDER_UNKNOWN = "Unknown"

# Glossary update modes
UPDATE_MODE_ADD = "Add"  # Only add new entries, preserve existing
UPDATE_MODE_UPDATE = "Update"  # Add new + fill empty fields in existing
UPDATE_MODE_OVERWRITE = "Overwrite"  # Add new + overwrite all fields
UPDATE_MODE_NEW = "New"  # Archive existing glossary and create fresh one


def diagnose_glossary_path(path: Path) -> Dict[str, Any]:
    """Perform comprehensive diagnostics on a glossary path.
    
    Returns dict with diagnostic information:
    - exists: bool
    - is_file: bool
    - is_dir: bool
    - parent_exists: bool
    - parent_writable: bool
    - readable: bool
    - writable: bool
    - size_bytes: int (if exists)
    - error: str (if any check fails)
    """
    result: Dict[str, Any] = {
        "path": str(path),
        "absolute_path": str(path.resolve()),
        "exists": False,
        "is_file": False,
        "is_dir": False,
        "parent_exists": False,
        "parent_writable": False,
        "readable": False,
        "writable": False,
        "size_bytes": 0,
        "error": None,
    }
    
    try:
        # Check if path exists
        result["exists"] = path.exists()
        if result["exists"]:
            result["is_file"] = path.is_file()
            result["is_dir"] = path.is_dir()
            result["size_bytes"] = path.stat().st_size if result["is_file"] else 0
            
            # Check readability
            try:
                with path.open("r", encoding="utf-8") as f:
                    f.read(1)
                result["readable"] = True
            except Exception as e:
                result["readable"] = False
                result["error"] = f"Cannot read file: {e}"
            
            # Check writability
            try:
                with path.open("a", encoding="utf-8") as f:
                    pass
                result["writable"] = True
            except Exception as e:
                result["writable"] = False
                if not result["error"]:
                    result["error"] = f"Cannot write to file: {e}"
        
        # Check parent directory
        parent = path.parent
        result["parent_exists"] = parent.exists()
        
        if result["parent_exists"]:
            # Check parent writability by attempting to create a temp file
            try:
                test_file = parent / f".test_write_{os.getpid()}.tmp"
                test_file.touch()
                test_file.unlink()
                result["parent_writable"] = True
            except Exception as e:
                result["parent_writable"] = False
                if not result["error"]:
                    result["error"] = f"Cannot write to parent directory {parent}: {e}"
        else:
            # Try to create parent directory
            try:
                parent.mkdir(parents=True, exist_ok=True)
                result["parent_exists"] = True
                result["parent_writable"] = True
            except Exception as e:
                result["parent_writable"] = False
                result["error"] = f"Cannot create parent directory {parent}: {e}"
    
    except Exception as e:
        result["error"] = f"Diagnostic failed: {e}"
    
    return result


def _unified_glossary_path() -> Path:
    """Return path to unified glossary TSV.

    Default: CherryAI/user/globalglossary.tsv  (Phase 62 canonical target)
    Test override: set env var CHERRYAI_TEST_GLOSSARY_PATH to a file path.

    Migration chain (runs once on first access):
        glossary.csv  →  GlobalGlossary.csv  →  globalglossary.tsv
    If global_glossary.json exists and globalglossary.tsv is absent, the JSON
    data is also merged during this call.
    """
    # Allow tests to override glossary location
    override = os.environ.get("CHERRYAI_TEST_GLOSSARY_PATH", "").strip()
    if override:
        p = Path(override)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return p

    here = Path(__file__).resolve()
    CherryAI_root = here.parent.parent
    user_dir = CherryAI_root / "user"
    user_dir.mkdir(parents=True, exist_ok=True)

    target = user_dir / "globalglossary.tsv"

    # --- Migration chain (runs only when target doesn't exist yet) ---
    if not target.exists():
        # Step 1: glossary.csv → GlobalGlossary.csv
        old_csv1 = user_dir / "glossary.csv"
        old_csv2 = user_dir / "GlobalGlossary.csv"
        if old_csv1.exists() and not old_csv2.exists():
            try:
                old_csv1.rename(old_csv2)
            except Exception:
                pass

        # Step 2: GlobalGlossary.csv → globalglossary.tsv (convert format)
        if old_csv2.exists():
            try:
                _migrate_csv_to_tsv(old_csv2, target)
                logging.info("Migrated GlobalGlossary.csv → globalglossary.tsv")
            except Exception as exc:
                logging.warning("CSV → TSV migration failed: %s", exc)
                # Fallback: return old csv path so nothing is lost
                return old_csv2

        # Step 3: merge global_glossary.json into globalglossary.tsv
        json_legacy = user_dir / "global_glossary.json"
        if json_legacy.exists():
            try:
                _merge_json_glossary_into_tsv(json_legacy, target)
                logging.info("Merged global_glossary.json → globalglossary.tsv")
                json_legacy.rename(json_legacy.with_suffix(".json.migrated"))
            except Exception as exc:
                logging.warning("JSON glossary merge failed: %s", exc)

    return target


def _code_glossary_path() -> Path:
    """Return path to global code database: CherryAI/user/codedatabase.tsv"""
    here = Path(__file__).resolve()
    CherryAI_root = here.parent.parent
    user_dir = CherryAI_root / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "codedatabase.tsv"


def _archive_glossary_with_timestamp(glossary_path: Path) -> Optional[Path]:
    """Archive existing glossary with timestamp format: YYYY-DD-MM-N.csv
    
    Creates archive in same directory as glossary with incrementing number suffix.
    Format: glossary.YYYY-DD-MM-N.csv (e.g., glossary.2025-11-11-1.csv)
    
    Args:
        glossary_path: Path to glossary file to archive
        
    Returns:
        Path to archived file, or None if no file to archive
    """
    if not glossary_path.exists():
        return None
    
    try:
        from datetime import datetime
        
        # Get current date in YYYY-DD-MM format (Year-Day-Month as requested)
        now = datetime.now()
        date_prefix = now.strftime("%Y-%d-%m")  # Year-Day-Month
        
        # Find next available number for this date
        parent_dir = glossary_path.parent
        base_name = glossary_path.stem  # "glossary" or "globalglossary"
        ext = glossary_path.suffix  # ".tsv" or ".csv"
        
        number = 1
        while True:
            archive_name = f"{base_name}.{date_prefix}-{number}{ext}"
            archive_path = parent_dir / archive_name
            if not archive_path.exists():
                break
            number += 1
        
        # Copy existing glossary to archive location
        import shutil
        shutil.copy2(glossary_path, archive_path)
        logging.info("Archived existing glossary to: %s", archive_path)
        return archive_path
        
    except Exception as e:
        logging.error("Failed to archive glossary: %s", e)
        return None


def _read_csv_rows(path: Path) -> List[List[str]]:
    """Read CSV rows from path (returns empty list if file doesn't exist)."""
    if not path.exists():
        return []
    rows: List[List[str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            rows.append(row)
    return rows


def _migrate_csv_to_tsv(csv_path: Path, tsv_path: Path) -> None:
    """Convert a legacy 8-column CSV glossary to 3-column TSV.

    Extra columns (source, type, gender, refers_to_themself_as, referred_to_as)
    are encoded as key=value pairs in the Notes field if non-empty.
    """
    rows = _read_csv_rows(csv_path)
    tsv_rows: List[List[str]] = [["Original", "Translation", "Notes"]]
    for i, row in enumerate(rows):
        if not row or not row[0].strip():
            continue
        # Skip header
        if i == 0 and row[0].strip().lower() == "original":
            continue
        while len(row) < 8:
            row.append("")
        original, translation, notes = row[0], row[1], row[2]
        source, etype, gender, refers, referred = row[3], row[4], row[5], row[6], row[7]
        # Encode non-empty extra fields into Notes parenthetical
        extras = []
        if source:
            extras.append(f"source={source}")
        if etype:
            extras.append(f"type={etype}")
        if gender:
            extras.append(f"gender={gender}")
        if refers:
            extras.append(f"refers_as={refers}")
        if referred:
            extras.append(f"referred_as={referred}")
        if extras:
            suffix = " (" + "; ".join(extras) + ")"
            notes = notes + suffix if notes else suffix.strip()
        tsv_rows.append([original, translation, notes])
    _write_tsv(tsv_path, tsv_rows)


def _merge_json_glossary_into_tsv(json_path: Path, tsv_path: Path) -> None:
    """Merge a legacy global_glossary.json into globalglossary.tsv.

    JSON format expected: list of {"col1": ..., "col2": ..., "col3": ...} dicts.
    Entries whose Original is already present in TSV are skipped.
    """
    import json
    try:
        with json_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return
    if not isinstance(data, list):
        return

    # Load existing TSV entries
    existing = read_unified_glossary()

    for item in data:
        if not isinstance(item, dict):
            continue
        original = str(item.get("col1", "")).strip()
        if not original or original.lower() == "original":
            continue
        if original in existing:
            continue  # don't overwrite
        existing[original] = GlossaryEntry(
            original=original,
            translation=str(item.get("col2", "")),
            notes=str(item.get("col3", "")),
        )

    write_unified_glossary(existing)


def _write_csv(path: Path, rows: List[List[str]]) -> None:
    """Write rows to CSV at path (creates parent directories if needed).
    
    Raises detailed exceptions if write fails.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        raise PermissionError(f"Cannot create directory {path.parent}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to create directory {path.parent}: {e}") from e
    
    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerows(rows)
    except PermissionError as e:
        raise PermissionError(f"Cannot write to {path}: Permission denied. Check file permissions or if file is open in another program.") from e
    except OSError as e:
        raise OSError(f"OS error writing to {path}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error writing to {path}: {e}") from e


# ---------------- Unified glossary data structure ---------------- #


class GlossaryEntry:
    """Represents a single glossary entry.

    The canonical storage format is a 3-column TSV (Original, Translation, Notes).
    Extended metadata (source, type, gender, refers_to_themself_as, referred_to_as)
    is serialised into the Notes field as a parenthetical key=value suffix and
    parsed back transparently when reading.

    Example Notes value with metadata:
        "Main heroine (source=Analysis; type=Name; gender=Female)"
    """

    def __init__(
        self,
        original: str,
        translation: str = "",
        notes: str = "",
        source: str = "",
        entry_type: str = "",
        gender: str = "",
        refers_to_themself_as: str = "",
        referred_to_as: str = "",
    ):
        self.original = original
        self.translation = translation
        self.notes = notes
        self.source = source
        self.entry_type = entry_type
        self.gender = gender
        self.refers_to_themself_as = refers_to_themself_as
        self.referred_to_as = referred_to_as

    # --- TSV 3-column serialisation (Phase 62 canonical format) ---

    def to_tsv_row(self) -> List[str]:
        """Encode entry as [Original, Translation, Notes] for TSV storage.

        Non-empty extended fields are appended to Notes as
        " (source=X; type=Y; gender=Z; refers_as=A; referred_as=B)".
        """
        extras = []
        if self.source:
            extras.append(f"source={self.source}")
        if self.entry_type:
            extras.append(f"type={self.entry_type}")
        if self.gender:
            extras.append(f"gender={self.gender}")
        if self.refers_to_themself_as:
            extras.append(f"refers_as={self.refers_to_themself_as}")
        if self.referred_to_as:
            extras.append(f"referred_as={self.referred_to_as}")

        notes = self.notes
        if extras:
            suffix = "(" + "; ".join(extras) + ")"
            notes = (notes + " " + suffix).strip() if notes else suffix
        return [self.original, self.translation, notes]

    @staticmethod
    def from_tsv_row(row: List[str]) -> "GlossaryEntry":
        """Create entry from a 3-column TSV row; decode embedded metadata."""
        while len(row) < 3:
            row.append("")
        original, translation, raw_notes = row[0], row[1], row[2]

        # Parse optional "(key=value; ...)" metadata suffix
        source = entry_type = gender = refers = referred = ""
        notes = raw_notes
        import re as _re
        m = _re.search(r"\(([^)]+)\)\s*$", raw_notes)
        if m:
            meta_str = m.group(1)
            # Only treat as metadata if it contains key=value pairs
            if "=" in meta_str:
                meta: dict[str, str] = {}
                for part in meta_str.split(";"):
                    part = part.strip()
                    if "=" in part:
                        k, _, v = part.partition("=")
                        meta[k.strip()] = v.strip()
                if any(k in meta for k in ("source", "type", "gender", "refers_as", "referred_as")):
                    source = meta.get("source", "")
                    entry_type = meta.get("type", "")
                    gender = meta.get("gender", "")
                    refers = meta.get("refers_as", "")
                    referred = meta.get("referred_as", "")
                    # Strip the metadata suffix from plain Notes text
                    notes = raw_notes[: m.start()].rstrip()

        return GlossaryEntry(
            original=original,
            translation=translation,
            notes=notes,
            source=source,
            entry_type=entry_type,
            gender=gender,
            refers_to_themself_as=refers,
            referred_to_as=referred,
        )

    # --- Legacy CSV compatibility (kept for internal migration only) ---

    def to_row(self) -> List[str]:
        """Legacy: Convert entry to 8-column CSV row (used by migration only)."""
        return [
            self.original,
            self.translation,
            self.notes,
            self.source,
            self.entry_type,
            self.gender,
            self.refers_to_themself_as,
            self.referred_to_as,
        ]

    @staticmethod
    def from_row(row: List[str]) -> "GlossaryEntry":
        """Legacy: Create entry from 8-column CSV row (pads missing columns)."""
        while len(row) < 8:
            row.append("")
        return GlossaryEntry(
            original=row[0],
            translation=row[1],
            notes=row[2],
            source=row[3],
            entry_type=row[4],
            gender=row[5],
            refers_to_themself_as=row[6],
            referred_to_as=row[7],
        )


def read_unified_glossary() -> Dict[str, GlossaryEntry]:
    """Read unified glossary TSV and return dict mapping Original -> GlossaryEntry.

    Reads from ``user/globalglossary.tsv`` (3-column TSV, Phase 62 format).
    Also accepts legacy 8-column CSV files transparently (migration triggers
    automatically on the first call via ``_unified_glossary_path()``).

    Returns:
        Ordered dict of Original → GlossaryEntry (empty if file missing).
    """
    path = _unified_glossary_path()
    entries: Dict[str, GlossaryEntry] = {}

    if not path.exists():
        return entries

    # Detect format: TSV vs CSV
    is_tsv = path.suffix.lower() == ".tsv"

    rows: List[List[str]] = []
    if is_tsv:
        rows = _read_tsv_rows(path)
    else:
        rows = _read_csv_rows(path)

    for i, row in enumerate(rows):
        if not row or not row[0].strip():
            continue
        # Skip header row
        if i == 0 and row[0].strip().lower() == "original":
            continue

        if is_tsv or len(row) <= 3:
            entry = GlossaryEntry.from_tsv_row(row)
        else:
            # Legacy 8-column CSV — use legacy parser
            entry = GlossaryEntry.from_row(row)

        entries[entry.original] = entry

    return entries


def write_unified_glossary(entries: Dict[str, GlossaryEntry]) -> Path:
    """Write glossary entries to unified TSV (3-column, Phase 62 format).

    Writes header row followed by all entries to ``user/globalglossary.tsv``.
    Extended metadata fields are encoded into the Notes column.

    Performs diagnostics and raises detailed exceptions if write fails.
    """
    path = _unified_glossary_path()

    # Perform pre-write diagnostics
    diag = diagnose_glossary_path(path)
    logging.debug("Pre-write diagnostics for %s: %s", path, diag)

    if diag["exists"] and not diag["writable"]:
        error_msg = (
            f"Glossary file exists but is not writable: {path}\n"
            f"Error: {diag.get('error', 'Unknown')}\n"
            "Check if the file is open in another program or permissions are incorrect."
        )
        logging.error(error_msg)
        raise PermissionError(error_msg)

    if not diag["parent_exists"] or not diag["parent_writable"]:
        error_msg = (
            f"Cannot write to glossary directory: {path.parent}\n"
            f"Parent exists: {diag['parent_exists']}, Writable: {diag['parent_writable']}\n"
            f"Error: {diag.get('error', 'Unknown')}"
        )
        logging.error(error_msg)
        raise PermissionError(error_msg)

    # Build TSV rows
    rows: List[List[str]] = [UNIFIED_HEADER]
    for entry in entries.values():
        rows.append(entry.to_tsv_row())

    try:
        _write_tsv(path, rows)
    except Exception as e:
        post_diag = diagnose_glossary_path(path)
        error_msg = (
            f"Failed to write glossary: {e}\n"
            f"Path: {path}\n"
            f"Post-failure diagnostics:\n"
            f"  Exists: {post_diag['exists']}\n"
            f"  Size: {post_diag['size_bytes']} bytes\n"
            f"  Writable: {post_diag['writable']}\n"
            f"  Error: {post_diag.get('error', 'None')}"
        )
        logging.error(error_msg)
        raise RuntimeError(error_msg) from e

    post_diag = diagnose_glossary_path(path)
    if not post_diag["exists"]:
        raise RuntimeError(f"Glossary written but file missing: {path}")
    if post_diag["size_bytes"] == 0:
        raise RuntimeError(
            f"Glossary written but file is empty: {path} ({len(entries)} entries attempted)"
        )

    logging.info(
        "Wrote unified glossary: %s (%d entries, %d bytes)",
        path, len(entries), post_diag["size_bytes"],
    )
    return path


def update_unified_glossary(
    new_entries: List[GlossaryEntry],
    update_mode: str = UPDATE_MODE_ADD,
) -> Path:
    """Update unified glossary with new entries based on update mode.
    
    Args:
        new_entries: List of entries to add/update
        update_mode: One of UPDATE_MODE_ADD, UPDATE_MODE_UPDATE, UPDATE_MODE_OVERWRITE, or UPDATE_MODE_NEW
            - ADD: Only add new entries (skip existing)
            - UPDATE: Add new + fill empty fields in existing entries
            - OVERWRITE: Add new + replace all fields in existing entries
            - NEW: Archive existing glossary and create fresh one with only new entries
        
    Returns:
        Path to updated glossary file
    """
    # Handle NEW mode: overwrite existing with fresh entries (no archiving)
    if update_mode == UPDATE_MODE_NEW:
        logging.info("NEW mode: Overwriting glossary with fresh entries")
        # Create fresh glossary with only new entries
        fresh_entries: Dict[str, GlossaryEntry] = {}
        for entry in new_entries:
            fresh_entries[entry.original] = entry
        return write_unified_glossary(fresh_entries)
    
    # Handle other modes: read existing and merge
    existing = read_unified_glossary()
    
    for entry in new_entries:
        if entry.original not in existing:
            # New entry: always add
            existing[entry.original] = entry
        elif update_mode == UPDATE_MODE_OVERWRITE:
            # Overwrite mode: replace all fields
            existing[entry.original] = entry
        elif update_mode == UPDATE_MODE_UPDATE:
            # Update mode: fill empty fields only
            old_entry = existing[entry.original]
            if not old_entry.translation and entry.translation:
                old_entry.translation = entry.translation
            if not old_entry.notes and entry.notes:
                old_entry.notes = entry.notes
            if not old_entry.source and entry.source:
                old_entry.source = entry.source
            if not old_entry.entry_type and entry.entry_type:
                old_entry.entry_type = entry.entry_type
            if not old_entry.gender and entry.gender:
                old_entry.gender = entry.gender
            if not old_entry.refers_to_themself_as and entry.refers_to_themself_as:
                old_entry.refers_to_themself_as = entry.refers_to_themself_as
            if not old_entry.referred_to_as and entry.referred_to_as:
                old_entry.referred_to_as = entry.referred_to_as
        # else: ADD mode, skip existing entries
    
    return write_unified_glossary(existing)


# ---------------- Legacy support and migration ---------------- #

def _glossary_dir() -> Path:
    """Legacy function - returns old glossaries directory."""
    here = Path(__file__).resolve()
    return here.parent / "glossaries"


def _read_tsv_rows(path: Path) -> List[List[str]]:
    if not path.exists():
        return []
    rows: List[List[str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            rows.append(row)
    return rows


def _write_tsv(path: Path, rows: List[List[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerows(rows)


# ---------------- Legacy support and migration ---------------- #

# NOTE: The following functions have been moved to glossaries/ modules:
# - infer_gender_from_context -> name_glossary_functions.py
# - romanize_pronoun -> name_glossary_functions.py
# - romanize_honorific -> name_glossary_functions.py
# - _is_valid_speaker_entry -> name_glossary_functions.py
# - update_speakers_in_glossary -> name_glossary_functions.py
# - update_code_in_glossary -> code_glossary_functions.py
# They are imported at the top of this file for backward compatibility.


# ---------------- Public entry: update glossaries from input ---------------- #

def update_glossaries_from_analysis(
    input_path: Path,
    logs_dir: Path,
    confidence_threshold: float = DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
    update_mode: str = UPDATE_MODE_ADD,
) -> Dict[str, Any]:
    """Analyze input minimally and update the unified glossary.

    Args:
        input_path: Path to input file to analyze
        logs_dir: Directory for log files
        confidence_threshold: Minimum confidence (0-100%) for gender inference
        update_mode: One of UPDATE_MODE_ADD, UPDATE_MODE_UPDATE, or UPDATE_MODE_OVERWRITE

    Returns:
        Dict with glossary paths and counts
    """
    # Recreate speaker/code counts with minimal IO
    lines: List[str] = []
    try:
        suffix = Path(input_path).suffix.lower()
        if suffix in (".txt",):
            lines = read_text(input_path).splitlines()
        elif suffix in (".csv", ".tsv"):
            rows, _ = read_table(input_path)
            lines = [row[0] if row else "" for row in rows]
        elif suffix in (".json",):
            pairs = read_json_pairs(input_path)
            lines = [p[0] for p in pairs]
        elif suffix in (".xlsx",):
            pairs = read_xlsx_pairs(input_path) or []
            lines = [p[0] for p in pairs]
    except Exception:
        lines = []

    # Lazy imports to avoid circular imports between glossary and helper modules
    from .glossaries.name_glossary_functions import (
        detect_speaker,
        update_speakers_in_glossary,
    )
    from .glossaries.code_glossary_functions import (
        detect_code,
        update_code_in_glossary,
    )

    speakers_count: Dict[str, int] = {}
    code_counts: Dict[str, int] = {}
    for line in lines:
        sp = detect_speaker(line)
        if sp:
            speakers_count[sp] = speakers_count.get(sp, 0) + 1
        cd = detect_code(line)
        if cd.get("has_code"):
            # Use spans returned by detect_code to extract segments
            for span in cd.get("spans", []):
                if not span or len(span) < 2:
                    continue
                s_idx, e_idx = span[0], span[1]
                seg = line[s_idx:e_idx]
                if seg:
                    code_counts[seg] = code_counts.get(seg, 0) + 1

    sp_path = update_speakers_in_glossary(
        speakers_count,
        confidence_threshold=confidence_threshold,
        update_mode=update_mode
    )
    code_path = update_code_in_glossary(code_counts, update_mode=update_mode)

    # Log convenience paths
    logging.info("Updated unified glossary: speakers=%d codes=%d", len(speakers_count), len(code_counts))
    return {"glossary_path": str(sp_path), "speakers_added": len(speakers_count), "codes_added": len(code_counts)}


# ---------------- Migration utilities ---------------- #

def migrate_legacy_glossaries_to_unified() -> Dict[str, int]:
    """Migrate existing TSV and JSON glossaries to unified CSV format.
    
    Reads from:
    - functions/glossaries/speakers.analysis.tsv
    - functions/glossaries/code.analysis.tsv
    - config/glossary.json
    
    Writes to:
    - user/glossary.csv (unified format)
    
    Returns:
        Dict with counts: {'speakers': N, 'codes': M, 'json': P}
    """
    counts = {"speakers": 0, "codes": 0, "json": 0}
    existing = read_unified_glossary()
    new_entries: List[GlossaryEntry] = []
    
    # 1. Migrate speakers.analysis.tsv
    try:
        old_glossaries = _glossary_dir()
        speakers_tsv = old_glossaries / "speakers.analysis.tsv"
        if speakers_tsv.exists():
            rows = _read_tsv_rows(speakers_tsv)
            for i, row in enumerate(rows):
                if not row or not row[0].strip():
                    continue
                # Skip header
                if i == 0 and row[0].strip().lower() == "speaker":
                    continue
                    
                original = row[0].strip()
                translation = row[1].strip() if len(row) > 1 else ""
                comment = row[2].strip() if len(row) > 2 else ""
                
                # Skip if already in unified glossary
                if original in existing:
                    continue
                
                entry = GlossaryEntry(
                    original=original,
                    translation=translation,
                    notes=comment,
                    source="Migrated from speakers.tsv",
                    entry_type=TYPE_NAME,
                    gender="",
                    refers_to_themself_as="",
                    referred_to_as="",
                )
                new_entries.append(entry)
                counts["speakers"] += 1
    except Exception as exc:
        logging.error("Failed to migrate speakers.tsv: %s", exc)
    
    # 2. Migrate code.analysis.tsv
    try:
        old_glossaries = _glossary_dir()
        code_tsv = old_glossaries / "code.analysis.tsv"
        if code_tsv.exists():
            rows = _read_tsv_rows(code_tsv)
            for i, row in enumerate(rows):
                if not row or not row[0].strip():
                    continue
                # Skip header
                if i == 0 and row[0].strip().lower() == "code":
                    continue
                    
                original = row[0].strip()
                # Skip if already in unified glossary
                if original in existing:
                    continue
                
                # Code TSV has: Code, IsInvisible, IsWord, IsNumber, IsBoundary, Comment
                flags = []
                if len(row) > 1:
                    flags.append(f"IsInvisible={row[1]}")
                if len(row) > 2:
                    flags.append(f"IsWord={row[2]}")
                if len(row) > 3:
                    flags.append(f"IsNumber={row[3]}")
                if len(row) > 4:
                    flags.append(f"IsBoundary={row[4]}")
                comment = row[5].strip() if len(row) > 5 else ""
                notes = ", ".join(flags) + (f" - {comment}" if comment else "")
                
                entry = GlossaryEntry(
                    original=original,
                    translation="",
                    notes=notes,
                    source="Migrated from code.tsv",
                    entry_type=TYPE_CODE,
                    gender="",
                    refers_to_themself_as="",
                    referred_to_as="",
                )
                new_entries.append(entry)
                counts["codes"] += 1
    except Exception as exc:
        logging.error("Failed to migrate code.tsv: %s", exc)
    
    # 3. Migrate glossary.json
    try:
        here = Path(__file__).resolve()
        CherryAI_root = here.parent.parent
        config_dir = CherryAI_root / "config"
        glossary_json = config_dir / "glossary.json"
        
        if glossary_json.exists():
            import json
            with glossary_json.open("r", encoding="utf-8") as f:
                items = json.load(f)
            
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    
                    original = item.get("in", "").strip()
                    if not original:
                        continue
                    
                    # Skip if already in unified glossary
                    if original in existing:
                        continue
                    
                    translation = item.get("out", "").strip()
                    note = item.get("note", "").strip()
                    
                    # Try to determine type based on note content
                    entry_type = TYPE_TERM
                    if any(gender in note for gender in ["Male", "Female", "Neutral"]):
                        entry_type = TYPE_NAME
                    
                    # Extract gender from note if present
                    gender = ""
                    for g in [GENDER_MALE, GENDER_FEMALE, GENDER_NEUTRAL, GENDER_UNKNOWN]:
                        if g in note:
                            gender = g
                            break
                    
                    entry = GlossaryEntry(
                        original=original,
                        translation=translation,
                        notes=note,
                        source="Migrated from glossary.json",
                        entry_type=entry_type,
                        gender=gender,
                        refers_to_themself_as="",
                        referred_to_as="",
                    )
                    new_entries.append(entry)
                    counts["json"] += 1
    except Exception as exc:
        logging.error("Failed to migrate glossary.json: %s", exc)
    
    # Write all new entries
    if new_entries:
        update_unified_glossary(new_entries, update_mode=UPDATE_MODE_ADD)
        logging.info(
            "Migration complete: %d speakers, %d codes, %d json entries",
            counts["speakers"],
            counts["codes"],
            counts["json"],
        )
    else:
        logging.info("No new entries to migrate")
    
    return counts


# ---------------- Backwards-compatibility wrappers ---------------- #
def update_speakers_in_glossary(
    speakers_count: Dict[str, int],
    confidence_threshold: float = DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
    update_mode: str = UPDATE_MODE_ADD,
) -> Path:
    """Compatibility wrapper that forwards to new name_glossary_functions.

    This function performs a lazy import to avoid circular import at module
    import time.
    """
    from .glossaries.name_glossary_functions import update_speakers_in_glossary as _impl

    return _impl(speakers_count, confidence_threshold=confidence_threshold, update_mode=update_mode)


def update_code_in_glossary(
    code_counts: Dict[str, int],
    update_mode: str = UPDATE_MODE_ADD,
) -> Path:
    """Compatibility wrapper that forwards to new code_glossary_functions.

    Lazy-imported to avoid circular imports.
    """
    from .glossaries.code_glossary_functions import update_code_in_glossary as _impl

    return _impl(code_counts, update_mode=update_mode)


def infer_gender_from_context(*args, **kwargs):
    """Backward-compatible forwarder to name_glossary_functions.infer_gender_from_context."""
    from .glossaries.name_glossary_functions import infer_gender_from_context as _impl
    return _impl(*args, **kwargs)


def romanize_pronoun(*args, **kwargs):
    from .glossaries.name_glossary_functions import romanize_pronoun as _impl
    return _impl(*args, **kwargs)


def romanize_honorific(*args, **kwargs):
    from .glossaries.name_glossary_functions import romanize_honorific as _impl
    return _impl(*args, **kwargs)


def detect_speaker(line: str) -> Optional[str]:
    """Forward to name_glossary_functions.detect_speaker for compatibility."""
    from .glossaries.name_glossary_functions import detect_speaker as _impl
    return _impl(line)


def detect_code(line: str) -> Dict[str, Any]:
    """Forward to code_glossary_functions.detect_code for compatibility."""
    from .glossaries.code_glossary_functions import detect_code as _impl
    return _impl(line)


def _is_valid_speaker_entry(name: str, count: int) -> bool:
    """Forward to name_glossary_functions._is_valid_speaker_entry for compatibility."""
    from .glossaries.name_glossary_functions import _is_valid_speaker_entry as _impl
    return _impl(name, count)


# ---------------------------------------------------------------------------
# Phase 52 — Selective Glossary Per Chunk
# ---------------------------------------------------------------------------

# Valid modes for glossary filtering
GLOSSARY_FILTER_ALL = "all"
GLOSSARY_FILTER_ORIGINAL = "original_only"
GLOSSARY_FILTER_BOTH = "original_or_translation"

GLOSSARY_FILTER_MODES = frozenset({
    GLOSSARY_FILTER_ALL,
    GLOSSARY_FILTER_ORIGINAL,
    GLOSSARY_FILTER_BOTH,
})


def filter_glossary_for_chunk(
    glossary_entries: Dict[str, "GlossaryEntry"],
    chunk_lines: List[str],
    mode: str = GLOSSARY_FILTER_ALL,
) -> List["GlossaryEntry"]:
    """Filter glossary entries to those relevant for a given chunk.

    Args:
        glossary_entries: Mapping of original term to GlossaryEntry.
        chunk_lines: Lines of text in the current translation chunk.
        mode: Filtering mode — one of ``"all"``, ``"original_only"``,
            or ``"original_or_translation"``.

    Returns:
        List of matching :class:`GlossaryEntry` instances.  When *mode*
        is ``"all"`` every entry is returned (unfiltered).
    """
    if mode == GLOSSARY_FILTER_ALL:
        return list(glossary_entries.values())

    batch_text = "\n".join(chunk_lines)
    result: List["GlossaryEntry"] = []

    for original, entry in glossary_entries.items():
        if original and original in batch_text:
            result.append(entry)
        elif (
            mode == GLOSSARY_FILTER_BOTH
            and entry.translation
            and entry.translation in batch_text
        ):
            result.append(entry)

    return result


# Re-export constants that analysis.py expects (lazy-loaded to avoid circular imports)
# These will be populated on first access via __getattr__ below
_LAZY_CONSTANTS = {
    'PRONOUN_GENDER': None,
    'HONORIFIC_GENDER': None,
    'PRONOUN_ROMANIZATION': None,
    'HONORIFIC_ROMANIZATION': None,
}


def __getattr__(name: str):
    """Lazy-load constants from glossaries modules to avoid circular imports."""
    if name == 'PRONOUN_GENDER':
        from .glossaries.name_glossary_constants import PRONOUN_GENDER
        return PRONOUN_GENDER
    elif name == 'HONORIFIC_GENDER':
        from .glossaries.name_glossary_constants import HONORIFIC_GENDER
        return HONORIFIC_GENDER
    elif name == 'PRONOUN_ROMANIZATION':
        from .glossaries.name_glossary_constants import PRONOUN_ROMANIZATION
        return PRONOUN_ROMANIZATION
    elif name == 'HONORIFIC_ROMANIZATION':
        from .glossaries.name_glossary_constants import HONORIFIC_ROMANIZATION
        return HONORIFIC_ROMANIZATION
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


