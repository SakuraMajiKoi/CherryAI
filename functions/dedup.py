from __future__ import annotations

import logging
from typing import List, Any, Dict, Optional, Set, Tuple
from pathlib import Path
import hashlib as _hashlib
import re as _re

# Maximum number of duplicate groups to process (by occurrence count).
MAX_DEDUP_GROUPS = 10


def _tag_dedup_line(processor: Any, idx: int, source_idx: int) -> None:
    """Add dedup tags (``dedup,D{source_idx}``) to a LineEntry.

    Creates the LineEntry if it doesn't exist.  Preserves existing tags
    that are not dedup-related.

    Args:
        processor: Processor with a manifest.
        idx: Index of the deduplicated line.
        source_idx: Index of the kept first-occurrence line.
    """
    try:
        le = processor.manifest.ensure_line(idx)
    except Exception:
        return
    existing = le.tags
    new_tags = ["dedup", f"D{source_idx}"]
    if existing is None or existing == "":
        le.tags = ",".join(new_tags)
    elif isinstance(existing, str):
        parts = [
            t for t in existing.split(",")
            if t and t != "dedup" and not (t.startswith("D") and t[1:].isdigit())
        ]
        parts.extend(new_tags)
        le.tags = ",".join(parts)
    else:
        # LineTags object or other — try flag-based approach
        try:
            if hasattr(existing, "add_flag"):
                existing.add_flag("dedup")
                existing.add_flag(f"D{source_idx}")
        except Exception:
            pass


def _read_dedup_tags(processor: Any, line_count: int) -> Dict[int, int]:
    """Read dedup source mappings from LineEntry tags.

    Scans ``processor.manifest.lines`` for entries tagged with
    ``dedup,D{source_idx}`` and returns a dict ``{dup_idx: source_idx}``.

    Args:
        processor: Processor with a manifest.
        line_count: Number of lines (for bounds checking).

    Returns:
        Dict mapping duplicate line indices to their source indices.
    """
    tag_sources: Dict[int, int] = {}
    try:
        for le in processor.manifest.lines:
            tags = le.tags
            if tags is None:
                continue
            if isinstance(tags, str):
                parts = tags.split(",")
                if "dedup" not in parts:
                    continue
                for t in parts:
                    if t.startswith("D") and t[1:].isdigit():
                        src = int(t[1:])
                        if 0 <= src < line_count:
                            tag_sources[le.idx] = src
                        break
            elif hasattr(tags, "has_flag"):
                if not tags.has_flag("dedup"):
                    continue
                for flag in getattr(tags, "flags", set()):
                    if flag.startswith("D") and flag[1:].isdigit():
                        src = int(flag[1:])
                        if 0 <= src < line_count:
                            tag_sources[le.idx] = src
                        break
    except Exception:
        pass
    return tag_sources


def _ensure_doc_id(processor: Any, lines: List[str]) -> str:
    """Return a stable doc id for the current file/session and persist it in metadata.

    Uses md5 of the pre-phase original lines as an identifier. Persist into
    manifest.metadata['current_doc_id'] and track all ids in mappings['doc_ids'].
    """
    try:
        mid = processor.manifest.metadata
    except Exception:
        mid = {}
    # Compute a stable md5 for the current content
    raw = "\n".join(lines)
    h = _hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()
    computed_id = f"md5:{h}"

    # If metadata has a different current_doc_id, update it; otherwise set it
    try:
        existing = str(mid.get("current_doc_id")) if mid else None
    except Exception:
        existing = None

    doc_id = computed_id
    try:
        if existing != computed_id:
            processor.manifest.metadata["current_doc_id"] = computed_id
    except Exception:
        pass
    # Track all known doc ids
    try:
        ids = processor.manifest.mappings.setdefault("doc_ids", [])
        if computed_id not in ids:
            ids.append(computed_id)
    except Exception:
        pass
    return doc_id


