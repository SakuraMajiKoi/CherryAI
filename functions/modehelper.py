from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

"""
Shared helpers for multiple modes (kept minimal):
 - PROT_PATTERN / PROT_TOKEN and their compression helpers
 - EMPTY_LINE_PLACEHOLDER sentinel

The anchor-specific helpers were moved into the anchor mode module
('modi/anchor.py') to keep responsibility localized.
"""

# Empty-line sentinel used by Pre/Post pipelines to mark lines that became empty
EMPTY_LINE_PLACEHOLDER = "__EMPTY__"

# PROTECTED placeholder regex (detection-only helper)
PROT_REGEX = re.compile(r"__\s*PROT\s*__")


# --- Anchor helpers moved to 'modi/anchor.py' --- #

# Anchor equivalence map shared across modes and analysis routines.
# Includes fullwidth variants and common typographic quote alternatives.
ANCHOR_EQUIVS: Dict[str, List[str]] = {
	"[": ["[", "［"],
	"]": ["]", "］"],
	"{": ["{", "｛"],
	"}": ["}", "｝"],
	"<": ["<", "＜"],
	">": [">", "＞"],
	"_": ["_", "＿"],
	'"': ['"', "＂", "“", "”", "„", "「", "」"],
	"!": ["!", "！"],
	"?": ["?", "？"],
	".": [".", "．", "。", "…"],
	",": [",", "，", "、", "､"],
	":": [":", "："],
	"(": ["(", "（"],
	")": [")", "）"],
}


def get_equivs(ch: str) -> List[str]:
	"""Return the list of equivalent characters for a given anchor character."""
	return ANCHOR_EQUIVS.get(ch, [ch])


def find_all_equiv_positions(s: str, ch: str) -> List[Tuple[int, str]]:
	"""Find all positions of any equivalent of `ch` in string `s`.

	Returns a list of tuples (position, matched_equiv) sorted by position.
	"""
	hits: List[Tuple[int, str]] = []
	for e in get_equivs(ch):
		start = 0
		while True:
			pos = s.find(e, start)
			if pos == -1:
				break
			hits.append((pos, e))
			start = pos + len(e)
	hits.sort(key=lambda x: x[0])
	return hits


def restore_placeholders_in_line(
	line: str,
	token: str,
	values: list,
	allow_anchor_fallback: bool = True,
	anchor_hint: str | None = None,
) -> tuple[str, int, bool]:
	"""Try to restore placeholders in a single line using several fallbacks.

	- Exact token replacement (e.g. '__CUST__').
	- Generic placeholder span match (e.g. '__...__' or '____').
	- Fuzzy match of the inner token (case-insensitive) and consume surrounding underscores.
	- Optional anchor fallback: insert at line start or end when nothing else matches.

	The provided ``values`` list is mutated (items popped) as replacements are consumed.

	Returns (new_line, replaced_count, used_anchor_fallback).
	"""
	import re

	if not token:
		return line, 0, False


	# SAFE_ANCHOR_CHARS: characters generally safe to use as anchors
	SAFE_ANCHOR_CHARS: List[str] = ["[", "]", "{", "}", "<", ">", "_", "!", "?", ".", ",", '"']

	replaced = 0
	used_anchor = False

	def _pop_value() -> str:
		return values.pop(0) if values else ""

	# 1) Exact token replacement
	try:
		if token:
			pattern = re.escape(token)
			def _repl_exact(m: re.Match[str]) -> str:
				return _pop_value()
			new_line, count = re.subn(pattern, _repl_exact, line)
			if count:
				return new_line, count, False
	except Exception:
		new_line = line

	# 2) Generic span-match: two-or-more underscores, non-underscore inside
	try:
		span_pat = re.compile(r"_{2,}[^_]{1,}?_{2,}")
		def _repl_span(m: re.Match[str]) -> str:
			return _pop_value()
		new_line, count = span_pat.subn(_repl_span, line)
		if count:
			return new_line, count, False
	except Exception:
		new_line = line

	# 3) Fuzzy inner match: search for inner token characters and consume surrounding underscores
	try:
		inner = token.strip("_")
		if inner and len(inner) >= 3:
			# find case-insensitive occurrence of a 3-char prefix of inner
			prefix = re.escape(inner[:3])
			m = re.search(prefix, line, flags=re.IGNORECASE)
			if m:
				# expand left/right to include contiguous underscores
				s = m.start()
				e = m.end()
				# include underscores to the left
				while s > 0 and line[s - 1] == "_":
					s -= 1
				# include underscores to the right
				while e < len(line) and line[e] == "_":
					e += 1
				new_line = line[:s] + _pop_value() + line[e:]
				return new_line, 1, False
	except Exception:
		new_line = line

	# 4) Anchor fallback (safe): insert at line start or end only when an explicit
	# anchor_hint ('start' or 'end') is provided. This prevents uncontrolled
	# insertion in the middle of lines for non-anchor modes.
	if allow_anchor_fallback and values and anchor_hint in ("start", "end"):
		try:
			v = _pop_value()
			if anchor_hint == "start":
				new_line = v + line
			else:
				new_line = line + v
			used_anchor = True
			return new_line, 1, True
		except Exception:
			pass

	return line, 0, False


