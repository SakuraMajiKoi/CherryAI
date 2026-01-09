from __future__ import annotations

"""
Anchor mode — workflow summary

Normal flow (Pre):
 - build an anchor spec from the UI 'Anchor Spec' (Input2) using
     `build_anchor_from_input2` which returns a spec list and an optional
     combined regex for more efficient matching.
 - compile the content pattern (Input1) as a regex (or the optimized
     combined form) and scan each line for matches.
 - for each line with matches, compute anchor references (no absolute
     indices): boundary anchors (line_start/line_end) and character-based
     anchors using equivalence maps. If there are fewer safe anchors than
     matches, the line is skipped (safe-only removal).
 - when safe, remove the matched text and record structured removal
     entries in `manifest.mappings['anchor_lines']` with enough metadata
     to attempt ordered restoration later.

Normal flow (Post):
 - load and deduplicate recorded `anchor_lines` and (if present)
     decompress any PROT clusters logged at Pre.
 - for each recorded removal, recompute concrete insertion indices on
     the current line using equivalence-aware position search and the
     stored anchor spec. Insert removed items in the recorded order.
 - if a robust anchor position cannot be found, the algorithm prefers
     conservative fallbacks (place at line start or try alternative anchors
     from the spec) and, only as a last resort, inserts a `__PROT__` token
     and records the original value under `protected_lines` so protect-mode
     restoration can later replace it.

Features:
 - Equivalence mapping for anchor characters (accepts full-width and
     smart variants) to increase resilience when translated text mutates
     punctuation characters.
 - Combined lookaround regex produced when Input2 specifies a single
     before/after anchor to speed removals and avoid mis-anchoring.
 - Per-line structured records to enable ordered and tolerant restoration.

Safeguards:
 - Safe-only Pre: skip removals when anchors are insufficient to avoid
     unsafe deletions.
 - Avoid anchoring into placeholders: Post computes placeholder spans
     (EMPTY_LINE_PLACEHOLDER, PROT tokens, and any custom placeholder
     tokens) and ignores positions that fall inside these spans.
 - Minimal invasiveness: the mode is silent (does not log). It uses
     `processor.trace_op` only when tracing is enabled for diagnostics.

Reporting behavior:
 - Persistent runtime data is stored in the manifest under
     `manifest.mappings` (keys used: 'anchor_lines', 'protected_lines',
     'prot_clusters'). These are later examined by the orchestrator
     (`Processor.process_post`) which emits summaries and incident
     diagnostics; the mode itself does not emit logs.
 - Tracing entries (if enabled) are emitted with `processor.trace_op`
     during Pre/Post to aid dry-run diagnostics.

Design rationale:
 - Localizing anchor helpers here keeps anchor-specific logic cohesive
     and minimizes cross-module coupling. The mode owns its full Pre/Post
     lifecycle while relying only on shared PROT/EMPTY helpers for token
     compression/decompression.
"""

import re
from typing import Any, Dict, List, Tuple, Optional

from CherryAI.functions.modehelper import (
    EMPTY_LINE_PLACEHOLDER,
    PROT_REGEX as _PROT_REGEX_PLACEHOLDER,
    ANCHOR_EQUIVS,
    get_equivs,
    find_all_equiv_positions,
)

# Local alias for PROT detection
PROT_REGEX = _PROT_REGEX_PLACEHOLDER


# Mode metadata
NAME = "Remove and Restore at Anchor"
PHASE = "Both"
PRIORITY = 15
USES_REGEX = True
INPUTS = ["Content Pattern", "Anchor Spec"]


# ─────────────────────────────────────────────────────────────────────────────
# v2.0 Manifest Compatibility Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _add_prepro_op(processor, idx: int, op_data: Dict[str, Any]) -> None:
    """Add a preprocessing operation to a line's prepro_ops (v2.0 pattern).

    Falls back to legacy mappings if Manifest.add_prepro_op is unavailable.
    """
    try:
        processor.manifest.add_prepro_op(idx, op_data)
    except AttributeError:
        # Fallback: Manifest doesn't support add_prepro_op (v1.0 compat)
        pass


def _get_prepro_ops(processor, idx: int, mode: str) -> List[Dict[str, Any]]:
    """Get preprocessing operations for a line filtered by mode (v2.0 pattern).

    Falls back to legacy mappings if Manifest.get_prepro_ops is unavailable.
    """
    try:
        return processor.manifest.get_prepro_ops(idx, mode) or []
    except AttributeError:
        return []


# ---------------------------- Anchor-local helpers ---------------------------- #

# Map of safe anchor chars (derive from shared equivalence map)
SAFE_ANCHOR_CHARS = list(ANCHOR_EQUIVS.keys())

# Local alias for character equivalence lookup
_get_equivs = get_equivs


