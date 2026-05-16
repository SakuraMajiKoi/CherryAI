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
import threading
import time
import datetime as dt
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

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
    CONTENT_WARNING = "content_warning"  # Unsafe/refused content handling
    FAILED = "failed"         # Red — not recovered, error persists
    PENDING = "pending"       # Awaiting response


UNKNOWN_VALUE = "Unknown"

PRICING_STATUS_OK = "ok"
PRICING_STATUS_FREE = "free"
PRICING_STATUS_UNKNOWN = "unknown"

VALIDATION_STATUS_PASSED = "passed"
VALIDATION_STATUS_RECOVERED = "recovered"
VALIDATION_STATUS_FAILED = "failed"
VALIDATION_STATUS_UNKNOWN = "unknown"

FAILURE_KIND_API = "api_failure"
FAILURE_KIND_INFERENCE = "inference_failure"
FAILURE_KIND_CONTENT_WARNING = "content_warning"


# ============================================================================
# Dataclasses
# ============================================================================

@dataclass
class LogEntrySent:
    """Data captured when an API request is sent."""
    project_name: str = ""
    model: str = ""
    provider: str = ""
    task_type: str = ""
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

    def to_ledger_row(self, log_path: Optional[Path] = None) -> Dict[str, Any]:
        """Convert this request/response pair into a canonical ledger row."""
        return build_ledger_row_from_entry(self, log_path=log_path)

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


def _infer_task_type(entry: LogEntry, sent: Optional[LogEntrySent]) -> str:
    if sent is not None and sent.task_type:
        return sent.task_type

    extra_type = ""
    if sent is not None and sent.extra:
        extra_type = str(sent.extra.get("type", "")).strip().lower()
    if extra_type == "connection_test":
        return "api_test"
    if extra_type == "model_translation_test":
        return "api_test"

    if entry.category == LogCategory.MAIN_TRANSLATION.value:
        return "translation"
    if entry.category == LogCategory.TERM_TRANSLATION.value:
        return "glossary"
    if entry.category == LogCategory.GENDER_INFERENCE.value:
        return "gender_inference"
    return ""


def category_for_task_type(task_type: str) -> LogCategory:
    """Map ledger task types back to API log categories."""
    normalized = (task_type or "").strip().lower()
    if normalized == "translation":
        return LogCategory.MAIN_TRANSLATION
    if normalized in {"glossary", "game_summary"}:
        return LogCategory.TERM_TRANSLATION
    if normalized == "gender_inference":
        return LogCategory.GENDER_INFERENCE
    return LogCategory.OTHER


def _infer_project_name(sent: Optional[LogEntrySent], log_path: Optional[Path]) -> str:
    if sent is not None and sent.project_name:
        return sent.project_name
    if log_path is None:
        return ""

    name = log_path.name
    if name.endswith(".api_log.jsonl"):
        return name[: -len(".api_log.jsonl")]
    if name.endswith(".jsonl"):
        return name[: -len(".jsonl")]
    return log_path.stem


def _coalesce_text(value: Any, default: str = UNKNOWN_VALUE) -> str:
    text = str(value or "").strip()
    return text or default


def _has_inference_output(received: Optional[LogEntryReceived]) -> bool:
    if received is None:
        return False
    return bool(
        received.content.strip()
        or received.prompt_tokens
        or received.completion_tokens
        or received.total_tokens
    )


