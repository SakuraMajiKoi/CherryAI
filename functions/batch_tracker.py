"""Batch API tracker for CherryAI.

TASK 17.1: Manages OpenAI-compatible Batch API jobs for cheaper
(~50% discount) asynchronous translation.

Workflow
--------
1. Build JSONL request file from translation chunks.
2. Upload file via Files API (``purpose="batch"``).
3. Create a Batch job pointing at ``/v1/chat/completions``.
4. Poll for status (``validating`` → ``in_progress`` → ``completed``).
5. Download result JSONL and parse translations.

The tracker persists job metadata to ``user/batch_jobs.json`` so that
long-running batches survive application restarts.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cherryai.batch")

# Default storage for batch job metadata
_BATCH_JOBS_FILE = "user/batch_jobs.json"

# Batch API statuses
BATCH_STATUSES_ACTIVE = {"validating", "in_progress", "finalizing"}
BATCH_STATUSES_TERMINAL = {"completed", "failed", "expired", "cancelled"}


@dataclass
class BatchRequest:
    """A single request line inside a JSONL batch file."""

    custom_id: str
    model: str
    messages: List[Dict[str, str]]
    temperature: float = 0.3
    response_format: Optional[Dict[str, str]] = None

    def to_jsonl_line(self) -> str:
        """Serialise to a Batch-API-compatible JSON dict string."""
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
        }
        if self.response_format:
            body["response_format"] = self.response_format
        return json.dumps(
            {
                "custom_id": self.custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": body,
            },
            ensure_ascii=False,
        )


@dataclass
class BatchJob:
    """Persistent metadata for a single batch job."""

    batch_id: str = ""
    input_file_id: str = ""
    output_file_id: str = ""
    error_file_id: str = ""
    status: str = "pending"
    created_at: float = 0.0
    completed_at: float = 0.0
    total_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    model: str = ""
    manifest_path: str = ""
    chunk_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ---- helpers ---------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Return True while the job is still processing."""
        return self.status in BATCH_STATUSES_ACTIVE

    @property
    def is_done(self) -> bool:
        """Return True when the job reached a terminal state."""
        return self.status in BATCH_STATUSES_TERMINAL

    @property
    def is_success(self) -> bool:
        """Return True only if the batch completed successfully."""
        return self.status == "completed"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchJob":
        """Deserialise from a dict, ignoring unknown keys."""
        known = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# -----------------------------------------------------------------------
# Batch job store
# -----------------------------------------------------------------------

def _jobs_path() -> Path:
    """Return the path for the batch-jobs persistence file."""
    return Path(_BATCH_JOBS_FILE)


def load_batch_jobs() -> List[BatchJob]:
    """Load all tracked batch jobs from disk."""
    path = _jobs_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [BatchJob.from_dict(j) for j in raw]
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.warning("Failed to load batch jobs: %s", exc)
        return []


def save_batch_jobs(jobs: List[BatchJob]) -> None:
    """Persist batch jobs to disk."""
    path = _jobs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [j.to_dict() for j in jobs]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def add_batch_job(job: BatchJob) -> None:
    """Append a new job and save."""
    jobs = load_batch_jobs()
    jobs.append(job)
    save_batch_jobs(jobs)


def update_batch_job(batch_id: str, **fields: Any) -> Optional[BatchJob]:
    """Update fields of an existing job by *batch_id*.

    Returns the updated job or ``None`` if not found.
    """
    jobs = load_batch_jobs()
    for job in jobs:
        if job.batch_id == batch_id:
            for key, value in fields.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            save_batch_jobs(jobs)
            return job
    return None


def get_batch_job(batch_id: str) -> Optional[BatchJob]:
    """Retrieve a single job by batch_id."""
    for job in load_batch_jobs():
        if job.batch_id == batch_id:
            return job
    return None


def get_active_jobs() -> List[BatchJob]:
    """Return all jobs that are still processing."""
    return [j for j in load_batch_jobs() if j.is_active]


