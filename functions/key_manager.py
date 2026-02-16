"""Multi-Key Management & Auto-Rotation for CherryAI.

TASK 17.2: Manages multiple API keys per provider with automatic
rotation on rate-limit errors, daily exhaustion, and priority-based
scheduling.

Key Pool Modes
--------------
- **sequential**: Use keys in order until each is exhausted.
- **even**: Spread requests evenly across all active keys.
- **priority**: Prefer higher-priority keys, fall back on exhaustion.

Storage
-------
Keys are persisted to ``user/api_keys.json``.  In production the file
should be protected (e.g. via OS file permissions or keyring).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cherryai.keys")

_KEYS_FILE = "user/api_keys.json"


class PoolMode(str, Enum):
    """Key selection strategy."""

    SEQUENTIAL = "sequential"
    EVEN = "even"
    PRIORITY = "priority"


class KeyStatus(str, Enum):
    """Runtime status of a key."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXHAUSTED = "exhausted"


@dataclass
class APIKey:
    """A single API key with metadata and usage tracking."""

    key_id: str = ""
    name: str = ""
    provider: str = "openai"
    api_key: str = ""
    status: str = "active"
    priority: int = 0  # lower = higher priority
    # Usage tracking (reset daily)
    requests_today: int = 0
    tokens_today: int = 0
    cost_today: float = 0.0
    requests_month: int = 0
    tokens_month: int = 0
    cost_month: float = 0.0
    last_used: float = 0.0
    last_error: str = ""
    exhausted_until: float = 0.0  # unix timestamp

    @property
    def is_available(self) -> bool:
        """True if the key can be used for requests."""
        if self.status != KeyStatus.ACTIVE:
            return False
        if self.exhausted_until and time.time() < self.exhausted_until:
            return False
        return True

    def record_usage(
        self, requests: int = 1, tokens: int = 0, cost: float = 0.0,
    ) -> None:
        """Record a successful API call."""
        self.requests_today += requests
        self.tokens_today += tokens
        self.cost_today += cost
        self.requests_month += requests
        self.tokens_month += tokens
        self.cost_month += cost
        self.last_used = time.time()
        self.last_error = ""

    def mark_exhausted(self, duration_seconds: float = 86400) -> None:
        """Mark this key as exhausted for *duration_seconds*."""
        self.status = KeyStatus.EXHAUSTED
        self.exhausted_until = time.time() + duration_seconds
        logger.info("Key '%s' marked exhausted until %s", self.name, self.exhausted_until)

    def reset(self) -> None:
        """Reset exhaustion status."""
        self.status = KeyStatus.ACTIVE
        self.exhausted_until = 0.0
        self.last_error = ""

    def reset_daily(self) -> None:
        """Reset daily counters."""
        self.requests_today = 0
        self.tokens_today = 0
        self.cost_today = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIKey":
        known = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# -----------------------------------------------------------------------
# Key store
# -----------------------------------------------------------------------

def _keys_path() -> Path:
    return Path(_KEYS_FILE)


def load_keys() -> List[APIKey]:
    """Load all stored API keys."""
    path = _keys_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [APIKey.from_dict(k) for k in raw.get("keys", [])]
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Failed to load API keys: %s", exc)
        return []


def save_keys(keys: List[APIKey]) -> None:
    """Persist API keys to disk."""
    path = _keys_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"keys": [k.to_dict() for k in keys]}
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8",
    )


def add_key(key: APIKey) -> None:
    """Add a new key and persist."""
    keys = load_keys()
    # Auto-generate key_id if not set
    if not key.key_id:
        existing_ids = {k.key_id for k in keys}
        idx = 1
        while f"key_{idx}" in existing_ids:
            idx += 1
        key.key_id = f"key_{idx}"
    keys.append(key)
    save_keys(keys)


def remove_key(key_id: str) -> bool:
    """Remove a key by its ID.  Returns True if found."""
    keys = load_keys()
    orig = len(keys)
    keys = [k for k in keys if k.key_id != key_id]
    if len(keys) < orig:
        save_keys(keys)
        return True
    return False


