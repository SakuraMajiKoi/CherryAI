"""Template for a CherryAI mode plugin.

Mandatory attributes:
  - NAME: str  # The exact mode label as it appears in the UI
  - PHASE: str # One of: 'Pre', 'Post', 'Both'

Optional attributes:
  - PRIORITY: int       # Lower runs earlier within the same phase
  - USES_REGEX: bool    # Advisory to UI for enabling regex toggle
  - INPUTS: list[str]   # Labels for in1..in4 (use fewer than 4 if not needed)

Optional functions (depending on PHASE):
  - apply_pre(processor, lines: list[str], op, stats: dict) -> int
  - apply_post(processor, lines: list[str], op, stats: dict) -> int

Notes:
  - 'processor' is the host Processor instance; you may access processor.manifest.
  - 'op' is the Operation dataclass for this row.
  - Return value should be an integer number of changes for logging/stats.
"""

# Example (commented):
# NAME = "My Custom Mode"
# PHASE = "Both"
# PRIORITY = 100
# USES_REGEX = True
# INPUTS = ["Pattern", "Replacement", "PostPattern", "PostReplacement"]

def apply_pre(processor, lines, op, stats):
    # Implement pre-translation transformation here
    return 0

def apply_post(processor, lines, op, stats):
    # Implement post-translation transformation here
    return 0
