"""Dry-run-only sabotage mode.

This plugin runs in the Pre phase and is intended to run last (high PRIORITY).
It only activates when the manifest indicates a dry run (manifest.metadata['dry_run']==True).

Behavior (heuristic):
- Find contiguous runs of Japanese characters (Kanji, Hiragana, Katakana).
- Replace each run with a short sequence of English words drawn from a small
  builtin wordlist. The number of words is proportional to the script:
  ~1.2 words per Kanji character, ~1 word per two Hiragana/Katakana chars.
- Replacement is deterministic per-line using a local RNG seeded from the
  manifest and line index so repeated dry runs are reproducible.

This deliberately noisy transform is intended to exercise other modes during
dry-run validation without requiring an external translation library.
"""

from __future__ import annotations

import hashlib
import random
import re
from typing import List, Tuple

# Plugin metadata
NAME = "Sabotage (Dry Run Only)"
PHASE = "Pre"
# Large PRIORITY so it runs after other pre-phase modes (lower priorities run first)
PRIORITY = 1000
# Signal to the processor that this mode should run automatically on Dry Run
ALWAYS_ON_DRY_RUN = True

# Module-level enable switch. Set to "TRUE" to enable, "FALSE" to disable.
# This is intentionally a string to match the user's requested format.
IsEnabled = "TRUE"

# Small English word list (kept intentionally tiny to avoid external deps)
_WORDLIST = (
	"alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron"
	" pi rho sigma tau upsilon phi chi psi omega quick brown fox jumps over lazy dog"
).split()

_PLACEHOLDER_RE = re.compile(r"__.*?__")

# Deterministic module-level salt — configurable constant used to derive RNG seeds
SAKURAKO1 = "SAKURAKO1"


def _sha1_int(s: str) -> int:
	return int(hashlib.sha1(s.encode("utf-8")).hexdigest()[:16], 16)


def _collect_placeholders(lines: List[str]) -> List[Tuple[int, int, int]]:
	"""Return a list of (line_idx, start, end) for placeholders matching __.*?__."""
	found: List[Tuple[int, int, int]] = []
	for i, line in enumerate(lines):
		for m in _PLACEHOLDER_RE.finditer(line):
			found.append((i, m.start(), m.end()))
	return found


def _transform_placeholder(substr: str, act: str, rng: random.Random) -> str:
	# Guard: ensure expected shape
	if not (substr.startswith("__") and substr.endswith("__")):
		return substr
	inner = substr[2:-2]
	if act == "remove_leading":
		return substr[1:]
	if act == "remove_trailing":
		return substr[:-1]
	if act == "strip_sides":
		return inner
	if act == "remove_inner_char":
		if inner:
			idx = rng.randrange(len(inner))
			inner = inner[:idx] + inner[idx + 1 :]
		return f"__{inner}__"
	if act == "remove_inner_all":
		return "____"
	if act == "remove_all":
		return ""
	if act == "replace_inner_word":
		return f"__{rng.choice(_WORDLIST)}__"
	return substr


def _apply_act(lines: List[str], act: str, base_seed: int, stats: dict, per_line_map: dict | None = None) -> int:
	"""Apply an act to up to 5 randomly chosen placeholders. Return #lines changed."""
	matches = _collect_placeholders(lines)
	if not matches:
		return 0
	# Deterministic RNG per act label
	rng = random.Random(base_seed ^ _sha1_int(f"sabotage:{act}"))
	k = min(5, len(matches))
	picks_idx = rng.sample(range(len(matches)), k=k)
	# Group selections by line and sort by start desc to avoid index shifts
	picks_by_line: dict[int, List[Tuple[int, int]]] = {}
	for j in picks_idx:
		li, s, e = matches[j]
		picks_by_line.setdefault(li, []).append((s, e))
	changed_lines = 0
	for li, spans in picks_by_line.items():
		spans.sort(key=lambda t: t[0], reverse=True)
		orig = lines[li]
		new = orig
		# Use a per-line RNG derived from act RNG for stable inner-char choices
		line_rng = random.Random(rng.random())
		for s, e in spans:
			sub = new[s:e]
			rep = _transform_placeholder(sub, act, line_rng)
			new = new[:s] + rep + new[e:]
		if new != orig:
			lines[li] = new
			changed_lines += 1
			if per_line_map is not None:
				per_line_map.setdefault(li, []).append(act)
	if k:
		stats[f"sabotage:{act}"] = stats.get(f"sabotage:{act}", 0) + k
	return changed_lines


def _is_japanese_char(ch: str) -> bool:
	o = ord(ch)
	# Hiragana
	if 0x3040 <= o <= 0x309F:
		return True
	# Katakana (including halfwidth)
	if 0x30A0 <= o <= 0x30FF or 0xFF66 <= o <= 0xFF9F:
		return True
	# Common CJK Unified Ideographs (Kanji)
	if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
		return True
	# CJK Compatibility Ideographs
	if 0xF900 <= o <= 0xFAFF:
		return True
	return False


