"""Process execution priority definitions.

TASK 42.11: Defines the canonical priority ordering for all
preprocessing and postprocessing operations.  Lower priority
numbers execute first during preprocessing; postprocessing
reverses the order (highest priority first).

Each modi/ module should expose a ``PRIORITY`` constant that
matches one of the values defined here.  The mode_adapter sorts
operations by this constant before execution.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# ──────────────────────────────────────────────────────────────
# Preprocessing priorities (lower → runs first)
# ──────────────────────────────────────────────────────────────

PRE_PRIORITIES: Dict[str, int] = {
    "deduplication": 10,
    "ellipsis_compression": 20,
    "symbol_conversion": 30,
    "width_conversion": 35,
    "speaker_replacement": 40,
    "code_spacing": 50,
    "prot_compression": 60,
    "custom_placeholders": 70,
    "anchoring": 75,
    "quote_stripping": 76,
    "protect_code": 80,
    "aggressive_dedup": 90,
}

# ──────────────────────────────────────────────────────────────
# Postprocessing priorities (lower → runs first)
# Highest priority (lowest number) runs first in post.
# ──────────────────────────────────────────────────────────────

POST_PRIORITIES: Dict[str, int] = {
    "aggressive_dedup": 5,
    "quote_stripping": 9,
    "anchoring": 10,
    "protect_code": 20,
    "custom_placeholders": 30,
    "prot_decompression": 40,
    "code_spacing": 50,
    "speaker_replacement": 60,
    "symbol_conversion": 70,
    "ellipsis_expansion": 80,
    "deduplication": 90,
    "quote_balance": 100,
    "bracket_balance": 110,
    "whitespace_normalization": 120,
    "code_spacing_post": 130,
}


def get_pre_order() -> List[Tuple[str, int]]:
    """Return preprocessing operations sorted by execution order.

    Returns:
        List of (process_name, priority) tuples, lowest priority first.
    """
    return sorted(PRE_PRIORITIES.items(), key=lambda kv: kv[1])


def get_post_order() -> List[Tuple[str, int]]:
    """Return postprocessing operations sorted by execution order.

    Returns:
        List of (process_name, priority) tuples, lowest priority first.
    """
    return sorted(POST_PRIORITIES.items(), key=lambda kv: kv[1])
