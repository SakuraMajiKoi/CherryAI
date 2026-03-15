"""API2Glossary module for CherryAI.

Purpose:
- Optional LLM-based gender inference using OpenAI-compatible API
- Designed for use with free Gemini API (or any OpenAI-format endpoint)
- Called by analysis.py when the API enrichment option is enabled

Entry point: enrich_speakers_via_api(speaker_data: Dict[str, List[str]]) -> Dict[str, Dict[str, str]]
  - Takes a dict mapping speaker names to their lines from the file
  - Constructs excerpts with X lines where name appears as speaker Y times
  - Returns dict mapping name -> {"gender": ..., "checks": ...}
  - Uses structured output (JSON schema) for reliable parsing
  - Implements multi-check validation for conflicting gender results

Configuration:
- API_KEY: Your API key (Gemini or OpenAI-compatible)
- API_URL: API endpoint (e.g., Gemini endpoint configured for OpenAI format)
- PROMPT_TEMPLATE: System/user prompt for name translation and gender inference
- DEFAULT_ENABLED: Whether to enable API enrichment by default (False recommended)
- EXCERPT_LINES: Number of lines per excerpt (default 5)
- EXCERPT_SPEAKER_OCCURRENCES: Required speaker occurrences in excerpt (default 3)
- INITIAL_CHECKS: Number of different excerpts to send initially (default 2)
- MAX_VALIDATION_CHECKS: Maximum checks for conflicting results (default 10)
- CONFIDENCE_THRESHOLD: Required confidence % to stop validation (51-90%, default 70%)

"""

from __future__ import annotations

import json
import logging
import os
import random
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from collections import Counter

# ---------------- Configuration (edit these values manually) ---------------- #

# API key for the LLM service (Gemini free tier or OpenAI-compatible endpoint)
# By default this is left empty and is read from the environment variable
# `API2GLOSSARY_API_KEY` or from `user/API.ini` [api2glossary] key.
API_KEY: str = ""

# API endpoint URL (OpenAI-compatible format)
# Example for Gemini (configured for OpenAI compatibility):
#   "https://generativelanguage.googleapis.com/v1beta/openai/"
# Example for OpenAI:
#   "https://api.openai.com/v1/"
API_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Model name to use (e.g., "gemini-1.5-flash" for Gemini, "gpt-4" for OpenAI)
MODEL_NAME: str = "gemini-2.0-flash-lite"

# Excerpt construction parameters
EXCERPT_LINES: int = 5  # Number of consecutive lines per excerpt
EXCERPT_SPEAKER_OCCURRENCES: int = 3  # Required times speaker appears in excerpt

# Validation parameters
INITIAL_CHECKS: int = 2  # Number of different excerpts to send initially
MAX_VALIDATION_CHECKS: int = 10  # Maximum total checks for conflicting results
CONFIDENCE_THRESHOLD: float = 70.0  # Required confidence % (51-90) to stop validation

# System prompt template for gender inference from excerpts
# {excerpt} / {Excerpt} will be replaced with the actual text excerpt
# {name} / {Original_Name} will be replaced with the speaker name to analyze
PROMPT_TEMPLATE: str = (
    'Infer the gender of the speaker "{name}" from the dialogue excerpt '
    "below. Base your answer on how others address this speaker, their "
    "speech patterns, and contextual clues. "
    "Don't guess a gender if you are unsure.\n\n"
    "{excerpt}\n\n"
    "Return a JSON object with exactly these fields:\n"
    '- details: gender (one word, "Unknown")'
)

# Default enabled state (set to False to require explicit opt-in via config)
DEFAULT_ENABLED: bool = False

# Request timeout in seconds
REQUEST_TIMEOUT: int = 30

# JSON schema for structured output (OpenAI response_format)
# This enforces the output structure and makes parsing reliable
RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "gender_inference_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "details": {
                    "type": "string",
                    "description": "Inferred gender in one word, or Unknown",
                },
            },
            "required": ["details"],
            "additionalProperties": False,
        },
    },
}

# ---------------- End Configuration ---------------- #

# Canonical gender values for title-case normalization.
_KNOWN_GENDERS = {
    "female": "Female",
    "male": "Male",
    "non-binary": "Non-Binary",
    "nonbinary": "Non-Binary",
    "nb": "Non-Binary",
    "transwoman": "Transwoman",
    "transman": "Transman",
}


