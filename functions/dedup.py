from __future__ import annotations

import logging
from typing import List, Any, Dict, Optional, Set, Tuple
from pathlib import Path
import hashlib as _hashlib
import re as _re


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
    - Detect duplicates anywhere in the file using a normalized key (aggressive if enabled).
    - Keep the first occurrence; replace later occurrences with the dedup placeholder.
    - Record a mapping for each replaced index with 'source_idx' pointing to the kept line.
    - If aggressive mode is enabled, mask numbers only on the kept line (once) and
      record numbers per duplicate so Post can restore. Line count never changes.

    Notes:
    - The 'threshold' parameter is ignored in global mode; any later duplicate collapses.
    - Uses per-doc storage so a single manifest can hold multiple files' mappings.
    """
    # Per-doc storage so a single manifest can hold multiple files' mappings
    doc_id = _ensure_doc_id(processor, lines)
    per_doc = processor.manifest.mappings.setdefault("dedup_by_doc", {})
    if not isinstance(per_doc, dict):
        per_doc = {}
        processor.manifest.mappings["dedup_by_doc"] = per_doc
    dedup_entries: List[Any] = per_doc.setdefault(doc_id, [])

    aggressive_enabled = False
    aggr_by_doc = processor.manifest.mappings.setdefault("aggressive_numbers_by_doc", {})
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

    changes = 0
    placeholder = getattr(processor, "DEDUP_PLACEHOLDER", "__DEDUP__")

    # Precompute normalized forms so later mutations don't affect comparisons
    try:
        norms: List[str] = [aggressive_normalize_line(ln) if aggressive_enabled else str(ln) for ln in lines]
    except Exception:
        norms = [str(ln) for ln in lines]

    # Global anywhere deduplication
    first_by_key: Dict[str, int] = {}
    for i, key in enumerate(norms):
        raw = lines[i]
        if not raw.strip():
            continue
        head_idx = first_by_key.get(key)
        if head_idx is not None:
            # If this occurrence was already placeholdered, skip
            if raw == placeholder:
                continue
            # Ensure head carries kept-only numeric mask when aggressive is enabled
            if aggressive_enabled and AGGR_NUM_TOKEN not in lines[head_idx]:
                try:
                    mh, nh = aggressive_mask_line(lines[head_idx])
                    if nh and mh != lines[head_idx]:
                        lines[head_idx] = mh
                        aggr_map[str(head_idx)] = nh
                except Exception:
                    pass
            # Record numbers for this duplicate occurrence so Post can restore
            if aggressive_enabled:
                try:
                    md, nd = aggressive_mask_line(raw)
                    if nd:
                        aggr_map[str(i)] = nd
                except Exception:
                    pass
            # Placeholder current occurrence and record mapping to head
            if lines[i] != placeholder:
                orig_text = lines[i]
                lines[i] = placeholder
                try:
                    exists = any(((isinstance(e, dict) and int(e.get("idx", -1)) == i)) for e in dedup_entries)
                except Exception:
                    exists = False
                if not exists:
                    try:
                        dedup_entries.append({"idx": i, "text": orig_text, "source_idx": head_idx})
                    except Exception:
                        pass
                changes += 1
        else:
            first_by_key[key] = i

    return changes


def deduplicate_post(processor, lines: List[str]) -> int:
    """Expand placeholder entries recorded in manifest.mappings['dedup_lines'].

    Restores placeholders using priority:
      1) If entry has 'source_idx' and that current line is non-placeholder, copy it.
      2) Nearest previous non-placeholder line in current `lines`.
      3) Recorded original text in the entry.
    Returns count of expanded replacements.
    """
    # Prefer per-doc mappings when available. If current_doc_id is missing or
    # doesn't match any stored doc, heuristically pick the best matching doc by
    # counting how many recorded indices are placeholders in current lines.
    doc_id = None
    try:
        doc_id = str(processor.manifest.metadata.get("current_doc_id"))
    except Exception:
        doc_id = None
    per_doc = processor.manifest.mappings.get("dedup_by_doc", {})
    raw: List[Any] = []
    chosen_doc: Optional[str] = None
    if isinstance(per_doc, dict) and per_doc:
        # Prefer metadata doc id when available and present; only override if
        # another doc has a strictly higher placeholder score.
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

        # Compute scores
        scores: Dict[str, int] = {did: _score_doc(did) for did in per_doc.keys()}
        # Start with metadata doc if present
        candidate_doc = doc_id if (doc_id in per_doc) else None
        best_doc = max(scores.items(), key=lambda kv: kv[1])[0] if scores else None
        best_score = scores.get(best_doc, -1) if best_doc is not None else -1
        chosen = candidate_doc or best_doc

        # Override only if another doc has a strictly higher placeholder score
        if candidate_doc and best_doc and scores.get(best_doc, 0) > scores.get(candidate_doc, 0):
            chosen = best_doc

        # If all placeholder scores are zero and we still have no confident choice,
        # use aggressive-number indices as a weak signal, but still prefer metadata
        # doc when present in that map.
        if all(v == 0 for v in scores.values()):
            try:
                aggr_by_doc = processor.manifest.mappings.get("aggressive_numbers_by_doc", {})
            except Exception:
                aggr_by_doc = {}
            if isinstance(aggr_by_doc, dict) and aggr_by_doc:
                tokens_in_lines = {i for i, ln in enumerate(lines) if (AGGR_NUM_TOKEN in ln)}
                if candidate_doc and candidate_doc in aggr_by_doc:
                    chosen = candidate_doc
                else:
                    best_doc2 = None
                    best_key = (-1, -10)  # (overlap, -size_distance)
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
                        chosen = best_doc2

        # Final fallbacks
        if chosen is None and len(per_doc) == 1:
            chosen = next(iter(per_doc.keys()))
        if chosen is None and doc_id in per_doc:
            chosen = doc_id
        if chosen is None:
            chosen = next(iter(per_doc.keys()))

        chosen_doc = chosen
        raw = per_doc.get(chosen, []) or []
    if not raw:
        raw = processor.manifest.mappings.get("dedup_lines", [])
    entries: List[Dict[str, Any]] = []
    try:
        for itm in raw or []:
            if isinstance(itm, dict) and "idx" in itm:
                entries.append({
                    "idx": int(itm.get("idx", -1)),
                    "text": itm.get("text"),
                    "source_idx": itm.get("source_idx"),
                })
            else:
                try:
                    entries.append({"idx": int(itm)})
                except Exception:
                    continue
    except Exception:
        entries = []

    entries.sort(key=lambda x: int(x.get("idx", -1)))
    placeholder = getattr(processor, "DEDUP_PLACEHOLDER", "__DEDUP__")
    changes = 0
    for entry in entries:
        try:
            idx_val = entry.get("idx", -1)
            idx = int(idx_val) if idx_val is not None else -1
        except Exception:
            continue
        if idx < 0 or idx >= len(lines):
            continue
        cur = lines[idx]
        if not is_dedup_placeholder(cur, processor):
            continue
        orig_text = entry.get("text") if isinstance(entry, dict) else None
        src_idx = None
        try:
            src_idx_val = entry.get("source_idx") if isinstance(entry, dict) else None
            src_idx = int(src_idx_val) if src_idx_val is not None else None
        except Exception:
            src_idx = None
        if src_idx is not None and 0 <= src_idx < len(lines):
            cand = lines[src_idx]
            if cand.strip() and not is_dedup_placeholder(cand, processor):
                lines[idx] = cand
                changes += 1
                continue
        j = idx - 1
        prev = None
        while j >= 0:
            cand = lines[j]
            if cand.strip() and not is_dedup_placeholder(cand, processor):
                prev = cand
                break
            j -= 1
        if prev is not None:
            lines[idx] = prev
            changes += 1
            continue
        if orig_text:
            lines[idx] = orig_text
            changes += 1
    # After dedup restoration, restore aggressive-masked numbers if present
    try:
        aggr_by_doc = processor.manifest.mappings.get("aggressive_numbers_by_doc", {})
        if not isinstance(aggr_by_doc, dict) or not aggr_by_doc:
            # Legacy single-map fallback
            aggr_map = processor.manifest.mappings.get("aggressive_numbers", {})
            if isinstance(aggr_map, dict) and aggr_map:
                for k, nums in aggr_map.items():
                    try:
                        idx = int(k)
                    except Exception:
                        continue
                    if 0 <= idx < len(lines) and (AGGR_NUM_TOKEN in lines[idx]):
                        after = aggressive_restore_line(lines[idx], nums if isinstance(nums, list) else [])
                        if after != lines[idx]:
                            lines[idx] = after
                            changes += 1
            return changes

        # Determine token-bearing line indices in current lines
        token_lines = {i for i, ln in enumerate(lines) if (AGGR_NUM_TOKEN in ln)}
        if not token_lines:
            return changes

        # Build candidate docs and pick the best fit
        candidates = list(aggr_by_doc.items())
        # Prefer metadata/selected doc by ordering if it exists
        active_doc = chosen_doc or doc_id
        if active_doc and active_doc in aggr_by_doc:
            candidates.sort(key=lambda kv: 0 if kv[0] == active_doc else 1)

        def _metrics(did: str, amap: Dict[str, Any]) -> Tuple[int, bool, bool, int]:
            try:
                doc_indices = {int(k) for k in amap.keys() if str(k).isdigit()}
            except Exception:
                doc_indices = set()
            overlap = len(doc_indices & token_lines)
            exact_subset = doc_indices.issubset(token_lines)
            size_match = len(doc_indices) == len(token_lines)
            size_dist = abs(len(doc_indices) - len(token_lines))
            return overlap, exact_subset, size_match, size_dist

        # First, look for an exact subset + size match
        perfect: Optional[str] = None
        best_overlap = -1
        best_tie = 10**9
        best_any: Optional[str] = None
        for did, amap in candidates:
            if not isinstance(amap, dict):
                continue
            overlap, exact_subset, size_match, size_dist = _metrics(did, amap)
            if exact_subset and size_match:
                # prefer metadata/active doc first in ordering
                perfect = perfect or did
            # Track best-any by overlap then closest size
            if overlap > best_overlap or (overlap == best_overlap and size_dist < best_tie):
                best_overlap = overlap
                best_tie = size_dist
                best_any = did

        chosen_nums_doc = perfect or best_any
        if not chosen_nums_doc:
            return changes

        # Apply restoration only at indices that currently have tokens and that are present in the chosen map
        amap = aggr_by_doc.get(chosen_nums_doc, {})
        if isinstance(amap, dict):
            for k, nums in amap.items():
                try:
                    idx = int(k)
                except Exception:
                    continue
                if idx in token_lines and 0 <= idx < len(lines):
                    after = aggressive_restore_line(lines[idx], nums if isinstance(nums, list) else [])
                    if after != lines[idx]:
                        lines[idx] = after
                        changes += 1

        # Per-line fallback: if some <NUM> tokens remain, try other docs' maps
        # for those indices, preferring an exact count match to the number of
        # tokens present on that line.
        remaining = {i for i in token_lines if (AGGR_NUM_TOKEN in lines[i])}
        if remaining:
            for i in sorted(remaining):
                # count tokens in the current line
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
        # Tolerate restoration failures
        pass
    return changes

    # Fallback path: if no entries existed (or none applied), try a blind
    # expansion of any remaining dedup placeholders by copying the nearest
    # previous non-placeholder line. This prevents leftover placeholders when
    # per-doc mappings are missing or mismatched.
    try:
        if not entries:
            placeholder = getattr(processor, "DEDUP_PLACEHOLDER", "__DEDUP__")
            for i in range(len(lines)):
                cur = lines[i]
                if not is_dedup_placeholder(cur, processor):
                    continue
                # find nearest previous non-placeholder
                j = i - 1
                while j >= 0:
                    cand = lines[j]
                    if cand.strip() and not is_dedup_placeholder(cand, processor):
                        lines[i] = cand
                        changes += 1
                        break
                    j -= 1
    except Exception:
        pass


# ----------------------------- Public helper API ----------------------------- #

def placeholder_tokens(processor: Any) -> Set[str]:
    """Return the tolerated set of dedup placeholder tokens.

    Includes the canonical token and legacy variants for backward compatibility.
    """
    try:
        canon = getattr(processor, "DEDUP_PLACEHOLDER", "__DEDUP__")
    except Exception:
        canon = "__DEDUP__"
    return {canon, "__DEDUP__", "_DEDUP__"}


def is_dedup_placeholder(text: str, processor: Any) -> bool:
    """Check whether a given text equals a recognized dedup placeholder token."""
    toks = placeholder_tokens(processor)
    try:
        s = (text or "")
        if s in toks:
            return True
        # Also accept a tolerant form with optional spaces inside underscores: '__ DEDUP __'
        # and tolerate single-leading underscore legacy forms with spaces: '_ DEDUP __'
        # Case-insensitive match on the token core.
        try:
            return bool(_re.fullmatch(r"_+\s*DEDUP\s*_+", s, flags=_re.IGNORECASE))
        except Exception:
            return False
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


def migrate_legacy_dedup_inplace(manifest: Any) -> int:
    """Rewrite any legacy int-only dedup_lines entries into dict records in-place.

    Uses manifest.mappings['original_lines'] or the runtime snapshot '_pre_lines_runtime'
    (if present) to populate the 'text' field when possible. 'source_idx' is left as None
    because it cannot be reliably reconstructed post-hoc. Returns the number of migrated
    entries (i.e., entries that were converted to dicts).
    """
    try:
        mappings = manifest.mappings
    except Exception:
        return 0
    raw = mappings.get("dedup_lines", []) or []
    # fast path: already dict form
    if not raw or all(isinstance(x, dict) for x in raw):
        return 0
    # Find a best-effort source for the original text
    orig_lines: Optional[List[str]] = None
    try:
        ol = mappings.get("original_lines")
        if isinstance(ol, list):
            orig_lines = [str(x) for x in ol]
    except Exception:
        orig_lines = None
    if orig_lines is None:
        try:
            runtime = getattr(manifest, "_pre_lines_runtime", None)
            if isinstance(runtime, list):
                orig_lines = [str(x) for x in runtime]
        except Exception:
            orig_lines = None
    migrated: List[Any] = []
    changed = 0
    for itm in raw:
        if isinstance(itm, dict) and "idx" in itm:
            migrated.append(itm)
            continue
        try:
            idx = int(itm)
        except Exception:
            # Drop unparseable legacy items
            continue
        text = None
        if orig_lines is not None and 0 <= idx < len(orig_lines):
            text = orig_lines[idx]
        migrated.append({"idx": idx, "text": text, "source_idx": None})
        changed += 1
    mappings["dedup_lines"] = migrated
    return changed


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
    # Default False
    enabled = False
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "config.txt"
        if cfg_path.exists():
            txt = cfg_path.read_text(encoding="utf-8", errors="ignore")
            for raw in txt.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip().lower() == "aggressive_dedup":
                        val = v.strip().strip().lower()
                        enabled = val in {"true", "1", "yes", "y"}
                        break
    except Exception:
        enabled = False
    _AGGR_DEDUP_FLAG = enabled
    return enabled

