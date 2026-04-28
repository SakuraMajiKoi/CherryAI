# Editor Redesign Draft

## Goal

Replace the separate `Full Table View`, `Patch Editor`, and workbench draft with one
non-modal `Editor` window that has two modes:

- `Full Files`
- `Lines Only`

The window should stay a separate reusable surface that does not lock the main CherryAI
window, matching the current non-modal behavior of Full Table View and API Log.

## Renaming Rules

The redesign should use these names consistently:

- `Editor` = the merged window
- `Full Files` = the full-file editing mode
- `Lines Only` = the line-level editing mode

And it should retire these standalone names once the merge lands:

- `Patch Editor`
- separate `Full Table View` window naming in the menu bar

`Lines Only` is the renamed successor to Full Table View.

`Full Files` is the recycled successor to Patch Editor.

## Mode Switch

The top-level control should be a visible switch with this presentation:

`Full Files [Switch] Lines Only`

The switch position itself must make the active mode obvious.

Requirements:

1. Switching modes should keep the same project context and selected file when possible.
2. The Editor remains single-instance per root window.
3. Reopening Editor focuses the existing window instead of creating duplicates.

## Scope Of Each Mode

### Full Files

This mode replaces the old Patch Editor behavior.

It should provide:

- staged full-file editing
- file tree navigation
- in-file search and replace
- unified diffs
- parser-backed line history
- save and reload prompts
- manifest-aware re-extraction and mapping tools

Nothing should remain as a separate `Patch Editor` product after the merge. The useful
Patch Editor functions should be reused inside `Full Files`.

### Lines Only

This mode replaces the old Full Table View naming while keeping its line-level strengths.

It should provide:

- spreadsheet-like manifest row editing
- stage-column visibility and filtering
- line-level search and replace
- light search for fast and precise line lookup before editing large files
- diff filtering
- sparse `final` editing
- row selection and bulk actions

The existing Full Table View logic should be reused, but the user-facing identity becomes
`Lines Only` inside Editor.

`Lines Only` is not manifest-only anymore in the redesign target. When users intentionally save
changed lines, the result must also participate in the staged translated-file and translated-patch
history, not only in `lines[]`.

## Relationship To Other Windows

### API Log

API Log remains a separate non-modal request viewer.

Editor should link to it directly, but API Log should not be absorbed into Editor.

### Costs / Ledger

Step 4 Costs remains the estimator.

The future `Ledger` window remains separate historical accounting.

Editor may show lightweight spend context, but it should not replace either surface.

## Shared Layout Direction

The merged Editor can still borrow from VS Code where that helps, but CherryAI terms and
state must stay primary.

Recommended layout:

- Left sidebar: file tree, search results, issue filters, checkpoints
- Center area: `Full Files` or `Lines Only` working surface
- Right sidebar: agent/chat/task surfaces
- Bottom panel: diff details, history, findings, logs, search results

## Manifest And Sync Rules

The merged window must preserve CherryAI's manifest-first model.

Rules:

1. The manifest remains the authoritative project state.
2. `Lines Only` edits affect sparse per-line fields in the manifest.
3. Both modes must keep staged translated history aligned with the manifest save that triggered the change.
4. `Full Files` saves affect staged full files plus manifest-backed editor history.
5. Parser-backed re-extraction remains mandatory whenever full-file edits need to align with
	manifest rows.
6. The extraction/input and injection/output path must gain stable source-line mapping so
	`Lines Only` diffs can target shared physical lines without ambiguity.

Compact serialization rule:

- Each manifest `lines[]` entry should be written as a single compact object line.
- Each entry must carry `idx`, `ln`, and `tags` together with its actual sparse stage fields.
- `ln` is mandatory for every saved line entry.
- `f` is optional and should be written only when multiple manifest entries originate from the same
	physical source line and therefore need a field discriminator.
- The writer should stop emitting brace-only lines for manifest objects. The opening and closing
	braces stay on the same line as object content while preserving the current indent depth.
- `filedir[]` entries should be written one object per line, for example
	`{"type": "menu?", "first_idx": 0, "last_idx": 47, "format": "lightvn", "rel_path": "ability.txt"}`.
- Embedded glossary and code-pattern objects should follow the same one-object-per-line compact
	writer rule instead of expanding every key onto its own line.

Tag-centered metadata rule:

- The redesign should move line-local recovery metadata such as `ellipsis_counts`, `dedup_map`, and
	`placeholder_captured` into canonical `tags`-driven read/write handling instead of keeping those
	as separate manifest areas for the same row-local facts.
