"""CherryAI Consistency System (Phase 55).

Ensures consistent translation of recurring terms, code-embedded text,
and styled spans across all translation requests.

Modes:
- Preliminary: Pre-translation LLM passes to establish canonical translations.
- During: First translated occurrence becomes canonical and propagates.
- Check: Post-translation verification flagging inconsistencies.

Term Types:
- Code (Translate): Code Database entries with action='translate'.
- Glossary: Glossary entries with empty translation or empty notes.
- Span: Paired tags (e.g. color start/end, bold start/end).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Valid consistency modes
CONSISTENCY_MODES = ("disabled", "preliminary", "during", "check")

# Valid term types
TERM_TYPES = ("code", "glossary", "span")


# =============================================================================
# Data Model (TASK 55.1)
# =============================================================================


@dataclass
class ConsistencyTerm:
    """A single term tracked for translation consistency.

    Attributes:
        original: The original (source language) text of the term.
        canonical_translation: The agreed-upon canonical translation.
        type: Term category — 'code', 'glossary', or 'span'.
        confidence: How confident the canonical translation is (0.0-1.0).
        source_line_idx: Line index where the term was first detected.
    """

    original: str
    canonical_translation: str = ""
    type: str = "glossary"
    confidence: float = 0.0
    source_line_idx: int = -1

    def __post_init__(self) -> None:
        """Validate term type."""
        if self.type not in TERM_TYPES:
            raise ValueError(
                f"Invalid term type '{self.type}'; must be one of {TERM_TYPES}"
            )

    def is_resolved(self) -> bool:
        """Return True if the term has a canonical translation."""
        return bool(self.canonical_translation)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation of this term.
        """
        return {
            "original": self.original,
            "canonical_translation": self.canonical_translation,
            "type": self.type,
            "confidence": self.confidence,
            "source_line_idx": self.source_line_idx,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsistencyTerm":
        """Deserialize from dictionary.

        Args:
            data: Dictionary with term fields.

        Returns:
            New ConsistencyTerm instance.
        """
        return cls(
            original=str(data.get("original", "")),
            canonical_translation=str(data.get("canonical_translation", "")),
            type=str(data.get("type", "glossary")),
            confidence=float(data.get("confidence", 0.0)),
            source_line_idx=int(data.get("source_line_idx", -1)),
        )


class ConsistencyStore:
    """Collection of consistency terms with lookup, update, and serialization.

    Terms are indexed by their normalized original text (lowercased).
    """

    def __init__(self) -> None:
        """Initialize an empty store."""
        self._terms: Dict[str, ConsistencyTerm] = {}

    # ---- Lookup ----

    def get(self, original: str) -> Optional[ConsistencyTerm]:
        """Look up a term by its original text (case-insensitive).

        Args:
            original: Source-language term to look up.

        Returns:
            ConsistencyTerm if found, else None.
        """
        return self._terms.get(original.lower())

    def has(self, original: str) -> bool:
        """Check if a term exists in the store.

        Args:
            original: Source-language term to check.

        Returns:
            True if the term is tracked.
        """
        return original.lower() in self._terms

    # ---- Mutation ----

    def add(self, term: ConsistencyTerm) -> None:
        """Add a term to the store. Overwrites if original already present.

        Args:
            term: ConsistencyTerm to add.
        """
        self._terms[term.original.lower()] = term
        logger.debug("Consistency: added term '%s' (%s)", term.original, term.type)

    def update_canonical(
        self, original: str, translation: str, confidence: float = 1.0
    ) -> bool:
        """Update the canonical translation for a term.

        Args:
            original: Source-language term.
            translation: Canonical translation to set.
            confidence: Confidence score (0.0-1.0).

        Returns:
            True if the term was found and updated.
        """
        key = original.lower()
        term = self._terms.get(key)
        if term is None:
            return False
        term.canonical_translation = translation
        term.confidence = confidence
        logger.debug(
            "Consistency: updated '%s' → '%s' (%.2f)",
            original, translation, confidence,
        )
        return True

    def remove(self, original: str) -> bool:
        """Remove a term from the store.

        Args:
            original: Source-language term to remove.

        Returns:
            True if the term was found and removed.
        """
        key = original.lower()
        if key in self._terms:
            del self._terms[key]
            return True
        return False

    # ---- Retrieval ----

    def all_terms(self) -> List[ConsistencyTerm]:
        """Return all terms in insertion order.

        Returns:
            List of all ConsistencyTerm instances.
        """
        return list(self._terms.values())

    def unresolved(self) -> List[ConsistencyTerm]:
        """Return terms without a canonical translation.

        Returns:
            List of unresolved ConsistencyTerm instances.
        """
        return [t for t in self._terms.values() if not t.is_resolved()]

    def resolved(self) -> List[ConsistencyTerm]:
        """Return terms with a canonical translation.

        Returns:
            List of resolved ConsistencyTerm instances.
        """
        return [t for t in self._terms.values() if t.is_resolved()]

    def by_type(self, term_type: str) -> List[ConsistencyTerm]:
        """Return all terms of a given type.

        Args:
            term_type: One of 'code', 'glossary', 'span'.

        Returns:
            Filtered list of terms.
        """
        return [t for t in self._terms.values() if t.type == term_type]

    def __len__(self) -> int:
        """Return number of terms in the store."""
        return len(self._terms)

    # ---- Serialization ----

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire store to a dictionary.

        Returns:
            Dictionary with 'terms' list.
        """
        return {
            "terms": [t.to_dict() for t in self._terms.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsistencyStore":
        """Deserialize from a dictionary.

        Args:
            data: Dictionary with 'terms' list.

        Returns:
            New ConsistencyStore instance.
        """
        store = cls()
        terms_raw = data.get("terms", [])
        if isinstance(terms_raw, list):
            for entry in terms_raw:
                if isinstance(entry, dict):
                    try:
                        term = ConsistencyTerm.from_dict(entry)
                        store.add(term)
                    except (ValueError, TypeError):
                        logger.warning(
                            "Skipping invalid consistency term: %s", entry
                        )
        return store


# =============================================================================
# Type Detection (TASK 55.2)
# =============================================================================

# Common paired tag patterns for span detection
_SPAN_PATTERNS: List[re.Pattern[str]] = [
    # RPG Maker color codes: \C[n] ... \C[0]
    re.compile(r"\\C\[([1-9]\d*)\](.+?)\\C\[0\]", re.DOTALL),
    # RPG Maker bold: \B[1] ... \B[0]
    re.compile(r"\\B\[1\](.+?)\\B\[0\]", re.DOTALL),
    # RPG Maker italic: \I[1] ... \I[0]
    re.compile(r"\\I\[1\](.+?)\\I\[0\]", re.DOTALL),
    # HTML-style: <b>...</b>, <i>...</i>, <color=...>...</color>
    re.compile(r"<(b|i|em|strong)>(.+?)</\1>", re.DOTALL | re.IGNORECASE),
    re.compile(
        r"<color=[^>]+>(.+?)</color>", re.DOTALL | re.IGNORECASE
    ),
]


def detect_code_terms(
    code_patterns: List[Dict[str, Any]],
) -> List[ConsistencyTerm]:
    """Detect consistency terms from the Code Database.

    Scans code patterns for entries with action='provides_context'.

    Args:
        code_patterns: List of code pattern dicts (from manifest).

    Returns:
        List of ConsistencyTerm with type='code'.
    """
    terms: List[ConsistencyTerm] = []
    for pat in code_patterns:
        if not isinstance(pat, dict):
            continue
        action = str(pat.get("action", "preserve")).lower()
        if action != "provides_context":
            continue
        original = str(pat.get("pattern", "")).strip()
        if not original:
            continue
        terms.append(ConsistencyTerm(
            original=original,
            type="code",
            source_line_idx=-1,
        ))
    logger.debug("Detected %d code consistency terms", len(terms))
    return terms


def detect_glossary_terms(
    glossary_entries: List[Dict[str, Any]],
) -> List[ConsistencyTerm]:
    """Detect consistency terms from glossary entries.

    Finds entries with empty translation or empty notes.

    Args:
        glossary_entries: List of glossary entry dicts (from manifest).

    Returns:
        List of ConsistencyTerm with type='glossary'.
    """
    terms: List[ConsistencyTerm] = []
    for entry in glossary_entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source", "")).strip()
        target = str(entry.get("target", "")).strip()
        notes = str(entry.get("notes", "")).strip()
        if not source:
            continue
        # Include if translation or notes are empty
        if not target or not notes:
            terms.append(ConsistencyTerm(
                original=source,
                canonical_translation=target,
                type="glossary",
                confidence=0.5 if target else 0.0,
                source_line_idx=-1,
            ))
    logger.debug("Detected %d glossary consistency terms", len(terms))
    return terms


def detect_span_terms(
    lines: Sequence[str],
) -> List[ConsistencyTerm]:
    """Detect consistency terms from paired tags (spans) in source text.

    Looks for content within paired color, bold, italic, HTML tags.

    Args:
        lines: Source text lines to scan.

    Returns:
        List of ConsistencyTerm with type='span'.
    """
    seen: set[str] = set()
    terms: List[ConsistencyTerm] = []
    for idx, line in enumerate(lines):
        for pattern in _SPAN_PATTERNS:
            for match in pattern.finditer(line):
                # Extract the text content (last group)
                content = match.group(match.lastindex or 0).strip()
                if not content or content.lower() in seen:
                    continue
                seen.add(content.lower())
                terms.append(ConsistencyTerm(
                    original=content,
                    type="span",
                    source_line_idx=idx,
                ))
    logger.debug("Detected %d span consistency terms", len(terms))
    return terms


def build_consistency_store(
    code_patterns: Optional[List[Dict[str, Any]]] = None,
    glossary_entries: Optional[List[Dict[str, Any]]] = None,
    lines: Optional[Sequence[str]] = None,
) -> ConsistencyStore:
    """Build a ConsistencyStore from all available project data.

    Combines code, glossary, and span term detection.

    Args:
        code_patterns: Code Database entries from manifest.
        glossary_entries: Glossary entries from manifest.
        lines: Source text lines for span detection.

    Returns:
        Populated ConsistencyStore.
    """
    store = ConsistencyStore()

    if code_patterns:
        for term in detect_code_terms(code_patterns):
            store.add(term)
    if glossary_entries:
        for term in detect_glossary_terms(glossary_entries):
            store.add(term)
    if lines:
        for term in detect_span_terms(lines):
            if not store.has(term.original):
                store.add(term)

    logger.info(
        "Consistency store built: %d terms (%d code, %d glossary, %d span)",
        len(store),
        len(store.by_type("code")),
        len(store.by_type("glossary")),
        len(store.by_type("span")),
    )
    return store


# =============================================================================
# Preliminary Mode (TASK 55.3)
# =============================================================================


def _build_preliminary_prompt(term: ConsistencyTerm, context: str) -> str:
    """Build a prompt asking the LLM to identify and translate a term.

    Args:
        term: The consistency term to ask about.
        context: Surrounding text context.

    Returns:
        Prompt string for the LLM.
    """
    return (
        f"The following text contains the term \"{term.original}\".\n\n"
        f"Context:\n{context}\n\n"
        f"Is \"{term.original}\" a person's name, a location, or a general term?\n"
        f"Please provide the appropriate English translation for "
        f"\"{term.original}\".\n\n"
        f"Respond with ONLY the translation, nothing else."
    )


def _extract_context(
    lines: Sequence[str], term: ConsistencyTerm, window: int = 3
) -> str:
    """Extract context lines around the first occurrence of a term.

    Args:
        lines: Source text lines.
        term: Term to find context for.
        window: Number of lines before and after to include.

    Returns:
        Context string with surrounding lines.
    """
    for idx, line in enumerate(lines):
        if term.original in line:
            start = max(0, idx - window)
            end = min(len(lines), idx + window + 1)
            return "\n".join(lines[start:end])
    return term.original


def run_preliminary(
    store: ConsistencyStore,
    lines: Sequence[str],
    api_call: Callable[[str], str],
    passes: int = 1,
) -> ConsistencyStore:
    """Run preliminary consistency passes to establish canonical translations.

    Sends text-only excerpts to the LLM for each unresolved term.
    Multiple passes increase confidence when results agree.

    Args:
        store: ConsistencyStore with detected terms.
        lines: Source text lines (code-free).
        api_call: Callable that sends a prompt string and returns LLM response.
        passes: Number of LLM passes for confidence (default 1).

    Returns:
        Updated ConsistencyStore with canonical translations.
    """
    unresolved = store.unresolved()
    if not unresolved:
        logger.info("Preliminary: no unresolved terms to process")
        return store

    logger.info("Preliminary: processing %d unresolved terms", len(unresolved))

    for term in unresolved:
        context = _extract_context(lines, term)
        prompt = _build_preliminary_prompt(term, context)

        results: List[str] = []
        for _ in range(passes):
            try:
                response = api_call(prompt)
                result = response.strip()
                if result:
                    results.append(result)
            except Exception:
                logger.warning(
                    "Preliminary: API call failed for '%s'", term.original,
                    exc_info=True,
                )

        if not results:
            continue

        # If multiple passes agree, higher confidence
        if len(results) == 1:
            store.update_canonical(term.original, results[0], 0.7)
        else:
            # Check agreement
            most_common = max(set(results), key=results.count)
            agreement = results.count(most_common) / len(results)
            store.update_canonical(term.original, most_common, agreement)

    resolved_count = len(store.resolved())
    logger.info("Preliminary: resolved %d / %d terms", resolved_count, len(store))
    return store


# =============================================================================
# During Mode (TASK 55.4)
# =============================================================================


def during_scan_output(
    store: ConsistencyStore,
    original_lines: Sequence[str],
    translated_lines: Sequence[str],
) -> List[Tuple[str, str]]:
    """Scan translated output for consistency terms and capture first translations.

    For each consistency term found in the original lines, checks the
    corresponding translated line. If the term has no canonical translation
    yet, the first occurrence becomes canonical.

    Args:
        store: ConsistencyStore with tracked terms.
        original_lines: Source lines from this chunk.
        translated_lines: Translated lines from this chunk.

    Returns:
        List of (original, canonical_translation) pairs that were newly set.
    """
    newly_set: List[Tuple[str, str]] = []

    for idx, orig_line in enumerate(original_lines):
        if idx >= len(translated_lines):
            break
        tl_line = translated_lines[idx]

        for term in store.all_terms():
            if term.original not in orig_line:
                continue
            if term.is_resolved():
                continue

            # Use the whole translated line as the canonical if it's short,
            # otherwise try to isolate the translation
            translation = tl_line.strip()
            if translation:
                store.update_canonical(term.original, translation, 0.8)
                newly_set.append((term.original, translation))
                logger.debug(
                    "During: first occurrence '%s' → '%s'",
                    term.original, translation,
                )

    return newly_set


def during_replace_in_requests(
    store: ConsistencyStore,
    request_lines: List[str],
) -> List[str]:
    """Replace unresolved terms in pending request lines with canonical translations.

    For each line, if a resolved consistency term's original appears,
    it is replaced with the canonical translation.

    Args:
        store: ConsistencyStore with some resolved terms.
        request_lines: Lines in a pending translation request.

    Returns:
        Modified lines with canonical replacements applied.
    """
    result: List[str] = []
    for line in request_lines:
        modified = line
        for term in store.resolved():
            if term.original in modified and term.canonical_translation:
                modified = modified.replace(term.original, term.canonical_translation)
        result.append(modified)
    return result


# =============================================================================
# Check Mode (TASK 55.5)
# =============================================================================


@dataclass
class InconsistencyFlag:
    """A flagged inconsistency in translated output.

    Attributes:
        original: The source-language term.
        translations_found: Set of different translations found.
        locations: List of (chunk_idx, line_idx) where each translation was found.
        canonical: The expected canonical translation (if any).
    """

    original: str
    translations_found: Dict[str, List[Tuple[int, int]]] = field(
        default_factory=dict,
    )
    canonical: str = ""

    def is_inconsistent(self) -> bool:
        """Return True if multiple different translations were found."""
        return len(self.translations_found) > 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "original": self.original,
            "translations_found": {
                tl: locs for tl, locs in self.translations_found.items()
            },
            "canonical": self.canonical,
            "is_inconsistent": self.is_inconsistent(),
        }


def check_consistency(
    store: ConsistencyStore,
    all_chunks: List[List[str]],
    all_originals: Optional[List[List[str]]] = None,
) -> List[InconsistencyFlag]:
    """Post-translation check for inconsistent translations.

    Scans all translated chunks for consistency terms and compares
    translations of the same term across different chunks.

    Args:
        store: ConsistencyStore with tracked terms.
        all_chunks: List of translated line lists (one list per chunk).
        all_originals: Optional list of original line lists.

    Returns:
        List of InconsistencyFlag for terms with different translations.
    """
    flags: List[InconsistencyFlag] = []

    for term in store.all_terms():
        flag = InconsistencyFlag(
            original=term.original,
            canonical=term.canonical_translation,
        )

        for chunk_idx, chunk_lines in enumerate(all_chunks):
            for line_idx, line in enumerate(chunk_lines):
                # Check if line likely contains a translation of this term
                # We look for the term or its canonical in the translated text
                matched_translation = ""

                if all_originals and chunk_idx < len(all_originals):
                    orig_lines = all_originals[chunk_idx]
                    if line_idx < len(orig_lines):
                        if term.original not in orig_lines[line_idx]:
                            continue
                    # The translated line is the translation of a line
                    # containing this term
                    matched_translation = line.strip()

                if matched_translation:
                    locs = flag.translations_found.setdefault(
                        matched_translation, [],
                    )
                    locs.append((chunk_idx, line_idx))

        if flag.is_inconsistent():
            flags.append(flag)
            logger.info(
                "Consistency check: '%s' has %d different translations",
                term.original, len(flag.translations_found),
            )

    logger.info(
        "Consistency check complete: %d inconsistencies found", len(flags),
    )
    return flags
