"""Search helpers for the Editor full-file surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
import re
from typing import Iterable, Mapping, Sequence


LINE_SCOPE_ALL = "all"
LINE_SCOPE_PARSED = "parsed"
LINE_SCOPE_NOT_PARSED = "not_parsed"


@dataclass(frozen=True)
class EditorSearchOptions:
	query: str = ""
	replace: str = ""
	use_regex: bool = False
	case_sensitive_search: bool = False
	case_sensitive_replace: bool = False
	whole_word: bool = False
	file_patterns: str = ""
	current_file_only: bool = False
	line_scope: str = LINE_SCOPE_ALL


@dataclass(frozen=True)
class EditorSearchMatch:
	rel_path: str
	start: int
	end: int
	line: int
	column: int
	preview: str


@dataclass(frozen=True)
class EditorFileSearchResult:
	rel_path: str
	matches: tuple[EditorSearchMatch, ...] = field(default_factory=tuple)


def text_offset_to_index(text: str, offset: int) -> str:
	"""Convert a character offset into Tk text ``line.column`` form."""
	safe_offset = min(max(offset, 0), len(text))
	line = text.count("\n", 0, safe_offset) + 1
	line_start = text.rfind("\n", 0, safe_offset)
	column = safe_offset if line_start < 0 else safe_offset - line_start - 1
	return f"{line}.{column}"


def compile_search_pattern(options: EditorSearchOptions, *, for_replace: bool = False) -> re.Pattern[str] | None:
	"""Build a compiled search pattern from Editor options."""
	query = options.query
	if not query:
		return None
	source = query if options.use_regex else re.escape(query)
	if options.whole_word:
		source = rf"\b(?:{source})\b"
	flags = re.MULTILINE
	case_sensitive = options.case_sensitive_replace if for_replace else options.case_sensitive_search
	if not case_sensitive:
		flags |= re.IGNORECASE
	try:
		return re.compile(source, flags)
	except re.error:
		return None


def find_search_spans(text: str, options: EditorSearchOptions) -> list[tuple[int, int]]:
	"""Return non-overlapping spans matching the Editor search options."""
	pattern = compile_search_pattern(options)
	if pattern is None:
		return []
	return [
		(match.start(), match.end())
		for match in pattern.finditer(text)
		if match.end() > match.start()
	]


def find_search_match_ranges(text: str, options: EditorSearchOptions) -> list[tuple[str, str]]:
	"""Return Tk text ranges matching the Editor search options."""
	return [
		(text_offset_to_index(text, start), text_offset_to_index(text, end))
		for start, end in find_search_spans(text, options)
	]


def parsed_line_numbers(locator_metadata: Iterable[Mapping[str, object]]) -> set[int]:
	"""Return physical editor lines covered by parser locator metadata."""
	lines: set[int] = set()
	for metadata in locator_metadata:
		if not metadata.get("matched"):
			continue
		try:
			start_line = int(str(metadata.get("editor_ln", "")).strip())
		except (TypeError, ValueError):
			continue
		try:
			line_count = max(1, int(str(metadata.get("editor_line_count", 1)).strip()))
		except (TypeError, ValueError):
			line_count = 1
		for line in range(start_line, start_line + line_count):
			lines.add(line)
	return lines


def line_number_for_offset(text: str, offset: int) -> int:
	"""Return the one-based line number containing *offset*."""
	return text.count("\n", 0, min(max(offset, 0), len(text))) + 1


def span_line_numbers(text: str, start: int, end: int) -> set[int]:
	"""Return one-based line numbers touched by a match span."""
	if end <= start:
		return {line_number_for_offset(text, start)}
	last_offset = max(start, end - 1)
	return set(range(line_number_for_offset(text, start), line_number_for_offset(text, last_offset) + 1))


def filter_spans_by_line_scope(
	text: str,
	spans: Sequence[tuple[int, int]],
	*,
	line_scope: str,
	parsed_lines: set[int],
) -> list[tuple[int, int]]:
	"""Filter spans by parsed/not-parsed line ownership."""
	if line_scope == LINE_SCOPE_ALL:
		return list(spans)
	filtered: list[tuple[int, int]] = []
	for start, end in spans:
		match_lines = span_line_numbers(text, start, end)
		touches_parsed = bool(match_lines & parsed_lines)
		if line_scope == LINE_SCOPE_PARSED and touches_parsed:
			filtered.append((start, end))
		elif line_scope == LINE_SCOPE_NOT_PARSED and not touches_parsed:
			filtered.append((start, end))
	return filtered


def parse_file_patterns(raw_patterns: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
	"""Split include/exclude file patterns; exclusions begin with ``!``."""
	tokens = [
		token.strip()
		for chunk in str(raw_patterns or "").replace(";", ",").split(",")
		for token in chunk.split()
		if token.strip()
	]
	includes: list[str] = []
	excludes: list[str] = []
	for token in tokens:
		if token.startswith("!") and token[1:].strip():
			excludes.append(token[1:].strip())
		else:
			includes.append(token)
	return tuple(includes), tuple(excludes)


def file_matches_patterns(rel_path: str, raw_patterns: str) -> bool:
	"""Return whether *rel_path* is allowed by include/exclude glob patterns."""
	includes, excludes = parse_file_patterns(raw_patterns)
	normalized = str(rel_path).replace("\\", "/")
	name = normalized.rsplit("/", 1)[-1]

	def matches(pattern: str) -> bool:
		pat = pattern.replace("\\", "/")
		return fnmatchcase(normalized.lower(), pat.lower()) or fnmatchcase(name.lower(), pat.lower())

	if includes and not any(matches(pattern) for pattern in includes):
		return False
	return not any(matches(pattern) for pattern in excludes)


def build_match_preview(text: str, start: int, end: int, *, max_chars: int = 160) -> str:
	"""Return a compact single-line preview for a match."""
	line_start = text.rfind("\n", 0, start) + 1
	line_end = text.find("\n", end)
	if line_end < 0:
		line_end = len(text)
	line = text[line_start:line_end].strip()
	if len(line) <= max_chars:
		return line
	return line[: max_chars - 1].rstrip() + "..."


def search_editor_files(
	files: Iterable[tuple[str, str, Iterable[Mapping[str, object]]]],
	options: EditorSearchOptions,
) -> list[EditorFileSearchResult]:
	"""Search ordered ``(rel_path, text, locator_metadata)`` file payloads."""
	return list(iter_search_editor_file_results(files, options))


def iter_search_editor_file_results(
	files: Iterable[tuple[str, str, Iterable[Mapping[str, object]]]],
	options: EditorSearchOptions,
) -> Iterable[EditorFileSearchResult]:
	"""Yield per-file search results without forcing a full search upfront."""
	if not options.query:
		return
	for rel_path, text, locator_metadata in files:
		if not file_matches_patterns(rel_path, options.file_patterns):
			continue
		spans = find_search_spans(text, options)
		spans = filter_spans_by_line_scope(
			text,
			spans,
			line_scope=options.line_scope,
			parsed_lines=parsed_line_numbers(locator_metadata),
		)
		matches = tuple(
			EditorSearchMatch(
				rel_path=rel_path,
				start=start,
				end=end,
				line=line_number_for_offset(text, start),
				column=max(0, start - (text.rfind("\n", 0, start) + 1)),
				preview=build_match_preview(text, start, end),
			)
			for start, end in spans
		)
		if matches:
			yield EditorFileSearchResult(rel_path=rel_path, matches=matches)


def replace_all(text: str, options: EditorSearchOptions) -> tuple[str, int]:
	"""Replace all matches in one text buffer with Editor replacement semantics."""
	pattern = compile_search_pattern(options, for_replace=True)
	if pattern is None:
		return text, 0
	return pattern.subn(options.replace, text)


def replace_all_scoped(
	text: str,
	options: EditorSearchOptions,
	*,
	parsed_lines: set[int] | None = None,
) -> tuple[str, int]:
	"""Replace all matches while honoring parsed/not-parsed line scope."""
	pattern = compile_search_pattern(options, for_replace=True)
	if pattern is None:
		return text, 0
	parsed = parsed_lines or set()
	replacements: list[tuple[int, int, str]] = []
	for match in pattern.finditer(text):
		if match.end() <= match.start():
			continue
		spans = filter_spans_by_line_scope(
			text,
			[(match.start(), match.end())],
			line_scope=options.line_scope,
			parsed_lines=parsed,
		)
		if not spans:
			continue
		replacements.append((match.start(), match.end(), match.expand(options.replace)))
	if not replacements:
		return text, 0
	new_text = text
	for start, end, replacement in reversed(replacements):
		new_text = new_text[:start] + replacement + new_text[end:]
	return new_text, len(replacements)
