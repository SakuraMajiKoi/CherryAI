"""Usage Analytics tracker for CherryAI.

TASK 17.5: Granular, SQLite-backed usage database that records every
API request with metadata (timestamp, model, key, profile, task type,
tokens, cost).

Provides query helpers for analytics dashboards and CSV export.

Task Types
----------
- ``api_test``
- ``glossary``
- ``game_summary``
- ``translation``
- ``tlc``
- ``editing``
"""

from __future__ import annotations

import csv
import io
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cherryai.usage")

_DB_PATH = "user/usage.db"

# Recognised task types
TASK_TYPES = frozenset({
    "api_test",
    "glossary",
    "game_summary",
    "translation",
    "tlc",
    "editing",
})


@dataclass
class UsageRecord:
    """A single API usage event."""

    timestamp: float = 0.0
    model: str = ""
    key_id: str = ""
    profile: str = ""
    task_type: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    provider: str = ""
    success: bool = True
    error_msg: str = ""


# -----------------------------------------------------------------------
# Database helpers
# -----------------------------------------------------------------------

def _db_path() -> Path:
    return Path(_DB_PATH)


def _connect() -> sqlite3.Connection:
    """Open (and optionally create) the usage database."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the usage table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  REAL    NOT NULL,
            model      TEXT    NOT NULL DEFAULT '',
            key_id     TEXT    NOT NULL DEFAULT '',
            profile    TEXT    NOT NULL DEFAULT '',
            task_type  TEXT    NOT NULL DEFAULT '',
            prompt_tokens     INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens      INTEGER NOT NULL DEFAULT 0,
            cost       REAL    NOT NULL DEFAULT 0.0,
            provider   TEXT    NOT NULL DEFAULT '',
            success    INTEGER NOT NULL DEFAULT 1,
            error_msg  TEXT    NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_timestamp
        ON usage (timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_model
        ON usage (model)
    """)
    conn.commit()


# -----------------------------------------------------------------------
# Write
# -----------------------------------------------------------------------

def record_usage(rec: UsageRecord) -> int:
    """Insert a usage record.  Returns the row ID."""
    if rec.timestamp <= 0:
        rec.timestamp = time.time()
    conn = _connect()
    cur = conn.execute(
        """
        INSERT INTO usage
            (timestamp, model, key_id, profile, task_type,
             prompt_tokens, completion_tokens, total_tokens,
             cost, provider, success, error_msg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rec.timestamp,
            rec.model,
            rec.key_id,
            rec.profile,
            rec.task_type,
            rec.prompt_tokens,
            rec.completion_tokens,
            rec.total_tokens,
            rec.cost,
            rec.provider,
            1 if rec.success else 0,
            rec.error_msg,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


# -----------------------------------------------------------------------
# Read / query
# -----------------------------------------------------------------------

def _rows_to_dicts(
    cursor: sqlite3.Cursor,
) -> List[Dict[str, Any]]:
    """Convert cursor rows to list of dicts."""
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def query_usage(
    *,
    model: Optional[str] = None,
    key_id: Optional[str] = None,
    profile: Optional[str] = None,
    task_type: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """Query usage records with optional filters.

    Args:
        model: Filter by model name.
        key_id: Filter by key ID.
        profile: Filter by API profile.
        task_type: Filter by task type.
        since: Unix timestamp lower bound (inclusive).
        until: Unix timestamp upper bound (inclusive).
        limit: Max rows to return.

    Returns:
        List of usage record dicts, newest first.
    """
    conn = _connect()
    clauses: List[str] = []
    params: List[Any] = []

    if model:
        clauses.append("model = ?")
        params.append(model)
    if key_id:
        clauses.append("key_id = ?")
        params.append(key_id)
    if profile:
        clauses.append("profile = ?")
        params.append(profile)
    if task_type:
        clauses.append("task_type = ?")
        params.append(task_type)
    if since is not None:
        clauses.append("timestamp >= ?")
        params.append(since)
    if until is not None:
        clauses.append("timestamp <= ?")
        params.append(until)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM usage {where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(sql, params)
    rows = _rows_to_dicts(cur)
    conn.close()
    return rows


def usage_summary(
    *,
    group_by: str = "model",
    since: Optional[float] = None,
    until: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Aggregate usage grouped by a column.

    Args:
        group_by: Column to group by (model, key_id, profile, task_type).
        since: Optional start timestamp.
        until: Optional end timestamp.

    Returns:
        List of dicts with group key, total_requests, total_tokens,
        total_cost.
    """
    allowed = {"model", "key_id", "profile", "task_type", "provider"}
    if group_by not in allowed:
        group_by = "model"

    conn = _connect()
    clauses: List[str] = []
    params: List[Any] = []
    if since is not None:
        clauses.append("timestamp >= ?")
        params.append(since)
    if until is not None:
        clauses.append("timestamp <= ?")
        params.append(until)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    sql = f"""
        SELECT
            {group_by}                          AS group_key,
            COUNT(*)                            AS total_requests,
            SUM(prompt_tokens)                  AS total_prompt_tokens,
            SUM(completion_tokens)              AS total_completion_tokens,
            SUM(total_tokens)                   AS total_tokens,
            SUM(cost)                           AS total_cost
        FROM usage
        {where}
        GROUP BY {group_by}
        ORDER BY total_cost DESC
    """
    cur = conn.execute(sql, params)
    rows = _rows_to_dicts(cur)
    conn.close()
    return rows


def total_cost(since: Optional[float] = None) -> float:
    """Return total cost across all usage (optionally since a timestamp)."""
    conn = _connect()
    if since is not None:
        cur = conn.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM usage WHERE timestamp >= ?",
            (since,),
        )
    else:
        cur = conn.execute("SELECT COALESCE(SUM(cost), 0) FROM usage")
    val = cur.fetchone()[0]
    conn.close()
    return float(val)


def total_tokens(since: Optional[float] = None) -> int:
    """Return total tokens consumed (optionally since a timestamp)."""
    conn = _connect()
    if since is not None:
        cur = conn.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM usage WHERE timestamp >= ?",
            (since,),
        )
    else:
        cur = conn.execute("SELECT COALESCE(SUM(total_tokens), 0) FROM usage")
    val = cur.fetchone()[0]
    conn.close()
    return int(val)


# -----------------------------------------------------------------------
# Export
# -----------------------------------------------------------------------

def export_csv(
    *,
    since: Optional[float] = None,
    until: Optional[float] = None,
) -> str:
    """Export usage records to CSV string.

    Returns:
        A CSV-formatted string with headers.
    """
    rows = query_usage(since=since, until=until, limit=100_000)
    if not rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# -----------------------------------------------------------------------
# Maintenance
# -----------------------------------------------------------------------

def purge_before(timestamp: float) -> int:
    """Delete records older than *timestamp*.  Returns count deleted."""
    conn = _connect()
    cur = conn.execute("DELETE FROM usage WHERE timestamp < ?", (timestamp,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


def record_count() -> int:
    """Return total number of usage records."""
    conn = _connect()
    cur = conn.execute("SELECT COUNT(*) FROM usage")
    count = cur.fetchone()[0]
    conn.close()
    return count