def parse_anchor_spec(spec: str) -> List[Tuple[str, Optional[str]]]:
    parts = [p.strip() for p in spec.split(";") if p.strip()]
    result: List[Tuple[str, Optional[str]]] = []
    for p in parts:
        if p in ("line_start", "line_end"):
            result.append((p, None))
        elif p.startswith("after:"):
            result.append(("after", p[len("after:"):]))
        elif p.startswith("before:"):
            result.append(("before", p[len("before:"):]))
        elif p.startswith("around:"):
            result.append(("around", p[len("around:"):]))
    return result


def _escape_charclass_chars(chars: List[str]) -> str:
    parts: List[str] = []
    for ch in chars:
        if ch == "]":
            parts.append(r"\]")
        elif ch == "-":
            parts.append(r"\-")
        elif ch == "^":
            parts.append(r"\^")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def build_anchor_from_input2(content_pattern: str, in2: str) -> Tuple[List[Tuple[str, Optional[str]]], Optional[str]]:
    text = (in2 or "").strip()
    if not text:
        # Default spec: exclude unsafe punctuation used for ellipsis ('.').
        # User requested that ellipsis / '...' not be treated as safe anchors.
        spec_list_default: List[Tuple[str, Optional[str]]] = []
        for ch in SAFE_ANCHOR_CHARS:
            if ch == ".":
                continue  # skip dot to avoid anchoring to ellipsis punctuation
            spec_list_default.append(("before", ch))
            spec_list_default.append(("after", ch))
        return spec_list_default, None
    parts = [p.strip() for p in re.split(r"[;,]", text) if p.strip()]
    spec_list: List[Tuple[str, Optional[str]]] = []
    look_kind: Optional[str] = None
    look_char: Optional[str] = None
    for p in parts:
        low = p.lower()
        if low in ("line_start", "^"):
            spec_list.append(("line_start", None))
            continue
        if low in ("line_end", "$"):
            spec_list.append(("line_end", None))
            continue
        if low.startswith("before:") and len(p) > 7:
            ch = p.split(":", 1)[1]
            spec_list.append(("before", ch))
            if look_kind is None:
                look_kind, look_char = "before", ch
            continue
        if low.startswith("after:") and len(p) > 6:
            ch = p.split(":", 1)[1]
            spec_list.append(("after", ch))
            if look_kind is None:
                look_kind, look_char = "after", ch
            continue
        if low.startswith("around:") and len(p) > 7:
            ch = p.split(":", 1)[1]
            spec_list.append(("around", ch))
            continue
        for ch in p:
            spec_list.append(("around", ch))
    combined: Optional[str] = None
    if look_kind in ("before", "after") and look_char is not None and len([1 for k, _ in spec_list if k in ("before", "after")]) == 1:
        equivs = _get_equivs(look_char)
        char_class = _escape_charclass_chars(equivs)
        if look_kind == "before":
            combined = f"(?:{content_pattern})(?=[{char_class}])"
        elif look_kind == "after":
            combined = f"(?<=[{char_class}])(?:{content_pattern})"
    return spec_list, combined


def anchor_spec_list_to_string(spec_list: List[Tuple[str, Optional[str]]]) -> str:
    parts: List[str] = []
    for kind, char in spec_list:
        if kind in ("line_start", "line_end"):
            parts.append(kind)
        elif kind in ("before", "after", "around") and char is not None:
            parts.append(f"{kind}:{char}")
    return ";".join(parts)


