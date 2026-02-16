"""Agent-Assisted Modes for CherryAI (TASK 17.8).

Provides a small mode registry with metadata (name, system prompt template,
default read/write capabilities) and a safe execution wrapper for LLM API calls.

This module is optional — the rest of the app runs without API credentials.
When credentials are absent, agent modes degrade gracefully.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SANDBOX_DIR = "dev/sandbox"
AGENT_LOG_DIR = "logs/agent"

# Files agents may read by default (relative to project root).
DOC_READ_PATHS: Set[str] = {
    "doc/features.md",
    "doc/technical.md",
    "doc/specs.md",
    "doc/cli_guide.md",
    "doc/local_llm_guide.md",
    "config/base_instructions.txt",
    "config/prompt.txt",
}

DEV_READ_PATHS: Set[str] = {
    "formats/",
    "functions/",
    "doc/",
}


class ReadScope(str, Enum):
    """What files a mode is allowed to read."""
    NONE = "none"
    DOCS = "docs"
    PROJECT = "project"
    ALL = "all"


class WriteScope(str, Enum):
    """What a mode is allowed to write."""
    NONE = "none"
    SUGGESTIONS = "suggestions"
    SANDBOX = "sandbox"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentMode:
    """Defines a single agent mode with its metadata and capabilities."""

    name: str
    display_name: str
    description: str
    system_prompt_template: str
    default_read_scope: ReadScope = ReadScope.DOCS
    default_write_scope: WriteScope = WriteScope.NONE
    icon: str = ""  # Optional emoji / icon hint for UI

    def build_system_prompt(self, context: Optional[Dict[str, str]] = None) -> str:
        """Render the system prompt template with optional context variables."""
        prompt = self.system_prompt_template
        if context:
            for key, value in context.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", value)
        return prompt


@dataclass
class AgentRequest:
    """A single request to be sent to the agent."""

    mode: str
    user_message: str
    context_snippets: List[str] = field(default_factory=list)
    read_scope: Optional[ReadScope] = None
    write_scope: Optional[WriteScope] = None


@dataclass
class AgentResponse:
    """Structured response from an agent call."""

    content: str = ""
    suggested_files: Dict[str, str] = field(default_factory=dict)
    commands: List[str] = field(default_factory=list)
    model: str = ""
    tokens_used: int = 0
    cost: float = 0.0
    error: str = ""
    success: bool = True


@dataclass
class AuditEntry:
    """Audit trail entry for agent operations."""

    timestamp: float = 0.0
    mode: str = ""
    user_message_hash: str = ""
    read_scope: str = ""
    write_scope: str = ""
    files_written: List[str] = field(default_factory=list)
    model: str = ""
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "user_message_hash": self.user_message_hash,
            "read_scope": self.read_scope,
            "write_scope": self.write_scope,
            "files_written": self.files_written,
            "model": self.model,
            "tokens_used": self.tokens_used,
        }


# ---------------------------------------------------------------------------
# Built-in mode definitions
# ---------------------------------------------------------------------------

INTERACTIVE_HELP = AgentMode(
    name="interactive_help",
    display_name="Interactive Help",
    description=(
        "An assistant configured as an interactive help system for CherryAI. "
        "Answers contextual questions about configuration and usage."
    ),
    system_prompt_template=(
        "You are the CherryAI Interactive Help assistant.\n"
        "You have access to the following documentation:\n"
        "{{docs_context}}\n\n"
        "Answer user questions about CherryAI configuration, usage, and features. "
        "Be concise, accurate, and reference specific config file locations when relevant."
    ),
    default_read_scope=ReadScope.DOCS,
    default_write_scope=WriteScope.NONE,
    icon="❓",
)

LANGUAGE_ASSISTANT = AgentMode(
    name="language_assistant",
    display_name="Language Assistant",
    description=(
        "A language-focused agent that analyzes and suggests language improvements, "
        "provides localized guidance, and operates on selected text context."
    ),
    system_prompt_template=(
        "You are the CherryAI Language Assistant.\n"
        "You help with language analysis, translation quality review, and "
        "localization suggestions.\n"
        "Selected context:\n{{selected_context}}\n\n"
        "Source language: {{source_lang}}\nTarget language: {{target_lang}}\n\n"
        "Provide precise, actionable language feedback."
    ),
    default_read_scope=ReadScope.PROJECT,
    default_write_scope=WriteScope.SUGGESTIONS,
    icon="🌐",
)

SCRIPT_AUTHOR = AgentMode(
    name="script_author",
    display_name="Script Author",
    description=(
        "An agent tuned to author new CherryAI scripts — extraction/injection "
        "handlers or format plugins. Writes to dev/sandbox/ only."
    ),
    system_prompt_template=(
        "You are the CherryAI Script Author agent.\n"
        "You help create CherryAI format handlers, mode plugins, and utility scripts.\n"
        "Developer documentation:\n{{dev_docs}}\n\n"
        "Guidelines:\n"
        "- Follow PEP 8 and the project's coding conventions.\n"
        "- All FormatHandler subclasses must implement extract() and inject().\n"
        "- All mode plugins must define NAME, PHASE, and the required apply functions.\n"
        "- Output complete, runnable Python modules.\n"
        "- Files are written to dev/sandbox/ for safety."
    ),
    default_read_scope=ReadScope.ALL,
    default_write_scope=WriteScope.SANDBOX,
    icon="📝",
)

TRANSLATION_CHECK = AgentMode(
    name="translation_check",
    display_name="Translation / TLC / Check",
    description=(
        "An agent specialized in targeted translation, edit passes, and validation. "
        "Accepts manifest or selected-line context and produces suggestions."
    ),
    system_prompt_template=(
        "You are the CherryAI Translation Check agent.\n"
        "You perform targeted translation review, editing passes, and validation.\n"
        "Context:\n{{translation_context}}\n\n"
        "Source language: {{source_lang}}\nTarget language: {{target_lang}}\n\n"
        "For each line, provide:\n"
        "1. Quality assessment (OK / needs-edit / error)\n"
        "2. Suggested edit (if applicable)\n"
        "3. Brief rationale"
    ),
    default_read_scope=ReadScope.PROJECT,
    default_write_scope=WriteScope.SUGGESTIONS,
    icon="✅",
)


# ---------------------------------------------------------------------------
# Mode Registry
# ---------------------------------------------------------------------------

_MODE_REGISTRY: Dict[str, AgentMode] = {}


def _init_builtin_modes() -> None:
    """Register the four built-in agent modes."""
    for mode in (INTERACTIVE_HELP, LANGUAGE_ASSISTANT, SCRIPT_AUTHOR, TRANSLATION_CHECK):
        _MODE_REGISTRY[mode.name] = mode


def register_mode(mode: AgentMode) -> None:
    """Register or replace an agent mode."""
    _MODE_REGISTRY[mode.name] = mode
    logger.debug("Registered agent mode: %s", mode.name)


def unregister_mode(name: str) -> bool:
    """Remove a registered mode. Returns True if found and removed."""
    return _MODE_REGISTRY.pop(name, None) is not None


def get_mode(name: str) -> Optional[AgentMode]:
    """Return mode by name, or None."""
    return _MODE_REGISTRY.get(name)


def list_modes() -> List[AgentMode]:
    """Return all registered modes sorted by name."""
    return sorted(_MODE_REGISTRY.values(), key=lambda m: m.name)


def list_mode_names() -> List[str]:
    """Return sorted list of registered mode names."""
    return sorted(_MODE_REGISTRY.keys())


def mode_count() -> int:
    """Return number of registered modes."""
    return len(_MODE_REGISTRY)


# ---------------------------------------------------------------------------
# Read scope helpers
# ---------------------------------------------------------------------------

def gather_context(
    root: Path,
    scope: ReadScope,
    extra_snippets: Optional[List[str]] = None,
) -> str:
    """Gather context snippets based on read scope.

    Args:
        root: Project root directory.
        scope: Which files the mode is allowed to read.
        extra_snippets: Additional user-provided context strings.

    Returns:
        Combined context string.
    """
    parts: List[str] = []

    if scope in (ReadScope.DOCS, ReadScope.PROJECT, ReadScope.ALL):
        for rel in sorted(DOC_READ_PATHS):
            path = root / rel
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    # Truncate very large files to first 4000 chars
                    if len(text) > 4000:
                        text = text[:4000] + "\n... (truncated)"
                    parts.append(f"--- {rel} ---\n{text}")
                except OSError:
                    pass

    if extra_snippets:
        for snippet in extra_snippets:
            parts.append(snippet)

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Sandbox write helpers
# ---------------------------------------------------------------------------

def sandbox_path(root: Path) -> Path:
    """Return the sandbox directory, creating it if needed."""
    sb = root / SANDBOX_DIR
    sb.mkdir(parents=True, exist_ok=True)
    return sb


def write_to_sandbox(
    root: Path,
    filename: str,
    content: str,
) -> Path:
    """Write content to the sandbox area and return the full path.

    Args:
        root: Project root.
        filename: Name of the file to create (no path separators allowed).
        content: File content.

    Returns:
        Absolute path of created file.

    Raises:
        ValueError: If filename contains path separators or tries to escape sandbox.
    """
    # Sanitize filename
    if "/" in filename or "\\" in filename:
        raise ValueError(f"Filename must not contain path separators: {filename}")

    sb = sandbox_path(root)
    target = (sb / filename).resolve()

    # Ensure target is inside sandbox (prevent path traversal)
    if not str(target).startswith(str(sb.resolve())):
        raise ValueError(f"Path traversal detected: {filename}")

    target.write_text(content, encoding="utf-8")
    logger.info("Wrote sandbox file: %s", target)
    return target


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def log_audit_entry(root: Path, entry: AuditEntry) -> Path:
    """Append an audit entry to the agent audit log.

    Returns:
        Path to the audit log file.
    """
    log_dir = root / AGENT_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "audit.jsonl"

    with open(log_file, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.to_dict()) + "\n")
    return log_file


def load_audit_log(root: Path) -> List[Dict[str, Any]]:
    """Load all audit entries from the log file."""
    log_file = root / AGENT_LOG_DIR / "audit.jsonl"
    if not log_file.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for line in log_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


# ---------------------------------------------------------------------------
# Agent call wrapper
# ---------------------------------------------------------------------------

def agent_call(
    api_call_fn: Callable[..., str],
    request: AgentRequest,
    root: Path,
    model: str = "",
    source_lang: str = "Japanese",
    target_lang: str = "English",
) -> AgentResponse:
    """Execute a single agent call with scope enforcement and auditing.

    Args:
        api_call_fn: Callable that takes (system_prompt: str, user_message: str)
            and returns the LLM response text. This indirection lets us mock the
            API layer in tests.
        request: The agent request with mode, message, and scopes.
        root: Project root for file I/O.
        model: Model name for audit logging.
        source_lang: Source language name.
        target_lang: Target language name.

    Returns:
        AgentResponse with content and metadata.
    """
    mode = get_mode(request.mode)
    if mode is None:
        return AgentResponse(
            content="",
            error=f"Unknown agent mode: {request.mode}",
            success=False,
        )

    # Resolve scopes (request overrides take priority, else mode defaults)
    read_scope = request.read_scope if request.read_scope is not None else mode.default_read_scope
    write_scope = request.write_scope if request.write_scope is not None else mode.default_write_scope

    # Build system prompt
    context_text = gather_context(root, read_scope, request.context_snippets)
    template_vars: Dict[str, str] = {
        "docs_context": context_text,
        "selected_context": context_text,
        "dev_docs": context_text,
        "translation_context": context_text,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }
    system_prompt = mode.build_system_prompt(template_vars)

    # Execute API call
    try:
        raw_response = api_call_fn(system_prompt, request.user_message)
    except Exception as exc:
        logger.error("Agent call failed for mode %s: %s", request.mode, exc)
        return AgentResponse(
            content="",
            error=str(exc),
            success=False,
        )

    # Parse response — attempt to extract structured data
    response = _parse_agent_response(raw_response, write_scope, root)
    response.model = model

    # Audit
    import hashlib
    msg_hash = hashlib.sha256(request.user_message.encode()).hexdigest()[:16]
    entry = AuditEntry(
        timestamp=time.time(),
        mode=request.mode,
        user_message_hash=msg_hash,
        read_scope=read_scope.value,
        write_scope=write_scope.value,
        files_written=list(response.suggested_files.keys()),
        model=model,
        tokens_used=response.tokens_used,
    )
    try:
        log_audit_entry(root, entry)
    except OSError as exc:
        logger.warning("Failed to write audit log: %s", exc)

    return response


def _parse_agent_response(
    raw: str,
    write_scope: WriteScope,
    root: Path,
) -> AgentResponse:
    """Parse raw LLM response and extract suggested files if present.

    The response may contain code blocks fenced with triple backticks and a
    filename hint (e.g., ```python:my_file.py ... ```). If write scope allows,
    these are extracted into suggested_files.
    """
    response = AgentResponse(content=raw, success=True)

    # Try to extract fenced code blocks with filename hints
    if "```" in raw:
        import re
        # Pattern: ```lang:filename\n...code...\n```
        pattern = r"```\w*:(\S+)\n(.*?)```"
        matches = re.findall(pattern, raw, re.DOTALL)
        for filename, code in matches:
            filename = filename.strip()
            code = code.strip()
            if filename and code:
                response.suggested_files[filename] = code

    return response


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

_init_builtin_modes()
