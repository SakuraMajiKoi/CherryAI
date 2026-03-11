"""API Log module for CherryAI.

Provides structured logging of all API requests and responses with:
- Typed dataclasses for log entries (sent/received pairs)
- Category classification (Main Translation, Term Translation, Gender Inference, Other)
- Status tracking (success, recovered, failed) with color coding
- Chronological ordering with sent/received coupling
- File persistence (JSON lines) alongside manifest
- In-memory subscription for live GUI updates

Architecture note: This module belongs in functions/ as shared logic.
Both GUI (API Log Window) and CLI can use it.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class LogCategory(str, Enum):
    """Category of an API request for filtering."""
    MAIN_TRANSLATION = "Main Translation"
    TERM_TRANSLATION = "Term Translation"
    GENDER_INFERENCE = "Gender Inference"
    OTHER = "Other"


class LogStatus(str, Enum):
    """Outcome status of a request/response pair."""
    SUCCESS = "success"       # Green — all good
    RECOVERED = "recovered"   # Yellow — had issues but recovered via retry
    FAILED = "failed"         # Red — not recovered, error persists
    PENDING = "pending"       # Awaiting response


# ============================================================================
# Dataclasses
# ============================================================================

@dataclass
class LogEntrySent:
    """Data captured when an API request is sent."""
    model: str = ""
    provider: str = ""
    temperature: float = 0.0
    system_prompt: str = ""
    user_content: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    line_count: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LogEntrySent:
        """Deserialize from dictionary."""
        known = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class LogEntryReceived:
    """Data captured when an API response arrives."""
    content: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    finish_reason: str = ""
    error_message: str = ""
    duration_ms: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LogEntryReceived:
        """Deserialize from dictionary."""
        known = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class LogEntry:
    """A coupled sent/received API log entry.

    Sent and received always belong together. A received response may
    arrive later but is always paired with its sent request.
    """
    entry_id: int = 0
    timestamp: str = ""
    category: str = LogCategory.OTHER.value
    status: str = LogStatus.PENDING.value
    attempt: int = 1
    max_attempts: int = 1
    sent: Optional[LogEntrySent] = None
    received: Optional[LogEntryReceived] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for persistence."""
        d: Dict[str, Any] = {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "category": self.category,
            "status": self.status,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
        }
        if self.sent is not None:
            d["sent"] = self.sent.to_dict()
        if self.received is not None:
            d["received"] = self.received.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LogEntry:
        """Deserialize from dictionary."""
        sent = None
        received = None
        if "sent" in data and data["sent"]:
            sent = LogEntrySent.from_dict(data["sent"])
        if "received" in data and data["received"]:
            received = LogEntryReceived.from_dict(data["received"])
        return cls(
            entry_id=data.get("entry_id", 0),
            timestamp=data.get("timestamp", ""),
            category=data.get("category", LogCategory.OTHER.value),
            status=data.get("status", LogStatus.PENDING.value),
            attempt=data.get("attempt", 1),
            max_attempts=data.get("max_attempts", 1),
            sent=sent,
            received=received,
        )


# ============================================================================
# API Log Store
# ============================================================================