def deduplicate_pre(processor, lines: List[str], threshold: int) -> int:
    """Anywhere deduplication (global non-adjacent) with optional aggressive masking.

    Behavior:
    - Detect duplicates anywhere in the file using a normalized key
      (aggressive if enabled).
    - Group duplicates by normalized key and only process the top
      ``MAX_DEDUP_GROUPS`` groups (ranked by duplicate count).
    - Keep the first occurrence; replace later occurrences with the
      dedup placeholder.
    - Tag each replaced LineEntry with ``dedup,D{source_idx}`` so that
      ``deduplicate_post`` can restore without a separate mapping dict.
    - If aggressive mode is enabled, mask numbers only on the kept line
      (once) and record numbers per duplicate so Post can restore.
    - Line count never changes.

    Notes:
        The *threshold* parameter is ignored in global mode; any later
        duplicate collapses.  Only the top ``MAX_DEDUP_GROUPS`` groups
        (by duplicate count) are collapsed to keep the manifest lean.
    """
    doc_id = _ensure_doc_id(processor, lines)

    aggressive_enabled = False
    aggr_by_doc = processor.manifest.mappings.setdefault(
        "aggressive_numbers_by_doc", {},
    )
    if not isinstance(aggr_by_doc, dict):
        aggr_by_doc = {}
        processor.manifest.mappings["aggressive_numbers_by_doc"] = aggr_by_doc
    aggr_map: Dict[str, List[str]] = {}
    try:
        aggressive_enabled = _is_aggressive_enabled()
        if aggressive_enabled:
            aggr_map = aggr_by_doc.setdefault(doc_id, {})
    except Exception:
        aggressive_enabled = False
        aggr_map = {}

    placeholder = getattr(processor, "DEDUP_PLACEHOLDER", "__DEDUP__")

    # Precompute normalized forms so later mutations don't affect comparisons
    try:
        norms: List[str] = [
            aggressive_normalize_line(ln) if aggressive_enabled else str(ln)
            for ln in lines
        ]
    except Exception:
        norms = [str(ln) for ln in lines]

    # --- Pass 1: collect duplicate groups ---
    first_by_key: Dict[str, int] = {}
    # key → list of duplicate indices (excludes the head/first occurrence)
    dup_groups: Dict[str, List[int]] = {}

    for i, key in enumerate(norms):
        raw = lines[i]
        if not raw.strip() or raw == placeholder:
            continue
        if key in first_by_key:
            dup_groups.setdefault(key, []).append(i)
        else:
            first_by_key[key] = i

    # --- Rank groups by count descending, keep top MAX_DEDUP_GROUPS ---
    sorted_groups = sorted(
        dup_groups.items(),
        key=lambda kv: len(kv[1]),
        reverse=True,
    )
    top_groups = sorted_groups[:MAX_DEDUP_GROUPS]

    # --- Pass 2: process only the top groups ---
    changes = 0
    for key, dup_indices in top_groups:
        if not dup_indices:
            continue
        head_idx = first_by_key[key]

        # Aggressive masking on the head line (once per group)
        if aggressive_enabled and AGGR_NUM_TOKEN not in lines[head_idx]:
            try:
                mh, nh = aggressive_mask_line(lines[head_idx])
                if nh and mh != lines[head_idx]:
                    lines[head_idx] = mh
                    aggr_map[str(head_idx)] = nh
            except Exception:
                pass

        for i in dup_indices:
            # Record numbers for this duplicate before overwriting
            if aggressive_enabled:
                try:
                    _md, nd = aggressive_mask_line(lines[i])
                    if nd:
                        aggr_map[str(i)] = nd
                except Exception:
                    pass

            # Replace with placeholder
            lines[i] = placeholder
            changes += 1

            # Tag the LineEntry with dedup,D{head_idx}
            _tag_dedup_line(processor, i, head_idx)

    return changes


