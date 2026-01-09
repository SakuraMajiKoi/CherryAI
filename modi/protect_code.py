from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

# PROT compression/decompression and clustering is centralized in Standard Helpers
# (modi/standard_mode.py). This module only replaces matched segments with
# the literal '__PROT__' token and records captured values per-line.

NAME = "Protect Code"


# ─────────────────────────────────────────────────────────────────────────────
# v2.0 Manifest Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _add_prepro_op(processor, idx: int, op_data: Dict[str, Any]) -> None:
    """Add a preprocessing operation to a line's prepro_ops."""
    processor.manifest.add_prepro_op(idx, op_data)


def _get_prepro_ops(processor, idx: int, mode: str) -> List[Dict[str, Any]]:
    """Get preprocessing operations for a line filtered by mode."""
    return processor.manifest.get_prepro_ops(idx, mode) or []
# PHASE rationale:
# - This mode temporarily replaces matched code-like segments with the unified __PROT__ token during Pre.
# - Restoration is performed in Post by this mode's apply_post to give the mode full lifecycle ownership.
# - PROT compression/decompression (clustering adjacent tokens) is centralized in Standard Helpers.
PHASE = "Both"
PRIORITY = 20
USES_REGEX = True
INPUTS = ["Pattern"]


def apply_pre(processor, lines: List[str], op, stats: Dict[str, int]) -> int:
    pattern_str = (op.in1 or "").strip()
    if not pattern_str:
        return 0
    pattern = re.compile(pattern_str)

    changes = 0
    for idx, line in enumerate(lines):
        # Protect should run on the current line state even if Anchor removed items.
        # Anchor skipping could hide code that must still be protected.
        matches = list(pattern.finditer(line))
        if not matches:
            continue

        # Record each match with surrounding context for identification
        captured: List[Dict[str, Any]] = []
        for m in matches:
            val = m.group(0)
            if not val:
                continue

            # Capture context: 10 chars before and after for identification
            start = m.start()
            end = m.end()
            context_before = line[max(0, start - 10) : start]
            context_after = line[end : min(len(line), end + 10)]

            captured.append(
                {
                    "value": val,
                    "context_before": context_before,
                    "context_after": context_after,
                    "orig_position": start,  # For ordering when contexts are identical
                }
            )

        if not captured:
            continue

        # Replace all matches with generic __PROT__ (process in reverse to maintain positions)
        new_line = line
        for match_idx in range(len(matches) - 1, -1, -1):
            m = matches[match_idx]
            val = m.group(0)
            if not val:
                continue
            start = m.start()
            end = m.end()
            new_line = new_line[:start] + "__PROT__" + new_line[end:]

        # Write to prepro_ops (primary storage)
        op_data = {
            "mode": NAME,
            "pattern": pattern_str,
            "items": captured,
        }
        _add_prepro_op(processor, idx, op_data)

        lines[idx] = new_line

        # Trace with accurate match count
        try:
            if getattr(processor, "trace_enabled", False):
                processor.trace_op(
                    idx, "Pre", NAME, f"{len(captured)} match(es) for pattern {pattern_str!r}"
                )
        except Exception:
            pass
        changes += len(captured)

    return changes


def apply_post(processor, lines: List[str], op, stats: Dict[str, int]) -> int:
    """Restore protected segments recorded during Pre by matching context around __PROT__.

    Uses surrounding text context to identify which recorded value corresponds to each
    __PROT__ placeholder, eliminating positional ambiguity without polluting translation
    with numbered tokens.
    """
    changes = 0

    try:
        # Build mapping of line -> list of recorded items with context from prepro_ops
        prot_map: Dict[int, List[Dict[str, Any]]] = {}

        for idx in range(len(lines)):
            ops = _get_prepro_ops(processor, idx, NAME)
            for op_data in ops:
                items = op_data.get("items", [])
                if items:
                    prot_map.setdefault(idx, []).extend(items)
        
        # Restore each line by matching context around __PROT__ tokens
        MAX_WARN = 50
        warned = 0
        suppressed = 0
        
        for idx, line in enumerate(lines):
            if idx not in prot_map:
                continue
            
            items = prot_map[idx]
            if not items:
                continue
            
            # Find all __PROT__ positions in current line
            prot_pattern = re.compile(r"__PROT__")
            prot_matches = list(prot_pattern.finditer(line))
            
            if not prot_matches:
                continue
            
            # Match each __PROT__ to a recorded item using context
            new_line = line
            offset = 0  # Track cumulative length change
            matched_items = set()  # Track which items we've used
            
            for prot_match in prot_matches:
                prot_start = prot_match.start() + offset
                prot_end = prot_match.end() + offset
                
                # Get context around this __PROT__ in current line
                current_before = new_line[max(0, prot_start - 10):prot_start]
                current_after = new_line[prot_end:min(len(new_line), prot_end + 10)]
                
                # Find best matching item by context similarity
                best_item = None
                best_score = -1
                
                for item_idx, item in enumerate(items):
                    if item_idx in matched_items:
                        continue  # Already used this item
                    
                    recorded_before = item.get("context_before", "")
                    recorded_after = item.get("context_after", "")
                    
                    # Score based on longest common substring in context
                    score = 0
                    # Match suffix of current_before with suffix of recorded_before
                    min_len_before = min(len(current_before), len(recorded_before))
                    for i in range(1, min_len_before + 1):
                        if current_before[-i:] == recorded_before[-i:]:
                            score += i
                        else:
                            break
                    
                    # Match prefix of current_after with prefix of recorded_after
                    min_len_after = min(len(current_after), len(recorded_after))
                    for i in range(1, min_len_after + 1):
                        if current_after[:i] == recorded_after[:i]:
                            score += i
                        else:
                            break
                    
                    if score > best_score:
                        best_score = score
                        best_item = (item_idx, item)
                
                # If no good match found (score 0), fall back to position order
                if best_score == 0 and items:
                    for item_idx, item in enumerate(items):
                        if item_idx not in matched_items:
                            best_item = (item_idx, item)
                            break
                
                if best_item:
                    item_idx, item = best_item
                    matched_items.add(item_idx)
                    value = item.get("value", "")
                    
                    # Replace this specific __PROT__ with the value
                    new_line = new_line[:prot_start] + value + new_line[prot_end:]
                    offset += len(value) - (prot_end - prot_start)
                    changes += 1
            
            if changes:
                lines[idx] = new_line
                try:
                    if getattr(processor, "trace_enabled", False):
                        processor.trace_op(idx, "Post", NAME, f"{len(matched_items)} placeholder(s) restored")
                except Exception:
                    pass
            
            # Warn about unmatched items
            unmatched = len(items) - len(matched_items)
            if unmatched > 0:
                if warned < MAX_WARN:
                    logging.warning("Protect restore: line %d has %d unmatched item(s)", 
                                    idx + 1, unmatched)
                    warned += 1
                else:
                    suppressed += 1
        
        if suppressed:
            logging.warning("Protect restore: %d additional warnings suppressed", suppressed)
        if changes:
            stats["protect_restored"] = stats.get("protect_restored", 0) + changes
        return changes
    except Exception:
        logging.exception("Protect mode: restoration failed")
        return 0