def _get_gender_prompt(name: str, excerpt: str) -> str:
    """Build the gender-inference prompt from the configurable template.

    Reads the template from CherryAI.ini ``[prompts] gender_inference``,
    falling back to the compiled-in default from global_options.py.
    Supports both ``{name}/{excerpt}`` and ``{Original_Name}/{Excerpt}``
    placeholder styles.
    """
    from CherryAI.gui.dialogs.global_options import DEFAULT_GENDER_INFERENCE_PROMPT

    template = PROMPT_TEMPLATE  # module-level default
    try:
        from CherryAI.functions import ini_manager
        val = ini_manager.get_user_default("prompts", "gender_inference")
        if val:
            template = val
    except Exception:
        pass

    # If ini_manager had no value, use compiled default
    if template == PROMPT_TEMPLATE:
        template = DEFAULT_GENDER_INFERENCE_PROMPT

    return template.format(
        name=name, excerpt=excerpt,
        Original_Name=name, Excerpt=excerpt,
    )


def _normalize_gender(raw: str) -> str:
    """Normalize any gender string to canonical title-case form.

    Case-insensitive: ``'female'``, ``'FEMALE'``, ``'Female'`` all
    become ``'Female'``.  ``'Unsure'``, ``'Unknown'``, and empty
    strings map to ``'Unknown'``.
    """
    stripped = raw.strip()
    if not stripped:
        return "Unknown"
    lowered = stripped.lower()
    if lowered in ("unsure", "unknown"):
        return "Unknown"
    if lowered in ("neutral",):
        return "Non-Binary"
    if lowered in _KNOWN_GENDERS:
        return _KNOWN_GENDERS[lowered]
    # Accept any other value — title-case it for consistency
    return stripped.title()


def _get_api_key() -> Optional[str]:
    """Return API key from module constant, environment variable, or config files.
    
    Priority order:
    1. Module constant (API_KEY)
    2. Environment variable (API2GLOSSARY_API_KEY)
    3. CherryAI.ini [api] section (api_key)
    4. user/API.ini [api2glossary] key
    """
    import configparser
    
    # 1) module constant (rare, discouraged)
    if API_KEY:
        return API_KEY

    # 2) environment variable
    env_key = os.environ.get("API2GLOSSARY_API_KEY")
    if env_key:
        return env_key

    # 3) CherryAI.ini file (main config)
    try:
        ini_path = Path(__file__).resolve().parents[1] / "CherryAI.ini"
        if ini_path.exists():
            config = configparser.ConfigParser()
            config.read(ini_path, encoding="utf-8")
            if config.has_option("api", "api_key"):
                val = config.get("api", "api_key").strip()
                if val:
                    return val
    except Exception:
        pass

    # 4) user/API.ini [api2glossary] key  (Session 25: removed config/config.txt)
    try:
        api_ini_path = Path(__file__).resolve().parents[1] / "user" / "API.ini"
        if api_ini_path.exists():
            config2 = configparser.ConfigParser()
            config2.read(api_ini_path, encoding="utf-8")
            if config2.has_option("api2glossary", "key"):
                val = config2.get("api2glossary", "key").strip()
                if val:
                    return val
    except Exception:
        pass

    return None


def _is_enabled() -> bool:
    """Check if API enrichment is enabled (key + URL present)."""
    key = _get_api_key()
    return bool(key and API_URL)