def cluster_adjacent_removals(removed_items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group anchor removals that were originally adjacent or consecutive.
    
    Removals are considered part of the same cluster if their orig_span values
    are consecutive (one ends where the next begins) or nearly adjacent (separated
    by 0-2 characters, allowing for whitespace or punctuation between tokens).
    
    Returns a list of clusters, where each cluster is a list of removal dicts
    ordered by their original position (left-to-right).
    
    Example:
        Input: [{"text": "[l]", "orig_span": (27, 30), ...}, 
                {"text": "[r]", "orig_span": (30, 33), ...}]
        Output: [[{"text": "[l]", ...}, {"text": "[r]", ...}]]
        
    Rationale:
        When multiple anchor-tagged tokens are consecutive (e.g., "[l][r]" or 
        "[l] [r]"), they should be restored as a unit. If only one has a safe 
        anchor, the entire cluster can use that anchor for restoration.
    """
    if not removed_items:
        return []
    
    # Sort by original position (start of span)
    sorted_items = sorted(removed_items, key=lambda x: x.get("orig_span", (0, 0))[0])
    
    clusters: List[List[Dict[str, Any]]] = []
    current_cluster: List[Dict[str, Any]] = [sorted_items[0]]
    
    for i in range(1, len(sorted_items)):
        prev_span = current_cluster[-1].get("orig_span")
        curr_span = sorted_items[i].get("orig_span")
        
        if prev_span and curr_span:
            prev_end = prev_span[1]
            curr_start = curr_span[0]
            gap = curr_start - prev_end
            
            # Consider adjacent if gap is 0-2 characters
            # (allows for direct adjacency or minimal whitespace/punctuation)
            if 0 <= gap <= 2:
                current_cluster.append(sorted_items[i])
            else:
                # Start new cluster
                clusters.append(current_cluster)
                current_cluster = [sorted_items[i]]
        else:
            # Missing span info, start new cluster to be safe
            clusters.append(current_cluster)
            current_cluster = [sorted_items[i]]
    
    # Don't forget the last cluster
    if current_cluster:
        clusters.append(current_cluster)
    
    return clusters


# ------------------------------- Mode logic -------------------------------- #


def apply_pre(processor, lines: List[str], op, stats: Dict[str, int]) -> int:
    if not (op.in1 or "").strip():
        return 0
    anchor_spec = (op.in2 or "").strip()
    spec_list, combined = build_anchor_from_input2(op.in1, anchor_spec)
    pattern_str = combined or op.in1
    try:
        pattern = re.compile(pattern_str)
    except re.error:
        return 0
    # Prefer per-doc storage to avoid cross-file bleed when sharing a manifest
    anchor_lines: List[Dict[str, Any]] = processor.manifest.mappings.setdefault("anchor_lines", [])
    by_doc: Dict[str, List[Dict[str, Any]]] = processor.manifest.mappings.setdefault("anchor_lines_by_doc", {})
    # Get doc id from metadata (set by Processor.process_pre at the start)
    doc_id: Optional[str] = None
    try:
        mid = processor.manifest.metadata
        doc_id = str(mid.get("current_doc_id")) if isinstance(mid, dict) and mid.get("current_doc_id") else None
    except Exception:
        doc_id = None
    active_list: List[Dict[str, Any]]
    if doc_id:
        active_list = by_doc.setdefault(doc_id, [])
    else:
        active_list = anchor_lines
    changes = 0
    for idx, line in enumerate(lines):
        # Phase 1: Outside-in boundary stripping using line_start/line_end anchors.
        # Repeatedly remove matches at the very start or end of the line and record
        # them with explicit boundary anchors. This is safe because start/end are
        # conceptual anchors that are never removed, only moved.
        boundary_changes = 0
        iter_guard = 0
        while True:
            iter_guard += 1
            if iter_guard > 1000:
                break  # safety guard against pathological patterns
            matches = [m for m in pattern.finditer(line) if m.end() > m.start()]
            if not matches:
                break
            start_m = next((m for m in matches if m.start() == 0), None)
            # Treat trailing whitespace/newlines as outside the logical end-of-line for boundary detection
            logical_end = len(line.rstrip())
            end_m = next((m for m in matches if m.end() == logical_end), None)
            removed_any = False
            rec = next((r for r in active_list if r.get("line") == idx), None)
            if start_m is not None:
                # record start-bound match
                item = {
                    "anchor_kind": "line_start",
                    "anchor_char": None,
                    "anchor_occurrence": 0,
                    "text": start_m.group(0),
                    "orig_span": (start_m.start(), start_m.end()),
                    "anchor_inside_removed": False,
                }
                if rec and isinstance(rec.get("removed"), list):
                    rec["removed"].append(item)
                    # Force concise boundary spec for boundary-driven records
                    rec["anchor_spec"] = "line_start"
                else:
                    rec = {
                        "line": idx,
                        "removed": [item],
                        # Boundary-only intent: keep anchor_spec minimal for clarity
                        "anchor_spec": "line_start",
                        "doc_id": (doc_id or ""),
                        "placeholders": False,
                        "source": [{"mode": NAME, "content_pattern": pattern_str, "anchor_spec": anchor_spec}],
                    }
                    active_list.append(rec)
                # remove from start
                line = line[start_m.end():]
                removed_any = True
                boundary_changes += 1
                # continue to next iteration to re-scan after removal
                continue
            if end_m is not None:
                # record end-bound match; mark with original span so Post can sort by orig_span for stable order
                item = {
                    "anchor_kind": "line_end",
                    "anchor_char": None,
                    "anchor_occurrence": 0,
                    "text": end_m.group(0),
                    "orig_span": (end_m.start(), end_m.end()),
                    "anchor_inside_removed": False,
                }
                if rec and isinstance(rec.get("removed"), list):
                    rec["removed"].append(item)
                    # Force concise boundary spec for boundary-driven records
                    rec["anchor_spec"] = "line_end"
                else:
                    rec = {
                        "line": idx,
                        "removed": [item],
                        # Boundary-only intent: keep anchor_spec minimal for clarity
                        "anchor_spec": "line_end",
                        "doc_id": (doc_id or ""),
                        "placeholders": False,
                        "source": [{"mode": NAME, "content_pattern": pattern_str, "anchor_spec": anchor_spec}],
                    }
                    active_list.append(rec)
                # remove from end, preserving any trailing whitespace/newlines beyond logical end
                tail = line[logical_end:]
                line = line[:end_m.start()] + tail
                removed_any = True
                boundary_changes += 1
                continue
            if not removed_any:
                break

        if boundary_changes:
            # write back intermediate line state and account changes
            lines[idx] = line
            changes += boundary_changes
            # Re-order end-bound removals to preserve original left-to-right order.
            try:
                recs_for_line = [r for r in active_list if r.get("line") == idx]
                for _rec in recs_for_line:
                    if _rec.get("anchor_spec") == "line_end":
                        end_removed_items = _rec.get("removed") or []
                        # Only reorder if all are pure line_end anchors.
                        if end_removed_items and all(isinstance(it, dict) and it.get("anchor_kind") == "line_end" for it in end_removed_items):
                            # Sort by original span start ascending to reflect original left-to-right sequence.
                            try:
                                end_removed_items.sort(key=lambda it: (isinstance(it.get("orig_span"), tuple) and it.get("orig_span")[0]) or 0)
                            except Exception:
                                pass
                            _rec["removed"] = end_removed_items
                            if getattr(processor, "trace_enabled", False):
                                processor.trace_op(idx, "Pre", NAME, f"Reordered line_end cluster ({len(end_removed_items)} item(s)) to original order")
            except Exception:
                pass
            try:
                if getattr(processor, "trace_enabled", False):
                    processor.trace_op(idx, "Pre", NAME, f"{boundary_changes} boundary match(es): content={pattern_str!r}, anchor='line_start/line_end'")
            except Exception:
                pass

        # Phase 2: Interior removals using robust per-match anchor selection.
        matches = [m for m in pattern.finditer(line) if m.end() > m.start()]
        if not matches:
            continue

        def _is_unsafe_ellipsis_segment(pos: int) -> bool:
            # Treat any '.' as unsafe; also skip the single unicode ellipsis '…'.
            try:
                ch = line[pos]
            except Exception:
                return False
            return ch == '.' or ch == '\u2026'

        # Precompute character occurrence indices for all safe chars excluding '.' and ellipsis.
        safe_occurrences: Dict[str, List[int]] = {}
        for ch in SAFE_ANCHOR_CHARS:
            if ch == '.' or ch == '\u2026':
                continue
            poss = [p for (p, _actual) in find_all_equiv_positions(line, ch)]
            # Filter out positions that correspond to unsafe ellipsis characters (redundant for dot, but keep for future)
            poss = [p for p in poss if not _is_unsafe_ellipsis_segment(p)]
            if poss:
                safe_occurrences[ch] = poss

        assigned: List[Dict[str, Any]] = []
        for m in matches:
            ms, me = m.start(), m.end()
            chosen: Optional[Dict[str, Any]] = None
            # Find nearest preceding safe char occurrence
            preceding: List[Tuple[str, int, int]] = []  # (char, occurrence_index, position)
            following: List[Tuple[str, int, int]] = []
            for ch, poss in safe_occurrences.items():
                for occ_i, p in enumerate(poss):
                    if p < ms:
                        preceding.append((ch, occ_i, p))
                    elif p >= me:
                        following.append((ch, occ_i, p))
            # Sort preceding by distance descending (closest first after reversal later) but we just pick closest
            if preceding:
                preceding.sort(key=lambda t: ms - t[2])  # smallest distance first
            if following:
                following.sort(key=lambda t: t[2] - me)
            if preceding:
                ch, occ_i, pos = preceding[0]
                chosen = {
                    "anchor_kind": "after",  # insert after preceding character
                    "anchor_char": ch,
                    "anchor_occurrence": int(occ_i),
                    "anchor_inside_removed": False,
                }
            elif following:
                ch, occ_i, pos = following[0]
                chosen = {
                    "anchor_kind": "before",  # insert before following character
                    "anchor_char": ch,
                    "anchor_occurrence": int(occ_i),
                    "anchor_inside_removed": False,
                }
            else:
                # Boundary fallback disabled by request: log refusal and skip anchoring this match.
                try:
                    processor.trace_op(idx, "Pre", NAME, f"Boundary fallback refused (no safe anchor): match={m.group(0)!r}, span=({ms},{me})")
                except Exception:
                    pass
                # Skip adding this match to assigned; it will remain in the line (unsafe removal avoided).
                continue
            assigned.append({
                **chosen,
                "text": m.group(0),
                "orig_span": (ms, me),
            })

        # If we failed to assign any (should not happen), fallback to previous heuristic.
        if len(assigned) < len(matches):
            # Last-chance heuristic: treat simple bracket-literal patterns like '[r]' OR escaped '\[r\]' as
            # literal bracket tokens. The UI commonly passes escaped variants. We only accept strictly
            # alphanumeric inner text to avoid over-matching character classes. When detected, remove all
            # literal occurrences and record them anchored at line_start for deterministic restoration.
            simple_bracket = False
            inner: Optional[str] = None
            try:
                # Literal unescaped form: [r]
                if pattern_str.startswith("[") and pattern_str.endswith("]") and pattern_str.count("[") == 1 and pattern_str.count("]") == 1:
                    inner = pattern_str[1:-1]
                # Escaped form: \[r\]
                elif pattern_str.startswith(r"\[") and pattern_str.endswith(r"\]") and pattern_str.count(r"\[") == 1 and pattern_str.count(r"\]") == 1:
                    inner = pattern_str[2:-2]
                if inner and all(ch.isalnum() for ch in inner):
                    simple_bracket = True
            except Exception:
                inner = None
                simple_bracket = False
            if simple_bracket:
                # Build the literal token as it appears in the original line text. For escaped form we want
                # the unescaped text e.g. '[r]' so attempt both when searching.
                lit = f"[{inner}]" if inner else pattern_str
                occs = []
                start = 0
                while True:
                    j = line.find(lit, start)
                    if j == -1:
                        break
                    occs.append((j, j+len(lit)))
                    start = j + 1  # allow overlap
                if occs:
                    # Remove all occurrences left-to-right
                    new_line_parts = []
                    last = 0
                    removed_items_cluster: List[Dict[str, Any]] = []
                    for s_, e_ in occs:
                        new_line_parts.append(line[last:s_])
                        # Prefer positional restoration: mark as inside-anchored and
                        # supply orig_span. Use an 'around' anchor on '[' with a
                        # computed occurrence index as a secondary hint if positional
                        # restoration cannot be applied exactly post-translation.
                        try:
                            occ_idx = line[:s_].count("[")
                        except Exception:
                            occ_idx = 0
                        removed_items_cluster.append({
                            "anchor_kind": "around",
                            "anchor_char": "[",
                            "anchor_occurrence": int(occ_idx),
                            "text": line[s_:e_],
                            "orig_span": (s_, e_),
                            "anchor_inside_removed": True,
                        })
                        last = e_
                    new_line_parts.append(line[last:])
                    tolerant_new = "".join(new_line_parts)
                    if tolerant_new != line:
                        # Cluster adjacent removals for atomic restoration
                        clusters = cluster_adjacent_removals(removed_items_cluster)
                        for cluster_idx, cluster in enumerate(clusters):
                            for item in cluster:
                                item["cluster_id"] = cluster_idx
                                item["cluster_size"] = len(cluster)
                        
                        record = next((r for r in active_list if r.get("line") == idx), None)
                        if record and isinstance(record.get("removed"), list):
                            record["removed"].extend(removed_items_cluster)
                        else:
                            active_list.append({
                                "line": idx,
                                "removed": removed_items_cluster,
                                "anchor_spec": (anchor_spec if anchor_spec else anchor_spec_list_to_string(spec_list)),
                                "placeholders": False,
                                "source": [{"mode": NAME, "content_pattern": pattern_str, "anchor_spec": anchor_spec}],
                            })
                        lines[idx] = tolerant_new
                        changes += len(removed_items_cluster)
                        try:
                            if getattr(processor, "trace_enabled", False):
                                processor.trace_op(idx, "Pre", NAME, f"tolerant bracket removal {len(removed_items_cluster)} occurrence(s): {pattern_str!r}")
                        except Exception:
                            pass
                        continue  # proceed to next line
            # No heuristic triggered; skip interior removal
            continue
        # perform interior removal: replace all matches with empty string (using regex subn)
        new_line, c = pattern.subn(lambda _m: "", line)
        if c:
            # Cluster adjacent removals for atomic restoration
            clusters = cluster_adjacent_removals(assigned)
            for cluster_idx, cluster in enumerate(clusters):
                for item in cluster:
                    item["cluster_id"] = cluster_idx
                    item["cluster_size"] = len(cluster)
            
            record = next((r for r in active_list if r.get("line") == idx), None)
            if record and isinstance(record.get("removed"), list):
                record["removed"].extend(assigned)
            else:
                active_list.append({
                    "line": idx,
                    "removed": assigned,
                    "anchor_spec": (anchor_spec if anchor_spec else anchor_spec_list_to_string(spec_list)),
                    "placeholders": False,
                    "source": [{"mode": NAME, "content_pattern": pattern_str, "anchor_spec": anchor_spec}],
                })
            lines[idx] = new_line
            try:
                if getattr(processor, "trace_enabled", False):
                    processor.trace_op(idx, "Pre", NAME, f"{c} interior match(es): content={pattern_str!r}, anchor={anchor_spec!r}")
            except Exception:
                pass
            changes += c
    
    # v2.0: Write anchor data to prepro_ops for each affected line
    # This consolidates all anchor records to prepro_ops at the end
    for record in active_list:
        line_idx = record.get("line")
        if line_idx is None:
            continue
        removed = record.get("removed", [])
        if removed:
            _add_prepro_op(processor, line_idx, {
                "mode": NAME,
                "removed": removed,
                "anchor_spec": record.get("anchor_spec", ""),
            })
    
    return changes


def apply_post(processor, lines: List[str], op, stats: Dict[str, int]) -> int:
    """Restore items removed at Pre using recorded anchor references.

    Policy: recompute insertion positions from current line content using
    equivalences; prefer boundary anchors when specific anchors are unavailable;
    fall back to inserting a PROT token while recording the value for protected
    restore. The mode stays silent (no logging); diagnostics occur elsewhere.
    """
    changes = 0
    # Prefer per-doc records when available
    by_doc: Dict[str, List[Dict[str, Any]]] = processor.manifest.mappings.get("anchor_lines_by_doc", {})
    # Resolve or compute an active doc id for this Post run
    doc_id: Optional[str] = None
    try:
        mid = processor.manifest.metadata
        doc_id = str(mid.get("current_doc_id")) if isinstance(mid, dict) and mid.get("current_doc_id") else None
    except Exception:
        doc_id = None
    if not doc_id:
        # Try to compute from current Post lines to align with per-doc maps
        try:
            try:
                from CherryAI.functions.dedup import _ensure_doc_id
            except Exception:
                from CherryAI.functions.dedup import _ensure_doc_id
            doc_id = _ensure_doc_id(processor, lines)
        except Exception:
            doc_id = None

    anch_lines: List[Dict[str, Any]] = []
    if isinstance(by_doc, dict) and by_doc:
        if doc_id and doc_id in by_doc:
            anch_lines = by_doc.get(doc_id, []) or []
        elif len(by_doc) == 1:
            anch_lines = next(iter(by_doc.values())) or []
        else:
            # Flatten all per-doc entries; idx bounds checks will safely skip non-matching docs
            tmp: List[Dict[str, Any]] = []
            for _did, lst in by_doc.items():
                if isinstance(lst, list):
                    tmp.extend(lst)
            anch_lines = tmp
    if not anch_lines:
        anch_lines = processor.manifest.mappings.get("anchor_lines", []) or []
    
    # v2.0: Also collect from prepro_ops (primary storage)
    prepro_anch: List[Dict[str, Any]] = []
    for idx in range(len(lines)):
        ops = _get_prepro_ops(processor, idx, NAME)
        for op_data in ops:
            removed = op_data.get("removed", [])
            if removed:
                prepro_anch.append({
                    "line": idx,
                    "removed": removed,
                    "anchor_spec": op_data.get("anchor_spec", ""),
                    "source": [{"mode": NAME}],
                })
    
    # Prefer prepro_ops data if available, else use legacy mappings
    if prepro_anch:
        anch_lines = prepro_anch
    
    if not anch_lines:
        return 0

    # Deduplicate records per (line, pattern, spec, removed_texts)
    new_anch: List[Dict[str, Any]] = []
    seen: set = set()
    for rec in anch_lines:
        line_no = rec.get("line")
        sources = rec.get("source") or []
        content_pat = None
        anchor_spec = None
        for s in sources:
            try:
                if s.get("mode") == NAME:
                    content_pat = s.get("content_pattern")
                    anchor_spec = s.get("anchor_spec")
                    break
            except Exception:
                pass
        removed = rec.get("removed") or []
        removed_texts = []
        for it in removed:
            if isinstance(it, dict):
                removed_texts.append(it.get("text"))
            elif isinstance(it, str):
                removed_texts.append(it)
        fp = (int(line_no) if isinstance(line_no, int) else line_no, content_pat, anchor_spec, tuple(removed_texts))
        if fp in seen:
            continue
        seen.add(fp)
        new_anch.append(rec)
    anch_lines[:] = new_anch

    # Helper regex for tolerant PROT compression (detection only). Actual
    # compression/decompression and prot_clusters recording is performed by
    # the Standard Helpers module at the end of Pre and the start of Post.
    # NOTE: PROT compression and PROT-token handling removed from this Post
    # implementation. Per request, do not insert or write any __PROT__ tokens
    # during Post; instead record failures where restoration could not be
    # performed and skip insertion.

    residuals: List[Tuple[int, int]] = []

    # Group records by line so we can compute all insertions relative to the same base line
    recs_by_line: Dict[int, List[Dict[str, Any]]] = {}
    for rec in anch_lines:
        raw_line = rec.get("line")
        li: Optional[int]
        if isinstance(raw_line, int):
            li = raw_line
        elif isinstance(raw_line, str):
            try:
                li = int(raw_line)
            except Exception:
                li = None
        else:
            li = None
        if li is None:
            continue
        if 0 <= li < len(lines):
            recs_by_line.setdefault(li, []).append(rec)

    for idx, recs in sorted(recs_by_line.items()):
        line = lines[idx]

        # Compute placeholder spans to avoid anchoring onto placeholders
        placeholder_spans: List[Tuple[int, int]] = []
        for m in re.finditer(re.escape(EMPTY_LINE_PLACEHOLDER), line):
            placeholder_spans.append((m.start(), m.end()))
        # Also avoid anchoring onto PROT tokens (they'll be restored later by protect_code)
        try:
            for m in PROT_REGEX.finditer(line):
                placeholder_spans.append((m.start(), m.end()))
        except Exception:
            pass
        try:
            cust_tokens = set()
            for _r in processor.manifest.mappings.get("custom_placeholder_lines", []):
                _tok = _r.get("token")
                if _tok:
                    cust_tokens.add(str(_tok))
            for _tok in cust_tokens:
                for m in re.finditer(re.escape(_tok), line):
                    placeholder_spans.append((m.start(), m.end()))
        except Exception:
            pass

        def _inside_placeholder(pos: int) -> bool:
            for s, e in placeholder_spans:
                if s <= pos < e:
                    return True
            return False

        inserts: List[Tuple[int, str, int]] = []  # (position, value, seq)
        seq_counter = 0
        # Track remain items per record
        remain_by_rec: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(len(recs))}

        # Collect ALL removal items from all records for this line
        all_items: List[Dict[str, Any]] = []
        for rec in recs:
            removed = rec.get("removed", [])
            if removed and isinstance(removed[0], str):
                removed = [{"text": t, "orig_span": None, "anchor_kind": "line_start", "anchor_char": None, "anchor_occurrence": 0} for t in list(removed)]
                rec["removed"] = removed
            all_items.extend(removed)
        
        # Re-cluster all items together (across all records) to handle [l] and [r] from different operations
        if all_items:
            # Re-assign cluster IDs based on current line state
            clusters = cluster_adjacent_removals(all_items)
            for cluster_idx, cluster in enumerate(clusters):
                for item in cluster:
                    item["cluster_id"] = cluster_idx
                    item["cluster_size"] = len(cluster)

        # Helper: compute insertion for one item given its parent rec anchor_spec
        def compute_insert_for_item(item: Dict[str, Any], spec_text: str) -> Tuple[Optional[int], str]:
            kind = item.get("anchor_kind")
            base = item.get("anchor_char")
            try:
                occ = int(item.get("anchor_occurrence", 0))
            except Exception:
                occ = 0
            val = item.get("text", "")
            insert_pos: Optional[int] = None
            # Logical end-of-line index that ignores trailing whitespace/newlines
            logical_end = len(line.rstrip())
            # Positional hint first if marked inside-removed
            if item.get("anchor_inside_removed") and isinstance(item.get("orig_span"), tuple):
                try:
                    o_s, _o_e = item.get("orig_span")  # type: ignore[misc]
                    if isinstance(o_s, int) and 0 <= o_s <= len(line):
                        insert_pos = o_s
                except Exception:
                    insert_pos = None
            if insert_pos is None:
                if kind == "line_start":
                    insert_pos = 0
                elif kind == "line_end":
                    insert_pos = logical_end
                elif kind in ("before", "after", "around") and base:
                    occurs = [(p, a) for (p, a) in find_all_equiv_positions(line, str(base)) if not _inside_placeholder(p)]
                    if 0 <= occ < len(occurs):
                        pos_idx, actual = occurs[occ]
                        if kind == "before":
                            insert_pos = pos_idx
                        elif kind == "after":
                            insert_pos = pos_idx + len(actual)
                        else:
                            insert_pos = pos_idx
            if insert_pos is None:
                # Fallbacks using rec's spec
                try:
                    alt_specs = parse_anchor_spec(spec_text) if spec_text else []
                except Exception:
                    alt_specs = []
                if any(a[0] == "line_start" for a in alt_specs):
                    insert_pos = 0
                elif any(a[0] == "line_end" for a in alt_specs):
                    insert_pos = logical_end
                else:
                    for akind, ach in alt_specs:
                        if akind in ("line_start", "line_end"):
                            continue
                        if akind in ("before", "after", "around") and ach:
                            try:
                                occurs_alt = [(p, a) for (p, a) in find_all_equiv_positions(line, str(ach)) if not _inside_placeholder(p)]
                                if occurs_alt:
                                    pos_idx_alt, actual_alt = occurs_alt[0]
                                    if akind == "before":
                                        insert_pos = pos_idx_alt
                                    elif akind == "after":
                                        insert_pos = pos_idx_alt + len(actual_alt)
                                    else:
                                        insert_pos = pos_idx_alt
                                    break
                            except Exception:
                                pass
            if insert_pos is None and isinstance(item.get("orig_span"), tuple):
                try:
                    o_s, _o_e = item.get("orig_span")  # type: ignore[misc]
                    if isinstance(o_s, int):
                        insert_pos = max(0, min(len(line), o_s))
                except Exception:
                    pass
            return insert_pos, val

        # Iterate records and their items, handling clusters atomically
        for rec_idx, rec in enumerate(recs):
            removed = rec.get("removed", [])
            if removed and isinstance(removed[0], str):
                removed = [{"text": t, "orig_span": None, "anchor_kind": "line_start", "anchor_char": None, "anchor_occurrence": 0} for t in list(removed)]
                rec["removed"] = removed
            if not removed:
                continue
            spec_txt = rec.get("anchor_spec") or ""
            
            # Group items by cluster_id
            clusters_map: Dict[Optional[int], List[Dict[str, Any]]] = {}
            for item in removed:
                cid = item.get("cluster_id")
                clusters_map.setdefault(cid, []).append(item)
            
            # Process each cluster atomically
            for cluster_id, cluster_items in clusters_map.items():
                if cluster_id is None or len(cluster_items) == 1:
                    # Not a cluster or singleton - process individually
                    for item in cluster_items:
                        pos, value = compute_insert_for_item(item, spec_txt)
                        if pos is not None and not _inside_placeholder(pos):
                            inserts.append((pos, value, seq_counter))
                            seq_counter += 1
                        else:
                            failures = processor.manifest.mappings.setdefault("anchor_restore_failures", [])
                            failures.append(
                                {
                                    "line": idx,
                                    "value": item.get("text", ""),
                                    "anchor_kind": item.get("anchor_kind"),
                                    "anchor_char": item.get("anchor_char"),
                                    "anchor_occurrence": item.get("anchor_occurrence"),
                                    "source": {"mode": NAME},
                                }
                            )
                            remain_by_rec[rec_idx].append(item)
                            try:
                                if getattr(processor, "trace_enabled", False):
                                    processor.trace_op(idx, "Post", NAME, f"Restore failed: no insertion point for value={item.get('text')!r}, anchor_kind={item.get('anchor_kind')}, anchor_char={item.get('anchor_char')!r}")
                            except Exception:
                                pass
                else:
                    # Cluster: find the best anchor position among all members
                    cluster_positions: List[Tuple[Optional[int], Dict[str, Any]]] = []
                    for item in cluster_items:
                        pos, _ = compute_insert_for_item(item, spec_txt)
                        cluster_positions.append((pos, item))
                    
                    # Find the first valid (non-None, not inside placeholder) position
                    anchor_pos: Optional[int] = None
                    for pos, _ in cluster_positions:
                        if pos is not None and not _inside_placeholder(pos):
                            anchor_pos = pos
                            break
                    
                    if anchor_pos is not None:
                        # Restore entire cluster at the anchor position
                        # Sort cluster items by orig_span to maintain original order
                        sorted_cluster = sorted(cluster_items, key=lambda x: x.get("orig_span", (0, 0))[0])
                        cluster_text = "".join(item.get("text", "") for item in sorted_cluster)
                        inserts.append((anchor_pos, cluster_text, seq_counter))
                        seq_counter += 1
                        try:
                            if getattr(processor, "trace_enabled", False):
                                processor.trace_op(idx, "Post", NAME, f"Cluster restore: {len(sorted_cluster)} items at pos={anchor_pos}: {cluster_text!r}")
                        except Exception:
                            pass
                    else:
                        # No valid anchor for cluster - record all as failures
                        for item in cluster_items:
                            failures = processor.manifest.mappings.setdefault("anchor_restore_failures", [])
                            failures.append(
                                {
                                    "line": idx,
                                    "value": item.get("text", ""),
                                    "anchor_kind": item.get("anchor_kind"),
                                    "anchor_char": item.get("anchor_char"),
                                    "anchor_occurrence": item.get("anchor_occurrence"),
                                    "cluster_id": cluster_id,
                                    "source": {"mode": NAME},
                                }
                            )
                            remain_by_rec[rec_idx].append(item)
                        try:
                            if getattr(processor, "trace_enabled", False):
                                processor.trace_op(idx, "Post", NAME, f"Cluster restore failed: {len(cluster_items)} items, cluster_id={cluster_id}")
                        except Exception:
                            pass

        if inserts:
            # Sort by position desc; for same position equal to 0 (start) OR end-of-line,
            # apply in reverse recorded order to preserve original left-to-right grouping
            # when inserting repeatedly at a boundary.
            line_len = len(line)

            # Sort with stable positional ordering and apply reverse sequence for identical positions so that
            # repeated insertions at the same index (e.g., boundaries) preserve the original left-to-right order.
            def _sort_key(t: Tuple[int, str, int]):
                pos, _v, seq = t
                # Overall we sort by position descending so later positions don't shift earlier ones.
                # For items sharing the same position, apply in reverse sequence order to maintain left-to-right appearance.
                return (-pos, -seq)

            inserts.sort(key=_sort_key)
            line_s = line
            for p, v, _seq in inserts:
                line_s = line_s[:p] + v + line_s[p:]
            lines[idx] = line_s
            changes += len(inserts)

        # Write back remains per rec and accumulate residuals
        for i, rec in enumerate(recs):
            rec["removed"] = remain_by_rec.get(i, [])
            if rec["removed"]:
                residuals.append((idx, len(rec["removed"])))

    # No PROT compression: per updated policy do not insert or manipulate __PROT__ tokens here.

    return changes