def _split_japanese_runs(s: str) -> List[Tuple[bool, str]]:
	"""Return list of tuples (is_japanese_run, text)."""
	if not s:
		return []
	runs: List[Tuple[bool, str]] = []
	cur_is_j = _is_japanese_char(s[0])
	cur = [s[0]]
	for ch in s[1:]:
		is_j = _is_japanese_char(ch)
		if is_j == cur_is_j:
			cur.append(ch)
		else:
			runs.append((cur_is_j, "".join(cur)))
			cur = [ch]
			cur_is_j = is_j
	runs.append((cur_is_j, "".join(cur)))
	return runs


def _choose_words(rng: random.Random, count: int) -> str:
	words = [rng.choice(_WORDLIST) for _ in range(max(1, int(count)))]
	return " ".join(words)


def apply_pre(processor, lines: List[str], op, stats: dict) -> int:
	"""Pseudo-translate Japanese runs in-place when running as a dry run.

	Returns number of lines changed (for logging/stats).
	"""
	# Respect the module-level enable toggle. Accept string values "TRUE"/"FALSE" (case-insensitive).
	try:
		enabled_raw = globals().get("IsEnabled", "TRUE")
		enabled = str(enabled_raw).strip().upper() in ("1", "TRUE", "YES", "ON")
	except Exception:
		enabled = True
	if not enabled:
		return 0

	try:
		dry = bool(processor.manifest.metadata.get("dry_run"))
	except Exception:
		dry = False
	if not dry:
		return 0

	# Seed RNG deterministically from module salt + manifest summary/created_utc so runs are reproducible
	manifest_seed = f"{SAKURAKO1}|{getattr(processor.manifest, 'summary', '')}|{processor.manifest.metadata.get('created_utc', '')}"
	base_seed = int(hashlib.sha1(manifest_seed.encode("utf-8")).hexdigest()[:16], 16)

	changed = 0
	for idx, line in enumerate(lines):
		runs = _split_japanese_runs(line)
		if not any(is_j for is_j, _ in runs):
			continue
		# Create RNG per-line for determinism
		rng = random.Random(base_seed ^ (idx + 0x9e3779b97f4a7c15))
		out_parts: List[str] = []
		line_changed = False
		for is_j, seg in runs:
			if not is_j:
				out_parts.append(seg)
				continue
			# Count kanji vs kana within segment
			kanji_count = sum(1 for ch in seg if (0x4E00 <= ord(ch) <= 0x9FFF or 0x3400 <= ord(ch) <= 0x4DBF or 0xF900 <= ord(ch) <= 0xFAFF))
			kana_count = sum(1 for ch in seg if (0x3040 <= ord(ch) <= 0x309F or 0x30A0 <= ord(ch) <= 0x30FF or 0xFF66 <= ord(ch) <= 0xFF9F))
			# Heuristic word counts
			words_for_kanji = int(round(1.2 * kanji_count)) if kanji_count else 0
			words_for_kana = int(round(0.5 * kana_count)) if kana_count else 0
			total_words = max(1, words_for_kanji + words_for_kana)
			replacement = _choose_words(rng, total_words)
			out_parts.append(replacement)
			line_changed = True
		new_line = "".join(out_parts)
		if line_changed and new_line != line:
			lines[idx] = new_line
			changed += 1
			try:
				processor.trace_op(idx, "Pre", NAME, f"sabotage {len(new_line)}")
			except Exception:
				pass

	# Phase 2: placeholder sabotage — perform 7 acts, 5 picks each (up to available)
	acts = [
		"remove_leading",
		"remove_trailing",
		"strip_sides",
		"remove_inner_char",
		"remove_inner_all",
		"remove_all",
		"replace_inner_word",
	]
	total_lines_changed = 0
	per_line_map: dict = {}
	for act in acts:
		total_lines_changed += _apply_act(lines, act, base_seed, stats, per_line_map)
	# Record per-line sabotage details in the manifest mappings so reporting can pick it up
	try:
		processor.manifest.mappings.setdefault("sabotage_lines", {})
		sl = processor.manifest.mappings.get("sabotage_lines", {})
		for li, acts_done in per_line_map.items():
			sl.setdefault(str(li), []).extend(acts_done)
		processor.manifest.mappings["sabotage_lines"] = sl
	except Exception:
		pass
	if total_lines_changed:
		changed += total_lines_changed
		try:
			# Mark each changed line with a trace entry
			ph_matches = _collect_placeholders(lines)
			touched = {li for li, _, _ in ph_matches}
			for li in touched:
				processor.trace_op(li, "Pre", NAME, f"placeholder {len(lines[li])}")
		except Exception:
			pass

	if changed:
		stats_key = f"sabotage:{NAME}"
		stats[stats_key] = stats.get(stats_key, 0) + changed
	return changed