def deduplicate_post(processor, lines: List[str]) -> int:
    """Restore dedup placeholders using per-line tags or legacy mappings.

    Resolution priority per placeholder line:
      1) **Tag-based** — read ``D{source_idx}`` from the LineEntry's tags
         and copy the current content of ``lines[source_idx]``.
      2) **Legacy mapping** — fall back to ``dedup_by_doc`` / ``dedup_lines``
         entries for manifests created before per-line tagging.
      3) **Nearest previous** — copy the nearest previous non-placeholder
         line (last resort).

    After dedup restoration, aggressive-masked numbers are restored using
    ``aggressive_numbers_by_doc``.

    Returns:
        Count of restored placeholder lines.
    """
    placeholder = getattr(processor, "DEDUP_PLACEHOLDER", "__DEDUP__")
    changes = 0

    # --- Primary path: tag-based restoration ---
    tag_sources = _read_dedup_tags(processor, len(lines))
    if tag_sources:
        for idx in sorted(tag_sources):
            if idx < 0 or idx >= len(lines):
                continue
            if not is_dedup_placeholder(lines[idx], processor):
                continue
            src_idx = tag_sources[idx]
            if 0 <= src_idx < len(lines):
                cand = lines[src_idx]
                if cand.strip() and not is_dedup_placeholder(cand, processor):
                    lines[idx] = cand
                    changes += 1
                    continue
            # Fallback: nearest previous non-placeholder
            j = idx - 1
            while j >= 0:
                cand = lines[j]
                if cand.strip() and not is_dedup_placeholder(cand, processor):
                    lines[idx] = cand
                    changes += 1
                    break
                j -= 1

    # --- Restore aggressive-masked numbers ---
    changes += _restore_aggressive_numbers(processor, lines)

    return changes


def _restore_aggressive_numbers(
    processor: Any, lines: List[str],
) -> int:
    """Restore aggressive-masked numbers after dedup restoration."""
    changes = 0
    doc_id = None
    try:
        doc_id = str(processor.manifest.metadata.get("current_doc_id"))
    except Exception:
        pass

    try:
        aggr_by_doc = processor.manifest.mappings.get(
            "aggressive_numbers_by_doc", {},
        )
        if not isinstance(aggr_by_doc, dict) or not aggr_by_doc:
            aggr_map = processor.manifest.mappings.get(
                "aggressive_numbers", {},
            )
            if isinstance(aggr_map, dict) and aggr_map:
                for k, nums in aggr_map.items():
                    try:
                        idx = int(k)
                    except Exception:
                        continue
                    if 0 <= idx < len(lines) and (AGGR_NUM_TOKEN in lines[idx]):
                        after = aggressive_restore_line(
                            lines[idx],
                            nums if isinstance(nums, list) else [],
                        )
                        if after != lines[idx]:
                            lines[idx] = after
                            changes += 1
            return changes

        token_lines = {
            i for i, ln in enumerate(lines) if (AGGR_NUM_TOKEN in ln)
        }
        if not token_lines:
            return changes

        candidates = list(aggr_by_doc.items())
        if doc_id and doc_id in aggr_by_doc:
            candidates.sort(key=lambda kv: 0 if kv[0] == doc_id else 1)

        def _metrics(
            did: str, amap: Dict[str, Any],
        ) -> Tuple[int, bool, bool, int]:
            try:
                doc_indices = {
                    int(k) for k in amap.keys() if str(k).isdigit()
                }
            except Exception:
                doc_indices = set()
            overlap = len(doc_indices & token_lines)
            exact_subset = doc_indices.issubset(token_lines)
            size_match = len(doc_indices) == len(token_lines)
            size_dist = abs(len(doc_indices) - len(token_lines))
            return overlap, exact_subset, size_match, size_dist

        perfect: Optional[str] = None
        best_overlap = -1
        best_tie = 10**9
        best_any: Optional[str] = None
        for did, amap in candidates:
            if not isinstance(amap, dict):
                continue
            overlap, exact_subset, size_match, size_dist = _metrics(did, amap)
            if exact_subset and size_match:
                perfect = perfect or did
            if overlap > best_overlap or (
                overlap == best_overlap and size_dist < best_tie
            ):
                best_overlap = overlap
                best_tie = size_dist
                best_any = did

        chosen_nums_doc = perfect or best_any
        if not chosen_nums_doc:
            return changes

        amap = aggr_by_doc.get(chosen_nums_doc, {})
        if isinstance(amap, dict):
            for k, nums in amap.items():
                try:
                    idx = int(k)
                except Exception:
                    continue
                if idx in token_lines and 0 <= idx < len(lines):
                    after = aggressive_restore_line(
                        lines[idx],
                        nums if isinstance(nums, list) else [],
                    )
                    if after != lines[idx]:
                        lines[idx] = after
                        changes += 1

        remaining = {i for i in token_lines if (AGGR_NUM_TOKEN in lines[i])}
        if remaining:
            for i in sorted(remaining):
                token_count = lines[i].count(AGGR_NUM_TOKEN)
                best: Optional[Tuple[str, List[str]]] = None
                for did, mmap in aggr_by_doc.items():
                    if not isinstance(mmap, dict) or did == chosen_nums_doc:
                        continue
                    nums = mmap.get(str(i))
                    if not isinstance(nums, list):
                        continue
                    if len(nums) == token_count:
                        best = (did, nums)
                        break
                if best:
                    _, nums = best
                    after = aggressive_restore_line(lines[i], nums)
                    if after != lines[i]:
                        lines[i] = after
                        changes += 1
    except Exception:
        pass
    return changes


