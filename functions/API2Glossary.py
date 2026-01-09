"""API2Glossary module for CherryAI.

Purpose:
- Optional LLM-based name translation and gender inference using OpenAI-compatible API
- Designed for use with free Gemini API (or any OpenAI-format endpoint)
- Called by analysis.py when the API enrichment option is enabled

Entry point: enrich_speakers_via_api(speaker_data: Dict[str, List[str]]) -> Dict[str, Dict[str, str]]
  - Takes a dict mapping speaker names to their lines from the file
  - Constructs excerpts with X lines where name appears as speaker Y times
  - Returns dict mapping name -> {"romaji": ..., "gender": ..., "note": ...}
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
# `API2GLOSSARY_API_KEY` or from the project's `config/config.txt` file.
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

# System prompt template for name translation and gender inference from excerpts
# {excerpt} will be replaced with the actual text excerpt
# {name} will be replaced with the speaker name to analyze
PROMPT_TEMPLATE: str = """You are a translator and gender inference assistant.

Analyze the following dialogue excerpt and provide information about the speaker "{name}":

1. If the name is written in non-Latin characters, provide its romanized reading. Otherwise repeat the name.
2. Gender inference (Male, Female, Neutral, or Unknown if not clear from context)
3. Optional note (e.g., a role like teacher, parent, student, etc.)

Base your gender inference on:
- How other characters refer to this speaker
- The speech patterns and word choices used by this speaker
- Any contextual clues in the surrounding dialogue

Excerpt:
{excerpt}

Return a JSON object with this structure:
{{
  "name": "original name from excerpt",
  "romaji": "romanized name",
  "gender": "Male|Female|Neutral|Unknown",
  "note": "optional context or role"
}}
"""

# Default enabled state (set to False to require explicit opt-in via config)
DEFAULT_ENABLED: bool = False

# Request timeout in seconds
REQUEST_TIMEOUT: int = 30

# JSON schema for structured output (OpenAI response_format)
# This enforces the output structure and makes parsing reliable
RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "name_analysis_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Original name from excerpt"},
                "romaji": {"type": "string", "description": "Romanized name (Hepburn)"},
                "gender": {
                    "type": "string",
                    "enum": ["Male", "Female", "Neutral", "Unknown"],
                    "description": "Inferred gender",
                },
                "note": {"type": "string", "description": "Optional context or notes"},
            },
            "required": ["name", "romaji", "gender", "note"],
            "additionalProperties": False,
        },
    },
}

# ---------------- End Configuration ---------------- #


def _get_api_key() -> Optional[str]:
    """Return API key from module constant, environment variable, or config files.
    
    Priority order:
    1. Module constant (API_KEY)
    2. Environment variable (API2GLOSSARY_API_KEY)
    3. CherryAI.ini [api] section (api_key)
    4. config/config.txt (API2GLOSSARY_API_KEY)
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

    # 4) project config file: <repo>/CherryAI/config/config.txt
    try:
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.txt"
        if cfg_path.exists():
            text = cfg_path.read_text(encoding="utf-8")
            for raw in text.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    key = k.strip().upper()
                    val = v.strip().strip('"').strip("'")
                    if key in {"API2GLOSSARY_API_KEY", "API_KEY", "API2GLOSSARY_KEY"} and val:
                        return val
    except Exception:
        # ignore errors reading config
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

    # Build prompt with excerpt and speaker name
    user_prompt = PROMPT_TEMPLATE.format(excerpt=excerpt, name=speaker)

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
        "temperature": 0.0,  # deterministic for name translation
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

    # Return the single result
    result = {
        "romaji": parsed.get("romaji", ""),
        "gender": parsed.get("gender", "Unknown"),
        "note": parsed.get("note", ""),
    }
    return result