def get_completed_jobs() -> List[BatchJob]:
    """Return all jobs that have finished (success, failed, or expired)."""
    return [j for j in load_batch_jobs() if j.is_done]


def remove_batch_job(batch_id: str) -> bool:
    """Remove a job from tracking.  Returns True if found and removed."""
    jobs = load_batch_jobs()
    orig_len = len(jobs)
    jobs = [j for j in jobs if j.batch_id != batch_id]
    if len(jobs) < orig_len:
        save_batch_jobs(jobs)
        return True
    return False


# -----------------------------------------------------------------------
# JSONL builder
# -----------------------------------------------------------------------

def build_batch_jsonl(
    chunks: List[List[str]],
    model: str,
    source_lang: str,
    target_lang: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.3,
) -> str:
    """Build a JSONL string for the Batch API.

    Each chunk becomes one request line.  ``custom_id`` encodes the
    zero-based chunk index as ``chunk_NNN``.

    Returns:
        Newline-separated JSON strings ready for upload.
    """
    base_system = (
        f"You are a professional translator translating from {source_lang} "
        f"to {target_lang}.\n"
        "Output must be a valid JSON object with a single key 'translations' "
        "containing an array of strings.\n"
        "The array must have exactly the same number of elements as the "
        "input 'lines' array.\n"
        "Preserve all special tokens like __PROT__ exactly.\n"
        "Do not translate proper names if you are unsure, or follow the "
        "glossary if provided."
    )
    if system_prompt:
        base_system += f"\n\nAdditional Instructions:\n{system_prompt}"

    lines: List[str] = []
    for idx, chunk in enumerate(chunks):
        req = BatchRequest(
            custom_id=f"chunk_{idx:04d}",
            model=model,
            messages=[
                {"role": "system", "content": base_system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"lines": chunk}, ensure_ascii=False,
                    ),
                },
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        lines.append(req.to_jsonl_line())

    return "\n".join(lines)


# -----------------------------------------------------------------------
# Batch result parser
# -----------------------------------------------------------------------

def parse_batch_results(
    result_jsonl: str,
    total_chunks: int,
) -> Dict[int, List[str]]:
    """Parse a Batch API output JSONL into chunk translations.

    Args:
        result_jsonl: Raw JSONL string from the output file.
        total_chunks: Expected number of chunks (for validation).

    Returns:
        Mapping of chunk index → list of translated strings.
        Missing or failed chunks are omitted from the dict.
    """
    translations: Dict[int, List[str]] = {}

    for line in result_jsonl.strip().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping unparseable result line")
            continue

        custom_id: str = entry.get("custom_id", "")
        response = entry.get("response")
        error = entry.get("error")

        if error:
            logger.warning("Batch request %s failed: %s", custom_id, error)
            continue

        if not response or response.get("status_code") != 200:
            logger.warning("Batch request %s non-200: %s", custom_id, response)
            continue

        # Extract chunk index from custom_id "chunk_NNNN"
        try:
            chunk_idx = int(custom_id.split("_")[1])
        except (IndexError, ValueError):
            logger.warning("Cannot parse chunk index from %s", custom_id)
            continue

        # Extract translations from response body
        body = response.get("body", {})
        content = ""
        choices = body.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        if not content:
            logger.warning("Empty content for %s", custom_id)
            continue

        try:
            data = json.loads(content)
            tl_lines = data.get("translations", [])
            if isinstance(tl_lines, list):
                translations[chunk_idx] = [str(t) for t in tl_lines]
            else:
                logger.warning("Non-list translations in %s", custom_id)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON response for %s", custom_id)

    found = len(translations)
    if found < total_chunks:
        logger.warning(
            "Batch results incomplete: got %d/%d chunks",
            found,
            total_chunks,
        )

    return translations


# -----------------------------------------------------------------------
# Batch API helpers (call via OpenAI client)
# -----------------------------------------------------------------------

