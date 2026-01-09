from __future__ import annotations

import re

NAME = "Free"
PHASE = "Both"
PRIORITY = 100
USES_REGEX = True
INPUTS = ["Pre Pattern", "Pre Replacement", "Post Pattern", "Post Replacement"]


def apply_pre(processor, lines, op, stats):
    pattern = getattr(op, "in1", "")
    repl = getattr(op, "in2", "")
    if not (pattern and repl):
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


def apply_post(processor, lines, op, stats):
    pattern = getattr(op, "in3", "")
    repl = getattr(op, "in4", "")
    if not (pattern and repl):
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