- Extraction/input, `Lines Only`, and injection/output should read the same row-local tag metadata so
	diffing, targeted rebuilds, and patch recording all resolve from one manifest source of truth.

Patch-history rule:

- The manifest should keep one patch-history entry per produced diff patch for a file.
- The actual diff patch content plus any apply/rebuild instructions belong in the staged patch folder,
	not duplicated as multiple manifest rows.
- `EditorState.files[rel_path]` should therefore reference the current translated patch artifact and its
	bounded history entries instead of becoming a second patch store.
- Individual patch-history entries may optionally carry a user-provided change label so later lookup can
	find a named edit quickly without changing the one-entry-per-diff-patch rule.

Required explicit actions:

- Refresh From Manifest
- Refresh From Staged File
- Re-extract Current File
- Show Manifest Line Mapping

## Required Directory Model

The old draft treated `Patch/` too broadly. The redesign should use four distinct staged
locations.

### `Original/`

- stores the very first staged source snapshot for the project
- must copy the entire loaded folder tree, not only files with parseable content or supported file types
- remains the baseline for future patch comparison

### `Translated/`

- stores the latest full translated output
- is overwritten by Editor saves and by Output when a newer full-file result is produced
- acts as the current editable working tree for `Full Files`
- when it already exists, `Lines Only` saves must also update the affected file there quickly and accurately

### `Patch/Original/`

- stores forward patches relative to `Original/`
- should use file hashes first
- same hash = skip
- different hash = diff when the file type supports it, otherwise copy the entire file
- new file = add full file or patch record as appropriate

### `Patch/Translated/`

- stores reverse patches and rollback material for `Translated/`
- captures prior translated states before Editor save overwrites or Output overwrites
- stores line-scoped patch artifacts from `Lines Only` saves when those edits change a file
- may exist even before a staged `Translated/` file exists for that file
- is the primary patch history source for both `Full Files` and `Lines Only`

## Save Rules

### Editor Save

When the user saves in `Full Files`:

1. Compare the current staged `Translated/` file against the new save target.
2. Record rollback material in `Patch/Translated/` before overwriting `Translated/`.
3. Update `Translated/` with the new full-file content.
4. Update `EditorState.files` with save metadata, diffs, and bounded history.

### Lines Only Save

When the user saves changed lines in `Lines Only`:

1. Use a light file-scoped search path to find target rows quickly and precisely by file, line index,
	original text, and the currently selected stage.
2. Persist the chosen sparse line-field changes into the manifest first, including the stable `ln`
	mapping and optional `f` discriminator needed for rows that share one physical source line.
3. The chosen saved field for each changed row must become the latest effective entry for that `idx` in the
	manifest stage chain used by the save action.
4. Rebuild or surgically update the affected translated file content for that file from the manifest-backed
	line set.
5. If a staged `Translated/` file already exists, update that file with the new line content, compare the
	before/after state, and record rollback material in `Patch/Translated/` before finalizing the overwrite.
6. If no staged `Translated/` file exists yet, still write a translated patch artifact plus patch
	instructions into `Patch/Translated/` so the edit history is recorded before any Step 9 injection run.
7. Keep exactly one manifest patch-history entry for the produced diff patch and point it at the patch
	artifact/instruction payload stored under `Patch/Translated/`.
8. Allow the save to optionally attach a human-readable change name so later search can find the saved edit
	by label in addition to file and line targeting.

This rule means `Translated/` may be absent for a file while translated patch history already exists.
Patch recording is mandatory; `Translated/` creation is conditional.

Performance rule:

- The `Lines Only` path should prefer indexed file/row targeting and targeted file updates over full
	project rebuilds so repeated small edits remain fast even when many changes are made in one session.
- Injection/output should be able to use `ln` plus optional `f` as the direct patch/update key so
	shared-line formats do not require broad rescans just to apply a few changed rows.

### Output Write

When Step 9 writes a newer full translated file:

1. Compare against the current `Translated/` file.
2. Store rollback material in `Patch/Translated/`.
3. Overwrite `Translated/` with the newest full output.

### Original Update / Patch Intake

When original files are compared or refreshed later:

1. Hash staged `Original/` files against the new incoming originals.
2. Skip identical files.
3. Write forward diffs or whole-file copies into `Patch/Original/`.
4. Preserve enough data for merge, compare, and future revert workflows.

## Diff Model

