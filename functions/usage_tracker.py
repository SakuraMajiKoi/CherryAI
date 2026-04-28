"""Usage analytics tracker for CherryAI.

TASK 17.5 originally used SQLite as a live store. The live backend is now a
tab-delimited ledger at ``user/ledger.tsv`` while ``user/usage.db`` is treated
as legacy input for one-time migration only.

Public query and aggregation helpers remain available so GUI and future Ledger
surfaces can reuse the same analytics layer.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger("cherryai.usage")

_DEFAULT_DB_PATH = "user/usage.db"
_DEFAULT_LEDGER_PATH = "user/ledger.tsv"
_DB_PATH = "user/usage.db"
_LEDGER_PATH = "user/ledger.tsv"
LEDGER_SCHEMA_VERSION = "1"

GROUP_BY_DEFAULT = "model"
GROUP_BY_REQUEST = "request"

_GROUP_BY_ALIASES = {
    "day": "day",
    "key": "key_id",
    "key_id": "key_id",
    "model": "model",
    "profile": "profile",
    "project": "project_name",
    "project_day": "project_day",
    "project_name": "project_name",
    "project_then_day": "project_day",
    "provider": "provider",
    "request": GROUP_BY_REQUEST,
    "status": "status",
    "task": "task_type",
    "task_type": "task_type",
    "ungrouped": GROUP_BY_REQUEST,
    "ungrouped_requests": GROUP_BY_REQUEST,
}

DATE_PRESET_LABELS = {
    "all time": "all_time",
    "all_time": "all_time",
    "today": "today",
    "7 days": "7_days",
    "7_days": "7_days",
    "30 days": "30_days",
    "30_days": "30_days",
    "this month": "this_month",
    "this_month": "this_month",
}

# Recognised task types
TASK_TYPES = frozenset({
    "api_test",
    "gender_inference",
    "glossary",
    "game_summary",
    "translation",
    "tlc",
    "editing",
})

LEDGER_COLUMNS = [
    "schema_version",
    "timestamp",
    "project_name",
    "provider",
    "model",
    "task_type",
    "status",
    "input_tokens",
    "prompt_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "output_tokens",
    "total_tokens",
    "input_cost",
    "cached_cost",
    "output_cost",
    "total_cost",
    "pricing_status",
    "estimate_total_cost",
    "estimate_delta_cost",
    "request_ref",
    "key_id",
    "profile",
    "success",
    "error_msg",
]

_INT_FIELDS = {
    "input_tokens",
    "prompt_tokens",
    "cached_input_tokens",
    "reasoning_tokens",
    "output_tokens",
    "total_tokens",
    "success",
}
_FLOAT_FIELDS = {
    "timestamp",
    "input_cost",
    "cached_cost",
    "output_cost",
    "total_cost",
    "estimate_total_cost",
    "estimate_delta_cost",
}


@dataclass
class UsageRecord:
    """A single usage event normalized into the ledger schema."""

    timestamp: float = 0.0
    project_name: str = ""
    provider: str = ""
    model: str = ""
    task_type: str = ""
    status: str = ""
    input_tokens: int = 0
    prompt_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost: float = 0.0
    cached_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    pricing_status: str = "unknown"
    estimate_total_cost: float = 0.0
    estimate_delta_cost: float = 0.0
    request_ref: str = ""
    key_id: str = ""
    profile: str = ""
    success: bool = True
    error_msg: str = ""

    # Legacy caller compatibility fields.
    completion_tokens: int = 0
    cost: float = 0.0

    def to_ledger_row(self) -> Dict[str, Any]:
        """Return a canonical ledger row dictionary."""
        return normalize_usage_record(self)


def _ledger_path() -> Path:
    if _LEDGER_PATH == _DEFAULT_LEDGER_PATH and _DB_PATH != _DEFAULT_DB_PATH:
        return Path(_DB_PATH).with_name("ledger.tsv")
    return Path(_LEDGER_PATH)


def _legacy_db_path() -> Path:
    return Path(_DB_PATH)


def _coerce_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def _coerce_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_str(value: Any) -> str:
    if value in (None,):
        return ""
    return str(value)


def _parse_datetime_value(
    value: Optional[Any],
    *,
    end_of_day: bool = False,
) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = _coerce_str(value).strip()
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        pass

    normalized = text.replace("Z", "+00:00")
    parsed: Optional[dt.datetime] = None

    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = dt.datetime.strptime(text, fmt)
                if fmt == "%Y-%m-%d" and end_of_day:
                    parsed = parsed.replace(hour=23, minute=59, second=59)
                break
            except ValueError:
                continue

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.timestamp()


def resolve_date_preset(
    preset: Optional[str],
    *,
    now: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """Resolve a date preset into a (since, until) tuple."""
    normalized = DATE_PRESET_LABELS.get(_coerce_str(preset).strip().lower(), "all_time")
    if normalized == "all_time":
        return None, None

    current = dt.datetime.fromtimestamp(now or time.time(), tz=dt.timezone.utc)
    if normalized == "today":
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), None
    if normalized == "7_days":
        return (current - dt.timedelta(days=7)).timestamp(), None
    if normalized == "30_days":
        return (current - dt.timedelta(days=30)).timestamp(), None
    if normalized == "this_month":
        start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), None
    return None, None


def _normalize_group_by(group_by: str) -> str:
    normalized = _coerce_str(group_by).strip().lower()
    return _GROUP_BY_ALIASES.get(normalized, GROUP_BY_DEFAULT)


def _group_key_for_row(row: Mapping[str, Any], group_by: str) -> Tuple[str, str]:
    if group_by == GROUP_BY_REQUEST:
        request_ref = _coerce_str(row.get("request_ref"))
        if request_ref:
            return request_ref, request_ref
        timestamp = _coerce_float(row.get("timestamp"))
        fallback = f"row:{timestamp:.6f}"
        return fallback, fallback

    if group_by == "day":
        label = dt.datetime.fromtimestamp(
            _coerce_float(row.get("timestamp")) or 0.0,
            tz=dt.timezone.utc,
        ).strftime("%Y-%m-%d")
        return label, label

    if group_by == "project_day":
        project_name = _coerce_str(row.get("project_name")) or "(No Project)"
        day_label = dt.datetime.fromtimestamp(
            _coerce_float(row.get("timestamp")) or 0.0,
            tz=dt.timezone.utc,
        ).strftime("%Y-%m-%d")
        key = f"{project_name}\t{day_label}"
        return key, f"{project_name} | {day_label}"

    label = _coerce_str(row.get(group_by))
    if not label:
        label = "(blank)"
    return label, label


def _merge_group_text(bucket: Dict[str, Any], field: str, value: Any) -> None:
    clean = _coerce_str(value)
    if not clean:
        return
    current = _coerce_str(bucket.get(field))
    if not current:
        bucket[field] = clean
        return
    if current != clean and current != "(multiple)":
        bucket[field] = "(multiple)"


def _build_group_bucket(group_by: str, group_key: str, group_label: str) -> Dict[str, Any]:
    return {
        "group_by": group_by,
        "group_key": group_key,
        "group_label": group_label,
        "request_count": 0,
        "total_requests": 0,
        "success_count": 0,
        "failed_count": 0,
        "success_rate": 0.0,
        "first_timestamp": 0.0,
        "last_timestamp": 0.0,
        "request_refs": [],
        "project_name": "",
        "provider": "",
        "model": "",
        "task_type": "",
        "status": "",
        "key_id": "",
        "profile": "",
        "pricing_status": "",
        "input_tokens": 0,
        "prompt_tokens": 0,
        "cached_input_tokens": 0,
        "reasoning_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "input_cost": 0.0,
        "cached_cost": 0.0,
        "output_cost": 0.0,
        "total_cost": 0.0,
        "estimate_total_cost": 0.0,
        "estimate_delta_cost": 0.0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "unknown_pricing_count": 0,
    }


def _build_totals(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "total_requests": 0,
            "total_cost": 0.0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "success_rate": 0.0,
            "unknown_pricing_count": 0,
            "estimate_total_cost": 0.0,
            "estimate_delta_cost": 0.0,
            "actual_minus_estimate": 0.0,
            "start_timestamp": None,
            "end_timestamp": None,
        }

    total_requests = len(rows)
    total_cost_value = 0.0
    total_tokens_value = 0
    cached_tokens_value = 0
    reasoning_tokens_value = 0
    success_count = 0
    unknown_pricing_count = 0
    estimate_total_cost_value = 0.0
    estimate_delta_cost_value = 0.0
    timestamps: List[float] = []

    for row in rows:
        total_cost_value += _coerce_float(row.get("total_cost"))
        total_tokens_value += _coerce_int(row.get("total_tokens"))
        cached_tokens_value += _coerce_int(row.get("cached_input_tokens"))
        reasoning_tokens_value += _coerce_int(row.get("reasoning_tokens"))
        estimate_total_cost_value += _coerce_float(row.get("estimate_total_cost"))
        estimate_delta_cost_value += _coerce_float(row.get("estimate_delta_cost"))
        if _coerce_int(row.get("success")):
            success_count += 1
        if _coerce_str(row.get("pricing_status")).strip().lower() == "unknown":
            unknown_pricing_count += 1
        timestamp = _coerce_float(row.get("timestamp"))
        if timestamp:
            timestamps.append(timestamp)

    return {
        "total_requests": total_requests,
        "total_cost": total_cost_value,
        "total_tokens": total_tokens_value,
        "cached_tokens": cached_tokens_value,
        "reasoning_tokens": reasoning_tokens_value,
        "success_rate": (success_count / total_requests * 100.0) if total_requests else 0.0,
        "unknown_pricing_count": unknown_pricing_count,
        "estimate_total_cost": estimate_total_cost_value,
        "estimate_delta_cost": estimate_delta_cost_value,
        "actual_minus_estimate": total_cost_value - estimate_total_cost_value,
        "start_timestamp": min(timestamps) if timestamps else None,
        "end_timestamp": max(timestamps) if timestamps else None,
    }


def _normalize_status(status: str, *, success: bool, error_msg: str) -> str:
    clean_status = (status or "").strip().lower()
    if clean_status:
        return clean_status
    if not success or error_msg:
        return "failed"
    return "success"


def normalize_usage_record(rec: UsageRecord) -> Dict[str, Any]:
    """Convert a record into the canonical ledger row shape."""
    timestamp = rec.timestamp if rec.timestamp > 0 else time.time()
    prompt_tokens = _coerce_int(rec.prompt_tokens)
    input_tokens = _coerce_int(rec.input_tokens) or prompt_tokens
    output_tokens = _coerce_int(rec.output_tokens) or _coerce_int(rec.completion_tokens)
    total_tokens = _coerce_int(rec.total_tokens) or (input_tokens + output_tokens)
    total_cost = _coerce_float(rec.total_cost) or _coerce_float(rec.cost)
    success = bool(rec.success)
    error_msg = _coerce_str(rec.error_msg)
    status = _normalize_status(rec.status, success=success, error_msg=error_msg)

    row = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "timestamp": float(timestamp),
        "project_name": _coerce_str(rec.project_name),
        "provider": _coerce_str(rec.provider),
        "model": _coerce_str(rec.model),
        "task_type": _coerce_str(rec.task_type),
        "status": status,
        "input_tokens": input_tokens,
        "prompt_tokens": prompt_tokens,
        "cached_input_tokens": _coerce_int(rec.cached_input_tokens),
        "reasoning_tokens": _coerce_int(rec.reasoning_tokens),
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "input_cost": _coerce_float(rec.input_cost),
        "cached_cost": _coerce_float(rec.cached_cost),
        "output_cost": _coerce_float(rec.output_cost),
        "total_cost": total_cost,
        "pricing_status": _coerce_str(rec.pricing_status) or "unknown",
        "estimate_total_cost": _coerce_float(rec.estimate_total_cost),
        "estimate_delta_cost": _coerce_float(rec.estimate_delta_cost),
        "request_ref": _coerce_str(rec.request_ref),
        "key_id": _coerce_str(rec.key_id),
        "profile": _coerce_str(rec.profile),
        "success": 1 if success else 0,
        "error_msg": error_msg,
    }
    return row


def _normalize_ledger_row(raw_row: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    for column in LEDGER_COLUMNS:
        value = raw_row.get(column, "")
        if column in _INT_FIELDS:
            row[column] = _coerce_int(value)
        elif column in _FLOAT_FIELDS:
            row[column] = _coerce_float(value)
        else:
            row[column] = _coerce_str(value)

    if not row["status"]:
        row["status"] = _normalize_status(
            "",
            success=bool(row["success"]),
            error_msg=_coerce_str(row["error_msg"]),
        )

    if not row["input_tokens"]:
        row["input_tokens"] = row["prompt_tokens"]
    if not row["total_tokens"]:
        row["total_tokens"] = row["input_tokens"] + row["output_tokens"]

    row["completion_tokens"] = row["output_tokens"]
    row["cost"] = row["total_cost"]
    return row


def _serialize_ledger_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_ledger_row(row)
    serialized: Dict[str, Any] = {}
    for column in LEDGER_COLUMNS:
        value = normalized[column]
        if column in _INT_FIELDS:
            serialized[column] = str(_coerce_int(value))
        elif column in _FLOAT_FIELDS:
            serialized[column] = str(_coerce_float(value))
        else:
            serialized[column] = _coerce_str(value)
    return serialized


def _ensure_ledger_file() -> None:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=LEDGER_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()


def _append_ledger_rows(rows: Iterable[Dict[str, Any]]) -> None:
    row_list = list(rows)
    if not row_list:
        return
    _ensure_ledger_file()
    with _ledger_path().open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=LEDGER_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
        )
        for row in row_list:
            writer.writerow(_serialize_ledger_row(row))


def _rewrite_ledger_rows(rows: Iterable[Dict[str, Any]]) -> None:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=LEDGER_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(_serialize_ledger_row(row))
    tmp_path.replace(path)


def _read_ledger_rows() -> List[Dict[str, Any]]:
    _maybe_migrate_legacy_db()
    path = _ledger_path()
    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            return []
        rows = []
        for raw_row in reader:
            if raw_row is None:
                continue
            if not any(value not in (None, "") for value in raw_row.values()):
                continue
            rows.append(_normalize_ledger_row(raw_row))
        return rows


def _legacy_usage_rows() -> List[Dict[str, Any]]:
    path = _legacy_db_path()
    if not path.exists():
        return []

    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    id,
                    timestamp,
                    model,
                    key_id,
                    profile,
                    task_type,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost,
                    provider,
                    success,
                    error_msg
                FROM usage
                ORDER BY id ASC
                """
            ).fetchall()
    except sqlite3.Error:
        logger.warning("Failed to read legacy usage.db for migration", exc_info=True)
        return []

    migrated: List[Dict[str, Any]] = []
    for row in rows:
        record = UsageRecord(
            timestamp=_coerce_float(row["timestamp"]),
            provider=_coerce_str(row["provider"]),
            model=_coerce_str(row["model"]),
            task_type=_coerce_str(row["task_type"]),
            prompt_tokens=_coerce_int(row["prompt_tokens"]),
            completion_tokens=_coerce_int(row["completion_tokens"]),
            total_tokens=_coerce_int(row["total_tokens"]),
            cost=_coerce_float(row["cost"]),
            key_id=_coerce_str(row["key_id"]),
            profile=_coerce_str(row["profile"]),
            success=bool(_coerce_int(row["success"])),
            error_msg=_coerce_str(row["error_msg"]),
            request_ref=f"legacy-sqlite:{_coerce_int(row['id'])}",
        )
        migrated.append(normalize_usage_record(record))
    return migrated


