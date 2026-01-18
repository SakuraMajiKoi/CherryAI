from __future__ import annotations

import datetime as dt
import json
import logging
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, Callable, cast
import csv
from dataclasses import dataclass, field


# ----------------------------- Data models (migrated) ----------------------------- #
@dataclass
class Operation:
    """A single operation row (mode + up to 4 inputs + optional regex flag).

    This was previously defined in `functions/models.py`; moved here during
    refactor so `mainhelper` is the single source of shared helpers and types.
    """

    modus: str
    in1: str = ""
    in2: str = ""
    in3: str = ""
    in4: str = ""
    is_regex: Optional[bool] = None


# ----------------------------- Manifest v2.0 LineEntry ----------------------------- #
# Maximum TLC/Edit pass number to search (reasonable upper limit for iterations)
_MAX_PASS_SEARCH = 100

# Field categories for resolution logic
TEXT_FIELDS = ["orig", "prepro", "tl", "postpro", "wordwr", "overwrite"]
METADATA_FIELDS = ["log", "prepro_ops", "deleted", "updated", "idx"]
OUTPUT_FIELDS = ["overwrite", "wordwr", "postpro"]


@dataclass
class LineEntry:
    """A single line entry in the Manifest v2.1 format.

    Stores progressive translation states for one line with sparse storage:
    only fields that are populated are serialized.

    Field Progression Order:
        orig → prepro → edited_prepro → tl → tlc1 → edit1 → tlc2 → edit2 → ... → postpro → wordwr → overwrite

    Special Fields (NEVER used as text input):
        - log: Error/warning messages for this line
        - prepro_ops: Metadata array for restoration operations (NOT text content)
        - deleted: Boolean flag for lines removed in game updates
        - updated: New content from game update (separate workflow)
        - tags: Content classification, status, severity, and quality tags (v2.1)
    """

    idx: int  # Line index (0-based)
    orig: str  # Original text (always present)

    # Preprocessing (optional, sparse)
    prepro: Optional[str] = None  # Pre-processed text
    prepro_ops: Optional[List[Dict[str, Any]]] = None  # Operation metadata (NOT text)
    edited_prepro: Optional[str] = None  # User-edited preprocessed text (Task 33.1)

    # Translation chain (optional, sparse)
    tl: Optional[str] = None  # Translation result
    # Dynamic TLC/Edit passes stored as instance attributes: tlc1, edit1, tlc2, etc.

    # Post-processing (optional, sparse)
    postpro: Optional[str] = None  # Post-processed (restored) text
    wordwr: Optional[str] = None  # Word-wrapped text
    overwrite: Optional[str] = None  # User manual override

    # Metadata (never used as text input)
    log: Optional[str] = None  # Errors/warnings for this line
    deleted: bool = False  # True if line was deleted in game update
    updated: Optional[str] = None  # New content from game update

    # Tags (v2.1) - Content classification, status, and quality tags
    tags: Optional[Any] = None  # LineTags from auto_tagger module

    def __post_init__(self) -> None:
        """Initialize dynamic tlc/edit attributes storage."""
        # Dynamic TLC/Edit passes are stored as regular attributes
        # e.g., self.tlc1, self.edit1, self.tlc2, etc.
        pass

    def set_tlc(self, pass_num: int, value: str) -> None:
        """Set TLC pass N result."""
        if pass_num < 1:
            raise ValueError(f"TLC pass number must be >= 1, got {pass_num}")
        setattr(self, f"tlc{pass_num}", value)

    def set_edit(self, pass_num: int, value: str) -> None:
        """Set Edit pass N result."""
        if pass_num < 1:
            raise ValueError(f"Edit pass number must be >= 1, got {pass_num}")
        setattr(self, f"edit{pass_num}", value)

    def get_tlc(self, pass_num: int) -> Optional[str]:
        """Get TLC pass N result, or None if not set."""
        return getattr(self, f"tlc{pass_num}", None)

    def get_edit(self, pass_num: int) -> Optional[str]:
        """Get Edit pass N result, or None if not set."""
        return getattr(self, f"edit{pass_num}", None)

    def get_input_for_translation(self) -> str:
        """Input for Translation API call.

        Returns: edited_prepro if exists, else prepro if exists, else orig.
        
        Resolution order:
        1. edited_prepro (user manually edited before translation)
        2. prepro (automated preprocessing result)
        3. orig (original text)
        """
        if self.edited_prepro is not None:
            return self.edited_prepro
        return self.prepro if self.prepro is not None else self.orig

    def get_input_for_tlc(self, pass_num: int) -> str:
        """Input for TLC Pass N.

        Resolution (backwards search):
        - Pass 1: Use "tl"
        - Pass N>1: Use edit{N-1} → tlc{N-1} → ... → tl

        Args:
            pass_num: The TLC pass number (1-indexed)

        Returns:
            Best available input for TLC pass
        """
        if pass_num < 1:
            raise ValueError(f"TLC pass number must be >= 1, got {pass_num}")

        if pass_num == 1:
            # TLC 1 checks the translation
            if self.tl is not None:
                return self.tl
            # Fallback if no translation yet
            return self.prepro if self.prepro is not None else self.orig

        # For pass N > 1: search backwards for edit{N-1}, tlc{N-1}, etc.
        for i in range(pass_num - 1, 0, -1):
            edit_val: Optional[str] = getattr(self, f"edit{i}", None)
            if edit_val is not None:
                return edit_val
            tlc_val = cast(Optional[str], getattr(self, f"tlc{i}", None))
            if tlc_val is not None:
                return tlc_val

        # Fallback to translation or earlier
        if self.tl is not None:
            return self.tl
        return self.prepro if self.prepro is not None else self.orig

    def get_input_for_edit(self, pass_num: int) -> str:
        """Input for Edit Pass N.

        Resolution (backwards search):
        - Use tlc{N} if exists
        - Else edit{N-1}, tlc{N-1}, ... → tl

        Args:
            pass_num: The Edit pass number (1-indexed)

        Returns:
            Best available input for Edit pass
        """
        if pass_num < 1:
            raise ValueError(f"Edit pass number must be >= 1, got {pass_num}")

        # First try tlc{N} for this edit pass
        tlc_val: Optional[str] = getattr(self, f"tlc{pass_num}", None)
        if tlc_val is not None:
            return tlc_val

        # Search backwards
        for i in range(pass_num - 1, 0, -1):
            edit_val: Optional[str] = getattr(self, f"edit{i}", None)
            if edit_val is not None:
                return edit_val
            tlc_val = cast(Optional[str], getattr(self, f"tlc{i}", None))
            if tlc_val is not None:
                return tlc_val

        # Fallback to translation or earlier
        if self.tl is not None:
            return self.tl
        return self.prepro if self.prepro is not None else self.orig

    def get_input_for_postprocessing(self) -> str:
        """Input for Post-processing (restoration).

        Resolution: Find latest in TLC/Edit chain, fallback to tl/prepro/orig.
        NOTE: Uses prepro_ops separately for restoration mappings.

        Returns:
            Latest translation result to restore into
        """
        # Find highest N with edit{N} or tlc{N}
        for n in range(_MAX_PASS_SEARCH, 0, -1):
            edit_val: Optional[str] = getattr(self, f"edit{n}", None)
            if edit_val is not None:
                return edit_val
            tlc_val: Optional[str] = getattr(self, f"tlc{n}", None)
            if tlc_val is not None:
                return tlc_val

        # Fallback chain
        if self.tl is not None:
            return self.tl
        if self.prepro is not None:
            return self.prepro
        return self.orig

    def get_input_for_wordwrap(self) -> str:
        """Input for Wordwrap operation.

        Returns: postpro if exists, else fallback via get_input_for_postprocessing()
        """
        if self.postpro is not None:
            return self.postpro
        return self.get_input_for_postprocessing()

    def get_final_output(self) -> str:
        """Output for final export.

        This is the ONLY case where "rightmost available" logic applies.

        Returns:
            overwrite → wordwr → postpro (first available)

        Raises:
            ValueError: If no output available
        """
        if self.overwrite is not None:
            return self.overwrite
        if self.wordwr is not None:
            return self.wordwr
        if self.postpro is not None:
            return self.postpro
        raise ValueError(f"Line {self.idx} has no final output (postpro/wordwr/overwrite)")

    def has_final_output(self) -> bool:
        """Check if any final output field is populated.

        Returns:
            True if overwrite, wordwr, or postpro exists
        """
        return (
            self.overwrite is not None
            or self.wordwr is not None
            or self.postpro is not None
        )

    def get_populated_fields(self) -> List[str]:
        """List of populated text fields (excludes metadata fields).

        Excludes: log, prepro_ops, deleted, updated, idx

        Returns:
            List of field names that have values
        """
        result: List[str] = []

        # Check static text fields
        if self.orig is not None:
            result.append("orig")
        if self.prepro is not None:
            result.append("prepro")
        if self.tl is not None:
            result.append("tl")
        if self.postpro is not None:
            result.append("postpro")
        if self.wordwr is not None:
            result.append("wordwr")
        if self.overwrite is not None:
            result.append("overwrite")

        # Add dynamic TLC/Edit fields in order
        for n in range(1, _MAX_PASS_SEARCH + 1):
            if getattr(self, f"tlc{n}", None) is not None:
                result.append(f"tlc{n}")
            if getattr(self, f"edit{n}", None) is not None:
                result.append(f"edit{n}")

        return result

    def get_highest_tlc_pass(self) -> int:
        """Get the highest TLC pass number that exists.

        Returns:
            Highest pass number, or 0 if no TLC passes exist
        """
        for n in range(_MAX_PASS_SEARCH, 0, -1):
            if getattr(self, f"tlc{n}", None) is not None:
                return n
        return 0

    def get_highest_edit_pass(self) -> int:
        """Get the highest Edit pass number that exists.

        Returns:
            Highest pass number, or 0 if no Edit passes exist
        """
        for n in range(_MAX_PASS_SEARCH, 0, -1):
            if getattr(self, f"edit{n}", None) is not None:
                return n
        return 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary with sparse storage.

        Only includes fields that are populated (not None, not False for bools).
        """
        result: Dict[str, Any] = {"idx": self.idx, "orig": self.orig}

        # Optional static fields
        if self.prepro is not None:
            result["prepro"] = self.prepro
        if self.prepro_ops is not None:
            result["prepro_ops"] = self.prepro_ops
        if self.edited_prepro is not None:
            result["edited_prepro"] = self.edited_prepro
        if self.tl is not None:
            result["tl"] = self.tl
        if self.postpro is not None:
            result["postpro"] = self.postpro
        if self.wordwr is not None:
            result["wordwr"] = self.wordwr
        if self.overwrite is not None:
            result["overwrite"] = self.overwrite

        # Metadata fields
        if self.log is not None:
            result["log"] = self.log
        if self.deleted:
            result["deleted"] = True
        if self.updated is not None:
            result["updated"] = self.updated

        # Tags (v2.1)
        if self.tags is not None:
            # LineTags has to_dict method
            tags_dict = self.tags.to_dict() if hasattr(self.tags, "to_dict") else self.tags
            if tags_dict:  # Only include if non-empty
                result["tags"] = tags_dict

        # Dynamic TLC/Edit fields
        for n in range(1, _MAX_PASS_SEARCH + 1):
            tlc_val = getattr(self, f"tlc{n}", None)
            if tlc_val is not None:
                result[f"tlc{n}"] = tlc_val
            edit_val = getattr(self, f"edit{n}", None)
            if edit_val is not None:
                result[f"edit{n}"] = edit_val

        return result

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "LineEntry":
        """Create LineEntry from dictionary.

        Args:
            data: Dictionary with line entry fields

        Returns:
            LineEntry instance
        """
        # Handle tags deserialization
        tags = None
        if "tags" in data:
            try:
                # Import LineTags lazily to avoid circular imports
                from .auto_tagger import LineTags
                tags = LineTags.from_dict(data["tags"])
            except (ImportError, TypeError):
                # Keep as dict if auto_tagger not available
                tags = data["tags"]

        entry = LineEntry(
            idx=data.get("idx", 0),
            orig=data.get("orig", ""),
            prepro=data.get("prepro"),
            prepro_ops=data.get("prepro_ops"),
            edited_prepro=data.get("edited_prepro"),
            tl=data.get("tl"),
            postpro=data.get("postpro"),
            wordwr=data.get("wordwr"),
            overwrite=data.get("overwrite"),
            log=data.get("log"),
            deleted=data.get("deleted", False),
            updated=data.get("updated"),
            tags=tags,
        )

        # Restore dynamic TLC/Edit fields
        for key, value in data.items():
            if key.startswith("tlc") and key[3:].isdigit():
                setattr(entry, key, value)
            elif key.startswith("edit") and key[4:].isdigit():
                setattr(entry, key, value)

        return entry


# ----------------------------- Manifest v2.1 Class ----------------------------- #
MANIFEST_VERSION = "2.1"


@dataclass
class Manifest:
    """Manifest v2.1 with per-line entry storage and tags support.

    Primary storage is the `lines` array of LineEntry objects.
    v2.1 adds: tags field for content classification, status, and quality.
    """

    summary: str
    metadata: Dict[str, Any]
    operations: List[Operation]
    mappings: Dict[str, Any] = field(
        default_factory=lambda: {
            "protected": [],
            "anchors": [],
        }
    )
    # Per-line entry storage (primary data structure)
    lines: List[LineEntry] = field(default_factory=list)
    # Manifest version
    version: str = MANIFEST_VERSION
    # Origin file tracking
    origin_file: Optional[str] = None
    root_selected: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize version if not set."""
        if not self.version:
            self.version = MANIFEST_VERSION

    def get_line(self, idx: int) -> Optional[LineEntry]:
        """Get LineEntry by index.

        Args:
            idx: Line index (0-based)

        Returns:
            LineEntry if exists, None otherwise
        """
        for line in self.lines:
            if line.idx == idx:
                return line
        return None

    def set_line(self, idx: int, line_entry: LineEntry) -> None:
        """Set or update a LineEntry.

        Args:
            idx: Line index (0-based)
            line_entry: LineEntry to set
        """
        for i, existing in enumerate(self.lines):
            if existing.idx == idx:
                self.lines[i] = line_entry
                return
        self.lines.append(line_entry)

    def ensure_line(self, idx: int, orig: str = "") -> LineEntry:
        """Get or create a LineEntry for the given index.

        Args:
            idx: Line index (0-based)
            orig: Original text if creating new entry

        Returns:
            Existing or new LineEntry
        """
        existing = self.get_line(idx)
        if existing is not None:
            return existing
        new_line = LineEntry(idx=idx, orig=orig)
        self.lines.append(new_line)
        return new_line

    def set_field(self, idx: int, field_name: str, value: Any) -> None:
        """Set a field value on a LineEntry (sparse insert).

        Args:
            idx: Line index (0-based)
            field_name: Field name (e.g., "prepro", "tl", "tlc1")
            value: Value to set
        """
        line = self.ensure_line(idx)
        if field_name.startswith("tlc") and field_name[3:].isdigit():
            line.set_tlc(int(field_name[3:]), value)
        elif field_name.startswith("edit") and field_name[4:].isdigit():
            line.set_edit(int(field_name[4:]), value)
        else:
            setattr(line, field_name, value)

    def add_prepro_op(self, idx: int, op_data: Dict[str, Any]) -> None:
        """Add a preprocessing operation to a line's prepro_ops.

        Args:
            idx: Line index (0-based)
            op_data: Operation data dict (e.g., {"mode": "protect_code", "mappings": {...}})
        """
        line = self.ensure_line(idx)
        if line.prepro_ops is None:
            line.prepro_ops = []
        line.prepro_ops.append(op_data)

    def get_prepro_ops(self, idx: int, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get preprocessing operations for a line.

        Args:
            idx: Line index (0-based)
            mode: Optional mode filter (e.g., "protect_code")

        Returns:
            List of operation dicts (empty if none)
        """
        line = self.get_line(idx)
        if line is None or line.prepro_ops is None:
            return []
        if mode is None:
            return line.prepro_ops
        return [op for op in line.prepro_ops if op.get("mode") == mode]

    def initialize_from_text(self, text: str) -> None:
        """Initialize lines array from input text.

        Creates LineEntry for each line with only the `orig` field populated.

        Args:
            text: Input text (newline-separated)
        """
        self.lines = []
        for idx, line_text in enumerate(text.split("\n")):
            self.lines.append(LineEntry(idx=idx, orig=line_text))

    def get_original_text(self) -> str:
        """Reconstruct original text from lines array.

        Returns:
            Original text with newlines
        """
        sorted_lines = sorted(self.lines, key=lambda x: x.idx)
        return "\n".join(line.orig for line in sorted_lines)

    def get_final_text(self) -> str:
        """Reconstruct final output text from lines array.

        Uses get_final_output() for each line.

        Returns:
            Final text with newlines

        Raises:
            ValueError: If any line has no final output
        """
        sorted_lines = sorted(self.lines, key=lambda x: x.idx)
        return "\n".join(line.get_final_output() for line in sorted_lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manifest to dictionary (v2.0 format).

        Returns:
            Dictionary with all manifest data including lines array
        """
        out: Dict[str, Any] = {
            "version": self.version,
            "summary": self.summary,
            "metadata": self.metadata,
            "operations": [op.__dict__ for op in self.operations],
            "mappings": self.mappings,
        }

        # v2.0: Add origin file tracking
        if self.origin_file is not None:
            out["origin_file"] = self.origin_file
        if self.root_selected is not None:
            out["root_selected"] = self.root_selected

        # v2.0: Add lines array (primary storage)
        if self.lines:
            out["lines"] = [line.to_dict() for line in self.lines]

        # Legacy support: If a pre-run snapshot exists, include it
        try:
            pre_lines = getattr(self, "_pre_lines_runtime", None)
            if pre_lines is not None:
                out["original_lines"] = list(pre_lines)
        except Exception:
            pass

        return out

    def to_pretty_dict(self) -> Dict[str, Any]:
        """Return a human-oriented manifest layout with top-level ops and per-line blocks.

        Structure:
        - ops: { pre: [{id, mode, inputs...}], post: [...] } with ids op1..opN
        - lines: [ { 'original:': str, 'preops:': [...], 'pretl:': str, 'posttl:': str,
                    'postops:': [...], 'final:': str, 'wordw:': str, 'overwrite': str } ]

        Falls back to existing mappings for line sources. Includes legacy fields too so
        older readers remain compatible.
        """
        # Number operations in the configured order
        op_ids: List[str] = [f"op{i+1}" for i in range(len(self.operations))]
        id_by_mode: Dict[str, str] = {}
        for i, op in enumerate(self.operations):
            # First occurrence wins for mode->id mapping
            id_by_mode.setdefault(op.modus, op_ids[i])

        # Identify pre/post-capable ops using the registry if available
        pre_list: List[Dict[str, Any]] = []
        post_list: List[Dict[str, Any]] = []
        try:
            for i, op in enumerate(self.operations):
                op_entry = {
                    "id": op_ids[i],
                    "mode": op.modus,
                    "in1": op.in1,
                    "in2": op.in2,
                    "in3": op.in3,
                    "in4": op.in4,
                    "is_regex": op.is_regex,
                }
                mod = None
                try:
                    mod = _get_mode_registry().get(op.modus)
                except Exception:
                    mod = None
                if mod is not None and hasattr(mod, "apply_pre"):
                    pre_list.append(op_entry)
                if mod is not None and hasattr(mod, "apply_post"):
                    post_list.append(op_entry)
        except Exception:
            # If anything goes wrong, still emit empty lists
            pre_list = pre_list or []
            post_list = post_list or []

        # Extract line data using persisted mappings when available, falling back sensibly
        maps = self.mappings if isinstance(self.mappings, dict) else {}
        # Original lines as recorded during Pre, else from entries
        raw_orig = maps.get("original_lines") if isinstance(maps, dict) else None
        if isinstance(raw_orig, list) and raw_orig:
            orig_lines: List[str] = [str(x) for x in raw_orig]
        else:
            orig_lines = [e.orig for e in self.lines]

        # Pre-TL lines (pre-processed), captured at end of Pre
        raw_pre = maps.get("pre_lines") if isinstance(maps, dict) else None
        pre_lines: List[str] = [str(x) for x in raw_pre] if isinstance(raw_pre, list) else []

        # Post input lines (immediately before Post processing began)
        raw_post_in = maps.get("post_in_lines") if isinstance(maps, dict) else None
        post_in_lines: List[str] = [str(x) for x in raw_post_in] if isinstance(raw_post_in, list) else []

        # Final lines after Post
        raw_final = maps.get("final_lines") if isinstance(maps, dict) else None
        final_lines: List[str] = [str(x) for x in raw_final] if isinstance(raw_final, list) else []

        # Wordwrap lines default to final_lines if absent
        raw_wordw = maps.get("wordwrap_lines") if isinstance(maps, dict) else None
        if isinstance(raw_wordw, list):
            wordw_lines: List[str] = [str(x) for x in raw_wordw]
        else:
            wordw_lines = list(final_lines)

        # Overwrite lines default to wordwrap (or final) if absent
        raw_over = maps.get("overwrite_lines") if isinstance(maps, dict) else None
        if isinstance(raw_over, list):
            overwrite_lines: List[str] = [str(x) for x in raw_over]
        else:
            overwrite_lines = list(wordw_lines)

        # Build preops/postops from LineEntry.prepro_ops
        preops_per_line: Dict[int, List[Dict[str, str]]] = {}
        postops_per_line: Dict[int, List[Dict[str, str]]] = {}
        try:
            for entry in self.lines:
                idx = entry.idx
                if entry.prepro_ops:
                    for op_rec in entry.prepro_ops:
                        phase = str(op_rec.get("phase", ""))
                        mode_name = str(op_rec.get("mode", ""))
                        detail = str(op_rec.get("detail", ""))
                        op_id = id_by_mode.get(mode_name) or mode_name
                        line_op_entry: Dict[str, str] = {"op": op_id, "detail": detail}
                        if phase.lower().startswith("pre"):
                            preops_per_line.setdefault(idx, []).append(line_op_entry)
                        elif phase.lower().startswith("post"):
                            postops_per_line.setdefault(idx, []).append(line_op_entry)
        except Exception:
            pass

        # Build lines array with required keys
        max_len = max(len(orig_lines), len(pre_lines), len(post_in_lines), len(final_lines), len(wordw_lines), len(overwrite_lines))
        lines_out: List[Dict[str, Any]] = []
        for i in range(max_len):
            rec: Dict[str, Any] = {
                "original:": orig_lines[i] if i < len(orig_lines) else "",
                "preops:": preops_per_line.get(i, []),
                "pretl:": pre_lines[i] if i < len(pre_lines) else "",
                "posttl:": post_in_lines[i] if i < len(post_in_lines) else "",
                "postops:": postops_per_line.get(i, []),
                "final:": final_lines[i] if i < len(final_lines) else "",
                "wordw:": wordw_lines[i] if i < len(wordw_lines) else (final_lines[i] if i < len(final_lines) else ""),
                "overwrite": overwrite_lines[i] if i < len(overwrite_lines) else (wordw_lines[i] if i < len(wordw_lines) else (final_lines[i] if i < len(final_lines) else "")),
            }
            lines_out.append(rec)

        pretty = {
            "summary": self.summary,
            "metadata": self.metadata,
            "ops": {"pre": pre_list, "post": post_list},
            "lines": lines_out,
            "operations": [op.__dict__ for op in self.operations],
            "mappings": self.mappings,
        }
        return pretty

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Manifest":
        """Create Manifest from dictionary.

        Args:
            data: Dictionary with manifest data

        Returns:
            Manifest instance
        """
        ops = [Operation(**op) for op in data.get("operations", [])]
        version = data.get("version", MANIFEST_VERSION)

        m = Manifest(
            summary=data.get("summary", ""),
            metadata=data.get("metadata", {}),
            operations=ops,
            mappings=data.get("mappings", {}),
            version=version,
            origin_file=data.get("origin_file"),
            root_selected=data.get("root_selected"),
        )

        # Load lines array directly
        lines_data = data.get("lines")
        if isinstance(lines_data, list) and lines_data:
            m.lines = [LineEntry.from_dict(ln) for ln in lines_data]

        return m



# Lazy getter for MODE_REGISTRY to avoid import-time circular dependency.
# MODE_REGISTRY is populated by load_modes() in CherryAI.py at startup,
# but mainhelper.py is imported early before that happens. This function
# fetches it on-demand from the modi module namespace.
def _get_mode_registry() -> Dict[str, Any]:
    """Lazily fetch MODE_REGISTRY from modi module after load_modes() is called."""
    try:
        from ..modi import MODE_REGISTRY
        return cast(Dict[str, Any], MODE_REGISTRY)
    except Exception:
        try:
            from CherryAI.modi import MODE_REGISTRY
            return cast(Dict[str, Any], MODE_REGISTRY)
        except Exception:
            return {}

from .modehelper import EMPTY_LINE_PLACEHOLDER

# models moved into this file; callers should import Operation/Manifest from here


def now_iso() -> str:
    # Use timezone-aware UTC to avoid deprecation of utcnow()
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def setup_logger(log_path: Path, logs_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Configure and return the application logger.

    Uses force=True so subsequent calls reconfigure handlers per run, ensuring the
    log file path updates when processing different inputs.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / log_path.name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            # Open in write mode to avoid unbounded log growth across runs
            logging.FileHandler(log_path, mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    return logging.getLogger()


def log_summary(message: str) -> None:
    """Log a concise end-of-run summary line."""
    logging.info(message)


def log_warning(message: str) -> None:
    logging.warning(message)


def log_error(message: str) -> None:
    logging.error(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="")


def derive_output_path(input_path: Path, suffix: str = "_translated") -> Path:
    """Return a non-destructive output path with the given suffix.

    Pattern: filename{suffix}.ext in the same directory as input.
    """
    stem = input_path.stem
    ext = input_path.suffix
    output = input_path.parent / f"{stem}{suffix}{ext}"
    return output


def detect_delimiter(path: Path) -> str:
    if path.suffix.lower() == ".tsv":
        return "\t"
    return ","


# ----------------------------- State persistence & UI helpers ------------------------- #
def _resolve_config_file() -> Path:
    """Attempt to resolve a canonical CONFIG_FILE Path from the CherryAI module.

    Falls back to a sensible local path if the CherryAI module cannot be
    imported.
    """
    try:
        import importlib

        for candidate in (
            "CherryAI.CherryAI",
            "CherryAI.CherryAI",
            "CherryAI.CherryAI",
            "CherryAI",
            "CherryAI",
        ):
            try:
                mod = importlib.import_module(candidate)
            except Exception:
                mod = None
            if mod is not None and hasattr(mod, "CONFIG_FILE"):
                cf = getattr(mod, "CONFIG_FILE")
                try:
                    return Path(cf)
                except Exception:
                    pass
    except Exception:
        pass
    # Fallback: place config next to the package root (two levels up from this file)
    return Path(__file__).resolve().parent.parent / "CherryAI.ini"


def load_app_state(config_file: Optional[Path] = None) -> Dict[str, Any]:
    """Load a JSON-serializable application UI state from an INI config.

    The state is stored in the [ui] section under the `state` key as JSON.
    Returns an empty dict on any error.
    """
    import configparser

    if config_file is None:
        config_file = _resolve_config_file()
    config = configparser.ConfigParser()
    if config_file.exists():
        try:
            config.read(config_file, encoding="utf-8")
        except Exception:
            return {}
    if "ui" in config and "state" in config["ui"]:
        raw = config["ui"].get("state", "{}")
        try:
            return cast(Dict[str, Any], json.loads(raw))
        except Exception:
            return {}
    return {}


def save_app_state(state: Dict[str, Any], config_file: Optional[Path] = None) -> None:
    """Save a JSON-serializable application state into the INI config.

    Keeps other INI sections intact.
    """
    import configparser

    if config_file is None:
        config_file = _resolve_config_file()
    config = configparser.ConfigParser()
    if config_file.exists():
        try:
            config.read(config_file, encoding="utf-8")
        except Exception:
            config = configparser.ConfigParser()
    if "ui" not in config:
        config["ui"] = {}
    try:
        config["ui"]["state"] = json.dumps(state, ensure_ascii=False)
        with config_file.open("w", encoding="utf-8", newline="") as fh:
            config.write(fh)
    except Exception:
        # best-effort: ignore write failures
        return


def select_input_files(initialdir: Optional[str] = None, filetypes: Optional[List[Tuple[str, str]]] = None) -> List[Path]:
    """Open a file-selection dialog allowing multiple files and return their Paths.

    If no initialdir is provided the function will try to use the last saved
    selection's parent directory (if available).
    """
    import tkinter as _tk
    from tkinter import filedialog as _filedialog

    # Use a transient root so the dialog does not leave an extra window.
    root = _tk.Tk()
    root.withdraw()
    state = load_app_state()
    if not initialdir:
        last = state.get("last_files")
        if isinstance(last, list) and last:
            initialdir = str(Path(last[0]).parent)
    if not filetypes:
        filetypes = [("All files", "*.*")]
    paths = _filedialog.askopenfilenames(title="Select input files", initialdir=(initialdir or str(Path.cwd())), filetypes=filetypes)
    root.destroy()
    return [Path(p) for p in paths]


def remember_last_selection(paths: List[Path], extra_state: Optional[Dict[str, Any]] = None) -> None:
    """Persist the provided list of input file paths as the last selection.

    Any extra_state mapping will be merged into the saved state.
    """
    state = load_app_state()
    state["last_files"] = [str(p) for p in paths]
    if extra_state:
        state.update(extra_state)
    save_app_state(state)


def read_table(path: Path) -> Tuple[List[List[str]], str]:
    delim = detect_delimiter(path)
    rows: List[List[str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        for row in reader:
            rows.append(list(row))
    return rows, delim


def write_table(path: Path, rows: List[List[str]], delim: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=delim)
        writer.writerows(rows)


# ------------------------------- Reporting --------------------------------- #

def write_failure_report(logs_dir: Path, basename: str, line_no_1based: int, lines: List[str]) -> Optional[Path]:
    """Write a dedicated failure report file into logs_dir.

    Returns the path on success, or None on error.
    """
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        path = logs_dir / f"{basename}.dryrun.failure.L{line_no_1based}.log"
        path.write_text("\n".join(lines), encoding="utf-8")
        logging.warning("Dry Run failure report written: %s", path)
        return path
    except Exception as exc:
        logging.error("Failed to write Dry Run failure report: %s", exc)
        return None


def summarize_unrestored_placeholders(per_line_occurs: Dict[str, List[str]]) -> None:
    """Emit one-line SUMMARY logs for leftover placeholders.

    per_line_occurs: mapping token -> list of textual occurrences like '12' or '12(3)'
    """
    for tok, occurs in per_line_occurs.items():
        if occurs:
            logging.warning("SUMMARY: Unrestored placeholder %s at lines: %s", tok, ", ".join(occurs))
        else:
            logging.info("SUMMARY: No occurrences of placeholder %s", tok)


# --------------------------------- JSON/XLSX -------------------------------- #

def read_json_pairs(path: Path) -> List[Tuple[str, str]]:
    data = json.loads(read_text(path))
    pairs: List[Tuple[str, str]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, list) and len(item) >= 2:
                pairs.append((str(item[0]), str(item[1])))
            elif isinstance(item, dict):
                if "original" in item and "translated" in item:
                    pairs.append((str(item["original"]), str(item["translated"])))
    return pairs


def write_json_pairs(path: Path, pairs: List[Tuple[str, str]]) -> None:
    data = [[o, t] for o, t in pairs]
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def read_xlsx_pairs(path: Path) -> Optional[List[Tuple[str, str]]]:
    try:
        import openpyxl
    except Exception as exc:  # pragma: no cover - import failure path
        logging.error("openpyxl not installed: %s", exc)
        return None
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    if ws is None:
        return None
    pairs: List[Tuple[str, str]] = []
    for row in ws.iter_rows(values_only=True):
        o = row[0] if len(row) >= 1 else None
        t = row[1] if len(row) >= 2 else None
        if o is None and t is None:
            continue
        pairs.append((str(o or ""), str(t or "")))
    return pairs


def write_xlsx_pairs(path: Path, pairs: List[Tuple[str, str]]) -> None:
    try:
        import openpyxl
    except Exception as exc:  # pragma: no cover - import failure path
        logging.error("openpyxl not installed: %s", exc)
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    if ws is None:
        # Should not happen with new workbook, but for type safety
        ws = wb.create_sheet()
    for o, t in pairs:
        ws.append([o, t])
    wb.save(path)


# -------------------------- Orchestrator (Processor) -------------------------- #

# Public constants that modes expect to find on the processor instance
# Use double-underscore sentinel for clarity and to avoid accidental collisions.
# Keep backward-compatibility checks for the legacy single-leading-underscore
# marker when restoring post-phase placeholders.
DEDUP_PLACEHOLDER = "__DEDUP__"
DEDUP_THRESHOLD_DEFAULT = 1


class Processor:
    """Thin orchestrator that delegates Pre/Post work to registered modes.

    - Applies apply_pre/apply_post in priority order
    - Records minimal runtime snapshots for diagnostics/dry-run
    - Exposes placeholders/constants used by some modes
    - Provides optional per-line tracing hook used by the GUI when enabled
    """

    # also expose on the class for convenient attribute access in modes
    DEDUP_PLACEHOLDER = DEDUP_PLACEHOLDER
    DEDUP_THRESHOLD_DEFAULT = DEDUP_THRESHOLD_DEFAULT

    def __init__(self, ops: List[Operation], manifest: Manifest) -> None:
        self.ops = ops
        self.manifest = manifest
        self.trace_enabled: bool = False
        # Optional progress callback: callable(phase:str, current:int, total:int, label:str)
        self.progress_callback: Optional[Callable[[str, int, int, str], None]] = None

    def trace_op(self, line_idx: int, phase: str, mode: str, detail: str) -> None:
        """Append a compact trace entry for a given line into manifest.mappings['op_trace']."""
        if not getattr(self, "trace_enabled", False):
            return
        try:
            traces: List[Dict[str, Any]] = self.manifest.mappings.setdefault("op_trace", [])
            rec = next((r for r in traces if int(r.get("line", -1)) == line_idx), None)
            entry = f"{phase}: {mode} - {detail}"
            if rec:
                rec.setdefault("events", []).append(entry)
            else:
                traces.append({"line": int(line_idx), "events": [entry]})
        except Exception:
            # tracing must never break processing
            pass

    def process_pre(self, text: str) -> Tuple[str, Dict[str, int]]:
        stats: Dict[str, int] = {}
        lines = text.splitlines()
        # Set/refresh the active doc id at the very start of Pre based on the
        # current original lines, so all per-doc mappings are correctly keyed
        # even when dedup is disabled.
        try:
            from .dedup import _ensure_doc_id
            _ensure_doc_id(self, lines)
        except Exception:
            pass
        # runtime snapshot and simple metadata used by post validation
        # Resolve and set the active doc id for this Post run conservatively.
        # If metadata already holds a doc id that exists in per-doc mappings,
        # keep it. Only attempt heuristic selection when missing or unknown.
        # Normalize to a well-typed optional callable
        select_active_doc_id: Optional[Callable[[Any, List[str]], Optional[str]]] = None
        try:
            from .dedup import select_active_doc_id as _sel
            select_active_doc_id = cast(Optional[Callable[[Any, List[str]], Optional[str]]], _sel)
        except Exception:
            select_active_doc_id = None
        try:
            current_did: Optional[str] = None
            try:
                cur_raw = self.manifest.metadata.get("current_doc_id")
                current_did = str(cur_raw) if cur_raw is not None else None
            except Exception:
                current_did = None
            maps = getattr(self.manifest, "mappings", {})
            known_docs: set[str] = set()
            try:
                per_doc = maps.get("dedup_by_doc", {}) or {}
                if isinstance(per_doc, dict):
                    known_docs.update(per_doc.keys())
            except Exception:
                pass
            try:
                aggr_by_doc = maps.get("aggressive_numbers_by_doc", {}) or {}
                if isinstance(aggr_by_doc, dict):
                    known_docs.update(aggr_by_doc.keys())
            except Exception:
                pass
            need_select = not current_did or (current_did not in known_docs)
            if need_select and select_active_doc_id is not None:
                did = select_active_doc_id(self, lines)
                if did:
                    self.manifest.metadata["current_doc_id"] = did
        except Exception:
            # Best-effort: if selection fails, proceed with existing metadata
            pass
        try:
            self.manifest.metadata["pre_line_count"] = len(lines)
        except Exception:
            pass
        setattr(self.manifest, "_pre_lines_runtime", list(lines))
        # Persist the original lines into mappings so saved manifests always
        # contain the full original text even if callers don't serialize
        # runtime attrs separately.
        try:
            maps = getattr(self.manifest, "mappings", None)
            if isinstance(maps, dict):
                # store under a stable key; use list(copy) to avoid mutation
                maps.setdefault("original_lines", list(lines))
                # Record enabled operations order up-front for manifest readability
                if "enabled_operations" not in maps:
                    maps["enabled_operations"] = [op.modus for op in self.ops]
        except Exception:
            pass

        # Ensure per-doc containers exist for multi-file manifests; do not clear
        # global mappings so one manifest can hold several files' maps.
        try:
            maps = getattr(self.manifest, "mappings", None)
            if isinstance(maps, dict):
                maps.setdefault("dedup_by_doc", {})
                maps.setdefault("aggressive_numbers_by_doc", {})
                maps.setdefault("doc_ids", [])
        except Exception:
            pass

        # Ensure deduplication runs first in the Pre phase. Dedup is the
        # single source of truth for collapsing repeated lines and records
        # entries under manifest.mappings['dedup_lines'].
        try:
            # Resolve optional dedup function
            _dedup_func: Optional[Callable[[Any, List[str], int], int]] = None
            try:
                from .dedup import deduplicate_pre as _dp
                _dedup_func = _dp
            except Exception:
                _dedup_func = None
            # Read runtime config if present; fall back to class default
            cfg = (self.manifest.mappings.get("standard_mode_config") if isinstance(self.manifest.mappings, dict) else None) or {}
            do_dedup = bool(cfg.get("dedup_enabled", True))
            thresh = int(cfg.get("dedup_threshold", getattr(self, "DEDUP_THRESHOLD_DEFAULT", 1)))
            if do_dedup and _dedup_func is not None:
                try:
                    d_changes = _dedup_func(self, lines, thresh)
                    if d_changes:
                        stats["dedup_collapsed"] = stats.get("dedup_collapsed", 0) + d_changes
                except Exception:
                    logging.exception("Processor: deduplication (pre) failed")
        except Exception:
            # tolerate absence of the centralized dedup module
            pass

        # collect applicable pre modes with their priority and stable index order
        pre_ops: List[Tuple[int, int, Operation, Any]] = []
        for i, op in enumerate(self.ops):
            mod = _get_mode_registry().get(op.modus)
            if mod and hasattr(mod, "apply_pre"):
                prio = int(getattr(mod, "PRIORITY", 100))
                pre_ops.append((prio, i, op, mod))
        pre_ops.sort(key=lambda t: (t[0], t[1]))
        # Persist which operations will run in Pre phase (in order)
        try:
            maps = getattr(self.manifest, "mappings", None)
            if isinstance(maps, dict):
                maps["pre_applied_ops"] = [op.modus for _, _, op, _ in pre_ops]
        except Exception:
            pass

        for _, i, op, mod in pre_ops:
            label = f"op{i}:{op.modus}"
            # report progress if callback is set (will be populated by the GUI)
            try:
                # progress total will be computed below; defer reporting until after auto_pre computed
                pass
            except Exception:
                pass
            try:
                changes = int(mod.apply_pre(self, lines, op, stats))
                stats[label] = stats.get(label, 0) + changes
            except Exception as exc:
                logging.error("%s failed: %s", label, exc)

        # After all pre-mode plugins ran, let Standard Helpers run once to
        # perform global tasks (ellipsis normalization, empty-line safeguard,
        # optional dedup) and compress any adjacent PROT runs. We honor the
        # runtime config in manifest.mappings['standard_mode_config'].
        try:
            try:
                import importlib
                std_mod = importlib.import_module('CherryAI.modi.standard_mode')
            except Exception:
                std_mod = None
            if std_mod is not None:
                # Run the main Standard Helpers pre hook (records ellipsis/empty-line/dedup)
                try:
                    from_types = Operation
                except Exception:
                    from_types = None
                try:
                    dummy = Operation(modus=getattr(std_mod, "NAME", "Standard Helpers")) if 'Operation' in globals() else None
                except Exception:
                    dummy = None
                try:
                    if hasattr(std_mod, "apply_pre"):
                        ch = int(std_mod.apply_pre(self, lines, dummy, stats))
                        if ch:
                            stats["standard_pre"] = stats.get("standard_pre", 0) + ch
                except Exception:
                    # Tolerate failures in optional helpers
                    pass
                # Then compress adjacent PROT runs centrally if enabled
                try:
                    if hasattr(std_mod, "compress_all_prot_lines"):
                        cfg = std_mod.get_standard_config(self) if hasattr(std_mod, "get_standard_config") else {}
                        if cfg.get("prot_enabled", True):
                            added = std_mod.compress_all_prot_lines(self, lines)
                            if added:
                                stats["prot_compressed"] = stats.get("prot_compressed", 0) + added
                except Exception:
                    pass
        except Exception:
            pass

        # If this is a Dry Run, invoke any modes that opt-in to always-on Dry Run
        try:
            is_dry = bool(self.manifest.metadata.get("dry_run"))
        except Exception:
            is_dry = False
        if is_dry:
            # Collect all pre-capable modes that declare ALWAYS_ON_DRY_RUN
            auto_pre: List[Tuple[int, str, Any]] = []
            for name, mod in _get_mode_registry().items():
                try:
                    if getattr(mod, "ALWAYS_ON_DRY_RUN", False) and hasattr(mod, "apply_pre"):
                        prio = int(getattr(mod, "PRIORITY", 100))
                        auto_pre.append((prio, name, mod))
                except Exception:
                    continue
            auto_pre.sort(key=lambda t: (t[0], t[1]))
            # Compute total steps (explicit pre_ops + auto_pre)
            total_steps = len(pre_ops) + len(auto_pre)
            current_step = 0
            # Re-run the explicit pre_ops with progress reporting
            for _, i, op, mod in pre_ops:
                current_step += 1
                label = f"op{i}:{op.modus}"
                try:
                    if self.progress_callback:
                        try:
                            self.progress_callback("Pre", current_step, total_steps, label)
                        except Exception:
                            pass
                    changes = int(mod.apply_pre(self, lines, op, stats))
                    stats[label] = stats.get(label, 0) + changes
                except Exception as exc:
                    logging.error("%s failed: %s", label, exc)

            # Now run auto_pre with progress reporting
            for prio, name, mod in auto_pre:
                current_step += 1
                label = f"auto:{name}"
                try:
                    if self.progress_callback:
                        try:
                            self.progress_callback("Pre", current_step, total_steps, label)
                        except Exception:
                            pass
                    dummy = Operation(modus=name)
                    changes = int(mod.apply_pre(self, lines, dummy, stats))
                    if changes:
                        stats[label] = stats.get(label, 0) + changes
                except Exception as exc:
                    logging.error("%s failed: %s", label, exc)

        # Persist final Pre-TL lines state
        try:
            maps = getattr(self.manifest, "mappings", None)
            if isinstance(maps, dict):
                maps["pre_lines"] = list(lines)
        except Exception:
            pass
        return "\n".join(lines), stats
        
    # Note: pre_lines persistence handled below; dead code path retained

    def process_post(self, text: str) -> Tuple[str, Dict[str, int]]:
        stats: Dict[str, int] = {}
        lines = text.splitlines()
        setattr(self.manifest, "_post_in_lines_runtime", list(lines))
        # Persist Post-TL input lines for later diagnostics and manifest completeness
        try:
            maps = getattr(self.manifest, "mappings", None)
            if isinstance(maps, dict):
                maps["post_in_lines"] = list(lines)
                # Persist which operations will run in Post phase (in order)
                post_op_names: List[str] = []
                for op in self.ops:
                    mod = _get_mode_registry().get(op.modus)
                    if mod and hasattr(mod, "apply_post"):
                        post_op_names.append(op.modus)
                maps["post_applied_ops"] = post_op_names
        except Exception:
            pass

        # Before running plugin Post phases, attempt to decompress any PROT
        # clusters recorded during Pre. This ensures protect-mode placeholders
        # are expanded back into tolerant tokens early so plugins can restore
        # them in their post hooks.
        try:
            try:
                import importlib
                std_mod = importlib.import_module('CherryAI.modi.standard_mode')
            except Exception:
                std_mod = None
            if std_mod and hasattr(std_mod, "decompress_all_prot_lines"):
                try:
                    dec = std_mod.decompress_all_prot_lines(self, lines)
                    if dec:
                        stats["prot_decompressed"] = stats.get("prot_decompressed", 0) + dec
                except Exception:
                    pass
        except Exception:
            pass

        # Convergence loop: allow multiple passes for interdependent restorations
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            post_changes = 0
            
            # Collect applicable post modes with their priority and stable index order
            # Post phase uses REVERSED priority order (higher priority runs first)
            # to mirror the Pre phase: Pre (low→high), Post (high→low)
            post_ops: List[Tuple[int, int, Any, Any]] = []
            for i, op in enumerate(self.ops):
                mod = _get_mode_registry().get(op.modus)
                if mod and hasattr(mod, "apply_post"):
                    prio = int(getattr(mod, "PRIORITY", 100))
                    post_ops.append((prio, i, op, mod))
            # Sort by priority DESCENDING (negative prio), then by index for stability
            post_ops.sort(key=lambda t: (-t[0], t[1]))
            
            total_steps = len(post_ops)
            current_step = 0
            
            for prio, i, op, mod in post_ops:
                current_step += 1
                label = f"op{i}:{op.modus}"
                # Report progress for Post phase (include attempt in phase name)
                try:
                    if self.progress_callback:
                        try:
                            self.progress_callback(f"Post pass {attempt}", current_step, total_steps, label)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    c = int(mod.apply_post(self, lines, op, stats))
                    post_changes += c
                    if c:
                        stats[label] = stats.get(label, 0) + c
                except Exception as exc:
                    logging.error("%s (post) failed: %s", label, exc)

            # Prefer per-doc anchor records when available for accurate remaining count
            try:
                by_doc = self.manifest.mappings.get("anchor_lines_by_doc", {})
            except Exception:
                by_doc = {}
            anch_lines: List[Dict[str, Any]] = []
            if isinstance(by_doc, dict) and by_doc:
                try:
                    cur_id = str(self.manifest.metadata.get("current_doc_id")) if isinstance(self.manifest.metadata, dict) else None
                except Exception:
                    cur_id = None
                if cur_id and cur_id in by_doc:
                    anch_lines = by_doc.get(cur_id, []) or []
                elif len(by_doc) == 1:
                    anch_lines = next(iter(by_doc.values())) or []
            if not anch_lines:
                anch_lines = self.manifest.mappings.get("anchor_lines", [])
            remaining = sum(len(rec.get("removed", [])) for rec in anch_lines)
            logging.info("Post pass %d summary: plugins=%d; remaining anchors=%d", attempt, post_changes, remaining)
            if remaining == 0 or post_changes == 0:
                break

        # After plugins ran, invoke Standard Helpers post hook to perform
        # final restorations (ellipsis, empty-line placeholders, dedup, etc.).
        try:
            try:
                import importlib
                std_mod = importlib.import_module('CherryAI.modi.standard_mode')
            except Exception:
                std_mod = None
            if std_mod is not None and hasattr(std_mod, "apply_post"):
                try:
                    dummy = Operation(modus=getattr(std_mod, "NAME", "Standard Helpers"))
                except Exception:
                    dummy = None
                try:
                    ch = int(std_mod.apply_post(self, lines, dummy, stats))
                    if ch:
                        stats["standard_post"] = stats.get("standard_post", 0) + ch
                except Exception:
                    pass
        except Exception:
            pass

        # Ensure deduplication runs last in the Post phase. Call the centralized
        # dedup restore after all plugins and standard post work, but before
        # diagnostics so incident reporting sees the restored lines.
        try:
            try:
                from .dedup import deduplicate_post, migrate_legacy_dedup_inplace
            except Exception:
                deduplicate_post = None  # type: ignore[assignment]
                migrate_legacy_dedup_inplace = None  # type: ignore[assignment]
            if migrate_legacy_dedup_inplace is not None:
                try:
                    migrate_legacy_dedup_inplace(self.manifest)
                except Exception:
                    pass
            if deduplicate_post is not None:
                try:
                    d_restored = deduplicate_post(self, lines)
                    if d_restored:
                        stats["dedup_restored"] = stats.get("dedup_restored", 0) + d_restored
                except Exception:
                    logging.exception("Processor: deduplication (post) failed")
        except Exception:
            # tolerate absence of the centralized dedup module
            pass

        # Diagnostics summary: report any leftover placeholders and anchors
        custom_tokens: List[str] = []
        # Prefer per-doc custom placeholders when available
        try:
            by_doc = self.manifest.mappings.get("custom_placeholder_by_doc", {})
            cur_id = str(self.manifest.metadata.get("current_doc_id")) if isinstance(self.manifest.metadata, dict) else None
            recs: List[Dict[str, Any]] = []
            if isinstance(by_doc, dict) and by_doc:
                if cur_id and cur_id in by_doc:
                    recs = by_doc.get(cur_id, []) or []
                elif len(by_doc) == 1:
                    recs = next(iter(by_doc.values())) or []
            if not recs:
                recs = self.manifest.mappings.get("custom_placeholder_lines", [])
            for rec in recs or []:
                tok = rec.get("token")
                if tok and tok not in custom_tokens:
                    custom_tokens.append(tok)
        except Exception:
            pass
        placeholder_patterns: List[Tuple[str, re.Pattern[str]]] = []
        for tok in custom_tokens:
            placeholder_patterns.append((tok, re.compile(re.escape(tok))))
        placeholder_patterns.append(("__PROT__", re.compile(r"__\s*PROT\s*__")))

        # Build per-line incident map
        incidents: Dict[int, Dict[str, Any]] = {}

        # Placeholder occurrences
        for label_tok, pat in placeholder_patterns:
            for idx, line in enumerate(lines):
                m = list(pat.finditer(line))
                if m:
                    inc = incidents.setdefault(idx, {})
                    pals = inc.setdefault("placeholders", [])
                    pals.append((label_tok, len(m)))

        # Leftover anchors
        # Prefer per-doc anchors when available
        anch_lines = []
        try:
            by_doc = self.manifest.mappings.get("anchor_lines_by_doc", {})
            cur_id = str(self.manifest.metadata.get("current_doc_id")) if isinstance(self.manifest.metadata, dict) else None
            if isinstance(by_doc, dict) and by_doc:
                if cur_id and cur_id in by_doc:
                    anch_lines = by_doc.get(cur_id, []) or []
                elif len(by_doc) == 1:
                    anch_lines = next(iter(by_doc.values())) or []
        except Exception:
            anch_lines = []
        if not anch_lines:
            anch_lines = self.manifest.mappings.get("anchor_lines", [])
        for rec in anch_lines:
            line_idx = int(rec.get("line", -1))
            if line_idx >= 0 and rec.get("removed"):
                inc = incidents.setdefault(line_idx, {})
                inc["anchor_leftover"] = True
                inc["anchor_record"] = rec

        # Dedup/empty placeholders still present
        # Delegate normalization and token handling to the centralized dedup module
        dedup_set = set()
        _is_dedup_placeholder = None
        try:
            from .dedup import normalize_dedup_entries, is_dedup_placeholder
            entries = normalize_dedup_entries(self.manifest)
            dedup_set = {int(e.get("idx", -1)) for e in entries if isinstance(e, dict)}
            _is_dedup_placeholder = is_dedup_placeholder
        except Exception:
            # Fallback to a tolerant legacy path if helpers are unavailable
            raw_dedup = self.manifest.mappings.get("dedup_lines", [])
            try:
                for itm in raw_dedup or []:
                    if isinstance(itm, dict) and "idx" in itm:
                        dedup_set.add(int(itm.get("idx", -1)))
                    else:
                        try:
                            dedup_set.add(int(itm))
                        except Exception:
                            continue
            except Exception:
                dedup_set = set()
        empty_set = set(self.manifest.mappings.get("empty_lines", []))
        for idx in sorted(dedup_set):
            if 0 <= idx < len(lines):
                try:
                    is_ph = bool(_is_dedup_placeholder and _is_dedup_placeholder(lines[idx], self))
                except Exception:
                    is_ph = False
                if not _is_dedup_placeholder:
                    # Last-resort legacy token check
                    try:
                        sentinels = {getattr(self, "DEDUP_PLACEHOLDER", DEDUP_PLACEHOLDER), "_DEDUP__", "__DEDUP__"}
                    except Exception:
                        sentinels = {DEDUP_PLACEHOLDER, "_DEDUP__", "__DEDUP__"}
                    is_ph = lines[idx] in sentinels
                if is_ph:
                    inc = incidents.setdefault(idx, {})
                    inc["dedup"] = True
        for idx in sorted(empty_set):
            if 0 <= idx < len(lines) and lines[idx].strip() == EMPTY_LINE_PLACEHOLDER:
                inc = incidents.setdefault(idx, {})
                inc["empty"] = True

        # Validate line count matches pre
        pre_count = self.manifest.metadata.get("pre_line_count")
        line_count_ok = not isinstance(pre_count, int) or pre_count == len(lines)

        # Keep only real incidents
        def _is_real_incident(entry: Dict[str, Any]) -> bool:
            return bool(
                entry.get("placeholders") or entry.get("anchor_leftover") or entry.get("dedup") or entry.get("empty")
            )

        incidents = {i: e for i, e in incidents.items() if _is_real_incident(e)}

        # Build a mapping of line -> set(modes) from op_trace to attribute failures per-op
        traces_raw = self.manifest.mappings.get("op_trace", [])
        traces_list: List[Dict[str, Any]] = traces_raw if isinstance(traces_raw, list) else []
        line_to_modes: Dict[int, set[str]] = {}
        for rec in traces_list:
            try:
                line_idx = int(rec.get("line", -1))
            except Exception:
                continue
            if line_idx < 0:
                continue
            evs = rec.get("events", []) or []
            modes: set[str] = set()
            for ev in evs:
                try:
                    # Event format expected: "Phase: Mode - detail"
                    tail = ev.split(":", 1)[1]
                    mode_name = tail.split("-", 1)[0].strip()
                    modes.add(mode_name)
                except Exception:
                    continue
            if modes:
                line_to_modes.setdefault(line_idx, set()).update(modes)

        # Prepare before/after snapshots for comparison
        before_lines: List[str] = getattr(self.manifest, "_pre_lines_runtime", list(lines))
        after_lines: List[str] = getattr(self.manifest, "_post_out_lines_runtime", list(lines))
        # If _post_out_lines_runtime hasn't been set yet, use current lines
        if not after_lines:
            after_lines = list(lines)

        max_len = max(len(before_lines), len(after_lines))

        # Build manifest-sourced maps for placeholders and anchors
        cust_map: Dict[int, List[str]] = {}
        try:
            by_doc = self.manifest.mappings.get("custom_placeholder_by_doc", {})
            cur_id = str(self.manifest.metadata.get("current_doc_id")) if isinstance(self.manifest.metadata, dict) else None
            recs = []
            if isinstance(by_doc, dict) and by_doc:
                if cur_id and cur_id in by_doc:
                    recs = by_doc.get(cur_id, []) or []
                elif len(by_doc) == 1:
                    recs = next(iter(by_doc.values())) or []
            if not recs:
                recs = self.manifest.mappings.get("custom_placeholder_lines", [])
            for rec in recs or []:
                try:
                    ln = int(rec.get("line", -1))
                    vals_any = rec.get("values", []) or []
                    if ln >= 0:
                        cust_map.setdefault(ln, []).extend([str(v) for v in vals_any])
                except Exception:
                    continue
        except Exception:
            pass

        prot_map: Dict[int, List[str]] = {}
        try:
            by_doc = self.manifest.mappings.get("protected_lines_by_doc", {})
            cur_id = str(self.manifest.metadata.get("current_doc_id")) if isinstance(self.manifest.metadata, dict) else None
            recs = []
            if isinstance(by_doc, dict) and by_doc:
                if cur_id and cur_id in by_doc:
                    recs = by_doc.get(cur_id, []) or []
                elif len(by_doc) == 1:
                    recs = next(iter(by_doc.values())) or []
            if not recs:
                recs = self.manifest.mappings.get("protected_lines", [])
            for rec in recs or []:
                try:
                    ln = int(rec.get("line", -1))
                    vals_any = rec.get("values", []) or []
                    if ln >= 0:
                        prot_map.setdefault(ln, []).extend([str(v) for v in vals_any])
                except Exception:
                    continue
        except Exception:
            pass

        anchor_map: Dict[int, List[str]] = {}
        try:
            by_doc = self.manifest.mappings.get("anchor_lines_by_doc", {})
            cur_id = str(self.manifest.metadata.get("current_doc_id")) if isinstance(self.manifest.metadata, dict) else None
            recs = []
            if isinstance(by_doc, dict) and by_doc:
                if cur_id and cur_id in by_doc:
                    recs = by_doc.get(cur_id, []) or []
                elif len(by_doc) == 1:
                    recs = next(iter(by_doc.values())) or []
            if not recs:
                recs = self.manifest.mappings.get("anchor_lines", [])
            for rec in recs or []:
                try:
                    ln = int(rec.get("line", -1))
                    removed = rec.get("removed", []) or []
                    texts: List[str] = []
                    for itm in removed:
                        if isinstance(itm, dict):
                            t = itm.get("text")
                            if t:
                                texts.append(str(t))
                        elif isinstance(itm, str):
                            texts.append(itm)
                    if ln >= 0 and texts:
                        anchor_map.setdefault(ln, []).extend(texts)
                except Exception:
                    continue
        except Exception:
            pass

        # Compute before/after restored counts using manifest data where available
        before_ph_counts: Dict[int, int] = {}
        restored_ph_counts: Dict[int, int] = {}
        before_anchor_counts: Dict[int, int] = {}
        restored_anchor_counts: Dict[int, int] = {}
        for idx in range(max_len):
            b = before_lines[idx] if idx < len(before_lines) else ""
            a = after_lines[idx] if idx < len(after_lines) else ""
            # Placeholder values from custom placeholders and protected values
            vals: List[str] = []
            vals.extend(cust_map.get(idx, []))
            vals.extend(prot_map.get(idx, []))
            before_ph_counts[idx] = len(vals)
            restored = 0
            for v in vals:
                if v and v in a:
                    restored += 1
            restored_ph_counts[idx] = restored
            # Anchors
            removed_texts = anchor_map.get(idx, [])
            before_anchor_counts[idx] = len(removed_texts)
            restored_a = 0
            for t in removed_texts:
                if t and t in a:
                    restored_a += 1
            restored_anchor_counts[idx] = restored_a

        # Now compute failed counts (items removed at Pre but not restored at Post)
        failed_placeholders = sum((before_ph_counts.get(i, 0) - restored_ph_counts.get(i, 0)) for i in range(max_len))
        failed_anchors = sum((before_anchor_counts.get(i, 0) - restored_anchor_counts.get(i, 0)) for i in range(max_len))

        # For each configured op, collect lines where restoration failed and that op appears in the trace
        per_op_failures: Dict[str, List[str]] = {}
        for i, op in enumerate(self.ops):
            name = op.modus
            failed_lines: List[str] = []
            # Check all incident lines and attribute failures to ops that appear in the trace for that line
            for idx in sorted(incidents.keys()):
                ph_failed = before_ph_counts.get(idx, 0) > 0 and (before_ph_counts.get(idx, 0) - restored_ph_counts.get(idx, 0)) > 0
                anch_failed = before_anchor_counts.get(idx, 0) > 0 and (before_anchor_counts.get(idx, 0) - restored_anchor_counts.get(idx, 0)) > 0
                if not (ph_failed or anch_failed):
                    continue
                if name in line_to_modes.get(idx, set()):
                    # If dry run and sabotage info exists, append sabotage acts
                    try:
                        sab = self.manifest.mappings.get("sabotage_lines", {})
                        acts = sab.get(str(idx), []) if isinstance(sab, dict) else []
                        if acts:
                            failed_lines.append(f"{idx + 1}({';'.join(acts)})")
                        else:
                            failed_lines.append(str(idx + 1))
                    except Exception:
                        failed_lines.append(str(idx + 1))
            per_op_failures[f"op{i}:{name}"] = failed_lines

        # Always emit a final summary with counts and per-op lines
        # Determine whether any real failures exist using the computed failed counts
        has_failures = (failed_placeholders > 0) or (failed_anchors > 0) or not line_count_ok
        if not has_failures:
            logging.info(
                "SUMMARY: All restoration succeeded — no placeholders or anchors remain and line count matches pre (failed_placeholders=%d; failed_anchors=%d)",
                failed_placeholders,
                failed_anchors,
            )
        else:
            logging.info(
                "SUMMARY: Restoration completed with issues; failed_placeholders=%d; failed_anchors=%d",
                failed_placeholders,
                failed_anchors,
            )

        # Emit per-op lines (one line per op)
        for op_key, lines_failed in per_op_failures.items():
            if lines_failed:
                logging.info("%s restoration failed at lines: %s", op_key, ";".join(lines_failed))
            else:
                logging.info("%s restoration OK", op_key)

        setattr(self.manifest, "_post_out_lines_runtime", list(lines))
        # Persist final lines and initialize overwrite_lines if missing
        try:
            maps = getattr(self.manifest, "mappings", None)
            if isinstance(maps, dict):
                maps["final_lines"] = list(lines)
                # Initialize wordwrap_lines as a copy of final_lines if not present
                maps.setdefault("wordwrap_lines", list(lines))
                # Initialize overwrite_lines from wordwrap_lines if not present
                maps.setdefault("overwrite_lines", list(maps.get("wordwrap_lines", list(lines))))
        except Exception:
            pass
        # If there are no detected incidents and no computed failures, return early
        if not incidents and not has_failures:
            return "\n".join(lines), stats

        # Report first incident with minimal context
        # Choose a reasonable first incident index. Prefer a real incident if one exists,
        # otherwise derive the first index that shows a failed placeholder/anchor according
        # to the manifest-based counts. Fall back to 0 if nothing else is available.
        if incidents:
            first_idx = min(incidents.keys())
        else:
            first_idx = 0
            for idx in range(max_len):
                ph_left = (before_ph_counts.get(idx, 0) - restored_ph_counts.get(idx, 0))
                an_left = (before_anchor_counts.get(idx, 0) - restored_anchor_counts.get(idx, 0))
                if ph_left > 0 or an_left > 0:
                    first_idx = idx
                    break
        try:
            self.manifest.metadata["_first_incident"] = int(first_idx)
        except Exception:
            pass
        setattr(self.manifest, "_post_out_lines_runtime", list(lines))
        reasons: List[str] = []
        rec = incidents.get(first_idx, {})
        if rec.get("placeholders"):
            reasons.append("placeholders remain")
        if rec.get("anchor_leftover"):
            reasons.append("unrestored anchors")
        if rec.get("dedup"):
            reasons.append("dedup placeholder remains")
        if rec.get("empty"):
            reasons.append("empty-line placeholder remains")
        logging.info(
            "SUMMARY: Restoration completed with issues; first incident at line %d — %s",
            first_idx + 1,
            ", ".join(reasons) if reasons else "see logs",
        )
        return "\n".join(lines), stats

    def prepare_auto_translate(self, input_text: str) -> Dict[str, Any]:
        """
        Runs the Pre-processing phase and prepares the API batches.
        Returns a dictionary with:
        - 'pre_text': The pre-processed text
        - 'batches': The list of RequestBatch objects
        - 'estimation': Token counts and cost estimates
        - 'stats': Pre-processing stats
        """
        # Local imports to avoid circular dependency
        from .prompt_builder import PromptBuilder
        from .analysis import estimate_cost

        # 1. Run Pre-Processing
        pre_text, stats = self.process_pre(input_text)
        lines = pre_text.splitlines()

        # 2. Build Batches
        builder = PromptBuilder()
        # TODO: Get context markers from config or manifest?
        # For now, use defaults or empty
        batches = builder.build_batches(lines)

        # 3. Estimate Costs
        input_tokens = builder.estimate_tokens(batches)
        # Heuristic: Output tokens approx 1.5x input for JP->EN (conservative)
        output_tokens = int(input_tokens * 1.5) 
        cost_est = estimate_cost(input_tokens, output_tokens)

        return {
            "pre_text": pre_text,
            "batches": batches,
            "estimation": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_est.get("total_usd", 0.0)
            },
            "stats": stats
        }

    def execute_auto_translate(self, batches: List[Any], enable_api_log: bool = False, api_log_path: Optional[str] = None, source_filename: str = "unknown") -> Tuple[str, Dict[str, int]]:
        """
        Executes the API calls for the given batches and runs Post-processing.
        
        Args:
            batches: List of batches to translate.
            enable_api_log: If True, log all API requests and responses.
            api_log_path: Custom path for API log file.
            source_filename: Name of the source file being translated.
            
        Returns:
            Tuple of (final_text, stats_dict).
        """
        # Local imports
        from .api_client import APIClient

        client = APIClient(enable_api_log=enable_api_log, api_log_path=api_log_path)
        all_translated_lines = []
        
        # We need to reconstruct the full list of lines in order
        # The batches preserve order, so we can just append
        
        total_batches = len(batches)
        total_lines = sum(len(batch.lines) for batch in batches)
        
        # Write log header with statistics
        if enable_api_log:
            client.write_log_header(source_filename, total_lines, total_batches)
        
        for i, batch in enumerate(batches):
            if self.progress_callback:
                self.progress_callback("Translating", i + 1, total_batches, f"Batch {i+1}/{total_batches}")
            
            # Execute translation
            # batch.lines contains the text to translate
            # batch.system_prompt contains the context-aware prompt
            translated_chunk = client.translate_batch(batch.lines, system_prompt=batch.system_prompt)
            all_translated_lines.extend(translated_chunk)

        # Write log footer with final stats
        if enable_api_log:
            client.write_log_footer()

        # Join lines
        post_input_text = "\n".join(all_translated_lines)

        # Run Post-Processing
        final_text, stats = self.process_post(post_input_text)
        
        return final_text, stats

    def run_full_auto_translate(self, input_text: str, confirm_callback: Optional[Callable[[Dict[str, Any]], bool]]) -> Optional[str]:
        """
        Orchestrates the full Auto-Translate pipeline:
        1. Pre-Process
        2. Estimate & Confirm (via callback if provided)
        3. Translate (API)
        4. Post-Process
        """
        prep_result = self.prepare_auto_translate(input_text)
        
        if confirm_callback is not None:
            if not confirm_callback(prep_result["estimation"]):
                return None
        
        final_text, _ = self.execute_auto_translate(prep_result["batches"])
        return final_text