def submit_batch(
    client: Any,
    jsonl_content: str,
    model: str,
    manifest_path: str = "",
    chunk_ids: Optional[List[str]] = None,
) -> BatchJob:
    """Upload JSONL and create a Batch API job.

    Args:
        client: An initialised ``openai.OpenAI`` instance.
        jsonl_content: The JSONL request body.
        model: Model name (for metadata).
        manifest_path: Optional project manifest path.
        chunk_ids: Optional list of custom_ids in the file.

    Returns:
        A :class:`BatchJob` with metadata filled in.
    """
    import io

    # 1. Upload the input file
    file_obj = client.files.create(
        file=io.BytesIO(jsonl_content.encode("utf-8")),
        purpose="batch",
    )
    logger.info("Uploaded batch input file: %s", file_obj.id)

    # 2. Create the batch
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    logger.info("Created batch: %s (status=%s)", batch.id, batch.status)

    # 3. Build tracking object
    total_requests = len(jsonl_content.strip().splitlines())
    job = BatchJob(
        batch_id=batch.id,
        input_file_id=file_obj.id,
        status=batch.status,
        created_at=time.time(),
        total_requests=total_requests,
        model=model,
        manifest_path=manifest_path,
        chunk_ids=chunk_ids or [],
    )
    add_batch_job(job)
    return job


def poll_batch_status(client: Any, batch_id: str) -> BatchJob:
    """Fetch the latest status of a batch from the API.

    Updates the persisted :class:`BatchJob` and returns it.
    """
    batch = client.batches.retrieve(batch_id)

    request_counts = getattr(batch, "request_counts", None)
    completed = getattr(request_counts, "completed", 0) if request_counts else 0
    failed = getattr(request_counts, "failed", 0) if request_counts else 0

    updates: Dict[str, Any] = {
        "status": batch.status,
        "completed_requests": completed,
        "failed_requests": failed,
    }

    if batch.output_file_id:
        updates["output_file_id"] = batch.output_file_id
    if batch.error_file_id:
        updates["error_file_id"] = batch.error_file_id
    if batch.status in BATCH_STATUSES_TERMINAL and not updates.get("completed_at"):
        updates["completed_at"] = time.time()

    job = update_batch_job(batch_id, **updates)
    if job is None:
        # Not tracked locally — create a stub
        job = BatchJob(batch_id=batch_id, **updates)
    return job


def retrieve_batch_results(client: Any, batch_id: str) -> Optional[str]:
    """Download the output JSONL for a completed batch.

    Returns:
        Raw JSONL string, or None if the output is not yet available.
    """
    job = get_batch_job(batch_id)
    output_file_id = job.output_file_id if job else ""

    if not output_file_id:
        # Try fetching from API
        batch = client.batches.retrieve(batch_id)
        output_file_id = batch.output_file_id or ""
        if not output_file_id:
            logger.info("Batch %s has no output file yet", batch_id)
            return None

    content = client.files.content(output_file_id)
    return content.text


def cancel_batch(client: Any, batch_id: str) -> BatchJob:
    """Cancel an in-progress batch.

    Returns the updated :class:`BatchJob`.
    """
    client.batches.cancel(batch_id)
    logger.info("Cancelled batch %s", batch_id)
    return poll_batch_status(client, batch_id)


def list_provider_batches(client: Any, limit: int = 20) -> List[Dict[str, Any]]:
    """List recent batches from the provider for informational display."""
    result: List[Dict[str, Any]] = []
    try:
        batches = client.batches.list(limit=limit)
        for b in batches:
            result.append({
                "id": b.id,
                "status": b.status,
                "created_at": b.created_at,
                "model": getattr(b, "model", ""),
                "total": getattr(
                    getattr(b, "request_counts", None), "total", 0,
                ),
            })
    except Exception as exc:
        logger.warning("Failed to list provider batches: %s", exc)
    return result
