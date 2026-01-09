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
    
    changes = 0
    for idx, line in enumerate(lines):
        if idx not in cust_map:
            continue
        recs = cust_map[idx]
        new_line = line
        # First: try to detect if any recorded values are already present in the line
        # (i.e. restored earlier by other modes). If found, consume them from the record
        # so we don't report false residual warnings.
        for rec in recs:
            pending_values: List[str] = rec.get("values", [])
            if not pending_values:
                continue
            consumed = []
            for v in list(pending_values):
                if v and v in new_line:
                    # consume first occurrence
                    new_line = new_line.replace(v, v, 1)
                    consumed.append(v)
                    pending_values.pop(0)
            if consumed:
                try:
                    if getattr(processor, "trace_enabled", False):
                        processor.trace_op(idx, "Post", NAME, f"Consumed {len(consumed)} pre-restored value(s) for token={rec.get('token')!r}")
                except Exception:
                    pass

        # Now perform token->value replacements for any remaining placeholders using helper
        from CherryAI.functions.modehelper import restore_placeholders_in_line
        for rec in recs:
            token = rec.get("token")
            values_for_token: List[str] = rec.get("values", [])
            if not token:
                continue
            try:
                # custom placeholders should not perform free-anchor fallbacks; only direct/fuzzy/span matches
                new_line, c, used_anchor = restore_placeholders_in_line(new_line, token, values_for_token, allow_anchor_fallback=False, anchor_hint=None)
                changes += c
                if c:
                    try:
                        if getattr(processor, "trace_enabled", False):
                            processor.trace_op(idx, "Post", NAME, f"{c} token(s) for {token} ({'anchor' if used_anchor else 'direct'})")
                    except Exception:
                        pass
            except Exception:
                # fallback to original simple replacement if helper fails
                pattern = re.escape(token)
                def repl(m: re.Match[str]) -> str:
                    if values_for_token:
                        return values_for_token.pop(0)
                    return token
                new_line, c = re.subn(pattern, repl, new_line)
                changes += c
                if c:
                    try:
                        if getattr(processor, "trace_enabled", False):
                            processor.trace_op(idx, "Post", NAME, f"{c} token(s) for {token}")
                    except Exception:
                        pass

        # After attempting both consumption and replacements, warn only if values remain
        remaining = sum(len(r.get("values", [])) for r in recs)
        if remaining:
            logging = __import__("logging")
            # Build a list[str] for tokens to satisfy typing
            token_set: List[str] = []
            for r in recs:
                tok = r.get("token")
                if isinstance(tok, str):
                    token_set.append(tok)
            token_list = sorted(set(token_set))
            logging.warning(
                "Custom restore residual on line %d: %d token(s) left for tokens %s",
                idx + 1,
                remaining,
                ", ".join(token_list),
            )

        lines[idx] = new_line
    return changes