def _validate_gender_with_checks(
    speaker: str, excerpts: List[str]
) -> Tuple[str, str, str, int]:
    """Run multiple checks to validate gender inference with confidence tracking.

    Args:
        speaker: Speaker name
        excerpts: List of available excerpts (should have at least INITIAL_CHECKS)

    Returns:
        Tuple of (romaji, gender, note, total_checks)
        - gender will be the consensus or "Unknown" if no consensus
        - total_checks is the number of API calls made
    """
    if not excerpts:
        return ("", "Unknown", "", 0)

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
        return ("", "Unknown", "", checks_made)

    # Analyze results: count genders (skip Unknown)
    def _analyze_results(res_list: List[Dict[str, str]]) -> Tuple[str, float, bool]:
        """Return (consensus_gender, confidence_pct, has_conflict)."""
        gender_counts = Counter(r["gender"] for r in res_list if r["gender"] != "Unknown")
        if not gender_counts:
            return ("Unknown", 0.0, False)

        total_non_unknown = sum(gender_counts.values())
        most_common_gender, most_common_count = gender_counts.most_common(1)[0]
        conf_pct = (most_common_count / total_non_unknown) * 100.0

        # Check for conflict: Male vs Female (ignore Neutral)
        has_male = gender_counts.get("Male", 0) > 0
        has_female = gender_counts.get("Female", 0) > 0
        has_conflict = has_male and has_female

        return (most_common_gender, conf_pct, has_conflict)

    consensus, conf_pct, has_conflict = _analyze_results(results)

    # If no conflict or confidence is high enough, stop
    if not has_conflict or conf_pct >= confidence:
        # Pick romaji and note from most common gender result
        best_result = next(
            (r for r in results if r["gender"] == consensus), results[0]
        )
        logging.info(
            "API2Glossary: '%s' resolved with %d checks (gender=%s, confidence=%.1f%%)",
            speaker,
            checks_made,
            consensus,
            conf_pct,
        )
        return (best_result["romaji"], consensus, best_result["note"], checks_made)

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
    best_result = next((r for r in results if r["gender"] == consensus), results[0])
    logging.info(
        "API2Glossary: '%s' finished with %d checks (gender=%s, confidence=%.1f%%)",
        speaker,
        checks_made,
        consensus,
        conf_pct,
    )
    return (best_result["romaji"], consensus, best_result["note"], checks_made)


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
        Dict mapping name -> {"romaji": str, "gender": str, "note": str, "checks": int}
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
            romaji, gender, note, checks = _validate_gender_with_checks(
                speaker, excerpts
            )

            results[speaker] = {
                "romaji": romaji,
                "gender": gender,
                "note": note,
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
                      (romaji, gender, note, checks)
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
            # Only update if fields are empty (preserve user edits)
            if not entry.translation and data.get("romaji"):
                entry.translation = data["romaji"]
            if not entry.gender and data.get("gender"):
                entry.gender = data["gender"]
            if not entry.notes and data.get("note"):
                entry.notes = data["note"]
            # Always update source to indicate API enrichment
            if entry.source != "API":
                entry.source = f"{entry.source}+API" if entry.source else "API"
        else:
            # Create new entry
            entry = GlossaryEntry(
                original=speaker,
                translation=data.get("romaji", ""),
                notes=data.get("note", ""),
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
        
        required_keys = {"romaji", "gender", "note"}
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
        romaji = result.get("romaji", "")
        note = result.get("note", "")
        
        logging.info("API2Glossary: test result - romaji=%s, gender=%s, note=%s", romaji, gender, note)
        
        # Check for correct Male inference
        if gender == "Male":
            return (True, {
                "status": "success",
                "message": f"'太郎' correctly inferred as 'Male'",
                "result": result,
                "romaji": romaji,
                "gender": gender,
                "note": note
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
                "romaji": romaji,
                "gender": gender,
                "note": note
            })
        
        # Neutral is acceptable but log as warning
        if gender == "Neutral":
            logging.warning("API2Glossary: test resulted in 'Neutral' gender (acceptable but not ideal)")
            return (True, {
                "status": "neutral_result",
                "message": f"'太郎' inferred as 'Neutral' (acceptable but 'Male' expected)",
                "result": result,
                "romaji": romaji,
                "gender": gender,
                "note": note
            })
        
        # Unexpected gender value
        logging.error("API2Glossary: test returned unexpected gender: %s", gender)
        return (False, {
            "status": "invalid_gender",
            "message": f"API returned unexpected gender value: '{gender}'",
            "error": f"Gender must be Male/Female/Neutral/Unknown, got '{gender}'",
            "result": result
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