def _maybe_migrate_legacy_db() -> None:
    legacy_path = _legacy_db_path()
    if not legacy_path.exists():
        return

    legacy_rows = _legacy_usage_rows()
    if not legacy_rows:
        return

    existing_rows: List[Dict[str, Any]] = []
    existing_refs: set[str] = set()
    ledger_path = _ledger_path()
    if ledger_path.exists() and ledger_path.stat().st_size > 0:
        existing_rows = _read_ledger_rows_without_migration()
        existing_refs = {
            row["request_ref"] for row in existing_rows if _coerce_str(row["request_ref"])
        }

    pending_rows = [
        row for row in legacy_rows if _coerce_str(row["request_ref"]) not in existing_refs
    ]
    if pending_rows:
        _append_ledger_rows(pending_rows)


def _read_ledger_rows_without_migration() -> List[Dict[str, Any]]:
    path = _ledger_path()
    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = []
        for raw_row in reader:
            if raw_row is None:
                continue
            if not any(value not in (None, "") for value in raw_row.values()):
                continue
            rows.append(_normalize_ledger_row(raw_row))
        return rows


def _filter_rows(
    rows: Iterable[Dict[str, Any]],
    *,
    project_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    key_id: Optional[str] = None,
    profile: Optional[str] = None,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    request_refs: Optional[Sequence[str]] = None,
    search_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ref_filter = {
        _coerce_str(ref) for ref in (request_refs or []) if _coerce_str(ref)
    }
    search_lower = _coerce_str(search_text).strip().lower()
    result = []
    for row in rows:
        if project_name and row["project_name"] != project_name:
            continue
        if provider and row["provider"] != provider:
            continue
        if model and row["model"] != model:
            continue
        if key_id and row["key_id"] != key_id:
            continue
        if profile and row["profile"] != profile:
            continue
        if task_type and row["task_type"] != task_type:
            continue
        if status and row["status"] != status:
            continue
        if since is not None and row["timestamp"] < since:
            continue
        if until is not None and row["timestamp"] > until:
            continue
        if ref_filter and _coerce_str(row["request_ref"]) not in ref_filter:
            continue
        if search_lower:
            haystack = " ".join(
                [
                    _coerce_str(row.get("project_name")),
                    _coerce_str(row.get("provider")),
                    _coerce_str(row.get("model")),
                    _coerce_str(row.get("task_type")),
                    _coerce_str(row.get("status")),
                    _coerce_str(row.get("pricing_status")),
                    _coerce_str(row.get("request_ref")),
                    _coerce_str(row.get("key_id")),
                    _coerce_str(row.get("profile")),
                    _coerce_str(row.get("error_msg")),
                ]
            ).lower()
            if search_lower not in haystack:
                continue
        result.append(row)
    return result


def _coerce_event_row(
    event: Any,
    *,
    log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if isinstance(event, UsageRecord):
        return normalize_usage_record(event)
    if isinstance(event, Mapping):
        return _normalize_ledger_row(dict(event))

    try:
        from .api_log import LogEntry, build_ledger_row_from_entry
    except ImportError as exc:  # pragma: no cover - defensive fallback
        raise TypeError("Unsupported ledger event type") from exc

    if isinstance(event, LogEntry):
        return _normalize_ledger_row(build_ledger_row_from_entry(event, log_path=log_path))

    raise TypeError(f"Unsupported ledger event type: {type(event)!r}")


def _append_unique_ledger_row(row: Dict[str, Any]) -> int:
    _maybe_migrate_legacy_db()
    existing_rows = _read_ledger_rows_without_migration()
    request_ref = _coerce_str(row.get("request_ref"))
    if request_ref:
        for index, existing in enumerate(existing_rows, start=1):
            if _coerce_str(existing.get("request_ref")) == request_ref:
                return index

    _append_ledger_rows([row])
    return len(existing_rows) + 1


def record_usage_event(
    event: Any,
    *,
    log_path: Optional[Path] = None,
) -> int:
    """Persist one ledger row from a canonical row, UsageRecord, or API Log entry."""
    row = _coerce_event_row(event, log_path=log_path)
    request_ref = _coerce_str(row.get("request_ref"))
    if not request_ref and not _coerce_float(row.get("timestamp")):
        row["timestamp"] = time.time()
    return _append_unique_ledger_row(row)


def record_usage(rec: UsageRecord) -> int:
    """Append a usage record to the canonical TSV ledger and return its row id."""
    return record_usage_event(rec)


def query_usage(
    *,
    project_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    key_id: Optional[str] = None,
    profile: Optional[str] = None,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    date_preset: Optional[str] = None,
    request_refs: Optional[Sequence[str]] = None,
    search_text: Optional[str] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """Query usage rows with optional filters, newest first."""
    if date_preset:
        preset_since, preset_until = resolve_date_preset(date_preset)
        if since is None:
            since = preset_since
        if until is None:
            until = preset_until

    since = _parse_datetime_value(since)
    until = _parse_datetime_value(until, end_of_day=True)
    rows = _filter_rows(
        _read_ledger_rows(),
        project_name=project_name,
        provider=provider,
        model=model,
        key_id=key_id,
        profile=profile,
        task_type=task_type,
        since=since,
        until=until,
        status=status,
        request_refs=request_refs,
        search_text=search_text,
    )
    rows.sort(key=lambda row: row["timestamp"], reverse=True)
    if limit < 0:
        limit = 0
    return rows[:limit]


def usage_summary(
    *,
    group_by: str = "model",
    project_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    key_id: Optional[str] = None,
    profile: Optional[str] = None,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    date_preset: Optional[str] = None,
    request_refs: Optional[Sequence[str]] = None,
    search_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Aggregate usage grouped by a supported column."""
    normalized_group_by = _normalize_group_by(group_by)
    rows = query_usage(
        project_name=project_name,
        provider=provider,
        model=model,
        key_id=key_id,
        profile=profile,
        task_type=task_type,
        status=status,
        since=since,
        until=until,
        date_preset=date_preset,
        request_refs=request_refs,
        search_text=search_text,
        limit=100_000,
    )

    groups: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        group_key, group_label = _group_key_for_row(row, normalized_group_by)
        bucket = groups.setdefault(
            group_key,
            _build_group_bucket(normalized_group_by, group_key, group_label),
        )

        bucket["request_count"] += 1
        bucket["total_requests"] = bucket["request_count"]
        if _coerce_int(row.get("success")):
            bucket["success_count"] += 1
        else:
            bucket["failed_count"] += 1

        timestamp = _coerce_float(row.get("timestamp"))
        if not bucket["first_timestamp"] or timestamp < bucket["first_timestamp"]:
            bucket["first_timestamp"] = timestamp
        if timestamp > bucket["last_timestamp"]:
            bucket["last_timestamp"] = timestamp

        request_ref = _coerce_str(row.get("request_ref"))
        if request_ref:
            bucket["request_refs"].append(request_ref)

        if _coerce_str(row.get("pricing_status")).strip().lower() == "unknown":
            bucket["unknown_pricing_count"] += 1

        for field in (
            "project_name",
            "provider",
            "model",
            "task_type",
            "status",
            "key_id",
            "profile",
            "pricing_status",
        ):
            _merge_group_text(bucket, field, row.get(field))

        for field in (
            "input_tokens",
            "prompt_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
            "output_tokens",
            "total_tokens",
        ):
            bucket[field] += _coerce_int(row.get(field))
        for field in (
            "input_cost",
            "cached_cost",
            "output_cost",
            "total_cost",
            "estimate_total_cost",
            "estimate_delta_cost",
        ):
            bucket[field] += _coerce_float(row.get(field))

        bucket["total_prompt_tokens"] = bucket["prompt_tokens"]
        bucket["total_completion_tokens"] = bucket["output_tokens"]

    result = list(groups.values())
    for item in result:
        if item["request_count"]:
            item["success_rate"] = (
                item["success_count"] / item["request_count"] * 100.0
            )

    if normalized_group_by == GROUP_BY_REQUEST:
        result.sort(key=lambda item: item["last_timestamp"], reverse=True)
    else:
        result.sort(
            key=lambda item: (
                item["total_cost"],
                item["last_timestamp"],
                item["group_label"],
            ),
            reverse=True,
        )
    return result


def summarize_usage_totals(
    *,
    project_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    key_id: Optional[str] = None,
    profile: Optional[str] = None,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    date_preset: Optional[str] = None,
    request_refs: Optional[Sequence[str]] = None,
    search_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Return compact totals for Ledger summary widgets."""
    rows = query_usage(
        project_name=project_name,
        provider=provider,
        model=model,
        key_id=key_id,
        profile=profile,
        task_type=task_type,
        status=status,
        since=since,
        until=until,
        date_preset=date_preset,
        request_refs=request_refs,
        search_text=search_text,
        limit=100_000,
    )
    return _build_totals(rows)


def total_cost(since: Optional[float] = None) -> float:
    """Return total cost across all usage rows."""
    return sum(
        _coerce_float(row["total_cost"])
        for row in _filter_rows(_read_ledger_rows(), since=_parse_datetime_value(since))
    )


def total_tokens(since: Optional[float] = None) -> int:
    """Return total tokens across all usage rows."""
    return sum(
        _coerce_int(row["total_tokens"])
        for row in _filter_rows(_read_ledger_rows(), since=_parse_datetime_value(since))
    )


def export_csv(
    *,
    since: Optional[float] = None,
    until: Optional[float] = None,
) -> str:
    """Export queried usage rows as a CSV string."""
    rows = query_usage(since=since, until=until, limit=100_000)
    if not rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def purge_before(timestamp: float) -> int:
    """Delete records older than *timestamp* and return the count deleted."""
    rows = _read_ledger_rows()
    kept_rows = [row for row in rows if row["timestamp"] >= timestamp]
    deleted = len(rows) - len(kept_rows)
    if deleted:
        _rewrite_ledger_rows(kept_rows)
    return deleted


def record_count() -> int:
    """Return the total number of usage rows currently in the ledger."""
    return len(_read_ledger_rows())


__all__ = [
    "DATE_PRESET_LABELS",
    "LEDGER_COLUMNS",
    "LEDGER_SCHEMA_VERSION",
    "TASK_TYPES",
    "UsageRecord",
    "export_csv",
    "normalize_usage_record",
    "purge_before",
    "query_usage",
    "record_count",
    "record_usage",
    "record_usage_event",
    "resolve_date_preset",
    "summarize_usage_totals",
    "total_cost",
    "total_tokens",
    "usage_summary",
]