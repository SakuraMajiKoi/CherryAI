from __future__ import annotations

import re

NAME = "Only Remove"
PHASE = "Pre"
PRIORITY = 100
USES_REGEX = True
INPUTS = ["Pattern"]


def apply_pre(processor, lines, op, stats):
    pattern = getattr(op, "in1", "")
    if not pattern:
        return 0
    compiled = re.compile(pattern)
    changes = 0
    for i, ln in enumerate(lines):
        new_ln, c = compiled.subn("", ln)
        if c:
            lines[i] = new_ln
            changes += c
    return changes