def _construct_excerpts(
    speaker: str, lines: List[int], all_lines: List[str], num_excerpts: int
) -> List[str]:
    """Construct excerpts where speaker appears EXCERPT_SPEAKER_OCCURRENCES times in EXCERPT_LINES lines.

    Args:
        speaker: The speaker name to search for
        lines: List of line indices where this speaker appears
        all_lines: Complete list of all lines from the file
        num_excerpts: Number of different excerpts to construct

    Returns:
        List of excerpt strings (may be fewer than requested if not enough valid excerpts)
    """
    excerpts: List[str] = []
    used_ranges: List[Tuple[int, int]] = []  # Track used ranges to avoid overlap

    # Convert line indices to actual lines with speaker detection
    speaker_indices = []
    for line_idx in range(len(all_lines)):
        line = all_lines[line_idx]
        # Check if this line has the speaker (simple colon-based detection)
        if line.strip().startswith(f"{speaker}:") or line.strip().startswith(f"{speaker}："):
            speaker_indices.append(line_idx)

    if len(speaker_indices) < EXCERPT_SPEAKER_OCCURRENCES:
        logging.debug(
            "API2Glossary: Not enough occurrences for '%s' (%d < %d)",
            speaker,
            len(speaker_indices),
            EXCERPT_SPEAKER_OCCURRENCES,
        )
        return []

    # Find valid windows: consecutive EXCERPT_LINES that contain >= EXCERPT_SPEAKER_OCCURRENCES of speaker
    valid_windows: List[Tuple[int, int]] = []
    for start_idx in range(len(all_lines) - EXCERPT_LINES + 1):
        end_idx = start_idx + EXCERPT_LINES
        window_speaker_count = sum(
            1 for idx in speaker_indices if start_idx <= idx < end_idx
        )
        if window_speaker_count >= EXCERPT_SPEAKER_OCCURRENCES:
            valid_windows.append((start_idx, end_idx))

    if not valid_windows:
        logging.debug(
            "API2Glossary: No valid excerpts for '%s' (need %d occurrences in %d lines)",
            speaker,
            EXCERPT_SPEAKER_OCCURRENCES,
            EXCERPT_LINES,
        )
        return []

    # Randomly sample non-overlapping windows
    random.shuffle(valid_windows)
    selected_count = 0
    for start, end in valid_windows:
        # Check for overlap with already used ranges
        overlaps = any(
            not (end <= used_start or start >= used_end)
            for used_start, used_end in used_ranges
        )
        if not overlaps:
            excerpt = "\n".join(all_lines[start:end])
            excerpts.append(excerpt)
            used_ranges.append((start, end))
            selected_count += 1
            if selected_count >= num_excerpts:
                break

    return excerpts


def _call_api_for_excerpt(speaker: str, excerpt: str) -> Dict[str, str]:
    """Call LLM API for a single excerpt and return parsed result."""
    import requests  # type: ignore[import-untyped]  # lazy import to avoid hard dependency

    key = _get_api_key()
    if not key or not API_URL:
        raise ValueError("API_KEY and API_URL must be configured")

    # Build prompt from configurable template
    user_prompt = _get_gender_prompt(speaker, excerpt)

    # Construct OpenAI-compatible request
    url = API_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": user_prompt}],
        "response_format": RESPONSE_SCHEMA,
        "temperature": 0.0,
        "max_tokens": 150,
        "store": False,
    }

    logging.debug("API2Glossary: calling API for speaker '%s'", speaker)
    resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    data = resp.json()
    # Extract content from OpenAI-style response
    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unexpected API response structure: {exc}") from exc

    # Return the single result with normalized gender
    result = {
        "gender": _normalize_gender(parsed.get("details", "Unknown")),
    }
    return result


