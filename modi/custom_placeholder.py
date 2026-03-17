from __future__ import annotations

import re
from typing import Any, Dict, List

NAME = "Custom Placeholder"
PHASE = "Pre"
PRIORITY = 10
USES_REGEX = True
INPUTS = ["Pattern", "Token"]


# ─────────────────────────────────────────────────────────────────────────────
# v2.0 Manifest Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _add_prepro_op(processor, idx: int, op_data: Dict[str, Any]) -> None:
    """Add a preprocessing operation to a line's prepro_ops."""
    processor.manifest.add_prepro_op(idx, op_data)


def _get_prepro_ops(processor, idx: int, mode: str) -> List[Dict[str, Any]]:
    """Get preprocessing operations for a line filtered by mode."""
    return processor.manifest.get_prepro_ops(idx, mode) or []


def apply_pre(processor, lines: List[str], op, stats: Dict[str, int]) -> int:
    pattern_str = (op.in1 or "").strip()
    token = (op.in2 or "__CUST__").strip() or "__CUST__"
    if not pattern_str:
        return 0
    compiled = re.compile(pattern_str) if (op.is_regex or op.is_regex is None) else None

    changes = 0
    for idx, line in enumerate(lines):
        captured: List[str] = []

        def repl(m: re.Match[str]) -> str:
            val = m.group(0)
            if not val:
                return val
            captured.append(val)
            return token

        if compiled is not None:
            new_line, c = compiled.subn(repl, line)
        else:
            new_line = line.replace(pattern_str, token)
            c = line.count(pattern_str)
            if c:
                captured = [pattern_str] * c
        if c:
            # Write to prepro_ops (primary storage)
            op_data = {
                "mode": NAME,
                "pattern": pattern_str,
                "token": token,
                "values": list(captured),
            }
            _add_prepro_op(processor, idx, op_data)

            lines[idx] = new_line
            # pre trace
            try:
                if getattr(processor, "trace_enabled", False):
                    processor.trace_op(
                        idx, "Pre", NAME, f"{c} match(es): pattern={pattern_str!r}, token={token!r}"
                    )
            except Exception:
                pass
            changes += c
    return changes


def apply_post(processor, lines: List[str], op, stats: Dict[str, int]) -> int:
    """Restore custom placeholder tokens recorded during Pre using manifest entries.

    This mirrors the 'restore_custom' logic previously present in the Processor so that
    the mode owns its full lifecycle (capture at Pre, restore at Post).
    """
    # Build mapping of line -> list of records with token and values from prepro_ops
    cust_map: Dict[int, List[Dict[str, Any]]] = {}

    for idx in range(len(lines)):
        ops = _get_prepro_ops(processor, idx, NAME)
        for op_data in ops:
            token = op_data.get("token", "__CUST__")
            captured_values = op_data.get("values", [])
            if captured_values:
                cust_map.setdefault(idx, []).append(
                    {
                        "token": token,
                        "values": list(captured_values),
                        "source": [
                            {"mode": NAME, "pattern": op_data.get("pattern", ""), "token": token}
                        ],
                    }
                )
    
    if not cust_map:
        return 0
    
    from CherryAI.functions.modehelper import restore_custom_placeholders_batch

    restored_lines, restore_stats, residuals = restore_custom_placeholders_batch(
        lines,
        cust_map,
    )
    lines[:] = restored_lines

    changes = int(restore_stats.get("local_restored", 0)) + int(
        restore_stats.get("global_restored", 0)
    )

    if changes:
        try:
            if getattr(processor, "trace_enabled", False):
                processor.trace_op(
                    -1,
                    "Post",
                    NAME,
                    (
                        f"{changes} token(s) restored "
                        f"(local={restore_stats.get('local_restored', 0)}, "
                        f"global={restore_stats.get('global_restored', 0)})"
                    ),
                )
        except Exception:
            pass

    if residuals:
        logging = __import__("logging")
        for token, values in residuals.items():
            logging.warning(
                "Custom restore residual: %d token(s) left for token %s",
                len(values),
                token,
            )

    return changes