class APILogStore:
    """In-memory store for API log entries with persistence and subscriptions.

    One instance per project. Created by ManifestManager or standalone.
    Supports live listeners for GUI updates.
    """

    def __init__(self, log_path: Optional[Path] = None) -> None:
        self._entries: List[LogEntry] = []
        self._next_id: int = 1
        self._log_path: Optional[Path] = log_path
        self._listeners: List[Callable[[LogEntry], None]] = []
        self._dirty: bool = False

    # --- Properties -------------------------------------------------------- #

    @property
    def entries(self) -> List[LogEntry]:
        """All log entries in chronological order."""
        return list(self._entries)

    @property
    def log_path(self) -> Optional[Path]:
        """Path to the log file on disk."""
        return self._log_path

    @log_path.setter
    def log_path(self, value: Optional[Path]) -> None:
        self._log_path = value

    @property
    def dirty(self) -> bool:
        """Whether unsaved changes exist."""
        return self._dirty

    # --- Subscription ------------------------------------------------------ #

    def subscribe(self, callback: Callable[[LogEntry], None]) -> None:
        """Register a listener called on every new or updated entry."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[LogEntry], None]) -> None:
        """Remove a previously registered listener."""
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    def _notify(self, entry: LogEntry) -> None:
        """Notify all listeners of a new or updated entry."""
        for cb in self._listeners:
            try:
                cb(entry)
            except Exception:
                logger.debug("Listener error", exc_info=True)

    # --- Entry management -------------------------------------------------- #

    def log_sent(
        self,
        category: LogCategory,
        sent: LogEntrySent,
        *,
        attempt: int = 1,
        max_attempts: int = 1,
    ) -> int:
        """Record an outgoing API request.

        Returns:
            The entry_id for later pairing with the response.
        """
        entry = LogEntry(
            entry_id=self._next_id,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            category=category.value,
            status=LogStatus.PENDING.value,
            attempt=attempt,
            max_attempts=max_attempts,
            sent=sent,
        )
        self._next_id += 1
        self._entries.append(entry)
        self._dirty = True
        self._notify(entry)
        return entry.entry_id

    def log_received(
        self,
        entry_id: int,
        received: LogEntryReceived,
        status: LogStatus = LogStatus.SUCCESS,
    ) -> None:
        """Pair a received response with a previously logged sent request."""
        entry = self._find_entry(entry_id)
        if entry is None:
            logger.warning("log_received: entry_id %s not found", entry_id)
            return
        entry.received = received
        entry.status = status.value
        self._dirty = True
        self._notify(entry)

    def log_pair(
        self,
        category: LogCategory,
        sent: LogEntrySent,
        received: LogEntryReceived,
        status: LogStatus = LogStatus.SUCCESS,
        *,
        attempt: int = 1,
        max_attempts: int = 1,
    ) -> int:
        """Log a complete request/response pair in one call.

        Returns:
            The entry_id.
        """
        entry = LogEntry(
            entry_id=self._next_id,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            category=category.value,
            status=status.value,
            attempt=attempt,
            max_attempts=max_attempts,
            sent=sent,
            received=received,
        )
        self._next_id += 1
        self._entries.append(entry)
        self._dirty = True
        self._notify(entry)
        return entry.entry_id

    def _find_entry(self, entry_id: int) -> Optional[LogEntry]:
        """Find an entry by its ID."""
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    # --- Filtering --------------------------------------------------------- #

    def get_filtered(
        self,
        *,
        category: Optional[LogCategory] = None,
        status: Optional[LogStatus] = None,
        search_text: str = "",
        view_mode: str = "Both",
    ) -> List[LogEntry]:
        """Return entries matching the given filters.

        Args:
            category: Filter by category (None = all).
            status: Filter by status (None = all).
            search_text: Case-insensitive text search across all fields.
            view_mode: "Sent", "Received", or "Both".

        Returns:
            Filtered list of LogEntry objects.
        """
        result: List[LogEntry] = []
        search_lower = search_text.lower() if search_text else ""
        view_lower = view_mode.lower() if view_mode else "both"

        for entry in self._entries:
            if category is not None and entry.category != category.value:
                continue
            if status is not None and entry.status != status.value:
                continue
            if view_lower == "sent" and entry.sent is None:
                continue
            if view_lower == "received" and entry.received is None:
                continue
            if search_lower and not self._entry_matches_search(entry, search_lower):
                continue
            result.append(entry)
        return result

    @staticmethod
    def _entry_matches_search(entry: LogEntry, search_lower: str) -> bool:
        """Check if any field in the entry contains the search text."""
        if search_lower in entry.category.lower():
            return True
        if search_lower in entry.status.lower():
            return True
        if search_lower in entry.timestamp.lower():
            return True
        if entry.sent:
            if search_lower in entry.sent.model.lower():
                return True
            if search_lower in entry.sent.system_prompt.lower():
                return True
            if search_lower in entry.sent.user_content.lower():
                return True
        if entry.received:
            if search_lower in entry.received.content.lower():
                return True
            if search_lower in entry.received.error_message.lower():
                return True
        return False

    # --- Persistence ------------------------------------------------------- #

    def save(self, path: Optional[Path] = None) -> bool:
        """Save all entries to the log file (JSON lines format).

        Args:
            path: Override path. Uses self._log_path if None.

        Returns:
            True if saved successfully.
        """
        target = path or self._log_path
        if target is None:
            return False
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                for entry in self._entries:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False))
                    f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp), str(target))
            self._dirty = False
            logger.debug("Saved API log: %s (%d entries)", target, len(self._entries))
            return True
        except Exception:
            logger.error("Failed to save API log to %s", target, exc_info=True)
            return False

    def load(self, path: Optional[Path] = None) -> bool:
        """Load entries from a log file.

        Args:
            path: Override path. Uses self._log_path if None.

        Returns:
            True if loaded successfully.
        """
        target = path or self._log_path
        if target is None or not target.exists():
            return False
        try:
            entries: List[LogEntry] = []
            max_id = 0
            with open(target, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = LogEntry.from_dict(data)
                        entries.append(entry)
                        if entry.entry_id > max_id:
                            max_id = entry.entry_id
                    except (json.JSONDecodeError, KeyError, TypeError):
                        logger.debug("Skipping corrupt log line")
            self._entries = entries
            self._next_id = max_id + 1
            self._dirty = False
            self._log_path = target
            logger.debug("Loaded API log: %s (%d entries)", target, len(entries))
            return True
        except Exception:
            logger.error("Failed to load API log from %s", target, exc_info=True)
            return False

    def clear(self) -> None:
        """Remove all entries from memory."""
        self._entries.clear()
        self._next_id = 1
        self._dirty = True


# ============================================================================
# Module-level singleton
# ============================================================================

_global_store: Optional[APILogStore] = None


def get_api_log_store() -> APILogStore:
    """Get or create the global API log store singleton."""
    global _global_store
    if _global_store is None:
        _global_store = APILogStore()
    return _global_store


def reset_api_log_store(log_path: Optional[Path] = None) -> APILogStore:
    """Reset and return a fresh global API log store.

    Called when creating or loading a new project to bind the log
    to the correct file path.
    """
    global _global_store
    _global_store = APILogStore(log_path=log_path)
    return _global_store