def _validate_gender_with_checks(
    speaker: str, excerpts: List[str]
) -> Tuple[str, int]:
    """Run multiple checks to validate gender inference with confidence tracking.

    Args:
        speaker: Speaker name
        excerpts: List of available excerpts (should have at least INITIAL_CHECKS)

    Returns:
        Tuple of (gender, total_checks)
        - gender will be the consensus or "Unknown" if no consensus
        - total_checks is the number of API calls made
    """
    if not excerpts:
        return ("Unknown", 0)

    # Clamp confidence threshold to valid range
    confidence = max(51.0, min(90.0, CONFIDENCE_THRESHOLD))

    results: List[Dict[str, str]] = []
    checks_made = 0

    # Initial checks
    initial_count = min(INITIAL_CHECKS, len(excerpts))
    for i in range(initial_count):
        try:
            result = _call_api_for_excerpt(speaker, excerpts[i])
            results.append(result)
            checks_made += 1
        except Exception as exc:
            logging.warning(
                "API2Glossary: Check %d for '%s' failed: %s", i + 1, speaker, exc
            )

    if not results:
        return ("Unknown", checks_made)

    # Analyze results: count genders (skip Unknown)
    def _analyze_results(res_list: List[Dict[str, str]]) -> Tuple[str, float, bool]:
        """Return (consensus_gender, confidence_pct, has_conflict)."""
        gender_counts = Counter(r["gender"] for r in res_list if r["gender"] != "Unknown")
        if not gender_counts:
            return ("Unknown", 0.0, False)

        total_non_unknown = sum(gender_counts.values())
        most_common_gender, most_common_count = gender_counts.most_common(1)[0]
        conf_pct = (most_common_count / total_non_unknown) * 100.0

        # Check for conflict: Male vs Female (ignore Non-Binary)
        has_male = gender_counts.get("Male", 0) > 0
        has_female = gender_counts.get("Female", 0) > 0
        has_conflict = has_male and has_female

        return (most_common_gender, conf_pct, has_conflict)

    consensus, conf_pct, has_conflict = _analyze_results(results)

    # If no conflict or confidence is high enough, stop
    if not has_conflict or conf_pct >= confidence:
        logging.info(
            "API2Glossary: '%s' resolved with %d checks (gender=%s, confidence=%.1f%%)",
            speaker,
            checks_made,
            consensus,
            conf_pct,
        )
        return (consensus, checks_made)

    # Continue with additional checks for conflicting results
    logging.info(
        "API2Glossary: '%s' has conflict after %d checks (confidence=%.1f%%), continuing...",
        speaker,
        checks_made,
        conf_pct,
    )

    excerpt_idx = initial_count
    while checks_made < MAX_VALIDATION_CHECKS and excerpt_idx < len(excerpts):
        try:
            result = _call_api_for_excerpt(speaker, excerpts[excerpt_idx])
            results.append(result)
            checks_made += 1
            excerpt_idx += 1

            # Re-analyze
            consensus, conf_pct, has_conflict = _analyze_results(results)

            # Stop if no conflict or confidence threshold met
            if not has_conflict or conf_pct >= confidence:
                logging.info(
                    "API2Glossary: '%s' resolved with %d checks (gender=%s, confidence=%.1f%%)",
                    speaker,
                    checks_made,
                    consensus,
                    conf_pct,
                )
                break
        except Exception as exc:
            logging.warning(
                "API2Glossary: Check %d for '%s' failed: %s",
                checks_made + 1,
                speaker,
                exc,
            )
            excerpt_idx += 1

    # Final result
    logging.info(
        "API2Glossary: '%s' finished with %d checks (gender=%s, confidence=%.1f%%)",
        speaker,
        checks_made,
        consensus,
        conf_pct,
    )
    return (consensus, checks_made)


