from __future__ import annotations

import re
from typing import Any, Dict, List

NAME = "Temporary Replacement"
PHASE = "Both"
PRIORITY = 100
USES_REGEX = True
INPUTS = ["Pre Pattern", "Pre Replacement"]


# ─────────────────────────────────────────────────────────────────────────────
# v2.0 Manifest Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _add_prepro_op(processor, idx: int, op_data: Dict[str, Any]) -> None:
    """Add a preprocessing operation to a line's prepro_ops."""
    processor.manifest.add_prepro_op(idx, op_data)


def _get_prepro_ops(processor, idx: int, mode: str) -> List[Dict[str, Any]]:
    """Get preprocessing operations for a line filtered by mode."""
    return processor.manifest.get_prepro_ops(idx, mode) or []


def apply_pre(processor, lines, op, stats):
    pattern = getattr(op, "in1", "")
    repl = getattr(op, "in2", "")
    if not pattern:
        return 0

    # If replacement is empty or whitespace-only, use a unique placeholder
    use_placeholder = not repl or not repl.strip()
    placeholder_prefix = "__TEMPREPL_"

    changes = 0
    if op.is_regex:
        try:
            compiled_pattern = re.compile(pattern)
        except re.error as e:
            # Log regex compilation error and skip
            try:
                import logging

                logging.error(f"Temporary Replacement: Invalid regex pattern '{pattern}': {e}")
            except Exception:
                pass
            return 0
        for i, ln in enumerate(lines):
            matches = list(compiled_pattern.finditer(ln))
            if matches:
                # Generate placeholders if needed
                line_replacements: List[Dict[str, Any]] = []
                if use_placeholder:
                    new_ln = ln
                    offset = 0
                    for match_idx, m in enumerate(matches):
                        placeholder = f"{placeholder_prefix}{i}_{match_idx}__"
                        replacement_item = {
                            "original": m.group(0),
                            "placeholder": placeholder,
                            "pattern": pattern,
                            "replacement": repl,
                            "is_regex": True,
                        }
                        line_replacements.append(replacement_item)
                        # Replace in line with offset adjustment
                        start = m.start() + offset
                        end = m.end() + offset
                        new_ln = new_ln[:start] + placeholder + new_ln[end:]
                        offset += len(placeholder) - (end - start)
                    lines[i] = new_ln
                    changes += len(matches)
                else:
                    for m in matches:
                        replacement_item = {
                            "original": m.group(0),
                            "placeholder": None,
                            "pattern": pattern,
                            "replacement": repl,
                            "is_regex": True,
                        }
                        line_replacements.append(replacement_item)
                    new_ln, c = compiled_pattern.subn(repl, ln)
                    lines[i] = new_ln
                    changes += c

                # Write to prepro_ops
                if line_replacements:
                    _add_prepro_op(
                        processor,
                        i,
                        {
                            "mode": NAME,
                            "replacements": line_replacements,
                        },
                    )
    else:
        for i, ln in enumerate(lines):
            if pattern not in ln:
                continue

            line_replacements = []
            if use_placeholder:
                new_ln = ln
                match_idx = 0
                while pattern in new_ln:
                    placeholder = f"{placeholder_prefix}{i}_{match_idx}__"
                    replacement_item = {
                        "original": pattern,
                        "placeholder": placeholder,
                        "pattern": pattern,
                        "replacement": repl,
                        "is_regex": False,
                    }
                    line_replacements.append(replacement_item)
                    new_ln = new_ln.replace(pattern, placeholder, 1)
                    match_idx += 1
                    changes += 1
                lines[i] = new_ln
            else:
                c = ln.count(pattern)
                for _ in range(c):
                    replacement_item = {
                        "original": pattern,
                        "placeholder": None,
                        "pattern": pattern,
                        "replacement": repl,
                        "is_regex": False,
                    }
                    line_replacements.append(replacement_item)
                lines[i] = ln.replace(pattern, repl)
                changes += c

            # Write to prepro_ops
            if line_replacements:
                _add_prepro_op(
                    processor,
                    i,
                    {
                        "mode": NAME,
                        "replacements": line_replacements,
                    },
                )
    return changes


def apply_post(processor, lines, op, stats):
    """Restore temporary replacements recorded during Pre."""
    # Build mapping of line -> list of replacement records from prepro_ops
    repl_map: Dict[int, List[Dict[str, Any]]] = {}

    for idx in range(len(lines)):
        ops = _get_prepro_ops(processor, idx, NAME)
        for op_data in ops:
            replacements = op_data.get("replacements", [])
            if replacements:
                repl_map.setdefault(idx, []).extend(replacements)

    if not repl_map:
        return 0

    changes = 0
    for line_idx, replacements in repl_map.items():
        if line_idx >= len(lines):
            continue
        if not replacements:
            continue

        line = lines[line_idx]

        # Process replacements
        for item in replacements:
            orig_text = item.get("original", "")
            placeholder = item.get("placeholder")
            repl_text = item.get("replacement", "")

            if placeholder:
                # Replace placeholder with original
                if placeholder in line:
                    line = line.replace(placeholder, orig_text, 1)
                    changes += 1
            elif repl_text:
                # Replace replacement text with original
                if repl_text in line:
                    line = line.replace(repl_text, orig_text, 1)
                    changes += 1

        lines[line_idx] = line

    return changes