def _replace_exact_token_occurrences(
	line: str,
	token: str,
	values: List[str],
) -> Tuple[str, int]:
	"""Replace exact token occurrences left-to-right using queued values."""
	if not token or not values:
		return line, 0

	replaced = 0
	result = line
	while values:
		pos = result.find(token)
		if pos < 0:
			break
		value = values.pop(0)
		result = result[:pos] + value + result[pos + len(token):]
		replaced += 1
	return result, replaced


def restore_custom_placeholders_batch(
	lines: List[str],
	records_by_line: Dict[int, List[Dict[str, Any]]],
) -> Tuple[List[str], Dict[str, int], Dict[str, List[str]]]:
	"""Restore custom placeholders across a whole batch of lines.

	This performs normal per-line restoration first, then a document-wide
	exact-token fallback for any remaining values. The global fallback lets a
	placeholder token restored by the LLM on the wrong line still be recovered.

	Args:
		lines: Translated lines to restore.
		records_by_line: ``{line_idx: [{token, values}, ...]}`` captured during pre.

	Returns:
		Tuple of ``(restored_lines, stats, residuals)`` where *stats* contains
		``local_restored``, ``global_restored``, and ``preexisting_consumed`` counts,
		and *residuals* maps tokens to unrecovered original values.
	"""
	result = list(lines)
	pending_by_token: Dict[str, List[str]] = {}
	residuals_by_token: Dict[str, List[str]] = {}
	local_restored = 0
	global_restored = 0
	preexisting_consumed = 0

	for idx, line in enumerate(result):
		recs = records_by_line.get(idx, [])
		if not recs:
			continue

		new_line = line
		for rec in recs:
			token = str(rec.get("token", "") or "").strip()
			values = [str(v) for v in (rec.get("values", []) or []) if v is not None]
			if not token or not values:
				continue

			# If another path already restored the original value on this line,
			# consume it so residual reporting stays accurate.
			while values and values[0] and values[0] in new_line:
				values.pop(0)
				preexisting_consumed += 1

			new_line, count, _used_anchor = restore_placeholders_in_line(
				new_line,
				token,
				values,
				allow_anchor_fallback=False,
				anchor_hint=None,
			)
			local_restored += count

			if values:
				if bool(rec.get("recover_everywhere", False)):
					pending_by_token.setdefault(token, []).extend(values)
				else:
					residuals_by_token.setdefault(token, []).extend(values)

		result[idx] = new_line

	if pending_by_token:
		for idx, line in enumerate(result):
			new_line = line
			for token, values in pending_by_token.items():
				new_line, count = _replace_exact_token_occurrences(
					new_line,
					token,
					values,
				)
				global_restored += count
			result[idx] = new_line

	for token, values in pending_by_token.items():
		if values:
			residuals_by_token.setdefault(token, []).extend(list(values))

	residuals = {
		token: list(values)
		for token, values in residuals_by_token.items()
		if values
	}
	stats = {
		"local_restored": local_restored,
		"global_restored": global_restored,
		"preexisting_consumed": preexisting_consumed,
	}
	return result, stats, residuals