def enrich_speakers_via_api(
    speaker_data: Dict[str, List[int]],
    all_lines: List[str],
    enabled: Optional[bool] = None,
    write_to_glossary: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Enrich speaker names via LLM API using constructed excerpts.

    Args:
        speaker_data: Dict mapping speaker names to list of line indices where they appear
        all_lines: Complete list of all lines from the file
        enabled: Explicit enable/disable override (None = use DEFAULT_ENABLED + config check)
        write_to_glossary: If True, write enriched data to unified glossary

    Returns:
        Dict mapping name -> {"gender": str, "checks": int}
        Empty dict if disabled or error occurs.

    Raises:
        No exceptions; logs errors and returns empty dict on failure.
    """
    # Check if feature is enabled
    if enabled is False or (enabled is None and not DEFAULT_ENABLED):
        logging.debug("API2Glossary: disabled (DEFAULT_ENABLED=False or explicit disable)")
        return {}

    if not _is_enabled():
        logging.warning("API2Glossary: missing API_KEY or API_URL; skipping enrichment")
        return {}

    if not speaker_data or not all_lines:
        logging.debug("API2Glossary: no speakers or lines provided")
        return {}

    results: Dict[str, Dict[str, Any]] = {}

    for speaker, line_indices in speaker_data.items():
        try:
            # Construct enough excerpts for potential validation
            num_needed = max(INITIAL_CHECKS, MAX_VALIDATION_CHECKS)
            excerpts = _construct_excerpts(speaker, line_indices, all_lines, num_needed)

            if not excerpts:
                logging.info(
                    "API2Glossary: Skipping '%s' (insufficient excerpts)", speaker
                )
                continue

            # Run validation with multiple checks
            gender, checks = _validate_gender_with_checks(
                speaker, excerpts
            )

            results[speaker] = {
                "gender": gender,
                "checks": checks,
            }

        except Exception as exc:
            logging.error("API2Glossary: Failed to enrich '%s': %s", speaker, exc)

    logging.info(
        "API2Glossary: Enriched %d/%d speakers", len(results), len(speaker_data)
    )
    
    # Write enriched data to unified glossary if requested
    if write_to_glossary and results:
        try:
            _write_enriched_to_glossary(results)
        except Exception as exc:
            logging.error("API2Glossary: Failed to write to glossary: %s", exc)
    
    return results


def _write_enriched_to_glossary(enriched_data: Dict[str, Dict[str, Any]]) -> None:
    """Write API-enriched speaker data to unified glossary.
    
    Args:
        enriched_data: Dict mapping speaker name to enrichment data
                      (gender, checks)
    """
    from .glossary import (
        read_unified_glossary,
        update_unified_glossary,
        GlossaryEntry,
        TYPE_NAME,
    )
    
    existing = read_unified_glossary()
    new_entries: List[GlossaryEntry] = []
    
    for speaker, data in enriched_data.items():
        # Update existing entry if present, otherwise create new
        if speaker in existing:
            entry = existing[speaker]
            # Only update gender if empty (preserve user edits)
            if not entry.gender and data.get("gender"):
                entry.gender = data["gender"]
            # Always update source to indicate API enrichment
            if entry.source != "API":
                entry.source = f"{entry.source}+API" if entry.source else "API"
        else:
            # Create new entry
            entry = GlossaryEntry(
                original=speaker,
                translation="",
                notes="",
                source="API",
                entry_type=TYPE_NAME,
                gender=data.get("gender", ""),
                refers_to_themself_as="",
                referred_to_as="",
            )
            new_entries.append(entry)
    
    # Update glossary with new entries
    if new_entries:
        # Use ADD mode by default: preserve existing entries, add new ones
        update_unified_glossary(new_entries, update_mode="Add")
    
    logging.info("API2Glossary: Wrote %d enriched entries to glossary", len(enriched_data))


# ---------------- Diagnostic / testing helper ---------------- #


def test_api_connection() -> Tuple[bool, Dict[str, Any]]:
    """Test API connection with a sample excerpt. 
    
    Returns:
        Tuple of (success: bool, details: dict)
        - success: True only if Male gender correctly inferred
        - details: Contains 'status', 'message', 'result' (if any), 'error' (if any)
    """
    try:
        # Create a simple test excerpt with clear Male speaker
        test_excerpt = """太郎: こんにちは！
花子: こんにちは、太郎くん。
太郎: 今日はいい天気ですね。
花子: そうですね。
太郎: 一緒に公園に行きませんか？"""

        logging.info("API2Glossary: Starting test with speaker '太郎'")
        result = _call_api_for_excerpt("太郎", test_excerpt)
        
        if not result:
            logging.error("API2Glossary: test returned empty result")
            return (False, {
                "status": "empty_response",
                "message": "API returned empty response",
                "error": "No data received from API"
            })
        
        # Validate result structure
        if not isinstance(result, dict):
            logging.error("API2Glossary: test returned non-dict result: %s", type(result))
            return (False, {
                "status": "malformed_response",
                "message": "API returned malformed response (not a dictionary)",
                "error": f"Expected dict, got {type(result).__name__}",
                "result": str(result)
            })
        
        required_keys = {"gender"}
        missing_keys = required_keys - set(result.keys())
        if missing_keys:
            logging.error("API2Glossary: test result missing keys: %s", missing_keys)
            return (False, {
                "status": "malformed_response",
                "message": f"API response missing required fields: {', '.join(missing_keys)}",
                "error": f"Missing keys: {missing_keys}",
                "result": result
            })
        
        gender = result.get("gender", "Unknown")
        
        logging.info("API2Glossary: test result - gender=%s", gender)
        
        # Check for correct Male inference
        if gender == "Male":
            return (True, {
                "status": "success",
                "message": "'太郎' correctly inferred as 'Male'",
                "result": result,
                "gender": gender,
            })
        
        # Female or Unknown = model not suitable
        if gender in ("Female", "Unknown"):
            logging.warning("API2Glossary: test failed - gender inferred as '%s' instead of 'Male'", gender)
            return (False, {
                "status": "incorrect_inference",
                "message": f"'太郎' incorrectly inferred as '{gender}' (expected 'Male')",
                "error": "LLM failed basic gender inference test",
                "guidance": "Consider using a more capable model (e.g., Gemini 1.5 Flash/Pro or GPT-4)",
                "result": result,
                "gender": gender,
            })
        
        # Non-Binary is acceptable but log as warning
        if gender == "Non-Binary":
            logging.warning("API2Glossary: test resulted in 'Non-Binary' gender (acceptable but not ideal)")
            return (True, {
                "status": "nonbinary_result",
                "message": "'太郎' inferred as 'Non-Binary' (acceptable but 'Male' expected)",
                "result": result,
                "gender": gender,
            })
        
        # Any other gender value — accept but warn
        logging.warning("API2Glossary: test returned unexpected gender: %s", gender)
        return (True, {
            "status": "unexpected_gender",
            "message": f"API returned gender value: '{gender}' (expected 'Male')",
            "result": result,
            "gender": gender,
        })
        
    except ValueError as exc:
        # API response structure error (from _call_api_for_excerpt)
        error_msg = str(exc)
        logging.error("API2Glossary: test failed with ValueError: %s", error_msg, exc_info=True)
        return (False, {
            "status": "malformed_response",
            "message": "API returned malformed response",
            "error": error_msg
        })
    except Exception as exc:
        # Network, auth, or other errors
        error_msg = str(exc)
        logging.error("API2Glossary: test failed: %s", error_msg, exc_info=True)
        return (False, {
            "status": "connection_error",
            "message": "API connection test failed",
            "error": error_msg
        })


# ============================================================================
# Configurable LLM Gender Inference (called from Information step)
# ============================================================================

def infer_gender_llm(
    speaker: str,
    all_lines: List[str],
    *,
    provider: str = "",
    key_name: str = "",
    model: str = "",
    minimum: int = 3,
    maximum: int = 5,
    ignore_unknown: bool = True,
    do_all: bool = False,
) -> Tuple[str, float]:
    """Infer a speaker's gender using the LLM with configurable confidence.

    Uses the API key/model from the ``[gender_inference]`` profile in
    API.ini (or explicit overrides).

    Args:
        speaker: Speaker name to infer gender for.
        all_lines: All lines from the loaded project.
        provider: API key provider (falls back to [gender_inference] profile).
        key_name: API key name (falls back to [gender_inference] profile).
        model: Model identifier (falls back to [gender_inference] profile).
        minimum: Minimum agreements needed (or min attempts when !do_all).
        maximum: Maximum checks to run.
        ignore_unknown: Whether Unknown results don't count toward max.
        do_all: Always run *maximum* checks regardless of early consensus.

    Returns:
        Tuple of (gender, confidence_pct).
        ``gender`` is one of 'Male', 'Female', 'Non-Binary', 'Unknown'.
        ``confidence_pct`` is 0-100.
    """
    from CherryAI.functions import api_config

    prov = provider or api_config.get_profile_setting(
        "gender_inference", "provider",
    ) or "openai"
    kname = key_name or api_config.get_profile_setting(
        "gender_inference", "key_name",
    ) or "default"
    mdl = model or api_config.get_profile_setting(
        "gender_inference", "model",
    ) or "gpt-4.1-nano"

    api_key = api_config.get_api_key_plain(prov, kname)
    if not api_key:
        raise RuntimeError(
            f"No API key for provider '{prov}', name '{kname}'. "
            "Configure in Global Options → Utility."
        )

    base_url = api_config.get_profile_setting(
        "gender_inference", "base_url",
    ) or None

    # Build excerpts
    num_needed = max(minimum, maximum)
    speaker_indices = [
        i for i, line in enumerate(all_lines)
        if line.strip().startswith(f"{speaker}:")
        or line.strip().startswith(f"{speaker}：")
    ]
    if len(speaker_indices) < EXCERPT_SPEAKER_OCCURRENCES:
        return ("Unknown", 0.0)

    excerpts = _construct_excerpts(
        speaker, speaker_indices, all_lines, num_needed,
    )
    if not excerpts:
        return ("Unknown", 0.0)

    # Perform checks with configurable confidence
    from collections import Counter
    results: List[str] = []
    checks_done = 0
    unknown_count = 0

    for excerpt in excerpts:
        if not do_all and _has_consensus(results, minimum):
            break
        effective_max = maximum + unknown_count if ignore_unknown else maximum
        if checks_done >= effective_max:
            break

        try:
            res = _call_api_for_excerpt_custom(
                speaker, excerpt, api_key, mdl, base_url,
            )
            gender = res.get("gender", "Unknown")
            if gender == "Unknown":
                unknown_count += 1
                if not ignore_unknown:
                    checks_done += 1
            else:
                results.append(gender)
                checks_done += 1
        except Exception as exc:
            logging.warning(
                "LLM gender check for '%s' failed: %s", speaker, exc,
            )
            checks_done += 1

    if not results:
        return ("Unknown", 0.0)

    counts = Counter(results)
    best_gender, best_count = counts.most_common(1)[0]
    confidence = (best_count / len(results)) * 100.0
    return (best_gender, confidence)


def _has_consensus(results: List[str], minimum: int) -> bool:
    """Return True when *minimum* results agree on one gender."""
    if not results or len(results) < minimum:
        return False
    from collections import Counter
    counts = Counter(results)
    _, top = counts.most_common(1)[0]
    return top >= minimum


def _call_api_for_excerpt_custom(
    speaker: str,
    excerpt: str,
    api_key: str,
    model: str,
    base_url: Optional[str] = None,
) -> Dict[str, str]:
    """Call LLM API for gender inference using the given credentials.

    Uses strict JSON-schema structured output, ``store=False`` and a
    ``max_tokens`` cap to minimise output-token waste.
    """
    import importlib

    openai_mod = importlib.import_module("openai")
    client_cls = getattr(openai_mod, "OpenAI")
    kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = client_cls(**kwargs)

    user_prompt = _get_gender_prompt(speaker, excerpt)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_prompt}],
        response_format=RESPONSE_SCHEMA,
        temperature=0.0,
        max_tokens=150,
        store=False,
    )

    content = response.choices[0].message.content
    parsed = json.loads(content)

    # Log to structured API log
    try:
        from .api_log import (
            LogCategory, LogStatus, LogEntrySent, LogEntryReceived,
            get_api_log_store,
        )
        _usage = response.usage
        store = get_api_log_store()
        store.log_pair(
            LogCategory.GENDER_INFERENCE,
            LogEntrySent(
                model=model,
                user_content=user_prompt,
                extra={"speaker": speaker},
            ),
            LogEntryReceived(
                content=content or "",
                prompt_tokens=_usage.prompt_tokens if _usage else 0,
                completion_tokens=_usage.completion_tokens if _usage else 0,
                total_tokens=getattr(_usage, "total_tokens", 0) if _usage else 0,
            ),
            LogStatus.SUCCESS,
        )
    except Exception:
        pass

    return {
        "gender": _normalize_gender(parsed.get("details", "Unknown")),
    }


if __name__ == "__main__":
    # Quick test when run as standalone script
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    print("API2Glossary test")
    print(f"API_KEY configured: {bool(_get_api_key())}")
    print(f"API_URL: {API_URL}")
    print(f"Enabled: {_is_enabled()}")
    print(f"Excerpt lines: {EXCERPT_LINES}")
    print(f"Speaker occurrences: {EXCERPT_SPEAKER_OCCURRENCES}")
    print(f"Initial checks: {INITIAL_CHECKS}")
    print(f"Max validation checks: {MAX_VALIDATION_CHECKS}")
    print(f"Confidence threshold: {CONFIDENCE_THRESHOLD}%")
    print()
    if _is_enabled():
        print("Running test with sample excerpt...")
        success, details = test_api_connection()
        print(f"Test {'passed' if success else 'failed'}")
        print(f"Status: {details.get('status', 'unknown')}")
        print(f"Message: {details.get('message', 'No message')}")
        if details.get("result"):
            print(f"Result: {json.dumps(details['result'], ensure_ascii=False, indent=2)}")
    else:
        print("API not configured; skipping test call")
