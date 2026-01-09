from __future__ import annotations

import re

NAME = "Only replace after TL"
PHASE = "Post"
PRIORITY = 100
USES_REGEX = True
INPUTS = ["Pattern", "Replacement"]


def apply_post(processor, lines, op, stats):
    pattern = getattr(op, "in3", "")
    repl = getattr(op, "in4", "")
    if not pattern:
        return 0
    changes = 0
    if op.is_regex:
        for i, ln in enumerate(lines):
            new_ln, c = re.subn(pattern, repl, ln)
            if c:
                lines[i] = new_ln
                changes += c
    else:
        for i, ln in enumerate(lines):
            c = ln.count(pattern)
            if c:
                lines[i] = ln.replace(pattern, repl)
                changes += c
    return changes