def _resolve_pricing_snapshot(
    sent: Optional[LogEntrySent],
    received: LogEntryReceived,
) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        "input_price_per_m": None,
        "cached_input_price_per_m": None,
        "output_price_per_m": None,
        "input_cost": 0.0,
        "cached_cost": 0.0,
        "output_cost": 0.0,
        "total_cost": 0.0,
        "pricing_status": PRICING_STATUS_UNKNOWN,
        "pricing_source": "API.ini",
    }

    model_id = (sent.model if sent is not None else "").strip()
    if not model_id:
        return snapshot

    try:
        from .model_registry import get_model_info

        model_info = get_model_info(model_id)
    except Exception:
        logger.debug("Unable to resolve model pricing for %s", model_id, exc_info=True)
        return snapshot

    if model_info is None:
        return snapshot

    input_price = model_info.input_price
    cached_input_price = model_info.cached_input_price
    output_price = model_info.output_price

    snapshot["input_price_per_m"] = input_price
    snapshot["cached_input_price_per_m"] = cached_input_price
    snapshot["output_price_per_m"] = output_price

    cached_tokens = max(int(received.cached_tokens or 0), 0)
    prompt_tokens = max(int(received.prompt_tokens or 0), 0)
    completion_tokens = max(int(received.completion_tokens or 0), 0)
    non_cached_prompt_tokens = max(prompt_tokens - cached_tokens, 0)

    used_prices: List[float] = []
    if non_cached_prompt_tokens > 0:
        if input_price is None:
            return snapshot
        used_prices.append(float(input_price))
    if cached_tokens > 0:
        if cached_input_price is None:
            return snapshot
        used_prices.append(float(cached_input_price))
    if completion_tokens > 0:
        if output_price is None:
            return snapshot
        used_prices.append(float(output_price))

    if not used_prices:
        for price in (input_price, cached_input_price, output_price):
            if price is not None:
                used_prices.append(float(price))
        if not used_prices:
            return snapshot

    input_cost = (
        non_cached_prompt_tokens * float(input_price or 0.0) / 1_000_000
    )
    cached_cost = cached_tokens * float(cached_input_price or 0.0) / 1_000_000
    output_cost = completion_tokens * float(output_price or 0.0) / 1_000_000
    total_cost = input_cost + cached_cost + output_cost

    snapshot["input_cost"] = round(input_cost, 12)
    snapshot["cached_cost"] = round(cached_cost, 12)
    snapshot["output_cost"] = round(output_cost, 12)
    snapshot["total_cost"] = round(total_cost, 12)
    snapshot["pricing_status"] = (
        PRICING_STATUS_FREE if all(price == 0.0 for price in used_prices)
        else PRICING_STATUS_OK
    )
    return snapshot


def _infer_failure_kind(entry: LogEntry, received: LogEntryReceived) -> str:
    extra_value = str(received.extra.get("failure_kind", "")).strip().lower()
    if extra_value:
        return extra_value
    if entry.status == LogStatus.CONTENT_WARNING.value:
        return FAILURE_KIND_CONTENT_WARNING
    if entry.status != LogStatus.FAILED.value:
        return ""
    if _has_inference_output(received):
        return FAILURE_KIND_INFERENCE
    return FAILURE_KIND_API


def _infer_validation_status(entry: LogEntry, received: LogEntryReceived) -> str:
    extra_value = str(received.extra.get("validation_status", "")).strip().lower()
    if extra_value:
        return extra_value
    if entry.status == LogStatus.SUCCESS.value:
        return VALIDATION_STATUS_PASSED
    if entry.status == LogStatus.RECOVERED.value:
        return VALIDATION_STATUS_RECOVERED
    if entry.status == LogStatus.CONTENT_WARNING.value:
        return VALIDATION_STATUS_FAILED
    if entry.status == LogStatus.FAILED.value and _has_inference_output(received):
        return VALIDATION_STATUS_FAILED
    return VALIDATION_STATUS_UNKNOWN


def enrich_completed_entry(
    entry: LogEntry,
    *,
    log_path: Optional[Path] = None,
) -> None:
    """Fill a completed entry with saved pricing and validation metadata."""
    if entry.status == LogStatus.PENDING.value or entry.received is None:
        return

    sent = entry.sent
    received = entry.received
    sent_extra = sent.extra if sent is not None else {}
    received_extra = received.extra

    pricing_snapshot = _resolve_pricing_snapshot(sent, received)
    for key, value in pricing_snapshot.items():
        if key not in received_extra and key not in sent_extra:
            received_extra[key] = value

    validation_status = _infer_validation_status(entry, received)
    if validation_status and "validation_status" not in received_extra:
        received_extra["validation_status"] = validation_status

    failure_kind = _infer_failure_kind(entry, received)
    if failure_kind and "failure_kind" not in received_extra:
        received_extra["failure_kind"] = failure_kind

    if entry.status == LogStatus.FAILED.value and received.error_message:
        received_extra.setdefault("validation_error", received.error_message)

    if sent is not None:
        sent_extra.setdefault(
            "resolved_project_name",
            _coalesce_text(_infer_project_name(sent, log_path)),
        )
        sent_extra.setdefault("resolved_provider", _coalesce_text(sent.provider))
        sent_extra.setdefault("resolved_model", _coalesce_text(sent.model))
        sent_extra.setdefault(
            "resolved_task_type",
            _coalesce_text(_infer_task_type(entry, sent)),
        )