# ----------------------------- Public helper API ----------------------------- #

def placeholder_tokens(processor: Any) -> Set[str]:
    """Return the set of recognized dedup placeholder tokens."""
    try:
        canon = getattr(processor, "DEDUP_PLACEHOLDER", "__DEDUP__")
    except Exception:
        canon = "__DEDUP__"
    return {canon, "__DEDUP__"}


def is_dedup_placeholder(text: str, processor: Any) -> bool:
    """Check whether a given text equals a recognized dedup placeholder token."""
    toks = placeholder_tokens(processor)
    try:
        s = (text or "")
        return s in toks
    except Exception:
        return False


def select_active_doc_id(processor: Any, lines: List[str]) -> Optional[str]:
    """Best-effort selection of the active document id for current `lines`.

    Uses per-doc dedup entries to score how many recorded indices currently
    contain a dedup placeholder; falls back to aggressive-numbers indices when
    no placeholders are present. Returns the chosen doc id or None if no
    reasonable choice can be made.
    """
    try:
        per_doc = processor.manifest.mappings.get("dedup_by_doc", {})
    except Exception:
        per_doc = {}
    if not isinstance(per_doc, dict) or not per_doc:
        # Try aggressive numbers as the only signal
        try:
            aggr_by_doc = processor.manifest.mappings.get("aggressive_numbers_by_doc", {})
        except Exception:
            aggr_by_doc = {}
        if isinstance(aggr_by_doc, dict) and aggr_by_doc:
            best_doc = None
            best_score = -1
            for did, amap in aggr_by_doc.items():
                s = 0
                if isinstance(amap, dict):
                    for k in amap.keys():
                        try:
                            idx = int(k)
                        except Exception:
                            continue
                        if 0 <= idx < len(lines) and (AGGR_NUM_TOKEN in lines[idx]):
                            s += 1
                if s > best_score:
                    best_score = s
                    best_doc = did
            return best_doc
        return None

    toks = placeholder_tokens(processor)

    def _score_doc(did: str) -> int:
        score = 0
        try:
            entries = per_doc.get(did, []) or []
            for itm in entries:
                try:
                    if isinstance(itm, dict):
                        idx_val = itm.get("idx")
                        idx = int(idx_val) if idx_val is not None else -1
                    else:
                        idx = int(itm)
                except Exception:
                    continue
                if 0 <= idx < len(lines) and (lines[idx] in toks):
                    score += 1
        except Exception:
            score = 0
        return score

    best_doc = None
    best_score = -1
    for did in per_doc.keys():
        s = _score_doc(did)
        if s > best_score:
            best_score = s
            best_doc = did

    if best_score <= 0:
        # secondary heuristic: aggressive numbers with overlap + size tie-breaker
        try:
            aggr_by_doc = processor.manifest.mappings.get("aggressive_numbers_by_doc", {})
        except Exception:
            aggr_by_doc = {}
        if isinstance(aggr_by_doc, dict) and aggr_by_doc:
            tokens_in_lines = {i for i, ln in enumerate(lines) if (AGGR_NUM_TOKEN in ln)}
            best_doc2 = None
            best_key = (-1, -10)
            for did, amap in aggr_by_doc.items():
                if not isinstance(amap, dict):
                    continue
                try:
                    doc_indices = {int(k) for k in amap.keys() if str(k).isdigit()}
                except Exception:
                    doc_indices = set()
                overlap = len(doc_indices & tokens_in_lines)
                size_dist = abs(len(doc_indices) - len(tokens_in_lines))
                key = (overlap, -size_dist)
                if key > best_key:
                    best_key = key
                    best_doc2 = did
            if best_doc2 is not None:
                best_doc = best_doc2

    if best_doc is None and len(per_doc) == 1:
        return str(next(iter(per_doc.keys())))
    return best_doc


