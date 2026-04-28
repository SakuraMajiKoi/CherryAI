"""Shared backend for the RegEx Maker help window.

The GUI layer should only collect examples, annotations, and option state. This
module owns normalization, candidate generation, validation, ranking, and
replacement inference so the feature can be tested without tkinter.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field, replace
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MODE_SEARCH_ONLY = "search_only"
MODE_SEARCH_REPLACE = "search_replace"

ROW_KIND_SEARCH = "search"
ROW_KIND_REPLACE = "replace"

_JAPANESE_FRAGMENT = r"[\u3040-\u30ff\u3400-\u9fff々〆ヵヶー]+"
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_SIMPLE_FAMILIES = frozenset(
    {
        "Whole line strict",
        "Escaped literal",
        "Whitespace-flex literal",
        "Digit wildcard",
        "Delimited capture",
        "Word wildcard",
        "Prefix + capture + suffix",
    }
)
_FAMILY_BASE_SCORES = {
    "Whole line strict": 160.0,
    "Escaped literal": 145.0,
    "Whitespace-flex literal": 135.0,
    "Digit wildcard": 140.0,
    "Delimited capture": 130.0,
    "Word wildcard": 120.0,
    "Prefix + capture + suffix": 115.0,
    "Search-only fallback generalization": 25.0,
}
_OPEN_TO_CLOSE = {
    "[": "]",
    "(": ")",
    "{": "}",
    "<": ">",
    "\"": "\"",
    "'": "'",
    "【": "】",
    "「": "」",
    "『": "』",
    "（": "）",
    "《": "》",
    "〈": "〉",
}


@dataclass(frozen=True)
class RegexExampleRow:
    """One editable example row from the RegEx Maker window."""

    text: str
    enabled: bool = True


@dataclass(frozen=True)
class SpanAnnotation:
    """Persistent span intent recorded from a text-selection context menu."""

    row_kind: str
    row_index: int
    start: int
    end: int
    annotation_type: str
    detail: str = ""
    scope: str = "local"
    hover_label: str = ""
    capture_group: int = 0


@dataclass(frozen=True)
class RegexMakerOptions:
    """Global options surfaced by the RegEx Options popup."""

    match_whole_line: bool = True
    ignore_spaces: bool = False
    ignore_leading_spaces: bool = False
    ignore_trailing_spaces: bool = False
    case_sensitive: bool = False
    prefer_simple: bool = True
    prefer_strict: bool = False
    allow_wildcard_fallback: bool = True
    disallow_lookaround: bool = True
    disallow_backreferences: bool = True
    require_replace_suggestion: bool = False
    max_candidates: int = 5


@dataclass(frozen=True)
class RegexExampleSet:
    """Normalized request passed from the GUI into the backend."""

    search_rows: Tuple[RegexExampleRow, ...]
    replace_rows: Tuple[RegexExampleRow, ...] = ()
    mode: str = MODE_SEARCH_ONLY
    annotations: Tuple[SpanAnnotation, ...] = ()
    options: RegexMakerOptions = field(default_factory=RegexMakerOptions)
    notes: str = ""
    compatibility_profile: str = "CherryAI (re, ignore-case search)"


@dataclass(frozen=True)
class RestrictionProfile:
    """Resolved scoring and generation constraints."""

    match_whole_line: bool
    ignore_spaces: bool
    ignore_leading_spaces: bool
    ignore_trailing_spaces: bool
    case_sensitive: bool
    prefer_simple: bool
    prefer_strict: bool
    allow_wildcard_fallback: bool
    disallow_lookaround: bool
    disallow_backreferences: bool
    require_replace_suggestion: bool
    preferred_capture_kind: str = "any"
    required_capture_groups: Tuple[int, ...] = ()
    literal_texts: Tuple[str, ...] = ()
    warning_texts: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RegexCandidate:
    """One validated search/replace suggestion."""

    search_pattern: str
    replace_pattern: str = ""
    family: str = ""
    score: float = 0.0
    explanation: str = ""
    warnings: Tuple[str, ...] = ()
    flags: int = re.IGNORECASE
    capture_count: int = 0
    replace_confidence: float = 0.0


@dataclass(frozen=True)
class RegexGenerationResult:
    """Candidate list plus user-visible warnings."""

    candidates: Tuple[RegexCandidate, ...]
    warnings: Tuple[str, ...]
    profile: RestrictionProfile


@dataclass(frozen=True)
class _ActiveExample:
    row_index: int
    search_text: str
    replace_text: str


def normalize_text_value(text: str) -> str:
    """Trim only trailing Text-widget newline artifacts."""

    normalized = str(text).replace("\r\n", "\n")
    return normalized.rstrip("\n")


def ensure_row_alignment(
    search_rows: Sequence[RegexExampleRow | str],
    replace_rows: Sequence[RegexExampleRow | str],
    mode: str,
) -> Tuple[Tuple[RegexExampleRow, ...], Tuple[RegexExampleRow, ...]]:
    """Keep replace rows index-aligned with search rows in replace mode."""

    normalized_search = tuple(_coerce_row(row) for row in search_rows)
    if mode != MODE_SEARCH_REPLACE:
        return normalized_search, ()

    normalized_replace = [_coerce_row(row) for row in replace_rows[: len(normalized_search)]]
    while len(normalized_replace) < len(normalized_search):
        normalized_replace.append(RegexExampleRow(text=""))
    return normalized_search, tuple(normalized_replace)


def compile_candidate_pattern(
    pattern: str,
    *,
    case_sensitive: bool = False,
) -> Optional[re.Pattern[str]]:
    """Compile *pattern* with CherryAI-compatible search flags."""

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(pattern, flags)
    except re.error:
        return None


def build_restriction_profile(example_set: RegexExampleSet) -> RestrictionProfile:
    """Merge popup options, annotations, and notes into one scoring profile."""

    options = example_set.options
    warnings: List[str] = []
    settings = {
        "match_whole_line": options.match_whole_line,
        "ignore_spaces": options.ignore_spaces,
        "ignore_leading_spaces": options.ignore_leading_spaces,
        "ignore_trailing_spaces": options.ignore_trailing_spaces,
        "case_sensitive": options.case_sensitive,
        "prefer_simple": options.prefer_simple,
        "prefer_strict": options.prefer_strict,
        "allow_wildcard_fallback": options.allow_wildcard_fallback,
        "disallow_lookaround": options.disallow_lookaround,
        "disallow_backreferences": options.disallow_backreferences,
        "require_replace_suggestion": options.require_replace_suggestion,
        "max_candidates": max(1, min(20, int(options.max_candidates))),
    }
    note_overrides: Dict[str, Any] = {}
    preferred_capture_kind = "any"
    required_capture_groups: List[int] = []
    literal_texts: List[str] = []

    for command in _split_commands(example_set.notes):
        if command in {"whole line", "match whole line", "must start", "must end"}:
            _set_note_override(note_overrides, warnings, "match_whole_line", True, command)
        elif command == "case sensitive":
            _set_note_override(note_overrides, warnings, "case_sensitive", True, command)
        elif command == "ignore spaces":
            _set_note_override(note_overrides, warnings, "ignore_spaces", True, command)
        elif command == "ignore leading spaces":
            _set_note_override(note_overrides, warnings, "ignore_leading_spaces", True, command)
        elif command == "ignore trailing spaces":
            _set_note_override(note_overrides, warnings, "ignore_trailing_spaces", True, command)
        elif command == "prefer simple":
            _set_note_override(note_overrides, warnings, "prefer_simple", True, command)
        elif command == "prefer strict":
            _set_note_override(note_overrides, warnings, "prefer_strict", True, command)
        elif command in {"allow wildcard", "allow wildcard fallback"}:
            _set_note_override(
                note_overrides,
                warnings,
                "allow_wildcard_fallback",
                True,
                command,
            )
        elif command in {"no wildcard", "disallow wildcard"}:
            _set_note_override(
                note_overrides,
                warnings,
                "allow_wildcard_fallback",
                False,
                command,
            )
        elif command in {"no lookaround", "disallow lookaround"}:
            _set_note_override(note_overrides, warnings, "disallow_lookaround", True, command)
        elif command in {"no backreference", "no backreferences", "disallow backreferences"}:
            _set_note_override(
                note_overrides,
                warnings,
                "disallow_backreferences",
                True,
                command,
            )
        elif command in {"replace required", "require replace suggestion"}:
            _set_note_override(
                note_overrides,
                warnings,
                "require_replace_suggestion",
                True,
                command,
            )
        elif command == "capture number":
            preferred_capture_kind = "number"
            required_capture_groups.append(1)
        elif command == "capture word":
            preferred_capture_kind = "word"
            required_capture_groups.append(1)
        elif command == "capture any":
            preferred_capture_kind = "any"
            required_capture_groups.append(1)
        elif command.startswith("max candidates "):
            try:
                settings["max_candidates"] = max(1, min(20, int(command.rsplit(" ", 1)[1])))
            except ValueError:
                warnings.append(f"Unsupported command: {command}")
        else:
            warnings.append(f"Unsupported command: {command}")

    settings.update(note_overrides)

    for annotation in example_set.annotations:
        kind = _normalized_annotation_kind(annotation)
        detail = _annotation_capture_kind(annotation)
        if kind in {"constant", "literal", "must_literal"}:
            literal_text = _annotation_text(example_set, annotation)
            if literal_text:
                literal_texts.append(literal_text)
        if kind in {"capture", "capture_group"}:
            required_capture_groups.append(annotation.capture_group or 1)
            if detail != "any":
                preferred_capture_kind = detail
        elif kind in {"prefer_digits", "variable_number"}:
            preferred_capture_kind = "number"
        elif kind in {"prefer_word", "variable_word"}:
            preferred_capture_kind = "word"
        elif kind == "variable_japanese":
            preferred_capture_kind = "japanese"
        elif kind in {"variable", "variable_any"} and detail in {"number", "word", "japanese"}:
            preferred_capture_kind = detail

    return RestrictionProfile(
        match_whole_line=bool(settings["match_whole_line"]),
        ignore_spaces=bool(settings["ignore_spaces"]),
        ignore_leading_spaces=bool(settings["ignore_leading_spaces"]),
        ignore_trailing_spaces=bool(settings["ignore_trailing_spaces"]),
        case_sensitive=bool(settings["case_sensitive"]),
        prefer_simple=bool(settings["prefer_simple"]),
        prefer_strict=bool(settings["prefer_strict"]),
        allow_wildcard_fallback=bool(settings["allow_wildcard_fallback"]),
        disallow_lookaround=bool(settings["disallow_lookaround"]),
        disallow_backreferences=bool(settings["disallow_backreferences"]),
        require_replace_suggestion=bool(settings["require_replace_suggestion"]),
        preferred_capture_kind=preferred_capture_kind,
        required_capture_groups=tuple(sorted(set(group for group in required_capture_groups if group > 0))),
        literal_texts=tuple(dict.fromkeys(text for text in literal_texts if text)),
        warning_texts=tuple(dict.fromkeys(warnings)),
    )


def generate_regex_suggestions(example_set: RegexExampleSet) -> RegexGenerationResult:
    """Generate ranked search/replace suggestions for *example_set*."""

    normalized_set = _normalize_example_set(example_set)
    payload = json.dumps(_serialize_example_set(normalized_set), ensure_ascii=False, sort_keys=True)
    return _generate_regex_suggestions_cached(payload)


@lru_cache(maxsize=64)
def _generate_regex_suggestions_cached(payload: str) -> RegexGenerationResult:
    example_set = _deserialize_example_set(json.loads(payload))
    profile = build_restriction_profile(example_set)
    warnings = list(profile.warning_texts)
    active_examples = _active_examples(example_set)
    if not active_examples:
        warnings.append("Add at least one enabled Line to find example.")
        return RegexGenerationResult((), tuple(dict.fromkeys(warnings)), profile)

    has_partial_replace = _has_partial_replace_pairs(active_examples)
    has_full_replace = _has_full_replace_pairs(active_examples)
    if has_partial_replace and not has_full_replace:
        warnings.append(
            "Replace suggestions need every enabled search row to have a paired replace target."
        )

    candidate_specs = _collect_candidate_specs(example_set, active_examples, profile)
    candidates: Dict[Tuple[str, str], RegexCandidate] = {}
    for family, pattern in candidate_specs:
        candidate = _evaluate_candidate(
            family,
            pattern,
            example_set,
            active_examples,
            profile,
            has_full_replace=has_full_replace,
        )
        if candidate is None:
            continue
        key = (candidate.search_pattern, candidate.replace_pattern)
        existing = candidates.get(key)
        if existing is None or candidate.score > existing.score:
            candidates[key] = candidate

    ranked_candidates = sorted(
        candidates.values(),
        key=lambda item: (-item.score, item.family, item.search_pattern),
    )
    max_candidates = max(1, min(20, example_set.options.max_candidates))
    limited_candidates = tuple(ranked_candidates[:max_candidates])
    if not limited_candidates:
        warnings.append("No stable regex candidate matched all enabled examples.")

    return RegexGenerationResult(limited_candidates, tuple(dict.fromkeys(warnings)), profile)


def infer_replace_pattern(
    pattern: re.Pattern[str],
    search_rows: Sequence[str],
    replace_rows: Sequence[str],
) -> Tuple[str, float, str]:
    """Infer one shared Python ``re.sub`` replacement string."""

    if pattern.groups < 1:
        return "", 0.0, "No capture groups are available for replacement inference."
    if len(search_rows) != len(replace_rows) or not search_rows:
        return "", 0.0, "Replace suggestions need one target for every enabled search row."

    templates: List[str] = []
    for search_text, replace_text in zip(search_rows, replace_rows):
        match = pattern.search(search_text)
        if match is None:
            return "", 0.0, "The candidate does not match all enabled search rows."

        template = replace_text
        placeholder_hits = 0
        group_values = [
            (group_index, match.group(group_index))
            for group_index in range(1, pattern.groups + 1)
            if match.start(group_index) >= 0 and match.group(group_index)
        ]
        for group_index, group_value in sorted(group_values, key=lambda item: len(item[1]), reverse=True):
            token = f"{{GROUP_{group_index}}}"
            if group_value and group_value in template:
                template = template.replace(group_value, token)
                placeholder_hits += 1
        if placeholder_hits == 0:
            return "", 0.0, "No stable capture mapping could be inferred from the replace targets."
        templates.append(template)

    canonical = templates[0]
    if any(template != canonical for template in templates[1:]):
        return "", 0.0, "The replace targets do not share one stable capture layout."

    replacement = canonical
    for group_index in range(1, pattern.groups + 1):
        replacement = replacement.replace(f"{{GROUP_{group_index}}}", rf"\g<{group_index}>")

    for search_text, replace_text in zip(search_rows, replace_rows):
        if pattern.sub(replacement, search_text, count=1) != replace_text:
            return "", 0.0, "The inferred replacement does not reproduce all replace targets."

    return replacement, 1.0, "Uses a stable capture mapping across all replace targets."


def _collect_candidate_specs(
    example_set: RegexExampleSet,
    active_examples: Sequence[_ActiveExample],
    profile: RestrictionProfile,
) -> List[Tuple[str, str]]:
    search_texts = [example.search_text for example in active_examples]
    candidate_specs: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()

    for family, pattern in _guided_annotation_candidates(example_set, active_examples, profile):
        _append_candidate_spec(candidate_specs, seen, family, pattern)
    for family, pattern in _exact_literal_candidates(search_texts, profile):
        _append_candidate_spec(candidate_specs, seen, family, pattern)
    for family, pattern in _digit_wildcard_candidates(search_texts, profile):
        _append_candidate_spec(candidate_specs, seen, family, pattern)
    for family, pattern in _word_wildcard_candidates(search_texts, profile):
        _append_candidate_spec(candidate_specs, seen, family, pattern)
    for family, pattern in _common_affix_candidates(search_texts, profile):
        _append_candidate_spec(candidate_specs, seen, family, pattern)
    for family, pattern in _fallback_candidates(profile):
        _append_candidate_spec(candidate_specs, seen, family, pattern)

    return candidate_specs


def _guided_annotation_candidates(
    example_set: RegexExampleSet,
    active_examples: Sequence[_ActiveExample],
    profile: RestrictionProfile,
) -> List[Tuple[str, str]]:
    annotations_by_row: Dict[int, SpanAnnotation] = {}
    for annotation in example_set.annotations:
        if annotation.row_kind != ROW_KIND_SEARCH:
            continue
        kind = _normalized_annotation_kind(annotation)
        if kind not in {
            "capture",
            "capture_group",
            "variable",
            "variable_any",
            "variable_number",
            "variable_word",
            "variable_japanese",
            "prefer_digits",
            "prefer_word",
        }:
            continue
        annotations_by_row.setdefault(annotation.row_index, annotation)

    if len(annotations_by_row) < len(active_examples):
        return []

    prefixes: List[str] = []
    suffixes: List[str] = []
    selected_texts: List[str] = []
    explicit_kinds: List[str] = []
    for example in active_examples:
        annotation = annotations_by_row.get(example.row_index)
        if annotation is None:
            return []
        start = max(0, min(len(example.search_text), int(annotation.start)))
        end = max(start, min(len(example.search_text), int(annotation.end)))
        if start >= end:
            return []
        prefixes.append(example.search_text[:start])
        suffixes.append(example.search_text[end:])
        selected_texts.append(example.search_text[start:end])
        explicit_kinds.append(_annotation_capture_kind(annotation))

    if len(set(prefixes)) != 1 or len(set(suffixes)) != 1:
        return []

    capture_kind = _select_capture_kind(selected_texts, profile, explicit_kinds)
    fragment = _capture_fragment(capture_kind)
    prefix = _escape_literal_segment(prefixes[0], profile, boundary_mode="relaxed-trailing")
    suffix = _escape_literal_segment(suffixes[0], profile, boundary_mode="relaxed-leading")
    family = _family_from_affixes(prefixes[0], suffixes[0], capture_kind)
    pattern = _anchor_pattern(f"{prefix}({fragment}){suffix}", profile, anchored=True)
    return [(family, pattern)]


def _exact_literal_candidates(
    search_texts: Sequence[str],
    profile: RestrictionProfile,
) -> List[Tuple[str, str]]:
    if not search_texts:
        return []

    candidates: List[Tuple[str, str]] = []
    if len(set(search_texts)) == 1:
        literal = _anchor_pattern(
            _escape_literal_segment(search_texts[0], profile),
            profile,
            anchored=True,
        )
        candidates.append(("Whole line strict", literal))
        if not profile.match_whole_line:
            candidates.append(
                ("Escaped literal", _escape_literal_segment(search_texts[0], profile))
            )

    collapsed = [_collapse_whitespace(text) for text in search_texts]
    if len(set(collapsed)) == 1 and len(set(search_texts)) > 1:
        flex_profile = replace(profile, ignore_spaces=True)
        candidates.append(
            (
                "Whitespace-flex literal",
                _anchor_pattern(
                    _escape_literal_segment(collapsed[0], flex_profile),
                    profile,
                    anchored=True,
                ),
            )
        )
    return candidates


def _digit_wildcard_candidates(
    search_texts: Sequence[str],
    profile: RestrictionProfile,
) -> List[Tuple[str, str]]:
    if not search_texts:
        return []

    split_rows = [re.split(r"(\d+)", text) for text in search_texts]
    if not any(len(parts) > 1 for parts in split_rows):
        return []
    part_count = len(split_rows[0])
    if any(len(parts) != part_count for parts in split_rows):
        return []

    for position in range(0, part_count, 2):
        if not _segments_equivalent([parts[position] for parts in split_rows], profile):
            return []
    for position in range(1, part_count, 2):
        if not all(parts[position].isdigit() for parts in split_rows):
            return []

    plain_parts: List[str] = []
    capture_parts: List[str] = []
    for position in range(part_count):
        if position % 2 == 0:
            boundary_mode = "literal"
            if part_count > 1:
                if position == 0:
                    boundary_mode = "relaxed-trailing"
                elif position == part_count - 1:
                    boundary_mode = "relaxed-leading"
                else:
                    boundary_mode = "relaxed-both"
            escaped = _escape_literal_segment(split_rows[0][position], profile, boundary_mode=boundary_mode)
            plain_parts.append(escaped)
            capture_parts.append(escaped)
        else:
            plain_parts.append(r"\d+")
            capture_parts.append(r"(\d+)")

    return [
        (
            "Digit wildcard",
            _anchor_pattern("".join(capture_parts), profile, anchored=True),
        ),
        (
            "Digit wildcard",
            _anchor_pattern("".join(plain_parts), profile, anchored=True),
        ),
    ]


def _word_wildcard_candidates(
    search_texts: Sequence[str],
    profile: RestrictionProfile,
) -> List[Tuple[str, str]]:
    if profile.preferred_capture_kind != "word":
        return []

    prefix, suffix, middles = _shared_affix_parts(search_texts)
    if not middles or not (prefix or suffix):
        return []
    if not all(_is_word_like(middle) for middle in middles):
        return []

    prefix_pattern = _escape_literal_segment(prefix, profile, boundary_mode="relaxed-trailing")
    suffix_pattern = _escape_literal_segment(suffix, profile, boundary_mode="relaxed-leading")
    capture = _anchor_pattern(f"{prefix_pattern}(\\w+){suffix_pattern}", profile, anchored=True)
    plain = _anchor_pattern(f"{prefix_pattern}\\w+{suffix_pattern}", profile, anchored=True)
    return [("Word wildcard", capture), ("Word wildcard", plain)]


def _common_affix_candidates(
    search_texts: Sequence[str],
    profile: RestrictionProfile,
) -> List[Tuple[str, str]]:
    prefix, suffix, middles = _shared_affix_parts(search_texts)
    if not middles or not (prefix or suffix):
        return []

    capture_kind = _select_capture_kind(middles, profile)
    fragment = _capture_fragment(capture_kind, allow_empty=any(middle == "" for middle in middles))
    prefix_pattern = _escape_literal_segment(prefix, profile, boundary_mode="relaxed-trailing")
    suffix_pattern = _escape_literal_segment(suffix, profile, boundary_mode="relaxed-leading")
    family = _family_from_affixes(prefix, suffix, capture_kind)
    capture = _anchor_pattern(f"{prefix_pattern}({fragment}){suffix_pattern}", profile, anchored=True)
    plain = _anchor_pattern(f"{prefix_pattern}{fragment}{suffix_pattern}", profile, anchored=True)
    return [(family, capture), (family, plain)]


def _fallback_candidates(profile: RestrictionProfile) -> List[Tuple[str, str]]:
    if not profile.allow_wildcard_fallback:
        return []
    return [
        (
            "Search-only fallback generalization",
            _anchor_pattern(r"(.+)", profile, anchored=True),
        )
    ]


def _evaluate_candidate(
    family: str,
    pattern: str,
    example_set: RegexExampleSet,
    active_examples: Sequence[_ActiveExample],
    profile: RestrictionProfile,
    *,
    has_full_replace: bool,
) -> Optional[RegexCandidate]:
    if profile.disallow_lookaround and _uses_lookaround(pattern):
        return None
    if profile.disallow_backreferences and _uses_backreference(pattern):
        return None
    if not profile.allow_wildcard_fallback and _uses_broad_wildcard(pattern):
        return None

    compiled = compile_candidate_pattern(pattern, case_sensitive=profile.case_sensitive)
    if compiled is None:
        return None
    if profile.required_capture_groups and compiled.groups < max(profile.required_capture_groups):
        return None

    matches: List[re.Match[str]] = []
    for example in active_examples:
        match = compiled.search(example.search_text)
        if match is None:
            return None
        matches.append(match)

    replace_pattern = ""
    replace_confidence = 0.0
    candidate_warnings: List[str] = []
    if has_full_replace:
        replace_pattern, replace_confidence, replace_warning = infer_replace_pattern(
            compiled,
            [example.search_text for example in active_examples],
            [example.replace_text for example in active_examples],
        )
        if replace_warning and not replace_pattern:
            candidate_warnings.append(replace_warning)
    if profile.require_replace_suggestion and not replace_pattern:
        return None

    annotation_bonus, annotation_warnings = _score_annotation_fit(
        pattern,
        compiled,
        example_set,
        active_examples,
        matches,
    )
    candidate_warnings.extend(annotation_warnings)

    score = 1000.0
    score += _FAMILY_BASE_SCORES.get(family, 0.0)
    if pattern.startswith("^") and pattern.endswith("$"):
        score += 80.0
    if compiled.groups == 0 and not has_full_replace and not profile.required_capture_groups:
        score += 18.0
    elif compiled.groups > 0 and not has_full_replace and not profile.required_capture_groups:
        score -= 8.0
    if profile.prefer_simple and family in _SIMPLE_FAMILIES:
        score += 35.0
    if profile.prefer_strict and pattern.startswith("^") and pattern.endswith("$"):
        score += 25.0
    if profile.preferred_capture_kind != "any":
        if _candidate_uses_capture_kind(pattern, profile.preferred_capture_kind):
            score += 30.0
        else:
            score -= 20.0
    score += annotation_bonus
    score += replace_confidence * 220.0
    score -= _complexity_penalty(pattern, compiled.groups)
    score -= _wildcard_penalty(pattern)

    explanation = _build_explanation(
        family,
        compiled,
        pattern,
        replace_pattern,
        active_examples,
        profile,
    )
    return RegexCandidate(
        search_pattern=pattern,
        replace_pattern=replace_pattern,
        family=family,
        score=score,
        explanation=explanation,
        warnings=tuple(dict.fromkeys(candidate_warnings)),
        flags=0 if profile.case_sensitive else re.IGNORECASE,
        capture_count=compiled.groups,
        replace_confidence=replace_confidence,
    )


def _build_explanation(
    family: str,
    compiled: re.Pattern[str],
    pattern: str,
    replace_pattern: str,
    active_examples: Sequence[_ActiveExample],
    profile: RestrictionProfile,
) -> str:
    reasons = [f"Matches all {len(active_examples)} enabled examples"]
    if pattern.startswith("^") and pattern.endswith("$"):
        reasons.append("stays anchored to the full line")
    if compiled.groups:
        reasons.append(f"uses {compiled.groups} capture group{'s' if compiled.groups != 1 else ''}")
    if replace_pattern:
        reasons.append("reproduces every supplied replace target")
    if profile.preferred_capture_kind == "number" and r"\d+" in pattern:
        reasons.append("captures only the varying number")
    elif profile.preferred_capture_kind == "word" and r"\w+" in pattern:
        reasons.append("stays within word-character matches")
    elif family == "Delimited capture":
        reasons.append("preserves the shared delimiters")
    elif family == "Search-only fallback generalization":
        reasons.append("is intentionally broader than stricter candidates")
    return f"{family}: " + ", ".join(reasons) + "."


def _score_annotation_fit(
    pattern: str,
    compiled: re.Pattern[str],
    example_set: RegexExampleSet,
    active_examples: Sequence[_ActiveExample],
    matches: Sequence[re.Match[str]],
) -> Tuple[float, Tuple[str, ...]]:
    active_texts = {example.row_index: example.search_text for example in active_examples}
    active_matches = {example.row_index: match for example, match in zip(active_examples, matches)}
    score = 0.0
    warnings: List[str] = []

    for annotation in example_set.annotations:
        if annotation.row_kind != ROW_KIND_SEARCH or annotation.row_index not in active_texts:
            continue

        selected_text = _annotation_text(example_set, annotation)
        if not selected_text:
            continue

        kind = _normalized_annotation_kind(annotation)
        match = active_matches[annotation.row_index]
        captured_values = [
            match.group(group_index)
            for group_index in range(1, compiled.groups + 1)
            if match.start(group_index) >= 0
        ]
        detail = _annotation_capture_kind(annotation)

        if kind in {"constant", "literal", "must_literal"}:
            if re.escape(selected_text) in pattern:
                score += 40.0
            else:
                score -= 90.0
                warnings.append(f"Literal span {selected_text!r} is not preserved literally.")
        elif kind in {
            "capture",
            "capture_group",
            "variable",
            "variable_any",
            "variable_number",
            "variable_word",
            "variable_japanese",
            "prefer_digits",
            "prefer_word",
        }:
            if selected_text in captured_values:
                score += 50.0
            elif selected_text in match.group(0):
                score += 10.0
            else:
                score -= 85.0
                warnings.append(f"Marked span {selected_text!r} is not captured cleanly.")
            if detail in {"number", "word", "japanese"}:
                if _candidate_uses_capture_kind(pattern, detail):
                    score += 20.0
                else:
                    score -= 15.0
        elif kind == "ignore" and re.escape(selected_text) in pattern:
            score -= 20.0
        elif kind == "optional" and any(token in pattern for token in ("?", "*")):
            score += 5.0

    return score, tuple(dict.fromkeys(warnings))


def _shared_affix_parts(search_texts: Sequence[str]) -> Tuple[str, str, List[str]]:
    if not search_texts:
        return "", "", []
    prefix = os.path.commonprefix(list(search_texts))
    suffix = _common_suffix(search_texts)
    shortest = min(len(text) for text in search_texts)
    while prefix and suffix and len(prefix) + len(suffix) > shortest:
        suffix = suffix[1:]
    middles = [text[len(prefix) : len(text) - len(suffix) if suffix else len(text)] for text in search_texts]
    if len(set(middles)) <= 1:
        return prefix, suffix, []
    return prefix, suffix, middles


def _family_from_affixes(prefix: str, suffix: str, capture_kind: str) -> str:
    if prefix and suffix and prefix[-1:] in _OPEN_TO_CLOSE and suffix[:1] == _OPEN_TO_CLOSE[prefix[-1:]]:
        return "Delimited capture"
    if capture_kind == "word":
        return "Word wildcard"
    return "Prefix + capture + suffix"


def _capture_fragment(kind: str, *, allow_empty: bool = False) -> str:
    if kind == "number":
        return r"\d*" if allow_empty else r"\d+"
    if kind == "word":
        return r"\w*" if allow_empty else r"\w+"
    if kind == "japanese":
        return _JAPANESE_FRAGMENT.replace("+", "*") if allow_empty else _JAPANESE_FRAGMENT
    return r".*?" if allow_empty else r".+"


def _select_capture_kind(
    values: Sequence[str],
    profile: RestrictionProfile,
    explicit_kinds: Sequence[str] = (),
) -> str:
    explicit = [kind for kind in explicit_kinds if kind in {"number", "word", "japanese", "any"}]
    if explicit:
        for preferred in ("number", "word", "japanese", "any"):
            if preferred in explicit:
                return preferred
    if profile.preferred_capture_kind in {"number", "word", "japanese"}:
        return profile.preferred_capture_kind
    if values and all(value.isdigit() for value in values if value):
        return "number"
    return "any"


def _segments_equivalent(values: Sequence[str], profile: RestrictionProfile) -> bool:
    if not values:
        return True
    if profile.ignore_spaces:
        normalized = [_collapse_whitespace(value) for value in values]
    elif profile.ignore_leading_spaces or profile.ignore_trailing_spaces:
        normalized = [
            _trim_boundary_spaces(
                value,
                ignore_leading=profile.ignore_leading_spaces,
                ignore_trailing=profile.ignore_trailing_spaces,
            )
            for value in values
        ]
    else:
        normalized = list(values)
    return len(set(normalized)) == 1


def _coerce_row(value: RegexExampleRow | str) -> RegexExampleRow:
    if isinstance(value, RegexExampleRow):
        return RegexExampleRow(text=normalize_text_value(value.text), enabled=bool(value.enabled))
    return RegexExampleRow(text=normalize_text_value(str(value)), enabled=True)


def _normalize_example_set(example_set: RegexExampleSet) -> RegexExampleSet:
    search_rows, replace_rows = ensure_row_alignment(
        example_set.search_rows,
        example_set.replace_rows,
        example_set.mode,
    )
    normalized_annotations = tuple(
        SpanAnnotation(
            row_kind=annotation.row_kind,
            row_index=int(annotation.row_index),
            start=max(0, int(annotation.start)),
            end=max(0, int(annotation.end)),
            annotation_type=str(annotation.annotation_type),
            detail=str(annotation.detail),
            scope=str(annotation.scope),
            hover_label=str(annotation.hover_label),
            capture_group=max(0, int(annotation.capture_group)),
        )
        for annotation in example_set.annotations
    )
    options = RegexMakerOptions(
        match_whole_line=bool(example_set.options.match_whole_line),
        ignore_spaces=bool(example_set.options.ignore_spaces),
        ignore_leading_spaces=bool(example_set.options.ignore_leading_spaces),
        ignore_trailing_spaces=bool(example_set.options.ignore_trailing_spaces),
        case_sensitive=bool(example_set.options.case_sensitive),
        prefer_simple=bool(example_set.options.prefer_simple),
        prefer_strict=bool(example_set.options.prefer_strict),
        allow_wildcard_fallback=bool(example_set.options.allow_wildcard_fallback),
        disallow_lookaround=bool(example_set.options.disallow_lookaround),
        disallow_backreferences=bool(example_set.options.disallow_backreferences),
        require_replace_suggestion=bool(example_set.options.require_replace_suggestion),
        max_candidates=max(1, min(20, int(example_set.options.max_candidates))),
    )
    return RegexExampleSet(
        search_rows=search_rows,
        replace_rows=replace_rows,
        mode=MODE_SEARCH_REPLACE if example_set.mode == MODE_SEARCH_REPLACE else MODE_SEARCH_ONLY,
        annotations=normalized_annotations,
        options=options,
        notes=str(example_set.notes),
        compatibility_profile=str(example_set.compatibility_profile),
    )


def _serialize_example_set(example_set: RegexExampleSet) -> Dict[str, Any]:
    return {
        "search_rows": [asdict(row) for row in example_set.search_rows],
        "replace_rows": [asdict(row) for row in example_set.replace_rows],
        "mode": example_set.mode,
        "annotations": [asdict(annotation) for annotation in example_set.annotations],
        "options": asdict(example_set.options),
        "notes": example_set.notes,
        "compatibility_profile": example_set.compatibility_profile,
    }


def _deserialize_example_set(payload: Dict[str, Any]) -> RegexExampleSet:
    search_rows = tuple(RegexExampleRow(**row) for row in payload.get("search_rows", []))
    replace_rows = tuple(RegexExampleRow(**row) for row in payload.get("replace_rows", []))
    annotations = tuple(SpanAnnotation(**annotation) for annotation in payload.get("annotations", []))
    options = RegexMakerOptions(**payload.get("options", {}))
    return RegexExampleSet(
        search_rows=search_rows,
        replace_rows=replace_rows,
        mode=str(payload.get("mode", MODE_SEARCH_ONLY)),
        annotations=annotations,
        options=options,
        notes=str(payload.get("notes", "")),
        compatibility_profile=str(payload.get("compatibility_profile", "CherryAI (re, ignore-case search)")),
    )


def _active_examples(example_set: RegexExampleSet) -> Tuple[_ActiveExample, ...]:
    active: List[_ActiveExample] = []
    for row_index, search_row in enumerate(example_set.search_rows):
        if not search_row.enabled:
            continue
        search_text = normalize_text_value(search_row.text)
        if not search_text.strip():
            continue
        replace_text = ""
        if row_index < len(example_set.replace_rows):
            replace_text = normalize_text_value(example_set.replace_rows[row_index].text)
        active.append(
            _ActiveExample(
                row_index=row_index,
                search_text=search_text,
                replace_text=replace_text,
            )
        )
    return tuple(active)


def _has_partial_replace_pairs(active_examples: Sequence[_ActiveExample]) -> bool:
    has_any = any(example.replace_text.strip() for example in active_examples)
    return has_any and not _has_full_replace_pairs(active_examples)


def _has_full_replace_pairs(active_examples: Sequence[_ActiveExample]) -> bool:
    return bool(active_examples) and all(example.replace_text.strip() for example in active_examples)


def _append_candidate_spec(
    candidate_specs: List[Tuple[str, str]],
    seen: set[Tuple[str, str]],
    family: str,
    pattern: str,
) -> None:
    key = (family, pattern)
    if not pattern or key in seen:
        return
    seen.add(key)
    candidate_specs.append((family, pattern))


def _escape_literal_segment(
    text: str,
    profile: RestrictionProfile,
    *,
    boundary_mode: str = "literal",
) -> str:
    if not text:
        return ""

    leading_match = re.match(r"\s*", text)
    trailing_match = re.search(r"\s*$", text)
    leading = leading_match.group(0) if leading_match else ""
    trailing = trailing_match.group(0) if trailing_match else ""
    core_start = len(leading)
    core_end = len(text) - len(trailing) if trailing else len(text)
    core = text[core_start:core_end]
    parts: List[str] = []
    if leading:
        if profile.ignore_spaces or profile.ignore_leading_spaces or boundary_mode in {"relaxed-leading", "relaxed-both"}:
            parts.append(r"\s*")
        else:
            parts.append(re.escape(leading))
    parts.append(_escape_core_with_spaces(core, flexible_spaces=profile.ignore_spaces))
    if trailing:
        if profile.ignore_spaces or profile.ignore_trailing_spaces or boundary_mode in {"relaxed-trailing", "relaxed-both"}:
            parts.append(r"\s*")
        else:
            parts.append(re.escape(trailing))
    return "".join(parts)


def _escape_core_with_spaces(text: str, *, flexible_spaces: bool) -> str:
    parts: List[str] = []
    for chunk in re.split(r"(\s+)", text):
        if not chunk:
            continue
        if chunk.isspace():
            parts.append(r"\s+" if flexible_spaces else re.escape(chunk))
        else:
            parts.append(re.escape(chunk))
    return "".join(parts)


def _anchor_pattern(pattern: str, profile: RestrictionProfile, *, anchored: bool) -> str:
    if pattern == "":
        return pattern
    if anchored or profile.match_whole_line:
        if not pattern.startswith("^"):
            pattern = f"^{pattern}"
        if not pattern.endswith("$"):
            pattern = f"{pattern}$"
    return pattern


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _trim_boundary_spaces(text: str, *, ignore_leading: bool, ignore_trailing: bool) -> str:
    result = text
    if ignore_leading:
        result = result.lstrip()
    if ignore_trailing:
        result = result.rstrip()
    return result


def _annotation_text(example_set: RegexExampleSet, annotation: SpanAnnotation) -> str:
    rows = example_set.search_rows if annotation.row_kind == ROW_KIND_SEARCH else example_set.replace_rows
    if annotation.row_index < 0 or annotation.row_index >= len(rows):
        return ""
    text = rows[annotation.row_index].text
    start = max(0, min(len(text), int(annotation.start)))
    end = max(start, min(len(text), int(annotation.end)))
    return text[start:end]


def _annotation_capture_kind(annotation: SpanAnnotation) -> str:
    detail = str(annotation.detail or "").strip().lower().replace(" ", "_")
    if detail in {"number", "word", "any", "japanese"}:
        return detail
    kind = _normalized_annotation_kind(annotation)
    if kind in {"variable_number", "prefer_digits"}:
        return "number"
    if kind in {"variable_word", "prefer_word"}:
        return "word"
    if kind == "variable_japanese":
        return "japanese"
    return "any"


def _normalized_annotation_kind(annotation: SpanAnnotation) -> str:
    return str(annotation.annotation_type or "").strip().lower().replace(" ", "_")


def _set_note_override(
    overrides: Dict[str, Any],
    warnings: List[str],
    key: str,
    value: Any,
    command: str,
) -> None:
    if key in overrides and overrides[key] != value:
        warnings.append(f"Conflicting command ignored: {command}")
        return
    overrides[key] = value


def _split_commands(notes: str) -> Iterable[str]:
    for raw in re.split(r"[\n,;]+", notes):
        command = raw.strip().lower()
        if command:
            yield command


def _common_suffix(values: Sequence[str]) -> str:
    reversed_values = [value[::-1] for value in values]
    return os.path.commonprefix(reversed_values)[::-1]


def _is_word_like(value: str) -> bool:
    return bool(_WORD_RE.fullmatch(value))


def _candidate_uses_capture_kind(pattern: str, kind: str) -> bool:
    if kind == "number":
        return r"\d+" in pattern or r"\d*" in pattern
    if kind == "word":
        return r"\w+" in pattern or r"\w*" in pattern
    if kind == "japanese":
        return _JAPANESE_FRAGMENT in pattern
    return True


def _uses_lookaround(pattern: str) -> bool:
    return any(token in pattern for token in ("(?=", "(?!", "(?<=", "(?<!"))


def _uses_backreference(pattern: str) -> bool:
    return bool(re.search(r"\\[1-9]", pattern))


def _uses_broad_wildcard(pattern: str) -> bool:
    return any(token in pattern for token in (".*", ".+")) and r"\d" not in pattern


def _complexity_penalty(pattern: str, capture_count: int) -> float:
    penalty = (len(pattern) / 14.0) + (capture_count * 10.0)
    penalty += pattern.count("|") * 25.0
    penalty += pattern.count("(?:") * 4.0
    if _uses_lookaround(pattern):
        penalty += 40.0
    if _uses_backreference(pattern):
        penalty += 55.0
    return penalty


def _wildcard_penalty(pattern: str) -> float:
    penalty = 0.0
    penalty += pattern.count(".*") * 55.0
    penalty += pattern.count(".+") * 22.0
    if not pattern.startswith("^") or not pattern.endswith("$"):
        penalty += 15.0
    return penalty


__all__ = [
    "MODE_SEARCH_ONLY",
    "MODE_SEARCH_REPLACE",
    "ROW_KIND_REPLACE",
    "ROW_KIND_SEARCH",
    "RegexCandidate",
    "RegexExampleRow",
    "RegexExampleSet",
    "RegexGenerationResult",
    "RegexMakerOptions",
    "RestrictionProfile",
    "SpanAnnotation",
    "build_restriction_profile",
    "compile_candidate_pattern",
    "ensure_row_alignment",
    "generate_regex_suggestions",
    "infer_replace_pattern",
    "normalize_text_value",
]