def _parse_entry_timestamp(timestamp: str) -> float:
    text = (timestamp or "").strip()
    if not text:
        return time.time()

    try:
        return float(text)
    except ValueError:
        pass

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(text, fmt).replace(tzinfo=dt.timezone.utc)
            return parsed.timestamp()
        except ValueError:
            continue

    return time.time()


def build_log_request_ref(entry: LogEntry, log_path: Optional[Path] = None) -> str:
    """Build a stable request reference for ledger rows."""
    if log_path is not None:
        return f"{log_path.name}:{entry.entry_id}"
    return f"api-log:{entry.entry_id}"


def parse_log_request_ref(request_ref: str) -> tuple[Optional[str], Optional[int]]:
    """Parse a ledger request reference back into (log_name, entry_id)."""
    text = (request_ref or "").strip()
    if not text or ":" not in text:
        return None, None
    log_name, _, entry_id_text = text.rpartition(":")
    if not log_name:
        return None, None
    try:
        return log_name, int(entry_id_text)
    except ValueError:
        return log_name, None


def build_ledger_row_from_entry(
    entry: LogEntry,
    log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Normalize an API log entry into the shared ledger row schema."""
    from .usage_tracker import UsageRecord

    enrich_completed_entry(entry, log_path=log_path)

    sent = entry.sent
    received = entry.received or LogEntryReceived()
    success = entry.status in {LogStatus.SUCCESS.value, LogStatus.RECOVERED.value}
    sent_extra = sent.extra if sent is not None else {}
    received_extra = received.extra if received is not None else {}
    record = UsageRecord(
        timestamp=_parse_entry_timestamp(entry.timestamp),
        project_name=_coalesce_text(
            sent_extra.get("resolved_project_name") or _infer_project_name(sent, log_path)
        ),
        provider=_coalesce_text(
            sent_extra.get("resolved_provider") or (sent.provider if sent is not None else "")
        ),
        model=_coalesce_text(
            sent_extra.get("resolved_model") or (sent.model if sent is not None else "")
        ),
        task_type=_coalesce_text(
            sent_extra.get("resolved_task_type") or _infer_task_type(entry, sent)
        ),
        status=entry.status,
        input_tokens=received.prompt_tokens,
        prompt_tokens=received.prompt_tokens,
        cached_input_tokens=received.cached_tokens,
        reasoning_tokens=received.reasoning_tokens,
        output_tokens=received.completion_tokens,
        total_tokens=received.total_tokens,
        input_cost=float(received_extra.get("input_cost") or sent_extra.get("input_cost") or 0.0),
        cached_cost=float(received_extra.get("cached_cost") or sent_extra.get("cached_cost") or 0.0),
        output_cost=float(received_extra.get("output_cost") or sent_extra.get("output_cost") or 0.0),
        total_cost=float(received_extra.get("total_cost") or sent_extra.get("total_cost") or 0.0),
        pricing_status=str(
            received_extra.get("pricing_status")
            or sent_extra.get("pricing_status")
            or PRICING_STATUS_UNKNOWN
        ),
        estimate_total_cost=float(
            received_extra.get("estimate_total_cost")
            or sent_extra.get("estimate_total_cost")
            or 0.0
        ),
        estimate_delta_cost=float(
            received_extra.get("estimate_delta_cost")
            or sent_extra.get("estimate_delta_cost")
            or 0.0
        ),
        request_ref=build_log_request_ref(entry, log_path),
        success=success,
        error_msg=received.error_message,
        key_id=str(sent_extra.get("key_id", "")),
        profile=str(sent_extra.get("profile", "")),
    )
    return record.to_ledger_row()


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
        self._io_lock = threading.Lock()

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

    def _mirror_completed_entry(self, entry: LogEntry) -> None:
        """Persist a completed API log entry into the shared ledger."""
        if entry.status == LogStatus.PENDING.value:
            return
        if entry.received is None:
            return
        try:
            from .usage_tracker import record_usage_event

            record_usage_event(entry, log_path=self._log_path)
        except Exception:
            logger.debug("Ledger mirror skipped for API log entry", exc_info=True)

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
        self._append_entry_snapshot(entry)
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
        enrich_completed_entry(entry, log_path=self._log_path)
        self._dirty = True
        self._mirror_completed_entry(entry)
        self._append_entry_snapshot(entry)
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
        enrich_completed_entry(entry, log_path=self._log_path)
        self._next_id += 1
        self._entries.append(entry)
        self._dirty = True
        self._mirror_completed_entry(entry)
        self._append_entry_snapshot(entry)
        self._notify(entry)
        return entry.entry_id

    def _append_entry_snapshot(
        self,
        entry: LogEntry,
        *,
        path: Optional[Path] = None,
    ) -> bool:
        """Append one entry snapshot to the JSONL file immediately."""
        target = path or self._log_path
        if target is None:
            return False

        try:
            enrich_completed_entry(entry, log_path=target)
            payload = json.dumps(entry.to_dict(), ensure_ascii=False)
            with self._io_lock:
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "a", encoding="utf-8") as f:
                    f.write(payload)
                    f.write("\n")
                    f.flush()
                    os.fsync(f.fileno())
            return True
        except Exception:
            logger.error("Failed to append API log entry to %s", target, exc_info=True)
            return False

    def _find_entry(self, entry_id: int) -> Optional[LogEntry]:
        """Find an entry by its ID."""
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    def find_entry_by_request_ref(self, request_ref: str) -> Optional[LogEntry]:
        """Resolve a ledger request reference back to the matching log entry."""
        log_name, entry_id = parse_log_request_ref(request_ref)
        if entry_id is None:
            return None

        if log_name not in {None, "api-log"}:
            current_log_name = self._log_path.name if self._log_path is not None else None
            if current_log_name != log_name:
                return None
        return self._find_entry(entry_id)

    def find_entries_by_request_refs(self, request_refs: Sequence[str]) -> List[LogEntry]:
        """Return matching entries for the provided ledger request references."""
        matches: List[LogEntry] = []
        seen_ids: set[int] = set()
        for request_ref in request_refs:
            entry = self.find_entry_by_request_ref(request_ref)
            if entry is None:
                continue
            if entry.entry_id in seen_ids:
                continue
            seen_ids.add(entry.entry_id)
            matches.append(entry)
        return matches

    def entry_to_ledger_row(self, entry: LogEntry) -> Dict[str, Any]:
        """Convert a stored entry into the shared ledger row schema."""
        return build_ledger_row_from_entry(entry, log_path=self._log_path)

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
            with self._io_lock:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    for entry in self._entries:
                        enrich_completed_entry(entry, log_path=target)
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
            entries_by_id: Dict[int, LogEntry] = {}
            entry_order: List[int] = []
            max_id = 0
            with self._io_lock:
                with open(target, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            entry = LogEntry.from_dict(data)
                            if entry.entry_id not in entries_by_id:
                                entry_order.append(entry.entry_id)
                            entries_by_id[entry.entry_id] = entry
                            if entry.entry_id > max_id:
                                max_id = entry.entry_id
                        except (json.JSONDecodeError, KeyError, TypeError):
                            logger.debug("Skipping corrupt log line")
            self._entries = [entries_by_id[entry_id] for entry_id in entry_order]
            self._next_id = max_id + 1
            self._dirty = False
            self._log_path = target
            logger.debug("Loaded API log: %s (%d entries)", target, len(self._entries))
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