def normalize_dedup_entries(manifest: Any) -> List[Dict[str, Any]]:
    """Normalize manifest.mappings['dedup_lines'] into a sorted list of dict entries.

    Each entry is of the shape: {'idx': int, 'text': Optional[str], 'source_idx': Optional[int]}.
    Legacy int entries are converted with text/source_idx=None. Sorting is done by idx.
    If per-doc storage exists (mappings['dedup_by_doc']), flatten all entries across
    docs for diagnostics purposes.
    """
    try:
        maps = manifest.mappings or {}
    except Exception:
        maps = {}
    out: List[Dict[str, Any]] = []
    # Prefer per-doc structure if present; flatten for diagnostics
    try:
        per_doc = maps.get("dedup_by_doc", {}) or {}
        if isinstance(per_doc, dict) and per_doc:
            for _, raw in per_doc.items():
                for itm in raw or []:
                    if isinstance(itm, dict) and "idx" in itm:
                        try:
                            idx_val = itm.get("idx", -1)
                            src_idx_val = itm.get("source_idx")
                            out.append({
                                "idx": int(idx_val) if idx_val is not None else -1,
                                "text": itm.get("text"),
                                "source_idx": int(src_idx_val) if src_idx_val is not None else None,
                            })
                        except Exception:
                            continue
                    else:
                        try:
                            out.append({"idx": int(itm), "text": None, "source_idx": None})
                        except Exception:
                            continue
        else:
            raw = maps.get("dedup_lines", []) or []
            for itm in raw:
                if isinstance(itm, dict) and "idx" in itm:
                    try:
                        idx_val = itm.get("idx", -1)
                        src_idx_val = itm.get("source_idx")
                        out.append({
                            "idx": int(idx_val) if idx_val is not None else -1,
                            "text": itm.get("text"),
                            "source_idx": int(src_idx_val) if src_idx_val is not None else None,
                        })
                    except Exception:
                        continue
                else:
                    try:
                        out.append({"idx": int(itm), "text": None, "source_idx": None})
                    except Exception:
                        continue
    except Exception:
        pass
    out.sort(key=lambda x: int(x.get("idx", -1) or -1))
    return out


# ---------------------- Aggressive dedup (estimation helpers) ---------------------- #

# Canonical token used when masking numbers during aggressive normalization
AGGR_NUM_TOKEN = "<NUM>"


