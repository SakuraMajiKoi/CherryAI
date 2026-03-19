**Current Structure:**

The current Wordwrap path is split across three layers that do not line up cleanly enough:

- gui/steps/wordwrap_overwrite.py owns most orchestration, per-tag settings, preview rows, and the Apply flow.
- functions/wordwrap.py owns the generic wrapping algorithms and speaker/code-aware width handling.
- formats/LightVN.py owns engine-specific textbox syntax and final dialogue injection.

This is workable, but the failure mode in the current implementation showed the main weakness: the step had multiple sources of truth for the same line set.

Current runtime flow:

1. Step 8 loads stage-bounded input through `qa_overwrite -> qa -> postpro -> tl -> prepro -> orig` into `self._lines`.
2. Apply / Refresh then used a different source (`step_data["lines"]`) instead of the already loaded `self._lines`.
3. If that session payload was empty, Wordwrap still ran its thread and logging path, but `_process_wrap()` had nothing to wrap, so the user saw activity with no result.
4. Tag lookup still had legacy-field assumptions in some places (`tag` instead of canonical `tags`), so parser-tagged lines could miss the intended per-tag config.
5. Generic wrapping also treated `MaxLines` as an output truncation limit, which is wrong for engines such as LightVN where overflow must become another textbox instead of silent data loss.
6. LightVN injection already knew how to format dialogue into `"...\\w` blocks, but it did not reliably treat explicit wrapped multiline text as authoritative input for textbox splitting.

Main flaws:

- Too many intermediate representations for the same line: manifest line, stage input line, preview line, wrapped line, parser injection line.
- Step logic depends on both manifest data and ad hoc session caches.
- Tag resolution is duplicated instead of centralized on the canonical manifest helper.
- `MaxLines` is doing two jobs that should stay separate: validation ceiling and formatting decision.
- Engine textbox splitting happens late in the parser, while the step still tries to think in generic wrapped strings.

Why this is fragile:

- The GUI step is effectively coordinating state, wrap planning, and part of engine behavior at once.
- Helper modularity is not the problem by itself; the problem is that the helpers are not arranged around one stable intermediate format.
- Python/Tkinter threading is not the root cause here. The real issue was inconsistent state flow plus silent no-op conditions.

**Proposed Structure:**

Goal: minimal changes, keep configurability, reduce moving parts.

Keep these responsibilities:

- GUI step: user interaction, preview, persistence only.
- functions/wordwrap.py: all wrap planning and generic line breaking.
- formats/LightVN.py and other parsers: engine-specific realization of already wrapped logical lines.

Introduce one stable intermediate representation for Step 8:

- `WrapRequest`
	- `idx`
	- `source_text`
	- `tag`
	- `width_mode`
	- `width`
	- `break_char`
	- `max_lines`
	- `speaker_handling`
	- `prefer_punct_breaks`
	- `prevent_orphans`
	- `new_textbox_injection`

- `WrapResult`
	- `idx`
	- `source_text`
	- `logical_lines` list[str]
	- `line_count`
	- `overflow`
	- `runaway`
	- `wrapped_text`

Minimal-change processing flow:

1. Step 8 reads manifest stage input once and only once.
2. Step 8 resolves the primary tag once via the canonical helper.
3. Step 8 builds one `WrapRequest` per loaded line.
4. functions/wordwrap.py returns `WrapResult` using only logical wrapped lines. No textbox syntax yet.
5. `MaxLines` is used for status only:
	 - if no textbox injection exists, mark runaway
	 - if textbox injection exists, keep all logical lines and let the parser split boxes later
6. Parser injection converts `logical_lines` or newline-separated `wrapped_text` into engine syntax.
7. Output remains the only stage that emits engine-specific control sequences such as LightVN `\\w` textbox breaks.

Why this structure is better:

- The GUI no longer decides whether overflow means truncation, warning, or textbox splitting.
- Generic wrapping stays generic.
- Parsers remain responsible for engine syntax only.
- The same wrapped content can be previewed, persisted, diffed, and injected without re-deriving it from different caches.

LightVN-specific expectation under the proposed structure:

- Only `dialogue` wraps by default.
- Width is character-based.
- Existing explicit line breaks remain authoritative.
- If logical dialogue exceeds 3 lines, LightVN injection emits multiple textboxes in this exact pattern:

	`"line 1`
	`line 2`
	`line 3\\w`
	`"line 4\\w`

This keeps the engine rule where `\\w`, literal newline, and the next opening `"` must appear in that exact order.

Best minimal next step after the current fix:

- Move Step 8 wrapping into a single `build_wrap_results(lines, tag_configs, parser_info)` function in functions/wordwrap.py.
- Keep the current GUI controls and manifest format.
- Keep parser defaults editable.
- Stop adding more branching behavior inside gui/steps/wordwrap_overwrite.py.