def update_key(key_id: str, **fields: Any) -> Optional[APIKey]:
    """Update fields on an existing key."""
    keys = load_keys()
    for key in keys:
        if key.key_id == key_id:
            for name, value in fields.items():
                if hasattr(key, name):
                    setattr(key, name, value)
            save_keys(keys)
            return key
    return None


def get_key(key_id: str) -> Optional[APIKey]:
    """Return a single key by ID."""
    for key in load_keys():
        if key.key_id == key_id:
            return key
    return None


def get_keys_for_provider(provider: str) -> List[APIKey]:
    """Return all keys for a given provider."""
    return [k for k in load_keys() if k.provider == provider]


# -----------------------------------------------------------------------
# Key pool / rotation
# -----------------------------------------------------------------------

class KeyPool:
    """Manages rotation across multiple API keys for a provider.

    Args:
        provider: Provider name (e.g. ``"openai"``).
        mode: Selection strategy.
    """

    def __init__(
        self,
        provider: str = "openai",
        mode: PoolMode = PoolMode.SEQUENTIAL,
    ) -> None:
        self.provider = provider
        self.mode = mode
        self._keys: List[APIKey] = []
        self._index = 0

    def load(self) -> None:
        """Load keys for this provider from disk."""
        self._keys = get_keys_for_provider(self.provider)
        self._index = 0

    @property
    def available_keys(self) -> List[APIKey]:
        """Return keys that are currently usable."""
        return [k for k in self._keys if k.is_available]

    def next_key(self) -> Optional[APIKey]:
        """Select the next key according to the pool mode.

        Returns ``None`` if no keys are available.
        """
        available = self.available_keys
        if not available:
            return None

        if self.mode == PoolMode.SEQUENTIAL:
            return self._next_sequential(available)
        if self.mode == PoolMode.EVEN:
            return self._next_even(available)
        if self.mode == PoolMode.PRIORITY:
            return self._next_priority(available)
        return available[0]

    def _next_sequential(self, available: List[APIKey]) -> APIKey:
        """Return the first available key (stable ordering by key_id)."""
        available.sort(key=lambda k: k.key_id)
        return available[0]

    def _next_even(self, available: List[APIKey]) -> APIKey:
        """Return the key with the fewest requests today."""
        return min(available, key=lambda k: k.requests_today)

    def _next_priority(self, available: List[APIKey]) -> APIKey:
        """Return the highest-priority available key."""
        return min(available, key=lambda k: k.priority)

    def on_rate_limit(self, key_id: str) -> Optional[APIKey]:
        """Handle a rate-limit error for *key_id*.

        Marks the key as exhausted and returns the next available key.
        """
        for key in self._keys:
            if key.key_id == key_id:
                key.mark_exhausted(duration_seconds=3600)
                break
        # Persist the exhaustion
        update_key(key_id, status=KeyStatus.EXHAUSTED,
                   exhausted_until=time.time() + 3600)
        return self.next_key()

    def record_usage(
        self,
        key_id: str,
        requests: int = 1,
        tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        """Record usage for a key and persist."""
        for key in self._keys:
            if key.key_id == key_id:
                key.record_usage(requests, tokens, cost)
                break
        update_key(
            key_id,
            requests_today=next(
                (k.requests_today for k in self._keys if k.key_id == key_id), 0,
            ),
            tokens_today=next(
                (k.tokens_today for k in self._keys if k.key_id == key_id), 0,
            ),
            cost_today=next(
                (k.cost_today for k in self._keys if k.key_id == key_id), 0.0,
            ),
        )

    def reset_all(self) -> None:
        """Reset exhaustion status for all keys in the pool."""
        for key in self._keys:
            key.reset()
        save_keys(load_keys())  # re-persist

    def summary(self) -> List[Dict[str, Any]]:
        """Return a summary of all keys in the pool."""
        result = []
        for key in self._keys:
            result.append({
                "key_id": key.key_id,
                "name": key.name,
                "provider": key.provider,
                "status": key.status,
                "priority": key.priority,
                "requests_today": key.requests_today,
                "tokens_today": key.tokens_today,
                "cost_today": key.cost_today,
                "available": key.is_available,
            })
        return result