def aggressive_normalize_line(line: str) -> str:
    """Return a normalized form of a line suitable for aggressive deduplication.

    Operations:
    - Remove simple HTML tags like <br> (non-greedy tag removal)
    - Replace parenthesized numbers like (1) or （１） with AGGR_NUM_TOKEN
    - Replace remaining ASCII/fullwidth digits with AGGR_NUM_TOKEN
    - Collapse whitespace to a single space and trim
    """
    if not line:
        return ""
    s = str(line)
    # Remove HTML tags
    s = _re.sub(r"<[^>]+?>", "", s)
    # Replace numbers in ASCII or fullwidth parentheses
    s = _re.sub(r"[（\(]\s*[0-9０-９]+\s*[）\)]", f" {AGGR_NUM_TOKEN} ", s)
    # Replace remaining digits (ASCII + fullwidth)
    s = _re.sub(r"[0-9０-９]+", f" {AGGR_NUM_TOKEN} ", s)
    # Collapse whitespace
    s = _re.sub(r"\s+", " ", s).strip()
    return s


def aggressive_mask_line(line: str) -> Tuple[str, List[str]]:
    """Mask numbers in a line with AGGR_NUM_TOKEN and return (masked, numbers).

    Only digits and parenthesized digits are masked. The returned list preserves
    left-to-right order and can be used with aggressive_restore_line to reconstruct
    the original text by replacing successive AGGR_NUM_TOKEN occurrences.
    """
    if not line:
        return "", []
    s = str(line)
    nums: List[str] = []

    def _paren_repl(m: Any) -> str:
        nums.append(m.group(0))
        return AGGR_NUM_TOKEN

    def _num_repl(m: Any) -> str:
        nums.append(m.group(0))
        return AGGR_NUM_TOKEN

    # First capture parenthesized numbers, then standalone numbers
    s = _re.sub(r"[（\(]\s*[0-9０-９]+\s*[）\)]", _paren_repl, s)
    s = _re.sub(r"[0-9０-９]+", _num_repl, s)
    return s, nums


def aggressive_restore_line(masked: str, numbers: List[str]) -> str:
    """Restore a masked line by replacing each AGGR_NUM_TOKEN with next number.

    Excess tokens or numbers are ignored; missing numbers leave the token in place.
    """
    if not masked:
        return masked
    out = []
    i = 0
    parts = masked.split(AGGR_NUM_TOKEN)
    for idx, part in enumerate(parts):
        out.append(part)
        if idx < len(parts) - 1:
            if i < len(numbers):
                out.append(numbers[i])
                i += 1
            else:
                out.append(AGGR_NUM_TOKEN)
    return "".join(out)


# ---------------------- Config reader for aggressive dedup ---------------------- #

_AGGR_DEDUP_FLAG: Optional[bool] = None


def _is_aggressive_enabled() -> bool:
    global _AGGR_DEDUP_FLAG
    if _AGGR_DEDUP_FLAG is not None:
        return _AGGR_DEDUP_FLAG
    # Default False — read from user/CherryAI.ini [caching].aggressive_dedup
    # (Session 25: removed config/config.txt, migrated to CherryAI.ini)
    enabled = False
    try:
        import configparser
        ini_path = Path(__file__).resolve().parents[1] / "user" / "CherryAI.ini"
        if ini_path.exists():
            cfg = configparser.ConfigParser()
            cfg.read(ini_path, encoding="utf-8")
            if cfg.has_option("caching", "aggressive_dedup"):
                val = cfg.get("caching", "aggressive_dedup").strip().lower()
                enabled = val in {"true", "1", "yes", "y"}
    except Exception:
        enabled = False
    _AGGR_DEDUP_FLAG = enabled
    return enabled


def set_aggressive_dedup(enabled: bool) -> None:
    """Set the aggressive dedup flag at runtime.

    TASK 42.4: Called by mainhelper before dedup runs to honour the
    UI toggle / manifest config value.

    Args:
        enabled: Whether aggressive number deduplication is active.
    """
    global _AGGR_DEDUP_FLAG
    _AGGR_DEDUP_FLAG = enabled