The merged Editor should support at least these comparisons:

1. `Original/` vs current `Translated/`
2. current `Translated/` vs prior translated state from `Patch/Translated/`
3. `Original/` vs staged original patch data from `Patch/Original/`
4. manifest stage comparisons for selected rows or files

## Search And Replace

The merged Editor should unify the current strengths of Full Table View and Patch Editor.

Required scopes:

- active file
- current mode
- project-wide
- current visible columns or stages for `Lines Only`

The `Lines Only` search path should stay lightweight and precise rather than becoming a second heavy
full-text editor. Its purpose is to jump to the correct manifest-backed rows in large files so line
edits can be saved into translated patch history without ambiguity.

Recommended match keys for fast and accurate lookup:

- file
- global `idx`
- per-file line number when available
- original text
- current latest stage text
- optional change label

Required behavior:

- regex mode
- next and previous
- replace current
- replace all
- results list

## Terminology

Prefer CherryAI-native terms:

- checkpoint
- staged original
- staged translated
- patch history
- manifest diff

Avoid pretending there is a generic Git repository when the actual state is staged and
manifest-driven.

## Phase Review Gates

### Phase 1: Editor Merge Review

Review before implementation:

1. Final window naming and menu-bar naming.
2. The exact switch control behavior.
3. What moves into `Full Files` versus `Lines Only`.
4. What remains separate, especially API Log and Ledger.
5. The manifest IO upgrade that `Lines Only` depends on.

### Phase 2: Full Files Review

Review before implementation:

1. Save semantics for `Translated/` and `Patch/Translated/`.
2. Diff panes and history panes.
3. Re-extraction and manifest mapping actions.
4. Single-window reuse and focus behavior.
5. How compact manifest rows and one-line patch metadata are surfaced in history views.

### Phase 3: Lines Only Review

Review before implementation:

1. How existing Full Table View actions map into Editor.
2. Shared file selection and project context between modes.
3. Which controls stay mode-specific versus shared.
4. The exact light-search match keys for precise row targeting in large files.
5. The save path when `Translated/` does not exist yet.
6. The one-entry-per-diff-patch manifest rule.
7. How optional change labels are stored and searched later.
8. The `ln` / optional `f` manifest mapping contract for shared-line parser formats.
9. Which row-local metadata is written and read through canonical `tags`.

### Phase 4: Manifest IO Review

Review before implementation:

1. `ln` is mandatory for every manifest row and `f` is written only when one physical line yields
	multiple entries.
2. `idx`, `ln`, optional `f`, and `tags` stay on the same compact line object as the stage payload.
3. `filedir[]`, glossary objects, and code-pattern objects use one-object-per-line formatting.
4. Braces are never written alone on their own line.
5. `ellipsis_counts`, `dedup_map`, and `placeholder_captured` are read and written through canonical
	tag-centered metadata instead of separate row-local stores.
6. Extraction/input and injection/output use the same manifest mapping so `Lines Only` diffing and
	patch application stay stable.

## Test Plan

The redesign should add focused script coverage for:

1. Editor window single-instance reuse.
2. Mode switching between `Full Files` and `Lines Only`.
3. Selection and file-context carry-over across the switch.
4. `Lines Only` light-search targeting for large files.
5. Save behavior into `Translated/` plus reverse-patch capture in `Patch/Translated/`.
6. `Lines Only` patch recording when `Translated/` does not exist yet.
7. Latest-stage precedence for each changed `idx` after a `Lines Only` save.
8. Optional named-change lookup in patch history.
9. One manifest patch-history entry per produced diff patch.
10. Hash and diff behavior for `Patch/Original/`.
11. Manifest history continuity in `EditorState.files` after the rename.
12. Shared search and replace behavior across both modes.
13. Manifest round-trip for mandatory `ln`, optional `f`, and compact one-row-per-object output.
14. Shared-line parser formats diff and inject correctly from `ln` plus optional `f`.
15. `filedir[]`, glossary objects, and code-pattern objects are emitted in the compact writer form.
16. `ellipsis_counts`, `dedup_map`, and `placeholder_captured` survive read/write through canonical
	tag-centered metadata.

## Summary

The new target is not a separate Translation Workbench beside Full Table View and Patch
Editor.

The new target is one non-modal `Editor` window with two clear modes:

- `Full Files` for full-file staged editing
- `Lines Only` for manifest-row editing

backed by a staged directory model that cleanly separates baseline originals, current
translated files, forward original patches, and reverse translated patches.